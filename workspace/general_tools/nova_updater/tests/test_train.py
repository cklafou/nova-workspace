# @nova: Tests LoRA training jobs: data checks, bundles and checksums, the loss-mask template patch on real Qwen templates, and RunPod runs that always stop the pod.
"""Run: python -m unittest discover -s general_tools/nova_updater/tests -v"""
import hashlib
import json
from pathlib import Path
import types
import unittest
import zipfile

from support import Workspace
from nova_updater import jobs, runpod, train
from nova_updater.pod import template_gen

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROW = {"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hey."}]}


class Specs(Workspace):
    def data(self, name="core.jsonl", rows=3, row=ROW):
        path = self.ws / "_admin" / "Training_stuff" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(row) for _ in range(rows)) + "\n", encoding="utf-8")
        return f"_admin/Training_stuff/{name}"

    def spec(self, **extra):
        request = {"base_model_id": "unsloth/Qwen3.8-27B", "data_files": [self.data()], "preset": "personality"}
        request.update(extra)
        return train.prepare_spec(request)

    def test_v7_recipe_is_the_default(self):
        spec = self.spec()
        self.assertEqual((spec["params"]["r"], spec["params"]["alpha"], spec["params"]["epochs"]), (16, 32, 2))
        self.assertEqual(spec["base_family"], "qwen3.8")
        self.assertTrue(spec["output_name"].startswith("nova_core_qwen38_"))
        self.assertFalse(spec["activate"])  # A/B both epochs before equipping

    def test_bad_data_and_limits_are_refused(self):
        bad = self.data("bad.jsonl", row={"messages": [{"role": "user", "content": "no answer"}]})
        with self.assertRaises(train.TrainError):
            train.prepare_spec({"base_model_id": "unsloth/Qwen3.8-27B", "data_files": [bad]})
        with self.assertRaises(train.TrainError):
            self.spec(params={"lr": 0.5})
        with self.assertRaises(train.TrainError):
            self.spec(params={"mystery": 1})

    def test_bundle_is_checksummed_and_exported(self):
        out = train.export(self.spec(output_name="t1"))
        bundle = self.ws / out["bundle"]["dir"]
        for line in (bundle / "inputs.sha256").read_text().splitlines():
            digest, name = line.split("  ")
            self.assertEqual(hashlib.sha256((bundle / name).read_bytes()).hexdigest(), digest)
        job = json.loads((bundle / "job.json").read_text())
        self.assertEqual((job["base_model_id"], job["data"][0]["rows"]), ("unsloth/Qwen3.8-27B", 3))
        names = zipfile.ZipFile(self.ws / out["zip"]).namelist()
        self.assertIn("t1/run_on_pod.sh", names)
        self.assertIn("t1/template_gen.py", names)

    def test_edited_data_after_review_is_refused(self):
        spec = self.spec()
        (self.ws / spec["data"][0]["path"]).write_text(json.dumps(ROW) + "\n", encoding="utf-8")
        with self.assertRaises(train.TrainError):
            train.build_bundle(spec, self.ws / "Temp" / "b")

    def test_outputs_install_only_when_checksums_match(self):
        spec = self.spec()
        out = self.ws / "Temp" / "gguf_out"
        out.mkdir(parents=True)
        (out / "nova_core_qwen38_epoch1.gguf").write_bytes(b"adapter-1")
        (out / "nova_core_qwen38_epoch2.gguf").write_bytes(b"adapter-2")
        sums = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in sorted(out.glob("*.gguf")))
        (out / "SHA256SUMS.txt").write_text(sums)
        placed = train.install_outputs(spec, out)
        self.assertEqual(placed["pick"], "models/qwen3.8/nova_core_qwen38_epoch2.gguf")
        with self.assertRaises(train.TrainError):
            train.install_outputs(spec, out)  # never overwrites
        (out / "nova_core_qwen38_epoch2.gguf").write_bytes(b"tampered")
        with self.assertRaises(train.TrainError):
            train.verify_outputs(out)

    def test_activate_writes_the_launcher_line(self):
        line = train.activate_lora("models/qwen3.8/nova_core_qwen38_epoch2.gguf", 1.0)
        self.assertEqual(line, "--lora-scaled models\\qwen3.8\\nova_core_qwen38_epoch2.gguf:1")
        self.assertEqual((self.ws / "nova_body/memory/active_lora.txt").read_bytes(), (line + "\r\n").encode())


class TemplatePatch(unittest.TestCase):
    """The v7 hand patch refused Qwen3.8's template; the structural patch handles both."""

    def test_marks_both_official_templates_once(self):
        for name in ("qwen3.6-27b", "qwen3.8-27b"):
            official = (FIXTURES / f"{name}.chat_template.jinja").read_text(encoding="utf-8")
            marked = template_gen.mark(official)
            self.assertEqual(marked.count("{%- generation %}"), 1, name)
            self.assertEqual(marked.count("{%- endgeneration %}"), 1, name)
            self.assertEqual(marked.replace("{%- generation %}", "").count("<|im_start|>"),
                             official.count("<|im_start|>"), name)

    def test_unknown_shapes_are_refused(self):
        with self.assertRaises(ValueError):
            template_gen.mark("{{ messages }}")

    def test_gates_with_real_tokenizer_logic(self):
        try:
            from transformers import PreTrainedTokenizerFast
            from tokenizers import Tokenizer, decoders, models, pre_tokenizers
        except Exception:
            self.skipTest("transformers/tokenizers not installed")
        vocab = {ch: i for i, ch in enumerate(sorted(set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_[]<>|/.,:'!?\n -")))}
        base = Tokenizer(models.WordLevel(vocab=dict(vocab, **{"[UNK]": len(vocab)}), unk_token="[UNK]"))
        base.pre_tokenizer = pre_tokenizers.Split("", "isolated")
        base.decoder = decoders.Fuse()  # characters back together without spaces
        for name in ("qwen3.6-27b", "qwen3.8-27b"):
            tok = PreTrainedTokenizerFast(tokenizer_object=base, unk_token="[UNK]")
            official = (FIXTURES / f"{name}.chat_template.jinja").read_text(encoding="utf-8")
            report = template_gen.gates(tok, official, template_gen.mark(official))
            self.assertIn("GATE B ok", report)


class FakeClient:
    def __init__(self, status="EXITED", cost=2.99):
        self.status, self.cost, self.calls = status, cost, []

    def pod(self, pod_id):
        self.calls.append("get")
        running = self.status == "RUNNING"
        return {"id": pod_id, "desiredStatus": self.status, "costPerHr": self.cost,
                "publicIp": "203.0.113.5" if running else None, "portMappings": {"22": 40022} if running else {}}

    def start(self, pod_id):
        self.calls.append("start")
        self.status = "RUNNING"

    def stop(self, pod_id):
        self.calls.append("stop")
        self.status = "EXITED"

    def create(self, body):
        raise AssertionError("must reuse the configured pod")


class FakeSSH:
    """Plays the pod: training finishes on the second poll; scp down creates gguf_out with sums."""
    def __init__(self, exit_code=0):
        self.exit_code, self.polls, self.commands = exit_code, 0, []

    def __call__(self, args, capture_output=True, text=True, timeout=None):
        self.commands.append(args)
        out = ""
        if args[0] == "ssh" and "cat EXIT" in args[-1]:
            self.polls += 1
            out = (f"{self.exit_code}\n---\nstep 2/2" if self.polls >= 2 else "---\nloss 1.6")
        if args[0] == "scp" and args[-2].endswith("gguf_out"):
            dest = Path(args[-1]) / "gguf_out"
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "a_epoch1.gguf").write_bytes(b"x" * 10)
            (dest / "SHA256SUMS.txt").write_text(f"{hashlib.sha256(b'x' * 10).hexdigest()}  a_epoch1.gguf\n")
        return types.SimpleNamespace(returncode=0, stdout=out, stderr="")


class RunPodRuns(Specs):
    def runner(self, ssh, client=None, ceiling=10.0):
        key = self.ws / "id_test"
        key.write_text("private")
        r = runpod.RunPodRunner(client or FakeClient(), pod_id="pod123", ssh_key=str(key), run=ssh,
                                sleep=lambda s: None, poll=0)
        r.max_cost_usd = ceiling
        return r

    def test_success_downloads_verifies_and_stops(self):
        ssh, client = FakeSSH(), FakeClient()
        spec = self.spec(output_name="a")
        result = train.run(spec, jobs.Job("train", "t"), self.runner(ssh, client))
        self.assertEqual(result["installed"], ["models/qwen3.8/a_epoch1.gguf"])
        self.assertEqual(client.calls.count("start"), 1)
        self.assertEqual(client.calls[-1], "stop")

    def test_failure_still_stops_the_pod(self):
        client = FakeClient()
        with self.assertRaises(runpod.RunPodError):
            train.run(self.spec(), jobs.Job("train", "t"), self.runner(FakeSSH(exit_code=1), client))
        self.assertEqual(client.calls[-1], "stop")

    def test_cost_ceiling_stops_the_pod(self):
        client = FakeClient(cost=1000.0)
        clock = iter(range(0, 10 ** 7, 3600))
        r = self.runner(FakeSSH(), client, ceiling=5.0)
        r._clock = lambda: next(clock)
        with self.assertRaises(runpod.RunPodError):
            r.run(self.ws / "Temp" / "b" / "bundle", self.ws / "Temp" / "b" / "gguf_out", jobs.Job("train", "t"))
        self.assertEqual(client.calls[-1], "stop")

    def test_no_ceiling_no_pod(self):
        client = FakeClient()
        r = self.runner(FakeSSH(), client)
        r.max_cost_usd = None
        with self.assertRaises(runpod.RunPodError):
            r.run(self.ws / "x", self.ws / "y", jobs.Job("train", "t"))
        self.assertEqual(client.calls, [])

    def test_start_needs_a_confirmed_ceiling_at_least_the_estimate(self):
        request = {"base_model_id": "unsloth/Qwen3.8-27B", "data_files": [self.data()], "runner": "runpod"}
        factory = lambda spec: self.runner(FakeSSH(), FakeClient())
        with self.assertRaises(train.TrainError):
            train.start(request, confirm={"max_cost_usd": 0.01}, runner_factory=factory)
        with self.assertRaises(train.TrainError):
            train.start(request, confirm=None, runner_factory=factory)

    def test_credentials_are_never_shown(self):
        view = runpod.save_credentials({"runpod_api_key": "rpa_secret_value", "pod_id": "pod123"})
        self.assertEqual((view["runpod_api_key"], view["pod_id"]), (True, "pod123"))
        self.assertNotIn("rpa_secret_value", json.dumps(view))


if __name__ == "__main__":
    unittest.main()
