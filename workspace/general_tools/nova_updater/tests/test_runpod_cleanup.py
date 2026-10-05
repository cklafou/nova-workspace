# Last updated: 2026-10-06 03:19:20
# @nova: Prove irreversible pod cleanup follows verified local adapters and provenance, retaining recovery data on every incomplete outcome.
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from support import Workspace
from nova_updater import jobs, net, runpod, train
import test_runpod_lifecycle as fixture


class PodCleanup(Workspace):
    spec = fixture.RunPodLifecycle.spec
    runner = fixture.RunPodLifecycle.runner

    def setup_run(self):
        remote = fixture.PodFilesystem(self.ws / "remote")
        runner, client = self.runner(remote)
        return self.spec(), jobs.Job("train", "cleanup fixture"), runner, client, remote

    def mutate_download(self, runner, mutate):
        original = runner._run
        def run(args, **kwargs):
            result = original(args, **kwargs)
            if args[0] == "scp" and args[-2].startswith("root@"):
                mutate(Path(args[-1]) / "gguf_out")
            return result
        runner._run = run

    def assert_retained(self, runner, client, job):
        self.assertFalse(any(call[0] == "delete" for call in client.calls))
        self.assertEqual(runner.cost_summary["cleanup_state"], "retained")
        self.assertFalse(runner.cost_summary["pod_deleted"])
        self.assertTrue(runner.cost_summary["storage_retained"])
        self.assertIn("charges", runner.cost_summary["cleanup_message"])
        self.assertEqual(job.to_dict()["runpod_cost"], runner.cost_summary)

    def test_delete_occurs_only_after_local_hashes_inputs_receipt_and_full_details(self):
        spec, job, runner, client, remote = self.setup_run()
        delete = client.delete
        checks = []
        def verify_before_delete(pod_id):
            self.assertIn(("stop", pod_id), client.calls)
            package = self.ws / spec["training_directory"]
            receipt = json.loads((package / "outputs.json").read_text())
            self.assertEqual(len(receipt["outputs"]), 2)
            for entry in receipt["outputs"]:
                self.assertEqual(hashlib.sha256((self.ws / entry["path"]).read_bytes()).hexdigest(), entry["sha256"])
            for line in (package / "inputs.sha256").read_text().splitlines():
                digest, name = line.split("  ")
                self.assertEqual(hashlib.sha256((package / name).read_bytes()).hexdigest(), digest)
            details = package / "Run Details" / job.id
            entries = (details / "SHA256SUMS.txt").read_text().splitlines()
            self.assertEqual(len(entries), 6)
            for line in entries:
                digest, name = line.split("  ")
                self.assertEqual(hashlib.sha256((details / name).read_bytes()).hexdigest(), digest)
            checks.append(True)
            delete(pod_id)
        client.delete = verify_before_delete
        result = train.run(spec, job, runner)
        self.assertEqual(checks, [True])
        self.assertTrue(result["runpod_cost"]["pod_deleted"])
        self.assertEqual(result["runpod_cost"]["cleanup_state"], "terminated")
        self.assertIsNotNone(result["runpod_cost"]["cleanup_verified_at"])
        self.assertIsNone(runner.pod_id)

    def test_bad_download_checksum_never_deletes(self):
        spec, job, runner, client, remote = self.setup_run()
        self.mutate_download(runner, lambda folder: (folder / (spec["output_name"] + "_epoch2.gguf")).write_bytes(b"bad"))
        with self.assertRaises(train.TrainError):
            train.run(spec, job, runner)
        self.assert_retained(runner, client, job)

    def test_missing_epoch_even_with_a_valid_manifest_never_deletes(self):
        spec, job, runner, client, remote = self.setup_run()
        def incomplete(folder):
            manifest = folder / "SHA256SUMS.txt"
            manifest.write_text(manifest.read_text().splitlines()[0] + "\n")
        self.mutate_download(runner, incomplete)
        with self.assertRaisesRegex(train.TrainError, "every requested epoch"):
            train.run(spec, job, runner)
        self.assert_retained(runner, client, job)

    def test_missing_or_partial_provenance_never_deletes(self):
        for missing in (True, False):
            with self.subTest(missing=missing):
                spec, job, runner, client, remote = self.setup_run()
                # Separate names/remote files keep this fixture independent within one workspace.
                spec = train.prepare_spec({"base_model_id":spec["base_model_id"],
                    "data_files":[item["path"] for item in spec["data"]], "runner":"runpod",
                    "output_name":spec["output_name"] + ("_missing" if missing else "_partial")})
                def incomplete(folder):
                    details = folder / "training_details"
                    if missing:
                        details.rename(folder / "unrecognized-details")
                    else:
                        manifest = details / "SHA256SUMS.txt"
                        manifest.write_text(manifest.read_text().splitlines()[0] + "\n")
                self.mutate_download(runner, incomplete)
                with self.assertRaisesRegex(train.TrainError, "reproducibility details"):
                    train.run(spec, job, runner)
                self.assert_retained(runner, client, job)

    def test_install_collision_preserves_existing_adapter_and_remote_pod(self):
        spec, job, runner, client, remote = self.setup_run()
        existing = self.ws / "models/qwen3.8" / (spec["output_name"] + "_epoch1.gguf")
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"previous adapter")
        with self.assertRaisesRegex(train.TrainError, "already exists"):
            train.run(spec, job, runner)
        self.assertEqual(existing.read_bytes(), b"previous adapter")
        self.assert_retained(runner, client, job)

    def test_corrupted_final_copy_is_not_a_verified_install(self):
        spec, job, runner, client, remote = self.setup_run()
        copy = train._atomic_copy
        def broken_copy(source, destination, **kwargs):
            copy(source, destination, **kwargs)
            if Path(destination).suffix == ".gguf":
                Path(destination).write_bytes(b"damaged final copy")
        with patch.object(train, "_atomic_copy", side_effect=broken_copy), self.assertRaisesRegex(train.TrainError, "Installed.*does not match"):
            train.run(spec, job, runner)
        self.assert_retained(runner, client, job)

    def test_cancel_after_download_retains_remote_recovery_files(self):
        spec, job, runner, client, remote = self.setup_run()
        self.mutate_download(runner, lambda _: job.cancel_event.set())
        with self.assertRaises(jobs.Cancelled):
            train.run(spec, job, runner)
        self.assert_retained(runner, client, job)
        self.assertIn(("stop", "fixture-h200"), client.calls)

    def test_cancel_after_local_install_before_delete_keeps_both_copies(self):
        spec, job, runner, client, remote = self.setup_run()
        install = train.install_outputs
        def cancel_after_install(*args):
            result = install(*args)
            job.cancel_event.set()
            return result
        with patch.object(train, "install_outputs", side_effect=cancel_after_install), self.assertRaises(jobs.Cancelled):
            train.run(spec, job, runner)
        self.assert_retained(runner, client, job)
        self.assertTrue((self.ws / "models/qwen3.8" / (spec["output_name"] + "_epoch2.gguf")).is_file())

    def test_delete_failure_keeps_successful_adapters_with_sanitized_warning_and_fallback_stop(self):
        spec, job, runner, client, remote = self.setup_run()
        def failed_delete(pod_id):
            client.calls.append(("delete", pod_id))
            raise RuntimeError("Bearer private-fixture-key; account-private-body")
        client.delete = failed_delete
        result = train.run(spec, job, runner)
        cost = result["runpod_cost"]
        self.assertEqual(len(result["installed"]), 2)
        self.assertEqual(cost["cleanup_state"], "cleanup_failed")
        self.assertFalse(cost["pod_deleted"])
        self.assertTrue(cost["storage_retained"])
        self.assertEqual(client.calls.count(("stop", "fixture-h200")), 2)
        self.assertNotIn("private-fixture", json.dumps(job.to_dict()))
        self.assertIn("could not be confirmed", cost["delete_error"])

    def test_auth_failure_after_delete_is_not_absence(self):
        spec, job, runner, client, remote = self.setup_run()
        original = client.pod
        def pod(pod_id):
            if any(c[0] == "delete" for c in client.calls):
                raise net.NetError("Forbidden", status_code=403)
            return original(pod_id)
        client.pod = pod
        result = train.run(spec, job, runner)
        self.assertFalse(result["runpod_cost"]["pod_deleted"])
        self.assertEqual(result["runpod_cost"]["cleanup_state"], "cleanup_failed")

    def test_already_absent_pod_and_repeat_finalization_are_idempotent(self):
        spec, job, runner, client, remote = self.setup_run()
        def gone(pod_id):
            client.calls.append(("delete", pod_id)); client.deleted.add(pod_id)
            raise net.NetError("Not found", status_code=404)
        client.delete = gone
        result = train.run(spec, job, runner)
        self.assertTrue(result["runpod_cost"]["pod_deleted"])
        runner.finalize_success(job)
        self.assertEqual(client.calls.count(("delete", "fixture-h200")), 1)

    def test_saved_pod_compare_and_clear_preserves_other_settings(self):
        spec, job, runner, client, remote = self.setup_run()
        runpod.save_credentials({"runpod_api_key":"fixture-key", "pod_id":"fixture-h200", "hf_token":"fixture-token"})
        result = train.run(spec, job, runner)
        self.assertTrue(result["runpod_cost"]["credentials_cleared"])
        self.assertEqual(runpod.load_credentials(), {"runpod_api_key":"fixture-key", "hf_token":"fixture-token"})
        self.assertIsNone(runpod.RunPodRunner.from_credentials(spec).pod_id)

    def test_user_selecting_another_pod_during_run_is_not_overwritten(self):
        spec, job, runner, client, remote = self.setup_run()
        runpod.save_credentials({"runpod_api_key":"fixture-key", "pod_id":"fixture-h200"})
        original = client.delete
        def user_changed(pod_id):
            runpod.save_credentials({"pod_id":"different-user-pod"})
            original(pod_id)
        client.delete = user_changed
        result = train.run(spec, job, runner)
        self.assertFalse(result["runpod_cost"]["credentials_cleared"])
        self.assertEqual(runpod.credentials_view()["pod_id"], "different-user-pod")

    def test_next_run_creates_a_fresh_japan_pod_after_success(self):
        spec, job, runner, client, remote = self.setup_run()
        train.run(spec, job, runner)
        spec = train.prepare_spec({"base_model_id":spec["base_model_id"],
            "data_files":[item["path"] for item in spec["data"]], "runner":"runpod",
            "output_name":spec["output_name"] + "_next"})
        result = train.run(spec, jobs.Job("train", "second attempt"), runner)
        creates = [call[1] for call in client.calls if call[0] == "create"]
        self.assertEqual(len(creates), 2)
        self.assertTrue(all(body["dataCenterIds"] == ["AP-JP-1"] for body in creates))
        self.assertEqual(result["runpod_cost"]["pod_id"], "fixture-h200-2")
        self.assertEqual(client.deleted, {"fixture-h200", "fixture-h200-2"})

    def test_shared_network_volume_is_never_deleted_or_claimed_removed(self):
        spec, job, runner, client, remote = self.setup_run()
        original = client.pod
        client.pod = lambda pod_id: {**original(pod_id), "networkVolumeId":"shared-volume-fixture"}
        result = train.run(spec, job, runner)
        self.assertTrue(result["runpod_cost"]["pod_deleted"])
        self.assertTrue(result["runpod_cost"]["network_volume_retained"])
        self.assertIn("separate network volume remains", result["runpod_cost"]["cleanup_message"])
        self.assertEqual([c[1] for c in client.calls if c[0] == "delete"], ["fixture-h200"])
