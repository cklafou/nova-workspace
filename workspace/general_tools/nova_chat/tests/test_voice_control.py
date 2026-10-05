# @nova: Test voice HTTP supervision and worker cancellation with temporary settings and fake processes/audio only.
"""Run: python -B workspace/general_tools/nova_chat/tests/test_voice_control.py
No production settings, child services, audio devices, models or GPU are used.
"""
from __future__ import annotations

import asyncio
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch

import httpx
from fastapi import FastAPI

TOOLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / 'voice_gateway'))
from nova_chat import voice_control as vc
from body import MemoryBody
from config import GatewayConfig
from nova_link import parse_event
from turns import VoiceSession
import stt
import tts
import speech

spec = importlib.util.spec_from_file_location('voice_control_worker_fixture', TOOLS / 'voice_gateway' / 'control_worker.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def readiness():
    return {'available': True, 'reason': 'Ready in fixture', 'capabilities': {
        'microphone_mute': True, 'output_mute': True, 'microphone_test': True, 'speaker_test': True},
        'backends': {'input': 'fake', 'output': 'fake'}}


class FakeThread:
    def __init__(self, *args, **kwargs):
        self.kwargs, self.started, self.joined = kwargs, False, False
    def start(self): self.started = True
    def join(self, **kwargs): self.joined = True


class FakeChild:
    pid = 98765432
    def __init__(self, events=(), code=None):
        self.returncode = code
        self.stdout = io.StringIO(''.join(vc.PREFIX + json.dumps(e) + '\n' for e in events))
        self.stdin = io.StringIO()
        self.kills = 0
        self.wait_calls = []
        self.wait_results = []
    def poll(self): return self.returncode
    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        if self.wait_results:
            result = self.wait_results.pop(0)
            if isinstance(result, BaseException): raise result
            self.returncode = result
        elif self.returncode is None:
            self.returncode = 0
        return self.returncode
    def kill(self): self.kills += 1; self.returncode = -9


class ControllerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        self.enabled = True
        self.control = vc.VoiceController(self.workspace, nova_enabled=lambda: self.enabled)
        self.children = []
        def child(*args, **kwargs):
            process = FakeChild()
            self.children.append(process)
            return process
        self.spawn = self.enterContext(patch.object(vc.subprocess, 'Popen', side_effect=child))
        self.run = self.enterContext(patch.object(vc.subprocess, 'run', side_effect=AssertionError('Unexpected real command')))
        self.thread = self.enterContext(patch.object(vc.threading, 'Thread', FakeThread))
        self.probe = self.enterContext(patch.object(self.control, '_small', return_value=readiness()))
        app = FastAPI(); app.include_router(self.control.router)
        self.app = app
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://127.0.0.1:8765')
        self.addAsyncCleanup(self.client.aclose)
        self.addAsyncCleanup(self.control.close)

    async def test_status_only_uses_cached_probe_no_capture_process_or_files(self):
        for _ in range(3):
            response = await self.client.get('/api/voice/status')
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()['running'])
        self.probe.assert_called_once_with('probe')
        self.spawn.assert_not_called()
        self.run.assert_not_called()
        self.assertFalse(self.control.settings_path.exists())
        self.assertEqual(list(self.workspace.iterdir()), [])

    async def test_actual_probe_command_uses_gateway_python_and_only_probe_mode(self):
        interpreter = self.control.folder / '.venv' / 'Scripts' / 'python.exe'
        interpreter.parent.mkdir(parents=True); interpreter.touch()
        result = types.SimpleNamespace(returncode=0, stdout='ignored setup line\n' + vc.PREFIX +
            json.dumps({'type': 'probe', **readiness()}) + '\n', stderr='')
        self.run.side_effect = None; self.run.return_value = result
        found = vc.VoiceController._small(self.control, 'probe')
        self.assertTrue(found['available'])
        args, kwargs = self.run.call_args
        self.assertEqual(args[0][0], str(interpreter))
        self.assertEqual(args[0][-1], 'probe')
        self.assertEqual(kwargs['cwd'], self.workspace)
        self.assertEqual(json.loads(kwargs['env']['NOVA_VOICE_SETTINGS_JSON']), self.control.settings)
        self.spawn.assert_not_called()

    async def test_remote_client_rejected_before_any_probe_or_action(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, client=('192.0.2.1', 1)),
                                     base_url='http://127.0.0.1:8765') as remote:
            for method, route in [('GET', '/status'), ('POST', '/test'), ('POST', '/start')]:
                response = await remote.request(method, '/api/voice' + route, json={'kind': 'microphone'})
                self.assertEqual(response.status_code, 403)
        self.probe.assert_not_called(); self.spawn.assert_not_called()

    async def test_cross_origin_simple_post_cannot_activate_audio(self):
        response = await self.client.post('/api/voice/test', content='{"kind":"microphone"}',
            headers={'Origin': 'https://other.example', 'Content-Type': 'text/plain'})
        self.assertEqual(response.status_code, 403)
        self.spawn.assert_not_called()

    async def test_nonlocal_host_and_forwarded_headers_rejected(self):
        for headers in ({'Host': 'other.example'}, {'X-Forwarded-For': '203.0.113.1'}, {'Sec-Fetch-Site': 'cross-site'}):
            with self.subTest(headers=headers):
                response = await self.client.get('/api/voice/status', headers=headers)
                self.assertEqual(response.status_code, 403)
        self.probe.assert_not_called()

    async def test_device_settings_are_strict_and_persist_atomically(self):
        bad = [{'input_device': True}, {'input_device': '2'}, {'output_device': -2},
               {'output_device': 4097}, {'tts_backend': 'unknown'}, ['invalid']]
        for payload in bad:
            with self.subTest(payload=payload):
                self.assertEqual((await self.client.post('/api/voice/config', json=payload)).status_code, 422)
        self.assertFalse(self.control.settings_path.exists())
        response = await self.client.post('/api/voice/config', json={'input_device': 2, 'output_device': 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(self.control.settings_path.read_text()), {'input_device': 2, 'output_device': 3})
        self.assertFalse(self.control.settings_path.with_name('voice_devices.json.tmp').exists())
        restored = vc.VoiceController(self.workspace)
        self.assertEqual(restored.settings, {'input_device': 2, 'output_device': 3})
        self.spawn.assert_not_called(); self.probe.assert_not_called()

    async def test_devices_are_queried_only_by_explicit_request(self):
        data = {'inputs': [{'id': 2, 'name': 'Fake microphone', 'default': True}], 'outputs': []}
        self.probe.return_value = data
        response = await self.client.get('/api/voice/devices')
        self.assertEqual(response.json(), data)
        self.probe.assert_called_once_with('devices')
        self.spawn.assert_not_called()

    async def test_nova_off_blocks_voice_but_allows_device_test(self):
        self.enabled = False
        self.assertEqual((await self.client.post('/api/voice/start', json={})).status_code, 409)
        self.probe.assert_not_called(); self.spawn.assert_not_called()
        self.assertEqual((await self.client.post('/api/voice/test', json={'kind': 'speaker'})).status_code, 200)
        self.assertEqual(self.spawn.call_args.args[0][-1], 'speaker')

    async def test_one_child_shared_by_start_tests_and_device_configuration(self):
        response = await self.client.post('/api/voice/start', json={})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['running'])
        for route, body in [('/start', {}), ('/test', {'kind': 'microphone'}), ('/config', {'input_device': 1})]:
            self.assertEqual((await self.client.post('/api/voice' + route, json=body)).status_code, 409)
        self.assertEqual(self.spawn.call_count, 1)
        self.assertFalse(self.control.settings_path.exists())

    async def test_unready_probe_and_failed_spawn_surface_actionable_errors(self):
        self.probe.return_value = {'available': False, 'reason': 'Fixture dependency missing', 'capabilities': {}}
        response = await self.client.post('/api/voice/start', json={})
        self.assertEqual(response.status_code, 503)
        self.assertIn('dependency missing', response.json()['detail'])
        self.spawn.assert_not_called()
        self.probe.return_value = readiness(); self.spawn.side_effect = OSError('Fixture spawn failure')
        response = await self.client.post('/api/voice/start', json={})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.control.snapshot()['state'], 'error')
        self.assertFalse(self.control.snapshot()['running'])

    async def test_mute_returns_only_acknowledged_state(self):
        await self.client.post('/api/voice/start', json={})
        for payload in ({}, {'output': 'yes'}, {'output': 1}, {'other': True}, []):
            self.assertEqual((await self.client.post('/api/voice/mute', json=payload)).status_code, 422)
        response = await self.client.post('/api/voice/mute', json={'output': True})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['output_muted'])
        self.assertEqual(json.loads(self.children[0].stdin.getvalue()), {'command': 'mute', 'output': True})
        self.control._event({'type': 'mute', 'output_muted': True, 'microphone_muted': False})
        self.assertTrue((await self.client.get('/api/voice/status')).json()['output_muted'])

    async def test_stop_sends_control_then_clears_owned_child_and_cancels_test(self):
        await self.client.post('/api/voice/test', json={'kind': 'microphone'})
        self.control._event({'type': 'test', 'kind': 'microphone', 'state': 'running'})
        response = await self.client.post('/api/voice/stop', json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(self.children[0].stdin.getvalue()), {'command': 'stop'})
        self.assertEqual(response.json()['state'], 'off')
        self.assertFalse(response.json()['running'])
        self.assertEqual(response.json()['test_result']['state'], 'cancelled')
        self.run.assert_not_called()

    async def test_late_previous_worker_events_cannot_change_new_session(self):
        await self.client.post('/api/voice/start', json={})
        old_generation = self.control._generation
        old = FakeChild([{'type': 'error', 'message': 'stale failure'},
                         {'type': 'body', 'event': {'type': 'caption', 'text': 'stale words'}}], code=5)
        self.control._generation += 1
        active = self.control._proc
        self.control._read_worker(old, old_generation)
        self.assertIs(self.control._proc, active)
        self.assertIsNone(self.control.snapshot()['error'])
        self.assertIsNone(self.control.snapshot()['last_caption'])

    async def test_worker_error_caption_and_microphone_result_are_retained(self):
        self.control._mode = 'microphone'
        self.control._event({'type': 'error', 'message': 'Fixture microphone failure'})
        self.assertEqual(self.control.snapshot()['test_result']['state'], 'error')
        self.control._event({'type': 'test', 'kind': 'microphone', 'state': 'complete', 'peak': .2, 'rms': .1})
        self.control._event({'type': 'body', 'event': {'type': 'caption', 'text': 'Delivered words',
            'audit': {'status': 'INCOMPLETE', 'reason': 'No image'}, 'clock': 'playback'}})
        data = self.control.snapshot()
        self.assertEqual(data['test_result']['peak'], .2)
        self.assertEqual(data['last_caption']['audit']['status'], 'INCOMPLETE')

    async def test_cancelled_speaker_result_is_not_overwritten_as_failure(self):
        self.control._mode = 'speaker'
        self.control._event({'type': 'test', 'kind': 'speaker', 'state': 'cancelled', 'message': 'Speaker test stopped'})
        self.control._event({'type': 'body', 'event': {'type': 'speech', 'phase': 'end', 'outcome': 'cut'}})
        self.assertEqual(self.control.snapshot()['test_result']['state'], 'cancelled')

    async def test_failed_child_exit_retains_error_and_invalid_events_do_not_crash_reader(self):
        self.control._mode = 'run'
        child = FakeChild([None, {'type': 'body', 'event': 'bad'}, {'type': 'error', 'message': 'Worker failed'}], code=1)
        self.control._proc = child
        self.control._read_worker(child, self.control._generation)
        self.assertEqual(self.control.snapshot()['state'], 'error')
        self.assertEqual(self.control.snapshot()['error'], 'Worker failed')
        self.assertFalse(self.control.snapshot()['running'])
        self.assertEqual(len(self.control.snapshot()['diagnostics']), 2)


class FakePlayer:
    instances = []
    def __init__(self, *args, **kwargs):
        self.queued = []; self.interruptions = []; self.closed = False
        self.instances.append(self)
    def start(self): return self
    def say(self, item): self.queued.append(item)
    def active(self): return False
    def interrupt(self, why): self.interruptions.append(why); self.queued.clear()
    async def drain(self): pass
    async def close(self): self.closed = True; self.queued.clear()


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.events = []
        self.enterContext(patch.object(worker, 'report', side_effect=lambda kind, **fields: self.events.append({'type': kind, **fields})))
        self.cfg = GatewayConfig()
        self.control = worker.Control()
        FakePlayer.instances = []

    async def test_probe_checks_presence_without_loading_audio_or_models(self):
        self.cfg.tts_backend = 'windows'
        installed = {'numpy', 'sounddevice', 'moonshine_onnx', 'websockets'}
        with patch.object(worker, '_installed', side_effect=lambda name: name in installed), \
             patch.object(worker.sys, 'platform', 'win32'), patch.object(worker.shutil, 'which', return_value='fake-powershell'), \
             patch.dict(sys.modules, {'sounddevice': None, 'torch': None, 'moonshine_onnx': None}):
            result = worker.probe(self.cfg)
        self.assertTrue(result['available'])
        self.assertTrue(result['capabilities']['microphone_test'])
        self.assertEqual(result['backends']['output'], 'windows')

    async def test_control_mute_acknowledges_flags_and_interrupts_current_output(self):
        player = FakePlayer(); session = types.SimpleNamespace(output_muted=False, player=player)
        self.control.session = session
        self.control.command({'command': 'mute', 'microphone': True, 'output': True})
        self.assertTrue(self.control.microphone_muted and session.output_muted)
        self.assertEqual(player.interruptions, ['output_muted'])
        self.assertEqual(self.events[-1], {'type': 'mute', 'microphone_muted': True, 'output_muted': True})
        self.control.command({'command': 'mute', 'output': False})
        self.assertFalse(session.output_muted)
        self.control.command({'command': 'stop'})
        self.assertTrue(self.control.stop.is_set())

    async def test_muted_delivered_reply_closes_request_but_never_queues_for_later(self):
        player, body = FakePlayer(), MemoryBody()
        session = VoiceSession(self.cfg, player, body)
        session.sent('request', 'Hello')
        session.output_muted = True
        context = {'author': 'Nova', 'request_id': 'request', 'reply_to': 'user', 'id': 'reply', 'run_id': 'run'}
        frames = [{'type': 'user_message', 'request_id': 'request', 'id': 'user'},
                  {'type': 'message_start', **context}, {'type': 'message_end', **context,
                   'content': 'Delivered but muted', 'delivery': 'delivered', 'audit': {'status': 'PASS'}}]
        for frame in frames: session.handle(parse_event(frame))
        self.assertEqual(player.queued, [])
        self.assertEqual(session.pending, {})
        self.assertIn('muted', body.of('message')[-1]['why'])
        session.output_muted = False
        session.handle(parse_event(frames[-1]))
        self.assertEqual(player.queued, [])

    async def test_pre_cancelled_speaker_test_never_loads_or_queues_audio(self):
        self.control.stop.set()
        backend = types.SimpleNamespace(name='fake', close=Mock())
        with patch.object(tts, 'make_tts', return_value=backend) as factory, patch.object(speech, 'SpeechPlayer', FakePlayer):
            await worker.speaker_test(self.cfg, self.control)
        factory.assert_not_called()
        self.assertEqual(FakePlayer.instances, [])

    async def test_stop_during_speaker_loading_prevents_any_queued_output(self):
        entered, release = threading.Event(), threading.Event()
        backend = types.SimpleNamespace(name='fake', close=Mock())
        def factory(cfg): entered.set(); release.wait(2); return backend
        with patch.object(tts, 'make_tts', side_effect=factory), patch.object(speech, 'SpeechPlayer', FakePlayer):
            task = asyncio.create_task(worker.speaker_test(self.cfg, self.control))
            try:
                for _ in range(100):
                    if entered.is_set(): break
                    await asyncio.sleep(.005)
                self.assertTrue(entered.is_set())
                self.control.stop.set(); release.set()
                await asyncio.wait_for(task, 1)
            finally:
                release.set()
                if not task.done(): task.cancel(); await asyncio.gather(task, return_exceptions=True)
        self.assertEqual(FakePlayer.instances, [])
        backend.close.assert_called_once()

    async def test_pre_cancelled_microphone_test_never_opens_device(self):
        self.control.stop.set()
        stream = Mock(); stream.__enter__ = Mock(return_value=stream); stream.__exit__ = Mock(return_value=False)
        audio = types.SimpleNamespace(InputStream=Mock(return_value=stream))
        with patch.dict(sys.modules, {'numpy': types.ModuleType('numpy'), 'sounddevice': audio}):
            await worker.microphone_test(self.cfg, self.control)
        audio.InputStream.assert_not_called()

    async def test_pre_cancelled_voice_never_initializes_recognition_or_tts(self):
        self.control.stop.set()
        recognition = types.SimpleNamespace(close=Mock())
        output = types.SimpleNamespace(name='fake', close=Mock())
        with patch.object(stt, 'MoonshineSTT', return_value=recognition) as input_factory, \
             patch.object(tts, 'make_tts', return_value=output) as output_factory:
            await worker.voice(self.cfg, self.control)
        input_factory.assert_not_called(); output_factory.assert_not_called()

    async def test_stop_during_recognition_loading_skips_tts_initialization(self):
        entered, release = threading.Event(), threading.Event()
        recognition = types.SimpleNamespace(close=Mock())
        output = types.SimpleNamespace(name='fake', close=Mock())
        def load(cfg): entered.set(); release.wait(2); return recognition
        with patch.object(stt, 'MoonshineSTT', side_effect=load), patch.object(tts, 'make_tts', return_value=output) as output_factory:
            task = asyncio.create_task(worker.voice(self.cfg, self.control))
            try:
                for _ in range(100):
                    if entered.is_set(): break
                    await asyncio.sleep(.005)
                self.assertTrue(entered.is_set())
                self.control.stop.set(); release.set()
                await asyncio.wait_for(task, 1)
            finally:
                release.set()
                if not task.done(): task.cancel(); await asyncio.gather(task, return_exceptions=True)
        output_factory.assert_not_called(); recognition.close.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
