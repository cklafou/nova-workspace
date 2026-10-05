# @nova: Regression coverage for controller lifecycle, widgets and model process control.
# Last updated: 2026-10-05 21:27:11
"""Regression coverage without starting Nova or inspecting her model directory."""
import ast
import asyncio
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch
from fastapi.responses import JSONResponse

from general_tools.nova_chat.widget_data import read_jsonl_tail
from general_tools.nova_console.hub import LogHub

ROOT = Path(__file__).resolve().parents[3]


def functions(path, names, namespace):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    nodes = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    for node in nodes:
        node.decorator_list = []
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


class ControllerRepairTests(unittest.TestCase):
    def test_hub_accepts_idempotent_restart_and_rejects_competing_shutdown(self):
        hub = LogHub(ROOT)
        self.assertEqual(hub.request_lifecycle('restart')[1], 202)
        self.assertEqual(hub.request_lifecycle('restart')[1], 202)
        self.assertEqual(hub.request_lifecycle('shutdown')[1], 409)
        self.assertTrue(hub._restart_req and hub._shutdown_req)

    def test_shutdown_never_becomes_restart_from_second_click(self):
        hub = LogHub(ROOT)
        hub.request_lifecycle('shutdown')
        self.assertEqual(hub.request_lifecycle('restart')[1], 409)
        self.assertFalse(hub._restart_req)

    def test_real_hub_http_acknowledges_then_releases_socket(self):
        import urllib.request
        import socket
        hub = LogHub(ROOT)
        hub.serve(0)
        port = hub._httpd.server_address[1]
        try:
            with urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{port}/api/restart', data=b'{}')) as response:
                self.assertEqual(response.status, 202)
                self.assertEqual(json.load(response)['action'], 'restart')
        finally:
            hub.shutdown()
        with socket.socket() as connection:
            self.assertNotEqual(connection.connect_ex(('127.0.0.1', port)), 0)

    def test_tail_returns_newest_valid_records_not_oldest_prefix(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'pipeline.jsonl'
            path.write_text(''.join(json.dumps({'i': i, 'data': 'x'*100})+'\n' for i in range(100))+'{"partial":', encoding='utf-8')
            rows = read_jsonl_tail(path, limit=3, max_bytes=1000)
            self.assertEqual([row['i'] for row in rows], [97, 98, 99])

    def test_missing_pipeline_has_honest_empty_state(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(read_jsonl_tail(Path(temp)/'missing'), [])

    def test_launcher_unavailable_is_failure_not_restart_issued(self):
        ns = functions(ROOT/'general_tools/nova_chat/server.py', {'_launcher_action'}, {'asyncio': asyncio, 'json': json, 'JSONResponse': JSONResponse})
        with patch('urllib.request.urlopen', side_effect=OSError('offline')):
            result = asyncio.run(ns['_launcher_action']('restart'))
        self.assertEqual(result.status_code, 503)
        self.assertFalse(json.loads(result.body)['ok'])

    def test_lifecycle_buttons_stop_current_work_before_requesting_teardown(self):
        for function in ['restart_full', 'shutdown_services', 'shutdown_endpoint']:
            events = []
            async def stop():
                events.append('stop')
            async def action(name):
                events.append(name)
                return 'accepted'
            ns = functions(ROOT/'general_tools/nova_chat/server.py', {function}, {'stop_endpoint':stop, '_launcher_action':action})
            self.assertEqual(asyncio.run(ns[function]()), 'accepted')
            self.assertEqual(events, ['stop', 'restart' if function == 'restart_full' else 'shutdown'])

    def test_launcher_acknowledgement_preserves_accepted_status(self):
        ns = functions(ROOT/'general_tools/nova_chat/server.py', {'_launcher_action'}, {'asyncio': asyncio, 'json': json, 'JSONResponse': JSONResponse})
        response = Mock(status=202)
        response.read.return_value = b'{"ok":true,"accepted":true}'
        context = Mock()
        context.__enter__ = Mock(return_value=response)
        context.__exit__ = Mock(return_value=False)
        with patch('urllib.request.urlopen', return_value=context):
            result = asyncio.run(ns['_launcher_action']('restart'))
        self.assertEqual(result.status_code, 202)

    def test_busy_service_prevents_duplicate_launcher(self):
        spawn = Mock()
        ns = functions(ROOT/'nova_start.py', {'_relaunch_after_shutdown'}, {
            'CHAT_ONLY':False, 'CHAT_PORT':8765, 'port_open':lambda port:port==8765, 'log':Mock(),
            'subprocess':types.SimpleNamespace(Popen=spawn)})
        ns['_relaunch_after_shutdown']()
        spawn.assert_not_called()

    def test_requested_shutdown_unblocks_wait_without_killing_child_early(self):
        signal = threading.Event(); signal.set()
        child = Mock(); child.poll.return_value = None
        ns = functions(ROOT/'nova_start.py', {'_wait_for_process'}, {'_SHUTDOWN':signal})
        ns['_wait_for_process'](child)
        child.terminate.assert_not_called()

    def test_file_tree_prunes_models_and_runs_off_thread(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'models').mkdir(); (root/'nova_body').mkdir()
            (root/'nova_body'/'status.md').write_text('ready')
            visited = []
            original = Path.iterdir
            def track(path):
                visited.append(path.name)
                return original(path)
            ns = functions(ROOT/'general_tools/nova_chat/server.py', {'files_tree'}, {
                'Path':Path, 'WORKSPACE_ROOT':root, 'EXCLUDE_DIRS':{'models'},
                'JSONResponse':JSONResponse, 'asyncio':asyncio})
            with patch.object(Path, 'iterdir', track):
                result = asyncio.run(ns['files_tree']())
            self.assertNotIn('models', visited)
            self.assertEqual(json.loads(result.body)['children'][0]['name'], 'nova_body')

    def test_two_gpu_metrics_are_summed(self):
        ns = functions(ROOT/'nova_body/nova_runtime/runtime.py', {'read_system_metrics'}, {})
        with patch('subprocess.run', return_value=types.SimpleNamespace(returncode=0, stdout='8192, 16384\n12288, 24576\n')):
            result = ns['read_system_metrics'](None)
        self.assertEqual(result['vram'], '20.0/40.0 GB (2 GPUs)')
        self.assertEqual(result['vram_pct'], 50)

    def test_model_stop_does_not_kill_independent_witness(self):
        import subprocess, sys
        run = Mock()
        ns = functions(ROOT/'nova_body/nova_runtime/llama_control.py', {'_kill_port'}, {'subprocess':subprocess, 'sys':sys})
        control = types.SimpleNamespace(port=8080, launcher_path=Path('start_llama_qwen36.cmd'), _run=run)
        ns['_kill_port'](control)
        command = run.call_args.args[0][-1]
        self.assertIn('-LocalPort 8080 -State Listen', command)
        self.assertNotIn('Stop-Process -Name', command)
        self.assertNotIn('8081', command)

    def test_model_start_does_not_duplicate_a_loading_server(self):
        import socket
        ns = functions(ROOT/'nova_body/nova_runtime/llama_control.py', {'start'}, {'socket':socket})
        control = types.SimpleNamespace(port=8080, _pending_start=0, _lifecycle_lock=threading.RLock(), _start=Mock())
        with patch('socket.socket') as connection:
            connection.return_value.__enter__.return_value.connect_ex.return_value=0
            self.assertFalse(ns['start'](control)['started'])
        control._start.assert_not_called()

    def test_repeated_start_before_port_binds_spawns_once(self):
        import socket
        ns = functions(ROOT/'nova_body/nova_runtime/llama_control.py', {'start'}, {'socket':socket})
        control = types.SimpleNamespace(port=8080, _pending_start=0, _lifecycle_lock=threading.RLock(), _start=Mock(return_value={'ok':True}))
        with patch('socket.socket') as connection, patch('time.monotonic', return_value=100):
            connection.return_value.__enter__.return_value.connect_ex.return_value=1
            self.assertTrue(ns['start'](control)['ok'])
            self.assertFalse(ns['start'](control)['started'])
        control._start.assert_called_once()

    def test_model_stop_surfaces_timeout(self):
        import subprocess, sys
        ns = functions(ROOT/'nova_body/nova_runtime/llama_control.py', {'_kill_port'}, {'subprocess':subprocess, 'sys':sys})
        control = types.SimpleNamespace(port=8080, launcher_path=Path('start_llama_qwen36.cmd'), _run=Mock(side_effect=TimeoutError('stuck')))
        with self.assertRaisesRegex(RuntimeError, 'Could not stop'):
            ns['_kill_port'](control)

    def test_launcher_stops_guardian_before_services_and_restarts_last(self):
        events = []
        signal = threading.Event(); signal.set()
        hub = types.SimpleNamespace(_restart_req=True, shutdown=lambda:events.append('hub'))
        ns = {'CHAT_ONLY':False, '_check_controller_mode':lambda:None, '_configure_nova_mode':lambda *args:None, 'HUB':hub, '_SHUTDOWN':signal, 'WS':ROOT, 'CHAT_PORT':8765, '_app_backend':'qt',
              'os':types.SimpleNamespace(getpid=lambda:1), 'time':types.SimpleNamespace(time=lambda:0, sleep=lambda _:None),
              'banner':lambda _:None, 'log':lambda *args:None, '_watch_for_shutdown':lambda:None,
              '_wait_for_process':lambda _:None, 'port_open':lambda _:False,
              'wait_for_llama':lambda:True, 'wait_for_nova':lambda:True, 'wait_for_witness':lambda:True,
              '_relaunch_after_shutdown':lambda:events.append('restart'),
              '_shutdown_nova':lambda p:events.append(p.label)}
        for name in ['llama','witness','nova','watcher','guardian','console','app']:
            proc = Mock(pid=1);proc.label=name;proc.poll.return_value=0
            ns['open_app_window' if name=='app' else 'start_'+name] = lambda p=proc:p
            ns['stop_'+name] = lambda p,n=name:events.append(n)
        functions(ROOT/'nova_start.py', {'main'}, ns)['main']()
        self.assertEqual(events, ['guardian','watcher','nova','app','llama','witness','hub','restart'])


if __name__ == '__main__':
    unittest.main()
