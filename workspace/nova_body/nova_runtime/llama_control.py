# Last updated: 2026-07-19 00:10:56
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
import sys
import subprocess
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
        # 2026-07-18 (watchdog): kill the LAUNCHER CMD *FIRST*, before its llama-server child.
        # cmd.exe re-reads its batch file by byte offset whenever a child returns; an orphaned
        # launcher cmd resuming after we kill llama-server executes garbled line fragments
        # (receipt in logs/llama/: 'COREKOELS_LORA"' is not recognized...), loses NOVA_EXTRA,
        # and relaunches llama-server BARE (no --lora) — and its instance binds :8080 before the
        # legitimate relaunch, which then dies on the busy port. Net effect: every restart
        # silently stripped her personality adapter (the launcher's "worst class of bug: a
        # SILENT one", via a second path). Killing the parent cmd first leaves nothing to
        # resume when the server dies.
        ps = ("Get-CimInstance Win32_Process -Filter \"Name='cmd.exe'\" | "
              f"Where-Object {{ $_.CommandLine -like '*{self.launcher_path.name}*' }} | "
              "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; "
              f"Get-NetTCPConnection -LocalPort {self.port} -ErrorAction SilentlyContinue | "
              "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }; "
              "Stop-Process -Name llama-server -Force -ErrorAction SilentlyContinue")
        try:
            # Hidden, not console-less. The chat server owns a hidden console; PowerShell inherits
            # it. CREATE_NO_WINDOW would detach it and make its children pop windows instead.
            kw = {}
            if sys.platform == "win32" and self._run is subprocess.run:
                kw["startupinfo"] = _hidden_si()
            self._run(["powershell", "-Command", ps], capture_output=True, text=True,
                      encoding="utf-8", errors="replace", timeout=10, **kw)
        except Exception:
            pass

    def start(self) -> dict:
        """Launch the llama launcher WITHOUT popping a console window.

        Was: os.startfile(...) — literally "double-click it", which spawned a visible cmd window
        every single time llama restarted (i.e. on every LoRA equip and every Full Restart).
        Now: spawn it detached with CREATE_NO_WINDOW and send its output to logs/llama/, which the
        Nova Console tails — so the restart is still fully visible, just in the llama-server tab
        instead of a new window. (self._startfile is kept ONLY as an injection point for tests
        and as a non-Windows fallback.)"""
        if not self.launcher_path.exists():
            return {"ok": False, "error": f"{self.launcher_path.name} not found at {self.launcher_path}"}
        try:
            if sys.platform == "win32":
                log_dir = self.workspace / "logs" / "llama"
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
