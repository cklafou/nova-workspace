# @nova: Tests GGUF header reading, the installed-file inventory, install plans, verified downloads, the load check with rollback, and trash quarantine.
"""Run: python -m unittest discover -s general_tools/nova_updater/tests -v"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from support import QWEN_CONFIG, FakeSource, Workspace, hit, wait_remembered
from nova_updater import catalog, current, gguf, install, inventory, jobs, paths, plan, store

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

    def test_keeping_a_lora_for_another_base_blocks(self):
        p = self.make(lora={"mode": "keep"}, replace=[])
        self.assertTrue(any("another base model" in message for message in p["blocking"]))
        before = current.snapshot_boot_files()
        with self.assertRaises(install.InstallError):
            install.execute(p, jobs.Job("install", "t"), opener=mock.Mock(side_effect=AssertionError("downloaded")))
        self.assertEqual(current.snapshot_boot_files(), before)

    def test_an_explicit_projector_choice_is_kept_exactly(self):
        proj = [catalog.FileInfo(path="vision/mmproj-F16.gguf", size=1), catalog.FileInfo(path="vision/mmproj-BF16.gguf", size=1)]
        self.assertEqual(plan.pick_projector(proj, "vision/mmproj-BF16.gguf", exact=True).path, "vision/mmproj-BF16.gguf")
        self.assertEqual(plan.pick_projector(proj, "mmproj-BF16.gguf", exact=True).path, "vision/mmproj-BF16.gguf")
        self.assertIsNone(plan.pick_projector(proj, "vision/mmproj-Q8_0.gguf", exact=True))
        self.assertEqual(plan.pick_projector(proj).path, "vision/mmproj-F16.gguf")  # no choice: F16 first
        self.assertEqual(self.make(mmproj="mmproj-BF16.gguf")["boot"]["mmproj"], "models/qwen3.8/mmproj-BF16.gguf")
        with self.assertRaises(plan.PlanError):
            self.make(mmproj="mmproj-Q8_0.gguf")

    def test_install_folder_the_launcher_cannot_pass_blocks_the_plan(self):
        p = self.make(folder="Qwen (new)")
        self.assertTrue(p["blocking"] and all("cannot pass" in b for b in p["blocking"]))
        self.assertEqual(self.make(folder="custom folder")["blocking"], [])  # spaces: the launcher quotes them


class Installs(Plans):
    def boot_text(self, name):
        path = self.ws / "nova_body" / "memory" / name
        return path.read_bytes() if path.exists() else None

    def test_compatible_keep_is_allowed_but_cannot_quarantine_selected_adapter(self):
        adapter = "models/qwen3.8/personality.gguf"
        self.model_file(adapter, {"general.type": "adapter", "adapter.type": "lora",
                                  "general.base_model.count": 1, "general.base_model.0.name": "Qwen3.8 27B"})
        self.boot("active_lora.txt", f"--lora-scaled {adapter}:1")
        self.assertEqual(self.make(lora={"mode": "keep"}, replace=[])["blocking"], [])
        bad = self.make(lora={"mode": "keep"}, replace=[adapter])
        self.assertTrue(any("still selected" in message for message in bad["blocking"]))

    def test_legacy_stored_keep_plan_is_rechecked_before_download_or_switch(self):
        p = self.make(lora={"mode": "keep"}, replace=[])
        p["blocking"] = []  # a stored plan made before the compatibility gate existed
        before = current.snapshot_boot_files()
        with self.assertRaisesRegex(install.InstallError, "another base model"):
            install.execute(p, jobs.Job("install", "t"), opener=mock.Mock(side_effect=AssertionError("downloaded")))
        self.assertEqual(current.snapshot_boot_files(), before)
        self.assertIsNone(install.pending())

    def test_legacy_pending_incompatible_adapter_cannot_finish_or_move_files(self):
        p = self.make()
        install.execute(p, jobs.Job("install", "t"), opener=self.src.opener())
        self.boot("active_lora.txt", "--lora-scaled models/qwen3.6/nova_core_v7_epoch2.gguf:1")
        before, pending = current.snapshot_boot_files(), install.pending()
        with self.assertRaisesRegex(jobs.Conflict, "another base model"):
            install.finish_pending(probe=lambda: "Qwen3.8-27B-UD-Q6_K_XL.gguf")
        self.assertEqual(install.pending(), pending)
        self.assertEqual(current.snapshot_boot_files(), before)
        self.assertTrue(all((self.ws / path).exists() for path in p["replace"]))

    def test_pending_compatible_selected_adapter_cannot_be_quarantined(self):
        p = self.make(replace=[])
        install.execute(p, jobs.Job("install", "t"), opener=self.src.opener())
        adapter = "models/qwen3.8/personality.gguf"
        self.model_file(adapter, {"general.type": "adapter", "adapter.type": "lora"})
        self.boot("active_lora.txt", f"--lora-scaled {adapter}:1")
        store.mutate(lambda data: data["pending"].update(replace=[adapter]))
        with self.assertRaisesRegex(jobs.Conflict, "still selected"):
            install.finish_pending(probe=lambda: "Qwen3.8-27B-UD-Q6_K_XL.gguf")
        self.assertTrue((self.ws / adapter).exists())
        self.assertIsNotNone(install.pending())

    def test_quarantine_preflights_all_paths_before_moving_any(self):
        old_model = "models/qwen3.6/Qwen3.6-27B-UD-Q6_K_XL.gguf"
        adapter = "models/qwen3.6/nova_core_v7_epoch2.gguf"
        with self.assertRaisesRegex(install.InstallError, "still selected"):
            install.quarantine([old_model, adapter])
        self.assertTrue((self.ws / old_model).exists())
        self.assertTrue((self.ws / adapter).exists())
        self.assertFalse(paths.trash_root().exists())

    def test_boot_change_after_install_keeps_pending_recovery(self):
        p = self.make()
        install.execute(p, jobs.Job("install", "t"), opener=self.src.opener())
        self.boot("active_model.txt", "models/qwen3.6/Qwen3.6-27B-UD-Q6_K_XL.gguf")
        with self.assertRaisesRegex(jobs.Conflict, "configured model changed"):
            install.finish_pending(probe=lambda: "Qwen3.8-27B-UD-Q6_K_XL.gguf")
        self.assertIsNotNone(install.pending())

    def test_adapter_selected_during_model_load_blocks_quarantine(self):
        p = self.make()
        def changed_selection():
            self.boot("active_lora.txt", "--lora-scaled models/qwen3.6/nova_core_v7_epoch2.gguf:1")
            return "Qwen3.8-27B-UD-Q6_K_XL.gguf"
        with self.assertRaises(jobs.Conflict):
            install.execute(p, jobs.Job("install", "t"), restart=lambda: {"ok": True},
                            probe=changed_selection, opener=self.src.opener())
        self.assertTrue(all((self.ws / path).exists() for path in p["replace"]))
        self.assertIsNotNone(install.pending())

    def test_new_activation_cannot_overwrite_pending_rollback_snapshot(self):
        p = self.make()
        install.execute(p, jobs.Job("install", "t"), opener=self.src.opener())
        before = install.pending()
        second = self.make(lora={"mode": "none"}, replace=[])
        with self.assertRaisesRegex(jobs.Conflict, "earlier model switch"):
            install.execute(second, jobs.Job("install", "t"),
                            opener=mock.Mock(side_effect=AssertionError("started another download")))
        self.assertEqual(install.pending(), before)

    def test_rollback_then_clean_replan_reuses_downloads_and_keeps_old_adapters(self):
        p = self.make()
        install.execute(p, jobs.Job("install", "t"), opener=self.src.opener())
        self.boot("active_lora.txt", "--lora-scaled models/qwen3.6/nova_core_v7_epoch2.gguf:1")
        self.assertEqual(install.rollback_pending()["state"], "restored")
        self.assertEqual(current.active_model()["label"], "Qwen3.6-27B")
        clean = self.make(lora={"mode": "none"}, replace=[])
        self.assertEqual(clean["download_bytes"], 0)
        result = install.execute(clean, jobs.Job("install", "t"),
                                 opener=mock.Mock(side_effect=AssertionError("redownloaded existing model")))
        self.assertTrue(result["pending"])
        self.assertFalse(result["verified"])
        self.assertEqual(current.active_loras(), [])
        self.assertEqual(current.active_model()["label"], "Qwen3.8-27B")
        self.assertEqual(install.pending()["replace"], [])
        self.assertTrue(all((self.ws / path).exists() for path in p["replace"]))

    def test_finish_and_rollback_wait_for_a_running_job(self):
        p = self.make()
        install.execute(p, jobs.Job("install", "t"), restart=lambda: {"ok": False, "chat_only": True},
                        probe=lambda: None, opener=self.src.opener())
        self.assertTrue(install.pending())
        release = threading.Event()
        job = jobs.JOBS.start("install", "Another install", lambda job: release.wait(5))
        self.addCleanup(release.set)
        with self.assertRaises(jobs.Conflict):
            install.rollback_pending()
        with self.assertRaises(jobs.Conflict):
            install.finish_pending(probe=lambda: "Qwen3.8-27B-UD-Q6_K_XL.gguf")
        self.assertTrue(install.pending())  # untouched while the job runs
        release.set()
        wait_remembered(job)
        self.assertEqual(install.rollback_pending()["state"], "restored")
        self.assertEqual(jobs.JOBS.get(job.id)["state"], "succeeded")

    def test_no_job_starts_while_recovery_holds_the_slot(self):
        with jobs.JOBS.exclusive("Undo the model switch"):
            with self.assertRaises(jobs.Conflict):
                jobs.JOBS.start("install", "t", lambda job: None)
        jobs.JOBS.start("install", "t", lambda job: None, background=False)

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

    def test_unsafe_boot_path_is_refused_before_downloading(self):
        p = self.make()
        p["boot"]["mmproj"] = "models/qwen3.8/mm&proj.gguf"  # e.g. a plan saved before the check existed
        with self.assertRaises(install.InstallError):
            install.execute(p, jobs.Job("install", "t"), opener=self.src.opener())
        self.assertEqual(list((self.ws / "models").rglob("*.part")), [])
        self.assertFalse((self.ws / "models/qwen3.8").exists())
        self.assertIsNone(self.boot_text("active_model.txt"))

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
        self.assertEqual(job.result["rollback"]["previous_model_restart"], "ok")
        self.assertIsNone(install.pending())
        self.assertIsNone(self.boot_text("active_model.txt"))
        self.assertEqual(self.boot_text("active_lora.txt"), before)
        self.assertTrue((self.ws / "models/qwen3.6/Qwen3.6-27B-UD-Q6_K_XL.gguf").exists())

    def test_failed_rollback_restart_is_reported(self):
        calls = []

        def restart():
            calls.append(1)
            return {"ok": True} if len(calls) == 1 else {"ok": False, "error": "port busy"}
        job = jobs.Job("install", "t")
        with self.assertRaises(install.InstallError) as caught:
            install.execute(self.make(), job, restart=restart,
                            probe=lambda: "Qwen3.6-27B-UD-Q6_K_XL.gguf", opener=self.src.opener(),
                            load_timeout=0.05, poll=0.01)
        self.assertIn("FAILED", str(caught.exception))
        self.assertEqual(job.result["rollback"]["previous_model_restart"], "failed")

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
        wait_remembered(job)  # its summary must land in this test's state, not the real one
        self.assertEqual(job.state, "succeeded")
        self.assertTrue(job.result["verified"])
        self.assertIn("pod refused SSH", job.result["after"]["error"])

    def test_switch_record_exists_before_the_first_boot_write(self):
        before = self.boot_text("active_lora.txt")
        real, calls = install.write_boot, []

        def dies_after_first_write(name, text):
            calls.append(name)
            if len(calls) == 2:
                raise KeyboardInterrupt("power cut")  # not an Exception: nothing in execute() catches it
            real(name, text)
        install.write_boot = dies_after_first_write
        self.addCleanup(setattr, install, "write_boot", real)
        with self.assertRaises(KeyboardInterrupt):
            install.execute(self.make(), jobs.Job("install", "t"), restart=lambda: {"ok": True},
                            opener=self.src.opener())
        install.write_boot = real
        todo = install.pending()
        self.assertEqual(todo["phase"], "switching")
        self.assertEqual(install.finish_pending(probe=lambda: "Qwen3.8-27B-UD-Q6_K_XL.gguf")["state"], "interrupted")
        self.assertEqual(install.rollback_pending()["state"], "restored")
        self.assertIsNone(self.boot_text("active_model.txt"))
        self.assertEqual(self.boot_text("active_lora.txt"), before)

    def test_a_failed_boot_write_restores_the_rest(self):
        before = self.boot_text("active_lora.txt")
        real, calls = install.write_boot, []

        def fails_second(name, text):
            calls.append(name)
            if len(calls) == 2:
                raise OSError("disk full")
            real(name, text)
        install.write_boot = fails_second
        self.addCleanup(setattr, install, "write_boot", real)
        with self.assertRaises(install.InstallError):
            install.execute(self.make(), jobs.Job("install", "t"), restart=lambda: {"ok": True},
                            opener=self.src.opener())
        install.write_boot = real
        self.assertIsNone(self.boot_text("active_model.txt"))
        self.assertEqual(self.boot_text("active_lora.txt"), before)
        self.assertIsNone(install.pending())

    def test_failed_first_restart_says_what_was_restored(self):
        calls = []

        def restart():
            calls.append(1)
            return {"ok": False, "error": "port busy"} if len(calls) == 1 else {"ok": True}
        job = jobs.Job("install", "t")
        with self.assertRaises(install.InstallError) as caught:
            install.execute(self.make(), job, restart=restart, opener=self.src.opener(),
                            probe=lambda: "Qwen3.6-27B-UD-Q6_K_XL.gguf", poll=0.01)
        self.assertIn("previous model is running again (verified)", str(caught.exception))
        self.assertEqual(job.result["rollback"]["previous_model_restart"], "ok")
        self.assertTrue(job.result["rollback"]["previous_model_verified"])
        self.assertIn("port busy", job.result["rollback"]["reason"])
        self.assertIsNone(install.pending())

    def test_rollback_distinguishes_accepted_restart_from_verified_recovery(self):
        job = jobs.Job("install", "t")
        with self.assertRaises(install.InstallError) as caught:
            install.execute(self.make(), job, restart=lambda: {"ok": True}, probe=lambda: None,
                            opener=self.src.opener(), load_timeout=0.05, rollback_timeout=0.05, poll=0.01)
        self.assertIn("not confirmed running", str(caught.exception))
        self.assertEqual((job.result["rollback"]["previous_model_restart"],
                          job.result["rollback"]["previous_model_verified"]), ("ok", False))

    def test_install_requires_confirmation(self):
        p = self.make()
        with self.assertRaises(install.InstallError):
            install.start(p["id"], confirm=False)


class Paths(unittest.TestCase):
    def test_credentials_live_in_the_profile_not_appdata(self):
        # Windows gives each MSIX-packaged launcher a private AppData; the profile is shared by all.
        with tempfile.TemporaryDirectory() as home, \
                mock.patch.dict(os.environ, {"LOCALAPPDATA": str(Path(home) / "AppData" / "Local")}), \
                mock.patch.object(Path, "home", return_value=Path(home)):
            os.environ.pop("NOVA_UPDATER_CREDENTIALS", None)
            self.assertEqual(paths.credentials_path(), Path(home) / "ProjectNovaData" / "Updater" / "credentials.json")

    def test_launcher_rules(self):
        self.assertIsNone(paths.launcher_problem("models/custom folder/model.gguf"))
        self.assertIn("a space", paths.launcher_problem("models/custom folder/a.gguf", spaces=False))
        for bad in ('models/"q"/m.gguf', "models/50%/m.gguf", "models/a^b/m.gguf", "models/(x)/m.gguf", "models/é/m.gguf"):
            self.assertIsNotNone(paths.launcher_problem(bad), bad)


if __name__ == "__main__":
    unittest.main()
