# @nova: Exercise real server voice routing and response callbacks with isolated providers, sessions and event sinks.
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


class Transcript:
    def __init__(self):
        self.messages = []

    def add(self, author, content, directed_at=None, images=None):
        message = {'id': 'stored-' + str(len(self.messages)), 'author': author,
                   'content': content, 'timestamp': datetime.now().isoformat(), 'images': images or []}
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
            asyncio=asyncio, json=json, uuid=uuid, datetime=datetime,
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
            _cole_message_queue=[], is_processing=False,
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
        fake_cortex.executive = types.SimpleNamespace(note_activity=Mock(), autonomy_enabled=lambda: False)
        self.modules = patch.dict(sys.modules, {'nova_runtime': fake_runtime,
                                                'nova_runtime.operations': fake_operations,
                                                'nova_cortex': fake_cortex})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        extract(SERVER, {'run_ai_response', '_run_response_queue', '_drain_cole_queue', '_end_queued_request',
                         'websocket_endpoint'}, self.ns)

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
                                            reply_to='stored-0', request_id='voice-001'))
        self.assertEqual(second.args[3], 'second')
        self.assertEqual(second.kwargs, dict(images=second_image, source='drain', register='voice_fast',
                                             reply_to='stored-1', request_id='voice-002'))
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

    async def test_newest_queue_policy_closes_older_request_ids_without_inventing_runs(self):
        pending = self.hold_scheduled_responses()
        first = self.queued_request('older', 'old-1')
        second = self.queued_request('middle', 'old-2', 'voice_fast')
        self.queued_request('newest', 'new-3')
        await self.ns['_drain_cole_queue']()
        self.assertEqual(self.request_ends(), [
            dict(type='request_end', request_id='old-1', reply_to=first['msg']['id'], register='voice', delivery='superseded'),
            dict(type='request_end', request_id='old-2', reply_to=second['msg']['id'], register='voice_fast', delivery='superseded')])
        self.assertTrue(self.ns['is_processing'])
        self.assertEqual(len(pending), 1)
        await pending.pop(0)
        run = self.ns['run_ai_response']
        run.assert_awaited_once()
        self.assertEqual(run.await_args.args[3], 'newest')
        self.assertEqual(run.await_args.kwargs['request_id'], 'new-3')
        self.assertFalse(self.ns['is_processing'])
        self.assertTrue(all('run_id' not in event and 'audit' not in event for event in self.request_ends()))

    async def test_already_answered_queue_request_closes_without_new_generation(self):
        pending = self.hold_scheduled_responses()
        request = self.queued_request('already seen', 'answered-1')
        self.transcript.add('Nova', 'Prior run answered this input.')
        self.ns['_inflight_upto'] = 1
        await self.ns['_drain_cole_queue']()
        self.assertEqual(self.request_ends(), [dict(type='request_end', request_id='answered-1',
                         reply_to=request['msg']['id'], register='voice', delivery='answered_elsewhere')])
        self.assertEqual(pending, [])
        self.ns['get_status'].assert_not_awaited()
        self.assertFalse(self.ns['is_processing'])
        self.assertFalse(any(e['type'] == 'processing_start' for e in self.events))

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
            if event.get('delivery') == 'superseded':
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
            self.assertEqual(len(self.ns['_cole_message_queue']), 1)
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
        self.assertEqual([call.kwargs['request_id'] for call in calls], ['selected', 'later'])
        self.assertEqual(len([e for e in self.events if e['type'] == 'processing_start']), 2)
        self.assertEqual([e['request_id'] for e in self.request_ends()], ['old'])
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
        self.queued_request('older', 'old')
        self.queued_request('selected', 'selected')
        normal_broadcast = self.ns['broadcast']
        async def stop_on_discard(event):
            await normal_broadcast(event)
            if event.get('delivery') == 'superseded':
                self.ns['_stop_requested'].set()
                await asyncio.sleep(0)
        self.ns['broadcast'] = stop_on_discard
        await self.ns['_drain_cole_queue']()
        self.assertEqual(pending, [])
        self.assertEqual([(e['request_id'], e['delivery']) for e in self.request_ends()],
                         [('old', 'superseded'), ('selected', 'cancelled')])
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
        for disposition in ('answered_elsewhere', 'unavailable', 'cancelled'):
            with self.subTest(disposition=disposition):
                self.events.clear()
                self.transcript.messages.clear()
                self.ns['_stop_requested'].clear()
                self.ns['_inflight_upto'] = 0
                self.queued_request('selected', 'partial-terminal')
                if disposition == 'answered_elsewhere':
                    self.transcript.add('Nova', 'already answered')
                    self.ns['_inflight_upto'] = 1
                elif disposition == 'cancelled':
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


if __name__ == '__main__':
    unittest.main()
