# @nova: Test voice identity, delivery, interruption and truthful playback using isolated fake backends.
# Last updated: 2026-10-06 03:07:09
#   never spoken, request matching, interruption, audit passthrough and the server event contract.
"""Run: python general_tools/voice_gateway/test_voice_flow.py   (no Nova, no audio, no network)"""
from __future__ import annotations

import asyncio
import contextlib
import io
import tempfile
import types
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))          # general_tools, for the server's own event builder

from body import MemoryBody                    # noqa: E402
from config import GatewayConfig               # noqa: E402
from nova_link import parse_event              # noqa: E402
from speech import SpeechPlayer, Utterance, speech_text   # noqa: E402
from turns import VoiceSession                 # noqa: E402
import stt
import tts as tts_module

try:
    from nova_chat.response_events import ResponseEvents
except Exception:                              # pragma: no cover - older server tree
    ResponseEvents = None


class FakeTTS:
    name = "fake"

    def __init__(self, block=False):
        self.spoken, self.stops = [], 0
        self._go = threading.Event()
        if not block:
            self._go.set()

    def speak(self, text):
        self.spoken.append(text)
        self._go.wait(timeout=5)

    def stop(self):
        self.stops += 1
        self._go.set()

    def close(self):
        pass


def frame(kind, **fields):
    base = {"author": "Nova", "id": "m1", "run_id": "run1", "reply_to": "u1", "request_id": "req1",
            "register": "voice"}
    return {**base, "type": kind, **fields}


def end(content="Hi Cole. The log says the API was down.", delivery="delivered", audit=None, **fields):
    audit = {"status": "PASS", "reason": "", "source": "inline"} if audit is None else audit
    return frame("message_end", content=content, delivery=delivery, audit=audit, **fields)


def ack(request_id="req1", server_id="u1"):
    return {"type": "user_message", "author": "Cole", "id": server_id, "request_id": request_id, "content": "…"}


def turn(request_id="req1", server_id="u1", message_id="m1", run_id="run1", **end_fields):
    """The three frames of one correctly identified reply."""
    ids = dict(request_id=request_id, reply_to=server_id, id=message_id, run_id=run_id)
    return [ack(request_id, server_id), frame("message_start", **ids), end(**{**ids, **end_fields})]


class GenTTS:
    """Synthesis then playback, like Chatterbox: waits in 'generate' until released."""
    name = "gen"

    def __init__(self):
        self.generated, self.played, self.stops = [], [], 0
        self.release = __import__("threading").Event()

    def speak(self, text, should_stop=None, on_playback=None):
        self.generated.append(text)
        self.release.wait(timeout=5)
        if should_stop is not None and should_stop():
            return
        if on_playback is not None:
            on_playback()
        if text == "boom.":
            raise RuntimeError("synth failed")
        self.played.append(text)

    def stop(self):
        self.stops += 1

    def close(self):
        pass


class Flow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.cfg = GatewayConfig()
        self.body = MemoryBody()
        self.tts = FakeTTS()
        self.player = SpeechPlayer(self.tts, self.body, tail_s=0).start()
        self.session = VoiceSession(self.cfg, self.player, self.body, log=lambda *_: None)

    async def asyncTearDown(self):
        await self.player.close()

    async def feed(self, *frames):
        for f in frames:
            ev = parse_event(f)
            if ev is not None:
                self.session.handle(ev)
        await self.player.drain()

    async def test_speaks_my_delivered_reply_with_its_audit(self):
        self.session.sent("req1", "is vtube studio up?")
        await self.feed(*turn(audit={"status": "INCOMPLETE", "reason": "frame omitted", "source": "inline"}))
        self.assertEqual(self.tts.spoken, ["Hi Cole.", "The log says the API was down."])
        captions = self.body.of("caption")
        self.assertEqual([c["unit"] for c in captions], [0, 1])
        self.assertTrue(all(c["message_id"] == "m1" and c["request_id"] == "req1" and c["run_id"] == "run1"
                            for c in captions))
        self.assertEqual(captions[0]["audit"]["status"], "INCOMPLETE")
        self.assertEqual(self.session.pending, {})
        self.assertEqual(self.body.of("state")[-1]["state"], "idle")

    async def test_never_speaks_non_delivered_ends(self):
        for delivery in ("error", "empty", "suppressed", "cancelled"):
            self.session.sent("req1", "hello")
            await self.feed(frame("message_start"), end(content="⚠ provider failed: 500", delivery=delivery))
            self.assertEqual(self.tts.spoken, [], delivery)
            self.assertNotIn("req1", self.session.pending, delivery)

    async def test_unsolicited_never_spoken_in_any_scope(self):
        for scope in ("mine", "replies"):
            self.cfg.speak_scope = scope
            await self.feed(end(content="FOR COLE: I finished the notes.", delivery="unsolicited",
                                request_id=None, reply_to=None, id=f"m9_{scope}_cole"))
        self.assertEqual(self.tts.spoken, [])

    async def test_replies_scope_still_needs_identity(self):
        self.cfg.speak_scope = "replies"
        await self.feed(end(request_id=None, reply_to=None, id="m3"))
        self.assertEqual(self.tts.spoken, [])

    async def test_old_schema_end_is_silent_with_one_diagnostic(self):
        self.session.sent("req1", "hello")
        old = {"type": "message_end", "author": "Nova", "id": "m1", "content": "⚠ Nova client error: boom"}
        await self.feed(old, old)
        self.assertEqual(self.tts.spoken, [])
        self.assertEqual(len([d for d in self.body.of("diagnostic") if "old server" in d["message"]]), 1)

    async def test_reply_to_someone_else_follows_scope(self):
        await self.feed(end(request_id=None, reply_to="typed1"))
        self.assertEqual(self.tts.spoken, [])
        self.cfg.speak_scope = "replies"
        await self.feed(end(request_id=None, reply_to="typed2", id="m2"))
        self.assertEqual(len(self.tts.spoken), 2)

    async def test_pass_only_gate_speaks_only_explicit_pass(self):
        self.cfg.audit_gate = "pass_only"
        for i, status in enumerate(("CONCERN", "NOT_RUN", "INCOMPLETE", "ERROR")):
            self.session.sent(f"r{i}", "hello")
            await self.feed(*turn(f"r{i}", f"u{i}", f"m{i}", f"run{i}",
                                  audit={"status": status, "reason": "", "source": "inline"}))
        self.assertEqual(self.tts.spoken, [])
        self.assertIn("pass_only", self.body.of("message")[-1]["why"])
        self.session.sent("r9", "hello")
        await self.feed(*turn("r9", "u9", "m9", "run9"))
        self.assertEqual(len(self.tts.spoken), 2)

    async def test_identity_must_match_ack_and_start(self):
        cases = {
            "no ack": [frame("message_start"), end()],
            "reply_to differs": [ack(), frame("message_start"), end(reply_to="u_other")],
            "unknown message": [ack(), frame("message_start"), end(id="m_other")],
            "run_id differs": [ack(), frame("message_start"), end(run_id="run_other")],
            "no request_id": [ack(), frame("message_start"), end(request_id=None)],
            "start with wrong reply_to": [ack(), frame("message_start", reply_to="u_other"), end()],
        }
        for name, frames in cases.items():
            self.session.sent("req1", "hello")
            await self.feed(*frames)
            self.assertEqual(self.tts.spoken, [], name)
            self.session.pending.clear()

    async def test_late_end_after_new_request_or_stop_is_silent(self):
        self.session.sent("req1", "first question")
        await self.feed(ack("req1", "u1"), frame("message_start"))
        self.session.sent("req2", "never mind, second question")
        await self.feed(end())                                   # req1's late final
        self.assertEqual(self.tts.spoken, [])
        self.assertIn("interrupted (new_request)", self.body.of("message")[-1]["why"])
        await self.feed(ack("req2", "u2"), frame("message_start", request_id="req2", reply_to="u2", id="m2",
                                                  run_id="run2"))
        self.session.handle(parse_event({"type": "stopped"}))
        await self.feed(end(request_id="req2", reply_to="u2", id="m2", run_id="run2"))
        self.assertEqual(self.tts.spoken, [])
        self.assertEqual(self.session.pending, {})

    async def test_cut_during_synthesis_never_plays(self):
        tts = GenTTS()
        player = SpeechPlayer(tts, self.body, tail_s=0).start()
        self.addAsyncCleanup(player.close)
        session = VoiceSession(self.cfg, player, self.body, log=lambda *_: None)
        session.sent("req1", "tell me")
        for f in turn(content="First sentence here. Second sentence here."):
            session.handle(parse_event(f))
        await asyncio.sleep(0.05)                                # synthesizing unit 0
        session.cancel("voice_stopped")
        tts.release.set()
        await player.drain()
        self.assertEqual(tts.generated, ["First sentence here."])
        self.assertEqual(tts.played, [])
        self.assertEqual([e["outcome"] for e in self.body.of("speech") if e["phase"] == "end"], ["skipped"])
        self.assertEqual(self.body.of("caption"), [])         # nothing was heard, so nothing captioned

    async def test_trace_separates_eligible_queued_and_played(self):
        tts = GenTTS()
        tts.release.set()
        player = SpeechPlayer(tts, self.body, tail_s=0).start()
        self.addAsyncCleanup(player.close)
        session = VoiceSession(self.cfg, player, self.body, log=lambda *_: None)
        session.sent("r1", "code please")
        for f in turn("r1", "u1", "m1", "run1", content="```python\nprint(1)\n```"):
            session.handle(parse_event(f))
        message = self.body.of("message")[-1]
        self.assertEqual((message["eligible"], message["queued_units"]), (True, 0))
        self.assertIn("nothing speakable", message["why"])
        session.sent("r2", "talk")
        for f in turn("r2", "u2", "m2", "run2", content="Hello there, Cole. boom."):
            session.handle(parse_event(f))
        await player.drain()
        ends = [e["outcome"] for e in self.body.of("speech") if e["phase"] == "end"]
        self.assertEqual(ends, ["played", "error"])
        self.assertEqual([c["clock"] for c in self.body.of("caption")], ["playback", "playback"])
        self.assertNotIn("spoken", message)

    async def test_missing_audit_is_not_run_never_pass(self):
        ev = parse_event({"type": "message_end", "author": "Nova", "id": "m1", "content": "x",
                          "delivery": "delivered"})
        self.assertEqual(ev.audit["status"], "NOT_RUN")

    async def test_request_end_and_error_clear_pending_silently(self):
        self.session.sent("req1", "one")
        await self.feed({"type": "request_end", "request_id": "req1", "reply_to": "u1", "register": "voice",
                         "delivery": "superseded"})
        self.assertEqual(self.session.pending, {})
        self.session.sent("req2", "two")
        await self.feed(ack("req2", "u2"),
                        frame("message_start", request_id="req2", reply_to="u2", id="m2", run_id="run2"),
                        frame("error", request_id="req2", reply_to="u2", id="m2", run_id="run2",
                              message="provider timeout"))
        self.assertEqual(self.session.pending, {})
        self.assertEqual(self.tts.spoken, [])

    async def test_timeout_sweep_never_leaves_it_thinking(self):
        now = [1000.0]
        session = VoiceSession(self.cfg, self.player, self.body, clock=lambda: now[0], log=lambda *_: None)
        session.sent("req1", "hello")
        now[0] += self.cfg.request_timeout_s + 1
        self.assertEqual(session.sweep(), ["req1"])
        self.assertEqual(self.body.of("state")[-1]["state"], "idle")

    async def test_slow_acknowledged_reply_keeps_correlation_and_is_spoken(self):
        now = [1000.0]
        session = VoiceSession(self.cfg, self.player, self.body, clock=lambda: now[0])
        session.sent("req1", "hello")
        session.handle(parse_event(ack()))
        session.handle(parse_event(frame("message_start")))
        now[0] += 313
        self.assertEqual(session.sweep(), [])
        self.assertTrue(session.pending["req1"].delayed)
        session.sweep()
        self.assertEqual(len([d for d in self.body.of("diagnostic") if "taking longer" in d["message"]]), 1)
        session.handle(parse_event(end(content="Hi!")))
        await self.player.drain()
        self.assertEqual(self.tts.spoken, ["Hi!"])
        self.assertEqual(self.body.of("message")[-1]["elapsed_s"], 313)
        self.assertEqual(session.pending, {})

    async def test_delayed_reply_never_speaks_after_stop_or_new_request(self):
        for reason in ("stop", "new"):
            with self.subTest(reason=reason):
                now = [1000.0]
                session = VoiceSession(self.cfg, self.player, self.body, clock=lambda: now[0])
                session.sent("req1", "hello")
                session.handle(parse_event(ack()))
                session.handle(parse_event(frame("message_start")))
                now[0] += 313
                session.sweep()
                if reason == "stop":
                    session.handle(parse_event({"type": "stopped"}))
                else:
                    session.sent("req2", "different question")
                session.handle(parse_event(end()))
                await self.player.drain()
                self.assertEqual(self.tts.spoken, [])
                self.assertIn("interrupted", self.body.of("message")[-1]["why"])
                self.assertTrue(any("not spoken" in d["message"] for d in self.body.of("diagnostic")))

    async def test_old_scoped_stop_ack_never_retires_newer_request(self):
        self.session.sent("req1", "first")
        await self.feed(ack(), frame("message_start"))
        self.session.sent("req2", "second")
        await self.feed({'type': 'stopped', 'request_id': 'req1', 'matched': True})
        self.assertTrue(self.session.pending['req2'].eligible)
        self.assertNotIn('req1', self.session.pending)
        await self.feed(*turn('req2', 'u2', 'm2', 'run2', content='Current reply.'))
        self.assertEqual(self.tts.spoken, ['Current reply.'])

    async def test_scoped_stop_tombstone_blocks_late_reply_in_replies_scope(self):
        self.cfg.speak_scope = 'replies'
        self.session.sent('req1', 'first')
        await self.feed(ack(), frame('message_start'), {'type': 'stopped', 'request_id': 'req1', 'matched': True})
        await self.feed(end())
        self.assertEqual(self.tts.spoken, [])

    async def test_explicit_voice_cancel_blocks_reply_before_worker_teardown(self):
        self.session.sent("req1", "hello")
        await self.feed(ack(), frame("message_start"))
        self.session.cancel()
        await self.feed(end(content="Late reply"))
        self.assertEqual(self.tts.spoken, [])
        self.assertTrue(self.session.output_muted)
        self.assertIn("muted", self.body.of("message")[-1]["why"])

    async def test_accepted_current_request_is_only_request_retained_after_timeout(self):
        now = [1000.0]
        session = VoiceSession(self.cfg, self.player, self.body, clock=lambda: now[0])
        for i in range(20):
            session.sent(f"r{i}", "question")
            session.handle(parse_event(ack(f"r{i}", f"u{i}")))
        now[0] += 301
        self.assertEqual(len(session.sweep()), 19)
        self.assertEqual(list(session.pending), ["r19"])

    async def test_new_input_preserves_delivered_speech_but_explicit_stop_flushes(self):
        tts = FakeTTS(block=True)
        player = SpeechPlayer(tts, self.body, tail_s=0).start()
        self.addAsyncCleanup(player.close)
        session = VoiceSession(self.cfg, player, self.body, log=lambda *_: None)
        session.sent("req1", "tell me a story")
        for f in turn(content="One. Two is here. Three is last."):
            session.handle(parse_event(f))
        await asyncio.sleep(0.05)                       # first unit is now speaking
        self.assertTrue(player.active())
        session.sent("req2", "additional detail")
        self.assertEqual(tts.stops, 0)                  # input is not an implicit Stop
        self.assertTrue(player.active())
        session.handle(parse_event({"type": "stopped"}))
        await player.drain()
        self.assertEqual(tts.spoken, ["One. Two is here."])   # "Three is last." was dropped
        self.assertEqual(tts.stops, 1)
        cut = self.body.of("interrupt")[-1]
        self.assertEqual((cut["reason"], cut["cut_message_id"]), ("stopped", "m1"))
        session.handle(parse_event({"type": "stopped"}))   # nothing playing: no further cut event

    async def test_half_duplex_gate_follows_playback(self):
        tts = FakeTTS(block=True)
        player = SpeechPlayer(tts, self.body, tail_s=0.2).start()
        self.addAsyncCleanup(player.close)
        session = VoiceSession(self.cfg, player, self.body, log=lambda *_: None)
        session.sent("req1", "hi")
        for f in turn(content="Hello there, Cole."):
            session.handle(parse_event(f))
        await asyncio.sleep(0.05)
        self.assertTrue(player.busy())
        tts.stop()
        await player.drain()
        self.assertTrue(player.busy())                  # inside the tail
        await asyncio.sleep(0.25)
        self.assertFalse(player.busy())

    async def test_stream_setting_never_speaks_tokens(self):
        cfg = GatewayConfig()
        cfg.speak_from = "stream"
        body = MemoryBody()
        session = VoiceSession(cfg, self.player, body, log=lambda *_: None)
        self.assertIn("does not permit token speech", body.of("diagnostic")[0]["message"])
        session.sent("req1", "hi")
        session.handle(parse_event(frame("token", token="Pre-audit words.")) or parse_event(frame("message_start")))
        await self.player.drain()
        self.assertEqual(self.tts.spoken, [])

    @unittest.skipIf(ResponseEvents is None, "server response_events not present")
    async def test_contract_with_the_servers_own_event_builder(self):
        events = ResponseEvents(author="Nova", message_id="m7", run_id="run7", reply_to="u7",
                                request_id="req7", register="voice")
        await events.on_audit({"status": "PASS", "reason": "", "source": "inline"})
        self.session.sent("req7", "hi")
        await self.feed(ack("req7", "u7"), events.event("message_start"),
                        events.event("message_end", content="All set. Talk soon.", delivery="delivered"))
        self.assertEqual(self.tts.spoken, ["All set.", "Talk soon."])
        self.assertEqual(self.body.of("caption")[0]["audit"]["source"], "inline")
        failing = ResponseEvents(author="Nova", message_id="m8", run_id="run8", reply_to="u8",
                                 request_id="req8", register="voice")
        self.session.sent("req8", "again")
        await self.feed(failing.event("message_end", content="⚠ boom", delivery="error"))
        self.assertEqual(self.tts.spoken, ["All set.", "Talk soon."])


class FakeFrame:
    def __init__(self, value):
        self.value = value

    def astype(self, *_):
        return self

    def __truediv__(self, *_):
        return self


def fake_numpy():
    module = types.ModuleType('numpy')
    module.frombuffer = lambda chunk, **_: FakeFrame(chunk[0])
    module.concatenate = lambda frames: [frame.value for frame in frames]
    module.zeros = lambda *_: []
    module.asarray = lambda value, **_: value
    return module


class FakeAudio:
    def __init__(self):
        self.events = []
        self.callback = None

    def play(self, *args, **kwargs):
        self.events.append('play')

    def stop(self):
        self.events.append('stop')

    def wait(self):
        self.events.append('wait')

    def RawInputStream(self, **kwargs):
        self.callback = kwargs['callback']
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def feed(self, value):
        self.callback(bytes([value]), 1, None, None)


@contextlib.contextmanager
def fake_chatterbox(model=None, audio=None, numpy=None):
    """Use the actual constructor with stub imports; never initialize real GPU/audio libraries."""
    audio = audio or FakeAudio()
    model = model or types.SimpleNamespace(generate=lambda *a, **kw: [1, 2])
    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    cb = types.ModuleType("chatterbox.tts")
    cb.ChatterboxTTS = types.SimpleNamespace(from_pretrained=lambda **kw: model)
    modules = {"numpy": numpy or fake_numpy(), "sounddevice": audio, "torch": torch,
               "chatterbox": types.ModuleType("chatterbox"), "chatterbox.tts": cb}
    with patch.dict(sys.modules, modules):
        yield tts_module.ChatterboxTTS(GatewayConfig()), audio


class CaptureGate(unittest.IsolatedAsyncioTestCase):
    async def test_closed_gate_frames_do_not_reappear_after_transcription(self):
        entered, release = threading.Event(), threading.Event()
        recorded = []
        gate_open = [True]
        audio = FakeAudio()

        def transcribe(samples):
            recorded.append(samples)
            if len(recorded) == 1:
                entered.set()
                if not release.wait(2):
                    raise RuntimeError('fake transcription release timed out')
                return 'human utterance'
            return 'Nova echo incorrectly treated as human'

        cfg = GatewayConfig()
        cfg.silence_ms = 30
        cfg.min_speech_ms = 32
        cfg.pre_roll_ms = 0
        cfg.vad_backend = 'none'
        with patch.dict(sys.modules, {'numpy': fake_numpy(), 'sounddevice': audio}), \
             patch.object(stt, '_load_moonshine', return_value=transcribe):
            microphone = stt.MoonshineSTT(cfg)
            microphone.gate = lambda: gate_open[0]
            microphone._is_voiced = lambda frame, continuing=False: frame.value > 0
            utterances = microphone.utterances()
            first = asyncio.create_task(anext(utterances))
            try:
                await asyncio.sleep(0)
                audio.feed(1)
                audio.feed(0)
                for _ in range(100):
                    if entered.is_set():
                        break
                    await asyncio.sleep(0.005)
                self.assertTrue(entered.is_set(), 'first utterance never reached transcription')
                gate_open[0] = False
                audio.feed(2)  # captured while Nova is speaking
                audio.feed(0)
                await asyncio.sleep(0)  # callbacks enqueue before the gate reopens
                gate_open[0] = True
                release.set()
                await asyncio.sleep(.1)
                self.assertFalse(first.done(), 'in-flight transcription survived the capture gate transition')
                self.assertEqual(recorded, [[1, 0]], 'Nova audio reached the transcriber')
            finally:
                release.set()
                if not first.done():
                    first.cancel()
                    await asyncio.gather(first, return_exceptions=True)
                await utterances.aclose()
                microphone.close()


class BackendCancellation(unittest.TestCase):
    def test_stop_during_synthesis_works_without_caller_hook(self):
        entered, release = threading.Event(), threading.Event()
        errors = []

        def generate(*args, **kwargs):
            entered.set()
            if not release.wait(2):
                raise RuntimeError("fake synthesis release timed out")
            return [1, 2]

        model = types.SimpleNamespace(generate=generate)
        with fake_chatterbox(model=model) as (backend, audio):
            def speak():
                try:
                    backend.speak("Cancelled synthesis")
                except BaseException as error:
                    errors.append(error)
            worker = threading.Thread(target=speak, daemon=True)
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                backend.stop()
            finally:
                release.set()
                worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
            self.assertNotIn("play", audio.events)
            # A completed stop must not permanently mute later intentional speech.
            backend.speak("A fresh utterance")
            self.assertEqual(audio.events.count("play"), 1)

    def test_stop_after_synthesis_before_play_is_checked_again(self):
        np = fake_numpy()
        with fake_chatterbox(numpy=np) as (backend, audio):
            def convert(value, **kwargs):
                backend.stop()  # cancellation after the synthesis-time check
                return value
            np.asarray = convert
            result = backend.speak("Do not start")
            self.assertEqual(result["outcome"], "skipped")
            self.assertNotIn("play", audio.events)

    def test_play_start_and_stop_are_serialized(self):
        entered, release, stop_called = threading.Event(), threading.Event(), threading.Event()
        errors = []

        class SlowStart(FakeAudio):
            def play(self, *args, **kwargs):
                self.events.append("play_enter")
                entered.set()
                if not release.wait(2):
                    raise RuntimeError("fake play start timed out")
                self.events.append("play_started")

        with fake_chatterbox(audio=SlowStart()) as (backend, audio):
            def speak():
                try:
                    backend.speak("Starting now")
                except BaseException as error:
                    errors.append(error)
            def stop():
                stop_called.set()
                backend.stop()
            speaker = threading.Thread(target=speak, daemon=True)
            stopper = threading.Thread(target=stop, daemon=True)
            speaker.start()
            try:
                self.assertTrue(entered.wait(2))
                stopper.start()
                self.assertTrue(stop_called.wait(2))
                self.assertNotIn("stop", audio.events)  # stop waits for the in-progress start
            finally:
                release.set()
                speaker.join(2)
                if stopper.ident is not None:
                    stopper.join(2)
            self.assertFalse(speaker.is_alive() or stopper.is_alive())
            self.assertEqual(errors, [])
            self.assertLess(audio.events.index("play_started"), audio.events.index("stop"))

    def test_chatterbox_play_failure_is_not_a_playback_start(self):
        class BrokenAudio(FakeAudio):
            def play(self, *args, **kwargs):
                raise RuntimeError("fake device rejected playback")
        callbacks = []
        with fake_chatterbox(audio=BrokenAudio()) as (backend, _):
            with self.assertRaisesRegex(RuntimeError, "rejected playback"):
                backend.speak("No audio", on_playback=lambda: callbacks.append(True))
        self.assertEqual(callbacks, [])

    def test_llama_synthesis_failure_propagates_without_playback(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "fake-exe").touch()
            (root / "fake-model").touch()
            cfg = types.SimpleNamespace(resolve=lambda rel: root / rel, llamacpp_tts_exe="fake-exe",
                                        llamacpp_tts_model="fake-model", llamacpp_tts_vocoder="")
            backend = tts_module.LlamaCppTTS(cfg)
            proc = types.SimpleNamespace(wait=lambda **kw: 4, poll=lambda: 4)
            callbacks = []
            with patch.object(tts_module.subprocess, "Popen", return_value=proc):
                with self.assertRaisesRegex(RuntimeError, "llama-tts exited 4"):
                    backend.speak("Failure", on_playback=lambda: callbacks.append(True))
            self.assertEqual(callbacks, [])
            self.assertIsNone(backend._proc)

    def test_process_fallback_failure_propagates_and_success_has_no_audio_clock(self):
        backend = tts_module._PlaybackControl()
        callbacks = []
        for code in (3, 0):
            proc = types.SimpleNamespace(wait=lambda code=code, **kw: code, poll=lambda: code)
            with patch.dict(sys.modules, {"sounddevice": None}), \
                 patch.object(tts_module.shutil, "which", return_value="fake-powershell"), \
                 patch.object(tts_module.subprocess, "Popen", return_value=proc) as launch:
                if code:
                    with self.assertRaisesRegex(RuntimeError, "playback process exited 3"):
                        tts_module._play_wav(Path("fake.wav"), backend, backend._begin(),
                                             on_playback=lambda: callbacks.append(True))
                else:
                    result = tts_module._play_wav(Path("fake.wav"), backend, backend._begin(),
                                                  on_playback=lambda: callbacks.append(True))
                    self.assertEqual(result, {"outcome": "completed", "clock": "process"})
                self.assertIn("Hidden", launch.call_args.args[0])
        self.assertEqual(callbacks, [])


class PlayerLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_stops_active_flushes_queued_and_rejects_more_work(self):
        tts = FakeTTS(block=True)
        body = MemoryBody()
        player = SpeechPlayer(tts, body, tail_s=0).start()
        player.say(Utterance("Active unit", "m1"))
        player.say(Utterance("Must never run", "m1", index=1))
        try:
            for _ in range(100):
                if tts.spoken:
                    break
                await asyncio.sleep(0.005)
            self.assertEqual(tts.spoken, ["Active unit"])
            await player.close()
            await asyncio.wait_for(player.drain(), 0.2)
            await player.close()  # idempotent
            self.assertEqual(tts.stops, 1)
            self.assertTrue(tts._go.is_set())
            self.assertFalse(player.active())
            self.assertEqual(tts.spoken, ["Active unit"])
            self.assertEqual(body.of("interrupt")[-1]["reason"], "close")
            self.assertEqual(body.of("speech")[-1]["outcome"], "cut")
            with self.assertRaisesRegex(RuntimeError, "closed"):
                player.say(Utterance("Late unit"))
        finally:
            tts._go.set()
            await player.close()

    async def test_close_invalidates_synthesis_that_finishes_later(self):
        tts = GenTTS()
        body = MemoryBody()
        player = SpeechPlayer(tts, body, tail_s=0).start()
        player.say(Utterance("Synthesis still running"))
        try:
            for _ in range(100):
                if tts.generated:
                    break
                await asyncio.sleep(0.005)
            self.assertEqual(tts.generated, ["Synthesis still running"])
            await player.close()
            self.assertEqual(tts.stops, 1)
            self.assertEqual(body.of("speech")[-1]["outcome"], "skipped")
            tts.release.set()
            await asyncio.to_thread(lambda: None)  # yield to the synthesis worker
            await asyncio.sleep(0.02)
            self.assertEqual(tts.played, [])
            self.assertEqual(body.of("caption"), [])
        finally:
            tts.release.set()
            await player.close()

    async def test_null_tts_never_reports_audio_playback(self):
        body = MemoryBody()
        player = SpeechPlayer(tts_module.NullTTS(), body, tail_s=0).start()
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                player.say(Utterance("Logging only"))
                await player.drain()
            self.assertEqual(body.of("caption"), [])
            self.assertEqual([e["phase"] for e in body.of("speech")], ["requested", "end"])
            self.assertEqual(body.of("speech")[-1]["outcome"], "no_audio")
        finally:
            await player.close()

    async def test_backend_playback_failure_reports_error_not_played(self):
        class BrokenAudio(FakeAudio):
            def wait(self):
                raise RuntimeError("fake playback failed after starting")
        body = MemoryBody()
        with fake_chatterbox(audio=BrokenAudio()) as (backend, _):
            player = SpeechPlayer(backend, body, tail_s=0).start()
            try:
                player.say(Utterance("Failure after submission"))
                await player.drain()
                self.assertEqual(body.of("speech")[-1]["outcome"], "error")
                self.assertIn("fake playback failed", body.of("diagnostic")[-1]["message"])
            finally:
                await player.close()

    async def test_fallback_completion_does_not_claim_an_audio_clock(self):
        class ProcessTTS:
            def speak(self, text, should_stop=None, on_playback=None):
                return {"outcome": "completed", "clock": "process"}
            def stop(self):
                pass
        body = MemoryBody()
        player = SpeechPlayer(ProcessTTS(), body, tail_s=0).start()
        try:
            player.say(Utterance("Process-only receipt"))
            await player.drain()
            self.assertEqual(body.of("caption"), [])
            self.assertEqual(body.of("speech")[-1]["outcome"], "completed")
            self.assertEqual(body.of("speech")[-1]["clock"], "process")
        finally:
            await player.close()


class ShutdownEdges(unittest.IsolatedAsyncioTestCase):
    """Claude's follow-up to the #78 review: honest outcomes and quiet late ends at shutdown."""

    def test_close_during_playback_reports_cut_not_played(self):
        stopped = threading.Event()

        class FakeSD:
            def play(self, samples, rate, **kw):
                pass

            def wait(self):
                stopped.wait(timeout=5)

            def stop(self):
                stopped.set()

        backend = tts_module._PlaybackControl()
        result = {}
        worker = threading.Thread(target=lambda: result.update(backend._play_array(
            FakeSD(), [0.0] * 10, 16000, backend._begin(), None, None)))
        worker.start()
        while backend._sd is None:                      # playback has started
            pass
        backend.close()
        worker.join(timeout=5)
        self.assertEqual(result, {"outcome": "cut"})

    async def test_late_end_after_player_close_is_a_diagnostic_not_a_crash(self):
        body = MemoryBody()
        player = SpeechPlayer(FakeTTS(), body, tail_s=0).start()
        session = VoiceSession(GatewayConfig(), player, body, log=lambda *_: None)
        session.sent("req1", "hi")
        for f in turn(content="Late but delivered.")[:2]:
            session.handle(parse_event(f))
        await player.close()
        session.handle(parse_event(turn(content="Late but delivered.")[2]))   # must not raise
        self.assertTrue(any("not queued" in d["message"] for d in body.of("diagnostic")))


class Text(unittest.TestCase):
    def test_speech_text_strips_scaffolding(self):
        raw = ("Let me look.\n\n[`computer_look` resulted in 130 bytes.]\n\n"
               "**Done.** The page at https://example.com/x?y=1 is open; see [the docs](https://e.com).\n"
               "```json\n{\"tool\": \"x\"}\n```\n- `paWE-GvDO1c` is the id\n# Heading\n| a | b |\n|---|---|\n| 1 | 2 |")
        out = speech_text(raw)
        for gone in ("resulted in", "**", "https://", "```", "{\"tool\"", "`", "# ", "|", "---"):
            self.assertNotIn(gone, out)
        for kept in ("Let me look.", "Done.", "a link", "the docs", "paWE-GvDO1c is the id", "Heading", "1, 2"):
            self.assertIn(kept, out)

    def test_inline_tool_marker_is_stripped_too(self):
        self.assertEqual(speech_text("Let me look. [`computer_look` resulted in 130 bytes.] Done."),
                         "Let me look. Done.")

    def test_snake_case_survives(self):
        self.assertEqual(speech_text("computer_look and computer_action ran."),
                         "computer_look and computer_action ran.")


if __name__ == "__main__":
    unittest.main()
