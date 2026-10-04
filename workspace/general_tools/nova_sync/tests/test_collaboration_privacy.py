# Last updated: 2026-10-04 15:01:23
# @nova: Keep private collaboration transport out of autosave, cloud mirrors and Nova's automatic context.
import ast
import importlib.util
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[3]


def load_parts(path, names, namespace):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    for node in nodes: node.decorator_list = []
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def constants(path, names):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)]
    ns = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)
    return ns


class CollaborationPrivacyTests(unittest.TestCase):
    def test_committed_spool_never_reaches_drive_copy(self):
        path = ROOT / "general_tools/nova_sync/drive_copy.py"
        ns = constants(path, {"MAX_BYTES", "SKIP_PARTS", "TEXT_SUFFIXES"})
        ns["Path"] = Path
        wanted = load_parts(path, {"wanted"}, ns)["wanted"]
        for private in ["workspace/Temp/collaboration/requests/x.json",
                        "workspace/Temp/collaboration/replies/x.json", "Temp/collaboration/x.txt"]:
            self.assertFalse(wanted(private, 24), private)
        self.assertTrue(wanted("workspace/Temp/collaboration-notes.txt", 24))
        self.assertTrue(wanted("workspace/general_tools/nova_chat/collaboration.py", 24))

    def test_cloud_scan_excludes_spool_before_reading_contents(self):
        path = ROOT / "general_tools/nova_sync/drive.py"
        ns = constants(path, {"EXCLUDE_DIRS", "EXCLUDE_DIR_PREFIXES", "EXCLUDE_SUBPATHS",
                              "INCLUDE_EXTENSIONS", "EXCLUDE_FILES", "SECRET_SUFFIXES"})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root / "Temp/collaboration/requests/x.json"
            private.parent.mkdir(parents=True); private.write_text("private")
            public = root / "README.md"; public.write_text("source")
            checksum = Mock(return_value="fixture")
            ns.update({"WORKSPACE_DIR": root, "_file_checksum": checksum})
            result = load_parts(path, {"_scan_local_files"}, ns)["_scan_local_files"]()
            self.assertEqual(result, {"README.md": "fixture"})
            checksum.assert_called_once_with(public)

    def test_watcher_does_not_stamp_or_queue_spool(self):
        path = ROOT / "general_tools/nova_sync/watcher.py"
        ns = constants(path, {"EXCLUDE_DIRS", "EXCLUDE_SUBPATHS", "AUDIT_EXCLUDE_PREFIXES"})
        with tempfile.TemporaryDirectory() as tmp:
            ns.update({"WORKSPACE_DIR": Path(tmp), "Path": Path, "time": time,
                       "GENERATED_ARTIFACTS": (), "update_timestamp_in_file": Mock()})
            methods = load_parts(path, {"_handle", "_audit_should_skip"}, ns)
            obj = types.SimpleNamespace(changed_files=set(), last_event_time=0)
            for rel in ["Temp/collaboration/requests/x.json", "Temp/collaboration/replies/reply.md"]:
                methods["_handle"](obj, str(Path(tmp) / rel))
                self.assertTrue(methods["_audit_should_skip"](rel))
            self.assertEqual(obj.changed_files, set())
            ns["update_timestamp_in_file"].assert_not_called()
            methods["_handle"](obj, str(Path(tmp) / "source.py"))
            self.assertEqual(len(obj.changed_files), 1)
            ns["update_timestamp_in_file"].assert_called_once()

    def test_direct_filename_recall_does_not_inject_spool(self):
        path = ROOT / "nova_body/nova_cortex/workspace_context.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private = root / "Temp/collaboration/replies/x.json"
            private.parent.mkdir(parents=True); private.write_text("private room text")
            public = root / "source.py"; public.write_text("public source")
            obj = types.SimpleNamespace(_on_demand={}, _known_files={})
            ns = {"WORKSPACE_DIR": root, "workspace_path": lambda p: root / p,
                  "TEXT_EXTENSIONS": {".json", ".py"}, "ONDEMAND_FILE_MAX": 4096,
                  "_context_paths": lambda: iter(()), "SKIP_DIRS": {"Temp"}}
            inject = load_parts(path, {"_inject_file"}, ns)["_inject_file"]
            inject(obj, "Temp/collaboration/replies/x.json")
            self.assertEqual(obj._on_demand, {})
            inject(obj, "source.py")
            self.assertEqual(obj._on_demand, {"source.py": "public source"})

    def test_inventory_and_context_prune_temp(self):
        context = constants(ROOT / "nova_body/nova_cortex/workspace_context.py", {"SKIP_DIRS"})
        orient = constants(ROOT / "general_tools/architecture_map/orient.py", {"SKIP"})
        self.assertIn("Temp", context["SKIP_DIRS"])
        self.assertIn("Temp", orient["SKIP"])
        self.assertIn("**/Temp/", (ROOT / ".gitignore").read_text(encoding="utf-8"))


if __name__ == "__main__": unittest.main()
