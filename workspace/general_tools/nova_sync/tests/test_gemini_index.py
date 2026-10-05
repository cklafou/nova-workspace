# Last updated: 2026-10-06 03:19:20
# @nova: Verify local Gemini index pruning without cloud authentication, content reads or changed backup eligibility.
import ast
from datetime import datetime
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

DRIVE = Path(__file__).resolve().parents[1] / "drive.py"
CONSTANTS = {"EXCLUDE_DIRS", "EXCLUDE_DIR_PREFIXES", "EXCLUDE_SUBPATHS",
             "INCLUDE_EXTENSIONS", "EXCLUDE_FILES", "SECRET_SUFFIXES", "FILE_DESCRIPTIONS"}
FUNCTIONS = {"_gemini_index_paths", "_build_gemini_index_content", "_scan_local_files"}


def pure_index_functions(root):
    tree = ast.parse(DRIVE.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if
             (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in CONSTANTS for target in node.targets)) or
             (isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS)]
    namespace = {"Path": Path, "datetime": datetime, "WORKSPACE_DIR": root,
                 "_file_checksum": lambda path: "fixture-checksum"}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(DRIVE), "exec"), namespace)
    return namespace


class GeminiIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("general_tools/current.py", "_admin/active_review.py",
                    "_admin/Trash/ScriptRetirement_2026-10-04/retired.py",
                    "Temp/diagnostic.py", "general_tools/Temp/scratch.md",
                    "models/model.gguf", "models/README.md", "node_modules/package/index.js",
                    "general_tools/nova_sync/GEMINI_INDEX.md", ".env"):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture", encoding="utf-8")
        self.functions = pure_index_functions(self.root)

    def test_prunes_before_descending_and_never_reads_file_contents(self):
        visited = []
        real_scandir = os.scandir

        def scandir(path):
            visited.append(Path(path).relative_to(self.root).as_posix())
            return real_scandir(path)

        with patch("os.scandir", side_effect=scandir), patch.object(Path, "read_text", side_effect=AssertionError("Index must not read content")):
            content = self.functions["_build_gemini_index_content"]()
        self.assertTrue(content.startswith("<!-- @nova:"))
        self.assertIn("`workspace/general_tools/current.py`", content)
        self.assertIn("`workspace/_admin/active_review.py`", content)
        for excluded in ("workspace/_admin/Trash/", "workspace/Temp/", "workspace/general_tools/Temp/", "workspace/models/", "workspace/.env"):
            self.assertNotIn(excluded, content)
        for forbidden in ("Temp", "general_tools/Temp", "_admin/Trash", "models", "node_modules"):
            self.assertNotIn(forbidden, visited, "Excluded directories must not be traversed")

    def test_index_pruning_does_not_change_cloud_backup_selection(self):
        scanned = self.functions["_scan_local_files"]()
        self.assertIn("_admin/Trash/ScriptRetirement_2026-10-04/retired.py", scanned)
        self.assertIn("Temp/diagnostic.py", scanned)
        self.assertIn("general_tools/current.py", scanned)
        self.assertNotIn("models/README.md", scanned)


if __name__ == "__main__":
    unittest.main()
