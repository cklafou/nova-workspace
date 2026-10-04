# Last updated: 2026-10-04 14:40:28
# @nova: Keep retired desktop-message aliases unavailable without spawning processes or touching Nova records.
import sys
from pathlib import Path
import subprocess
import types
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nova_voice import tool_router


class RetiredDesktopPing(unittest.TestCase):
    def test_aliases_fail_honestly_without_spawning_or_writing_records(self):
        forge = types.ModuleType("nova_forge")
        forge.call = Mock(return_value=(False, ""))
        forge.catalog_line = lambda: ""
        with patch.dict(sys.modules, {"nova_forge":forge}), \
             patch.object(tool_router, "_log_tool_receipt") as receipt, \
             patch.object(tool_router, "run_process") as supervised, \
             patch.object(subprocess, "run") as run, \
             patch.object(subprocess, "Popen") as spawn:
            for alias in ("ping_claude", "ask_claude", "call_claude", "reach_claude"):
                result = tool_router.execute_tool(alias, {"message":"fixture only", "urgent":True})
                self.assertFalse(result.ok)
                self.assertIn("no tool called", str(result))
                self.assertIn(alias, str(result))
            supervised.assert_not_called();run.assert_not_called();spawn.assert_not_called()
            self.assertEqual(receipt.call_count, 4)

    def test_current_tool_catalog_and_prompt_do_not_advertise_retired_tool(self):
        self.assertNotIn("ping_claude", tool_router.AVAILABLE_TOOLS)
        self.assertFalse(hasattr(tool_router, "ping_claude"))
        with patch.object(tool_router, "_forged_section", return_value=""):
            self.assertNotIn("ping_claude", tool_router.list_tools())
        source = (Path(__file__).resolve().parents[1] / "nova_voice/nova.py").read_text(encoding="utf-8")
        self.assertNotIn("ping_claude", source)


if __name__ == "__main__":
    unittest.main()
