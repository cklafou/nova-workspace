# Last updated: 2026-10-05 18:30:24
# @nova: Exercise real Nova lifecycle HTTP routes with a fake launcher and isolated updater job manager.
import asyncio
import ast
import json
import types
import sys
from pathlib import Path
import threading
import unittest
from unittest.mock import AsyncMock, Mock

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from nova_chat.lifecycle import NovaLifecycle
from nova_updater import jobs, api


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = jobs.Jobs()
        self.calls = []
        self.data = {'ok': True, 'state': 'off', 'pending': False, 'target': None, 'chat_only': True}
        self.before_stop = AsyncMock()
        self.control = NovaLifecycle(chat_only=True, before_stop=self.before_stop,
                                     transport=self.transport, manager=self.manager, poll_seconds=60)
        app = FastAPI()
        app.include_router(self.control.router)
        app.include_router(api.create_router(lifecycle_pending=lambda: self.control.pending))
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1:8765')
        self.addAsyncCleanup(self.client.aclose)
        self.addAsyncCleanup(self.control.close)

    def transport(self, method, action):
        self.calls.append((method, action))
        if method == 'POST':
            target = 'on' if action == 'start' else 'off'
            if self.data['pending'] and self.data['target'] != target:
                return {'ok': False, 'error': 'Opposing transition pending'}, 409
            self.data.update(state='starting' if target == 'on' else 'stopping', pending=True, target=target)
            return dict(self.data), 202
        return dict(self.data), 200

    async def test_chat_only_can_request_start_without_touching_body(self):
        response = await self.client.post('/api/nova/start', json={})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()['state'], 'starting')
        self.assertTrue(response.json()['chat_only'])
        self.before_stop.assert_not_called()
        self.assertIsNotNone(self.manager.busy())

    async def test_paid_work_blocks_mode_switch_before_launcher_request(self):
        with self.manager.exclusive('Paid training'):
            response = await self.client.post('/api/nova/start', json={})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(self.calls, [])

    async def test_pending_transition_blocks_new_jobs_and_updater_mutations(self):
        await self.client.post('/api/nova/start', json={})
        with self.assertRaises(jobs.Conflict):
            self.manager.start('train', 'Another training run', lambda job: None, background=False)
        response = await self.client.post('/api/updater/check', json={})
        self.assertEqual(response.status_code, 409)

    async def test_duplicate_and_opposing_requests_keep_original_guard(self):
        await self.client.post('/api/nova/start', json={})
        self.assertEqual((await self.client.post('/api/nova/start', json={})).status_code, 202)
        self.assertEqual((await self.client.post('/api/nova/stop', json={})).status_code, 409)
        self.assertTrue(self.control.pending)
        self.assertIsNotNone(self.manager.busy())

    async def test_terminal_status_releases_guard_and_identifies_current_worker_mode(self):
        await self.client.post('/api/nova/start', json={})
        self.data.update(state='on', pending=False, target=None, chat_only=False)
        response = await self.client.get('/api/nova/lifecycle')
        self.assertTrue(response.json()['chat_only'])
        self.assertFalse(response.json()['launcher_chat_only'])
        self.assertFalse(response.json()['busy'])
        self.assertIsNone(self.manager.busy())

    async def test_stop_cancels_activity_only_for_enabled_worker(self):
        self.control.chat_only = False
        response = await self.client.post('/api/nova/stop', json={})
        self.assertEqual(response.status_code, 202)
        self.before_stop.assert_awaited_once()

    async def test_old_launcher_rejection_releases_updater_guard(self):
        self.control.transport = lambda *args: ({'ok': False, 'error': 'Update launcher'}, 404)
        response = await self.client.post('/api/nova/start', json={})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()['available'])
        self.assertIsNone(self.manager.busy())

    async def test_network_ambiguity_keeps_guard_until_terminal_status(self):
        def unavailable(*args):
            raise OSError('fixture network failure')
        self.control.transport = unavailable
        response = await self.client.post('/api/nova/start', json={})
        self.assertEqual(response.status_code, 503)
        self.assertIsNotNone(self.manager.busy())
        self.control.transport = self.transport
        await self.client.get('/api/nova/lifecycle')
        self.assertIsNone(self.manager.busy())

    async def test_status_cannot_unlock_guard_during_unacknowledged_post(self):
        entered, release = threading.Event(), threading.Event()
        def delayed(method, action):
            if method == 'POST':
                entered.set()
                release.wait(3)
            return self.transport(method, action)
        self.control.transport = delayed
        post = asyncio.create_task(self.client.post('/api/nova/start', json={}))
        await asyncio.to_thread(entered.wait, 2)
        status = asyncio.create_task(self.client.get('/api/nova/lifecycle'))
        await asyncio.sleep(.02)
        self.assertFalse(status.done())
        self.assertIsNotNone(self.manager.busy())
        release.set()
        await post
        self.assertEqual((await status).json()['state'], 'starting')
        self.assertIsNotNone(self.manager.busy())

    async def test_replacement_worker_inherits_pending_transition_before_serving_jobs(self):
        self.data.update(state='starting', pending=True, target='on')
        await self.control.initialize()
        self.assertTrue(self.control.pending)
        self.assertIsNotNone(self.manager.busy())
        response = await self.client.post('/api/updater/check', json={})
        self.assertEqual(response.status_code, 409)
        self.data.update(state='on', pending=False, target=None)
        await self.client.get('/api/nova/lifecycle')
        self.assertIsNone(self.manager.busy())

    async def test_undrained_operation_refuses_worker_shutdown(self):
        self.control.chat_only = False
        self.before_stop.return_value = {'stopped': False, 'operations': [{'id': 'still-writing'}]}
        response = await self.client.post('/api/nova/stop', json={})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.calls, [])
        self.assertIsNone(self.manager.busy())

    async def test_foreign_browser_or_form_cannot_trigger_lifecycle(self):
        response = await self.client.post('/api/nova/start', json={}, headers={'Origin': 'http://evil.invalid'})
        self.assertEqual(response.status_code, 403)
        response = await self.client.post('/api/nova/start', data={'start': 'true'})
        self.assertEqual(response.status_code, 415)
        self.assertEqual(self.calls, [])


class ServerTransitionTests(unittest.IsolatedAsyncioTestCase):
    def extract(self, names, ns):
        path = Path(__file__).resolve().parents[1] / 'server.py'
        nodes = [node for node in ast.parse(path.read_text(encoding='utf-8')).body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
        for node in nodes:
            node.decorator_list = []
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), ns)
        return ns

    async def test_transition_blocks_new_body_actions_but_keeps_collaboration_and_status(self):
        ns = self.extract({'_chat_only_blocks', '_auth_gate'}, {
            'CHAT_ONLY': False, 'Request': object, 'JSONResponse': JSONResponse,
            '_nova_lifecycle': types.SimpleNamespace(pending=True), '_LOCAL_HOSTS': {'127.0.0.1'}})
        next_handler = AsyncMock(return_value=JSONResponse({'ok': True}))
        for path in ['/api/wake', '/api/runtime/resume', '/nova-message', '/api/llama/start', '/sessions/new']:
            request = types.SimpleNamespace(client=types.SimpleNamespace(host='127.0.0.1'),
                                            url=types.SimpleNamespace(path=path), method='POST')
            response = await ns['_auth_gate'](request, next_handler)
            self.assertEqual(response.status_code, 409)
        next_handler.assert_not_called()
        for path, method in [('/api/nova/lifecycle','GET'),('/api/nova/quiesce','POST'),('/api/collaboration/messages','POST')]:
            request = types.SimpleNamespace(client=types.SimpleNamespace(host='127.0.0.1'),
                                            url=types.SimpleNamespace(path=path), method=method)
            self.assertEqual((await ns['_auth_gate'](request,next_handler)).status_code,200)

    async def test_cancelled_response_cannot_drain_queued_message_during_shutdown(self):
        queue = [{'content': 'Keep this queued message'}]
        stop = asyncio.Event(); stop.set()
        ns = self.extract({'_drain_cole_queue'}, {'is_processing': False, '_cole_message_queue': queue,
                          '_nova_lifecycle': types.SimpleNamespace(pending=True), '_stop_requested':stop})
        await ns['_drain_cole_queue']()
        self.assertEqual(len(queue),1)
        self.assertTrue(stop.is_set())

    async def test_flush_and_owned_helper_cleanup_require_drained_operations(self):
        active=Mock(); runtime=Mock()
        stop=AsyncMock(return_value=JSONResponse({'stopped':False,'remaining':[{'id':'writing'}]}))
        ns=self.extract({'_prepare_nova_off','_quiesce_nova_worker'}, {
            'CHAT_ONLY':False,'asyncio':asyncio,'json':json,'JSONResponse':JSONResponse,
            'session_mgr':types.SimpleNamespace(active=active),'_rt':runtime,'stop_endpoint':stop})
        response=await ns['_quiesce_nova_worker']()
        self.assertEqual(response.status_code,409)
        active.flush_all.assert_not_called();runtime.stop_indexer.assert_not_called()
        stop.return_value=JSONResponse({'stopped':True,'remaining':[]})
        response=await ns['_quiesce_nova_worker']()
        self.assertEqual(response.status_code,200)
        active.flush_all.assert_called_once();runtime.stop_indexer.assert_called_once()
        runtime.stop_computer_session.assert_called_once()


if __name__ == '__main__':
    unittest.main()
