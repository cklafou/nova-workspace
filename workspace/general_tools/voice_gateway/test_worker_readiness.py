# Last updated: 2026-10-05 21:33:05
# @nova: Regress Windows control-pipe startup and local speech readiness/segmentation using isolated fixtures, without opening audio devices.
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from config import GatewayConfig
import control_worker as worker
import stt


class PipeProcess:
    def __init__(self, code):
        env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
        self.proc = subprocess.Popen([sys.executable, '-u', '-c', code], cwd=str(ROOT), env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.lines = queue.Queue()
        def reader():
            for line in iter(self.proc.stdout.readline, b''):
                self.lines.put(line.decode('utf-8', errors='replace').strip())
        self.reader = threading.Thread(target=reader, daemon=True)
        self.reader.start()

    def expect(self, prefix, timeout=10):
        deadline, received = time.monotonic() + timeout, []
        while time.monotonic() < deadline:
            try:
                line = self.lines.get(timeout=max(.01, deadline - time.monotonic()))
            except queue.Empty:
                break
            received.append(line)
            if line.startswith(prefix):
                return line
        raise AssertionError(f'Missing {prefix!r}; received {received!r}')

    def close(self):
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait(timeout=5)
        for stream in (self.proc.stdin, self.proc.stdout):
            if stream:
                stream.close()
        self.reader.join(timeout=1)


@unittest.skipUnless(sys.platform == 'win32', 'Windows anonymous pipe regression')
class ControlPipeTests(unittest.TestCase):
    @unittest.skipUnless(all(importlib.util.find_spec(m) for m in
                        ('numpy', 'sounddevice', 'onnxruntime', 'moonshine_onnx')), 'isolated voice dependencies')
    def test_native_imports_finish_while_stdin_remains_open_and_empty(self):
        child = PipeProcess("""
import asyncio
from control_worker import Control
async def main():
    control = Control(); control.listen()
    await asyncio.sleep(.1)
    import numpy, sounddevice, onnxruntime, moonshine_onnx
    print('IMPORTED', flush=True)
    await control.stop.wait()
asyncio.run(main())
""")
        try:
            child.expect('IMPORTED', timeout=10)
            self.assertFalse(child.proc.stdin.closed)
            child.proc.stdin.write(b'{"command":"stop"}\n'); child.proc.stdin.flush()
            self.assertEqual(child.proc.wait(timeout=3), 0)
        finally:
            child.close()

    def test_fragmented_unicode_lines_and_eof_preserve_protocol(self):
        child = PipeProcess("""
import json, sys
from control_worker import _control_lines
print('READY', flush=True)
for line in _control_lines(sys.stdin):
    print('LINE:' + json.dumps(json.loads(line), ensure_ascii=False), flush=True)
print('EOF', flush=True)
""")
        try:
            child.expect('READY')
            encoded = json.dumps({'text': 'Cole — 안녕'}, ensure_ascii=False).encode('utf-8')
            cut = encoded.index('안'.encode('utf-8')) + 1
            child.proc.stdin.write(encoded[:cut]); child.proc.stdin.flush()
            time.sleep(.05)
            child.proc.stdin.write(encoded[cut:] + b'\n{"command":"stop"}'); child.proc.stdin.flush()
            child.proc.stdin.close()
            self.assertEqual(json.loads(child.expect('LINE:')[5:]), {'text': 'Cole — 안녕'})
            self.assertEqual(json.loads(child.expect('LINE:')[5:]), {'command': 'stop'})
            child.expect('EOF')
            self.assertEqual(child.proc.wait(timeout=3), 0)
        finally:
            child.close()

    def test_malformed_line_does_not_swallow_later_stop(self):
        child = PipeProcess("""
import asyncio
from control_worker import Control
async def main():
    control = Control(); control.listen(); print('READY', flush=True)
    await control.stop.wait(); print('STOPPED', flush=True)
asyncio.run(main())
""")
        try:
            child.expect('READY')
            child.proc.stdin.write(b'not json\n{"command":"stop"}\n'); child.proc.stdin.flush()
            child.expect('STOPPED')
            self.assertEqual(child.proc.wait(timeout=3), 0)
        finally:
            child.close()


class ReadinessTests(unittest.TestCase):
    def test_probe_is_unavailable_when_assets_missing_without_loading_models(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(stt.sys, 'prefix', folder), \
             patch.object(worker, '_installed', return_value=True), \
             patch.object(worker.shutil, 'which', return_value='powershell'), \
             patch.object(worker.sys, 'platform', 'win32'):
            result = worker.probe(GatewayConfig(tts_backend='windows', stt_backend='moonshine'))
        self.assertFalse(result['available'])
        self.assertTrue(result['capabilities']['microphone_test'])
        self.assertIn('--assets-only', result['reason'])
        self.assertEqual(len(result['assets']['missing']), 3)

    def test_local_loader_never_falls_back_to_download_or_energy(self):
        model = Mock()
        fake = types.SimpleNamespace(MoonshineOnnxModel=model)
        with tempfile.TemporaryDirectory() as folder, patch.object(stt.sys, 'prefix', folder), \
             patch.dict(sys.modules, {'moonshine_onnx': fake}):
            with self.assertRaisesRegex(RuntimeError, 'assets missing'):
                stt._load_moonshine(GatewayConfig())
            with self.assertRaisesRegex(RuntimeError, 'Silero asset missing'):
                stt._load_silero(GatewayConfig())
        model.assert_not_called()

    def test_devices_excludes_rejected_rate_and_retains_real_ids(self):
        calls = []
        def check(**settings):
            calls.append(settings)
            if settings['device'] == 1:
                raise ValueError('invalid sample rate')
        fake = types.SimpleNamespace(default=types.SimpleNamespace(device=(0, 2)),
            query_devices=lambda: [dict(name=str(i), hostapi=0, max_input_channels=int(i < 2),
                                      max_output_channels=int(i > 0)) for i in range(3)],
            query_hostapis=lambda: [{'name': 'fixture'}], check_input_settings=check,
            check_output_settings=check)
        with patch.dict(sys.modules, {'sounddevice': fake}):
            result = worker.devices()
        self.assertEqual([d['id'] for d in result['inputs']], [0])
        self.assertEqual([d['id'] for d in result['outputs']], [2])
        self.assertEqual(len(result['excluded']), 2)
        self.assertTrue(all(c['samplerate'] == 16000 and c['channels'] == 1 for c in calls))


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'isolated voice numpy')
class SegmentationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import numpy as np
        self.np = np
        self.stream = {}
        outer = self
        class Input:
            def __init__(self, **kwargs): outer.stream.update(kwargs)
            def __enter__(self): return self
            def __exit__(self, *args): pass
        self.enterContext(patch.dict(sys.modules, {'sounddevice': types.SimpleNamespace(RawInputStream=Input)}))
        self.enterContext(patch.object(stt, '_load_silero', return_value=lambda frame: float(np.max(frame) > .1)))
        self.decode = Mock(return_value='recognized speech')
        self.enterContext(patch.object(stt, '_load_moonshine', return_value=self.decode))
        self.mic = stt.MoonshineSTT(GatewayConfig(silence_ms=96, pre_roll_ms=64, speech_tail_ms=32))
        self.diagnostics = []
        self.mic.on_diagnostic = self.diagnostics.append
        self.iterator = self.mic.utterances()
        self.task = asyncio.create_task(anext(self.iterator))
        await asyncio.sleep(0)

    async def asyncTearDown(self):
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)
        await self.iterator.aclose()

    def feed(self, values):
        for value in values:
            self.stream['callback'](self.np.full(512, value, 'int16').tobytes(), 512, None, None)

    async def test_noise_spike_is_rejected_and_speech_keeps_onset_trims_tail(self):
        self.feed([16000] + [0] * 3)  # 32ms click cannot become a request
        await asyncio.sleep(.05)
        self.decode.assert_not_called()
        self.assertFalse(self.task.done())
        self.feed([100, 200] + [16000] * 6 + [0] * 3)
        self.assertEqual(await asyncio.wait_for(self.task, 1), 'recognized speech')
        audio = self.decode.call_args.args[0]
        self.assertEqual(len(audio), 9 * 512)  # 2 onset + 6 voiced + 1 tail
        self.assertAlmostEqual(float(audio[0]), 100 / 32768)
        self.assertAlmostEqual(float(audio[512]), 200 / 32768)

    async def test_decode_failure_reports_diagnostic_and_next_utterance_works(self):
        self.decode.side_effect = [RuntimeError('fixture decoder failure'), 'second utterance']
        self.feed([16000] * 6 + [0] * 3)
        for _ in range(50):
            if self.diagnostics: break
            await asyncio.sleep(.01)
        self.assertEqual(len(self.diagnostics), 1)
        self.assertIn('listening continues', self.diagnostics[0])
        self.assertFalse(self.task.done())
        self.feed([16000] * 6 + [0] * 3)
        self.assertEqual(await asyncio.wait_for(self.task, 1), 'second utterance')
        self.assertEqual(self.decode.call_count, 2)

    async def test_gate_transition_clears_preroll_even_before_speech(self):
        opened = [True]
        self.mic.gate = lambda: opened[0]
        self.feed([2000, 2000])
        await asyncio.sleep(.01)
        opened[0] = False
        self.feed([16000])
        opened[0] = True
        self.feed([16000] * 6 + [0] * 3)
        await asyncio.wait_for(self.task, 1)
        self.assertEqual(len(self.decode.call_args.args[0]), 7 * 512)

    async def test_inflight_transcript_is_discarded_after_gate_generation_changes(self):
        entered, release = threading.Event(), threading.Event()
        opened = [True]
        self.mic.gate = lambda: opened[0]
        def decode(audio):
            if self.decode.call_count == 1:
                entered.set()
                if not release.wait(2):
                    raise RuntimeError('fixture decode release timed out')
                return 'stale transcript must not be sent'
            return 'fresh user speech'
        self.decode.side_effect = decode
        try:
            self.feed([16000] * 6 + [0] * 3)
            for _ in range(50):
                if entered.is_set(): break
                await asyncio.sleep(.01)
            self.assertTrue(entered.is_set())
            opened[0] = False
            self.feed([16000])  # capture callback invalidates the in-flight generation
            opened[0] = True
            release.set()
            await asyncio.sleep(.05)
            self.assertFalse(self.task.done(), 'stale transcript escaped after reopening')
            self.feed([16000] * 6 + [0] * 3)
            self.assertEqual(await asyncio.wait_for(self.task, 1), 'fresh user speech')
            self.assertEqual(self.decode.call_count, 2)
        finally:
            release.set()

    async def test_closed_gate_discards_decode_even_before_next_audio_callback(self):
        entered, release = threading.Event(), threading.Event()
        opened = [True]
        self.mic.gate = lambda: opened[0]
        def decode(audio):
            entered.set()
            if not release.wait(2): raise RuntimeError('fixture decode timed out')
            return 'muted transcript'
        self.decode.side_effect = decode
        try:
            self.feed([16000] * 6 + [0] * 3)
            for _ in range(50):
                if entered.is_set(): break
                await asyncio.sleep(.01)
            self.assertTrue(entered.is_set())
            opened[0] = False
            release.set()
            await asyncio.sleep(.05)
            self.assertFalse(self.task.done(), 'closed gate did not discard decoding result')
        finally:
            release.set()

    def test_vad_hysteresis_requires_higher_onset_than_continuation(self):
        self.mic._vad = lambda frame: .4
        self.assertFalse(self.mic._is_voiced(None))
        self.assertTrue(self.mic._is_voiced(None, continuing=True))


if __name__ == '__main__':
    unittest.main()
