# Last updated: 2026-10-06 03:19:20
"""Isolation, evidence and change-detection tests; never write to Nova's real state."""
import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import Module, collect, digest, symbol_hash
from serve import Atlas, handler_for, watched_signature


class ArchitectureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.catalog = self.root / "catalog.json"
        self.catalog.write_text("{}", encoding="utf-8")
        self.write("nova_body/nova_demo/__init__.py", "")

    def tearDown(self):
        self.temp.cleanup()

    def write(self, rel, content):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def collect(self):
        return collect(self.root, self.catalog)

    def test_relative_and_from_package_imports_resolve(self):
        self.write("nova_body/nova_demo/target.py", "def run(): pass\n")
        self.write("nova_body/nova_demo/client.py", "from . import target as t\nfrom nova_demo.target import run as go\ndef use():\n t.run()\n go()\n")
        result = self.collect()
        calls = [c for c in result["calls"] if c["from"].endswith("client.py")]
        self.assertEqual(2, len(calls))
        self.assertTrue(all(c["to"].endswith("target.py") and c["callee"] == "run" for c in calls))

    def test_method_names_do_not_guess_receiver(self):
        self.write("nova_body/nova_demo/a.py", "def write(): pass\ndef work(unknown):\n unknown.write()\n")
        result = self.collect()
        self.assertFalse(result["calls"])
        self.assertTrue(any(u["expression"] == "unknown.write" for u in result["unresolved"]))

    def test_parameter_shadows_local_function(self):
        self.write("nova_body/nova_demo/a.py", "def run(): pass\ndef work(run):\n run()\n")
        self.assertFalse(self.collect()["calls"])

    def test_parameter_shadows_import(self):
        self.write("nova_body/nova_demo/a.py", "def run(): pass\n")
        self.write("nova_body/nova_demo/b.py", "from .a import run\ndef work(run):\n run()\n")
        self.assertFalse(self.collect()["calls"])

    def test_constructor_receiver_and_self_method(self):
        self.write("nova_body/nova_demo/a.py", "class Worker:\n def run(self): pass\n")
        self.write("nova_body/nova_demo/b.py", "from .a import Worker\nclass Host:\n def __init__(self):\n  self.worker = Worker()\n def drive(self):\n  self.worker.run()\n  self.local()\n def local(self): pass\n")
        calls = self.collect()["calls"]
        self.assertTrue(any(c["callee"] == "Worker.run" for c in calls))
        self.assertTrue(any(c["callee"] == "Host.local" for c in calls))

    def test_reassigned_receiver_and_import_are_not_guessed(self):
        self.write("nova_body/nova_demo/a.py", "class Worker:\n def run(self): pass\ndef run(): pass\n")
        self.write("nova_body/nova_demo/b.py", "from .a import Worker, run\ndef work(unknown):\n worker = Worker()\n worker = unknown\n worker.run()\n run = unknown\n run()\n")
        calls = self.collect()["calls"]
        self.assertEqual(["Worker"], [c["callee"] for c in calls])

    def test_class_scope_is_not_a_method_closure(self):
        self.write("nova_body/nova_demo/a.py", "def run(): pass\nclass Host:\n def run(self): pass\n def work(self):\n  run()\n")
        calls = self.collect()["calls"]
        self.assertEqual(["run"], [c["callee"] for c in calls])

    def test_else_branch_is_not_reported_as_true_branch(self):
        self.write("nova_body/nova_demo/a.py", "def run(): pass\ndef work(flag):\n if flag:\n  pass\n else:\n  run()\n")
        self.assertEqual(["else of flag"], self.collect()["calls"][0]["conditions"])

    def test_ambiguous_import_does_not_invent_call(self):
        self.write("nova_body/nova_demo/a.py", "def run(): pass\n")
        self.write("nova_body/nova_demo/b.py", "def run(): pass\n")
        self.write("nova_body/nova_demo/c.py", "try:\n from .a import run\nexcept ImportError:\n from .b import run\nrun()\n")
        self.assertFalse(self.collect()["calls"])

    def test_inspection_never_executes_body_code(self):
        marker = self.root / "side_effect.txt"
        self.write("nova_body/nova_demo/a.py", f"from pathlib import Path\nPath({str(marker)!r}).write_text('BAD')\nraise RuntimeError('never run')\n")
        self.collect()
        self.assertFalse(marker.exists())

    def test_add_remove_and_parse_failure_are_visible(self):
        before = self.collect()
        p = self.write("nova_body/nova_demo/new.py", "def new(): pass\n")
        after = self.collect()
        self.assertEqual(len(before["nodes"]) + 1, len(after["nodes"]))
        self.assertNotEqual(before["revision"], after["revision"])
        p.write_text("def broken(\n", encoding="utf-8")
        broken = self.collect()
        self.assertEqual(1, len(broken["errors"]))
        self.assertTrue(any(n["status"] == "parse_error" for n in broken["nodes"]))
        p.unlink()
        self.assertEqual(len(before["nodes"]), len(self.collect()["nodes"]))

    def test_reviewed_seam_invalidated_by_function_change(self):
        file = "nova_body/nova_demo/a.py"
        source = "def write():\n return 1\n"
        self.write(file, source)
        mod = Module(file, source)
        catalog = {"modules": {file: {"summary": "A checked explanation", "review_hash": digest(source)}},
                   "resources": [{"id": "store:test", "label": "test"}],
                   "connections": [{"id": "test", "from": file, "to": "store:test", "label": "Writes", "kind": "write",
                                    "refs": [{"file": file, "symbol": "write", "contains": "return", "hash": symbol_hash(mod, "write")}]}]}
        self.catalog.write_text(json.dumps(catalog), encoding="utf-8")
        self.assertEqual("source_checked", self.collect()["connections"][0]["status"])
        self.write(file, "def write():\n return 2\n")
        changed = self.collect()
        self.assertEqual("needs_review", changed["connections"][0]["status"])
        self.assertEqual("needs_review", next(n for n in changed["nodes"] if n["id"] == file)["explanation_status"])

    def test_endpoint_default_updates_and_dynamic_unknown_is_not_stale_port(self):
        file = "nova_body/nova_demo/a.py"
        self.write(file, "URL = 'http://127.0.0.1:8080/v1/chat/completions'\n")
        self.catalog.write_text(json.dumps({"resources": [{"id": "s", "label": "model", "port": 8080,
            "url_ref": {"file": file, "name": "URL"}}]}), encoding="utf-8")
        self.assertEqual(8080, self.collect()["resources"][0]["port"])
        self.write(file, "URL = 'http://127.0.0.1:8089/v1/chat/completions'\n")
        self.assertEqual(8089, self.collect()["resources"][0]["port"])
        self.write(file, "URL = get_dynamic_endpoint()\n")
        self.assertIsNone(self.collect()["resources"][0]["port"])

    def test_unmapped_tools_and_tests_are_excluded(self):
        self.write("general_tools/private_tool.py", "raise Exception('never scan')\n")
        self.write("nova_body/nova_demo/tests/test_something.py", "def ignored(): pass\n")
        paths = [n["id"] for n in self.collect()["nodes"]]
        self.assertEqual(["nova_body/nova_demo/__init__.py"], paths)

    def test_provisioned_port_change_is_reflected(self):
        file = "nova_body/nova_demo/provision.sh"
        self.write(file, "ExecStart=websockify 6080 localhost:5901\n")
        self.catalog.write_text(json.dumps({"resources": [{"id": "desktop", "label": "Desktop", "port_ref": {
            "file": file, "pattern": r"^ExecStart=websockify (\d+) localhost:\d+"}}]}), encoding="utf-8")
        self.assertEqual(6080, self.collect()["resources"][0]["port"])
        self.write(file, "ExecStart=websockify 6090 localhost:5901\n")
        self.assertEqual(6090, self.collect()["resources"][0]["port"])
        self.write(file, "ExecStart=websockify $PORT localhost:5901\n")
        self.assertIsNone(self.collect()["resources"][0]["port"])

    def test_watcher_changes_without_touching_real_workspace(self):
        self.write("nova_body/nova_demo/a.py", "def a(): pass\n")
        atlas = Atlas(self.root, self.root / "output", self.catalog, interval=.03)
        old = atlas.data["revision"]
        watcher = threading.Thread(target=atlas.watch, daemon=True)
        watcher.start()
        try:
            self.write("nova_body/nova_demo/b.py", "from .a import a\ndef b(): a()\n")
            deadline = time.monotonic() + 4
            while atlas.data["revision"] == old and time.monotonic() < deadline:
                time.sleep(.03)
            self.assertNotEqual(old, atlas.data["revision"])
            saved = json.loads((self.root / "output/architecture.json").read_text(encoding="utf8"))
            self.assertEqual(atlas.data["revision"], saved["revision"])
            old = atlas.data["revision"]
            self.write("nova_body/nova_config.json", '{"test": 1}')
            self.assertTrue(atlas.check_once())
            self.assertNotEqual(old, atlas.data["revision"])
        finally:
            atlas.stop_event.set()
            watcher.join(3)

    def test_invalid_catalog_preserves_last_good_map(self):
        atlas = Atlas(self.root, self.root / "output", self.catalog)
        old = atlas.data["revision"]
        self.catalog.write_text("{bad", encoding="utf-8")
        self.assertFalse(atlas.check_once())
        self.assertIsNotNone(atlas.error)
        self.assertEqual(old, atlas.data["revision"])

    def test_http_source_is_scoped_and_shutdown_requires_token(self):
        self.write("nova_body/nova_demo/a.py", "def a(): pass\n")
        self.write("memory/COLE.md", "private fixture text")
        atlas = Atlas(self.root, self.root / "output", self.catalog)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(atlas))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urllib.request.urlopen(base + "/api/source?path=nova_body/nova_demo/a.py&line=1") as r:
                self.assertEqual(["def a(): pass"], json.load(r)["lines"])
            for path in ["/api/source?path=../secret.txt", "/api/source?path=memory/COLE.md", "/../catalog.json"]:
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(base + path)
                self.assertIn(caught.exception.code, [403, 404])
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(urllib.request.Request(base+"/api/shutdown", method="POST"))
            self.assertEqual(403, caught.exception.code)
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(urllib.request.Request(base+"/api/map", headers={"Host":"foreign.example"}))
            self.assertEqual(403, caught.exception.code)
        finally:
            server.shutdown();server.server_close();thread.join(3)


if __name__ == "__main__":
    unittest.main()
