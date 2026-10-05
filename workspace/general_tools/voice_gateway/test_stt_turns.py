# @nova: Verify natural-pause and in-flight recognition continuation stay one bounded gated conversational turn without audio hardware.
import asyncio
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import GatewayConfig
import stt


class TurnEndpointingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.stream, self.calls, self.states, self.diagnostics = {}, [], [], []
        self.entered, self.release = threading.Event(), threading.Event()
        self.block_first = False
        self.opened = True
        self.frame_count = 0
        outer = self
        class Input:
            def __init__(self, **kw): outer.stream.update(kw)
            def __enter__(self): return self
            def __exit__(self, *args): return False
        def vad(frame):
            self.frame_count += 1
            return float(np.max(frame) > .1)
        def decode(audio):
            self.calls.append(audio.copy())
            if self.block_first and len(self.calls) == 1:
                self.entered.set()
                if not self.release.wait(3):
                    raise RuntimeError('fixture decoder release timed out')
            first = bool(np.any(audio == np.float32(16000 / 32768)))
            second = bool(np.any(audio == np.float32(24000 / 32768)))
            return 'first plus continuation' if first and second else 'first' if first else 'continuation'
        self.enterContext(patch.dict(sys.modules, {'sounddevice': types.SimpleNamespace(RawInputStream=Input)}))
        self.enterContext(patch.object(stt, '_load_silero', return_value=vad))
        self.enterContext(patch.object(stt, '_load_moonshine', return_value=decode))
        self.cfg = GatewayConfig(silence_ms=64, min_speech_ms=32, pre_roll_ms=0, speech_tail_ms=32)
        self.mic = stt.MoonshineSTT(self.cfg)
        self.mic.gate = lambda: self.opened
        self.mic.on_state = self.states.append
        self.mic.on_diagnostic = self.diagnostics.append
        self.iterator = None
        self.task = None

    async def asyncTearDown(self):
        self.release.set()
        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        if self.iterator is not None:
            await self.iterator.aclose()

    async def start(self):
        self.iterator = self.mic.utterances()
        self.task = asyncio.create_task(anext(self.iterator))
        await asyncio.sleep(0)

    def feed(self, values):
        for value in values:
            self.stream['callback'](np.full(512, value, 'int16').tobytes(), 512, None, None)

    async def until(self, predicate):
        for _ in range(200):
            if predicate(): return
            await asyncio.sleep(.005)
        self.fail('fixture condition did not complete')

    async def test_default_allows_two_second_natural_pause_without_partial_decode(self):
        self.assertEqual(GatewayConfig().silence_ms, 2000)
        self.cfg.silence_ms = GatewayConfig().silence_ms
        await self.start()
        self.feed([16000] * 6 + [0] * 62)  # 1.984s pause is still the same turn
        await self.until(lambda: self.frame_count == 68)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.task.done())
        self.assertEqual(self.states[-1], 'finishing_turn')
        self.feed([24000] * 6 + [0] * 63)
        self.assertEqual(await asyncio.wait_for(self.task, 1), 'first plus continuation')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(self.calls[0]), (6 + 62 + 6 + 1) * 512)

    async def test_continuation_captured_during_decode_is_joined_before_any_yield(self):
        self.block_first = True
        await self.start()
        self.feed([16000] * 6 + [0] * 2)
        await self.until(self.entered.is_set)
        self.feed([24000] * 6 + [0] * 2)
        await self.until(lambda: self.frame_count == 16)
        self.assertFalse(self.task.done())
        self.assertEqual(len(self.calls), 1, 'decoder ran concurrently')
        self.release.set()
        self.assertEqual(await asyncio.wait_for(self.task, 1), 'first plus continuation')
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(self.calls[1]), (6 + 2 + 6 + 1) * 512)
        self.assertEqual(self.states, ['hearing', 'finishing_turn', 'transcribing',
                                     'hearing', 'finishing_turn', 'transcribing', 'listening'])

    async def test_finished_old_decode_waits_for_continuation_to_end(self):
        self.block_first = True
        await self.start()
        self.feed([16000] * 6 + [0] * 2)
        await self.until(self.entered.is_set)
        self.feed([24000] * 6)
        await self.until(lambda: self.frame_count == 14)
        self.release.set()
        await asyncio.sleep(.05)
        self.assertFalse(self.task.done())
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.states[-1], 'hearing')
        self.feed([0] * 2)
        self.assertEqual(await asyncio.wait_for(self.task, 1), 'first plus continuation')

    async def test_silence_during_decode_does_not_trigger_duplicate_recognition(self):
        self.block_first = True
        await self.start()
        self.feed([16000] * 6 + [0] * 2)
        await self.until(self.entered.is_set)
        self.feed([0] * 150)  # represents another 4.8s while CPU recognition is busy
        await self.until(lambda: self.frame_count == 158)
        self.release.set()
        self.assertEqual(await asyncio.wait_for(self.task, 1), 'first')
        self.assertEqual(len(self.calls), 1)

    async def test_gate_invalidates_whole_combined_turn_and_preserves_only_fresh_audio(self):
        self.block_first = True
        await self.start()
        self.feed([16000] * 6 + [0] * 2)
        await self.until(self.entered.is_set)
        self.feed([16000] * 6)
        await self.until(lambda: self.frame_count == 14)
        self.opened = False
        self.feed([16000])  # capture generation advances; no echo enters queue
        self.opened = True
        self.feed([24000] * 6 + [0] * 2)
        await self.until(lambda: self.frame_count == 22)
        self.release.set()
        self.assertEqual(await asyncio.wait_for(self.task, 1), 'continuation')
        self.assertEqual(len(self.calls), 2)
        self.assertFalse(np.any(self.calls[1] == np.float32(16000 / 32768)))

    async def test_observed_mute_between_callbacks_invalidates_old_decode_after_reopen(self):
        self.block_first = True
        await self.start()
        self.feed([16000] * 6 + [0] * 2)
        await self.until(self.entered.is_set)
        self.opened = False
        await self.until(lambda: self.states[-1] == 'listening')
        # No callback occurred while muted. Fresh speech has the same voiced-frame count,
        # so the old result must be distinguished by generation, not just its revision.
        self.opened = True
        self.feed([24000] * 6)
        await self.until(lambda: self.frame_count == 14)
        self.release.set()
        await asyncio.sleep(.05)
        self.assertFalse(self.task.done())
        self.feed([0] * 2)
        self.assertEqual(await asyncio.wait_for(self.task, 1), 'continuation')
        self.assertEqual(len(self.calls), 2)

    async def test_hard_sixty_second_boundary_preserves_next_turn(self):
        self.block_first = True
        await self.start()
        self.feed([16000] * 1875)
        await self.until(self.entered.is_set)
        self.assertEqual(len(self.calls[0]), 60 * 16000)
        self.feed([24000] * 6 + [0] * 2)
        self.release.set()
        self.assertEqual(await asyncio.wait_for(self.task, 1), 'first')
        self.task = asyncio.create_task(anext(self.iterator))
        self.assertEqual(await asyncio.wait_for(self.task, 1), 'continuation')
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(any('60-second turn limit' in item for item in self.diagnostics))

    async def test_overflow_discards_incomplete_capture_instead_of_publishing_fragment(self):
        await self.start()
        self.feed([16000] * 1900)  # callbacks queued before the consumer runs
        await self.until(lambda: bool(self.diagnostics))
        self.assertTrue(any('overflow' in item for item in self.diagnostics))
        self.assertEqual(self.calls, [])
        self.assertFalse(self.task.done())
        self.feed([24000] * 6 + [0] * 2)
        self.assertEqual(await asyncio.wait_for(self.task, 1), 'continuation')

    async def test_stop_during_recognition_never_emits_late_transcript(self):
        self.block_first = True
        await self.start()
        self.feed([16000] * 6 + [0] * 2)
        await self.until(self.entered.is_set)
        self.task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await self.task
        self.release.set()
        await self.iterator.aclose()
        self.assertEqual(len(self.calls), 1)


if __name__ == '__main__':
    unittest.main()
