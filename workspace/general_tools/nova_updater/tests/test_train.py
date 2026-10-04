# @nova: Tests LoRA training jobs: data checks, bundles and checksums, the loss-mask template patch on real Qwen templates, and RunPod runs that always stop the pod.
"""Run: python -m unittest discover -s general_tools/nova_updater/tests -v"""
import hashlib
import json
from pathlib import Path
import types
import unittest
from unittest.mock import patch
import zipfile

from support import Workspace
from nova_updater import jobs, net, runpod, train
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
        self.assertEqual(line, '--lora-scaled "models\\qwen3.8\\nova_core_qwen38_epoch2.gguf:1"')
        self.assertEqual((self.ws / "nova_body/memory/active_lora.txt").read_bytes(), (line + "\r\n").encode())

    def test_adapter_paths_the_launcher_would_split_are_refused(self):
        self.boot("active_lora.txt", "none\r\n")
        for bad in ("models/qwen3.8/a&b.gguf", "models/qwen3.8/노바.gguf",
                    "D:/models/a.gguf", "models/a,b.gguf"):  # ':' and ',' separate FNAME:SCALE,...
            with self.assertRaises(train.TrainError):
                train.activate_lora(bad, 1.0)
        self.assertEqual((self.ws / "nova_body/memory/active_lora.txt").read_bytes(), b"none\r\n")

    def test_output_names_and_family_folders_stay_launcher_safe(self):
        self.assertEqual(self.spec(output_name="노바 v8 (final)!")["output_name"], "v8final")
        self.assertTrue(self.spec(output_name="노바")["output_name"].startswith("nova_core_qwen38_"))
        for family in ("../outside", "qwen 3.8", ".."):
            with self.assertRaises(train.TrainError):
                self.spec(base_family=family)


class Activation(Workspace):
    def setUp(self):
        super().setUp()
        self.adapter = "models/qwen3.8/nova_core_qwen38_epoch2.gguf"
        (self.ws / self.adapter).parent.mkdir(parents=True, exist_ok=True)
        (self.ws / self.adapter).write_bytes(b"adapter")
        self.boot("active_lora.txt", "--lora-scaled models\\qwen3.6\\nova_core_v7_epoch2.gguf:1.0\r\n")
        self.before = (self.ws / "nova_body/memory/active_lora.txt").read_bytes()

    def lora_line(self):
        return (self.ws / "nova_body/memory/active_lora.txt").read_bytes()

    def test_verified_when_llama_server_lists_the_adapter(self):
        result = train.activate(self.adapter, 1.0, restart=lambda: {"ok": True},
                                probe=lambda: ["nova_core_qwen38_epoch2.gguf"], timeout=1, poll=0.01)
        self.assertTrue(result["ok"] and result["verified"])

    def test_restart_failure_is_reported_and_undone(self):
        calls = []

        def restart():
            calls.append(1)
            if len(calls) == 1:
                raise OSError("port busy")
            return {"ok": True}
        result = train.activate(self.adapter, 1.0, restart=restart, probe=lambda: [], timeout=0.05, poll=0.01)
        self.assertFalse(result["ok"])
        self.assertIn("port busy", result["error"])
        self.assertEqual((result["restored_previous"], result["previous_restart"]), (True, "ok"))
        self.assertEqual(self.lora_line(), self.before)

    def test_running_bare_is_a_failure_not_a_success(self):
        result = train.activate(self.adapter, 1.0, restart=lambda: {"ok": True}, probe=lambda: [],
                                timeout=0.05, poll=0.01)
        self.assertFalse(result["ok"])
        self.assertIn("running without", result["error"])
        self.assertEqual(self.lora_line(), self.before)

    def test_chat_only_defers(self):
        result = train.activate(self.adapter, 1.0, restart=lambda: {"ok": False, "chat_only": True})
        self.assertTrue(result["ok"])
        self.assertFalse(result["verified"])


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
        self.deleted = False

    def balance(self):
        self.calls.append("balance")
        return 100000.0

    def pod(self, pod_id):
        self.calls.append("get")
        if self.deleted:
            raise net.NetError("Pod not found", status_code=404)
        running = self.status == "RUNNING"
        return {"id": pod_id, "desiredStatus": self.status, "costPerHr": self.cost,
                "publicIp": "203.0.113.5" if running else None, "portMappings": {"22": 40022} if running else {}}

    def start(self, pod_id):
        self.calls.append("start")
        self.status = "RUNNING"

    def stop(self, pod_id):
        self.calls.append("stop")
        self.status = "EXITED"

    def delete(self, pod_id):
        self.calls.append("delete")
        self.deleted = True

    def create(self, body):
        raise AssertionError("must reuse the configured pod")


class FakeSSH:
    """Plays the pod: training finishes on the second poll; scp down creates gguf_out with sums."""
    def __init__(self, exit_code=0):
        self.exit_code, self.polls, self.commands = exit_code, 0, []
        self.recipe = None

    def __call__(self, args, capture_output=True, text=True, timeout=None):
        self.commands.append(args)
        out = ""
        if args[0] == "ssh" and "cat EXIT" in args[-1]:
            self.polls += 1
            out = (f"{self.exit_code}\n---\nstep 2/2" if self.polls >= 2 else "---\nloss 1.6")
        if args[0] == "scp" and not args[-2].endswith("gguf_out"):
            self.recipe = json.loads((Path(args[-2]) / "job.json").read_text(encoding="utf-8"))
        if args[0] == "scp" and args[-2].endswith("gguf_out"):
            dest = Path(args[-1]) / "gguf_out"
            dest.mkdir(parents=True, exist_ok=True)
            names = [f"{self.recipe['output_name']}_epoch{i}.gguf" for i in range(1, self.recipe["params"]["epochs"] + 1)]
            for name in names:
                (dest / name).write_bytes(b"x" * 10)
            (dest / "SHA256SUMS.txt").write_text("".join(f"{hashlib.sha256(b'x' * 10).hexdigest()}  {name}\n" for name in names))
            details = dest / "training_details"
            detail_names = ("environment.txt", "base_source.json", "tokenization_report.json",
                            "chat_template.gen.jinja", "base_config/config.json", "README.md")
            for name in detail_names:
                target = details / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"fixture")
            (details / "SHA256SUMS.txt").write_text("".join(f"{hashlib.sha256(b'fixture').hexdigest()}  {name}\n" for name in detail_names))
        return types.SimpleNamespace(returncode=0, stdout=out, stderr="")


class RunPodRuns(Specs):
    def runner(self, ssh, client=None):
        key = self.ws / "id_test"
        key.write_text("private")
        r = runpod.RunPodRunner(client or FakeClient(), pod_id="pod123", ssh_key=str(key), run=ssh,
                                sleep=lambda s: None, poll=0)
        r.paid_confirmed = True
        return r

    def test_success_downloads_verifies_and_stops(self):
        ssh, client = FakeSSH(), FakeClient()
        spec = self.spec(output_name="a")
        result = train.run(spec, jobs.Job("train", "t"), self.runner(ssh, client))
        self.assertEqual(result["installed"], ["models/qwen3.8/a_epoch1.gguf", "models/qwen3.8/a_epoch2.gguf"])
        self.assertTrue(result["runpod_cost"]["pod_deleted"])
        self.assertLess(client.calls.index("stop"), client.calls.index("delete"))
        self.assertEqual(client.calls.count("start"), 1)
        self.assertIn("stop", client.calls)

    def test_failure_still_stops_the_pod(self):
        client = FakeClient()
        with self.assertRaises(runpod.RunPodError):
            train.run(self.spec(), jobs.Job("train", "t"), self.runner(FakeSSH(exit_code=1), client))
        self.assertIn("stop", client.calls)

    def test_cancel_stops_the_pod(self):
        client = FakeClient()
        job = jobs.Job("train", "cancel fixture")
        r = self.runner(FakeSSH(), client)
        r._sleep = lambda seconds: job.cancel_event.set()
        with self.assertRaises(jobs.Cancelled):
            train.run(self.spec(), job, r)
        self.assertIn("stop", client.calls)
        self.assertTrue(job.to_dict()["runpod_cost"]["stop_requested"])

    def test_no_paid_confirmation_no_pod(self):
        client = FakeClient()
        r = self.runner(FakeSSH(), client)
        r.paid_confirmed = False
        with self.assertRaises(runpod.RunPodError):
            r.run(self.ws / "x", self.ws / "y", jobs.Job("train", "t"))
        self.assertEqual(client.calls, [])

    def test_paid_run_requires_explicit_consent_without_a_spending_cap(self):
        review = train.preview({"base_model_id": "unsloth/Qwen3.8-27B",
                                "data_files": [self.data()], "runner": "runpod"})["review_id"]
        runner = self.runner(FakeSSH(), FakeClient())
        with patch.object(jobs.JOBS, "start") as schedule:
            for confirm in (None, True, {}, {"paid": False}, {"paid": 1}, {"max_cost_usd": 999}):
                with self.subTest(confirm=confirm), self.assertRaises(train.TrainError):
                    train.start(review, confirm=confirm, runner_factory=lambda spec: runner)
            schedule.assert_not_called()
            train.start(review, confirm={"paid": True}, runner_factory=lambda spec: runner)
            schedule.assert_called_once()
            self.assertTrue(runner.paid_confirmed)

    def test_runs_start_only_from_an_unchanged_review(self):
        request = {"base_model_id": "unsloth/Qwen3.8-27B", "data_files": [self.data()], "runner": "runpod"}
        review = train.preview(request)["review_id"]
        self.assertEqual(train.reviewed(review)["rows"], 3)
        with self.assertRaises(train.TrainError):
            train.start(None, confirm={"paid": True})  # no preview, no run
        self.data(rows=4)  # same file, edited after the preview
        with self.assertRaises(jobs.Conflict):
            train.start(review, confirm={"paid": True}, runner_factory=lambda s: self.runner(FakeSSH(), FakeClient()))

    def test_credentials_are_never_shown(self):
        view = runpod.save_credentials({"runpod_api_key": "rpa_secret_value", "pod_id": "pod123"})
        self.assertEqual((view["runpod_api_key"], view["pod_id"]), (True, "pod123"))
        self.assertNotIn("rpa_secret_value", json.dumps(view))


if __name__ == "__main__":
    unittest.main()
