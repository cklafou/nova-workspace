# @nova: Transcribe gated microphone input and provide a typed-input fallback for the voice gateway.
# Last updated: 2026-10-04 15:01:23
#   utterances; Moonshine transcribes each. A stdin backend (type instead of talk) lets the whole
#   gateway run and be tested with no microphone or audio libraries at all.
"""voice_gateway/stt.py — yield Cole's utterances as text. Backends expose async utterances()."""
from __future__ import annotations

import asyncio
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
        block = int(sr * 0.03)                        # 30ms frames
        silence_frames = max(1, self.cfg.silence_ms // 30)
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
                    if silent >= silence_frames:
                        audio = np.concatenate(buf) if buf else np.zeros(1, "float32")
                        buf, silent, speaking = [], 0, False
                        text = await loop.run_in_executor(None, self._transcribe, audio)
                        text = (text or "").strip()
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
def _load_silero(cfg):
    """Return a callable(frame)->speech_prob in [0,1], or None on failure."""
    try:
        import numpy as np
        import onnxruntime as ort  # noqa: F401
        import torch
        model, _ = torch.hub.load("snakers4/silero-vad", "silero_vad", trust_repo=True)
        sr = cfg.sample_rate

        def _prob(frame):
            with torch.no_grad():
                t = torch.from_numpy(np.asarray(frame, dtype="float32"))
                return float(model(t, sr).item())
        return _prob
    except Exception as e:
        print(f"[voice_gateway] Silero VAD unavailable ({e}) — using energy gate")
        return None


def _load_moonshine(cfg):
    """Return a callable(audio_np)->text."""
    try:
        import moonshine_onnx as moonshine
        model = cfg.moonshine_model

        def _t(audio):
            return moonshine.transcribe(audio, model)
        return _t
    except Exception:
        pass
    try:
        import moonshine
        model = cfg.moonshine_model

        def _t2(audio):
            return moonshine.transcribe(audio, model)
        return _t2
    except Exception as e:
        raise RuntimeError(f"moonshine not installed ({e}) — pip install useful-moonshine-onnx")
