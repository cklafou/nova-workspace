# @nova: Protect frozen training hashes from timestamp maintenance and PUP replacement while preserving sync detection.
# Last updated: 2026-10-06 03:19:20
import ast
import os
from pathlib import Path
import re
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "watcher.py"


def load_watcher_parts(workspace):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    constants = {"EXCLUDE_FROM_TIMESTAMPS", "EXCLUDE_DIRS", "EXCLUDE_SUBPATHS",
                 "GENERATED_ARTIFACTS", "WORKSPACE_ROOT_FILES", "STAMP_COOLDOWN_S"}
    nodes = [n for n in tree.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id in constants for t in n.targets)]
    names = {"_is_frozen_file", "update_timestamp_in_file", "_handle", "run_pup_cycle"}
    nodes.extend(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name in names)
    ns = {"WORKSPACE_DIR": workspace, "Path": Path, "os": os, "re": re, "time": time,
          "_LAST_STAMP": {}, "_similarity": lambda *args: 1.0,
          "run_push_cycle": Mock(return_value="fixture-commit"), "run_sync_and_backup": Mock(),
          "print_session_urls": Mock()}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), ns)
    return ns


class FrozenTrainingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        env = patch.dict(os.environ, {"NOVA_MODELS_DIR": ""})
        env.start(); self.addCleanup(env.stop)
        self.ns = load_watcher_parts(self.workspace)

    def make_file(self, rel, data=b"# original frozen contents\r\n"):
        p = self.workspace / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def test_timestamp_function_preserves_all_friendly_model_packages_byte_for_byte(self):
        for rel in ("models/Training Files/Qwen 3.6 27B Dense/Nova Core v7/train.py",
                    "models/Training Files/Qwen 3.8 27B Dense/run/README.md",
                    "Models/training files/Other Model/new_run/Run Details/run/environment.py"):
            with self.subTest(path=rel):
                p = self.make_file(rel)
                before = p.read_bytes()
                self.ns["update_timestamp_in_file"](p)
                self.assertEqual(p.read_bytes(), before)
                self.assertNotIn(str(p), self.ns["_LAST_STAMP"])

    def test_frozen_event_still_queues_sync_without_rewriting_recipe(self):
        p = self.make_file("models/Training Files/Qwen 3.8 27B Dense/run/train.py")
        before = p.read_bytes()
        handler = types.SimpleNamespace(changed_files=set(), last_event_time=0)
        self.ns["_handle"](handler, str(p))
        self.assertEqual(p.read_bytes(), before)
        self.assertEqual(handler.changed_files, {str(p)})
        self.assertGreater(handler.last_event_time, 0)

    def test_archived_originals_keep_exact_bytes_and_still_queue_backup(self):
        p = self.make_file("_admin/Trash/retirement_date/package/old.py")
        before = p.read_bytes()
        handler = types.SimpleNamespace(changed_files=set(), last_event_time=0)
        self.ns["_handle"](handler, str(p))
        self.assertEqual(p.read_bytes(), before)
        self.assertEqual(handler.changed_files, {str(p)})

    def test_pup_cannot_reactivate_an_archived_only_match(self):
        staged = self.make_file("old.py", b"replacement source\n")
        archived = self.make_file("_admin/Trash/retirement_date/package/old.py")
        before = archived.read_bytes()
        self.assertIsNone(self.ns["run_pup_cycle"]())
        self.assertEqual(archived.read_bytes(), before)
        self.assertTrue(staged.exists())
        self.ns["run_push_cycle"].assert_not_called()

    def test_explicit_models_root_override_is_protected(self):
        models = self.root / "separate models"
        p = models / "Training Files/Any Future Model/run/train.py"
        p.parent.mkdir(parents=True); p.write_bytes(b"frozen\n")
        with patch.dict(os.environ, {"NOVA_MODELS_DIR": str(models)}):
            self.ns["update_timestamp_in_file"](p)
        self.assertEqual(p.read_bytes(), b"frozen\n")

    def test_similar_folder_names_and_normal_source_keep_timestamp_behavior(self):
        for rel in ("models/Training Files backup/check.py", "general_tools/example.py"):
            with self.subTest(path=rel):
                p = self.make_file(rel)
                self.ns["update_timestamp_in_file"](p)
                self.assertIn("# Last updated:", p.read_text())

    def test_explicit_pup_walk_never_replaces_a_frozen_only_match(self):
        staged = self.make_file("train_lora.py", b"replacement source\n")
        frozen = self.make_file("models/Training Files/Qwen 3.8 27B Dense/run/train_lora.py")
        original = frozen.read_bytes()
        self.assertIsNone(self.ns["run_pup_cycle"]())
        self.assertEqual(frozen.read_bytes(), original)
        self.assertTrue(staged.is_file())
        self.ns["run_push_cycle"].assert_not_called()

    def test_explicit_pup_walk_can_patch_active_source_beside_frozen_copy(self):
        staged = self.make_file("train_lora.py", b"replacement source\n")
        frozen = self.make_file("models/Training Files/Qwen 3.8 27B Dense/run/train_lora.py")
        active = self.make_file("general_tools/nova_updater/pod/train_lora.py", b"old source\n")
        original = frozen.read_bytes()
        self.assertEqual(self.ns["run_pup_cycle"](), "fixture-commit")
        self.assertEqual(frozen.read_bytes(), original)
        self.assertEqual(active.read_text(), "replacement source\n")
        self.assertFalse(staged.exists())


if __name__ == "__main__":
    unittest.main()
