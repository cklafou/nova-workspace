# @nova: Verify face routing, body-owned continuation, request correlation and Stop with isolated provider/session fixtures.
# Last updated: 2026-10-05 17:52:28
import ast
import asyncio
import contextvars
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import types
import unittest
import uuid
from unittest.mock import AsyncMock, Mock, patch

WORKSPACE = Path(__file__).resolve().parents[3]
SERVER = WORKSPACE / 'general_tools/nova_chat/server.py'
MODEL_CLIENT = WORKSPACE / 'nova_body/nova_runtime/model_client.py'
EVENTS = SERVER.with_name('response_events.py')


def extract(path, names, namespace):
    """Compile complete real functions, removing only service/operation decorators."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
             and node.name in names]
    if {node.name for node in nodes} != set(names):
        raise AssertionError('A tested server contract was removed or renamed')
    for node in nodes:
        node.decorator_list = []
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


spec = importlib.util.spec_from_file_location('isolated_response_events', EVENTS)
events_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(events_module)
NORMALIZERS = extract(MODEL_CLIENT, {'normalize_register'}, {})
conversation_spec = importlib.util.spec_from_file_location('isolated_body_conversation',
    WORKSPACE / 'nova_body/nova_runtime/conversation.py')
conversation_module = importlib.util.module_from_spec(conversation_spec)
conversation_spec.loader.exec_module(conversation_module)
work_spec = importlib.util.spec_from_file_location('isolated_body_work_owner',
    WORKSPACE / 'nova_body/nova_runtime/work_owner.py')
work_module = importlib.util.module_from_spec(work_spec)
work_spec.loader.exec_module(work_module)


class Transcript:
    def __init__(self):
        self.messages = []

    def add(self, author, content, directed_at=None, images=None, response_metadata=None):
        message = {'id': 'stored-' + str(len(self.messages)), 'author': author,
                   'content': content, 'timestamp': datetime.now().isoformat(), 'images': images or []}
        if response_metadata is not None:
            from copy import deepcopy
            message['response_metadata'] = deepcopy(response_metadata)
        self.messages.append(message)
        return message

    def get_recent(self, count):
        return self.messages[-count:]


class SocketClosed(Exception):
    pass


class Socket:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.sent = []

    async def accept(self):
        pass

    async def receive_text(self):
        try:
            return json.dumps(next(self.messages))
        except StopIteration:
            raise SocketClosed()

    async def send_text(self, value):
        self.sent.append(json.loads(value))


class TransportHarness(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.transcript = Transcript()
        self.session = types.SimpleNamespace(active=self.transcript, active_id='session-fixture',
                                             update_meta_from_message=Mock(), get_all_meta=lambda: [])
        self.events = []

        async def broadcast(event):
            self.events.append(event)

        self.ns = dict(
            asyncio=asyncio, json=json, uuid=uuid, datetime=datetime, time=time,
            ResponseEvents=events_module.ResponseEvents,
            normalize_request_id=events_module.normalize_request_id,
            normalize_register=NORMALIZERS['normalize_register'],
            session_mgr=self.session, broadcast=broadcast,
            _nova_lifecycle=types.SimpleNamespace(pending=False),
            workspace=types.SimpleNamespace(update_for_message=Mock(), build_nova_memory_context=lambda *_: '',
                                            build_nova_context_block=lambda: 'fixture context'),
            _DISCOURSE_OK=False, _WS_ROOT_FOR_PROBE=self.root, WORKSPACE_ROOT=self.root,
            body_path=lambda *parts, **kw: self.root.joinpath(*parts),
            _trace_gen=Mock(), _stop_requested=threading.Event(),
            _rt_guard=types.SimpleNamespace(record_success=Mock(), record_error=Mock(return_value=False),
                                           throttled=False),
            _nova_temperature=.7, _nova_top_p=.9, autonomous_mode=True,
            memory_indexer=None, _mirror_to_runtime=Mock(), _maybe_route_inbox=Mock(),
            handle_nova_message=AsyncMock(return_value=[]), _is_echo_of_recent=lambda *_: False,
            _may_speak_to_cole_unprompted=lambda: (True, 'fixture trigger'),
            _llama_error_streak=0, _last_error_msg='', _last_error_time=0,
            _ERROR_DEDUP_WINDOW=30, _LLAMA_ERROR_BACKOFF=3,
            _inflight_upto=0, CLIENT_MAP={'Nova': object()}, _mute_states={'Nova': False},
            _cole_message_queue=[], _request_work={}, _turn_transports={}, is_processing=False,
            get_status=AsyncMock(return_value={'Nova': True}),
            build_response_queue=lambda targets, status: [n for n in targets if status.get(n)],
            parse_directed=lambda content: [], _resolve_speaker=lambda value: value or 'Cole',
            _screen_speaker=lambda speaker, content: (content, ''), _mirror_cole_intent=Mock(),
            emit_event=AsyncMock(), CHAT_ONLY=False, connected_clients=[], active_tasks=[],
            WebSocket=object, WebSocketDisconnect=SocketClosed,
        )
        self.operation = contextvars.ContextVar('voice_transport_fixture_operation', default=None)
        fake_runtime = types.ModuleType('nova_runtime')
        fake_operations = types.ModuleType('nova_runtime.operations')
        fake_operations.current_operation = self.operation
        fake_cortex = types.ModuleType('nova_cortex')
        fake_voice = types.ModuleType('nova_voice')
        self.phase_receipt = Mock()
        fake_voice.provider_diagnostics = types.SimpleNamespace(record_phase=self.phase_receipt)
        fake_cortex.executive = types.SimpleNamespace(note_activity=Mock(), autonomy_enabled=lambda: False)
        self.modules = patch.dict(sys.modules, {'nova_runtime': fake_runtime,
                                                'nova_runtime.operations': fake_operations,
                                                'nova_cortex': fake_cortex, 'nova_voice': fake_voice})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        extract(SERVER, {'run_ai_response', '_run_ai_response_owned', '_attend_autonomy_inputs', '_run_response_queue', '_drain_cole_queue', '_end_queued_request',
                         '_release_request_work', '_scoped_stop_reply', '_stop_request', '_steer_request',
                         'websocket_endpoint'}, self.ns)

    def start_body_response(self, provider, *, owner=None):
        """Run actual face callbacks/registry with the actual body inbox; only inference is fake."""
        owner = owner or Socket([])
        manager = conversation_module.ConversationTurns()
        generate = AsyncMock(side_effect=provider)
        self.ns['_rt'] = types.SimpleNamespace(conversations=manager,
            model_client=types.SimpleNamespace(generate=generate))
        message = self.transcript.add('Cole', 'original request')
        work = dict(owner=owner, request_id='initial', register='voice', msg=message,
                    content=message['content'], transcript=self.transcript,
                    conversation_id=self.session.active_id, directed_at=[], images=[])
        self.ns['_request_work'][(owner, 'initial')] = work
        self.ns['is_processing'] = True
        task = asyncio.create_task(self.ns['run_ai_response']('Nova', object(), 'shared-reply',
            message['content'], register='voice', reply_to=message['id'], request_id='initial',
            request_work=work))
        work.update(task=task, started=True)
        async def cleanup():
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self.addAsyncCleanup(cleanup)
        return owner, manager, task, generate

    async def send_inputs(self, owner, inputs):
        owner.messages = iter([dict(type='message', content=content, register='voice', request_id=rid)
                               for rid, content in inputs])
        await self.ns['websocket_endpoint'](owner)

    async def test_autonomous_owner_attends_input_then_resumes_same_work_with_context(self):
        coordinator = work_module.WorkCoordinator()
        manager = conversation_module.ConversationTurns()
        owner_id = None
        async def provider(_name, transcript, **sinks):
            self.assertEqual(coordinator.active.id, owner_id)
            self.assertEqual(coordinator.active.kind, 'autonomy')
            self.assertIn('original-project-task', sinks['workspace_context'])
            self.assertIn('Completed inspection; action receipt retained.', sinks['workspace_context'])
            turn = sinks['steering']
            await sinks['on_segment']('I incorporated that while keeping the project task.', dict(
                turn_id=turn.turn_id, segment_index=1, input_revision=0,
                audit=dict(status='PASS', input_revision=0, turn_id=turn.turn_id)))
            self.assertTrue(turn.try_seal())
            await sinks['on_done']('I incorporated that while keeping the project task.')
        self.ns['_rt'] = types.SimpleNamespace(work_owner=coordinator, conversations=manager,
            model_client=types.SimpleNamespace(generate=AsyncMock(side_effect=provider)))
        self.ns['is_processing'] = True
        async with coordinator.lease('autonomy', focus='original-project-task') as owner:
            owner_id = owner.id
            owner.record_phase('execution', 'Completed inspection; action receipt retained.')
            ws = Socket([dict(type='message', content='Add a note to the current task.',
                              register='text', request_id='during-autonomy')])
            await self.ns['websocket_endpoint'](ws)
            self.assertTrue(owner.pending)
            self.assertEqual(len(self.ns['_cole_message_queue']), 1)
            self.assertTrue(await self.ns['_attend_autonomy_inputs'](owner))
            self.assertEqual(coordinator.active.id, owner_id)
            self.assertEqual(owner.focus, 'original-project-task')
            self.assertFalse(owner.pending)
            self.assertFalse(self.ns['_cole_message_queue'])
            self.assertEqual(owner.phase_outputs[0]['text'], 'Completed inspection; action receipt retained.')
        self.assertIsNone(coordinator.active)
        self.assertEqual(self.terminal()[0]['request_ids'], ['during-autonomy'])

    async def test_completed_segments_survive_followups_and_terminal_does_not_duplicate_history(self):
        delivered, proceed = asyncio.Event(), asyncio.Event()
        async def provider(_name, transcript, **sinks):
            turn = sinks['steering']
            async def segment(text, index):
                await sinks['on_segment'](text, dict(turn_id=turn.turn_id, segment_index=index,
                    input_revision=turn.applied_revision, audit=dict(status='PASS', source='fixture',
                    reason='Fixture evidence', turn_id=turn.turn_id, input_revision=turn.applied_revision)))
            await segment('First completed useful result.', 1)
            delivered.set()
            await proceed.wait()
            batch, revision = await turn.consume()
            self.assertEqual(len(batch), 1)
            self.assertTrue(batch[0]['content'].endswith('added requirement'))
            await segment('Next result incorporates the added requirement.', 2)
            self.assertTrue(turn.try_seal())
            await sinks['on_done']('First completed useful result.\n\nNext result incorporates the added requirement.')
        owner, _, task, _ = self.start_body_response(provider)
        await asyncio.wait_for(delivered.wait(), 2)
        self.assertFalse(task.done(), 'Useful result must arrive before the work is finished')
        self.assertFalse(self.terminal())
        await self.send_inputs(owner, [('followup', 'added requirement')])
        proceed.set()
        await asyncio.wait_for(task, 2)
        parts = [e for e in self.events if e['type'] == 'message_segment']
        self.assertEqual([e['segment_index'] for e in parts], [1, 2])
        self.assertEqual(parts[0]['request_ids'], ['initial'])
        self.assertEqual(parts[1]['request_ids'], ['initial', 'followup'])
        self.assertEqual(self.terminal()[0]['segment_count'], 2)
        self.assertEqual([m['content'] for m in self.transcript.messages if m['author'] == 'Nova'],
                         [e['content'] for e in parts])
        self.assertEqual(self.terminal()[0]['content'], '\n\n'.join(e['content'] for e in parts))

    async def test_scoped_stop_acknowledges_owner_completion_without_killing_scheduler(self):
        coordinator = work_module.WorkCoordinator()
        self.ns['_rt'] = types.SimpleNamespace(work_owner=coordinator)
        entered, still_available = asyncio.Event(), asyncio.Event()
        async def scheduler():
            async with coordinator.lease('autonomy') as owner:
                entered.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    if not owner.absorb_requested_stop():
                        raise
            still_available.set()
            await asyncio.Event().wait()
        task = asyncio.create_task(scheduler())
        try:
            await asyncio.wait_for(entered.wait(), 2)
            ws = Socket([])
            self.ns['_request_work'][(ws, 'owned-input')] = dict(owner=ws, request_id='owned-input',
                                                               task=task, started=True)
            await self.ns['_stop_request'](ws, 'owned-input')
            self.assertTrue(still_available.is_set())
            self.assertFalse(task.done())
            self.assertIsNone(coordinator.active)
            self.assertEqual(ws.sent, [dict(type='stopped', request_id='owned-input', matched=True)])
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_input_after_nested_seal_enters_next_body_boundary(self):
        coordinator = work_module.WorkCoordinator()
        manager = conversation_module.ConversationTurns()
        self.ns['_rt'] = types.SimpleNamespace(work_owner=coordinator, conversations=manager)
        async with coordinator.lease('autonomy', focus='retained-task') as owner:
            sealed = manager.begin(self.session.active_id)
            self.assertTrue(sealed.try_seal())
            self.ns['_turn_transports'][self.session.active_id] = dict(
                turn=sealed, task=asyncio.current_task(), works=[])
            message = self.transcript.add('Cole', 'arrived during terminal broadcast')
            work = dict(content=message['content'], msg=message, request_id='late',
                        conversation_id=self.session.active_id, directed_at=[])
            self.assertFalse(self.ns['_steer_request'](work))
            self.assertTrue(work['body_admitted'])
            self.assertEqual(owner.take_inputs()[0]['reply_to'], message['id'])
            manager.end(self.session.active_id, sealed)

    async def test_index_failure_cannot_suppress_a_saved_segment(self):
        async def provider(_name, transcript, **sinks):
            turn = sinks['steering']
            await sinks['on_segment']('Saved despite index outage.', dict(turn_id=turn.turn_id,
                segment_index=1, input_revision=0, audit=dict(status='PASS', source='fixture',
                turn_id=turn.turn_id, input_revision=0)))
            self.assertTrue(turn.try_seal())
            await sinks['on_done']('Saved despite index outage.')
        self.ns['memory_indexer'] = types.SimpleNamespace(add_message=Mock(side_effect=RuntimeError('index down')))
        _, _, task, _ = self.start_body_response(provider)
        await asyncio.wait_for(task, 2)
        self.assertEqual(len([e for e in self.events if e['type'] == 'message_segment']), 1)
        self.assertEqual(self.terminal()[0]['delivery'], 'delivered')
        self.assertEqual(self.terminal()[0]['segment_count'], 1)

    async def test_failed_segment_sink_is_not_counted_as_committed_delivery(self):
        async def provider(_name, transcript, **sinks):
            turn = sinks['steering']
            self.transcript.add = Mock(side_effect=OSError('sink down'))
            await sinks['on_segment']('Must not claim committed.', dict(turn_id=turn.turn_id,
                segment_index=1, input_revision=0, audit=dict(status='PASS', source='fixture',
                turn_id=turn.turn_id, input_revision=0)))
        _, _, task, _ = self.start_body_response(provider)
        result = await asyncio.gather(task, return_exceptions=True)
        self.assertIsInstance(result[0], OSError)
        self.assertFalse([e for e in self.events if e['type'] == 'message_segment'])
        self.assertEqual(self.terminal()[0]['segment_count'], 0)
        self.assertNotIn('Must not claim committed.', self.terminal()[0]['content'])

    async def test_explicit_stop_retains_delivered_segment_and_withholds_unfinished_step(self):
        delivered = asyncio.Event()
        async def provider(_name, transcript, **sinks):
            turn = sinks['steering']
            await sinks['on_segment']('Completed before Stop.', dict(turn_id=turn.turn_id,
                segment_index=1, input_revision=0, audit=dict(status='PASS', source='fixture',
                reason='Fixture evidence', turn_id=turn.turn_id, input_revision=0)))
            delivered.set()
            await asyncio.Event().wait()
        owner, _, task, _ = self.start_body_response(provider)
        await asyncio.wait_for(delivered.wait(), 2)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self.assertEqual([m['content'] for m in self.transcript.messages if m['author'] == 'Nova'],
                         ['Completed before Stop.'])
        self.assertEqual(self.terminal()[0]['delivery'], 'cancelled')
        self.assertEqual(self.terminal()[0]['content'], 'Completed before Stop.')
        self.assertEqual(self.terminal()[0]['segment_count'], 1)

    async def test_admission_precedes_echo_await_and_context_follows_acknowledgement(self):
        entered, attempt_consume = asyncio.Event(), asyncio.Event()
        echo_entered, echo_release = asyncio.Event(), asyncio.Event()
        observed = {}
        async def provider(_name, transcript, **sinks):
            observed['turn'] = sinks['steering']
            entered.set()
            await attempt_consume.wait()
            observed['batch'], _ = await sinks['steering'].consume()
            self.assertTrue(sinks['steering'].try_seal())
            await sinks['on_done']('Answer after echo acknowledgement.')
        owner, _, task, _ = self.start_body_response(provider)
        await asyncio.wait_for(entered.wait(), 2)
        normal_broadcast = self.ns['broadcast']
        async def paused_echo(event):
            if event.get('type') == 'user_message' and event.get('request_id') == 'during-echo':
                echo_entered.set()
                await echo_release.wait()
            await normal_broadcast(event)
        self.ns['broadcast'] = paused_echo
        sending = asyncio.create_task(self.send_inputs(owner, [('during-echo', 'input before echo completes')]))
        try:
            await asyncio.wait_for(echo_entered.wait(), 2)
            self.assertTrue(observed['turn'].pending)
            self.assertFalse(observed['turn'].try_seal(), 'Accepted input must block stale final delivery')
            attempt_consume.set()
            await asyncio.sleep(.01)
            self.assertFalse(task.done())
            self.assertFalse(any(e['type'] == 'message_context' for e in self.events))
        finally:
            echo_release.set()
            await asyncio.gather(sending, return_exceptions=True)
        await asyncio.wait_for(task, 2)
        relevant = [e['type'] for e in self.events if e['type'] in {'user_message', 'message_context', 'message_end'}]
        self.assertEqual(relevant, ['user_message', 'message_context', 'message_end'])
        self.assertEqual(self.terminal()[0]['request_ids'], ['initial', 'during-echo'])
        self.assertEqual(len(observed['batch']), 1)

    async def test_detached_socket_during_echo_does_not_strand_accepted_body_input(self):
        entered, attempt_consume, echo_entered = asyncio.Event(), asyncio.Event(), asyncio.Event()
        observed = {}
        async def provider(_name, transcript, **sinks):
            observed['turn'] = sinks['steering']
            entered.set()
            await attempt_consume.wait()
            observed['batch'], _ = await sinks['steering'].consume()
            self.assertTrue(sinks['steering'].try_seal())
            await sinks['on_done']('Accepted input survives a detached face.')
        owner, manager, task, _ = self.start_body_response(provider)
        await asyncio.wait_for(entered.wait(), 2)
        normal_broadcast = self.ns['broadcast']
        async def paused_echo(event):
            if event.get('type') == 'user_message' and event.get('request_id') == 'detached':
                echo_entered.set()
                await asyncio.Event().wait()
            await normal_broadcast(event)
        self.ns['broadcast'] = paused_echo
        sending = asyncio.create_task(self.send_inputs(owner, [('detached', 'accepted before socket detaches')]))
        try:
            await asyncio.wait_for(echo_entered.wait(), 2)
            self.assertTrue(observed['turn'].pending)
        finally:
            sending.cancel()
            await asyncio.gather(sending, return_exceptions=True)
        attempt_consume.set()
        await asyncio.wait_for(task, 1)
        self.assertEqual([entry['request_id'] for entry in observed['batch']], ['detached'])
        self.assertEqual(self.terminal()[0]['request_ids'], ['initial', 'detached'])
        self.assertIsNone(manager.get('session-fixture'))
        self.assertEqual(self.ns['_request_work'], {})

    async def test_three_followups_join_same_body_turn_once_after_pending_provider(self):
        entered, finish = asyncio.Event(), asyncio.Event()
        observed = {}
        async def provider(_name, transcript, **sinks):
            observed['snapshot'] = [m['content'] for m in transcript.messages]
            observed['turn'] = sinks['steering']
            entered.set()
            await finish.wait()
            observed['batch'], observed['revision'] = await sinks['steering'].consume()
            observed['again'], _ = await sinks['steering'].consume()
            self.assertTrue(sinks['steering'].try_seal())
            await sinks['on_audit']({'status': 'PASS', 'source': 'inline', 'reason': 'fixture'})
            await sinks['on_done']('One reply incorporating every follow-up.')
        owner, manager, task, generate = self.start_body_response(provider)
        await asyncio.wait_for(entered.wait(), 2)
        inputs = [('follow-1', 'first correction'), ('follow-2', 'second detail'), ('follow-3', 'third constraint')]
        await self.send_inputs(owner, inputs)
        self.assertFalse(task.done())
        self.assertEqual(task.cancelling(), 0)
        self.assertIs(manager.get('session-fixture'), observed['turn'])
        for rid, _ in inputs:
            self.assertIs(self.ns['_request_work'][(owner, rid)]['task'], task)
        self.assertEqual(self.ns['_cole_message_queue'], [])
        finish.set()
        await asyncio.wait_for(task, 2)
        self.assertEqual(observed['snapshot'], ['original request'])
        self.assertEqual([e['content'] for e in observed['batch']], ['[Cole is speaking to you]\n' + text for _, text in inputs])
        self.assertEqual(observed['again'], [])
        self.assertEqual(observed['revision'], 3)
        self.assertEqual(generate.await_count, 1)
        contexts = [e for e in self.events if e['type'] == 'message_context']
        self.assertEqual(len(contexts), 1)
        for event in contexts + self.terminal():
            self.assertEqual(event['request_ids'], ['initial', 'follow-1', 'follow-2', 'follow-3'])
            self.assertEqual(event['reply_to_ids'], ['stored-0', 'stored-1', 'stored-2', 'stored-3'])
            self.assertEqual(event['input_revision'], 3)
            self.assertEqual(event['id'], 'shared-reply')
            self.assertEqual(event['run_id'], observed['turn'].turn_id)
        self.assertEqual(self.terminal()[0]['delivery'], 'delivered')
        self.assertEqual(self.terminal()[0]['audit']['status'], 'PASS')
        self.assertEqual(self.request_ends(), [])
        self.assertEqual(self.ns['_request_work'], {})
        self.assertEqual(self.ns['_turn_transports'], {})
        self.assertIsNone(manager.get('session-fixture'))

    async def test_followups_during_context_preparation_are_adopted_without_snapshot_duplication(self):
        entered, release = threading.Event(), threading.Event()
        def update(_):
            entered.set()
            if not release.wait(3):
                raise TimeoutError('fixture context preparation was not released')
        self.ns['workspace'].update_for_message = update
        observed = {}
        async def provider(_name, transcript, **sinks):
            observed['snapshot'] = [m['content'] for m in transcript.messages]
            observed['batch'], _ = await sinks['steering'].consume()
            self.assertFalse(sinks['steering'].pending)
            self.assertTrue(sinks['steering'].try_seal())
            await sinks['on_done']('Reply after prepared context.')
        owner, manager, task, _ = self.start_body_response(provider)
        try:
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            self.assertIsNone(manager.get('session-fixture'))
            await self.send_inputs(owner, [('during-1', 'arrived before inference'), ('during-2', 'also preserve this')])
            self.assertEqual(len(self.ns['_cole_message_queue']), 2)
        finally:
            release.set()
        await asyncio.wait_for(task, 2)
        self.assertEqual(observed['snapshot'], ['original request'])
        self.assertEqual([e['content'] for e in observed['batch']],
                         ['[Cole is speaking to you]\narrived before inference', '[Cole is speaking to you]\nalso preserve this'])
        self.assertEqual(self.terminal()[0]['request_ids'], ['initial', 'during-1', 'during-2'])
        self.assertEqual(self.ns['_cole_message_queue'], [])
        self.assertEqual(self.ns['_request_work'], {})

    async def test_input_after_body_seal_queues_next_turn_without_changing_delivered_aliases(self):
        sealed, release = asyncio.Event(), asyncio.Event()
        async def provider(_name, transcript, **sinks):
            self.assertTrue(sinks['steering'].try_seal())
            sealed.set()
            await release.wait()
            await sinks['on_done']('First sealed answer.')
        owner, _, task, _ = self.start_body_response(provider)
        await asyncio.wait_for(sealed.wait(), 2)
        await self.send_inputs(owner, [('late', 'follow-up after admission closed')])
        self.assertEqual(len(self.ns['_cole_message_queue']), 1)
        next_work = self.ns['_cole_message_queue'][0]
        self.assertNotIn('task', next_work)
        release.set()
        await asyncio.wait_for(task, 2)
        self.assertEqual(self.terminal()[0]['request_ids'], ['initial'])
        self.assertIn((owner, 'late'), self.ns['_request_work'])
        pending = self.hold_scheduled_responses()
        self.ns['is_processing'] = False
        await self.ns['_drain_cole_queue']()
        self.assertEqual(len(pending), 1)
        await pending.pop(0)
        self.assertEqual(self.ns['run_ai_response'].await_args.kwargs['request_id'], 'late')
        self.assertIs(self.ns['run_ai_response'].await_args.kwargs['request_work'], next_work)
        self.assertEqual(self.request_ends(), [])

    async def test_different_conversation_does_not_steer_or_receive_active_reply(self):
        entered, release = asyncio.Event(), asyncio.Event()
        observed = {}
        async def provider(_name, transcript, **sinks):
            observed['turn'] = sinks['steering']
            entered.set()
            await release.wait()
            self.assertEqual(await sinks['steering'].consume(), ([], 0))
            self.assertTrue(sinks['steering'].try_seal())
            await sinks['on_done']('Reply belonging to original conversation.')
        owner, _, task, _ = self.start_body_response(provider)
        await asyncio.wait_for(entered.wait(), 2)
        other = Transcript()
        other.add('Cole', 'earlier unrelated conversation')
        other.add('Nova', 'Reply belonging to original conversation.')
        self.session.active = other
        self.session.active_id = 'other-conversation'
        await self.send_inputs(owner, [('other-request', 'different conversation request')])
        self.assertFalse(observed['turn'].pending)
        other.add('Nova', 'Reply belonging to original conversation.')
        self.assertEqual(len(self.ns['_cole_message_queue']), 1)
        self.assertEqual(self.ns['_cole_message_queue'][0]['conversation_id'], 'other-conversation')
        release.set()
        await asyncio.wait_for(task, 2)
        self.assertEqual(self.terminal()[0]['request_ids'], ['initial'])
        self.assertEqual([m['author'] for m in other.messages], ['Cole', 'Nova', 'Cole', 'Nova'])
        self.assertEqual(self.transcript.messages[-1]['content'], 'Reply belonging to original conversation.')

    async def test_stop_accepted_followup_cancels_owned_shared_turn_and_closes_all_aliases(self):
        entered = asyncio.Event()
        async def provider(_name, transcript, **sinks):
            entered.set()
            await asyncio.Event().wait()
        owner, manager, task, _ = self.start_body_response(provider)
        await asyncio.wait_for(entered.wait(), 2)
        await self.send_inputs(owner, [('stop-followup', 'joined pending input')])
        other_task = asyncio.create_task(asyncio.Event().wait())
        self.addCleanup(other_task.cancel)
        other_owner = Socket([])
        other_work = {'owner': other_owner, 'request_id': 'unrelated', 'task': other_task, 'started': True}
        self.ns['_request_work'][(other_owner, 'unrelated')] = other_work
        await self.ns['_stop_request'](owner, 'stop-followup')
        self.assertTrue(task.cancelled())
        self.assertFalse(other_task.done())
        self.assertFalse(self.ns['_stop_requested'].is_set())
        self.assertEqual(owner.sent[-1], {'type': 'stopped', 'request_id': 'stop-followup', 'matched': True})
        self.assertEqual([(e['request_ids'], e['delivery']) for e in self.terminal()], [(['initial'], 'cancelled')])
        self.assertEqual([(e['request_id'], e['delivery']) for e in self.request_ends()],
                         [('stop-followup', 'cancelled')])
        self.assertEqual(list(self.ns['_request_work']), [(other_owner, 'unrelated')])
        self.assertEqual(self.ns['_turn_transports'], {})
        self.assertIsNone(manager.get('session-fixture'))

    async def test_scoped_stop_removes_only_own_queued_request(self):
        owner, other = Socket([]), Socket([])
        own = self.queued_request('voice', 'voice-old'); own['owner'] = owner
        adjacent = self.queued_request('typed', 'typed-new'); adjacent['owner'] = other
        self.ns['_request_work'][(owner, 'voice-old')] = own
        self.ns['_request_work'][(other, 'typed-new')] = adjacent
        self.ns['is_processing'] = True
        await self.ns['_stop_request'](owner, 'voice-old')
        self.assertEqual(self.ns['_cole_message_queue'], [adjacent])
        self.assertTrue(self.ns['is_processing'])
        self.assertFalse(self.ns['_stop_requested'].is_set())
        self.assertEqual(self.request_ends()[0]['delivery'], 'cancelled')
        self.assertEqual(owner.sent[-1], {'type': 'stopped', 'request_id': 'voice-old', 'matched': True})
        self.assertIn((other, 'typed-new'), self.ns['_request_work'])

    async def test_scoped_stop_cancels_own_active_task_without_global_stop(self):
        owner = Socket([])
        entered = asyncio.Event()
        async def work():
            entered.set()
            await asyncio.Event().wait()
        task = asyncio.create_task(work())
        other = asyncio.create_task(asyncio.Event().wait())
        self.addCleanup(other.cancel)
        await entered.wait()
        entry = {'owner': owner, 'request_id': 'active', 'started': True, 'task': task}
        self.ns['_request_work'][(owner, 'active')] = entry
        await self.ns['_stop_request'](owner, 'active')
        self.assertTrue(task.cancelled())
        self.assertFalse(other.done())
        self.assertFalse(self.ns['_stop_requested'].is_set())
        self.assertEqual(owner.sent[-1]['matched'], True)
        self.assertEqual(self.request_ends(), [])

    async def test_scoped_stop_pending_ack_waits_for_the_owned_task_to_finish(self):
        owner = Socket([])
        entered = asyncio.Event()
        async def work():
            entered.set(); await asyncio.Event().wait()
        task = asyncio.create_task(work())
        await entered.wait()
        self.ns['_request_work'][(owner, 'pending')] = {
            'owner': owner, 'request_id': 'pending', 'task': task, 'started': True}
        self.ns['asyncio'] = types.SimpleNamespace(wait=AsyncMock(return_value=(set(), {task})),
            ensure_future=asyncio.ensure_future, CancelledError=asyncio.CancelledError)
        await self.ns['_stop_request'](owner, 'pending')
        self.assertEqual(owner.sent, [{'type': 'stop_pending', 'request_id': 'pending'}])
        await asyncio.sleep(0); await asyncio.sleep(0); await asyncio.sleep(0)
        self.assertTrue(task.cancelled())
        self.assertEqual(owner.sent[-1], {'type': 'stopped', 'request_id': 'pending', 'matched': True})

    async def test_stale_other_socket_and_invalid_scoped_stop_cannot_cancel_new_work(self):
        owner, other = Socket([]), Socket([])
        task = asyncio.create_task(asyncio.Event().wait())
        self.addCleanup(task.cancel)
        self.ns['_request_work'][(owner, 'new')] = {'owner': owner, 'request_id': 'new', 'task': task, 'started': True}
        for socket, request in [(owner, 'old'), (other, 'new'), (owner, None), (owner, ['new'])]:
            await self.ns['_stop_request'](socket, request)
            self.assertFalse(socket.sent[-1]['matched'])
            self.assertFalse(task.done())
        self.assertFalse(self.ns['_stop_requested'].is_set())

    async def test_scoped_cancel_before_task_starts_releases_only_its_reservation(self):
        owner = Socket([])
        ran = []
        async def work(): ran.append(True)
        task = asyncio.create_task(work())
        entry = {'owner': owner, 'request_id': 'before-start', 'task': task,
                 'msg': {'id': 'input'}, 'register': 'voice'}
        self.ns['_request_work'][(owner, 'before-start')] = entry
        self.ns['is_processing'] = True
        self.ns['_drain_cole_queue'] = AsyncMock()
        await self.ns['_stop_request'](owner, 'before-start')
        self.assertFalse(ran)
        self.assertTrue(task.cancelled())
        self.assertFalse(self.ns['is_processing'])
        self.assertEqual(self.request_ends()[0]['request_id'], 'before-start')
        self.ns['_drain_cole_queue'].assert_awaited_once()
        self.assertNotIn((owner, 'before-start'), self.ns['_request_work'])

    async def test_scoped_cancel_during_drain_status_cannot_launch_generation(self):
        owner = Socket([])
        entry = self.queued_request('voice', 'selected'); entry['owner'] = owner
        self.ns['_request_work'][(owner, 'selected')] = entry
        selected = asyncio.Event(); release = asyncio.Event()
        async def status():
            selected.set(); await release.wait(); return {'Nova': True}
        self.ns['get_status'] = status
        self.ns['_run_response_queue'] = AsyncMock()
        drain = asyncio.create_task(self.ns['_drain_cole_queue']())
        await selected.wait()
        await self.ns['_stop_request'](owner, 'selected')
        release.set(); await drain
        self.ns['_run_response_queue'].assert_not_awaited()
        self.assertFalse(self.ns['is_processing'])
        self.assertEqual(len(self.request_ends()), 1)
        self.assertEqual(self.request_ends()[0]['delivery'], 'cancelled')

    async def test_scoped_websocket_stop_never_falls_back_to_global(self):
        self.ns['_stop_request'] = AsyncMock()
        self.ns['stop_endpoint'] = AsyncMock()
        ws = Socket([{'type': 'stop', 'request_id': None}, {'type': 'stop', 'request_id': 'mine'}])
        await self.ns['websocket_endpoint'](ws)
        self.assertEqual(self.ns['_stop_request'].await_count, 2)
        self.ns['stop_endpoint'].assert_not_awaited()
        ws = Socket([{'type': 'stop'}])
        await self.ns['websocket_endpoint'](ws)
        self.ns['stop_endpoint'].assert_awaited_once()

    async def test_context_phase_timings_preserve_request_identity(self):
        async def provider(*args, **sinks):
            await sinks['on_done']('Hello.')
        await self.response(provider)
        calls = self.phase_receipt.call_args_list
        self.assertEqual([c.args[0] for c in calls],
                         ['context_update', 'context_memory', 'context_workspace'])
        for call in calls:
            self.assertEqual(call.kwargs, {'request_id': 'request-1', 'reply_to': 'human-1', 'register': 'voice'})
            self.assertIsInstance(call.args[1], float)

    def terminal(self):
        return [event for event in self.events if event['type'] == 'message_end']

    async def response(self, provider, **kwargs):
        generate = AsyncMock(side_effect=provider)
        self.ns['_rt'] = types.SimpleNamespace(model_client=types.SimpleNamespace(generate=generate))
        result = await self.ns['run_ai_response']('Nova', object(), 'reply-1', 'human request',
                                                 register='voice', reply_to='human-1',
                                                 request_id='request-1', **kwargs)
        return result, generate

    async def test_start_tokens_end_keep_request_message_and_operation_identity(self):
        async def provider(*args, **sinks):
            self.assertFalse(sinks['autonomous'], 'Global autonomy must not change a human chat request')
            self.assertEqual(sinks['register'], 'voice')
            await sinks['on_token']('Hello ')
            await sinks['on_token']('Cole')
            await sinks['on_audit']({'status': 'PASS', 'reason': 'Fixture verified', 'source': 'inline'})
            await sinks['on_done']('Hello Cole')
        token = self.operation.set(types.SimpleNamespace(id='operation-fixture'))
        try:
            result, _ = await self.response(provider)
        finally:
            self.operation.reset(token)
        stream = [e for e in self.events if e['type'] in {'message_start', 'token', 'message_end'}]
        self.assertEqual([e['type'] for e in stream], ['message_start', 'token', 'token', 'message_end'])
        for event in stream:
            self.assertEqual({k: event[k] for k in ('id', 'run_id', 'reply_to', 'request_id', 'register')},
                             dict(id='reply-1', run_id='operation-fixture', reply_to='human-1',
                                  request_id='request-1', register='voice'))
        self.assertEqual(result, 'Hello Cole')
        self.assertEqual(self.terminal()[0]['delivery'], 'delivered')
        self.assertEqual(self.terminal()[0]['audit']['status'], 'PASS')
        self.assertEqual(self.transcript.messages[-1]['content'], result)

    async def test_missing_operation_still_has_one_nonempty_run_id(self):
        async def provider(*args, **sinks):
            await sinks['on_token']('Final')
            await sinks['on_done']('Final')
        await self.response(provider)
        stream = [e for e in self.events if e['type'] in {'message_start', 'token', 'message_end'}]
        self.assertTrue(stream[0]['run_id'])
        self.assertEqual(len({e['run_id'] for e in stream}), 1)
        self.assertEqual(self.terminal()[0]['audit']['status'], 'NOT_RUN')

    async def test_error_and_identical_error_dedup_each_close_without_delivery(self):
        async def provider(*args, **sinks):
            await sinks['on_audit']({'status': 'PASS'})
            await sinks['on_error'](RuntimeError('fixture provider offline'))
        await self.response(provider)
        await self.response(provider)
        ends = self.terminal()
        self.assertEqual(len(ends), 2)
        self.assertTrue(ends[0]['content'])
        self.assertEqual(ends[1]['content'], '')
        self.assertTrue(all(e['delivery'] == 'error' and e['audit']['status'] == 'NOT_RUN' for e in ends))
        self.assertEqual(len([e for e in self.events if e['type'] == 'error']), 1)
        self.assertEqual(self.transcript.messages, [])

    async def test_callback_error_then_raise_emits_only_one_terminal(self):
        async def provider(*args, **sinks):
            error = RuntimeError('fixture callback and raise')
            await sinks['on_error'](error)
            raise error
        with self.assertRaisesRegex(RuntimeError, 'fixture callback and raise'):
            await self.response(provider)
        self.assertEqual(len(self.terminal()), 1)
        self.assertEqual(self.terminal()[0]['delivery'], 'error')

    async def test_user_stop_closes_stream_as_cancelled_and_does_not_commit(self):
        async def provider(*args, **sinks):
            await sinks['on_audit']({'status': 'PASS'})
            self.ns['_stop_requested'].set()
            await sinks['on_token']('must not stream')
        with self.assertRaises(asyncio.CancelledError):
            await self.response(provider)
        self.assertEqual(len(self.terminal()), 1)
        self.assertEqual(self.terminal()[0]['delivery'], 'cancelled')
        self.assertEqual(self.terminal()[0]['audit']['status'], 'NOT_RUN')
        self.assertEqual(self.transcript.messages, [])
        self.assertFalse(any(e['type'] == 'token' for e in self.events))

    async def test_stop_before_final_without_further_tokens_never_commits(self):
        async def provider(*args, **sinks):
            await sinks['on_audit']({'status': 'PASS'})
            self.ns['_stop_requested'].set()
            await sinks['on_done']('late final after Stop')
        with self.assertRaises(asyncio.CancelledError):
            await self.response(provider)
        self.assertEqual(self.transcript.messages, [])
        self.assertEqual(len(self.terminal()), 1)
        self.assertEqual(self.terminal()[0]['delivery'], 'cancelled')

    async def test_empty_and_duplicate_responses_are_not_delivered_or_approved(self):
        for full, expected in [('', 'empty'), ('already spoken', 'suppressed')]:
            with self.subTest(outcome=expected):
                self.events.clear()
                self.transcript.messages.clear()
                if full:
                    self.transcript.add('Nova', full)
                original_count = len(self.transcript.messages)
                async def provider(*args, **sinks):
                    await sinks['on_audit']({'status': 'PASS'})
                    await sinks['on_done'](full)
                await self.response(provider)
                self.assertEqual(len(self.terminal()), 1)
                self.assertEqual(self.terminal()[0]['delivery'], expected)
                self.assertEqual(self.terminal()[0]['content'], '')
                self.assertEqual(self.terminal()[0]['audit']['status'], 'NOT_RUN')
                self.assertEqual(len(self.transcript.messages), original_count)

    async def test_delivered_unapproved_answer_retains_honest_audit_disposition(self):
        async def provider(*args, **sinks):
            await sinks['on_audit']({'status': 'INCOMPLETE', 'reason': 'evidence unavailable'})
            await sinks['on_done']('I could not verify the result.')
        await self.response(provider)
        end = self.terminal()[0]
        self.assertEqual(end['delivery'], 'delivered')
        self.assertEqual(end['audit']['status'], 'INCOMPLETE')

    async def test_silent_tick_only_promotes_explicit_unsolicited_content(self):
        heartbeat = Transcript()
        async def provider(*args, **sinks):
            self.assertIs(args[1], heartbeat)
            self.assertTrue(sinks['autonomous'])
            await sinks['on_token']('private tick')
            await sinks['on_audit']({'status': 'PASS', 'source': 'inline'})
            await sinks['on_done']('Work log. FOR COLE: A fresh update.')
        await self.response(provider, hb_ctx=heartbeat, cole_pending=False)
        self.assertFalse(any(e['type'] in {'message_start', 'token'} for e in self.events))
        self.assertTrue(any(e['type'] == 'autonomous_start' for e in self.events))
        end = self.terminal()[0]
        self.assertEqual(end['id'], 'reply-1_cole')
        self.assertEqual(end['delivery'], 'unsolicited')
        self.assertEqual(end['content'], 'A fresh update.')
        self.assertIsNone(end['reply_to'])
        self.assertIsNone(end['request_id'])
        self.assertEqual(end['audit']['status'], 'NOT_RUN')
        self.assertEqual(self.transcript.messages[-1]['content'], 'A fresh update.')

    async def test_quiet_silent_tick_does_not_emit_a_spoken_terminal(self):
        async def provider(*args, **sinks):
            await sinks['on_done']('Background work only.')
        await self.response(provider, hb_ctx=Transcript(), cole_pending=False)
        self.assertEqual(self.terminal(), [])
        self.assertEqual(self.transcript.messages, [])

    async def test_websocket_first_request_closure_survives_busy_second_request_and_drain(self):
        pending = []
        scheduled = []
        def schedule(coroutine):
            pending.append(coroutine)
            scheduled.append(coroutine)
            return coroutine
        self.addCleanup(lambda: [coroutine.close() for coroutine in scheduled])
        self.ns['asyncio'] = types.SimpleNamespace(ensure_future=schedule, CancelledError=asyncio.CancelledError)
        run = AsyncMock(return_value='')
        self.ns['run_ai_response'] = run
        first_image = [{'dataUrl': 'fixture-image-a', 'name': 'a'}]
        second_image = [{'dataUrl': 'fixture-image-b', 'name': 'b'}]
        ws = Socket([dict(type='message', content='first', register='voice', request_id='voice-001', images=first_image),
                     dict(type='message', content='second', register='voice_fast', request_id='voice-002', images=second_image)])
        await self.ns['websocket_endpoint'](ws)
        self.assertEqual(len(pending), 1)
        self.assertEqual(len(self.ns['_cole_message_queue']), 1)
        queued = self.ns['_cole_message_queue'][0]
        self.assertEqual((queued['register'], queued['request_id']), ('voice_fast', 'voice-002'))
        queued_notice = next(event for event in ws.sent if event['type'] == 'queued')
        self.assertEqual({k: queued_notice[k] for k in ('request_id', 'reply_to', 'register')},
                         dict(request_id='voice-002', reply_to='stored-1', register='voice_fast'))
        while pending:
            await pending.pop(0)
        self.assertEqual(run.await_count, 2)
        first, second = run.await_args_list
        self.assertEqual(first.args[3], 'first')
        self.assertEqual(first.kwargs, dict(images=first_image, source='ws', register='voice',
                                            reply_to='stored-0', request_id='voice-001', request_work=first.kwargs['request_work']))
        self.assertIs(first.kwargs['request_work']['owner'], ws)
        self.assertEqual(first.kwargs['request_work']['conversation_id'], 'session-fixture')
        self.assertEqual(second.args[3], 'second')
        self.assertEqual(second.kwargs, dict(images=second_image, source='drain', register='voice_fast',
                                             reply_to='stored-1', request_id='voice-002', request_work=second.kwargs['request_work']))
        self.assertIs(second.kwargs['request_work'], queued)
        echoes = [e for e in self.events if e['type'] == 'user_message']
        self.assertEqual([(e['request_id'], e['register']) for e in echoes],
                         [('voice-001', 'voice'), ('voice-002', 'voice_fast')])
        self.assertFalse(self.ns['is_processing'])
        self.assertEqual(self.ns['_cole_message_queue'], [])

    async def test_malformed_websocket_voice_metadata_falls_back_before_queueing(self):
        self.ns['is_processing'] = True
        ws = Socket([dict(type='message', content='queued', register={'voice': True}, request_id='bad id with spaces')])
        await self.ns['websocket_endpoint'](ws)
        queued = self.ns['_cole_message_queue'][0]
        self.assertEqual(queued['register'], 'text')
        self.assertIsNone(queued['request_id'])
        echo = next(e for e in self.events if e['type'] == 'user_message')
        self.assertEqual(echo['register'], 'text')
        self.assertIsNone(echo['request_id'])

    def queued_request(self, content, request_id, register='voice'):
        message = self.transcript.add('Cole', content)
        queued = dict(content=content, request_id=request_id, register=register, msg=message,
                      directed_at=[], images=[])
        self.ns['_cole_message_queue'].append(queued)
        return queued

    def hold_scheduled_responses(self):
        pending, scheduled = [], []
        def schedule(coroutine):
            pending.append(coroutine)
            scheduled.append(coroutine)
            return coroutine
        self.addCleanup(lambda: [coroutine.close() for coroutine in scheduled])
        self.ns['asyncio'] = types.SimpleNamespace(ensure_future=schedule, CancelledError=asyncio.CancelledError)
        self.ns['run_ai_response'] = AsyncMock(return_value='')
        return pending

    def request_ends(self):
        return [event for event in self.events if event['type'] == 'request_end']

    async def test_fifo_queue_preserves_every_request_without_superseding(self):
        pending = self.hold_scheduled_responses()
        entries = [self.queued_request(content, request, register) for content, request, register in
                   [('first', 'old-1', 'voice'), ('middle', 'old-2', 'voice_fast'), ('newest', 'new-3', 'text')]]
        await self.ns['_drain_cole_queue']()
        self.assertTrue(self.ns['is_processing'])
        self.assertEqual(len(pending), 1)
        while pending:
            await pending.pop(0)
        calls = self.ns['run_ai_response'].await_args_list
        self.assertEqual([call.kwargs['request_id'] for call in calls], ['old-1', 'old-2', 'new-3'])
        for call, entry in zip(calls, entries):
            self.assertIs(call.kwargs['request_work'], entry)
        self.assertEqual(self.request_ends(), [])
        self.assertFalse(self.ns['is_processing'])
        self.assertEqual(self.ns['_cole_message_queue'], [])

    async def test_watermark_and_prior_reply_do_not_silently_discard_queued_input(self):
        pending = self.hold_scheduled_responses()
        request = self.queued_request('still requires admission', 'answered-1')
        self.transcript.add('Nova', 'Prior run answered an earlier input.')
        self.ns['_inflight_upto'] = 999
        await self.ns['_drain_cole_queue']()
        self.assertEqual(len(pending), 1)
        await pending.pop(0)
        self.assertEqual(self.request_ends(), [])
        self.assertEqual(self.ns['run_ai_response'].await_args.kwargs['request_id'], 'answered-1')
        self.assertIs(self.ns['run_ai_response'].await_args.kwargs['request_work'], request)
        self.assertFalse(self.ns['is_processing'])

    async def test_no_eligible_provider_closes_selected_request_and_releases_busy(self):
        pending = self.hold_scheduled_responses()
        self.queued_request('cannot answer', 'unavailable-1')
        self.ns['_mute_states']['Nova'] = True
        await self.ns['_drain_cole_queue']()
        self.assertEqual([(e['request_id'], e['delivery']) for e in self.request_ends()], [('unavailable-1', 'unavailable')])
        self.assertFalse(self.ns['is_processing'])
        self.assertEqual(pending, [])
        self.assertEqual(self.ns['_cole_message_queue'], [])

    async def test_status_failure_closes_request_without_stranding_busy_state(self):
        pending = self.hold_scheduled_responses()
        self.queued_request('provider status failed', 'probe-failed')
        self.ns['get_status'] = AsyncMock(side_effect=RuntimeError('fixture provider unavailable'))
        await self.ns['_drain_cole_queue']()
        self.assertEqual(self.request_ends()[0]['delivery'], 'unavailable')
        self.assertFalse(self.ns['is_processing'])
        self.assertEqual(pending, [])

    async def test_broadcast_await_cannot_admit_duplicate_drains_or_immediate_response(self):
        pending = self.hold_scheduled_responses()
        self.queued_request('older', 'old')
        self.queued_request('selected', 'selected')
        reached, release = asyncio.Event(), asyncio.Event()
        normal_broadcast = self.ns['broadcast']
        async def paused_broadcast(event):
            await normal_broadcast(event)
            if event.get('type') == 'processing_start' and not reached.is_set():
                reached.set()
                await release.wait()
        self.ns['broadcast'] = paused_broadcast
        drain = asyncio.create_task(self.ns['_drain_cole_queue']())
        try:
            await asyncio.wait_for(reached.wait(), 1)
            self.assertTrue(self.ns['is_processing'])
            await self.ns['_drain_cole_queue']()
            self.assertEqual(pending, [])
            await self.ns['websocket_endpoint'](Socket([dict(type='message', content='arrived during broadcast',
                                                           register='voice_fast', request_id='later')]))
            self.assertEqual(len(self.ns['_cole_message_queue']), 2)
            self.assertEqual(pending, [])
            release.set()
            await drain
            self.assertEqual(len(pending), 1)
            while pending:
                await pending.pop(0)
        finally:
            release.set()
            if not drain.done():
                drain.cancel()
                await asyncio.gather(drain, return_exceptions=True)
        calls = self.ns['run_ai_response'].await_args_list
        self.assertEqual([call.kwargs['request_id'] for call in calls], ['old', 'selected', 'later'])
        self.assertEqual(len([e for e in self.events if e['type'] == 'processing_start']), 3)
        self.assertEqual(self.request_ends(), [])
        self.assertFalse(self.ns['is_processing'])

    async def test_request_arriving_during_unavailable_notice_gets_next_drain(self):
        pending = self.hold_scheduled_responses()
        self.queued_request('offline request', 'offline')
        self.ns['get_status'] = AsyncMock(side_effect=[{'Nova': False}, {'Nova': True}])
        normal_broadcast = self.ns['broadcast']
        async def arriving_broadcast(event):
            await normal_broadcast(event)
            if event.get('delivery') == 'unavailable':
                self.assertTrue(self.ns['is_processing'])
                self.queued_request('next request', 'next')
        self.ns['broadcast'] = arriving_broadcast
        await self.ns['_drain_cole_queue']()
        self.assertEqual(len(pending), 1)
        await pending.pop(0)
        self.assertEqual(self.ns['run_ai_response'].await_args.kwargs['request_id'], 'next')
        self.assertEqual([(e['request_id'], e['delivery']) for e in self.request_ends()], [('offline', 'unavailable')])
        self.assertFalse(self.ns['is_processing'])

    async def test_cancelled_status_reservation_releases_busy_and_closes_selected_request(self):
        pending = self.hold_scheduled_responses()
        self.queued_request('cancelled reservation', 'cancelled-reservation')
        self.ns['get_status'] = AsyncMock(side_effect=asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            await self.ns['_drain_cole_queue']()
        self.assertFalse(self.ns['is_processing'])
        self.assertEqual(pending, [])
        self.assertEqual([(e['request_id'], e['delivery']) for e in self.request_ends()], [('cancelled-reservation', 'cancelled')])

    async def test_already_stopped_queue_cancels_every_entry_without_clearing_stop(self):
        pending = self.hold_scheduled_responses()
        self.queued_request('older', 'old-stopped')
        self.queued_request('newest', 'new-stopped')
        self.ns['_stop_requested'].set()
        await self.ns['_drain_cole_queue']()
        self.assertEqual([(e['request_id'], e['delivery']) for e in self.request_ends()],
                         [('old-stopped', 'cancelled'), ('new-stopped', 'cancelled')])
        self.assertEqual(pending, [])
        self.ns['get_status'].assert_not_awaited()
        self.assertTrue(self.ns['_stop_requested'].is_set())
        self.assertFalse(self.ns['is_processing'])

    async def test_stop_during_status_wait_does_not_schedule_generation(self):
        pending = self.hold_scheduled_responses()
        self.queued_request('status waiting', 'status-stopped')
        async def status():
            self.ns['_stop_requested'].set()
            await asyncio.sleep(0)
            return {'Nova': True}
        self.ns['get_status'] = status
        await self.ns['_drain_cole_queue']()
        self.assertEqual(pending, [])
        self.assertEqual(self.request_ends()[0]['delivery'], 'cancelled')
        self.assertTrue(self.ns['_stop_requested'].is_set())
        self.assertFalse(any(e['type'] == 'processing_start' for e in self.events))

    async def test_stop_during_completion_broadcast_cancels_remaining_unstarted_requests(self):
        pending = self.hold_scheduled_responses()
        self.queued_request('first', 'old')
        self.queued_request('next', 'selected')
        normal_broadcast = self.ns['broadcast']
        async def stop_on_completion(event):
            await normal_broadcast(event)
            if event.get('type') == 'processing_end':
                self.ns['_stop_requested'].set()
                await asyncio.sleep(0)
        self.ns['broadcast'] = stop_on_completion
        await self.ns['_drain_cole_queue']()
        await pending.pop(0)
        self.assertEqual(pending, [])
        self.assertEqual(self.ns['run_ai_response'].await_count, 1)
        self.assertEqual(self.ns['run_ai_response'].await_args.kwargs['request_id'], 'old')
        self.assertEqual([(e['request_id'], e['delivery']) for e in self.request_ends()], [('selected', 'cancelled')])
        self.assertTrue(self.ns['_stop_requested'].is_set())

    async def test_stop_during_processing_start_broadcast_balances_state_without_generation(self):
        pending = self.hold_scheduled_responses()
        self.queued_request('start notice waiting', 'start-stopped')
        normal_broadcast = self.ns['broadcast']
        async def stop_on_start(event):
            await normal_broadcast(event)
            if event['type'] == 'processing_start':
                self.ns['_stop_requested'].set()
                await asyncio.sleep(0)
        self.ns['broadcast'] = stop_on_start
        await self.ns['_drain_cole_queue']()
        self.assertEqual(pending, [])
        self.assertEqual(self.request_ends()[0]['delivery'], 'cancelled')
        self.assertEqual([e['type'] for e in self.events if e['type'].startswith('processing_')],
                         ['processing_start', 'processing_end'])
        self.assertFalse(self.ns['is_processing'])
        self.assertTrue(self.ns['_stop_requested'].is_set())

    async def test_stop_after_scheduling_before_execution_cancels_request_without_provider(self):
        pending = self.hold_scheduled_responses()
        self.queued_request('scheduled', 'scheduled-stopped')
        await self.ns['_drain_cole_queue']()
        self.assertEqual(len(pending), 1)
        self.ns['_stop_requested'].set()
        await pending.pop(0)
        self.ns['run_ai_response'].assert_not_awaited()
        self.assertEqual(self.request_ends()[0]['delivery'], 'cancelled')
        self.assertFalse(self.ns['is_processing'])
        self.assertTrue(self.ns['_stop_requested'].is_set())

    async def test_cancel_during_selected_terminal_broadcast_never_emits_conflicting_end(self):
        for disposition in ('unavailable', 'cancelled'):
            with self.subTest(disposition=disposition):
                self.events.clear()
                self.transcript.messages.clear()
                self.ns['_stop_requested'].clear()
                self.ns['_inflight_upto'] = 0
                self.queued_request('selected', 'partial-terminal')
                if disposition == 'cancelled':
                    self.ns['_stop_requested'].set()
                self.ns['get_status'] = AsyncMock(return_value={'Nova': False})
                reached = asyncio.Event()
                first = True
                async def partial_broadcast(event):
                    nonlocal first
                    self.events.append(event)
                    if event['type'] == 'request_end' and first:
                        first = False
                        reached.set()
                        await asyncio.Event().wait()
                self.ns['broadcast'] = partial_broadcast
                task = asyncio.create_task(self.ns['_drain_cole_queue']())
                try:
                    await asyncio.wait_for(reached.wait(), 1)
                    task.cancel()
                    result = await asyncio.gather(task, return_exceptions=True)
                    self.assertIsInstance(result[0], asyncio.CancelledError)
                finally:
                    if not task.done():
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
                self.assertEqual([(e['request_id'], e['delivery']) for e in self.request_ends()],
                                 [('partial-terminal', disposition)])
                self.assertFalse(self.ns['is_processing'])

    async def test_discard_notice_normalizes_register_and_omits_uncorrelated_requests(self):
        await self.ns['_end_queued_request']({'request_id': 'valid', 'register': ['voice'], 'msg': {'id': 'inbound'}}, 'unavailable')
        for invalid in (None, '', 'bad id', {}, 'x' * 129):
            await self.ns['_end_queued_request']({'request_id': invalid}, 'superseded')
        self.assertEqual(self.request_ends(), [dict(type='request_end', request_id='valid',
                         reply_to='inbound', register='text', delivery='unavailable')])

    async def test_transition_leaves_busy_queue_intact_without_starting_generation(self):
        self.ns['_nova_lifecycle'].pending = True
        message = {'content': 'pending request', 'register': 'voice', 'request_id': 'pending-id'}
        self.ns['_cole_message_queue'].append(message)
        await self.ns['_drain_cole_queue']()
        self.assertEqual(self.ns['_cole_message_queue'], [message])
        self.assertEqual(self.events, [])


    async def test_unavailable_immediate_provider_closes_request(self):
        self.ns['get_status'] = AsyncMock(return_value={'Nova': False})
        ws = Socket([dict(type='message', content='hello', register='voice', request_id='no-provider')])
        await self.ns['websocket_endpoint'](ws)
        echo = next(e for e in self.events if e['type'] == 'user_message')
        self.assertEqual(self.request_ends(), [dict(type='request_end', request_id='no-provider',
                         reply_to=echo['id'], register='voice', delivery='unavailable')])
        self.assertEqual(self.ns['active_tasks'], [])

    async def test_chat_only_and_transition_reject_without_storing_input(self):
        for chat_only in (True, False):
            with self.subTest(chat_only=chat_only):
                self.events.clear()
                self.ns['CHAT_ONLY'] = chat_only
                self.ns['_nova_lifecycle'].pending = not chat_only
                self.ns['_CHAT_ONLY_MESSAGE'] = 'Nova is off.'
                ws = Socket([dict(type='message', content='hello', register='voice', request_id='off')])
                await self.ns['websocket_endpoint'](ws)
                self.assertEqual(self.request_ends(), [dict(type='request_end', request_id='off',
                                 reply_to=None, register='voice', delivery='unavailable')])
                self.assertEqual(self.transcript.messages, [])
                self.assertEqual(self.ns['active_tasks'], [])

    async def test_transition_before_generation_closes_request_without_provider(self):
        self.ns['_nova_lifecycle'].pending = True
        provider = AsyncMock()
        result, generate = await self.response(provider)
        self.assertEqual(result, '')
        generate.assert_not_awaited()
        self.assertEqual(self.request_ends(), [dict(type='request_end', request_id='request-1',
                         reply_to='human-1', register='voice', delivery='unavailable')])


class SegmentEvidenceTests(unittest.TestCase):
    def test_later_input_does_not_relabel_earlier_evidence_or_mutate_emitted_aliases(self):
        events = events_module.ResponseEvents(author='Nova', message_id='reply', run_id='run',
                                              request_id='first', reply_to='human-1')
        events.apply_inputs([dict(request_id='second', reply_to='human-2')], 1)
        meta = dict(turn_id='run', segment_index=1, input_revision=0,
                    audit=dict(status='PASS', turn_id='run', input_revision=0))
        part = events.segment('A completed result for the initial input.', meta)
        self.assertEqual(part['request_ids'], ['first'])
        part['request_ids'].append('untrusted-mutation')
        self.assertEqual(events.revisions[0]['request_ids'], ['first'])
        self.assertEqual(events.segments[0]['request_ids'], ['first'])
        with self.assertRaises(ValueError):
            events.segment('Duplicate delivery is rejected.', meta)
        meta.update(segment_index=2, input_revision=1)
        with self.assertRaises(ValueError):
            events.segment('Stale audit cannot certify a different revision.', meta)


if __name__ == '__main__':
    unittest.main()
