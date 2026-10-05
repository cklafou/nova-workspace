# Last updated: 2026-10-05 18:30:24
# @nova: Verify private collaboration connector identity, cursor handling, bounds, failures and MCP framing without contacting Nova.
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import os
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

MODULE = Path(__file__).resolve().parents[2] / 'nova_collaboration' / 'bridge.py'
spec = importlib.util.spec_from_file_location('collaboration_bridge_under_test', MODULE)
bridge_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge_module)


class FakeResponse:
    def __init__(self, data):
        self.raw = json.dumps(data).encode('utf-8')
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, count):
        return self.raw[:count]


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.credential = Path(self.temp.name) / 'credentials.json'
        self.credential.write_text(json.dumps({'version': 1, 'tokens': {'codex': 'secret-codex-token-123456', 'claude': 'secret-claude-token-456789'}}))
        self.calls = []
        def opener(request, timeout):
            self.calls.append((request, timeout))
            if '/events?' in request.full_url:
                return FakeResponse({'events': [{'seq': 7, 'participant': 'claude', 'text': 'Verified.'}], 'cursor': 7, 'has_more': False})
            return FakeResponse({'ok': True})
        self.bridge = bridge_module.Bridge('codex', credentials_file=self.credential, opener=opener)

    def test_default_credentials_are_outside_virtualized_appdata(self):
        home = Path(self.temp.name) / 'user-home'
        with patch.dict(os.environ, {'NOVA_COLLABORATION_DIR': '', 'LOCALAPPDATA': str(Path(self.temp.name) / 'virtual-appdata')}), \
             patch.object(bridge_module.Path, 'home', return_value=home):
            self.assertEqual(bridge_module.credentials_path(), home / 'ProjectNovaData' / 'Collaboration' / 'credentials.json')

    def test_explicit_broker_directory_overrides_default(self):
        configured = Path(self.temp.name) / 'explicit-room'
        with patch.dict(os.environ, {'NOVA_COLLABORATION_DIR': str(configured)}):
            self.assertEqual(bridge_module.credentials_path(), configured / 'credentials.json')

    def test_old_appdata_credentials_are_not_a_silent_fallback(self):
        home = Path(self.temp.name) / 'user-home'
        legacy = Path(self.temp.name) / 'legacy-appdata'
        old = legacy / 'ProjectNova' / 'Collaboration' / 'credentials.json'
        old.parent.mkdir(parents=True)
        old.write_text(json.dumps({'tokens': {'codex': 'old-token-must-not-be-selected'}}))
        with patch.dict(os.environ, {'NOVA_COLLABORATION_DIR': '', 'LOCALAPPDATA': str(legacy)}), \
             patch.object(bridge_module.Path, 'home', return_value=home):
            bridge = bridge_module.Bridge('codex')
            with self.assertRaises(bridge_module.BridgeError):
                bridge._token()

    def test_send_uses_bound_identity_and_stable_id(self):
        self.bridge.send('Keep Unicode: Nova \u03b1', 'repeatable-id')
        request = self.calls[-1][0]
        self.assertEqual(request.get_header('Authorization'), 'Bearer secret-codex-token-123456')
        self.assertEqual(request.get_header('X-nova-collaboration-participant'), 'codex')
        self.assertEqual(json.loads(request.data), {'text': 'Keep Unicode: Nova \u03b1', 'client_message_id': 'repeatable-id'})
        self.assertNotIn('participant', json.loads(request.data))

    def test_wait_updates_cursor_and_presence(self):
        result = self.bridge.read(after=4, wait=45)
        self.assertEqual(result['cursor'], 7)
        self.assertEqual(self.bridge.last_read, 7)
        self.assertEqual(json.loads(self.calls[0][0].data)['state'], 'waiting')
        self.assertIn('after=4&wait=45', self.calls[1][0].full_url)
        self.assertEqual(self.calls[1][1], 57)
        self.assertEqual(json.loads(self.calls[-1][0].data), {'state': 'active', 'last_read': 7})

    def test_rejects_remote_origin_before_reading_credentials(self):
        for url in ['https://example.com', 'http://example.com', 'http://localhost@evil.test', 'http://localhost/path', 'http://127.0.0.1:9999', 'http://localhost:bad']:
            with self.subTest(url=url), self.assertRaises(bridge_module.BridgeError):
                bridge_module.Bridge('claude', url, self.credential)

    def test_redirects_never_forward_credentials(self):
        from urllib.request import Request
        request = Request('http://127.0.0.1:8765/api/collaboration/state', headers={'Authorization': 'Bearer PRIVATE'})
        with self.assertRaises(bridge_module.BridgeError):
            bridge_module.NoRedirect().redirect_request(request, None, 302, 'Redirect', {}, 'https://example.com/capture')

    def test_inputs_bounded_before_network(self):
        for after, seconds in [(-1, 0), (True, 1), (0, 46), (0, float('nan'))]:
            with self.subTest(after=after, seconds=seconds), self.assertRaises(bridge_module.BridgeError):
                self.bridge.read(after, seconds)
        for text in ['', ' ', 'x' * (bridge_module.MAX_TEXT + 1)]:
            with self.assertRaises(bridge_module.BridgeError):
                self.bridge.send(text)
        self.assertEqual(self.calls, [])

    def test_missing_token_fails_without_dumping_config(self):
        self.credential.write_text('{"tokens":{"claude":"OTHER-SECRET"}}')
        with self.assertRaises(bridge_module.BridgeError) as caught:
            self.bridge.status()
        self.assertNotIn('OTHER-SECRET', str(caught.exception))

    def test_error_body_does_not_leak_tokens(self):
        def rejected(request, timeout):
            raise HTTPError(request.full_url, 403, 'secret-codex-token-123456', {}, io.BytesIO(b'private response'))
        self.bridge.opener = rejected
        with self.assertRaises(bridge_module.BridgeError) as caught:
            self.bridge.send('hello')
        self.assertEqual(str(caught.exception), 'Nova Chat rejected the collaboration request (HTTP 403).')

    def test_mcp_stream_initializes_lists_tools_and_marks_offline(self):
        requests = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'collaboration_read', 'arguments': {'after': 0}}},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'collaboration_send', 'arguments': {'text': 'hello', 'participant': 'cole'}}},
        ]
        sink = io.StringIO()
        bridge_module.serve_mcp(self.bridge, io.StringIO('\n'.join(map(json.dumps, requests)) + '\n'), sink)
        replies = [json.loads(line) for line in sink.getvalue().splitlines()]
        self.assertEqual(len(replies), 4)
        self.assertEqual(replies[0]['result']['protocolVersion'], '2025-06-18')
        self.assertEqual(len(replies[1]['result']['tools']), 4)
        self.assertFalse(replies[2]['result']['isError'])
        self.assertTrue(replies[3]['result']['isError'])
        self.assertEqual(json.loads(self.calls[-1][0].data)['state'], 'offline')
        self.assertNotIn('secret-codex-token', sink.getvalue())

    def test_mcp_rejects_unknown_method_and_invalid_arguments(self):
        with self.assertRaises(bridge_module.BridgeError):
            bridge_module.call_tool(self.bridge, 'collaboration_read', [])
        sink = io.StringIO()
        bridge_module.serve_mcp(self.bridge, io.StringIO('{"jsonrpc":"2.0","id":8,"method":"arbitrary/exec"}\n'), sink)
        self.assertEqual(json.loads(sink.getvalue())['error']['code'], -32601)



class FileBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bridge = bridge_module.FileBridge('claude', self.root)
        self.calls = []
        self.stop = threading.Event()
        self.worker = None

    def broker(self, handler):
        requests = self.root / 'requests'
        replies = self.root / 'replies'
        requests.mkdir(exist_ok=True)
        replies.mkdir(exist_ok=True)
        def serve():
            while not self.stop.is_set():
                for path in list(requests.glob('*.json')):
                    request = json.loads(path.read_text(encoding='utf-8'))
                    self.calls.append(request)
                    result = handler(request)
                    envelope = {'id': request['id'], 'ok': True, 'result': result}
                    temp = replies / (request['id'] + '.tmp')
                    temp.write_text(json.dumps(envelope), encoding='utf-8')
                    os.replace(temp, replies / path.name)
                    path.unlink()
                self.stop.wait(0.005)
        self.worker = threading.Thread(target=serve, daemon=True)
        self.worker.start()
        self.addCleanup(self.shutdown)

    def shutdown(self):
        self.stop.set()
        if self.worker:
            self.worker.join(2)

    def test_send_waits_for_ack_without_token_or_participant_payload(self):
        self.broker(lambda request: {'seq': 1, 'text': request.get('text', '')})
        result = self.bridge.send('Claude via mounted files', 'stable-file-id')
        self.assertEqual(result['seq'], 1)
        request = self.calls[-1]
        self.assertEqual(request['action'], 'send')
        self.assertEqual(request['client_message_id'], 'stable-file-id')
        self.assertNotIn('participant', request)
        self.assertNotIn('token', request)
        self.assertTrue(list((self.root / 'replies').glob('*.json')))
        self.assertFalse(list((self.root / 'requests').glob('*.tmp')))

    def test_file_transport_cannot_claim_codex(self):
        with self.assertRaises(bridge_module.BridgeError):
            bridge_module.FileBridge('codex', self.root)

    def test_wait_reads_server_cursor_and_updates_receipt(self):
        def handler(request):
            if request['action'] == 'read':
                return {'events': [{'seq': 8, 'participant': 'codex', 'text': 'Evidence ready.'}], 'cursor': 8, 'has_more': False}
            return {'ok': True}
        self.broker(handler)
        result = self.bridge.read(7, 45)
        self.assertEqual(result['cursor'], 8)
        self.assertEqual(self.calls[0]['state'], 'waiting')
        self.assertEqual(self.calls[1]['after'], 7)
        self.assertEqual(self.calls[-1]['last_read'], 8)

    def test_final_poll_keeps_ack_budget_and_delivers_late_reply(self):
        read_timeouts = []
        def request(route, body=None, timeout=10):
            if route.startswith('events?'):
                read_timeouts.append(timeout)
                events = [] if len(read_timeouts) == 1 else [{'seq': 8, 'participant': 'codex', 'text': 'Arrived during final poll.'}]
                return {'events': events, 'cursor': 8 if events else 7, 'has_more': False}
            return {'ok': True}
        # First poll finishes at 43.9 s; another starts at 44.9 s and is
        # acknowledged at 48.4 s. Its message must survive the nominal deadline.
        with patch.object(self.bridge, '_request', side_effect=request), \
             patch.object(bridge_module.time, 'monotonic', side_effect=[0, 43.9, 44.9, 48.4]), \
             patch.object(bridge_module.time, 'sleep'):
            result = self.bridge.read(7, 45)
        self.assertEqual(read_timeouts, [10, 10])
        self.assertEqual(result['events'][0]['seq'], 8)
        self.assertEqual(self.bridge.last_read, 8)

    def test_unacknowledged_send_reports_uncertainty_and_retry_id(self):
        with self.assertRaises(bridge_module.BridgeError) as caught:
            self.bridge._request('messages', {'text': 'hello', 'client_message_id': 'retry-this-id'}, timeout=0.001)
        self.assertIn('delivery is unconfirmed', str(caught.exception))
        self.assertIn('retry-this-id', str(caught.exception))
        request = next((self.root / 'requests').glob('*.json'))
        self.assertEqual(json.loads(request.read_text())['client_message_id'], 'retry-this-id')


if __name__ == '__main__':
    unittest.main()
