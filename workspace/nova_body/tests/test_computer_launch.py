# @nova: Isolated regression tests for guest desktop routing and honest process/window launch verification.
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

BODY = Path(__file__).resolve().parents[1]
if str(BODY) not in sys.path:
    sys.path.insert(0, str(BODY))
from nova_computer.backends import nova_desktop_command
from nova_computer.hands import Hands, _launch_probe
from nova_computer import tools


class LaunchProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'logs').mkdir()

    def run_probe(self, *, code=None, window_pid=None, before=False, process_name='firefox', display_ok=True):
        owner = window_pid or 321
        proc_dir = self.root / str(owner)
        proc_dir.mkdir()
        (proc_dir / 'status').write_text('Name:\t'+process_name+'\nPPid:\t1\n')
        count = 0
        def run(argv, **kwargs):
            nonlocal count
            out, err, rc = '', '', 0
            if argv[1] == 'getdisplaygeometry':
                out = '1600 900' if display_ok else ''
                err = '' if display_ok else 'Authorization required; cannot open display :1'
                rc = 0 if display_ok else 1
            elif argv[1] == 'search':
                count += 1
                visible = window_pid is not None and (before or count > 1)
                out, rc = ('900', 0) if visible else ('', 1)
            elif argv[1] == 'getwindowname':
                out = 'Example browser window'
            elif argv[1] == 'getwindowpid':
                out = str(window_pid)
            return types.SimpleNamespace(returncode=rc, stdout=out, stderr=err)
        process = types.SimpleNamespace(pid=321, returncode=code, poll=lambda:code)
        def popen(argv, **kwargs):
            kwargs['stdout'].write(b'launcher output\n');kwargs['stdout'].flush()
            kwargs['stderr'].write(b'Snap diagnostic preserved\n');kwargs['stderr'].flush()
            return process
        with patch('subprocess.run', side_effect=run), patch('subprocess.Popen', side_effect=popen) as spawn, \
             patch('tempfile.mkdtemp', return_value=str(self.root/'logs')), \
             patch.object(Path, 'iterdir', return_value=iter([proc_dir])), \
             patch('signal.signal'):
            result = _launch_probe(['firefox', '--new-window', 'https://example.com'], 0)
        return result, spawn

    def test_display_authentication_failure_never_launches(self):
        result, spawn = self.run_probe(display_ok=False)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('Authorization required', result['stderr'])
        spawn.assert_not_called()

    def test_browser_error_retains_stderr_and_nonzero_exit(self):
        result, _ = self.run_probe(code=1)
        self.assertEqual((result['status'], result['exit_code']), ('failed', 1))
        self.assertIn('Snap diagnostic', result['stderr'])
        self.assertTrue(Path(result['log_paths']['stderr']).is_file())

    def test_exit_zero_echo_without_window_is_unknown(self):
        result, _ = self.run_probe(code=0)
        self.assertEqual(result['status'], 'unknown')
        self.assertFalse(result['page_verified'])

    def test_running_process_without_window_is_unknown(self):
        result, _ = self.run_probe(code=None)
        self.assertEqual(result['status'], 'unknown')
        self.assertTrue(result['process_running'])

    def test_own_live_window_confirms_only_window_not_page_or_playback(self):
        result, _ = self.run_probe(code=None, window_pid=321)
        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(result['windows'][0]['pid'], 321)
        self.assertFalse(result['page_verified'])
        self.assertFalse(result['playback_verified'])

    def test_unrelated_window_is_not_launch_success(self):
        result, _ = self.run_probe(code=None, window_pid=999, process_name='other-app')
        self.assertEqual(result['status'], 'unknown')

    def test_snap_mount_process_is_not_browser_success(self):
        result, _ = self.run_probe(code=0, window_pid=999, process_name='snapfuse')
        self.assertEqual(result['status'], 'unknown')

    def test_new_window_owned_by_existing_browser_accepts_handoff(self):
        result, _ = self.run_probe(code=0, window_pid=999)
        self.assertEqual(result['status'], 'succeeded')
        self.assertFalse(result['process_running'])
        self.assertTrue(result['window_processes_running'])

    def test_preexisting_browser_window_cannot_prove_new_launch(self):
        result, _ = self.run_probe(code=0, window_pid=999, before=True)
        self.assertEqual(result['status'], 'unknown')


class DesktopContractTests(unittest.TestCase):
    def setUp(self):
        self.pc = types.SimpleNamespace(bash=Mock(), backend=types.SimpleNamespace(name='fixture'))
        self.hands = Hands(self.pc)

    def test_invalid_launch_inputs_do_not_execute(self):
        for command, wait in [(None, 3), ('', 3), ('firefox', float('nan')), ('firefox', 21),
                              ('cmd.exe /c start anything', 3), ('firefox ; echo launched', 3)]:
            with self.subTest(command=command, wait=wait):
                self.assertEqual(self.hands.launch(command, wait)['status'], 'failed')
        self.pc.bash.assert_not_called()

    def test_bad_url_and_browser_do_not_execute(self):
        for url, browser in [('file:///tmp/private', 'firefox'), ('https://example.com', 'cmd.exe')]:
            self.assertEqual(self.hands.open_url(url, browser)['status'], 'failed')
        self.pc.bash.assert_not_called()

    def test_backend_transport_failure_does_not_become_launch_success(self):
        self.pc.bash.return_value = (124, 'guest command timed out')
        result = self.hands.launch('firefox')
        self.assertEqual(result['status'], 'timed_out')
        self.assertIn('timed out', result['stderr'])

    def test_browser_url_is_passed_as_one_literal_argument(self):
        with patch.object(self.hands, 'launch', return_value={'status':'unknown'}) as launch:
            url = 'https://example.com/?q=a&value=$(oops)'
            result = self.hands.open_url(url, wait=1)
        import shlex
        self.assertEqual(shlex.split(launch.call_args.args[0]), ['firefox', '--new-window', url])
        self.assertFalse(result['page_verified'])

    def test_real_shell_defaults_align_with_hands_and_explicit_override_survives(self):
        bash = shutil.which('bash')
        if os.name == 'nt':
            candidate = Path('C:/Program Files/Git/bin/bash.exe')
            bash = str(candidate) if candidate.is_file() else None
        if not bash:
            self.skipTest('Disposable shell interpreter unavailable')
        env = dict(os.environ, DISPLAY=':0', WAYLAND_DISPLAY='wayland-0', XAUTHORITY='/wrong')
        script = nova_desktop_command("printf '%s|%s|%s' \"$DISPLAY\" \"$XAUTHORITY\" \"${WAYLAND_DISPLAY-unset}\"")
        result = subprocess.run([bash, '-c', script], env=env, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, ':1|/home/nova/.Xauthority|unset')
        explicit = subprocess.run([bash, '-c', nova_desktop_command('export DISPLAY=:0; printf %s "$DISPLAY"')],
                                  env=env, capture_output=True, text=True, timeout=5)
        self.assertEqual(explicit.stdout, ':0')

    def test_tool_preserves_unknown_launch_and_diagnostics(self):
        probe = {'status':'unknown','exit_code':0,'stdout':'wrapper exited','stderr':'diagnostic',
                 'message':'no matching window'}
        fake_router = types.SimpleNamespace(_catastrophic=lambda _:None, _sealed_cmd=lambda _:None)
        with patch.object(tools, 'NovaComputer', return_value=self.pc), \
             patch.object(tools, 'Hands', return_value=self.hands), \
             patch.object(tools, 'handoff', return_value={'owner':'nova'}), \
             patch('nova_computer.session.ensure', return_value=None), \
             patch.object(self.hands, 'launch', return_value=probe), \
             patch.dict(sys.modules, {'nova_voice.tool_router':fake_router}):
            result = tools.call('computer_action', {'action':'launch','parameters':{'command':'firefox'}})
        self.assertIsNone(result.ok)
        self.assertEqual(result.stderr, 'diagnostic')
        self.assertEqual(result.environment['display'], ':1')

    def test_human_handoff_blocks_launch_without_running_it(self):
        with patch.object(tools, 'NovaComputer', return_value=self.pc), \
             patch.object(tools, 'Hands', return_value=self.hands), \
             patch.object(tools, 'handoff', return_value={'owner':'human'}), \
             patch('nova_computer.session.ensure', return_value=None), \
             patch.object(self.hands, 'launch') as launch:
            result = tools.call('computer_action', {'action':'launch','parameters':{'command':'firefox'}})
        self.assertEqual(result.status, 'refused')
        launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
