# @nova: Tests GGUF header reading, the installed-file inventory, install plans, verified downloads, the load check with rollback, and trash quarantine.
"""Run: python -m unittest discover -s general_tools/nova_updater/tests -v"""
import hashlib
import json
import unittest

from support import QWEN_CONFIG, FakeSource, Workspace, hit
from nova_updater import gguf, install, inventory, jobs, plan

MODEL_BYTES = b"GGUF-model-" + bytes(range(256)) * 64
PROJ_BYTES = b"GGUF-projector-" + bytes(range(256)) * 8
GGUF_REPO = "unsloth/Qwen3.8-27B-GGUF"


def gguf_source():
    hits = [hit(GGUF_REPO, formats=["gguf"], downloads=10), hit("someone/Qwen3.8-27B-abliterated-GGUF", formats=["gguf"]),
            hit("bartowski/Qwen_Qwen3.8-27B-GGUF", formats=["gguf"], downloads=99)]
    files = {(GGUF_REPO, "Qwen3.8-27B-UD-Q6_K_XL.gguf"): MODEL_BYTES,
             (GGUF_REPO, "Qwen3.8-27B-UD-Q4_K_M.gguf"): MODEL_BYTES[:100],
             (GGUF_REPO, "mmproj-F16.gguf"): PROJ_BYTES, (GGUF_REPO, "mmproj-BF16.gguf"): PROJ_BYTES[:50]}
    return FakeSource(hits, files, {"Qwen/Qwen3.8-27B": QWEN_CONFIG, "Qwen/Qwen3.6-27B": QWEN_CONFIG})


def plenty(_path):
    class Usage:
        free = 10 * 1024 ** 4
    return Usage()


class Headers(Workspace):
    def test_classify_model_lora_projector(self):
        model = self.model_file("models/qwen3.6/Qwen3.6-27B-UD-Q6_K_XL.gguf")
        lora = self.model_file("models/qwen3.6/nova_core_v7_epoch2.gguf",
                               {"general.type": "adapter", "adapter.type": "lora", "adapter.lora.alpha": 32.0})
        proj = self.model_file("models/qwen3.6/mmproj-F16.gguf", {"general.type": "mmproj", "general.architecture": "clip"})
        self.assertEqual([gguf.classify(gguf.read_metadata(p)) for p in (model, lora, proj)], ["model", "lora", "projector"])

    def test_stops_before_tokenizer_arrays(self):
        path = self.model_file("models/x.gguf", {"general.architecture": "qwen35",
                                                 "tokenizer.ggml.tokens": ["a"] * 50, "later.key": "unreached"})
        meta = gguf.read_metadata(path)
        self.assertEqual(meta["_truncated_at"], "tokenizer.ggml.tokens")
        self.assertNotIn("later.key", meta)

    def test_inventory_binds_loras_and_marks_active(self):
        self.model_file("models/qwen3.6/Qwen3.6-27B-UD-Q6_K_XL.gguf")
        self.model_file("models/qwen3.6/mmproj-F16.gguf", {"general.type": "mmproj"})
        self.model_file("models/qwen3.6/nova_core_v7_epoch2.gguf", {"general.type": "adapter", "adapter.type": "lora"})
        self.model_file("models/qwen3.6/nova_core_v6_epoch1.gguf", {"general.type": "adapter", "adapter.type": "lora"})
        self.boot("active_lora.txt", "--lora-scaled models\\qwen3.6\\nova_core_v7_epoch2.gguf:1.0\r\n")
        inv = inventory.scan()
        self.assertEqual(len(inv["models"]), 1)
        self.assertTrue(inv["models"][0]["active"])
        active = [l["path"] for l in inv["loras"] if l["active"]]
        self.assertEqual(active, ["models/qwen3.6/nova_core_v7_epoch2.gguf"])
        self.assertTrue(all(l["bound_to"] == "qwen3.6" and l["bound_by"] == "folder" for l in inv["loras"]))
        stale = inventory.invalidated_by("qwen3.8", inv)
        self.assertEqual({s["kind"] for s in stale}, {"lora", "projector"})


class Plans(Workspace):
    def setUp(self):
        super().setUp()
        self.model_file("models/qwen3.6/Qwen3.6-27B-UD-Q6_K_XL.gguf")
        self.model_file("models/qwen3.6/mmproj-F16.gguf", {"general.type": "mmproj"})
        self.model_file("models/qwen3.6/nova_core_v7_epoch2.gguf", {"general.type": "adapter", "adapter.type": "lora"})
        self.boot("active_lora.txt", "--lora-scaled models\\qwen3.6\\nova_core_v7_epoch2.gguf:1.0\r\n")
        self.src = gguf_source()

    def make(self, **extra):
        request = {"model_id": "Qwen/Qwen3.8-27B", "replace": ["models/qwen3.6/Qwen3.6-27B-UD-Q6_K_XL.gguf",
                                                              "models/qwen3.6/nova_core_v7_epoch2.gguf"]}
        request.update(extra)
        return plan.build(request, src=self.src, disk_usage=plenty)

    def test_like_for_like_plan(self):
        p = self.make()
        self.assertEqual((p["gguf_repo"], p["quant"]), (GGUF_REPO, "UD-Q6_K_XL"))
        self.assertEqual([d["name"] for d in p["downloads"]], ["Qwen3.8-27B-UD-Q6_K_XL.gguf", "mmproj-F16.gguf"])
        self.assertEqual(p["boot"], {"model": "models/qwen3.8/Qwen3.8-27B-UD-Q6_K_XL.gguf",
                                     "mmproj": "models/qwen3.8/mmproj-F16.gguf"})
        self.assertTrue(p["compatibility"]["same_architecture"])
        self.assertIn("models/qwen3.6/nova_core_v7_epoch2.gguf", [i["path"] for i in p["invalidated"]])
        self.assertEqual(p["blocking"], [])

    def test_finetunes_are_not_offered_as_builds(self):
        builds = [h.id for h in plan.gguf_sources("Qwen/Qwen3.8-27B", self.src, "unsloth")]
        self.assertEqual(builds, [GGUF_REPO, "bartowski/Qwen_Qwen3.8-27B-GGUF"])

    def test_refuses_paths_outside_models(self):
        with self.assertRaises(plan.PlanError):
            self.make(replace=["nova_body/memory/active_lora.txt"])

    def test_disk_space_blocks(self):
        def tiny(_):
            class Usage:
                free = 10
            return Usage()
        p = plan.build({"model_id": "Qwen/Qwen3.8-27B"}, src=self.src, disk_usage=tiny)
        self.assertTrue(p["blocking"])
        with self.assertRaises(install.InstallError):
            install.execute(p, jobs.Job("install", "t"), opener=self.src.opener())

    def test_keeping_a_lora_for_another_base_warns(self):
        p = self.make(lora={"mode": "keep"})
        self.assertTrue(any("another base model" in w for w in p["warnings"]))


class Installs(Plans):
    def boot_text(self, name):
        path = self.ws / "nova_body" / "memory" / name
        return path.read_bytes() if path.exists() else None

    def test_verified_install_switch_and_quarantine(self):
        p = self.make()
        restarts = []
        result = install.execute(p, jobs.Job("install", "t"), restart=lambda: restarts.append(1) or {"ok": True},
                                 probe=lambda: "Qwen3.8-27B-UD-Q6_K_XL.gguf", opener=self.src.opener())
        self.assertTrue(result["verified"])
        self.assertEqual((self.ws / "models/qwen3.8/Qwen3.8-27B-UD-Q6_K_XL.gguf").read_bytes(), MODEL_BYTES)
        self.assertEqual(self.boot_text("active_model.txt"), b"models\\qwen3.8\\Qwen3.8-27B-UD-Q6_K_XL.gguf\r\n")
        self.assertEqual(self.boot_text("active_lora.txt"), b"none\r\n")
        moved = {m["from"] for m in result["quarantine"]["moved"]}
        self.assertEqual(moved, set(p["replace"]))
        self.assertFalse((self.ws / "models/qwen3.6/Qwen3.6-27B-UD-Q6_K_XL.gguf").exists())
        manifest = json.loads((self.ws / result["quarantine"]["folder"] / "manifest.json").read_text())
        self.assertEqual(len(manifest["moved"]), 2)
        self.assertEqual(len(restarts), 1)

    def test_wrong_model_loaded_rolls_back_exactly_and_moves_nothing(self):
        before = self.boot_text("active_lora.txt")
        p = self.make()
        with self.assertRaises(install.InstallError):
            install.execute(p, jobs.Job("install", "t"), restart=lambda: {"ok": True},
                            probe=lambda: "Qwen3.6-27B-UD-Q6_K_XL.gguf", opener=self.src.opener(), load_timeout=0.01)
        self.assertIsNone(self.boot_text("active_model.txt"))
        self.assertEqual(self.boot_text("active_lora.txt"), before)
        self.assertTrue((self.ws / "models/qwen3.6/Qwen3.6-27B-UD-Q6_K_XL.gguf").exists())
        self.assertTrue((self.ws / "models/qwen3.8/Qwen3.8-27B-UD-Q6_K_XL.gguf").exists())

    def test_resume_and_hash(self):
        p = self.make()
        staging = self.ws / "models/.incoming"
        staging.mkdir(parents=True)
        (staging / "Qwen3.8-27B-UD-Q6_K_XL.gguf.part").write_bytes(MODEL_BYTES[:5000])
        p["activate"] = False
        install.execute(p, jobs.Job("install", "t"), opener=self.src.opener())
        data = (self.ws / "models/qwen3.8/Qwen3.8-27B-UD-Q6_K_XL.gguf").read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), hashlib.sha256(MODEL_BYTES).hexdigest())

    def test_corrupt_download_is_set_aside(self):
        p = self.make()
        p["downloads"][0]["sha256"] = "0" * 64
        with self.assertRaises(install.InstallError):
            install.execute(p, jobs.Job("install", "t"), opener=self.src.opener())
        self.assertTrue((self.ws / "models/.incoming/Qwen3.8-27B-UD-Q6_K_XL.gguf.part.bad").exists())
        self.assertFalse((self.ws / "models/qwen3.8/Qwen3.8-27B-UD-Q6_K_XL.gguf").exists())

    def test_chat_only_defers_until_the_new_model_really_loads(self):
        p = self.make()
        result = install.execute(p, jobs.Job("install", "t"), restart=lambda: {"ok": False, "chat_only": True},
                                 opener=self.src.opener())
        self.assertIn("next full start", result["pending"])
        self.assertTrue((self.ws / "models/qwen3.6/nova_core_v7_epoch2.gguf").exists())
        self.assertEqual(install.finish_pending(probe=lambda: "Qwen3.6-27B-UD-Q6_K_XL.gguf")["state"], "mismatch")
        done = install.finish_pending(probe=lambda: "Qwen3.8-27B-UD-Q6_K_XL.gguf")
        self.assertEqual(done["state"], "finished")
        self.assertFalse((self.ws / "models/qwen3.6/nova_core_v7_epoch2.gguf").exists())
        self.assertIsNone(install.pending())

    def test_rollback_pending_restores_boot_files(self):
        before = self.boot_text("active_lora.txt")
        install.execute(self.make(), jobs.Job("install", "t"), opener=self.src.opener())
        self.assertEqual(install.rollback_pending()["state"], "restored")
        self.assertEqual(self.boot_text("active_lora.txt"), before)
        self.assertIsNone(self.boot_text("active_model.txt"))

    def test_koels_adapters_for_the_old_base_are_cleared_and_restorable(self):
        self.boot("koels_lora_args.txt", "--lora models\\qwen3.6\\koels_gaming.gguf\r\n")
        install.execute(self.make(), jobs.Job("install", "t"), opener=self.src.opener())
        self.assertIsNone(self.boot_text("koels_lora_args.txt"))
        install.rollback_pending()
        self.assertEqual(self.boot_text("koels_lora_args.txt"), b"--lora models\\qwen3.6\\koels_gaming.gguf\r\n")

    def test_restart_that_raises_restores_boot_files(self):
        before = self.boot_text("active_lora.txt")
        def boom():
            raise OSError("launcher missing")
        with self.assertRaises(install.InstallError):
            install.execute(self.make(), jobs.Job("install", "t"), restart=boom, opener=self.src.opener())
        self.assertIsNone(self.boot_text("active_model.txt"))
        self.assertEqual(self.boot_text("active_lora.txt"), before)

    def test_cancel_while_loading_rolls_back_and_restarts(self):
        before = self.boot_text("active_lora.txt")
        job, restarts = jobs.Job("install", "t"), []

        def probe():
            job.cancel_event.set()
            return "Qwen3.6-27B-UD-Q6_K_XL.gguf"
        with self.assertRaises(jobs.Cancelled):
            install.execute(self.make(), job, restart=lambda: restarts.append(1) or {"ok": True}, probe=probe,
                            opener=self.src.opener(), poll=0.01)
        self.assertEqual(len(restarts), 2)
        self.assertIsNone(self.boot_text("active_model.txt"))
        self.assertEqual(self.boot_text("active_lora.txt"), before)
        self.assertTrue((self.ws / "models/qwen3.6/Qwen3.6-27B-UD-Q6_K_XL.gguf").exists())

    def test_failed_rollback_restart_is_reported(self):
        calls = []

        def restart():
            calls.append(1)
            return {"ok": True} if len(calls) == 1 else {"ok": False, "error": "port busy"}
        with self.assertRaises(install.InstallError) as caught:
            install.execute(self.make(), jobs.Job("install", "t"), restart=restart,
                            probe=lambda: "Qwen3.6-27B-UD-Q6_K_XL.gguf", opener=self.src.opener(),
                            load_timeout=0.05, poll=0.01)
        self.assertIn("FAILED", str(caught.exception))

    def test_training_failure_does_not_fail_a_verified_install(self):
        import time

        def after(job, the_plan, result):
            raise RuntimeError("pod refused SSH")
        p = self.make()
        job = install.start(p["id"], True, restart=lambda: {"ok": True}, after=after,
                            probe=lambda: "Qwen3.8-27B-UD-Q6_K_XL.gguf", opener=self.src.opener(), poll=0.01)
        deadline = time.time() + 10
        while job.state in ("queued", "running") and time.time() < deadline:
            time.sleep(0.02)
        self.assertEqual(job.state, "succeeded")
        self.assertTrue(job.result["verified"])
        self.assertIn("pod refused SSH", job.result["after"]["error"])

    def test_install_requires_confirmation(self):
        p = self.make()
        with self.assertRaises(install.InstallError):
            install.start(p["id"], confirm=False)


if __name__ == "__main__":
    unittest.main()
