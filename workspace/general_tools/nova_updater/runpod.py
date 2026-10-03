# @nova: Runs a training bundle on the user's RunPod pod: start it, upload over SSH, train, download, verify, and always stop (never terminate) the pod.
"""RunPod runner for LoRA training.

Needs, in the local credentials file (never in the project):
    runpod_api_key   your RunPod API key
    ssh_key_path     private key whose public half is in RunPod > Settings > SSH Public Keys
    pod_id           optional: your existing pod (the v6/v7 one keeps llama.cpp and caches)
    hf_token         optional: for gated base models / higher Hugging Face rate limits

Spending rules: a run starts only with a confirmed cost ceiling; the pod is stopped in a
`finally` block whatever happens (success, failure, cancel, ceiling reached); it is never
terminated, because Terminate wipes /workspace.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import time

from . import jobs, net, paths, store

REST = "https://rest.runpod.io/v1"
DEFAULT_IMAGE = "runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04"
DEFAULT_PER_HOUR = 3.0           # v6 actual on an H100 SXM was $3.01/h
COST_MARGIN = 1.25
CREDENTIAL_KEYS = ("runpod_api_key", "ssh_key_path", "pod_id", "hf_token")


class RunPodError(RuntimeError):
    pass


def load_credentials() -> dict:
    try:
        data = json.loads(paths.credentials_path().read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if k in CREDENTIAL_KEYS and isinstance(v, str)}
    except (OSError, ValueError):
        return {}


def credentials_view() -> dict:
    """What the UI may show: which secrets are set, never their values."""
    data = load_credentials()
    return {"path": str(paths.credentials_path()), "runpod_api_key": bool(data.get("runpod_api_key")),
            "hf_token": bool(data.get("hf_token")), "ssh_key_path": data.get("ssh_key_path", ""),
            "pod_id": data.get("pod_id", "")}


def save_credentials(changes: dict) -> dict:
    """Merge the provided fields (empty string clears one). Typed by the user in the UI."""
    data = load_credentials()
    for key in CREDENTIAL_KEYS:
        if key in (changes or {}):
            value = str(changes[key] or "").strip()
            if value:
                data[key] = value
            else:
                data.pop(key, None)
    target = paths.credentials_path()
    store.atomic_write_text(target, json.dumps(data, indent=2) + "\n")
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return credentials_view()


class RunPodClient:
    def __init__(self, api_key: str, send=None, get=None):
        if not api_key:
            raise RunPodError("Add your RunPod API key in the updater settings first.")
        self._key = api_key
        self._send = send or net.send_json
        self._get = get or net.get_json

    def _headers(self) -> dict:
        return {"Authorization": "Bearer " + self._key}

    def pod(self, pod_id: str) -> dict:
        return self._get(f"{REST}/pods/{pod_id}", None, self._headers(), 20)

    def pods(self) -> list:
        data = self._get(f"{REST}/pods", None, self._headers(), 20)
        return data if isinstance(data, list) else (data or {}).get("pods", [])

    def start(self, pod_id: str) -> dict:
        return self._send(f"{REST}/pods/{pod_id}/start", "POST", None, self._headers())

    def stop(self, pod_id: str) -> dict:
        return self._send(f"{REST}/pods/{pod_id}/stop", "POST", None, self._headers())

    def create(self, body: dict) -> dict:
        return self._send(f"{REST}/pods", "POST", body, self._headers())


class RunPodRunner:
    def __init__(self, client: RunPodClient, pod_id: str | None = None, ssh_key: str | None = None,
                 gpu: str = "NVIDIA H100 80GB HBM3", image: str = DEFAULT_IMAGE, hf_token: str | None = None,
                 run=subprocess.run, sleep=time.sleep, poll: float = 30.0, clock=time.monotonic):
        self.client, self.pod_id, self.gpu, self.image = client, pod_id or None, gpu, image
        self.ssh_key = ssh_key or str(Path.home() / ".ssh" / "id_ed25519")
        self.hf_token, self._run, self._sleep, self.poll, self._clock = hf_token, run, sleep, poll, clock
        self.max_cost_usd: float | None = None
        self.known_hosts = paths.state_dir() / "runpod_known_hosts"

    @classmethod
    def from_credentials(cls, spec: dict | None = None) -> "RunPodRunner":
        creds = load_credentials()
        return cls(RunPodClient(creds.get("runpod_api_key", "")), creds.get("pod_id"), creds.get("ssh_key_path"),
                   gpu=(spec or {}).get("gpu") or "NVIDIA H100 80GB HBM3", hf_token=creds.get("hf_token"))

    def estimate(self, spec: dict) -> dict:
        per_hour, source = DEFAULT_PER_HOUR, "typical H100 price"
        if self.pod_id:
            try:
                info = self.client.pod(self.pod_id)
                if info.get("costPerHr"):
                    per_hour, source = float(info["costPerHr"]), "your pod's price"
            except net.NetError:
                pass
        hours = float(spec.get("estimate_hours", 1.0))
        return {"per_hour": per_hour, "hours": hours, "cost_usd": round(per_hour * hours * COST_MARGIN, 2),
                "basis": f"{source}, {hours} h estimate, +{int((COST_MARGIN - 1) * 100)}% margin"}

    # ── SSH helpers ──────────────────────────────────────────────────────────────────────
    def _ssh(self, ip: str, port: int, command: str, timeout: float = 120) -> str:
        args = ["ssh", "-i", self.ssh_key, "-p", str(port), "-o", "StrictHostKeyChecking=accept-new",
                "-o", f"UserKnownHostsFile={self.known_hosts}", "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=20", f"root@{ip}", command]
        done = self._run(args, capture_output=True, text=True, timeout=timeout)
        if done.returncode != 0:
            raise RunPodError(f"ssh failed ({done.returncode}): {(done.stderr or '').strip()[-300:]}")
        return done.stdout or ""

    def _scp(self, ip: str, port: int, source: str, dest: str, timeout: float = 3600) -> None:
        args = ["scp", "-i", self.ssh_key, "-P", str(port), "-o", "StrictHostKeyChecking=accept-new",
                "-o", f"UserKnownHostsFile={self.known_hosts}", "-o", "BatchMode=yes", "-r", source, dest]
        done = self._run(args, capture_output=True, text=True, timeout=timeout)
        if done.returncode != 0:
            raise RunPodError(f"file copy failed ({done.returncode}): {(done.stderr or '').strip()[-300:]}")

    # ── pod lifecycle ───────────────────────────────────────────────────────────────────
    def _create(self, job: jobs.Job) -> str:
        public_key = Path(self.ssh_key + ".pub")
        env = {"PUBLIC_KEY": public_key.read_text(encoding="utf-8").strip()} if public_key.is_file() else {}
        body = {"name": "nova-lora-training", "imageName": self.image, "gpuTypeIds": [self.gpu], "gpuCount": 1,
                "cloudType": "SECURE", "containerDiskInGb": 200, "volumeInGb": 150,
                "volumeMountPath": "/workspace", "ports": ["22/tcp"], "env": env}
        created = self.client.create(body)
        pod_id = created.get("id")
        if not pod_id:
            raise RunPodError("RunPod did not return a pod id.")
        job.say(f"Created pod {pod_id} ({self.gpu}).")
        self.pod_id = pod_id
        return pod_id

    def _wait_ssh(self, pod_id: str, job: jobs.Job, timeout: float = 900) -> tuple:
        deadline = self._clock() + timeout
        while self._clock() < deadline:
            job.check_cancel()
            info = self.client.pod(pod_id)
            mapping = info.get("portMappings") or {}
            port = mapping.get("22") or mapping.get(22)
            if info.get("desiredStatus") == "RUNNING" and info.get("publicIp") and port:
                return info["publicIp"], int(port)
            self._sleep(10)
        raise RunPodError("The pod did not expose SSH (port 22) within 15 minutes.")

    def run(self, bundle_dir: Path, out_dir: Path, job: jobs.Job) -> Path:
        if self.max_cost_usd is None:
            raise RunPodError("No confirmed cost ceiling; refusing to start a paid pod.")
        bundle_dir, out_dir = Path(bundle_dir), Path(out_dir)
        if not Path(self.ssh_key).is_file():
            raise RunPodError(f"SSH key not found at {self.ssh_key}; set ssh_key_path in the updater settings.")
        per_hour = self.estimate({"estimate_hours": 1})["per_hour"]
        job.set_step("Starting the RunPod pod")
        pod_id = self.pod_id or self._create(job)
        started = self._clock()
        remote = f"/workspace/nova_jobs/{bundle_dir.parent.name}"
        launched = False
        try:
            info = self.client.pod(pod_id)
            if info.get("desiredStatus") != "RUNNING":
                self.client.start(pod_id)
            ip, port = self._wait_ssh(pod_id, job)
            job.set_step(f"Uploading the bundle to {ip}:{port}")
            self._ssh(ip, port, f"mkdir -p {shlex.quote(remote)}")
            self._scp(ip, port, str(bundle_dir), f"root@{ip}:{remote}/")
            token = f"export HF_TOKEN={shlex.quote(self.hf_token)}; " if self.hf_token else ""
            job.set_step("Training on the pod (this takes a while)")
            self._ssh(ip, port, f"cd {shlex.quote(remote)}/bundle && {token}nohup bash -c "
                                f"'bash run_on_pod.sh > train.log 2>&1; echo $? > EXIT' > /dev/null 2>&1 &")
            launched = True
            code = None
            while code is None:
                job.check_cancel()
                spent = (self._clock() - started) / 3600 * per_hour
                if spent > self.max_cost_usd:
                    raise RunPodError(f"Cost ceiling ${self.max_cost_usd:.2f} reached (about ${spent:.2f}); stopped.")
                self._sleep(self.poll)
                out = self._ssh(ip, port, f"cd {shlex.quote(remote)}/bundle; cat EXIT 2>/dev/null; echo ---; tail -n 2 train.log 2>/dev/null")
                head, _, tail = out.partition("---")
                if tail.strip():
                    job.say("pod: " + tail.strip().splitlines()[-1][:200])
                if head.strip().isdigit():
                    code = int(head.strip())
            if code != 0:
                log = self._ssh(ip, port, f"tail -n 25 {shlex.quote(remote)}/bundle/train.log")
                raise RunPodError(f"Training stopped with exit code {code}. Last log lines:\n{log[-2000:]}")
            job.set_step("Downloading the trained adapters")
            out_dir.parent.mkdir(parents=True, exist_ok=True)
            self._scp(ip, port, f"root@{ip}:{remote}/bundle/gguf_out", str(out_dir.parent))
            return out_dir.parent / "gguf_out"
        except jobs.Cancelled:
            if launched:
                try:
                    self._ssh(ip, port, "pkill -f run_on_pod.sh; pkill -f train_lora.py", timeout=30)
                except Exception:
                    pass
            raise
        finally:
            try:
                self.client.stop(pod_id)
                job.say(f"Pod {pod_id} stopped (not terminated). Approx. cost "
                        f"${(self._clock() - started) / 3600 * per_hour:.2f}.")
            except Exception as error:
                job.say(f"WARNING: could not stop pod {pod_id} ({error}). Stop it in the RunPod console NOW.")
