# @nova: Exercise full-draft witness delivery and tool observability with isolated providers, receipts and images.
import asyncio
import copy
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

BODY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BODY))
from nova_cortex import witness
from nova_runtime import operations
from nova_voice.tool_result import ToolResult

# Nova's log module creates session folders on import; use an inert logger while
# loading the actual inference module. No personal state or provider is touched.
_logger = types.ModuleType('nova_logs.logger')
_logger.log_thought = lambda *a, **k: None
with patch.dict(sys.modules, {'nova_logs.logger': _logger}), patch.object(witness, 'pipeline_event'):
    from nova_voice import nova


def text_of(messages):
    return '\n'.join(m['content'] if isinstance(m['content'], str) else '\n'.join(
        c.get('text', '') for c in m['content']) for m in messages)


def call(name='read_file', **args):
    return '```json\n' + json.dumps({'tool': name, 'args': args}) + '\n```'


class Transcript:
    def to_messages(self, name, system, **kwargs):
        return [{'role': 'system', 'content': system},
                {'role': 'user', 'content': 'Explain what the visible desktop actually shows.'}]


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.events, self.done, self.errors, self.audit_calls, self.main_calls = [], [], [], [], []
        self.tools, self.reads = [], []
        self.generations, self.verdicts, self.results = [], [], []
        self.config = {'max_tool_loops': 12, 'witness_max_rounds': 2,
                       'heavy_witness_enabled': False, 'binding_cloud_escalation': False,
                       'hold_back_streaming': True}
        self.stack.enter_context(patch.object(nova, '_tune', side_effect=lambda k, d: self.config.get(k, d)))
        self.stack.enter_context(patch.object(nova, '_INTEGRITY_OK', True))
        self.stack.enter_context(patch.object(nova, '_claims_a_receipt', return_value=False))
        self.stack.enter_context(patch.object(nova, '_was_asked_to_act', return_value=False))
        self.stack.enter_context(patch.object(nova, '_log_nova_thought'))
        for name, value in [('now_card', ''), ('human_in_room', True),
                            ('minutes_since_last_human', 0), ('session_tool_record', ''),
                            ('wire_record', ''), ('human_record', ''), ('begin_turn', 'fixture')]:
            self.stack.enter_context(patch.object(witness, name, return_value=value))
        self.stack.enter_context(patch.object(witness, 'pipeline_event', side_effect=
            lambda stage, detail='', **kw: self.events.append({'stage': stage, 'detail': detail, **kw})))
        self.stack.enter_context(patch.object(nova, '_fetch_llama_streaming', side_effect=self.fetch))
        self.router = types.ModuleType('nova_voice.tool_router')
        self.router.execute_tool = self.execute
        self.router._execute_tool_inner = self.verify
        self.stack.enter_context(patch.dict(sys.modules, {'nova_voice.tool_router': self.router}))
        self.stack.enter_context(patch.object(operations, 'run_in_worker', side_effect=self.worker))
        token = operations.current_operation.set(operations.Operation(id='fixture-run'))
        self.addCleanup(operations.current_operation.reset, token)

    async def worker(self, fn, *args, **kwargs):
        return fn(*args, **kwargs)

    def execute(self, tool, args, *, operation_id=None):
        self.tools.append((tool, args, operation_id))
        result = self.results.pop(0) if self.results else ToolResult('fixture receipt')
        if isinstance(result, BaseException):
            raise result
        result.operation_id = operation_id
        return result

    def verify(self, tool, args):
        self.reads.append((tool, args))
        return 'fixture evidence remains inconclusive'

    async def fetch(self, messages, on_token, **kwargs):
        if kwargs.get('preserve_messages'):
            self.audit_calls.append((copy.deepcopy(messages), kwargs))
            value = self.verdicts.pop(0)
            if isinstance(value, BaseException):
                raise value
            return value
        self.main_calls.append(copy.deepcopy(messages))
        value = self.generations.pop(0)
        await on_token(value)
        return value

    async def run_turn(self, images=None):
        async def token(_): pass
        async def done(value): self.done.append(value)
        async def error(value): self.errors.append(value)
        await nova.stream_response(Transcript(), token, done, error, images=images)
        await asyncio.sleep(0)  # any disabled background audit exits without I/O
        self.assertEqual(self.errors, [])

    def stages(self):
        return [e['stage'] for e in self.events]

    async def test_whole_delivered_candidate_and_correlated_tool_evidence(self):
        prefix = 'EARLIER CLAIM: the browser was already playing a video.'
        tail = 'LATER CLAIM: I can describe only the desktop shown in the available evidence.'
        self.generations = [prefix + '\n' + call('computer_exec', command='PRIVATE_COMMAND'), tail]
        self.verdicts = ['PASS']
        self.results = [ToolResult('PRIVATE_RESULT', status='failed', exit_code=127,
                                  environment={'target': 'guest', 'shell': 'bash', 'default_display': ':1'})]
        await self.run_turn()
        audit = text_of(self.audit_calls[0][0])
        self.assertIn(self.done[0], audit)
        self.assertIn(prefix, self.done[0])
        self.assertIn(tail, self.done[0])
        started, ended = [e for e in self.events if e['stage'].startswith('tool_')]
        self.assertEqual(started['operation_id'], ended['operation_id'])
        self.assertEqual(started['operation_id'], self.tools[0][2])
        self.assertEqual(ended['run_id'], 'fixture-run')
        self.assertEqual(ended['status'], 'failed')
        self.assertEqual(ended['exit_code'], 127)
        self.assertEqual(ended['environment'], 'guest')
        self.assertNotIn('PRIVATE_', json.dumps([started, ended]))
        observation = text_of(self.main_calls[1])
        self.assertIn('"exit_code": 127', observation)
        self.assertIn('"shell": "bash"', observation)
        self.assertEqual(self.stages().count('witness_pass'), 1)

    async def test_concern_replaces_full_draft_in_novas_own_words(self):
        prefix = 'ORIGINAL PREFIX claims an unobserved browser was working.'
        tail = 'The rest of my answer claimed that the requested video had been watched.'
        revised = 'I have a desktop screenshot, but no evidence that the browser or video opened.'
        self.generations = [prefix + '\n' + call(), tail, revised]
        self.verdicts = ['CONCERN: The video claim lacks visual evidence.', 'PASS']
        await self.run_turn()
        self.assertIn(prefix, text_of(self.audit_calls[0][0]))
        self.assertEqual(self.done, [revised])
        self.assertNotIn(prefix, text_of(self.audit_calls[1][0]))
        self.assertIn(revised, text_of(self.audit_calls[1][0]))
        self.assertIn('witness_answered', self.stages())

    async def test_fourth_read_request_is_incomplete_not_pass(self):
        draft = 'This is Nova\'s own draft, retained without pretending that its audit completed.'
        self.generations = [draft]
        self.verdicts = [call('read_file', path='fixture')] * 4
        await self.run_turn()
        self.assertEqual(len(self.reads), 3)
        self.assertEqual(len(self.audit_calls), 4)
        self.assertIn('No further tool calls will run', text_of(self.audit_calls[-1][0]))
        self.assertEqual(self.done, [draft])
        self.assertIn('witness_incomplete', self.stages())
        self.assertNotIn('witness_pass', self.stages())

    async def test_malformed_verdict_preserves_draft_and_records_incomplete(self):
        draft = 'A complete draft from Nova whose witness returned malformed data instead of a ruling.'
        self.generations = [draft]
        self.verdicts = ['PASS but CONCERN: this is not approval']
        await self.run_turn()
        self.assertEqual(self.done, [draft])
        self.assertIn('witness_incomplete', self.stages())
        self.assertNotIn('witness_pass', self.stages())

    async def test_provider_error_preserves_draft_without_exposing_error_payload(self):
        draft = 'A complete draft from Nova whose witness service failed before giving a ruling.'
        self.generations = [draft]
        self.verdicts = [TimeoutError('SECRET endpoint credential must not enter pipeline')]
        await self.run_turn()
        self.assertEqual(self.done, [draft])
        event = next(e for e in self.events if e['stage'] == 'witness_error')
        self.assertEqual(event['status'], 'ERROR')
        self.assertNotIn('SECRET', json.dumps(self.events))
        self.assertNotIn('witness_pass', self.stages())

    async def test_last_three_tool_images_and_user_pixels_reach_witness(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for i in range(4):
                path = Path(directory) / f'frame-{i}.png'
                path.write_bytes(b'fixture-image-' + bytes([i]))
                paths.append(path)
            self.results = [ToolResult('screenshot', artifacts=[{'kind': 'image', 'path': str(p)}],
                              environment={'display': ':1', 'target': 'nova_desktop'}) for p in paths]
            self.generations = [call('computer_look')] * 4 + [
                'The screenshot shows the desktop; it does not establish video playback or audio.']
            self.verdicts = ['PASS']
            await self.run_turn(images=[{'dataUrl': 'data:image/png;base64,dXNlcg=='}])
        parts = self.audit_calls[0][0][1]['content']
        urls = [p['image_url']['url'] for p in parts if p['type'] == 'image_url']
        import base64
        self.assertEqual(len(urls), 4)
        self.assertEqual(urls[0], 'data:image/png;base64,dXNlcg==')
        self.assertEqual([base64.b64decode(u.split(',')[1]) for u in urls[1:]],
                         [b'fixture-image-' + bytes([i]) for i in (1, 2, 3)])
        self.assertIn('1 earlier image(s) were omitted', text_of(self.audit_calls[0][0]))
        self.assertIn('display=:1', text_of(self.audit_calls[0][0]))
        self.assertIn('does not prove playback', text_of(self.audit_calls[0][0]))

    async def test_failed_attempt_does_not_trigger_false_zero_tools_challenge(self):
        for status in ('failed', 'unknown'):
            with self.subTest(status=status):
                self.generations = [call('computer_exec', command='fixture'),
                    'I checked the desktop; the command failed with exit code 127.']
                self.results = [ToolResult('fixture failure', status=status, exit_code=127)]
                self.verdicts = ['PASS']
                from nova_cortex import integrity
                self.assertTrue(integrity.claims_a_receipt(self.generations[-1]))
                with patch.object(nova, '_claims_a_receipt', integrity.claims_a_receipt):
                    await self.run_turn()
                self.assertNotIn('assertion_challenge', self.stages())
                self.assertEqual(len(self.generations), 0)

    async def test_earlier_claim_is_visible_to_assertion_guard_before_audit(self):
        # No complete attempted tool: a separate guard still sees all final text.
        draft = 'I checked the desktop and the browser was visible in the screenshot.'
        self.generations = [draft, call('computer_look'),
                            'The screenshot confirms only the desktop, not video playback or audio.']
        self.verdicts = ['PASS']
        from nova_cortex import integrity
        with patch.object(nova, '_claims_a_receipt', integrity.claims_a_receipt):
            await self.run_turn()
        challenged = [e for e in self.events if e['stage'] == 'assertion_challenge']
        self.assertEqual(len(challenged), 1)
        self.assertEqual(challenged[0]['draft'], draft)

    async def test_unknown_tool_status_stays_unknown(self):
        self.generations = [call(), 'The available output does not provide a confirmed success status for this action.']
        self.results = [ToolResult('untyped adapter', status='unknown')]
        self.verdicts = ['INCOMPLETE: The tool result is unverified.']
        await self.run_turn()
        ended = next(e for e in self.events if e['stage'] == 'tool_completed')
        self.assertIsNone(ended['ok'])
        self.assertEqual(ended['status'], 'unknown')

    async def test_cancelled_tool_has_correlated_terminal_event(self):
        self.generations = [call()]
        self.results = [asyncio.CancelledError()]
        with self.assertRaises(asyncio.CancelledError):
            await self.run_turn()
        events = [e for e in self.events if e['stage'].startswith('tool_')]
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]['operation_id'], events[1]['operation_id'])
        self.assertEqual(events[1]['status'], 'cancellation_requested')
        self.assertIn('cleanup may still be pending', events[1]['detail'])
        self.assertEqual(self.done, [])


class VerdictTests(unittest.TestCase):
    def test_only_complete_explicit_pass_is_approval(self):
        for value in ('PASS', '2. PASS.', '```text\nPASS!\n```', '```\npass\n```'):
            with self.subTest(value=value):
                self.assertEqual(witness.parse_witness_verdict(value).status, 'PASS')
        for value in ('', 'PASSAGE', 'PASS but CONCERN: wrong', 'PASS\nCONCERN: wrong',
                      '{}', call(), 'CONCERN:', '```plain\nPASS\n```', 'PASS because it looks fine'):
            with self.subTest(value=value):
                self.assertEqual(witness.parse_witness_verdict(value).status, 'INCOMPLETE')
                self.assertIsNotNone(witness.parse_witness(value))
        self.assertEqual(witness.parse_witness_verdict('CONCERN: Missing proof').status, 'CONCERN')
        self.assertEqual(witness.parse_witness_verdict('PASS', exhausted=True).status, 'INCOMPLETE')
        self.assertEqual(witness.parse_witness_verdict('PASS', error='provider failed').status, 'ERROR')

    def test_replay_load_and_incomplete_status_without_network(self):
        spec = importlib.util.spec_from_file_location('fixture_replay', BODY / 'nova_witness' / 'replay.py')
        replay = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(replay)
        loaded = replay.load_witness(BODY.parent)
        with patch.object(replay, 'ask', return_value=(call(), 0.1)):
            result = replay.run_case(loaded, 'http://unused.invalid', {
                'draft': 'fixture', 'expected': 'PASS'})
        self.assertEqual(result['got'], 'INCOMPLETE')
        self.assertFalse(result['correct'])
        with patch.object(replay, 'ask', return_value=('PASS', 0.1)):
            result = replay.run_case(loaded, 'http://unused.invalid', {'draft': 'fixture', 'expected': 'PASS'})
        self.assertTrue(result['correct'])

    def test_missing_pixels_are_not_a_blanket_visual_pass(self):
        with patch.object(witness, 'wire_record', return_value=''), \
             patch.object(witness, 'human_record', return_value=''), \
             patch.object(witness, 'session_tool_record', return_value=''):
            prompt = text_of(witness.build_witness('visual claim', [], has_image=True))
        self.assertIn('pixels are NOT included', prompt)
        self.assertIn('report INCOMPLETE', prompt)
        self.assertNotIn('Her image descriptions are grounded', prompt)

    def test_exhausted_prompt_has_no_tool_menu_and_keeps_all_evidence(self):
        with patch.object(witness, 'wire_record', return_value='fixture wire'), \
             patch.object(witness, 'human_record', return_value='fixture human'), \
             patch.object(witness, 'session_tool_record', return_value='fixture session'):
            messages = witness.build_witness('COMPLETE_DRAFT', [('read_file', {}, 'receipt')],
                prior_concern='old concern', checks=[('read_file', {}, 'prior result')], reads_remaining=0)
        prompt = text_of(messages)
        for fragment in ('COMPLETE_DRAFT', 'fixture wire', 'fixture human', 'fixture session',
                         'old concern', 'prior result', 'receipt'):
            self.assertIn(fragment, prompt)
        self.assertIn('no tool calls are available', messages[0]['content'])
        self.assertNotIn(witness._VERIFY_BLOCK, prompt)
        self.assertNotIn('A single read-only tool call', prompt)
        self.assertIn(witness._EVIDENCE_GRADES, prompt)
        self.assertTrue(messages[1]['content'].endswith('never counts as completed verification.'))

    def test_environment_survives_receipt_serialization(self):
        result = ToolResult('ok', environment={'target': 'guest', 'shell': 'bash'})
        self.assertEqual(result.to_dict()['environment'], {'target': 'guest', 'shell': 'bash'})


class AuditTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_fetch_preserves_entire_long_candidate(self):
        messages = [{'role': 'system', 'content': 'audit'},
                    {'role': 'user', 'content': 'PREFIX' + 'x' * 30000 + 'FINAL_CLAIM'}]
        sent = []
        class Response:
            is_success = True
            def raise_for_status(self): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def aiter_lines(self):
                yield 'data: ' + json.dumps({'choices': [{'delta': {'content': 'PASS'}}]})
                yield 'data: [DONE]'
        class Client:
            def __init__(self, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            def stream(self, method, url, *, json):
                sent.append(json)
                return Response()
        async def token(_): pass
        with patch.object(nova.httpx, 'AsyncClient', Client), \
             patch.object(nova, '_fit_messages_to_window', side_effect=AssertionError('must not truncate audit')):
            result = await nova._fetch_llama_streaming(messages, token, preserve_messages=True)
        self.assertEqual(result, 'PASS')
        self.assertEqual(sent[0]['messages'], messages)
        self.assertTrue(sent[0]['messages'][1]['content'].endswith('FINAL_CLAIM'))


if __name__ == '__main__':
    unittest.main()
