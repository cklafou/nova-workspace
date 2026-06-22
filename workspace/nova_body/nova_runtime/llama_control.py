# Last updated: 2026-06-22 18:56:08
# @nova: LlamaControl — runtime/life-support control of her model server (llama.cpp on
#        :8080): health check, autostart, stop, restart. Bringing her mind up/down is a
#        bodily I/O act, so it belongs in HER runtime, never in a pluckable chat tool.
#        KoELS self-restart later extends restart() to relaunch with a chosen loadout
#        (--lora set) — this is the home the KoELS finding pointed at.
"""
nova_runtime/llama_control.py — relocated faithfully from general_tools/nova_chat/server.py
(`/api/llama/start|stop|status`, `/api/restart/server`, `_kill_port`, `_bg_llama_autostart`).
Behavior is unchanged; it just lives in the body now and returns plain dicts instead of
FastAPI responses, so a face (or the runtime) can call it and render the result however it likes.

The Windows OS calls (`os.startfile`, PowerShell `Get-NetTCPConnection`) are injectable so the
decision logic is unit-testable off-Windows; defaults are the real ops.
"""

import os
import subprocess
import urllib.request
from pathlib import Path


class LlamaControl:
    def __init__(self, workspace, port: int = 8080, launcher: str = "start_llama.cmd",
                 startfile=None, runner=None, health=None):
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
        # Kill whatever holds the port AND any llama-server by name. The port-only kill
        # (Get-NetTCPConnection -> Stop-Process by OwningProcess) can miss the real process
        # on some setups — the restart live-test (2026-06-01) caught it not killing llama —
        # so we also stop it by name. Belt-and-suspenders, and what KoELS self-restart relies on.
        ps = (f"Get-NetTCPConnection -LocalPort {self.port} -ErrorAction SilentlyContinue | "
              "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }; "
              "Stop-Process -Name llama-server -Force -ErrorAction SilentlyContinue")
        try:
            self._run(["powershell", "-Command", ps], capture_output=True, text=True,
                      encoding="utf-8", errors="replace", timeout=10)
        except Exception:
            pass

    def start(self) -> dict:
        """Launch start_llama.cmd in its own console (os.startfile == double-click)."""
        if not self.launcher_path.exists():
            return {"ok": False, "error": f"{self.launcher_path.name} not found at {self.launcher_path}"}
        if self._startfile is None:
            return {"ok": False, "error": "startfile unavailable on this platform"}
        try:
            self._startfile(str(self.launcher_path))
            return {"ok": True, "message": f"llama-server starting on port {self.port}…"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def stop(self) -> dict:
        try:
            self._kill_port()
            return {"ok": True, "message": "llama-server stopped."}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def restart(self) -> dict:
        """Kill the model server, then relaunch it. (KoELS self-restart will extend this to
        relaunch with a chosen loadout; for now it relaunches the standard launcher.)"""
        self._kill_port()
        return self.start()

    def autostart(self) -> dict:
        """Boot-time life-support: start the model server only if it isn't already up."""
        if self.is_running():
            return {"ok": True, "message": "already running", "started": False}
        res = self.start()
        res["started"] = bool(res.get("ok"))
        return res
