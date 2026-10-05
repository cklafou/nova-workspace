# @nova: Synthesize a labelled Windows system voice to PCM WAV and play through the gateway's cancellable device path.
"""System.Speech is a CPU/native baseline, not a cloned voice or a GPU model.

Text and paths travel as JSON on stdin; no utterance becomes PowerShell source.
Synthesis writes a file only. Playback stays in _PlaybackControl / sounddevice.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
import wave

from tts import _PlaybackControl, _play_wav

_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$novaSpeechRequest = [Console]::In.ReadToEnd() | ConvertFrom-Json
$novaSpeech = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    if ($novaSpeechRequest.voice) { $novaSpeech.SelectVoice([string]$novaSpeechRequest.voice) }
    $novaSpeechFormat = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
        16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
        [System.Speech.AudioFormat.AudioChannel]::Mono)
    $novaSpeech.SetOutputToWaveFile([string]$novaSpeechRequest.path, $novaSpeechFormat)
    $novaSpeech.Speak([string]$novaSpeechRequest.text)
    $novaSpeech.SetOutputToNull()
    @{ voice = $novaSpeech.Voice.Name; backend = 'Windows system voice' } | ConvertTo-Json -Compress
} finally { $novaSpeech.Dispose() }
"""


class WindowsTTS(_PlaybackControl):
    name = "windows"
    label = "Windows system voice"

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.exe = shutil.which("powershell") if sys.platform == "win32" else None
        if not self.exe:
            raise RuntimeError("Windows system voice requires Windows PowerShell and System.Speech")
        self.voice_name = str(getattr(cfg, "windows_voice", "") or "")

    def synthesize_to_file(self, text, path, should_stop=None, *, epoch=None):
        """Create and validate a WAV without opening an output device or playing sound."""
        epoch = self._begin() if epoch is None else epoch
        if self._cancelled(epoch, should_stop):
            return {"outcome": "skipped"}
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Speech text must be nonempty")
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = path.with_name(f".{path.stem}.{uuid.uuid4().hex}.wav")
        payload = json.dumps({"text": text, "path": str(pending), "voice": self.voice_name}, ensure_ascii=True)
        command = [self.exe, "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-EncodedCommand",
                   base64.b64encode(_SCRIPT.encode("utf-16-le")).decode("ascii")]
        proc = None
        try:
            with self._playback_lock:
                if self._cancelled(epoch, should_stop):
                    return {"outcome": "skipped"}
                proc = self._proc = subprocess.Popen(command, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                stdout, stderr = proc.communicate(payload, timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                if self._cancelled(epoch, should_stop):
                    return {"outcome": "skipped"}
                raise RuntimeError("Windows speech synthesis timed out") from None
            if self._cancelled(epoch, should_stop):
                return {"outcome": "skipped"}
            if proc.returncode:
                raise RuntimeError(f"Windows speech synthesis exited {proc.returncode}: {stderr.strip()[:600]}")
            details = json.loads(stdout.strip())
            with wave.open(str(pending), "rb") as wav:
                if (wav.getsampwidth(), wav.getnchannels(), wav.getframerate()) != (2, 1, 16000) or wav.getnframes() == 0:
                    raise RuntimeError("Windows speech returned an empty or unsupported WAV")
                duration = wav.getnframes() / wav.getframerate()
            # A stop that arrives during validation still prevents publication and playback.
            with self._playback_lock:
                if self._cancelled(epoch, should_stop):
                    return {"outcome": "skipped"}
                os.replace(pending, path)
            return {"outcome": "synthesized", "path": str(path), "voice": details.get("voice", ""),
                    "backend": self.label, "sample_rate": 16000, "duration_s": duration}
        finally:
            with self._playback_lock:
                if self._proc is proc:
                    self._proc = None
            pending.unlink(missing_ok=True)

    def speak(self, text, should_stop=None, on_playback=None):
        epoch = self._begin()
        if self._cancelled(epoch, should_stop):
            return {"outcome": "skipped"}
        with tempfile.TemporaryDirectory(prefix="nova-windows-voice-") as folder:
            path = Path(folder) / "speech.wav"
            result = self.synthesize_to_file(text, path, should_stop, epoch=epoch)
            if result["outcome"] != "synthesized":
                return result
            return _play_wav(path, self, epoch, should_stop, on_playback)
