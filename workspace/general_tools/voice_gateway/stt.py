# @nova: Transcribe gated microphone input and provide a typed-input fallback for the voice gateway.
# Last updated: 2026-10-04 15:01:23
#   utterances; Moonshine transcribes each. A stdin backend (type instead of talk) lets the whole
#   gateway run and be tested with no microphone or audio libraries at all.
"""voice_gateway/stt.py — yield Cole's utterances as text. Backends expose async utterances()."""
from __future__ import annotations

import asyncio
from collections import deque
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
        self._transcribe = self._load_model(cfg)
        self.gate = None              # callable -> bool; False = drop mic frames (half duplex)
        self.on_speech_start = None   # callable(); first voiced frame of an utterance (barge-in)
        self.on_diagnostic = None     # optional observer; a decoder failure does not end listening
        self.on_state = None          # hearing/finishing_turn/transcribing/listening; capture truth

    def _load_model(self, cfg):
        return _load_moonshine(cfg)

    def _state(self, state):
        callback = getattr(self, "on_state", None)
        if callable(callback):
            try:
                callback(state)
            except Exception:
                pass

    async def utterances(self):
        np, sd = self._np, self._sd
        sr = self.cfg.sample_rate
        # Current Silero ONNX requires exactly 512 samples at 16k (32ms), not 480.
        block = 512 if sr == 16000 else 256 if sr == 8000 else int(sr * 0.032)
        silence_frames = max(1, math.ceil(self.cfg.silence_ms * sr / (1000 * block)))
        min_voiced = max(1, math.ceil(self.cfg.min_speech_ms * sr / (1000 * block)))
        pre_frames = max(0, math.ceil(self.cfg.pre_roll_ms * sr / (1000 * block)))
        tail_frames = max(0, math.ceil(self.cfg.speech_tail_ms * sr / (1000 * block)))
        max_frames = max(1, int(60 * sr / block))       # Moonshine accepts strictly under 64s
        q: asyncio.Queue = asyncio.Queue(maxsize=max_frames)
        loop = asyncio.get_running_loop()
        generation = [0]                              # bumps while the gate is closed
        reported_state = [None]

        def state(value):
            if reported_state[0] != value:
                reported_state[0] = value
                self._state(value)

        def diagnostic(message):
            if callable(self.on_diagnostic):
                try:
                    self.on_diagnostic(message)
                except Exception:
                    pass
            else:
                print(f"[voice_gateway] {message}", flush=True)

        def enqueue(stamp, chunk):
            if stamp != generation[0]:
                return
            if q.full():
                # Bound delayed-consumer memory. Never turn a clipped recording into a request.
                generation[0] += 1
                while not q.empty():
                    q.get_nowait()
                diagnostic("Microphone capture overflow; incomplete speech discarded, listening continues")
                return
            q.put_nowait((stamp, chunk))

        def _cb(indata, frames, time_info, status):
            # Audio thread. Gate at CAPTURE: her voice never enters the queue, and every
            # frame captured before the gate closed carries a stale generation.
            if self.gate is not None and not self.gate():
                generation[0] += 1
                return
            loop.call_soon_threadsafe(enqueue, generation[0], bytes(indata))

        dev = None if self.cfg.input_device < 0 else self.cfg.input_device
        with sd.RawInputStream(samplerate=sr, blocksize=block, dtype="int16",
                               channels=1, device=dev, callback=_cb):
            buf, silent, speaking, born, voiced_count = [], 0, False, 0, 0
            pre_roll = deque(maxlen=pre_frames)
            seen_generation = generation[0]
            revision, capped, decoding = 0, False, None
            decoded_revision, decoded_generation = -1, -1

            def reset_turn():
                nonlocal buf, silent, speaking, voiced_count, revision, capped
                buf, silent, speaking, voiced_count = [], 0, False, 0
                revision, capped = 0, False

            def reset_capture():
                reset_turn()
                pre_roll.clear()                     # never splice audio across her turn
                if hasattr(self._vad, "reset"):
                    self._vad.reset()
                state("listening")

            try:
                while True:
                    if self.gate is not None and not self.gate():
                        # A mute observed between callbacks must invalidate the old decoder too.
                        generation[0] += 1
                    if seen_generation != generation[0]:
                        reset_capture()
                        seen_generation = generation[0]

                    # Do not wait for ASR before collecting/VAD-processing continuation.
                    # Drain captured frames before accepting a completed decode: it may already
                    # be obsolete. At the explicit 60s bound, queue the next turn separately.
                    if not capped and not q.empty():
                        stamp, chunk = q.get_nowait()
                    elif decoding is not None and decoding.done():
                        finished = decoding
                        decoding = None
                        try:
                            text = _transcript_text(finished.result())
                        except Exception as error:
                            diagnostic(f"Speech recognition failed ({type(error).__name__}); listening continues")
                            if decoded_generation == born and decoded_revision == revision:
                                reset_turn()
                                state("listening")
                            continue
                        valid = (decoded_generation == generation[0] == born
                                 and (self.gate is None or self.gate()))
                        if valid and decoded_revision == revision and speaking:
                            # Same complete candidate, with no continuation captured during
                            # decoding. Silence alone does not require another ASR pass.
                            reset_turn()
                            state("listening")
                            if text:
                                yield text
                        # If new speech arrived, keep its audio and re-decode the whole turn
                        # after its pause. An obsolete partial transcript is never published.
                        continue
                    elif speaking and (capped or silent >= silence_frames) and decoding is None:
                        if voiced_count < min_voiced:
                            reset_turn()
                            state("listening")
                            continue
                        trim = max(0, silent - tail_frames)
                        frames_to_decode = buf[:-trim] if trim else buf
                        audio = np.concatenate(frames_to_decode)
                        decoded_revision, decoded_generation = revision, born
                        state("transcribing")
                        decoding = loop.run_in_executor(None, self._transcribe, audio)
                        continue
                    elif decoding is not None:
                        # A short poll permits both cancellation and completion with no new
                        # input (including a muted mic). Only one decoder runs at a time.
                        if capped:
                            await asyncio.sleep(0.016)
                            continue
                        try:
                            stamp, chunk = await asyncio.wait_for(q.get(), timeout=0.016)
                        except asyncio.TimeoutError:
                            continue
                    else:
                        stamp, chunk = await q.get()

                    stale = stamp != generation[0]
                    if stale or stamp != seen_generation:
                        reset_capture()
                        if stale:
                            continue
                    seen_generation = stamp
                    frame = np.frombuffer(chunk, dtype="int16").astype("float32") / 32768.0
                    voiced = self._is_voiced(frame, continuing=speaking)
                    if voiced:
                        if not speaking:
                            born = stamp
                            buf = list(pre_roll)
                            pre_roll.clear()
                            if callable(self.on_speech_start):
                                self.on_speech_start()
                        speaking = True
                        voiced_count += 1
                        revision += 1
                        silent = 0
                        buf.append(frame)
                        state("hearing")
                    elif speaking:
                        silent += 1
                        buf.append(frame)
                        if silent < silence_frames:
                            state("finishing_turn")
                        elif voiced_count >= min_voiced:
                            state("transcribing")
                    else:
                        pre_roll.append(frame)
                    if speaking and len(buf) >= max_frames:
                        capped = True
                        diagnostic("Speech reached the 60-second turn limit; remaining audio starts the next turn")
                    if speaking and silent >= silence_frames and voiced_count < min_voiced:
                        reset_turn()                       # isolated noise, not a pending decode
                        state("listening")
            finally:
                if decoding is not None:
                    decoding.cancel()                    # never publish a result after capture closes

    def _is_voiced(self, frame, continuing=False) -> bool:
        if self._vad is None:
            # energy gate fallback
            import numpy as np
            return float(np.sqrt(np.mean(frame ** 2))) > 0.02
        return self._vad(frame) >= max(0.01, self.cfg.vad_threshold - (0.15 if continuing else 0))

    def close(self):
        pass


class FasterWhisperSTT(MoonshineSTT):
    """Share capture/VAD/gating with Moonshine; decode with larger local Whisper turbo."""
    name = "faster_whisper"

    def _load_model(self, cfg):
        return _load_faster_whisper(cfg)


def make_stt(cfg, *, allow_fallback=True):
    want = (cfg.stt_backend or "stdin").lower()
    backends = {"stdin": StdinSTT, "moonshine": MoonshineSTT,
                "faster_whisper": FasterWhisperSTT}
    if want not in backends:
        raise ValueError(f"Unknown speech recognition backend: {want}")
    try:
        return backends[want](cfg)
    except Exception as error:
        if not allow_fallback:
            raise
        print(f"[voice_gateway] STT backend '{want}' unavailable ({error}) — using stdin (type to talk)")
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


def _moonshine_path(cfg):
    name = str(cfg.moonshine_model)
    return (Path(sys.prefix) / "share/nova_voice/moonshine-base" if name in ("moonshine/base", "base")
            else Path(name).expanduser())


def _whisper_path(cfg):
    name = str(cfg.whisper_model)
    return (Path(sys.prefix) / "share/nova_voice/whisper-large-v3-turbo"
            if name == "large-v3-turbo" else Path(name).expanduser())


def local_asset_status(cfg):
    """Check only selected local assets; never load models or download during status polling."""
    recognizer = (cfg.stt_backend or "stdin").lower()
    labels = {"faster_whisper": "Whisper large-v3-turbo · English · CPU int8",
              "moonshine": "Moonshine base · English", "stdin": "Typed input"}
    if recognizer == "faster_whisper":
        path = _whisper_path(cfg)
        paths = [path / name for name in ("model.bin", "config.json", "tokenizer.json", "preprocessor_config.json")]
    elif recognizer == "moonshine":
        path = _moonshine_path(cfg)
        paths = [path / "encoder_model.onnx", path / "decoder_model_merged.onnx"]
    elif recognizer == "stdin":
        paths = []
    else:
        return {"ready": False, "missing": [], "vad": cfg.vad_backend,
                "recognizer": recognizer, "label": recognizer, "reason": "Unknown speech recognizer"}
    if recognizer != "stdin" and cfg.vad_backend == "silero":
        paths.append(Path(sys.prefix) / "share/nova_voice/silero_vad.onnx")
    missing = [str(path) for path in paths if not path.is_file() or path.stat().st_size == 0]
    rate_ok = recognizer == "stdin" or cfg.sample_rate == 16000
    return {"ready": not missing and rate_ok, "missing": missing, "vad": cfg.vad_backend,
            "recognizer": recognizer, "label": labels[recognizer],
            "reason": "" if rate_ok else "Speech recognition requires 16000 Hz mono input"}


def _load_faster_whisper(cfg):
    """Load a prepared local CTranslate2 model without CUDA or network fallback."""
    if cfg.sample_rate != 16000:
        raise RuntimeError("Whisper requires sample_rate=16000")
    import numpy as np
    from faster_whisper import WhisperModel
    status = local_asset_status(cfg)
    if not status["ready"]:
        raise RuntimeError("Local Whisper assets missing; run setup_windows.py --assets-only")
    model = WhisperModel(str(_whisper_path(cfg)), device="cpu", compute_type="int8",
                         cpu_threads=max(1, int(cfg.whisper_cpu_threads)), num_workers=1,
                         local_files_only=True)
    def transcribe(audio):
        samples = np.asarray(audio, dtype="float32")
        if samples.ndim != 1 or not np.isfinite(samples).all():
            raise ValueError("Whisper input must be finite mono audio")
        if samples.size < 1600:
            return ""
        segments, _ = model.transcribe(samples, language=cfg.speech_language or None,
            beam_size=5, temperature=0.0, condition_on_previous_text=False,
            vad_filter=False, without_timestamps=True)
        return " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
    return transcribe


def _load_silero(cfg):
    """Require the prepared local CPU asset; never silently substitute an energy gate."""
    path = Path(sys.prefix) / "share/nova_voice/silero_vad.onnx"
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError("Pinned Silero asset missing; run setup_windows.py --assets-only")
    return _SileroOnnx(path, cfg.sample_rate)


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
    path = _moonshine_path(cfg)
    for filename in ("encoder_model.onnx", "decoder_model_merged.onnx"):
        asset = path / filename
        if not asset.is_file() or asset.stat().st_size == 0:
            raise RuntimeError("Local Moonshine assets missing; run setup_windows.py --assets-only "
                               "or configure a prepared ONNX directory")
    # The current upstream class still needs base/tiny to size decoder caches.
    family = "tiny" if "tiny" in path.name.lower() else "base"
    model = moonshine.MoonshineOnnxModel(models_dir=str(path), model_name=family)
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
        tokens = model.generate(samples[None, :], max_len=min(448, int(seconds * 6.5) + 10))
        return _transcript_text(tokenizer.decode_batch(tokens))
    return transcribe
