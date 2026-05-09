"""
NovaLauncher.py  (fixed)
========================
Unified launcher for Project Nova.

Fixes vs previous version:
  - PyInstaller freeze guard (multiprocessing.freeze_support) prevents recursive spawn
  - nova_gateway runs IN-PROCESS via uvicorn.Server (not subprocess) so sys.executable
    loop can't happen
  - pywebview failure is caught cleanly and falls back to one browser tab, not 194

Requirements:
  pip install pywebview

Build to Nova.exe:
  pip install pyinstaller
  python build_nova.py
"""

import multiprocessing
multiprocessing.freeze_support()   # MUST be first — prevents PyInstaller recursive spawn

import sys
import threading
import time
import asyncio
import logging
from pathlib import Path

# ── Resolve paths — works both as plain script and as PyInstaller bundle ──────
if getattr(sys, 'frozen', False):
    # Inside a PyInstaller bundle.
    # sys._MEIPASS is the temp extraction dir; bundled packages live under
    # _MEIPASS/nova_body/ and _MEIPASS/general_tools/ per the spec.
    _MEIPASS = Path(sys._MEIPASS)
    for _p in [str(_MEIPASS / "nova_body"), str(_MEIPASS / "general_tools")]:
        if _p not in sys.path:
            sys.path.insert(0, _p)
    _EXE_DIR = Path(sys.executable).resolve().parent
    # Support two build layouts:
    #   One-file build:  Nova.exe lives directly in workspace root
    #                    => _WS = _EXE_DIR
    #   Directory build: Nova.exe lives at workspace/_build/Nova/Nova.exe
    #                    => _WS = _EXE_DIR.parent.parent
    # Detect by checking whether workspace marker files exist in _EXE_DIR.
    if (_EXE_DIR / "nova_body").exists() or (_EXE_DIR / "general_tools").exists():
        _WS = _EXE_DIR          # one-file, exe is in workspace root
    else:
        _WS = _EXE_DIR.parent.parent  # directory build
else:
    # Plain script: NovaLauncher.py lives at workspace/general_tools/NovaLauncher.py
    _TOOLS = Path(__file__).resolve().parent
    _ws_root = _TOOLS.parent
    # Insert in reverse priority order (each insert goes to [0]), so the final
    # sys.path order is: workspace_root, nova_body, general_tools, ...
    # workspace_root exposes nova_lancedb/; nova_body/ exposes nova_memory/ (session manager).
    # The two packages are now uniquely named — no collision.
    for _p in [str(_ws_root / "general_tools"), str(_ws_root / "nova_body"), str(_ws_root)]:
        if _p not in sys.path:
            sys.path.insert(0, _p)
    _WS = _TOOLS.parent
    _EXE_DIR = _TOOLS

# ── Logging — always write to workspace/logs/ regardless of frozen/script mode ─
_LOG_DIR = _WS / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "nova_launcher.log"

_handlers = [logging.FileHandler(_LOG_FILE, encoding="utf-8")]
if not getattr(sys, 'frozen', False):
    _handlers.append(logging.StreamHandler())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=_handlers,
)
log = logging.getLogger("NovaLauncher")
log.info("NovaLauncher starting. frozen=%s  sys.path[0]=%s", getattr(sys, 'frozen', False), sys.path[0])

# Expose the real workspace root so server.py can find nova_gateway_runner.py
# even when running as a frozen bundle where __file__ paths are inside _internal/.
import os as _os
_os.environ.setdefault("NOVA_WORKSPACE", str(_WS))

CHAT_URL  = "http://127.0.0.1:8765"
CHAT_PORT = 8765
GW_PORT   = 18790

try:
    import webview
    WEBVIEW_AVAILABLE = True
except ImportError:
    WEBVIEW_AVAILABLE = False
    log.warning("pywebview not installed — will open in browser. Run: pip install pywebview")


# ── Server runners (in-process, each in its own thread + event loop) ──────────

def run_nova_chat():
    """Start nova_chat FastAPI server in this thread."""
    try:
        import uvicorn
        from nova_chat.server import app
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        config = uvicorn.Config(app, host="127.0.0.1", port=CHAT_PORT, log_level="warning")
        server = uvicorn.Server(config)
        loop.run_until_complete(server.serve())
    except Exception as e:
        log.error("nova_chat server error: %s", e, exc_info=True)


def run_nova_gateway():
    """
    Start nova gateway FastAPI server in this thread.
    Runs in-process — no subprocess, no sys.executable recursion.
    Imports from general_tools/gateway.py (dissolved from nova_gateway, 2026-05-08).
    """
    try:
        from gateway import app as gw_app
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        import uvicorn
        config = uvicorn.Config(gw_app, host="127.0.0.1", port=GW_PORT, log_level="warning")
        server = uvicorn.Server(config)
        loop.run_until_complete(server.serve())
    except Exception as e:
        log.error("nova_gateway server error: %s", e, exc_info=True)


def wait_for_port(port: int, timeout: float = 20.0) -> bool:
    """Poll until the port accepts connections or we time out."""
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=0.5)
            s.close()
            return True
        except OSError:
            time.sleep(0.3)
    return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 52)
    print("  PROJECT NOVA")
    print("  Starting servers...")
    print("=" * 52)
    print()

    # Start both servers in daemon threads (die with the main process)
    chat_thread = threading.Thread(target=run_nova_chat,    daemon=True, name="nova_chat")
    gw_thread   = threading.Thread(target=run_nova_gateway, daemon=True, name="nova_gateway")
    chat_thread.start()
    gw_thread.start()

    log.info("Waiting for nova_chat on port %d...", CHAT_PORT)
    if not wait_for_port(CHAT_PORT, timeout=25):
        log.error("nova_chat didn't start in 25s. Check for errors above.")
        try:
            input("Press Enter to exit...")
        except (RuntimeError, EOFError):
            time.sleep(5)
        return

    log.info("Servers ready. Opening Nova Qt window...")

    # ── PyQt6 native window (replaces pywebview) ──────────────────────────────
    try:
        from nova_qt.main import run_qt_window
        run_qt_window()   # blocks until window is closed
        log.info("Window closed.")
    except Exception as e:
        log.error("nova_qt failed (%s) — falling back to browser.", e, exc_info=True)
        import webbrowser
        webbrowser.open(CHAT_URL)
        try:
            input("Nova is running at http://127.0.0.1:8765 — Press Enter to stop.")
        except (RuntimeError, EOFError):
            while True:
                time.sleep(60)

    # Graceful shutdown: ask gateway to stop
    try:
        import urllib.request
        urllib.request.urlopen(
            urllib.request.Request(f"http://127.0.0.1:{GW_PORT}/shutdown",
                                   method="POST"), timeout=2
        )
    except Exception:
        pass

    log.info("Nova stopped.")


if __name__ == "__main__":
    main()