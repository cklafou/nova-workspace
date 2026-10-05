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


if __name__ == "__main__":
    unittest.main()
