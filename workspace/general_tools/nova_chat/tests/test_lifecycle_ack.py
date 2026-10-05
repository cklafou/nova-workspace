# Last updated: 2026-10-05 21:27:11
# @nova: Preserve lifecycle HTTP acknowledgement before fast controller teardown without extending grace on retries.
import ast
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, patch

from general_tools.nova_console.hub import LogHub

ROOT = Path(__file__).resolve().parents[3]


class LifecycleAcknowledgementTests(unittest.TestCase):
    def test_first_request_starts_grace_and_retries_cannot_extend_it(self):
        hub = LogHub(ROOT)
        with patch("general_tools.nova_console.hub.time.monotonic", return_value=10.0):
            self.assertFalse(hub.lifecycle_ready())
            self.assertEqual(hub.request_lifecycle("restart")[1], 202)
            self.assertFalse(hub.lifecycle_ready())
            self.assertEqual(hub._lifecycle_ready_at, 11.0)
        with patch("general_tools.nova_console.hub.time.monotonic", return_value=10.9):
            self.assertEqual(hub.request_lifecycle("restart")[1], 202)
            self.assertEqual(hub.request_lifecycle("shutdown")[1], 409)
            self.assertEqual(hub._lifecycle_ready_at, 11.0)
            self.assertFalse(hub.lifecycle_ready())
        with patch("general_tools.nova_console.hub.time.monotonic", return_value=11.0):
            self.assertTrue(hub.lifecycle_ready())
            self.assertEqual(hub.request_lifecycle("restart")[1], 202)
            self.assertTrue(hub.lifecycle_ready())
            self.assertEqual(hub._lifecycle_ready_at, 11.0)

    def test_shutdown_uses_the_same_grace(self):
        hub = LogHub(ROOT)
        with patch("general_tools.nova_console.hub.time.monotonic", return_value=20.0):
            self.assertEqual(hub.request_lifecycle("shutdown")[1], 202)
            self.assertFalse(hub._restart_req)
            self.assertFalse(hub.lifecycle_ready())
        with patch("general_tools.nova_console.hub.time.monotonic", return_value=21.1):
            self.assertTrue(hub.lifecycle_ready())

    def test_launcher_waits_for_ready_gate_not_the_immediate_request_flag(self):
        hub = types.SimpleNamespace(_shutdown_req=True,
                                    lifecycle_ready=Mock(side_effect=[False, False, True]))
        signal = types.SimpleNamespace(wait=Mock(return_value=False), set=Mock())
        thread = lambda **kwargs: types.SimpleNamespace(start=kwargs["target"])
        path = ROOT / "nova_start.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_watch_for_shutdown")
        ns = {"HUB": hub, "_SHUTDOWN": signal, "threading": types.SimpleNamespace(Thread=thread),
              "log": Mock()}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
        ns["_watch_for_shutdown"]()
        self.assertEqual(hub.lifecycle_ready.call_count, 3)
        signal.set.assert_called_once()


if __name__ == "__main__": unittest.main()
