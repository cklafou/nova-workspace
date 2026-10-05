# @nova: Verify delayed server startup stays alive through the controller deadline while failed threads stop promptly.
import ast
from pathlib import Path
import types
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / 'NovaLauncher.py'

class LauncherReadinessTests(unittest.TestCase):
    def fixture(self, ready_at):
        clock = [0.0]
        def connect(*args, **kwargs):
            if clock[0] < ready_at:
                raise OSError('still importing')
            return types.SimpleNamespace(close=lambda: None)
        clock_api = types.SimpleNamespace(monotonic=lambda: clock[0],
            sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds))
        tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'wait_for_port')
        ns = {'time': clock_api}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), 'exec'), ns)
        return clock, connect, ns['wait_for_port']

    def test_slow_import_can_finish_after_old_twenty_five_second_cutoff(self):
        clock, connect, wait = self.fixture(31)
        with patch('socket.create_connection', side_effect=connect):
            self.assertTrue(wait(8765, worker_alive=lambda: True))
        self.assertGreaterEqual(clock[0], 31)
        self.assertLess(clock[0], 60)

    def test_dead_worker_does_not_wait_for_deadline(self):
        clock, connect, wait = self.fixture(100)
        with patch('socket.create_connection', side_effect=connect):
            self.assertFalse(wait(8765, worker_alive=lambda: clock[0] < 2))
        self.assertLess(clock[0], 3)

    def test_unready_live_worker_still_has_bounded_wait(self):
        clock, connect, wait = self.fixture(100)
        with patch('socket.create_connection', side_effect=connect):
            self.assertFalse(wait(8765, worker_alive=lambda: True))
        self.assertGreaterEqual(clock[0], 60)
        self.assertLess(clock[0], 61)

if __name__ == '__main__':
    unittest.main()
