# @nova: Supervise explicit local voice sessions, device settings and bounded audio tests for Conversation controls.
from __future__ import annotations

import asyncio
from collections import deque
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request

PREFIX = "[voice-control] "
LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}


class VoiceController:
    """Own exactly one child. Construction/status never opens audio devices or starts Nova."""
    def __init__(self, workspace: Path, nova_enabled=lambda: False):
        self.workspace = Path(workspace)
        self.folder = self.workspace / "general_tools" / "voice_gateway"
        self.settings_path = self.workspace / "_admin" / "voice_devices.json"
        self.nova_enabled = nova_enabled
        self.settings = {"input_device": -1, "output_device": -1}
        try:
            saved = json.loads(self.settings_path.read_text(encoding="utf-8"))
            self.settings.update(self._validate_settings(saved))
        except (OSError, ValueError, TypeError):
            pass
        self._lock = threading.RLock()
        self._action = asyncio.Lock()
        self._probe_lock = asyncio.Lock()
        self._proc = None
        self._reader = None
        self._mode = None
        self._state = "off"
        self._reason = "Voice is off"
        self._error = None
        self._microphone_muted = False
        self._output_muted = False
        self._last_caption = None
        self._last_transcript = ""
        self._test_result = None
        self._diagnostics = deque(maxlen=12)
        self._probe = None
        self._probed_at = 0
        self._stopping = False
        self._generation = 0
        self.router = APIRouter(prefix="/api/voice")
        for path, handler, methods in (
            ("/status", self.status, ["GET"]), ("/devices", self.devices, ["GET"]),
            ("/config", self.configure, ["POST"]), ("/start", self.start, ["POST"]),
            ("/stop", self.stop, ["POST"]), ("/mute", self.mute, ["POST"]),
            ("/test", self.test, ["POST"]),
        ):
            self.router.add_api_route(path, handler, methods=methods)
        self.router.add_event_handler("shutdown", self.close)

    @staticmethod
    def _guard(request):
        if request is None:
            return
        if request.client is None or request.client.host not in LOOPBACK:
            raise HTTPException(403, "Voice device control is available only on this computer")
        host = request.headers.get("host", "")
        try:
            parsed = urlsplit("http://" + host)
            local = parsed.hostname in {"127.0.0.1", "localhost", "::1"} and parsed.port is not None
        except ValueError:
            local = False
        if not local or any(key in request.headers for key in ("forwarded", "x-forwarded-for", "x-forwarded-host", "x-real-ip")):
            raise HTTPException(403, "Direct loopback requests only")
        if request.headers.get("origin") not in (None, "http://" + host):
            raise HTTPException(403, "Voice control rejects cross-origin requests")
        if request.headers.get("sec-fetch-site") not in (None, "none", "same-origin"):
            raise HTTPException(403, "Voice control rejects cross-site requests")
        if request.method == "POST" and request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
            raise HTTPException(415, "Send application/json")

    @staticmethod
    def _validate_settings(values):
        if not isinstance(values, dict) or set(values) - {"input_device", "output_device"}:
            raise ValueError("Only microphone and output device settings are accepted")
        result = {}
        for key, value in values.items():
            if type(value) is not int or not -1 <= value <= 4096:
                raise ValueError(f"{key} must be a device ID or -1 for system default")
            result[key] = value
        return result

    def _python(self):
        for path in (self.folder / ".venv" / "Scripts" / "python.exe",
                     self.folder / ".venv" / "bin" / "python"):
            if path.is_file():
                return str(path)
        path = Path(sys.executable)
        if path.name.lower() == "pythonw.exe":
            path = path.with_name("python.exe")
        return str(path)

    def _command(self, mode):
        return [self._python(), "-u", str(self.folder / "control_worker.py"), mode]

    def _environment(self):
        return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1",
                "NOVA_VOICE_SETTINGS_JSON": json.dumps(self.settings)}

    def _small(self, mode):
        completed = subprocess.run(self._command(mode), cwd=self.workspace, env=self._environment(),
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", errors="replace", timeout=20,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        events = []
        for line in completed.stdout.splitlines():
            if line.startswith(PREFIX):
                try:
                    events.append(json.loads(line[len(PREFIX):]))
                except ValueError:
                    pass
        found = next((e for e in events if e.get("type") == mode), None)
        if completed.returncode or found is None:
            message = next((e.get("message") for e in events if e.get("type") == "error"), None)
            raise RuntimeError(message or f"Voice {mode} failed ({completed.returncode}); check its Python environment")
        return found

    async def _readiness(self, force=False):
        async with self._probe_lock:
            if not force and self._probe is not None and time.monotonic() - self._probed_at < 30:
                return self._probe
            try:
                result = await asyncio.to_thread(self._small, "probe")
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                result = {"available": False, "reason": str(error), "capabilities": {}}
            self._probe, self._probed_at = result, time.monotonic()
            return result

    def snapshot(self):
        with self._lock:
            ready = self._probe or {}
            running = self._proc is not None and self._proc.poll() is None
            return {"running": running, "state": self._state,
                    "available": bool(ready.get("available")), "reason": self._reason if running else ready.get("reason", self._reason),
                    "error": self._error, "microphone_muted": self._microphone_muted,
                    "output_muted": self._output_muted, "capabilities": ready.get("capabilities", {}),
                    "settings": dict(self.settings), "backends": ready.get("backends", {}),
                    "last_caption": self._last_caption, "last_transcript": self._last_transcript,
                    "test_result": self._test_result, "diagnostics": list(self._diagnostics)}

    async def status(self, request: Request):
        self._guard(request)
        await self._readiness()
        return self.snapshot()

    async def devices(self, request: Request):
        self._guard(request)
        try:
            return await asyncio.to_thread(self._small, "devices")
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            raise HTTPException(503, str(error)) from error

    async def configure(self, request: Request):
        self._guard(request)
        try:
            updates = self._validate_settings(await request.json())
        except (TypeError, ValueError) as error:
            raise HTTPException(422, str(error)) from error
        async with self._action:
            if self.snapshot()["running"]:
                raise HTTPException(409, "Stop voice or the audio test before changing devices")
            settings = {**self.settings, **updates}
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.settings_path.with_name(self.settings_path.name + ".tmp")
            temporary.write_bytes((json.dumps(settings, indent=2) + "\n").encode("utf-8"))
            os.replace(temporary, self.settings_path)
            self.settings = settings
        return self.snapshot()

    def _event(self, event):
        kind = event.get("type")
        if kind == "error":
            self._state, self._error = "error", str(event.get("message", "Voice worker failed"))[:2000]
            if self._mode in {"microphone", "speaker"}:
                self._test_result = {"kind": self._mode, "state": "error", "message": self._error}
        elif kind == "state":
            self._state = event.get("state", self._state)
            self._reason = str(event.get("reason", ""))[:500]
            if self._probe and event.get("backends"):
                self._probe["backends"] = event["backends"]
        elif kind == "mute":
            self._microphone_muted = bool(event.get("microphone_muted"))
            self._output_muted = bool(event.get("output_muted"))
        elif kind == "transcript":
            self._last_transcript = str(event.get("text", ""))[:8000]
        elif kind == "test":
            self._test_result = {k: v for k, v in event.items() if k != "type"}
        elif kind == "body":
            value = event.get("event", {})
            if value.get("type") == "caption":
                self._last_caption = {"text": str(value.get("text", ""))[:8000], "audit": value.get("audit", {}),
                                      "clock": value.get("clock")}
            elif value.get("type") == "state" and self._mode == "run":
                state = value.get("state")
                self._state = "listening" if state == "idle" else state
            elif value.get("type") == "diagnostic":
                self._diagnostics.append(str(value.get("message", ""))[:500])
                if value.get("level") == "error":
                    self._error = str(value.get("message", ""))[:2000]
            elif value.get("type") == "speech" and value.get("phase") == "end" and self._mode == "speaker":
                outcome = value.get("outcome")
                success = outcome in {"played", "completed"}
                cancelled = self._stopping or (self._test_result or {}).get("state") == "cancelled"
                self._test_result = {"kind": "speaker", "state": "cancelled" if cancelled else "complete" if success else "error",
                                     "message": ("Speaker test stopped" if cancelled else
                                                 "Playback API completed; confirm you heard it on the selected output" if success
                                                 else self._error or f"Speaker test ended: {outcome}"), "outcome": outcome}

    def _read_worker(self, proc, generation):
        try:
            for line in proc.stdout:
                with self._lock:
                    if generation != self._generation:
                        continue
                    if line.startswith(PREFIX):
                        try:
                            self._event(json.loads(line[len(PREFIX):]))
                        except (ValueError, TypeError, AttributeError):
                            self._diagnostics.append("Voice worker emitted an invalid status event")
                    elif line.strip():
                        self._diagnostics.append(line.strip()[:500])
            code = proc.wait()
            with self._lock:
                if generation != self._generation:
                    return
                if not self._stopping and self._mode == "run" and not self._error:
                    self._error = "Voice session ended; start voice again to reconnect"
                if code and not self._stopping and not self._error:
                    self._error = f"Voice worker exited with code {code}"
                self._state = "error" if self._error and not self._stopping else "off"
                self._proc = None
        finally:
            proc.stdout.close()
            if proc.stdin:
                proc.stdin.close()

    def _launch(self, mode):
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                raise HTTPException(409, "A voice session or audio test is already running")
            self._mode, self._state = mode, "starting" if mode == "run" else "testing"
            self._reason = "Starting local voice" if mode == "run" else f"Testing {mode}"
            self._error = None
            self._test_result = None
            self._last_caption = None
            self._last_transcript = ""
            self._microphone_muted = self._output_muted = self._stopping = False
            self._diagnostics.clear()
            self._generation += 1
            try:
                self._proc = subprocess.Popen(self._command(mode), cwd=self.workspace, env=self._environment(),
                                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                              text=True, encoding="utf-8", errors="replace", bufsize=1,
                                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                                              | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
            except OSError as error:
                self._state, self._error = "error", str(error)
                raise HTTPException(503, str(error)) from error
            self._reader = threading.Thread(target=self._read_worker, args=(self._proc, self._generation),
                                            name="nova-voice-status", daemon=True)
            self._reader.start()

    async def start(self, request: Request):
        self._guard(request)
        async with self._action:
            if not self.nova_enabled():
                raise HTTPException(409, "Start Nova in Conversation before starting voice")
            ready = await self._readiness(force=True)
            if not ready.get("available"):
                raise HTTPException(503, ready.get("reason", "Voice is not ready"))
            self._launch("run")
        return self.snapshot()

    async def test(self, request: Request):
        self._guard(request)
        try:
            kind = (await request.json()).get("kind")
        except (ValueError, AttributeError):
            kind = None
        if kind not in {"microphone", "speaker"}:
            raise HTTPException(422, "Choose microphone or speaker test")
        async with self._action:
            ready = await self._readiness(force=True)
            if not ready.get("capabilities", {}).get(kind + "_test"):
                raise HTTPException(503, ready.get("reason", "Audio test is not ready"))
            self._launch(kind)
        return self.snapshot()

    def _send(self, command):
        with self._lock:
            proc = self._proc
            if proc is None or proc.poll() is not None:
                raise HTTPException(409, "Voice is not running")
            try:
                proc.stdin.write(json.dumps(command) + "\n")
                proc.stdin.flush()
            except (OSError, ValueError) as error:
                raise HTTPException(409, "Voice connection closed; restart voice") from error

    async def mute(self, request: Request):
        self._guard(request)
        try:
            payload = await request.json()
        except ValueError as error:
            raise HTTPException(422, "Invalid mute settings") from error
        if not isinstance(payload, dict) or not payload or set(payload) - {"microphone", "output"} or any(type(v) is not bool for v in payload.values()):
            raise HTTPException(422, "Mute settings must be microphone/output booleans")
        async with self._action:
            if self._mode != "run":
                raise HTTPException(409, "Mute is available during voice conversations; use Stop voice to cancel an audio test")
            self._send({"command": "mute", **payload})
        # Return confirmed state only; the worker acknowledgement arrives through status polling.
        return self.snapshot()

    def _stop_child(self):
        with self._lock:
            proc = self._proc
            if proc is None or proc.poll() is not None:
                self._state, self._stopping = "off", False
                return
            self._stopping, self._state = True, "stopping"
        try:
            self._send({"command": "stop"})
        except HTTPException:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Only the still-owned child tree is eligible; never kill a service by port/name.
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True,
                               timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            else:
                proc.kill()
            proc.wait(timeout=5)
        if self._reader and self._reader is not threading.current_thread():
            self._reader.join(timeout=1)
        with self._lock:
            self._proc, self._state, self._stopping = None, "off", False
            if self._test_result and self._test_result.get("state") == "running":
                self._test_result.update(state="cancelled", message="Audio test stopped")

    async def stop(self, request: Request):
        self._guard(request)
        async with self._action:
            try:
                await asyncio.to_thread(self._stop_child)
            except (OSError, subprocess.TimeoutExpired) as error:
                self._state, self._error = "error", f"Voice shutdown did not complete: {error}"
                raise HTTPException(503, self._error) from error
        return self.snapshot()

    async def close(self):
        async with self._action:
            await asyncio.to_thread(self._stop_child)
