# Last updated: 2026-10-05 21:33:33
# @nova: Provide cancellable speech backends with truthful playback callbacks and surfaced failures.
"""Speech backends accept optional should_stop() and on_playback() callbacks.

on_playback means the audio API accepted playback, not that audible output was measured.
Synthesis may continue after stop, but cancellation prevents its later playback. The
optional PowerShell WAV fallback reports process completion without an audio timestamp.
"""
from __future__ import annotations

import shutil
import subprocess
import threading
import wave
from pathlib import Path


class NullTTS:
    """Log what would be said without reporting real playback."""
    name = "null"

    def __init__(self, cfg=None):
        self.cfg = cfg

    def speak(self, text: str, should_stop=None, on_playback=None):
        if should_stop is not None and should_stop():
            return {"outcome": "skipped"}
        print(f"[tts:null] would speak: {text}")
        return {"outcome": "no_audio"}

    def stop(self) -> None:
        pass

    def close(self):
        pass


class _PlaybackControl:
    """Serialize the short start/stop boundary, never the expensive synthesis or wait."""

    def __init__(self):
        self._playback_lock = threading.RLock()
        self._stop_epoch = 0
        self._closed = False
        self._proc = None
        self._sd = None

    def _begin(self):
        with self._playback_lock:
            if self._closed:
                raise RuntimeError("TTS backend is closed")
            return self._stop_epoch

    def _cancelled(self, epoch, should_stop):
        with self._playback_lock:
            return self._closed or epoch != self._stop_epoch or bool(should_stop and should_stop())

    def stop(self) -> None:
        # If play won this lock first, stop follows it; otherwise that play sees a stale epoch.
        with self._playback_lock:
            self._stop_epoch += 1
            _stop_holder(self)

    def close(self):
        with self._playback_lock:
            self._closed = True
            self.stop()

    def _play_array(self, sd, samples, rate, epoch, should_stop, on_playback, **kwargs):
        with self._playback_lock:
            if self._cancelled(epoch, should_stop):
                return {"outcome": "skipped"}
            self._sd = sd
            sd.play(samples, rate, **kwargs)
            if on_playback is not None:
                on_playback()
        try:
            sd.wait()  # stop() can acquire the lock and interrupt this wait
        except Exception:
            self.stop()
            raise
        if self._cancelled(epoch, should_stop):
            return {"outcome": "cut"}       # stopped mid-playback (also by close(), not only the player)
        return {"outcome": "played"}


class LlamaCppTTS(_PlaybackControl):
    """Synthesize a WAV using llama-tts, then play it through sounddevice or PowerShell."""
    name = "llamacpp"

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.exe = cfg.resolve(cfg.llamacpp_tts_exe)
        self.model = cfg.resolve(cfg.llamacpp_tts_model) if cfg.llamacpp_tts_model else None
        self.vocoder = cfg.resolve(cfg.llamacpp_tts_vocoder) if cfg.llamacpp_tts_vocoder else None
        self._i = 0
        if not self.exe.exists():
            raise RuntimeError(f"llama-tts not found at {self.exe}")
        if not self.model or not self.model.exists():
            raise RuntimeError("llamacpp_tts_model (a TTS gguf) is not set/present — see README")

    def speak(self, text: str, should_stop=None, on_playback=None):
        epoch = self._begin()
        if self._cancelled(epoch, should_stop):
            return {"outcome": "skipped"}
        out = self.cfg.resolve(f"logs/Temp/voice_out_{self._i:04d}.wav")
        out.parent.mkdir(parents=True, exist_ok=True)
        self._i += 1
        cmd = [str(self.exe), "-m", str(self.model), "-p", text, "-o", str(out)]
        if self.vocoder:
            cmd += ["--vocoder", str(self.vocoder)]
        with self._playback_lock:
            if self._cancelled(epoch, should_stop):
                return {"outcome": "skipped"}
            proc = self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            try:
                code = proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                raise
            if self._cancelled(epoch, should_stop):
                return {"outcome": "skipped"}
            if code != 0:
                raise RuntimeError(f"llama-tts exited {code}")
        finally:
            with self._playback_lock:
                if self._proc is proc:
                    self._proc = None
        return _play_wav(out, self, epoch, should_stop, on_playback)


class ChatterboxTTS(_PlaybackControl):
    """Synthesize with Chatterbox; cancellation also works without a caller-supplied hook."""
    name = "chatterbox"

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        try:
            import torch  # noqa: F401
            from chatterbox.tts import ChatterboxTTS as _CB
        except Exception as error:
            raise RuntimeError(f"chatterbox/torch not installed ({error}) — see requirements.txt")
        self._model = _CB.from_pretrained(device="cuda" if _cuda_available() else "cpu")
        self.ref = cfg.resolve(cfg.tts_reference_wav) if cfg.tts_reference_wav else None
        try:
            import sounddevice
            self._sd = sounddevice
        except ImportError:
            pass

    def speak(self, text: str, should_stop=None, on_playback=None):
        epoch = self._begin()
        if self._cancelled(epoch, should_stop):
            return {"outcome": "skipped"}
        kw = {"exaggeration": self.cfg.tts_exaggeration, "cfg_weight": self.cfg.tts_cfg_weight}
        if self.ref and self.ref.exists():
            kw["audio_prompt_path"] = str(self.ref)
        wav = self._model.generate(text, **kw)
        if self._cancelled(epoch, should_stop):
            return {"outcome": "skipped"}
        if self._sd is None:
            raise RuntimeError("sounddevice is unavailable; synthesized speech was not played")
        import numpy as np
        arr = wav.squeeze().detach().cpu().numpy().astype("float32") \
            if hasattr(wav, "detach") else np.asarray(wav, dtype="float32")
        rate = int(getattr(self._model, "sr", 24000))
        device = None if self.cfg.output_device < 0 else self.cfg.output_device
        return self._play_array(self._sd, arr, rate, epoch, should_stop, on_playback, device=device)


def make_tts(cfg):
    """Resolve configured backends, falling back to logging if none can be constructed."""
    want = (cfg.tts_backend or "auto").lower()
    order = {"auto": ["chatterbox", "llamacpp", "null"], "chatterbox": ["chatterbox", "null"],
             "llamacpp": ["llamacpp", "null"], "windows": ["windows", "null"], "null": ["null"]}.get(want, ["null"])
    for backend in order:
        try:
            if backend == "windows":
                from windows_tts import WindowsTTS
                return WindowsTTS(cfg)
            if backend == "chatterbox":
                return ChatterboxTTS(cfg)
            if backend == "llamacpp":
                return LlamaCppTTS(cfg)
            return NullTTS(cfg)
        except Exception as error:
            print(f"[voice_gateway] TTS backend '{backend}' unavailable: {error}")
    return NullTTS(cfg)


def _cuda_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _play_wav(path: Path, holder, epoch, should_stop=None, on_playback=None):
    try:
        import sounddevice as sd
        import numpy as np
    except ImportError:
        # A launched process is not an audio-clock receipt. No on_playback callback here.
        player = shutil.which("powershell")
        if not player:
            raise RuntimeError("WAV playback requires sounddevice or PowerShell")
        quoted_path = str(path).replace("'", "''")
        script = ("$ErrorActionPreference='Stop'; "
                  f"$novaVoicePlayer=New-Object Media.SoundPlayer '{quoted_path}'; "
                  "try { $novaVoicePlayer.PlaySync() } finally { $novaVoicePlayer.Dispose() }")
        with holder._playback_lock:
            if holder._cancelled(epoch, should_stop):
                return {"outcome": "skipped"}
            proc = holder._proc = subprocess.Popen(
                [player, "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            try:
                code = proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                raise
            if holder._cancelled(epoch, should_stop):
                return {"outcome": "skipped"}
            if code != 0:
                raise RuntimeError(f"WAV playback process exited {code}")
            return {"outcome": "completed", "clock": "process"}
        finally:
            with holder._playback_lock:
                if holder._proc is proc:
                    holder._proc = None
    with wave.open(str(path), "rb") as wav:
        rate = wav.getframerate()
        channels = wav.getnchannels()
        if wav.getsampwidth() != 2 or wav.getcomptype() != "NONE":
            raise RuntimeError("WAV playback requires uncompressed PCM16 audio")
        frames = wav.readframes(wav.getnframes())
    samples = np.frombuffer(frames, dtype="int16").astype("float32") / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels)
    output_device = getattr(getattr(holder, "cfg", None), "output_device", -1)
    device = None if output_device < 0 else output_device
    return holder._play_array(sd, samples, rate, epoch, should_stop, on_playback, device=device)


def _stop_holder(holder) -> None:
    """Attempt both stop paths; expose failure so the caller can record uncertain shutdown."""
    errors = []
    proc = getattr(holder, "_proc", None)
    if proc is not None and proc.poll() is None:
        try:
            proc.kill()
        except Exception as error:
            errors.append(error)
    sd = getattr(holder, "_sd", None)
    if sd is not None:
        try:
            sd.stop()
        except Exception as error:
            errors.append(error)
    if errors:
        raise RuntimeError(f"TTS stop failed: {errors[0]}") from errors[0]
