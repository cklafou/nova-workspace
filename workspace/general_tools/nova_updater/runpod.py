# Last updated: 2026-10-05 18:23:37
# @nova: Run paid LoRA training, always request GPU stop, and delete only the job pod after verified local adapters and provenance are preserved.
"""RunPod runner for LoRA training.

Needs, in the local credentials file (never in the project):
    runpod_api_key   your RunPod API key
    ssh_key_path     private key whose public half is in RunPod > Settings > SSH Public Keys
    pod_id           optional: your existing pod (the v6/v7 one keeps llama.cpp and caches)
    hf_token         optional: for gated base models / higher Hugging Face rate limits

Spending rules: a paid run needs explicit confirmation and the provider's one-hour starting
credit. The prepaid wallet is the spending limit: Nova never recharges it or stops at a custom
run ceiling. Stop is requested on success, failure or cancellation. Only after local verification
and installation may finalization delete this job's pod and its attached storage. Failed or cancelled
runs retain recovery data and report storage costs. Separate network volumes are never deleted.
"""
from __future__ import annotations

import json
import math
from decimal import Decimal, ROUND_CEILING
import re
import os
from pathlib import Path
import shlex
import subprocess
import time
import threading

from . import jobs, net, paths, store

REST = "https://rest.runpod.io/v1"
GRAPHQL = "https://api.runpod.io/graphql"
BILLING_URL = "https://console.runpod.io/user/billing"
DEFAULT_DATA_CENTERS = ("AP-JP-1",)  # Japan: explicit nearby-Korea preference, never global fallback.
DEFAULT_IMAGE = "runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404"
DEFAULT_PER_HOUR = 3.0           # v6 actual on an H100 SXM was $3.01/h
COST_MARGIN = 1.25
CREDENTIAL_KEYS = ("runpod_api_key", "ssh_key_path", "pod_id", "hf_token")
_CREDENTIALS_LOCK = threading.RLock()


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


def _write_credentials(data):
    target = paths.credentials_path()
    store.atomic_write_text(target, json.dumps(data, indent=2) + "\n")
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass


def save_credentials(changes: dict) -> dict:
    """Merge user settings atomically with cleanup's compare-and-clear operation."""
    with _CREDENTIALS_LOCK:
        data = load_credentials()
        for key in CREDENTIAL_KEYS:
            if key in (changes or {}):
                value = str(changes[key] or "").strip()
                if value:
                    data[key] = value
                else:
                    data.pop(key, None)
        _write_credentials(data)
        return credentials_view()


def clear_deleted_pod(pod_id: str) -> bool:
    """Forget only the confirmed-deleted pod; preserve a newly selected pod and all secrets."""
    with _CREDENTIALS_LOCK:
        data = load_credentials()
        if data.get("pod_id") != pod_id:
            return False
        data.pop("pod_id")
        _write_credentials(data)
        return True


def _amount(value, name):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a nonnegative finite amount")
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a nonnegative finite amount") from None
    if not math.isfinite(amount) or amount < 0:
        raise ValueError(f"{name} must be a nonnegative finite amount")
    return amount


def funding_status(required_usd=None, per_hour=None, client=None) -> dict:
    """Read prepaid credits only; never charge, recharge or change an account.

    Sources: https://graphql-spec.runpod.io/#query-myself (clientBalance),
    https://docs.runpod.io/accounts-billing/billing (one-hour deployment minimum).
    Authentication follows runpod/runpod-python's official Bearer GraphQL client.
    """
    requested = _amount(required_usd, "required_usd")
    hourly = _amount(per_hour, "per_hour")
    required = hourly  # Provider deployment minimum; the whole-run estimate is advisory.
    result = {"state": "unavailable", "balance_usd": None, "required_usd": required,
              "shortfall_usd": None, "estimated_cost_usd": requested, "minimum_start_usd": hourly,
              "billing_url": BILLING_URL, "checked_at": store.now_iso(), "message": "",
              "estimate_exceeds_balance": False}
    if client is None:
        key = load_credentials().get("runpod_api_key")
        if not key:
            result.update(state="unconfigured", message="Add a RunPod API key in updater Settings to check credit. Signing in with Google in your browser does not configure Nova's API access.")
            return result
        client = RunPodClient(key)
    try:
        balance = client.balance()
        if isinstance(balance, bool) or not isinstance(balance, (int, float)) or not math.isfinite(balance):
            raise RunPodError("Invalid balance response")
    except Exception:
        result["message"] = "RunPod balance is unavailable, not zero. Check API-key access or the RunPod service and retry; no paid training will start without a verified balance."
        return result
    result["balance_usd"] = balance
    result["estimate_exceeds_balance"] = requested is not None and requested > balance
    if required is None:
        result.update(state="available", message=f"RunPod prepaid balance: ${balance:.2f}. Preview training to compare it with the estimated cost.")
    elif balance < required:
        shortfall = float((Decimal(str(required)) - Decimal(str(balance))).quantize(Decimal("0.01"), rounding=ROUND_CEILING))
        result.update(state="insufficient", shortfall_usd=shortfall,
                      message=f"RunPod credit is insufficient: ${balance:.2f} available; at least ${required:.2f} needed. Add at least ${shortfall:.2f} in RunPod Billing, then recheck. Nova will not recharge automatically.")
    else:
        result.update(state="sufficient", shortfall_usd=0.0,
                      message=f"${balance:.2f} available; the provider requires ${required:.2f} for one GPU hour. Other resources and storage can also consume credit.")
    if result["estimate_exceeds_balance"]:
        result["message"] += f" The estimated GPU run cost (${requested:.2f}) exceeds this balance; RunPod may stop the pod if prepaid credit runs out. Nova will not recharge automatically."
    return result


class RunPodClient:
    def __init__(self, api_key: str, send=None, get=None):
        if not api_key:
            raise RunPodError("Add your RunPod API key in the updater settings first.")
        self._key = api_key
        self._send = send or net.send_json
        self._get = get or net.get_json

    def _headers(self) -> dict:
        return {"Authorization": "Bearer " + self._key}

    def balance(self) -> float:
        """Only request credit; omit profile, billing-method and identity fields."""
        try:
            reply = self._send(GRAPHQL, "POST", {"query": "query NovaFunding { myself { clientBalance } }"}, self._headers())
            if not isinstance(reply, dict) or reply.get("errors"):
                raise RunPodError("Balance query refused")
            value = reply.get("data", {}).get("myself", {}).get("clientBalance")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise RunPodError("Balance query did not return a numeric credit balance")
            return float(value)
        except Exception:
            # Provider error bodies may contain account data. Never echo them or credentials.
            raise RunPodError("Could not verify RunPod credit balance; check API-key access and try again.") from None

    def pod(self, pod_id: str) -> dict:
        return self._get(f"{REST}/pods/{pod_id}", None, self._headers(), 20)

    def pods(self) -> list:
        data = self._get(f"{REST}/pods", None, self._headers(), 20)
        return data if isinstance(data, list) else (data or {}).get("pods", [])

    def start(self, pod_id: str) -> dict:
        return self._send(f"{REST}/pods/{pod_id}/start", "POST", None, self._headers())

    def stop(self, pod_id: str) -> dict:
        return self._send(f"{REST}/pods/{pod_id}/stop", "POST", None, self._headers())

    def delete(self, pod_id: str) -> dict:
        # Pod-scoped only: never address or delete a shared network-volume resource.
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", str(pod_id)):
            raise RunPodError("Invalid RunPod pod identifier; no deletion requested.")
        return self._send(f"{REST}/pods/{pod_id}", "DELETE", None, self._headers())

    def create(self, body: dict) -> dict:
        return self._send(f"{REST}/pods", "POST", body, self._headers())


class RunPodRunner:
    def __init__(self, client: RunPodClient, pod_id: str | None = None, ssh_key: str | None = None,
                 gpu: str = "NVIDIA H100 80GB HBM3", image: str = DEFAULT_IMAGE, hf_token: str | None = None,
                 run=subprocess.run, sleep=time.sleep, poll: float = 30.0, clock=time.monotonic,
                 data_center_ids=None):
        self.client, self.pod_id, self.gpu, self.image = client, pod_id or None, gpu, image
        self.ssh_key = ssh_key or str(Path.home() / ".ssh" / "id_ed25519")
        self.hf_token, self._run, self._sleep, self.poll, self._clock = hf_token, run, sleep, poll, clock
        self.paid_confirmed = False
        self.cost_summary = {}
        self._run_pod_id = None
        self._downloaded_job_id = None
        self._network_volume_id = None
        self.known_hosts = paths.state_dir() / "runpod_known_hosts"
        self.data_center_ids = list(DEFAULT_DATA_CENTERS if data_center_ids is None else data_center_ids)
        if not self.data_center_ids or any(not isinstance(value, str) or not re.fullmatch(r"[A-Z]{2,3}-[A-Z0-9]+-[0-9]+", value) for value in self.data_center_ids):
            raise RunPodError("Choose one or more explicit RunPod data centers, such as AP-JP-1 (Japan).")
        self._required_funds = None
        self._estimate_hours = None

    @classmethod
    def from_credentials(cls, spec: dict | None = None) -> "RunPodRunner":
        creds = load_credentials()
        return cls(RunPodClient(creds.get("runpod_api_key", "")), creds.get("pod_id"), creds.get("ssh_key_path"),
                   gpu=(spec or {}).get("gpu") or "NVIDIA H100 80GB HBM3", hf_token=creds.get("hf_token"),
                   data_center_ids=(spec or {}).get("data_center_ids"))

    def _hourly_rate(self):
        per_hour, source = DEFAULT_PER_HOUR, "typical H100 price"
        if self.pod_id:
            try:
                info = self.client.pod(self.pod_id)
                if info.get("costPerHr"):
                    per_hour, source = float(info["costPerHr"]), "your pod's price"
            except net.NetError:
                pass
        return per_hour, source

    def estimate(self, spec: dict) -> dict:
        per_hour, source = self._hourly_rate()
        hours = float(spec.get("estimate_hours", 1.0))
        cost = round(per_hour * hours * COST_MARGIN, 2)
        self._required_funds = cost
        self._estimate_hours = hours
        return {"per_hour": per_hour, "hours": hours, "cost_usd": cost,
                "basis": f"{source}, {hours} h estimate, +{int((COST_MARGIN - 1) * 100)}% margin. New-pod rates are provisional until RunPod returns the actual price; storage is additional.",
                "funding": funding_status(cost, per_hour, client=self.client),
                "data_center_ids": self.data_center_ids, "reuses_existing_pod": bool(self.pod_id)}

    def _publish_cost(self, job: jobs.Job, started: float, per_hour: float, *, funding=None,
                      refresh_wallet=False, stop_requested=None, stop_error=None):
        """Publish estimates and observed prepaid credit, never a billing guarantee."""
        if refresh_wallet:
            funding = funding_status(self._required_funds, per_hour, client=self.client)
        summary = dict(self.cost_summary)
        elapsed = max(0.0, self._clock() - started)
        summary.update(pod_id=self.pod_id, gpu=self.gpu, per_hour=per_hour,
                       elapsed_seconds=round(elapsed, 1), estimated_gpu_cost_usd=round(elapsed / 3600 * per_hour, 4),
                       storage_included=False, billing_url=BILLING_URL)
        if funding is not None:
            if funding.get("balance_usd") is not None:
                summary.update(balance_usd=funding["balance_usd"], balance_checked_at=funding["checked_at"])
            summary["balance_error"] = funding["message"] if funding["state"] in ("unavailable", "unconfigured") else ""
            summary["funding_warning"] = funding["message"] if funding.get("estimate_exceeds_balance") else ""
        if stop_requested is not None:
            summary["stop_requested"] = stop_requested
        if stop_error is not None:
            summary["stop_error"] = stop_error
        self.cost_summary = summary
        job.set_runpod_cost(summary)

    def _publish_cleanup(self, job, **changes):
        self.cost_summary = {**self.cost_summary, **changes}
        job.set_runpod_cost(self.cost_summary)

    def retain_unverified(self, job):
        """A failed, cancelled or locally unverified job must keep its remote recovery files."""
        if not self._run_pod_id or self.cost_summary.get("pod_deleted") or self.cost_summary.get("cleanup_state") == "retained":
            return
        message = ("Pod retained for recovery because training, local verification or installation did not finish. "
                   "Pod storage continues to incur charges; check RunPod Billing.")
        self._publish_cleanup(job, cleanup_state="retained", storage_retained=True,
                              pod_deleted=False, cleanup_message=message)
        job.say("WARNING: " + message)

    def finalize_success(self, job):
        """Called only after train.run verifies installed adapters and complete local provenance."""
        if self._downloaded_job_id != job.id:
            raise RunPodError("Pod cleanup requires this job's completed download and local verification.")
        if self.cost_summary.get("pod_deleted"):
            return dict(self.cost_summary)  # Idempotent for the already-finalized attempt.
        job.check_cancel()
        pod_id = self._run_pod_id
        if not pod_id:
            raise RunPodError("No training pod is recorded for this job's cleanup.")
        job.set_step("Deleting the pod after verified local installation")
        self._publish_cleanup(job, cleanup_state="deleting", delete_requested=True,
                              delete_error="", cleanup_message="Local adapters and provenance verified; confirming pod deletion.")
        try:
            self.client.delete(pod_id)
        except Exception:
            pass  # A lost response or an already-absent pod still requires GET-404 proof.
        absent = False
        for attempt in range(6):
            try:
                self.client.pod(pod_id)
            except net.NetError as error:
                if error.status_code == 404:
                    absent = True
                    break
                if error.status_code in (400, 401, 403):
                    break
            except Exception:
                pass
            if attempt < 5:
                self._sleep(2)
        if not absent:
            error = ("RunPod pod deletion could not be confirmed. Local adapters are installed, "
                     "but retained pod storage may still incur charges; check the RunPod console.")
            try:
                self.client.stop(pod_id)
                stop = {"stop_requested": True, "stop_error": ""}
            except Exception:
                stop = {"stop_requested": False,
                        "stop_error": "RunPod did not accept the fallback stop; stop the pod in the RunPod console now."}
            self._publish_cleanup(job, cleanup_state="cleanup_failed", pod_deleted=False, storage_retained=True,
                                  delete_error=error, cleanup_message=error, **stop)
            job.say("WARNING: " + error)
            return dict(self.cost_summary)
        # HTTP 404 is actual absence, unlike an empty DELETE response or a stop request.
        message = "Pod deletion confirmed; its attached pod storage was removed."
        if self._network_volume_id:
            message += " A separate network volume remains; its storage charges continue and it was not deleted."
        cleared = False
        try:
            cleared = clear_deleted_pod(pod_id)
        except Exception:
            message += " The saved pod setting could not be cleared; clear that deleted pod ID in Settings before another run."
        self.pod_id = None  # Reusing this runner also creates a fresh pod on the next job.
        self._publish_cleanup(job, cleanup_state="terminated", pod_deleted=True, storage_retained=False,
                              delete_error="", stop_error="", cleanup_message=message,
                              cleanup_verified_at=store.now_iso(), credentials_cleared=cleared,
                              network_volume_retained=bool(self._network_volume_id))
        job.say(message)
        return dict(self.cost_summary)

    # ── SSH helpers ──────────────────────────────────────────────────────────────────────
    def _ssh(self, ip: str, port: int, command: str, timeout: float = 120) -> str:
        args = ["ssh", "-i", self.ssh_key, "-p", str(port), "-o", "StrictHostKeyChecking=accept-new",
                "-o", f"UserKnownHostsFile={self.known_hosts}", "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=20", f"root@{ip}", command]
        try:
            done = self._run(args, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            # TimeoutExpired includes argv, which can contain the optional HF_TOKEN.
            raise RunPodError(f"SSH operation timed out after {timeout:g} seconds.") from None
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
                "volumeMountPath": "/workspace", "ports": ["22/tcp"], "env": env,
                "dataCenterIds": self.data_center_ids, "dataCenterPriority": "custom"}
        try:
            created = self.client.create(body)
        except Exception:
            message = ("RunPod creation could not be confirmed in " + ", ".join(self.data_center_ids) +
                       ". Check the RunPod console for nova-lora-training before retrying: a pod may have been created, "
                       "but its ID is unknown and Nova cannot stop it automatically. No other region was selected.")
            self._publish_cleanup(job, cleanup_state="cleanup_failed", storage_retained=None, cleanup_message=message)
            raise RunPodError(message) from None
        pod_id = created.get("id")
        if not pod_id:
            message = "RunPod returned no pod ID. Check nova-lora-training in the console; creation may have succeeded and automatic stop is unavailable."
            self._publish_cleanup(job, cleanup_state="cleanup_failed", storage_retained=None, cleanup_message=message)
            raise RunPodError(message)
        self.pod_id = pod_id
        job.say(f"Created pod {pod_id} ({self.gpu}).")
        return pod_id

    def _wait_ssh(self, pod_id: str, job: jobs.Job, timeout: float = 900) -> tuple:
        deadline = self._clock() + timeout
        while self._clock() < deadline:
            job.check_cancel()
            info = self.client.pod(pod_id)
            mapping = info.get("portMappings") or {}
            port = mapping.get("22") or mapping.get(22)
            if info.get("desiredStatus") == "RUNNING" and info.get("publicIp") and port:
                try:
                    # The provider publishes mapped ports before the image's sshd is ready.
                    self._ssh(info["publicIp"], int(port), "true", timeout=30)
                except (RunPodError, subprocess.TimeoutExpired):
                    pass
                else:
                    return info["publicIp"], int(port)
            self._sleep(10)
        raise RunPodError("The pod did not accept SSH (port 22) within 15 minutes.")

    def run(self, bundle_dir: Path, out_dir: Path, job: jobs.Job) -> Path:
        if self.paid_confirmed is not True:
            raise RunPodError("Paid training was not explicitly confirmed; refusing to start a pod.")
        job.check_cancel()
        bundle_dir, out_dir = Path(bundle_dir), Path(out_dir)
        if not Path(self.ssh_key).is_file():
            raise RunPodError(f"SSH key not found at {self.ssh_key}; set ssh_key_path in the updater settings.")
        per_hour, _ = self._hourly_rate()
        funding = funding_status(self._required_funds, per_hour, client=self.client)
        if funding["state"] != "sufficient":
            raise RunPodError(funding["message"] + " No paid pod was started. " + BILLING_URL)
        job.say(f"Funding checked: ${funding['balance_usd']:.2f} available; ${funding['required_usd']:.2f} required.")
        job.check_cancel()
        job.set_step("Starting the RunPod pod")
        started = self._clock()
        pod_id = None
        self._run_pod_id = self._downloaded_job_id = self._network_volume_id = None
        self.cost_summary = {"cleanup_state": "pending_verification", "pod_deleted": False,
                             "delete_requested": False, "delete_error": "", "storage_retained": True,
                             "cleanup_message": "Pod is retained until local adapters and provenance are verified.",
                             "cleanup_verified_at": None, "credentials_cleared": False}
        self._publish_cost(job, started, per_hour, funding=funding, stop_requested=False, stop_error="")
        # Persistent input packages are named runs under a friendly model directory.
        # Give every paid attempt its own remote folder; never reuse an old EXIT/checkpoint.
        remote = f"/workspace/nova_jobs/{job.id}"
        remote_bundle = remote + "/bundle"
        launched = False
        try:
            pod_id = self.pod_id or self._create(job)
            self._run_pod_id = pod_id
            info = self.client.pod(pod_id)
            self._network_volume_id = info.get("networkVolumeId")
            self._publish_cleanup(job, network_volume_retained=bool(self._network_volume_id))
            try:
                actual_rate = float(info["costPerHr"])
                if not math.isfinite(actual_rate) or actual_rate <= 0:
                    raise ValueError("invalid pod rate")
            except (KeyError, TypeError, ValueError):
                raise RunPodError("RunPod did not report a valid actual GPU price; stopped before uploading or training.") from None
            per_hour = actual_rate
            actual_estimate = (round(per_hour * self._estimate_hours * COST_MARGIN, 2)
                               if self._estimate_hours is not None else self._required_funds)
            self._required_funds = actual_estimate
            actual_funding = funding_status(actual_estimate, per_hour, client=self.client)
            self._publish_cost(job, started, per_hour, funding=actual_funding)
            if actual_funding["state"] != "sufficient":
                raise RunPodError(actual_funding["message"] + " Pod stopped before training.")
            job.say(f"Actual pod GPU rate ${per_hour:.2f}/h. Prepaid wallet is the limit; no automatic recharge or custom run cap. Storage is additional.")
            if actual_funding.get("estimate_exceeds_balance"):
                job.say(actual_funding["message"])
            job.check_cancel()
            if info.get("desiredStatus") != "RUNNING":
                self.client.start(pod_id)
            ip, port = self._wait_ssh(pod_id, job)
            job.set_step(f"Uploading the bundle to {ip}:{port}")
            self._ssh(ip, port, f"mkdir -p /workspace/nova_jobs && mkdir {shlex.quote(remote)}")
            # The destination does not exist: scp creates exactly 'bundle', irrespective
            # of the local package's descriptive basename (including spaces).
            self._scp(ip, port, str(bundle_dir), f"root@{ip}:{remote_bundle}")
            job.say(f"Remote recovery directory: {remote_bundle} (pod {pod_id}).")
            token = f"export HF_TOKEN={shlex.quote(self.hf_token)}; " if self.hf_token else ""
            job.set_step("Training on the pod (this takes a while)")
            # Validate cd/input synchronously. Background only the training command,
            # otherwise a missing directory returns SSH success and polls without training.
            self._ssh(ip, port, f"cd {shlex.quote(remote_bundle)} && test -s run_on_pod.sh && {{ {token}"
                                "nohup bash -c 'bash run_on_pod.sh > train.log 2>&1; echo $? > EXIT' "
                                "< /dev/null > /dev/null 2>&1 & }")
            launched = True
            code = None
            while code is None:
                job.check_cancel()
                self._sleep(self.poll)
                try:
                    live_rate = float(self.client.pod(pod_id).get("costPerHr", per_hour))
                    if math.isfinite(live_rate) and live_rate > 0:
                        per_hour = live_rate
                except (net.NetError, TypeError, ValueError):
                    pass  # Keep the last observed rate; never turn a missing price into zero.
                self._publish_cost(job, started, per_hour, refresh_wallet=True)
                out = self._ssh(ip, port, f"cd {shlex.quote(remote_bundle)} && {{ cat EXIT 2>/dev/null; echo ---; tail -n 2 train.log 2>/dev/null; }}")
                head, _, tail = out.partition("---")
                if tail.strip():
                    job.say("pod: " + tail.strip().splitlines()[-1][:200])
                if head.strip().isdigit():
                    code = int(head.strip())
            if code != 0:
                log = self._ssh(ip, port, f"tail -n 25 {shlex.quote(remote_bundle + '/train.log')}")
                raise RunPodError(f"Training stopped with exit code {code}. Last log lines:\n{log[-2000:]}")
            job.set_step("Downloading the trained adapters")
            out_dir.parent.mkdir(parents=True, exist_ok=True)
            self._scp(ip, port, f"root@{ip}:{remote_bundle}/gguf_out", str(out_dir.parent))
            job.check_cancel()
            self._downloaded_job_id = job.id
            return out_dir.parent / "gguf_out"
        except jobs.Cancelled:
            if launched:
                try:
                    self._ssh(ip, port, "pkill -f run_on_pod.sh; pkill -f train_lora.py", timeout=30)
                except Exception:
                    pass
            raise
        finally:
            # Creation can succeed before a later local check fails. Retain the id
            # early so the stop request still runs for that newly billed pod.
            pod_id = pod_id or self.pod_id
            if pod_id:
                try:
                    self.client.stop(pod_id)
                    self._publish_cost(job, started, per_hour, refresh_wallet=True, stop_requested=True, stop_error="")
                    job.say(f"Pod {pod_id} stop requested; deletion waits for verified local installation. Approx. GPU cost "
                            f"${(self._clock() - started) / 3600 * per_hour:.2f}; provider billing and storage may differ.")
                except Exception:
                    self._publish_cost(job, started, per_hour, stop_requested=False,
                                       stop_error="RunPod did not accept the stop request; stop it in the RunPod console now.")
                    job.say(f"WARNING: could not stop pod {pod_id}. Stop it in the RunPod console NOW.")
            if self._downloaded_job_id != job.id:
                self.retain_unverified(job)
