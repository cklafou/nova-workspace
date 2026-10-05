# Last updated: 2026-10-06 03:10:51
# @nova: Verify voice transport and disconnect cleanup against a local mock WebSocket server.
#   2026-10-05 event contract, the gateway's NovaLink + session on the other end. No Nova, no audio.
"""Run: python general_tools/voice_gateway/test_link_socket.py   (needs `websockets`; skips without)"""
from __future__ import annotations

import asyncio
import json
import sys
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    import websockets
except Exception:  # pragma: no cover
    websockets = None

from body import MemoryBody                     # noqa: E402
from config import GatewayConfig                # noqa: E402
from speech import SpeechPlayer                 # noqa: E402
from turns import VoiceSession                  # noqa: E402


class RecordingTTS:
    name = "recording"

    def __init__(self):
        self.spoken = []
        self.lock = threading.Lock()

    def speak(self, text):
        with self.lock:
            self.spoken.append(text)

    def stop(self):
        pass

    def close(self):
        pass


@unittest.skipIf(websockets is None, "websockets is not installed")
class LinkOverSocket(unittest.IsolatedAsyncioTestCase):
    async def test_scoped_stop_waits_for_exact_final_receipt_and_never_sends_global(self):
        from nova_link import NovaLink
        received, release, pending_seen = [], asyncio.Event(), asyncio.Event()
        async def server(ws):
            async for raw in ws:
                data = json.loads(raw); received.append(data)
                await ws.send(json.dumps({'type': 'stop_pending', 'request_id': data['request_id']}))
                pending_seen.set()
                await release.wait()
                await ws.send(json.dumps({'type': 'stopped', 'request_id': data['request_id'], 'matched': True}))
        async with websockets.serve(server, '127.0.0.1', 0) as fixture:
            port = next(iter(fixture.sockets)).getsockname()[1]
            async with NovaLink(f'ws://127.0.0.1:{port}') as link:
                async def listen():
                    async for event in link.events(): pass
                listener = asyncio.create_task(listen())
                stop = asyncio.create_task(link.stop('my-request'))
                try:
                    await asyncio.wait_for(pending_seen.wait(), 1)
                    await asyncio.sleep(.03)
                    self.assertFalse(stop.done(), 'stop_pending incorrectly confirmed cancellation')
                    release.set()
                    self.assertTrue(await asyncio.wait_for(stop, 1))
                    self.assertEqual(received, [{'type': 'stop', 'request_id': 'my-request'}])
                finally:
                    release.set(); listener.cancel(); stop.cancel()
                    await asyncio.gather(listener, stop, return_exceptions=True)

    async def test_request_id_round_trip_and_only_delivered_reply_spoken(self):
        from nova_link import NovaLink, new_request_id
        received = []

        async def fake_nova_chat(ws):
            async for raw in ws:
                msg = json.loads(raw)
                received.append(msg)
                if msg.get("type") != "message":
                    continue
                rid = msg["request_id"]
                ctx = {"author": "Nova", "id": "m1", "run_id": "run1", "reply_to": "u1", "request_id": rid,
                       "register": msg.get("register")}
                for frame in (
                    {"type": "status", "nova": "online"},
                    {"type": "user_message", "author": msg["speaker"], "id": "u1", "request_id": rid,
                     "content": msg["content"]},
                    {"type": "message_end", "author": "Nova", "id": "m0", "content": "⚠ stale diagnostic"},
                    {**ctx, "type": "message_start"},
                    {**ctx, "type": "token", "token": "Pre-audit draft words. "},
                    {"type": "pipeline", "stage": "witness_check"},
                    {**ctx, "type": "message_end", "content": "The API was down.\n\n[`read_file` resulted in "
                     "1792 bytes.]\n\nI'll check again later.", "delivery": "delivered",
                     "audit": {"status": "INCOMPLETE", "reason": "evidence cut", "source": "inline"}},
                ):
                    await ws.send(json.dumps(frame))

        async with websockets.serve(fake_nova_chat, "127.0.0.1", 0) as server:
            port = next(iter(server.sockets)).getsockname()[1]
            cfg = GatewayConfig()
            body, tts = MemoryBody(), RecordingTTS()
            async with NovaLink(f"ws://127.0.0.1:{port}/ws", "Cole", "voice") as link:
                player = SpeechPlayer(tts, body, tail_s=0).start()
                session = VoiceSession(cfg, player, body, log=lambda *_: None)
                rid = new_request_id()
                session.sent(rid, "was vtube studio up?")
                await link.say("was vtube studio up?", request_id=rid)

                async def until_done():
                    async for ev in link.events():
                        session.handle(ev)
                        if rid not in session.pending:
                            return
                await asyncio.wait_for(until_done(), timeout=10)
                await player.drain()
                await player.close()

        sent = [m for m in received if m.get("type") == "message"][0]
        self.assertEqual((sent["speaker"], sent["register"], sent["request_id"]), ("Cole", "voice", rid))
        self.assertEqual(len(rid), 32)
        self.assertEqual(tts.spoken, ["The API was down.", "I'll check again later."])
        self.assertEqual({c["audit"]["status"] for c in body.of("caption")}, {"INCOMPLETE"})
        self.assertEqual(len([d for d in body.of("diagnostic") if "old server" in d["message"]]), 1)


@unittest.skipIf(websockets is None, "websockets is not installed")
class Supervision(unittest.IsolatedAsyncioTestCase):
    async def test_socket_loss_stops_the_mic_and_cleans_up(self):
        import gateway
        import stt as stt_module
        import tts as tts_module

        class ForeverMic:
            name, gate, on_speech_start, closed = "forever", None, None, False

            async def utterances(self):
                await asyncio.Event().wait()
                yield ""                                           # never reached

            def close(self):
                ForeverMic.closed = True

        async def hang_up(ws):
            await ws.send(json.dumps({"type": "status", "nova": "online"}))
            await ws.close()

        async with websockets.serve(hang_up, "127.0.0.1", 0) as server:
            port = next(iter(server.sockets)).getsockname()[1]
            cfg = GatewayConfig()
            cfg.nova_ws_url = f"ws://127.0.0.1:{port}/ws"
            body = MemoryBody()
            originals = (stt_module.make_stt, tts_module.make_tts, gateway.make_body)
            stt_module.make_stt = lambda c: ForeverMic()
            tts_module.make_tts = lambda c: RecordingTTS()
            gateway.make_body = lambda c: body
            try:
                await asyncio.wait_for(gateway.run(cfg), timeout=10)
            finally:
                stt_module.make_stt, tts_module.make_tts, gateway.make_body = originals
        self.assertTrue(ForeverMic.closed)
        self.assertTrue(any("link ended" in d["message"] for d in body.of("diagnostic")))


@unittest.skipIf(websockets is None, "websockets is not installed")
class LiveWorkerPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_worker_utterance_reaches_correlated_playback_and_stop_cleans_up(self):
        # Real worker orchestration + local WebSocket; fake capture/playback only.
        # This is transport integration, explicitly not hardware audibility proof.
        import control_worker as worker
        import stt as recognition
        import tts as output
        from unittest.mock import patch
        class Mic:
            name = 'fixture recognizer'
            gate = on_speech_start = on_diagnostic = None
            closed = False
            async def utterances(self):
                yield 'Hello Nova.'
                await asyncio.Event().wait()
            def close(self): self.closed = True
        class Voice:
            name = 'fixture audio'
            closed = False
            def __init__(self): self.spoken = []
            def speak(self, text, should_stop=None, on_playback=None):
                if should_stop(): return {'outcome': 'skipped'}
                self.spoken.append(text)
                on_playback()
                return {'outcome': 'played'}
            def stop(self): pass
            def close(self): self.closed = True
        mic, voice, events, requests = Mic(), Voice(), [], []
        control = worker.Control()
        async def server(ws):
            async for raw in ws:
                request = json.loads(raw); requests.append(request)
                rid = request['request_id']
                ids = dict(author='Nova', request_id=rid, reply_to='user1', id='reply1', run_id='run1')
                for frame in [dict(type='user_message', request_id=rid, id='user1'),
                              dict(type='message_start', **ids),
                              dict(type='message_end', content='Hello Cole.', delivery='delivered',
                                   audit={'status': 'INCOMPLETE'}, **ids)]:
                    await ws.send(json.dumps(frame))
        def report(kind, **fields):
            events.append(dict(type=kind, **fields))
            body = fields.get('event', {})
            if body.get('type') == 'speech' and body.get('phase') == 'end':
                control.command({'command': 'stop'})
        async with websockets.serve(server, '127.0.0.1', 0) as fixture:
            port = next(iter(fixture.sockets)).getsockname()[1]
            cfg = GatewayConfig(nova_ws_url=f'ws://127.0.0.1:{port}/ws')
            with patch.object(recognition, 'make_stt', return_value=mic) as factory, \
                 patch.object(recognition, 'local_asset_status', return_value={'label': 'fixture'}), \
                 patch.object(output, 'make_tts', return_value=voice), patch.object(worker, 'report', side_effect=report):
                await asyncio.wait_for(worker.voice(cfg, control), 5)
            factory.assert_called_once_with(cfg, allow_fallback=False)
        self.assertEqual(voice.spoken, ['Hello Cole.'])
        self.assertTrue(mic.closed and voice.closed)
        self.assertEqual(len(requests), 1)
        body = [e['event'] for e in events if e['type'] == 'body']
        end = next(e for e in body if e['type'] == 'speech' and e['phase'] == 'end')
        self.assertEqual(end['outcome'], 'played')
        self.assertEqual(end['request_id'], requests[0]['request_id'])
        self.assertTrue(any(e['type'] == 'caption' and e['clock'] == 'playback' for e in body))

    async def test_end_call_cancels_owned_request_before_socket_close(self):
        import control_worker as worker
        import nova_link
        import stt as recognition
        import tts as output
        from unittest.mock import Mock, patch
        record, frames = [], asyncio.Queue()
        control = worker.Control()
        class Link:
            def __init__(self, *args): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): record.append('socket_closed')
            async def say(self, text, request_id):
                record.append(('sent', request_id))
                await frames.put(nova_link.parse_event(dict(type='user_message', request_id=request_id, id='u1')))
                await frames.put(nova_link.parse_event(dict(type='message_start', request_id=request_id, id='m1',
                                                           reply_to='u1', run_id='run1', author='Nova')))
            async def stop(self, request_id=None, *, timeout_s=2):
                if not request_id: raise AssertionError('global stop is forbidden')
                record.append(('cancel_requested', request_id))
                await asyncio.sleep(.02)
                record.append('cancel_acknowledged')
                return True
            async def events(self):
                while True: yield await frames.get()
        class Mic:
            name = 'fixture'
            gate = on_speech_start = on_state = on_diagnostic = None
            async def utterances(self):
                self.on_state('transcribing'); self.on_state('listening')
                yield 'Hello'
                await asyncio.Event().wait()
            def close(self): pass
        voice = RecordingTTS()
        def report(kind, **fields):
            event = fields.get('event', {})
            if event.get('type') == 'state' and event.get('state') == 'thinking':
                control.command({'command': 'stop'})
            if event.get('state') == 'transcribing': record.append('transcribing')
        with patch.object(nova_link, 'NovaLink', Link), patch.object(recognition, 'make_stt', return_value=Mic()), \
             patch.object(recognition, 'local_asset_status', return_value={'label':'fixture'}), \
             patch.object(output, 'make_tts', return_value=voice), patch.object(worker, 'report', side_effect=report):
            await asyncio.wait_for(worker.voice(GatewayConfig(), control), 2)
        sent = next(item[1] for item in record if isinstance(item, tuple) and item[0] == 'sent')
        self.assertIn(('cancel_requested', sent), record)
        self.assertLess(record.index('cancel_acknowledged'), record.index('socket_closed'))
        self.assertIn('transcribing', record)
        self.assertEqual(voice.spoken, [])

    async def test_audio_smoke_refuses_null_before_opening_transport(self):
        import gateway
        import tts as output
        from unittest.mock import patch
        cfg = GatewayConfig(tts_backend='null')
        with patch.object(output, 'make_tts', return_value=output.NullTTS(cfg)):
            with self.assertRaisesRegex(RuntimeError, 'NullTTS is not voice proof'):
                await gateway.smoke_link(cfg, 'fixture', audio=True)


if __name__ == "__main__":
    unittest.main()
