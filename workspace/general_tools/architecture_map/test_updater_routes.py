# Last updated: 2026-10-04 13:40:00
# @nova: Verify that Orient publishes updater route prefixes from source without importing its runtime.
import tempfile
import unittest
from pathlib import Path
from orient import refresh

class UpdaterRouteInventoryTests(unittest.TestCase):
    def test_attached_router_paths_are_prefixed_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "general_tools" / "nova_updater" / "api.py"
            path.parent.mkdir(parents=True)
            path.write_text("# @nova: Fixture updater router.\ndef create_router():\n    @router.get('/status')\n    def status(): pass\n    @router.post('/install')\n    def install(): pass\n", encoding="utf-8")
            refresh(root)
            result = (root / "Orient" / "OPERATIONS.md").read_text(encoding="utf-8")
            self.assertIn("| GET | `/api/updater/status` | `status` |", result)
            self.assertIn("| POST | `/api/updater/install` | `install` |", result)
            self.assertNotIn("| GET | `/status`", result)
