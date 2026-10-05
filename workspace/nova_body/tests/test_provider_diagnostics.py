# @nova: Verify opt-in exact provider snapshots, stream timing and bounded/cancel-safe diagnostics without network or Nova state.
import ast
import asyncio
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

BODY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BODY))
from nova_voice import provider_diagnostics as diagnostics
from nova_cortex.context_budget import fit_messages


class ProviderDiagnostics(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'diagnostics'
        p = patch.object(diagnostics, 'ROOT', self.root)
        p.start(); self.addCleanup(p.stop)

    def enable(self, seconds=300, capture_id='fixture'):
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'capture.json').write_text(json.dumps({
            'capture_id': capture_id,
            'expires_at': (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()}), encoding='utf-8')

    def records(self):
        return [json.loads(p.read_text(encoding='utf-8')) for p in (self.root / 'fixture').glob('*.json')]

    def fetch(self, handler):
        path = BODY / 'nova_voice/nova.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        functions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and n.name in {'_fetch_llama_streaming', '_diagnostic_payload'}]
        ns = {'MAX_TOKENS_CHAT': 128, 'Callable': lambda: None, 'Awaitable': lambda: None,
              'Optional': lambda: None, 'asyncio': asyncio, 'json': json,
              '_provider_diagnostics': diagnostics,
              '_fit_messages_to_window': lambda messages, **kw: fit_messages(messages),
              'LLAMA_CPP_URL': 'https://fixture.invalid/completions'}
        # Postponed annotations let the extracted production function execute unchanged.
        functions.insert(0, ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0))
        class Client:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            def stream(self, method, url, *, json):
                return handler(copy.deepcopy(json))
        ns['httpx'] = types.SimpleNamespace(AsyncClient=lambda **kw: Client())
        exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), str(path), 'exec'), ns)
        return ns['_fetch_llama_streaming']

    async def test_default_off_and_expired_or_invalid_markers_create_no_receipts(self):
        self.assertIsNone(diagnostics.begin({'messages': []}, phase='generation'))
        self.assertFalse(self.root.exists())
        for seconds, name in [(-1, 'fixture'), (1200, 'fixture'), (300, '../escape')]:
            self.enable(seconds, name)
            self.assertIsNone(diagnostics.begin({'messages': []}, phase='generation'))
        self.assertFalse((self.root / 'fixture').exists())

    async def test_actual_fetch_snapshot_matches_outgoing_fields_and_captures_usage(self):
        self.enable()
        payloads, delivered = [], []
        class Response:
            is_success = True
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            def raise_for_status(self): pass
            async def aiter_lines(self):
                yield 'data: ' + json.dumps({'choices': [{'delta': {'reasoning_content': 'thought'}}]})
                yield 'data: ' + json.dumps({'choices': [{'delta': {'content': 'Hello.'}, 'finish_reason': 'stop'}],
                    'usage': {'prompt_tokens': 42, 'completion_tokens': 3}, 'timings': {'prompt_ms': 2.5}})
                yield 'data: [DONE]'
        def handler(payload):
            payloads.append(payload); return Response()
        async def token(text): delivered.append(text)
        messages = [{'role': 'system', 'content': 'fixture'},
                    {'role': 'user', 'content': 'Cole → you: Say hello.'}]
        result = await self.fetch(handler)(messages, token, enable_thinking=False)
        record, = self.records()
        self.assertEqual(result, 'Hello.')
        self.assertEqual(delivered, ['Hello.'])
        self.assertEqual(record['payload'], payloads[0])
        self.assertEqual(record['canonical_payload_sha256'], diagnostics._hash(payloads[0]))
        self.assertEqual(record['current_request_index'], 1)
        self.assertEqual(record['status'], 'completed')
        self.assertEqual(record['usage']['prompt_tokens'], 42)
        self.assertEqual(record['thinking_chars'], 7)
        self.assertLessEqual(record['first_token_ms'], record['first_content_ms'])
        self.assertLessEqual(record['first_content_ms'], record['elapsed_ms'])

    async def test_cancelled_transport_has_terminal_receipt_and_propagates_cancel(self):
        self.enable()
        class Response:
            is_success = True
            async def __aenter__(self): raise asyncio.CancelledError()
            async def __aexit__(self, *args): return False
        async def token(_): pass
        with self.assertRaises(asyncio.CancelledError):
            await self.fetch(lambda payload: Response())([], token)
        record, = self.records()
        self.assertEqual(record['status'], 'cancelled')
        self.assertIsNone(record['first_token_ms'])

    async def test_transport_error_remains_error_without_error_payload_in_receipt(self):
        self.enable()
        def failure(payload): raise RuntimeError('SECRET must not be logged')
        async def token(_): pass
        with self.assertRaises(RuntimeError):
            await self.fetch(failure)([], token)
        record, = self.records()
        self.assertEqual(record['status'], 'error')
        self.assertNotIn('SECRET', json.dumps(record))

    async def test_image_pixels_are_omitted_without_mutating_original(self):
        self.enable()
        payload = {'messages': [{'role': 'user', 'content': [{'type': 'image_url',
                    'image_url': {'url': 'data:image/png;base64,PRIVATEPIXELS'}}]}]}
        original = copy.deepcopy(payload)
        trace = diagnostics.begin(payload, phase='audit')
        trace.finish('completed')
        record, = self.records()
        self.assertNotIn('PRIVATEPIXELS', json.dumps(record))
        self.assertEqual(payload, original)
        self.assertEqual(record['canonical_payload_sha256'], diagnostics._hash(original))
        self.assertEqual(record['phase'], 'audit')

    async def test_count_and_byte_limits_do_not_interrupt_generation(self):
        self.enable()
        with patch.object(diagnostics, 'MAX_FILES', 2):
            traces = [diagnostics.begin({'messages': []}, phase='generation') for _ in range(3)]
            self.assertEqual(sum(t is not None for t in traces), 2)
            for trace in traces[:2]: trace.finish('completed')
        self.assertEqual(len(self.records()), 2)
        with patch.object(diagnostics, 'MAX_TOTAL_BYTES', 1):
            self.assertIsNone(diagnostics.begin({'messages': []}, phase='generation'))
        with patch.object(diagnostics, 'MAX_FILE_BYTES', 1):
            self.assertIsNone(diagnostics.begin({'messages': []}, phase='generation'))
        self.assertEqual(len(self.records()), 2)
        self.assertFalse(list(self.root.rglob('*.tmp')))

    async def test_phase_timings_are_correlated_without_prompt_content(self):
        self.enable()
        diagnostics.record_phase('context_memory', diagnostics.time.perf_counter(), request_id='fixture-request')
        record, = self.records()
        self.assertEqual(record['phase'], 'context_memory')
        self.assertEqual(record['request_id'], 'fixture-request')
        self.assertGreaterEqual(record['elapsed_ms'], 0)
        self.assertNotIn('payload', record)


if __name__ == '__main__':
    unittest.main()
