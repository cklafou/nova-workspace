# Last updated: 2026-10-03 09:49:51
# @nova: LlamaControl — runtime/life-support control of her model server (llama.cpp on
#        :8080): health check, autostart, stop, restart. Bringing her mind up/down is a
#        bodily I/O act, so it belongs in HER runtime, never in a pluckable chat tool.
#        KoELS self-restart later extends restart() to relaunch with a chosen loadout
#        (--lora set) — this is the home the KoELS finding pointed at.
"""
nova_runtime/llama_control.py — relocated faithfully from general_tools/nova_chat/server.py
(`/api/llama/start|stop|status`, `/api/restart/server`, `_kill_port`, `_bg_llama_autostart`).
Lifecycle now waits for confirmed socket closure before stop/restart succeeds. It returns plain dicts instead of
FastAPI responses, so a face (or the runtime) can call it and render the result however it likes.

The Windows OS calls (`os.startfile`, PowerShell `Get-NetTCPConnection`) are injectable so the
decision logic is unit-testable off-Windows; defaults are the real ops.
"""

from nova_paths import body_path

import os
import sys
import subprocess
import socket
import threading
import urllib.request
from datetime import datetime
from pathlib import Path


def _hidden_si():
    """STARTUPINFO that hides any console the child creates.

    Deliberately NOT CREATE_NO_WINDOW. That flag means "no console AT ALL", so the child's own
    children then each allocate a fresh VISIBLE console — which is exactly how killing the
    watcher's console produced a storm of flashing git windows. Inheriting (or hiding) a console
    fixes the whole process tree; detaching from one just moves the problem down a generation."""
    if sys.platform != "win32":
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    return si


class LlamaControl:
    def __init__(self, workspace, port: int = 8080, launcher: str = "start_llama_qwen36.cmd",
                 startfile=None, runner=None, health=None):
        self._lifecycle_lock = threading.RLock()
        self._pending_start = 0.0
        self.workspace = Path(workspace)
        self.port = port
        self.launcher_path = self.workspace / launcher
        # Injectable for tests; default to the real OS ops. os.startfile only exists on
        # Windows, so guard it — on other platforms it's None until injected.
        self._startfile = startfile if startfile is not None else getattr(os, "startfile", None)
        self._run = runner if runner is not None else subprocess.run
        self._health = health   # optional () -> bool override for tests

    def is_running(self) -> bool:
        """True if llama-server answers /health on its port. Pure check — safe anywhere."""
        if self._health is not None:
            return bool(self._health())
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=1) as r:
                return r.status == 200
        except Exception:
            return False

    def _kill_port(self) -> None:
        # Stop only this model port and its specific batch launcher. Killing every
        # llama-server by name also killed the independent witness on port 8081.
        ps = ("Get-CimInstance Win32_Process -Filter \"Name='cmd.exe'\" | "
              f"Where-Object {{ $_.CommandLine -like '*{self.launcher_path.name}*' }} | "
              "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; "
              f"Get-NetTCPConnection -LocalPort {self.port} -State Listen -ErrorAction SilentlyContinue | "
              "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }")
        try:
            # Hidden, not console-less. The chat server owns a hidden console; PowerShell inherits
            # it. CREATE_NO_WINDOW would detach it and make its children pop windows instead.
            kw = {}
            if sys.platform == "win32" and self._run is subprocess.run:
                kw["startupinfo"] = _hidden_si()
            self._run(["powershell", "-Command", ps], capture_output=True, text=True,
                      encoding="utf-8", errors="replace", timeout=10, **kw)
        except Exception as error:
            raise RuntimeError(f"Could not stop model server: {error}") from error

    def _wait_stopped(self, timeout=10.0):
        """A kill request is not proof that the old listening socket has gone away."""
        import time
        deadline = time.monotonic() + timeout
        while True:
            with socket.socket() as connection:
                connection.settimeout(0.25)
                if connection.connect_ex(("127.0.0.1", self.port)) != 0:
                    return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.1)

    def start(self) -> dict:
        import time
        with self._lifecycle_lock:
            # A cold model answers /health with 503. A listening socket or a recent
            # accepted spawn still means Start must not create another instance.
            with socket.socket() as connection:
                connection.settimeout(0.25)
                listening = connection.connect_ex(("127.0.0.1", self.port)) == 0
            if listening or time.monotonic() - self._pending_start < 90:
                return {"ok": True, "message": "Model server is already running or starting.", "started": False}
            result = self._start()
            if result.get("ok"):
                self._pending_start = time.monotonic()
            return result

    def _start(self) -> dict:
        """Launch the llama launcher WITHOUT popping a console window.

        Was: os.startfile(...) — literally "double-click it", which spawned a visible cmd window
        every single time llama restarted (i.e. on every LoRA equip and every Full Restart).
        Now: spawn it detached with CREATE_NO_WINDOW and send its output to logs/llama/, which the
        Nova Console tails — so the restart is still fully visible, just in the llama-server tab
        instead of a new window. (self._startfile is kept ONLY as an injection point for tests
        and as a non-Windows fallback.)"""
        if self.is_running():
            return {"ok": True, "message": "Model server already running.", "started": False}
        if not self.launcher_path.exists():
            return {"ok": False, "error": f"{self.launcher_path.name} not found at {self.launcher_path}"}
        try:
            if sys.platform == "win32":
                log_dir = body_path('logs', workspace=self.workspace) / "llama"
                log_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime("%Y-%m-%d")
                lf = open(log_dir / f"llama-{stamp}.log", "a", encoding="utf-8", errors="replace")
                # Hidden console, NOT CREATE_NO_WINDOW: this cmd spawns llama-server.exe, which is
                # itself a console app. With no console, llama-server would allocate a visible one
                # on every LoRA equip. Hiding instead of detaching keeps the whole chain silent.
                subprocess.Popen(
                    ["cmd", "/c", str(self.launcher_path)],
                    cwd=str(self.workspace),
                    stdout=lf, stderr=subprocess.STDOUT,
                    startupinfo=_hidden_si(),
                )
            elif self._startfile is not None:
                self._startfile(str(self.launcher_path))
            else:
                return {"ok": False, "error": "no way to launch on this platform"}
            return {"ok": True, "started": True, "message": f"llama-server starting on port {self.port}…"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def stop(self) -> dict:
        with self._lifecycle_lock:
            self._pending_start = 0.0
            return self._stop()

    def _stop(self) -> dict:
        try:
            self._kill_port()
            if not self._wait_stopped():
                return {"ok": False, "error": f"Model port {self.port} did not close after stop."}
            return {"ok": True, "message": "llama-server stopped."}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def restart(self) -> dict:
        """Kill the model server, then relaunch it. (KoELS self-restart will extend this to
        relaunch with a chosen loadout; for now it relaunches the standard launcher.)"""
        with self._lifecycle_lock:
            try:
                self._pending_start = 0.0
                self._kill_port()
                if not self._wait_stopped():
                    return {"ok": False, "started": False,
                            "error": f"Model port {self.port} did not close; restart was not performed."}
                result = self._start()
                if result.get("ok") and result.get("started") is not False:
                    import time
                    self._pending_start = time.monotonic()
                elif result.get("started") is False:
                    return {"ok": False, "started": False, "error": "Another model occupied the port before relaunch."}
                return result
            except Exception as error:
                return {"ok": False, "error": str(error)}

    def autostart(self) -> dict:
        """Boot-time life-support: start the model server only if it isn't already up."""
        if self.is_running():
            return {"ok": True, "message": "already running", "started": False}
        res = self.start()
        res.setdefault("started", bool(res.get("ok")))
        return res
