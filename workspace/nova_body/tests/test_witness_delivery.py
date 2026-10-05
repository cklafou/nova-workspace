# Last updated: 2026-10-05 21:36:15
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
        self.delivery_audits, self.delivery_order = [], []
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

    async def collect_audit(self, metadata):
        self.delivery_audits.append(copy.deepcopy(metadata))
        self.delivery_order.append('audit')

    async def run_turn(self, images=None, on_audit=None, transcript=None):
        async def token(_): pass
        async def done(value):
            self.done.append(value)
            self.delivery_order.append('done')
        async def error(value): self.errors.append(value)
        await nova.stream_response(transcript or Transcript(), token, done, error,
                                   images=images, on_audit=on_audit)
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
        self.assertIn("exit=127", observation)
        self.assertIn("shell=bash", observation)
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

    async def test_unknown_witness_tool_is_invalid_without_dispatch_or_green_verdict(self):
        self.generations = ["This reply makes a claim that requires an audit before it is delivered."]
        self.verdicts = [call('run_command', command='must not execute')]
        await self.run_turn()
        self.assertEqual(self.reads, [])
        self.assertEqual(len(self.audit_calls), 1)
        self.assertNotIn('witness_verified', self.stages())
        self.assertIn('witness_incomplete', self.stages())
        self.assertNotIn('witness_pass', self.stages())

    async def test_witness_read_counts_keep_output_failure_and_refusal_distinct(self):
        counts = nova._audit_read_counts([('read_file', {}, 'fixture content'),
            ('read_file', {}, 'ERROR: missing'), ('list_dir', {}, 'REFUSED: unavailable')])
        self.assertEqual(counts, {'read_attempts': 3, 'read_returned': 1,
                                 'read_refused': 1, 'read_failed': 1})

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
        ended = next(e for e in self.events if e['stage'] in {'tool_completed', 'tool_finished'})
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

    async def test_concern_quoting_tool_json_is_not_executed_as_a_read(self):
        self.generations = ["The video was definitely opened on the desktop.",
                            "The attempted launch did not verify a visible page."]
        self.verdicts = ['CONCERN: {"tool":"computer_exec","args":{}} is only an attempted launch.', 'PASS']
        await self.run_turn()
        self.assertEqual(self.reads, [])
        self.assertIn('witness_concern', self.stages())
        self.assertEqual(self.done, ['The attempted launch did not verify a visible page.'])

    async def test_failed_reaudit_keeps_correction_check_and_honest_status(self):
        from unittest.mock import Mock
        self.config['heavy_witness_enabled'] = True
        self.generations = ["The file exists and contains the exact expected output.",
                            "The file content is unverified; I withdrew the earlier claim."]
        self.verdicts = ['CONCERN: The file receipt contradicts the claimed contents.',
                         'INCOMPLETE: The second audit could not settle the file contents.']
        dispatched = []
        def fake_task(coro):
            dispatched.append(coro.cr_code.co_name)
            coro.close()
            task = Mock()
            task.add_done_callback.side_effect = lambda fn: fn(task)
            return task
        with patch.object(nova.asyncio, 'create_task', side_effect=fake_task):
            await self.run_turn()
        self.assertIn('_heavy_correction_check', dispatched)
        answered = [e for e in self.events if e['stage']=='witness_answered']
        self.assertEqual(answered[-1]['status'], 'INCOMPLETE')
        self.assertNotIn('witness_pass', self.stages())

    async def test_tool_at_loop_limit_never_delivers_raw_json_or_duplicate_prefix(self):
        self.config['max_tool_loops'] = 1
        self.generations = ['One attempt now.\n'+call('computer_exec', command='PRIVATE_COMMAND')]
        self.results = [ToolResult('done')]
        await self.run_turn()
        self.assertEqual(self.done[0].count('One attempt now.'), 1)
        self.assertNotIn('PRIVATE_COMMAND', self.done[0])
        self.assertNotIn('"tool"', self.done[0])


    async def test_final_audit_callback_precedes_delivery_and_preserves_actual_status(self):
        for verdict, status in [('PASS', 'PASS'), ('', 'INCOMPLETE'),
                                (TimeoutError('fixture'), 'ERROR')]:
            with self.subTest(status=status):
                self.generations = ['This candidate describes the limited evidence available for the current request.']
                self.verdicts = [verdict]
                await self.run_turn(on_audit=self.collect_audit)
                self.assertEqual(self.delivery_audits[-1]['status'], status)
                self.assertEqual(self.delivery_audits[-1]['source'], 'inline')
                self.assertTrue(self.delivery_audits[-1]['reason'])
                self.assertEqual(self.delivery_order[-2:], ['audit', 'done'])

    async def test_concern_on_final_candidate_is_not_approval(self):
        self.config['witness_max_rounds'] = 1
        self.generations = ['This candidate maintains a disputed file claim without resolving its evidence.'] * 2
        self.verdicts = ['CONCERN: File contents remain disputed.'] * 2
        await self.run_turn(on_audit=self.collect_audit)
        self.assertEqual(len(self.delivery_audits), 1)
        self.assertEqual(self.delivery_audits[0]['status'], 'CONCERN')
        self.assertIn('File contents', self.delivery_audits[0]['reason'])

    async def test_revision_reports_only_its_own_final_audit(self):
        revised = 'My revised reply describes only the evidence that the screenshot actually supports.'
        self.generations = ['The first candidate claims a browser result without enough visual evidence.', revised]
        self.verdicts = ['CONCERN: The browser claim is unsupported.', 'INCOMPLETE: Remaining image was omitted.']
        await self.run_turn(on_audit=self.collect_audit)
        self.assertEqual(self.done, [revised])
        self.assertEqual(self.delivery_audits, [{'status': 'INCOMPLETE', 'source': 'inline',
                                              'reason': 'Remaining image was omitted.'}])

    async def test_echo_revision_does_not_inherit_pass_when_final_answer_is_unaudited(self):
        repeated = 'This was the earlier delivered answer, sufficiently long to trigger the witness check.'
        class History(Transcript):
            def to_messages(self, *args, **kwargs):
                messages = super().to_messages(*args, **kwargs)
                messages.insert(1, {'role': 'assistant', 'content': repeated})
                return messages
        self.generations = [repeated, 'Okay.']
        self.verdicts = ['PASS']
        with patch.object(witness, 'needs_witness', return_value=False):
            await self.run_turn(on_audit=self.collect_audit, transcript=History())
        self.assertIn('echo_retry', self.stages())
        self.assertEqual(self.done, ['Okay.'])
        self.assertEqual(self.delivery_audits[0]['status'], 'NOT_RUN')
        self.assertEqual(self.delivery_audits[0]['source'], 'none')

    async def test_tool_continuation_and_salvage_cannot_inherit_prior_pass(self):
        repeated = 'An earlier delivered answer repeats here and should be discarded after its audit.'
        class History(Transcript):
            def to_messages(self, *args, **kwargs):
                messages = super().to_messages(*args, **kwargs)
                messages.insert(1, {'role': 'assistant', 'content': repeated})
                return messages
        self.config['max_tool_loops'] = 2
        self.generations = [repeated, 'Attempting a receipt.\n' + call('read_file', path='fixture')]
        self.verdicts = ['PASS']
        await self.run_turn(on_audit=self.collect_audit, transcript=History())
        self.assertIn('loop_exhausted', self.stages())
        self.assertEqual(len(self.tools), 1)
        self.assertEqual(self.delivery_audits[0]['status'], 'NOT_RUN')
        self.assertIn('salvage', self.delivery_audits[0]['reason'])
        self.assertEqual(len(self.delivery_audits), 1)

    async def test_audit_observer_failure_does_not_suppress_final_reply(self):
        for failure in (ValueError('fixture observer failure'), asyncio.CancelledError()):
            with self.subTest(failure=type(failure).__name__):
                self.generations = ['This candidate is delivered even when its optional metadata observer fails.']
                self.verdicts = ['PASS']
                async def observer(metadata):
                    metadata['status'] = 'MUTATED_BY_OBSERVER'
                    raise failure
                before = len(self.done)
                await self.run_turn(on_audit=observer)
                self.assertEqual(len(self.done), before + 1)

    async def test_real_turn_cancellation_during_observer_still_cancels_delivery(self):
        self.generations = ['This candidate is approved, but the turn will be cancelled during observation.']
        self.verdicts = ['PASS']
        entered = asyncio.Event()
        waiting = asyncio.Event()
        async def observer(metadata):
            entered.set()
            await waiting.wait()
        task = asyncio.create_task(self.run_turn(on_audit=observer))
        await asyncio.wait_for(entered.wait(), timeout=2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.done, [])

    async def test_already_pending_cancel_prevents_observer_and_final_delivery(self):
        for observe in (False, True):
            with self.subTest(observer=observe):
                self.generations = ['This approved candidate must not ship after an already pending stop.']
                self.verdicts = ['PASS']
                observer_calls = []
                async def observer(metadata):
                    observer_calls.append(metadata)
                    await asyncio.sleep(0)
                def event(stage, detail='', **fields):
                    self.events.append({'stage': stage, 'detail': detail, **fields})
                    if stage == 'witness_pass':
                        # No await remains before _deliver; its first await used to
                        # swallow this real cancellation as an observer failure.
                        asyncio.current_task().cancel()
                with patch.object(witness, 'pipeline_event', side_effect=event):
                    task = asyncio.create_task(self.run_turn(on_audit=observer if observe else None))
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                self.assertTrue(task.cancelled())
                self.assertEqual(observer_calls, [])
                self.assertEqual(self.done, [])

    async def test_observer_cannot_swallow_task_stop_and_allow_delivery(self):
        for yield_before_return in (False, True):
            with self.subTest(yield_before_return=yield_before_return):
                self.generations = ['This approved candidate must not ship after the observer receives a real stop.']
                self.verdicts = ['PASS']
                async def observer(metadata):
                    asyncio.current_task().cancel()
                    if yield_before_return:
                        try:
                            await asyncio.sleep(0)
                        except asyncio.CancelledError:
                            pass  # Even a mistaken observer cannot clear the stop.
                task = asyncio.create_task(self.run_turn(on_audit=observer))
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assertTrue(task.cancelled())
                self.assertEqual(self.done, [])

    async def test_foreground_arbiter_pass_is_bound_to_same_delivered_candidate(self):
        self.config.update(witness_max_rounds=1, heavy_witness_enabled=True,
                           binding_cloud_escalation=True)
        draft = 'This candidate keeps its file claim because the existing foreground arbiter will settle it.'
        self.generations, self.verdicts = [draft, draft], ['CONCERN: File claim disputed.'] * 2
        judged = []
        def judge(candidate, *args, **kwargs):
            judged.append(candidate)
            return 'PASS'
        loader = types.SimpleNamespace(exec_module=lambda module: None)
        module = types.SimpleNamespace(heavy_witness=judge)
        with patch.object(witness, 'is_checkable_fact_concern', return_value=True), \
             patch.object(importlib.util, 'spec_from_file_location', return_value=types.SimpleNamespace(loader=loader)), \
             patch.object(importlib.util, 'module_from_spec', return_value=module):
            await self.run_turn(on_audit=self.collect_audit)
        self.assertEqual(judged, self.done)
        self.assertEqual(self.delivery_audits[0]['status'], 'PASS')
        self.assertEqual(self.delivery_audits[0]['source'], 'foreground_arbiter')
        self.assertEqual(len(self.delivery_audits), 1)

    async def test_background_cloud_cannot_rewrite_delivered_audit_snapshot(self):
        self.config.update(witness_max_rounds=1, heavy_witness_enabled=True,
                           binding_cloud_escalation=False)
        draft = 'This candidate still has a disputed file claim when the synchronous reply is delivered.'
        self.generations, self.verdicts = [draft, draft], ['CONCERN: File claim disputed.'] * 2
        loader = types.SimpleNamespace(exec_module=lambda module: None)
        module = types.SimpleNamespace(heavy_witness=lambda *a, **k: 'PASS')
        tasks = []
        create_task = asyncio.create_task
        def tracked(coro):
            task = create_task(coro)
            tasks.append(task)
            return task
        with patch.object(witness, 'is_checkable_fact_concern', return_value=True), \
             patch.object(importlib.util, 'spec_from_file_location', return_value=types.SimpleNamespace(loader=loader)), \
             patch.object(importlib.util, 'module_from_spec', return_value=module), \
             patch.object(nova.asyncio, 'create_task', side_effect=tracked):
            await self.run_turn(on_audit=self.collect_audit)
            snapshot = copy.deepcopy(self.delivery_audits)
            await asyncio.gather(*tasks)
        self.assertTrue(tasks)
        self.assertEqual(self.delivery_audits, snapshot)
        self.assertEqual(snapshot[0]['status'], 'CONCERN')
        self.assertEqual(snapshot[0]['source'], 'inline')


class VerdictTests(unittest.TestCase):
    def test_diagnostic_payload_omits_pixels_without_mutating_request(self):
        original = {'messages': [{'content': [{'type': 'image_url', 'image_url':
                    {'url': 'data:image/png;base64,SECRET_PIXELS'}},
                    {'type': 'text', 'text': 'keep the diagnostic text'}]}]}
        rendered = nova._diagnostic_payload(original)
        self.assertNotIn('SECRET_PIXELS', json.dumps(rendered))
        self.assertIn('keep the diagnostic text', json.dumps(rendered))
        self.assertIn('SECRET_PIXELS', json.dumps(original))

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
