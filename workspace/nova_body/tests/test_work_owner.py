# @nova: Verify body work exclusion, autonomous attention, deadline accounting and headless input persistence without live services.
import ast
import asyncio
import contextvars
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

BODY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BODY))
from nova_runtime.work_owner import WorkCoordinator
from nova_runtime.conversation import ConversationTurns
from nova_runtime.transcript_store import TranscriptStore


def runtime_methods(namespace):
    path = BODY / 'nova_runtime/runtime.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'NovaRuntime')
    names = {'run_autonomy', '_run_one_wake', '_attend_inputs_headless', '_generate_headless'}
    methods = [node for node in cls.body if isinstance(node, ast.AsyncFunctionDef) and node.name in names]
    assert len(methods) == len(names)
    for method in methods:
        method.decorator_list = []
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_task_reentrant_and_competing_task_waits(self):
        coordinator = WorkCoordinator()
        entered = asyncio.Event()
        async with coordinator.lease('autonomy', focus='t1') as owner:
            async with coordinator.lease('conversation') as nested:
                self.assertIs(nested, owner)
                self.assertEqual(owner.depth, 2)
            async def competing():
                self.assertIsNone(coordinator.try_claim('conversation'))
                async with coordinator.lease('conversation') as next_owner:
                    entered.set()
                    return next_owner.id
            task = asyncio.create_task(competing())
            await asyncio.sleep(0)
            self.assertFalse(entered.is_set())
        next_id = await asyncio.wait_for(task, 1)
        self.assertNotEqual(next_id, owner.id)
        self.assertFalse(coordinator.snapshot()['active'])

    async def test_serializable_ordered_input_survives_release_and_can_be_cancelled(self):
        coordinator = WorkCoordinator()
        async with coordinator.lease('autonomy'):
            entry = {'content': [{'type': 'text', 'text': 'first'}], 'reply_to': 'm1', 'request_id': 'r1', 'conversation_id': 'c'}
            self.assertTrue(coordinator.submit_input(entry))
            coordinator.submit_input(entry)
            entry['content'][0]['text'] = 'mutated outside'
            coordinator.submit_input({'content': 'second', 'reply_to': 'm2', 'conversation_id': 'c'})
            coordinator.submit_input({'content': 'cancelled', 'reply_to': 'm3', 'conversation_id': 'c'})
            self.assertEqual(coordinator.remove_input('m3', conversation_id='wrong'), 0)
            self.assertEqual(coordinator.remove_input('m3', conversation_id='c'), 1)
        self.assertEqual(coordinator.snapshot()['pending_inputs'], 2)
        async with coordinator.lease('autonomy') as next_owner:
            entries = next_owner.take_inputs()
            self.assertEqual([e['reply_to'] for e in entries], ['m1', 'm2'])
            self.assertEqual(entries[0]['content'][0]['text'], 'first')
            self.assertEqual(next_owner.take_inputs(), [])
            with self.assertRaises(TypeError):
                coordinator.submit_input({'content': 'x', 'reply_to': object()})
        self.assertFalse(coordinator.submit_input({'content': 'no owner'}))

    async def test_snapshot_never_exposes_private_phase_output_and_context_is_bounded(self):
        coordinator = WorkCoordinator()
        async with coordinator.lease('autonomy', focus='task-7') as owner:
            owner.record_phase('reflection', 'PRIVATE-' * 2000, 'op-1')
            owner.record_phase('execution', 'Action summary, not proof', 'op-2')
            self.assertNotIn('PRIVATE', json.dumps(coordinator.snapshot()))
            context = coordinator.context_for_input(1800)
            self.assertLessEqual(len(context), 1800)
            self.assertIn('task-7', context)
            self.assertIn('shortened', context)
            self.assertIn('Action summary', context)
            self.assertEqual(owner.phase_outputs[0]['text'], 'PRIVATE-' * 2000)

    async def test_cancelled_waiter_does_not_release_another_owner(self):
        coordinator = WorkCoordinator()
        async with coordinator.lease('autonomy') as owner:
            async def wait():
                async with coordinator.lease('conversation'):
                    self.fail('waiter should not acquire')
            waiter = asyncio.create_task(wait())
            await asyncio.sleep(0)
            waiter.cancel()
            await asyncio.gather(waiter, return_exceptions=True)
            self.assertIs(coordinator.active, owner)


class RuntimeAttentionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tasks = {'t1': {'id': 't1', 'status': 'open', 'title': 'original ongoing work'}}
        self.active = ['t1']
        self.progress = []
        self.bus_events = []
        self.bus = types.SimpleNamespace(publish=AsyncMock(side_effect=self.bus_events.append))
        self.executive = types.SimpleNamespace(
            autonomy_enabled=lambda: True, active_focus=lambda: self.active[0],
            should_wake=lambda pending: (True, 'fixture event'), _cfg=lambda: {'wake_budget_seconds': 30},
            ensure_standing_chores=lambda: [], pick_execution_target=lambda: self.active[0],
            build_execution=lambda task, recent: task['id'] + ':' + recent,
            parse_execution=lambda text: ('progress', text), reset_continuation=Mock(),
            schedule_soon=Mock(), set_active=lambda value: self.active.__setitem__(0, value),
            note_real_work=Mock())
        self.tasking = types.SimpleNamespace(all_tasks=lambda: self.tasks,
            progress=lambda tid, value: self.progress.append((tid, value)), complete=Mock(return_value=True))
        cortex = types.ModuleType('nova_cortex')
        cortex.executive = self.executive
        cortex.tasking = self.tasking
        cortex.integrity = types.SimpleNamespace(reconcile_board=lambda: None)
        self.modules = patch.dict(sys.modules, {'nova_cortex': cortex})
        self.modules.start(); self.addCleanup(self.modules.stop)
        async def worker(fn, *args, **kwargs): return fn(*args, **kwargs)
        from datetime import datetime
        self.ns = runtime_methods(dict(asyncio=asyncio, datetime=datetime,
            WorkQueue=lambda: types.SimpleNamespace(claim=lambda **kw: None),
            body_path=lambda *args, **kwargs: self.root.joinpath(*args),
            current_phase=contextvars.ContextVar('test-phase', default='idle'),
            current_operation=contextvars.ContextVar('test-op', default=None),
            run_in_worker=worker, TranscriptStore=TranscriptStore))
        self.runtime = types.SimpleNamespace(workspace=self.root, work_owner=WorkCoordinator(), conversations=ConversationTurns(),
            bus=self.bus, emit=AsyncMock(), populate_touch=Mock(), clear_touch_active=Mock(), _autonomy_stop=False)
        for name in ('run_autonomy', '_run_one_wake', '_attend_inputs_headless', '_generate_headless'):
            setattr(self.runtime, name, types.MethodType(self.ns[name], self.runtime))

    async def test_wake_claim_prevents_chat_race_during_model_availability(self):
        attempts = []
        async def competing():
            attempts.append(self.runtime.work_owner.try_claim('conversation'))
        async def available():
            await asyncio.create_task(competing())
            return True
        async def wake(*args, **kwargs):
            self.assertIs(kwargs['owner'], self.runtime.work_owner.active)
            self.runtime._autonomy_stop = True
        self.runtime._run_one_wake = wake
        real_sleep = asyncio.sleep
        async def quick_sleep(*args): await real_sleep(0)
        self.ns['asyncio'] = types.SimpleNamespace(sleep=quick_sleep, timeout=asyncio.timeout,
            current_task=asyncio.current_task, get_running_loop=asyncio.get_running_loop,
            TimeoutError=asyncio.TimeoutError, CancelledError=asyncio.CancelledError)
        await self.runtime.run_autonomy(perceive_cole_pending=lambda: False, recent_context=lambda: '',
            model_available=available, generate=None, is_busy=lambda: False, set_busy=Mock())
        self.assertEqual(attempts, [None])
        self.assertIsNone(self.runtime.work_owner.active)

    async def test_force_wake_is_not_consumed_when_body_owner_is_busy(self):
        force = asyncio.Event(); force.set()
        def occupied(*args, **kwargs):
            self.runtime._autonomy_stop = True
            return None
        self.runtime.work_owner.try_claim = occupied
        async def quick_sleep(*args): pass
        self.ns['asyncio'] = types.SimpleNamespace(sleep=quick_sleep,
            TimeoutError=asyncio.TimeoutError, CancelledError=asyncio.CancelledError)
        available = AsyncMock()
        await self.runtime.run_autonomy(perceive_cole_pending=lambda: False, recent_context=lambda: '',
            model_available=available, generate=None, is_busy=lambda: False, set_busy=Mock(), force_wake=force)
        self.assertTrue(force.is_set())
        available.assert_not_awaited()

    async def test_human_attention_keeps_owner_output_and_resumes_original_task(self):
        generated = []
        attended = []
        recent = ['before input']
        async def generate(prompt, speak):
            generated.append(prompt)
            if len(generated) == 1:
                for i in range(3):
                    self.runtime.work_owner.submit_input({'content': f'follow {i}', 'reply_to': f'm{i}'})
                context = await self.runtime.work_owner.active.on_boundary({'stage': 'tool_complete',
                    'last_completed_action': {'tool': 'fixture_tool', 'operation_id': 'tool-1', 'status': 'unknown', 'ok': None}})
                self.assertIn('ALREADY been delivered', context[0]['content'])
                self.assertIn('follow 2', context[0]['content'])
            return f'completed step {len(generated)}'
        async def attend(owner):
            entries = owner.take_inputs()
            if not entries: return False
            self.assertIn('tool-1', owner.phase_outputs[-1]['text'])
            self.assertIn('unknown', owner.phase_outputs[-1]['text'])
            async with self.runtime.work_owner.lease('conversation') as same:
                self.assertIs(owner, same)
                self.assertIn('t1', same.prompt_context())
                attended.extend(entry['content'] for entry in entries)
                owner.record_phase('attention', '\n'.join(attended) + '\nThe human reply was delivered.')
            recent[0] = 'after answering all three'
            return True
        async with self.runtime.work_owner.lease('autonomy', focus='t1') as owner:
            for _ in range(2):
                await self.runtime._run_one_wake('fixture', False, False, lambda: recent[0],
                    generate, Mock(), None, owner=owner, attend_inputs=attend)
            self.assertEqual([p['text'] for p in owner.phase_outputs if p['phase'] == 'execution'], ['completed step 1', 'completed step 2'])
        self.assertEqual(attended, ['follow 0', 'follow 1', 'follow 2'])
        self.assertEqual(generated, ['t1:before input', 't1:after answering all three'])
        self.assertEqual(self.active[0], 't1')
        self.assertEqual(self.progress, [('t1', 'completed step 1'), ('t1', 'completed step 2')])

    async def test_human_attention_suspends_autonomy_deadline(self):
        async def generate(*args):
            self.runtime.work_owner.submit_input({'content': 'human input', 'reply_to': 'm1'})
            return 'completed step'
        async def attend(owner):
            if not owner.take_inputs(): return False
            await asyncio.sleep(.08)
            return True
        async with self.runtime.work_owner.lease('autonomy') as owner:
            async with asyncio.timeout(.04) as deadline:
                owner.timeout = deadline
                await self.runtime._run_one_wake('fixture', False, False, lambda: '', generate,
                    Mock(), None, owner=owner, attend_inputs=attend)
                self.assertFalse(deadline.expired())
                owner.timeout = None
        self.assertEqual(self.progress, [], 'A pre-attention board directive must be re-evaluated')

    async def test_attention_task_change_prevents_stale_completion_from_clearing_new_focus(self):
        self.executive.parse_execution = lambda _: ('done', 'old completion')
        async def generate(*args):
            self.runtime.work_owner.submit_input({'content': 'change task', 'reply_to': 'm1'})
            return 'DONE: old completion'
        async def attend(owner):
            if not owner.take_inputs(): return False
            self.tasks['t1']['status'] = 'cancelled'
            self.tasks['t2'] = {'id': 't2', 'status': 'open', 'title': 'new task'}
            self.active[0] = 't2'
            return True
        async with self.runtime.work_owner.lease('autonomy') as owner:
            await self.runtime._run_one_wake('fixture', False, False, lambda: '', generate,
                Mock(), None, owner=owner, attend_inputs=attend)
            self.assertEqual(owner.phase_outputs[-1]['text'], 'DONE: old completion')
        self.tasking.complete.assert_not_called()
        self.assertEqual(self.active[0], 't2')

    async def _start_test_daemon(self, wake, stop_requested=None):
        self.runtime._run_one_wake = wake
        real_sleep = asyncio.sleep
        async def quick_sleep(delay):
            await real_sleep(0 if delay in (2, 3, .5) else delay)
        self.ns['asyncio'] = types.SimpleNamespace(sleep=quick_sleep, timeout=asyncio.timeout,
            current_task=asyncio.current_task, get_running_loop=asyncio.get_running_loop,
            TimeoutError=asyncio.TimeoutError, CancelledError=asyncio.CancelledError)
        task = asyncio.create_task(self.runtime.run_autonomy(perceive_cole_pending=lambda: False,
            recent_context=lambda: '', model_available=AsyncMock(return_value=True), generate=None,
            is_busy=lambda: False, set_busy=Mock(), stop_requested=stop_requested))
        async def cleanup():
            if not task.done(): task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self.addAsyncCleanup(cleanup)
        return task

    async def test_scoped_stop_finishes_current_lease_and_next_wake_still_runs(self):
        first, second = asyncio.Event(), asyncio.Event()
        owners = []
        async def wake(*args, **kwargs):
            owners.append(kwargs['owner'])
            if len(owners) == 1:
                first.set()
                await asyncio.Event().wait()
            second.set()
            self.runtime._autonomy_stop = True
        daemon = await self._start_test_daemon(wake)
        await asyncio.wait_for(first.wait(), 1)
        self.assertTrue(owners[0].request_stop())
        await asyncio.wait_for(owners[0].finished.wait(), 1)
        await asyncio.wait_for(second.wait(), 1)
        await asyncio.wait_for(daemon, 1)
        self.assertFalse(daemon.cancelled())
        self.assertEqual(daemon.cancelling(), 0)
        self.assertNotEqual(owners[0].id, owners[1].id)

    async def test_external_daemon_cancel_is_not_absorbed_as_owned_stop(self):
        first = asyncio.Event()
        async def wake(*args, **kwargs):
            first.set()
            await asyncio.Event().wait()
        daemon = await self._start_test_daemon(wake)
        await asyncio.wait_for(first.wait(), 1)
        owner = self.runtime.work_owner.active
        daemon.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await daemon
        self.assertTrue(owner.finished.is_set())
        self.assertIsNone(self.runtime.work_owner.active)

    async def test_owned_stop_waits_for_supervised_worker_cleanup_before_finished(self):
        first = asyncio.Event()
        worker = {'running': 'fixture tool'}
        async def wake(*args, **kwargs):
            kwargs['owner'].operation = types.SimpleNamespace(workers=worker, processes={}, cleanup={})
            first.set()
            await asyncio.Event().wait()
        daemon = await self._start_test_daemon(wake)
        await asyncio.wait_for(first.wait(), 1)
        owner = self.runtime.work_owner.active
        owner.request_stop()
        await asyncio.sleep(.01)
        self.assertFalse(owner.finished.is_set())
        self.assertTrue(owner.request_stop(), 'Repeated Stop is idempotent during cleanup')
        self.assertIs(self.runtime.work_owner.active, owner)
        self.runtime._autonomy_stop = True
        worker.clear()
        await asyncio.wait_for(owner.finished.wait(), 1)
        await asyncio.wait_for(daemon, 1)

    async def test_headless_reply_marks_only_captured_input_and_persists_output(self):
        transcript = TranscriptStore(self.root/'transcript.jsonl')
        first = transcript.append('Cole', 'first input')
        self.runtime.transcript = transcript
        async def generate(prompt, cole_pending, **callbacks):
            self.assertTrue(cole_pending)
            transcript.append('Cole', 'arrived during answer')
            await callbacks['on_segment']('Reply to the captured first input.',
                {'turn_id': callbacks['steering'].turn_id, 'segment_index': 1, 'input_revision': 0,
                 'audit': {'status': 'PASS'}, 'final': True})
            return 'Reply to the captured first input.'
        self.runtime._generate_headless = generate
        async with self.runtime.work_owner.lease('autonomy') as owner:
            self.assertTrue(await self.runtime._attend_inputs_headless(owner))
        reopened = TranscriptStore(transcript.log_path)
        self.assertEqual(reopened.attended_through, first['seq'])
        self.assertTrue(reopened.has_unread_cole())
        self.assertEqual(reopened.messages[-1]['author'], 'Nova')
        self.assertEqual(self.bus_events[-1]['type'], 'runtime_reply')
        self.assertEqual(self.bus_events[-1]['input_through'], first['seq'])

    async def test_global_stop_clears_cancel_counter_and_manual_resume_runs(self):
        first = asyncio.Event()
        stop = asyncio.Event()
        calls = []
        async def wake(*args, **kwargs):
            calls.append(kwargs['owner'])
            if len(calls) == 1:
                first.set()
                await asyncio.Event().wait()
            self.runtime._autonomy_stop = True
        daemon = await self._start_test_daemon(wake, stop_requested=stop)
        await asyncio.wait_for(first.wait(), 1)
        stop.set(); daemon.cancel()
        await asyncio.wait_for(calls[0].finished.wait(), 1)
        self.assertEqual(daemon.cancelling(), 0)
        stop.clear()
        await asyncio.wait_for(daemon, 1)
        self.assertEqual(len(calls), 2)
        self.assertFalse(daemon.cancelled())

    async def test_headless_followup_uses_same_turn_and_segments_persist_without_aggregate_duplicate(self):
        transcript = TranscriptStore(self.root/'transcript.jsonl')
        transcript.append('Cole', 'first request')
        self.runtime.transcript = transcript
        async def generate(prompt, cole_pending, **callbacks):
            turn = callbacks['steering']
            self.assertEqual([m['content'] for m in callbacks['transcript_context'].messages], ['first request'])
            first_meta = {'turn_id': turn.turn_id, 'segment_index': 1, 'input_revision': 0,
                          'audit': {'status': 'PASS'}, 'final': False}
            await callbacks['on_segment']('First spoken segment.', first_meta)
            followup = transcript.append('Cole', 'new information')
            self.assertEqual(await callbacks['on_boundary']({'stage': 'before_provider'}), [])
            entries, revision = await turn.consume()
            self.assertEqual([e['request_id'] for e in entries], [f"runtime-{followup['seq']}"])
            self.assertIn('new information', entries[0]['content'])
            await callbacks['on_segment']('Second spoken segment.', {**first_meta, 'segment_index': 2,
                'input_revision': revision, 'audit': {'status': 'INCOMPLETE'}, 'final': True})
            return 'First spoken segment.\nSecond spoken segment.'
        self.runtime._generate_headless = generate
        async with self.runtime.work_owner.lease('autonomy') as owner:
            self.assertTrue(await self.runtime._attend_inputs_headless(owner))
        reopened = TranscriptStore(transcript.log_path)
        self.assertEqual([m['content'] for m in reopened.messages if m['author']=='Nova'],
                         ['First spoken segment.', 'Second spoken segment.'])
        self.assertFalse(reopened.has_unread_cole())
        self.assertEqual([event['input_revision'] for event in self.bus_events], [0, 1])
        self.assertEqual([event['audit']['status'] for event in self.bus_events], ['PASS', 'INCOMPLETE'])
        self.assertEqual(len({event['turn_id'] for event in self.bus_events}), 1)
        self.assertIsNone(self.runtime.conversations.get('runtime'))

    async def test_reply_coverage_recovers_after_sidecar_failure_and_rejects_invalid_claims(self):
        transcript = TranscriptStore(self.root/'transcript.jsonl')
        first = transcript.append('Cole', 'accepted input')
        with patch.object(transcript, '_persist_state', side_effect=OSError('fixture sidecar failure')):
            with self.assertRaises(OSError):
                transcript.append('Nova', 'durable reply', attended_through=first['seq'])
        reopened = TranscriptStore(transcript.log_path)
        self.assertFalse(reopened.has_unread_cole())
        self.assertEqual(reopened.attended_through, first['seq'])
        for author, claim in [('Cole', 0), ('Nova', 100), ('Nova', True)]:
            with self.assertRaises(ValueError):
                reopened.append(author, 'invalid', attended_through=claim)
        with transcript.log_path.open('a', encoding='utf-8') as out:
            out.write(json.dumps({'author': 'Nova', 'content': 'invalid future claim', 'attended_through': 999})+'\n')
        reopened.reload_from_disk()
        self.assertEqual(reopened.attended_through, first['seq'])

    async def test_real_headless_adapter_forwards_body_turn_and_persists_only_segment(self):
        from nova_runtime.conversation_context import ConversationContext
        self.runtime.transcript = TranscriptStore(self.root/'transcript.jsonl')
        self.runtime.transcript.append('Cole', 'fixture request')
        workspace_context = types.ModuleType('nova_cortex.workspace_context')
        workspace_context.WorkspaceContext = lambda: types.SimpleNamespace(prepare_nova_context=AsyncMock(return_value='fixture grounding'))
        calls = []
        async def generate(name, context, **callbacks):
            calls.append(context)
            self.assertEqual(name, 'Nova')
            self.assertIsInstance(context, ConversationContext)
            self.assertEqual(context.messages[0]['content'], 'fixture request')
            self.assertFalse(callbacks['autonomous'])
            self.assertIn('fixture grounding', callbacks['workspace_context'])
            self.assertIn('ongoing task', callbacks['workspace_context'])
            self.assertEqual(await callbacks['on_boundary']({'stage': 'before_provider'}), [])
            turn = callbacks['steering']
            self.assertIs(turn, self.runtime.conversations.get('runtime'))
            await callbacks['on_segment']('Delivered once.', {'turn_id': turn.turn_id,
                'segment_index': 1, 'input_revision': 0, 'audit': {'status': 'NOT_RUN'}, 'final': True})
            await callbacks['on_done']('Delivered once.')
        self.runtime.model_client = types.SimpleNamespace(generate=generate)
        with patch.dict(sys.modules, {'nova_cortex.workspace_context': workspace_context}):
            async with self.runtime.work_owner.lease('autonomy', focus='t1') as owner:
                self.assertTrue(await self.runtime._attend_inputs_headless(owner))
        self.assertEqual(len(calls), 1)
        self.assertEqual([m['content'] for m in self.runtime.transcript.messages if m['author']=='Nova'], ['Delivered once.'])
        self.assertEqual(self.bus_events[-1]['audit']['status'], 'NOT_RUN')
        self.assertFalse(self.runtime.transcript.has_unread_cole())

    async def test_real_headless_autonomy_adapter_forwards_active_owner_boundary(self):
        workspace_context = types.ModuleType('nova_cortex.workspace_context')
        workspace_context.WorkspaceContext = lambda: types.SimpleNamespace(prepare_nova_context=AsyncMock(return_value='grounding'))
        self.ns['_TickContext'] = lambda prompt: types.SimpleNamespace(prompt=prompt)
        async def generate(name, context, **callbacks):
            self.assertTrue(callbacks['autonomous'])
            self.assertEqual(context.prompt, 'private phase')
            self.assertNotIn('steering', callbacks)
            self.assertNotIn('on_segment', callbacks)
            self.assertEqual(callbacks['on_boundary'], self.runtime.work_owner.active.on_boundary)
            await callbacks['on_boundary']({'stage': 'provider_complete', 'draft': {'text_preview':'fact'}})
            await callbacks['on_done']('phase output')
        self.runtime.model_client = types.SimpleNamespace(generate=generate)
        with patch.dict(sys.modules, {'nova_cortex.workspace_context': workspace_context}):
            async with self.runtime.work_owner.lease('autonomy') as owner:
                self.assertEqual(await self.runtime._generate_headless('private phase', False), 'phase output')
                self.assertEqual(owner.phase_outputs[-1]['phase'], 'boundary:provider_complete')

    async def test_skipped_log_lines_do_not_collide_with_new_sequence_coverage(self):
        path = self.root/'transcript.jsonl'
        path.write_text('not-json\n\n'+json.dumps({'author':'Cole','content':'older'})+'\n', encoding='utf-8')
        transcript = TranscriptStore(path)
        self.assertEqual(transcript.last_seq('Cole'), 2)
        human = transcript.append('Cole', 'newer')
        self.assertEqual(human['seq'], 3)
        reply = transcript.append('Nova', 'answer', attended_through=human['seq'])
        self.assertEqual(reply['seq'], 4)
        reopened = TranscriptStore(path)
        self.assertEqual([m['seq'] for m in reopened.messages], [2,3,4])
        self.assertEqual(reopened.attended_through, 3)
        self.assertFalse(reopened.has_unread_cole())

    async def test_headless_empty_reply_does_not_acknowledge_pending_input(self):
        self.runtime.transcript = TranscriptStore(self.root/'transcript.jsonl')
        self.runtime.transcript.append('Cole', 'unanswered')
        self.runtime._generate_headless = AsyncMock(return_value='')
        async with self.runtime.work_owner.lease('autonomy') as owner:
            self.assertFalse(await self.runtime._attend_inputs_headless(owner))
        self.assertTrue(self.runtime.transcript.has_unread_cole())
        self.assertEqual(self.runtime.transcript.attended_through, -1)
        self.assertEqual(self.bus_events, [])


if __name__ == '__main__':
    unittest.main()
