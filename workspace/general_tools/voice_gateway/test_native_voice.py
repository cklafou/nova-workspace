# @nova: Verify native speech file synthesis, cancellation, output-device selection and current Moonshine/Silero contracts without audio hardware.
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from config import GatewayConfig
import stt
import tts
import windows_tts


def write_wav(path, channels=1):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x10" * 3200 * channels)


class FakeProcess:
    def __init__(self, commands, action=None):
        self.commands, self.action, self.returncode = commands, action, None
        self.payload = None

    def communicate(self, payload=None, timeout=None):
        self.payload = json.loads(payload) if payload else self.payload
        if self.payload:
            write_wav(self.payload["path"])
        if self.action:
            self.action()
        if self.returncode is None:
            self.returncode = 0
        return json.dumps({"voice": "fixture voice"}), ""

    def poll(self):
        return self.returncode

    def kill(self):
        self.returncode = -9


class WindowsSpeechTests(unittest.TestCase):
    def backend(self):
        with patch.object(windows_tts.sys, "platform", "win32"), patch.object(windows_tts.shutil, "which", return_value="powershell.exe"):
            return windows_tts.WindowsTTS(GatewayConfig())

    def test_synthesis_uses_json_data_not_script_interpolation_and_never_plays(self):
        backend = self.backend()
        observed = []
        def popen(command, **kwargs):
            process = FakeProcess(command)
            observed.append(process)
            return process
        utterance = "Quote ' and $() stay spoken text; no shell interpolation."
        with tempfile.TemporaryDirectory() as folder, patch.object(windows_tts.subprocess, "Popen", side_effect=popen), \
             patch.object(windows_tts, "_play_wav", side_effect=AssertionError("file synthesis must not play")):
            path = Path(folder) / "space in name.wav"
            result = backend.synthesize_to_file(utterance, path)
            self.assertTrue(path.is_file())
            self.assertEqual(result["outcome"], "synthesized")
            self.assertEqual(result["sample_rate"], 16000)
            self.assertEqual(observed[0].payload["text"], utterance)
            self.assertNotIn(utterance, " ".join(observed[0].commands))
            self.assertEqual(list(Path(folder).glob(".*.wav")), [])

    def test_stop_during_synthesis_prevents_publication_and_playback(self):
        backend = self.backend()
        with tempfile.TemporaryDirectory() as folder, patch.object(windows_tts.subprocess, "Popen", side_effect=lambda cmd, **kw: FakeProcess(cmd, backend.stop)), \
             patch.object(windows_tts, "_play_wav", side_effect=AssertionError("cancelled synthesis played")):
            path = Path(folder) / "voice.wav"
            self.assertEqual(backend.synthesize_to_file("hello", path)["outcome"], "skipped")
            self.assertFalse(path.exists())
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_close_prevents_late_speech(self):
        backend = self.backend()
        backend.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            backend.speak("late speech")

    def test_windows_backend_is_selected_explicitly(self):
        cfg = GatewayConfig(tts_backend="windows")
        with patch.object(windows_tts, "WindowsTTS", return_value="selected"):
            self.assertEqual(tts.make_tts(cfg), "selected")

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "requires the isolated voice numpy dependency")
    def test_pcm_playback_preserves_stereo_and_selected_device(self):
        import numpy as np
        captured = []
        fake = types.SimpleNamespace(play=lambda data, rate, **kw: captured.append((data.shape, rate, kw)),
                                     wait=lambda: None, stop=lambda: None)
        backend = tts._PlaybackControl()
        backend.cfg = types.SimpleNamespace(output_device=17)
        with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {"sounddevice": fake}):
            path = Path(folder) / "voice.wav"
            write_wav(path, channels=2)
            result = tts._play_wav(path, backend, backend._begin())
        self.assertEqual(result["outcome"], "played")
        self.assertEqual(captured, [((3200, 2), 16000, {"device": 17})])


class MoonshineContractTests(unittest.TestCase):
    def test_transcript_batch_is_normalized_without_stringifying_objects(self):
        self.assertEqual(stt._transcript_text([" hello ", "world", ""]), "hello world")
        self.assertEqual(stt._transcript_text(" hello "), "hello")
        self.assertEqual(stt._transcript_text(None), "")
        with self.assertRaises(TypeError):
            stt._transcript_text({"text": "not the current API"})

    @unittest.skipUnless(importlib.util.find_spec("numpy"), "requires numpy")
    def test_one_model_and_tokenizer_are_cached_for_multiple_utterances(self):
        import numpy as np
        creates, decoded = [], []
        class Model:
            def __init__(self, **kwargs):
                creates.append(kwargs)
            def generate(self, data):
                self_shape = data.shape
                if len(self_shape) != 2 or self_shape[0] != 1:
                    raise AssertionError(self_shape)
                return [[1, 2]]
        def tokenizer():
            decoded.append("created")
            return types.SimpleNamespace(decode_batch=lambda tokens: [" transcript "])
        fake = types.SimpleNamespace(MoonshineOnnxModel=Model, load_tokenizer=tokenizer)
        with patch.dict(sys.modules, {"moonshine_onnx": fake}):
            transcribe = stt._load_moonshine(GatewayConfig())
            self.assertEqual(transcribe(np.zeros(3200, "float32")), "transcript")
            self.assertEqual(transcribe(np.zeros(3200, "float32")), "transcript")
            self.assertEqual(transcribe(np.zeros(100, "float32")), "")
            with self.assertRaisesRegex(ValueError, "shorter than 64"):
                transcribe(np.zeros(64 * 16000, "float32"))
        self.assertEqual(len(creates), 1)
        self.assertEqual(decoded, ["created"])

    def test_non_16k_input_is_rejected_before_model_loading(self):
        with self.assertRaisesRegex(RuntimeError, "16000"):
            stt._load_moonshine(GatewayConfig(sample_rate=8000))


@unittest.skipUnless(importlib.util.find_spec("numpy"), "requires numpy")
class FrameContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_capture_uses_512_samples_and_real_frame_duration(self):
        import numpy as np
        captured, frame_lengths = {}, []
        class Input:
            def __init__(self, **kwargs):
                captured.update(kwargs)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
        def vad(frame):
            frame_lengths.append(len(frame))
            return float(np.max(frame) > 0)
        cfg = GatewayConfig(silence_ms=33)
        with patch.dict(sys.modules, {"sounddevice": types.SimpleNamespace(RawInputStream=Input)}), \
             patch.object(stt, "_load_silero", return_value=vad), \
             patch.object(stt, "_load_moonshine", return_value=lambda audio: ["hello"]):
            microphone = stt.MoonshineSTT(cfg)
            iterator = microphone.utterances()
            task = asyncio.create_task(anext(iterator))
            try:
                await asyncio.sleep(0)
                self.assertEqual(captured["blocksize"], 512)
                callback = captured["callback"]
                callback(np.full(512, 1000, "int16").tobytes(), 512, None, None)
                callback(np.zeros(512, "int16").tobytes(), 512, None, None)
                await asyncio.sleep(0.02)
                self.assertFalse(task.done(), "33ms silence incorrectly rounded down to one32ms frame")
                callback(np.zeros(512, "int16").tobytes(), 512, None, None)
                self.assertEqual(await asyncio.wait_for(task, 1), "hello")
                self.assertEqual(frame_lengths, [512, 512, 512])
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                await iterator.aclose()

    def test_silero_state_and_context_are_cpu_only_and_resettable(self):
        import numpy as np
        inputs = []
        class Session:
            def __init__(self, path, **kwargs):
                self.options = kwargs
                self.assert_cpu = kwargs["providers"] == ["CPUExecutionProvider"]
            def run(self, outputs, data):
                inputs.append({k:v.copy() for k,v in data.items()})
                return np.array([[0.75]], "float32"), np.ones((2, 1, 128), "float32")
        fake = types.SimpleNamespace(SessionOptions=types.SimpleNamespace, InferenceSession=Session)
        with patch.dict(sys.modules, {"onnxruntime": fake}):
            vad = stt._SileroOnnx("fake.onnx", 16000)
            self.assertTrue(vad.session.assert_cpu)
            self.assertEqual(vad(np.ones(512, "float32")), 0.75)
            vad(np.zeros(512, "float32"))
            self.assertEqual(inputs[0]["input"].shape, (1, 576))
            self.assertTrue(np.all(inputs[1]["input"][:, :64] == 1))
            self.assertTrue(np.all(inputs[1]["state"] == 1))
            vad.reset()
            self.assertTrue(np.all(vad.state == 0))
            with self.assertRaisesRegex(ValueError, "512"):
                vad(np.zeros(480, "float32"))


if __name__ == "__main__":
    unittest.main()
