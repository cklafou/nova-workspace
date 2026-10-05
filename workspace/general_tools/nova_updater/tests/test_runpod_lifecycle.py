# Last updated: 2026-10-06 03:19:20
# @nova: Prove RunPod transfers named persistent training packages, retries SSH readiness and isolates paid attempts using local fake pods.
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess

from support import Workspace
from nova_updater import jobs, net, runpod, train


class FakePod:
    def __init__(self):
        self.calls = []
        self.deleted = set()
        self.created = 0

    def balance(self):
        return 63.11

    def create(self, body):
        self.calls.append(("create", body))
        self.created += 1
        return {"id": "fixture-h200" if self.created == 1 else f"fixture-h200-{self.created}"}

    def pod(self, pod_id):
        if pod_id in self.deleted:
            raise net.NetError("Pod not found", status_code=404)
        return {"desiredStatus": "RUNNING", "costPerHr": 4.59,
                "publicIp": "192.0.2.1", "portMappings": {"22": 40022}}

    def start(self, pod_id):
        raise AssertionError("new pod is already running")

    def stop(self, pod_id):
        self.calls.append(("stop", pod_id))

    def delete(self, pod_id):
        self.calls.append(("delete", pod_id))
        self.deleted.add(pod_id)


class PodFilesystem:
    """Model scp's directory semantics and reject commands pointed at missing directories."""
    def __init__(self, root, readiness_failures=0, lose_script=False):
        self.root = root
        self.commands = []
        self.uploads = []
        self.readiness_failures = readiness_failures
        self.lose_script = lose_script
        self.polls = 0

    def path(self, remote):
        return self.root / remote.lstrip("/")

    def __call__(self, args, **kwargs):
        self.commands.append(args)
        output = ""
        if args[0] == "scp":
            source, destination = args[-2:]
            if source.startswith("root@"):
                remote = self.path(source.split(":", 1)[1])
                assert remote.is_dir(), f"download directory missing: {remote}"
                shutil.copytree(remote, Path(destination) / remote.name)
            else:
                remote = self.path(destination.split(":", 1)[1])
                if remote.is_dir():
                    remote = remote / Path(source).name
                shutil.copytree(source, remote)
                self.uploads.append((source, remote))
                if self.lose_script:
                    (remote / "run_on_pod.sh").unlink()
        else:
            command = args[-1]
            if command == "true":
                if self.readiness_failures:
                    self.readiness_failures -= 1
                    return subprocess.CompletedProcess(args, 255, "", "Connection refused")
            elif command.startswith("mkdir -p /workspace/nova_jobs && mkdir "):
                remote = self.path(shlex.split(command)[-1])
                remote.parent.mkdir(parents=True, exist_ok=True)
                remote.mkdir()  # refuse previous attempt's EXIT/checkpoints
            elif command.startswith("cd "):
                remote = self.path(shlex.split(command)[1])
                if not remote.is_dir():
                    return subprocess.CompletedProcess(args, 1, "", "cd: directory missing")
                if "nohup" in command:
                    if not (remote / "run_on_pod.sh").is_file():
                        return subprocess.CompletedProcess(args, 1, "", "script missing")
                    assert "&& test -s run_on_pod.sh && {" in command
                    assert command.endswith("& }")  # only training is detached
                    recipe = json.loads((remote / "job.json").read_text(encoding="utf-8"))
                    outputs = remote / "gguf_out"
                    outputs.mkdir()
                    blob = b"fake trained adapter"
                    names = [f"{recipe['output_name']}_epoch{i}.gguf" for i in range(1, recipe["params"]["epochs"] + 1)]
                    for name in names:
                        (outputs / name).write_bytes(blob)
                    (outputs / "SHA256SUMS.txt").write_text("".join(hashlib.sha256(blob).hexdigest() + "  " + name + "\n" for name in names))
                    details = outputs / "training_details"
                    detail_names = ("environment.txt", "base_source.json", "tokenization_report.json",
                                    "chat_template.gen.jinja", "base_config/config.json", "README.md")
                    for name in detail_names:
                        target = details / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(b"fixture provenance")
                    (details / "SHA256SUMS.txt").write_text("".join(hashlib.sha256(b"fixture provenance").hexdigest() + "  " + name + "\n" for name in detail_names))
                elif "cat EXIT" in command:
                    self.polls += 1
                    output = "0\n---\nTRAINING COMPLETE"
            else:
                raise AssertionError(f"Unexpected fake SSH command: {command}")
        return subprocess.CompletedProcess(args, 0, output, "")


class RunPodLifecycle(Workspace):
    def spec(self):
        data = self.ws / "fixture-inputs" / "Nova Core v7.jsonl"
        data.parent.mkdir(exist_ok=True)
        row = {"messages": [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]}
        data.write_text((json.dumps(row) + "\n") * 399, encoding="utf-8")
        return train.prepare_spec({"base_model_id": "unsloth/Qwen3.8-27B", "data_files": [str(data)],
                                   "output_name": "nova_core_qwen38_v7", "runner": "runpod", "gpu": "NVIDIA H200",
                                   "data_center_ids": ["AP-JP-1"]})

    def runner(self, remote):
        key = self.ws / "fake-key"
        key.write_text("fixture only", encoding="utf-8")
        key.with_name(key.name + ".pub").write_text("ssh-ed25519 fixture", encoding="utf-8")
        client = FakePod()
        runner = runpod.RunPodRunner(client, ssh_key=str(key), gpu="NVIDIA H200", run=remote,
                                    sleep=lambda seconds: None, poll=0)
        runner.paid_confirmed = True
        return runner, client

    def test_named_persistent_package_reaches_training_download_and_install(self):
        remote = PodFilesystem(self.ws / "fake-remote", readiness_failures=2)
        runner, client = self.runner(remote)
        spec = self.spec()
        runner.estimate(spec)
        job = jobs.Job("train", "399 row H200 fixture")
        result = train.run(spec, job, runner)
        self.assertEqual(spec["rows"], 399)
        source, destination = remote.uploads[0]
        self.assertIn("Training Files", source)
        self.assertIn("Qwen 3.8 27B Dense", source)
        self.assertEqual(Path(source).name, "nova_core_qwen38_v7")
        self.assertEqual(destination, remote.path(f"/workspace/nova_jobs/{job.id}/bundle"))
        self.assertEqual(result["installed"], ["models/qwen3.8/nova_core_qwen38_v7_epoch1.gguf", "models/qwen3.8/nova_core_qwen38_v7_epoch2.gguf"])
        self.assertTrue((self.ws / result["installed"][0]).is_file())
        self.assertEqual(client.calls[0][1]["dataCenterIds"], ["AP-JP-1"])
        self.assertEqual(client.calls[0][1]["gpuTypeIds"], ["NVIDIA H200"])
        self.assertEqual(client.calls[0][1]["imageName"], runpod.DEFAULT_IMAGE)
        self.assertEqual(client.calls[-1][0], "delete")
        self.assertLess(next(i for i,c in enumerate(client.calls) if c[0] == "stop"),len(client.calls)-1)
        self.assertEqual(sum(args[-1] == "true" for args in remote.commands), 3)
        self.assertEqual(remote.polls, 1)
        summary = job.to_dict()["runpod_cost"]
        self.assertEqual(summary["balance_usd"], 63.11)
        self.assertEqual(summary["per_hour"], 4.59)
        self.assertEqual(summary["pod_id"], "fixture-h200")
        self.assertTrue(summary["stop_requested"])
        self.assertFalse(summary["storage_included"])
        self.assertTrue(summary["pod_deleted"])
        self.assertFalse(summary["storage_retained"])

    def test_reusing_inputs_has_separate_remote_attempts_and_no_stale_exit(self):
        spec = self.spec()
        package = self.ws / train.preserve_inputs(spec)["dir"]
        remote = PodFilesystem(self.ws / "fake-remote")
        seen = []
        for attempt in range(2):
            runner, client = self.runner(remote)
            job = jobs.Job("train", "retry fixture")
            output = runner.run(package, self.ws / "Temp" / str(attempt) / "gguf_out", job)
            self.assertTrue((output / "SHA256SUMS.txt").is_file())
            seen.append(remote.uploads[-1][1])
            self.assertEqual(client.calls[-1][0], "stop")
        self.assertNotEqual(seen[0], seen[1])
        self.assertEqual(remote.polls, 2)

    def test_missing_uploaded_script_fails_before_poll_and_stops(self):
        remote = PodFilesystem(self.ws / "fake-remote", lose_script=True)
        runner, client = self.runner(remote)
        with self.assertRaises(runpod.RunPodError):
            train.run(self.spec(), jobs.Job("train", "broken upload fixture"), runner)
        self.assertEqual(remote.polls, 0)
        self.assertEqual(client.calls[-1][0], "stop")

    def test_wallet_refresh_recognizes_added_credit_and_large_estimate_is_advisory(self):
        remote = PodFilesystem(self.ws / "fake-remote")
        runner, client = self.runner(remote)
        balances = iter([10.0, 10.0, 10.0, 80.0, 79.5])
        client.balance = lambda: next(balances)
        runner.estimate({"estimate_hours": 10})  # More than wallet, but wallet covers one hour.
        job = jobs.Job("train", "wallet refresh fixture")
        train.run(self.spec(), job, runner)
        summary = job.to_dict()["runpod_cost"]
        self.assertEqual(summary["balance_usd"], 79.5)
        self.assertEqual(summary["funding_warning"], "")
        self.assertEqual(summary["balance_error"], "")
        self.assertTrue(summary["stop_requested"])
        self.assertEqual(remote.polls, 1)

    def test_failure_keeps_cost_summary_and_stop_failure_is_visible(self):
        remote = PodFilesystem(self.ws / "fake-remote", lose_script=True)
        runner, client = self.runner(remote)
        def cannot_stop(pod_id):
            raise RuntimeError("provider unavailable")
        client.stop = cannot_stop
        job = jobs.Job("train", "stop failure fixture")
        with self.assertRaises(runpod.RunPodError):
            train.run(self.spec(), job, runner)
        summary = job.to_dict()["runpod_cost"]
        self.assertFalse(summary["stop_requested"])
        self.assertIn("RunPod console", summary["stop_error"])
        self.assertEqual(summary["balance_usd"], 63.11)

    def test_ssh_timeout_never_exposes_optional_token_in_job_error(self):
        runner, client = self.runner(PodFilesystem(self.ws / "fake-remote"))
        def timeout(args, **kwargs):
            raise subprocess.TimeoutExpired(args, kwargs["timeout"])
        runner._run = timeout
        with self.assertRaises(runpod.RunPodError) as caught:
            runner._ssh("192.0.2.1", 22, "export HF_TOKEN=fixture-private-token; sleep 1000", timeout=1)
        self.assertNotIn("fixture-private-token", str(caught.exception))
        self.assertIn("timed out", str(caught.exception))
        self.assertEqual(client.calls, [])
