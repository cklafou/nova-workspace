"""
Nova Group Chat - Launcher
==========================
Double-click NovaChatLauncher.exe  or  run: python tools/nova_chat/launch.py

Two guards prevent .exe bomb loops:
  1. Lock file: if another launcher process is alive, exit immediately.
  2. Port check: if the server is already running, just open the browser.
"""
import os
import sys
import time
import socket
import subprocess
import webbrowser
from pathlib import Path

TOOLS_DIR = Path(__file__).parent.parent
PORT      = 8765
HOST      = "127.0.0.1"
URL       = "http://{}:{}".format(HOST, PORT)
LOCK_FILE = Path(__file__).parent / ".launcher.lock"


# ── Guard 1: single-instance lock ─────────────────────────────────────────────

def _acquire_lock():
    """Return True if we got the lock, False if another launcher is running."""
    try:
        if LOCK_FILE.exists():
            try:
                pid = int(LOCK_FILE.read_text().strip())
                import ctypes
                h = ctypes.windll.kernel32.OpenProcess(0x100000, False, pid)
                if h:
                    ctypes.windll.kernel32.CloseHandle(h)
                    return False   # other process still alive
            except Exception:
                pass   # stale lock, overwrite it
        LOCK_FILE.write_text(str(os.getpid()))
        return True
    except Exception:
        return True    # can't create lock — proceed anyway


def _release_lock():
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass


# ── Guard 2: server already running ───────────────────────────────────────────

def _server_is_running():
    try:
        s = socket.create_connection((HOST, PORT), timeout=1)
        s.close()
        return True
    except Exception:
        return False


# ── Write the runner script executed inside the new terminal ──────────────────

def _write_runner():
    runner = Path(__file__).parent / "server_runner.py"
    tools_path = str(TOOLS_DIR)
    runner.write_text(
        "\n".join([
            "import sys",
            "from pathlib import Path",
            "sys.path.insert(0, r'" + tools_path + "')",
            "",
            "import uvicorn",
            "from nova_chat.server import app",
            "",
            "print()",
            "print('=' * 52)",
            "print('  NOVA GROUP CHAT  --  http://" + HOST + ":" + str(PORT) + "')",
            "print('  Close this window to stop the server.')",
            "print('=' * 52)",
            "print()",
            "",
            "uvicorn.run(app, host='" + HOST + "', port=" + str(PORT) + ", log_level='info')",
            "",
        ]),
        encoding="utf-8",
    )
    return runner


# ── Spawn server in a new visible terminal ────────────────────────────────────

def _spawn_server(runner):
    python = sys.executable
    if sys.platform == "win32":
        subprocess.Popen(
            'start "Nova Chat Server" cmd /k ""' + python + '" "' + str(runner) + '""',
            shell=True,
        )
    else:
        cmd = '"' + python + '" "' + str(runner) + '"'
        for term in [
            ["gnome-terminal", "--", "bash", "-c", cmd + "; exec bash"],
            ["xterm", "-title", "Nova Chat Server", "-e", cmd],
            ["konsole", "-e", cmd],
        ]:
            try:
                subprocess.Popen(term)
                return
            except FileNotFoundError:
                continue
        subprocess.Popen([python, str(runner)], start_new_session=True)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    # Guard 1: only one launcher at a time
    if not _acquire_lock():
        if _server_is_running():
            webbrowser.open(URL)
        sys.exit(0)

    try:
        # Guard 2: server already up — just open the browser
        if _server_is_running():
            print("  Server already running at " + URL)
            webbrowser.open(URL)
            return

        runner = _write_runner()
        _spawn_server(runner)

        # Wait up to 8s for the server to become ready
        print("  Waiting for server", end="", flush=True)
        for _ in range(24):
            time.sleep(0.35)
            print(".", end="", flush=True)
            if _server_is_running():
                break
        if _server_is_running():
            print(" ready")
            webbrowser.open(URL)
            print("  Opened " + URL)
        else:
            print(" timed out")
            print("  ERROR: Server did not start. Check the server terminal for errors.")

    finally:
        _release_lock()


if __name__ == "__main__":
    main()
