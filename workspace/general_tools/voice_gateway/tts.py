# Last updated: 2026-08-05 20:31:29
# @nova-adjacent: voice_gateway — text→speech backends. Three, in preference order:
#   Chatterbox (expressive, zero-shot clone — Cole's "tomboyish, not-AI"), llama.cpp TTS
#   (zero python-deps, uses the llama-tts.exe already on the box), and Null (logs only, for
#   smoke tests with no audio stack). make_tts() picks the best available and falls back.
"""voice_gateway/tts.py — speak a committed unit. Every backend exposes .speak(text: str)."""
from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path


class NullTTS:
    """No audio. Logs what WOULD be spoken. Always available — the smoke-test backend and the
    guaranteed fallback so the gateway never hard-crashes for lack of an audio stack."""
    name = "null"

    def __init__(self, cfg=None):
        self.cfg = cfg

    def speak(self, text: str) -> None:
        print(f"[tts:null] 🔊 {text}")

    def close(self):
        pass


class LlamaCppTTS:
    """Uses llama/llama-tts.exe (already present) + a TTS gguf (e.g. OuteTTS) + a vocoder.
    No torch, no python audio deps. Less expressive than Chatterbox but a solid zero-install
    fallback. Writes a wav and plays it. Requires cfg.llamacpp_tts_model to be set."""
    name = "llamacpp"

    def __init__(self, cfg):
        self.cfg = cfg
        self.exe = cfg.resolve(cfg.llamacpp_tts_exe)
        self.model = cfg.resolve(cfg.llamacpp_tts_model) if cfg.llamacpp_tts_model else None
        self.vocoder = cfg.resolve(cfg.llamacpp_tts_vocoder) if cfg.llamacpp_tts_vocoder else None
        self._i = 0
        if not self.exe.exists():
            raise RuntimeError(f"llama-tts not found at {self.exe}")
        if not self.model or not self.model.exists():
            raise RuntimeError("llamacpp_tts_model (a TTS gguf) is not set/present — see README")

    def speak(self, text: str) -> None:
        out = self.cfg.resolve(f"logs/Temp/voice_out_{self._i:04d}.wav")
        out.parent.mkdir(parents=True, exist_ok=True)
        self._i += 1
        cmd = [str(self.exe), "-m", str(self.model), "-p", text, "-o", str(out)]
        if self.vocoder:
            cmd += ["--vocoder", str(self.vocoder)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=60)
            _play_wav(out)
        except Exception as e:
            print(f"[tts:llamacpp] failed ({e}) — falling back to text: {text}")

    def close(self):
        pass


class ChatterboxTTS:
    """Chatterbox-Turbo: expressive, ~emotion exaggeration, zero-shot voice clone from a ~10s
    reference clip. Needs torch + chatterbox-tts + a reference wav. This is the target voice
    for the audition round with Cole."""
    name = "chatterbox"

    def __init__(self, cfg):
        self.cfg = cfg
        try:
            import torch  # noqa: F401
            from chatterbox.tts import ChatterboxTTS as _CB
        except Exception as e:
            raise RuntimeError(f"chatterbox/torch not installed ({e}) — see requirements.txt")
        dev = "cuda" if _cuda_available() else "cpu"
        self._model = _CB.from_pretrained(device=dev)
        self.ref = cfg.resolve(cfg.tts_reference_wav) if cfg.tts_reference_wav else None
        try:
            import sounddevice  # noqa: F401
            self._sd = sounddevice
        except Exception:
            self._sd = None

    def speak(self, text: str) -> None:
        kw = {"exaggeration": self.cfg.tts_exaggeration, "cfg_weight": self.cfg.tts_cfg_weight}
        if self.ref and self.ref.exists():
            kw["audio_prompt_path"] = str(self.ref)
        wav = self._model.generate(text, **kw)
        try:
            import numpy as np
            arr = wav.squeeze().detach().cpu().numpy().astype("float32") \
                if hasattr(wav, "detach") else np.asarray(wav, dtype="float32")
            sr = int(getattr(self._model, "sr", 24000))
            if self._sd is not None:
                dev = None if self.cfg.output_device < 0 else self.cfg.output_device
                self._sd.play(arr, sr, device=dev)
                self._sd.wait()
            else:
                print(f"[tts:chatterbox] no sounddevice — synthesized {len(arr)} samples for: {text}")
        except Exception as e:
            print(f"[tts:chatterbox] playback failed ({e}) — text was: {text}")

    def close(self):
        pass


def make_tts(cfg):
    """Resolve cfg.tts_backend to a concrete backend, falling back gracefully to Null."""
    want = (cfg.tts_backend or "auto").lower()
    order = {
        "auto": ["chatterbox", "llamacpp", "null"],
        "chatterbox": ["chatterbox", "null"],
        "llamacpp": ["llamacpp", "null"],
        "null": ["null"],
    }.get(want, ["null"])
    for backend in order:
        try:
            if backend == "chatterbox":
                return ChatterboxTTS(cfg)
            if backend == "llamacpp":
                return LlamaCppTTS(cfg)
            return NullTTS(cfg)
        except Exception as e:
            print(f"[voice_gateway] TTS backend '{backend}' unavailable: {e}")
    return NullTTS(cfg)


# ── helpers ────────────────────────────────────────────────────────────────────────────────
def _cuda_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _play_wav(path: Path) -> None:
    """Best-effort playback of a wav file without a hard dependency."""
    try:
        import sounddevice as sd
        import numpy as np
        with wave.open(str(path), "rb") as w:
            sr = w.getframerate()
            frames = w.readframes(w.getnframes())
        arr = np.frombuffer(frames, dtype="int16").astype("float32") / 32768.0
        sd.play(arr, sr)
        sd.wait()
        return
    except Exception:
        pass
    # last resort on Windows: the shell's default player
    player = shutil.which("powershell")
    if player:
        try:
            subprocess.run([player, "-NoProfile", "-c",
                            f"(New-Object Media.SoundPlayer '{path}').PlaySync();"],
                           check=False, timeout=60)
        except Exception:
            pass
