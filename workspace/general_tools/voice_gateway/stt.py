# @nova: Transcribe gated microphone input and provide a typed-input fallback for the voice gateway.
# Last updated: 2026-10-04 15:01:23
#   utterances; Moonshine transcribes each. A stdin backend (type instead of talk) lets the whole
#   gateway run and be tested with no microphone or audio libraries at all.
"""voice_gateway/stt.py — yield Cole's utterances as text. Backends expose async utterances()."""
from __future__ import annotations

import asyncio
import math
from pathlib import Path
import sys
import threading


class StdinSTT:
    """No microphone. Read typed lines as 'utterances'. This is what makes the full gateway
    loop testable without any audio stack — and a genuinely useful text-console mode."""
    name = "stdin"

    def __init__(self, cfg=None):
        self.cfg = cfg
        self.gate = None              # typed input is never her own voice; accepted for symmetry
        self.on_speech_start = None

    async def utterances(self):
        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue()

        def _reader():                      # daemon: a blocked readline never holds up shutdown
            try:
                for line in sys.stdin:
                    loop.call_soon_threadsafe(q.put_nowait, line)
                loop.call_soon_threadsafe(q.put_nowait, None)
            except RuntimeError:            # the loop closed while we were reading
                pass

        threading.Thread(target=_reader, name="voice-stdin", daemon=True).start()
        print("[stt:stdin] type to Nova (blank line or Ctrl-D to quit):")
        while True:
            line = await q.get()
            if line is None:
                break
            line = line.strip()
            if not line:
                break
            yield line

    def close(self):
        pass


class MoonshineSTT:
    """Silero VAD + Moonshine streaming STT over the default mic. Requires sounddevice,
    numpy, onnxruntime and the moonshine model. Guards every import so a missing piece is a
    clear message, not a stack trace."""
    name = "moonshine"

    def __init__(self, cfg):
        self.cfg = cfg
        try:
            import numpy as np
            import sounddevice as sd
        except Exception as e:
            raise RuntimeError(f"sounddevice/numpy required for mic input ({e}) — "
                               f"or set stt_backend='stdin'")
        self._np, self._sd = np, sd
        self._vad = _load_silero(cfg) if cfg.vad_backend == "silero" else None
        self._transcribe = _load_moonshine(cfg)
        self.gate = None              # callable -> bool; False = drop mic frames (half duplex)
        self.on_speech_start = None   # callable(); first voiced frame of an utterance (barge-in)

    async def utterances(self):
        np, sd = self._np, self._sd
        sr = self.cfg.sample_rate
        # Current Silero ONNX requires exactly 512 samples at 16k (32ms), not 480.
        block = 512 if sr == 16000 else 256 if sr == 8000 else int(sr * 0.032)
        silence_frames = max(1, math.ceil(self.cfg.silence_ms * sr / (1000 * block)))
        max_frames = max(1, int(60 * sr / block))       # Moonshine accepts strictly under 64s
        q: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        generation = [0]                              # bumps while the gate is closed

        def _cb(indata, frames, time_info, status):
            # Audio thread. Gate at CAPTURE (Codex review #72): her voice never enters the queue,
            # and every frame captured before the gate closed carries a stale generation.
            if self.gate is not None and not self.gate():
                generation[0] += 1
                return
            loop.call_soon_threadsafe(q.put_nowait, (generation[0], bytes(indata)))

        dev = None if self.cfg.input_device < 0 else self.cfg.input_device
        with sd.RawInputStream(samplerate=sr, blocksize=block, dtype="int16",
                               channels=1, device=dev, callback=_cb):
            buf, silent, speaking, born = [], 0, False, 0
            while True:
                stamp, chunk = await q.get()
                stale = stamp != generation[0]
                if stale or (speaking and stamp != born):
                    buf, silent, speaking = [], 0, False       # never splice audio across her turn
                    if hasattr(self._vad, "reset"):
                        self._vad.reset()
                    if stale:
                        continue
                frame = np.frombuffer(chunk, dtype="int16").astype("float32") / 32768.0
                voiced = self._is_voiced(frame)
                if voiced:
                    if not speaking:
                        born = stamp
                        if callable(self.on_speech_start):
                            self.on_speech_start()
                    speaking = True
                    silent = 0
                    buf.append(frame)
                elif speaking:
                    silent += 1
                    buf.append(frame)
                if speaking and (silent >= silence_frames or len(buf) >= max_frames):
                    audio = np.concatenate(buf) if buf else np.zeros(1, "float32")
                    buf, silent, speaking = [], 0, False
                    text = await loop.run_in_executor(None, self._transcribe, audio)
                    text = _transcript_text(text)
                    if text:
                        yield text

    def _is_voiced(self, frame) -> bool:
        if self._vad is None:
            # energy gate fallback
            import numpy as np
            return float(np.sqrt(np.mean(frame ** 2))) > 0.02
        return self._vad(frame) >= self.cfg.vad_threshold

    def close(self):
        pass


def make_stt(cfg):
    want = (cfg.stt_backend or "stdin").lower()
    if want == "stdin":
        return StdinSTT(cfg)
    try:
        return MoonshineSTT(cfg)
    except Exception as e:
        print(f"[voice_gateway] STT backend '{want}' unavailable ({e}) — using stdin (type to talk)")
        return StdinSTT(cfg)


# ── model loaders (kept out of the class so import failures are localized) ───────────────────
class _SileroOnnx:
    """Single-stream NumPy adapter for the official Silero v6 ONNX state/context inputs.

    Contract: github.com/snakers4/silero-vad/blob/v6.2.1/src/silero_vad/utils_vad.py.
    No Torch import, GPU session, network call, or microphone acquisition.
    """
    def __init__(self, path, sample_rate):
        import numpy as np
        import onnxruntime as ort
        if sample_rate not in (8000, 16000):
            raise ValueError("Silero supports 8000 or 16000 Hz")
        self.np, self.sample_rate = np, sample_rate
        self.frame_size = 512 if sample_rate == 16000 else 256
        self.context_size = 64 if sample_rate == 16000 else 32
        options = ort.SessionOptions()
        options.inter_op_num_threads = options.intra_op_num_threads = 1
        self.session = ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])
        self.reset()

    def reset(self):
        self.state = self.np.zeros((2, 1, 128), dtype="float32")
        self.context = self.np.zeros((1, self.context_size), dtype="float32")

    def __call__(self, frame):
        np = self.np
        frame = np.asarray(frame, dtype="float32").reshape(1, -1)
        if frame.shape[1] != self.frame_size:
            raise ValueError(f"Silero needs {self.frame_size} samples, got {frame.shape[1]}")
        audio = np.concatenate((self.context, frame), axis=1)
        probability, self.state = self.session.run(None, {
            "input": audio, "state": self.state, "sr": np.array(self.sample_rate, dtype="int64")})
        self.context = audio[:, -self.context_size:].copy()
        return float(probability.reshape(-1)[0])


def _load_silero(cfg):
    """Use the pinned local CPU ONNX asset, with an explicit energy fallback if absent."""
    try:
        path = Path(sys.prefix) / "share" / "nova_voice" / "silero_vad.onnx"
        if not path.is_file():
            raise RuntimeError("pinned Silero asset missing; run setup_windows.py")
        return _SileroOnnx(path, cfg.sample_rate)
    except Exception as error:
        print(f"[voice_gateway] Silero VAD unavailable ({error}) — using energy gate")
        return None


def _transcript_text(result):
    """Moonshine ONNX returns one string per batch item; do not call .strip on its list."""
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, (list, tuple)) and all(isinstance(item, str) for item in result):
        return " ".join(item.strip() for item in result if item.strip())
    raise TypeError(f"Unexpected Moonshine transcript type: {type(result).__name__}")


def _load_moonshine(cfg):
    """Cache one CPU ONNX model and tokenizer for the microphone session, at 16k mono."""
    if cfg.sample_rate != 16000:
        raise RuntimeError("Moonshine requires sample_rate=16000; select a 16k microphone stream")
    try:
        import moonshine_onnx as moonshine
        import numpy as np
    except ImportError as error:
        raise RuntimeError(f"Moonshine ONNX is unavailable ({error}) — run setup_windows.py") from error
    name = str(cfg.moonshine_model)
    path = Path(name)
    prepared = Path(sys.prefix) / "share/nova_voice/moonshine-base"
    if name in ("moonshine/base", "base") and prepared.is_dir():
        path = prepared
    if path.is_dir():
        # The current upstream class still needs base/tiny to size decoder caches.
        family = "tiny" if "tiny" in path.name.lower() else "base"
        model = moonshine.MoonshineOnnxModel(models_dir=str(path), model_name=family)
    else:
        model = moonshine.MoonshineOnnxModel(model_name=name)
    tokenizer = moonshine.load_tokenizer()

    def transcribe(audio):
        samples = np.asarray(audio, dtype="float32")
        if samples.ndim != 1:
            raise ValueError("Moonshine input must be mono audio")
        seconds = samples.size / 16000
        if seconds <= 0.1:
            return ""                              # too short to be an utterance
        if seconds >= 64:
            raise ValueError("Moonshine utterance must be shorter than 64 seconds")
        tokens = model.generate(samples[None, :])
        return _transcript_text(tokenizer.decode_batch(tokens))
    return transcribe
