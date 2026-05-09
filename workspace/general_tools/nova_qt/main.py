"""
main.py — Entry point for the Nova Qt desktop app.

Usage (dev, no rebuild):
    python general_tools/NovaLauncher.py
    -- or --
    python -m nova_qt.main   (from workspace/)

The server (FastAPI + WS on port 8765) is started by NovaLauncher.py
before this function is called. main() just opens the window.

Window rendering priority:
  1. pywebview  — uses Windows Edge WebView2 (built into Win10/11, no install).
                  Renders index.html at full CSS/JS quality. Best option.
  2. QWebEngineView — Chromium inside Qt. Requires PyQt6-WebEngine.
  3. Qt widgets — native fallback, no external deps but limited visual quality.
  4. System browser — last resort if PyQt6 is missing entirely.
"""
import sys
import os

# Ensure nova_qt can be imported from workspace/general_tools/
_here = os.path.dirname(os.path.abspath(__file__))
_general = os.path.dirname(_here)
if _general not in sys.path:
    sys.path.insert(0, _general)

CHAT_URL = "http://127.0.0.1:8765"


def run_qt_window():
    """
    Launch the Nova window. Blocks until closed.
    Called by NovaLauncher.py after servers are ready.
    """

    # ── 1. pywebview — Edge WebView2, built into Win10/11 ────────────────────
    try:
        import webview

        print("[nova_qt] Using pywebview (Edge WebView2) — full HTML UI active.")

        # Build kwargs — context_menu was added in pywebview 5.x; ignore on older versions
        _wv_kwargs = dict(
            title            = "Project Nova",
            url              = CHAT_URL,
            width            = 1440,
            height           = 920,
            min_size         = (960, 640),
            background_color = "#080810",
            text_select      = True,
        )
        try:
            import inspect as _ins
            if "context_menu" in _ins.signature(webview.create_window).parameters:
                _wv_kwargs["context_menu"] = True
        except Exception:
            pass
        window = webview.create_window(**_wv_kwargs)

        # On window close, shut down the nova_chat server
        def _on_closed():
            try:
                import requests as _req
                _req.post("http://127.0.0.1:8765/shutdown", timeout=2)
            except Exception:
                pass

        window.events.closed += _on_closed

        webview.start(debug=False)
        return

    except ImportError:
        print("[nova_qt] pywebview not installed.")
        print("[nova_qt] Run:  python -m pip install pywebview")

    except Exception as e:
        print(f"[nova_qt] pywebview failed: {e}")

    # ── 2. QWebEngineView inside Qt ───────────────────────────────────────────
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
    except ImportError:
        # No PyQt6 at all — open browser and block
        print("[nova_qt] PyQt6 not installed. Run Install_Nova_Qt.cmd")
        import webbrowser
        webbrowser.open(CHAT_URL)
        try:
            input(f"Nova is running at {CHAT_URL} — Press Enter to stop.")
        except (RuntimeError, EOFError):
            import time
            while True:
                time.sleep(60)
        return

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Project Nova")
    app.setOrganizationName("Nova")

    try:
        from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: availability check
        from .webview_window import NovaWebWindow

        app.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        print("[nova_qt] Using QWebEngineView — full HTML UI active.")
        window = NovaWebWindow(CHAT_URL)
        window.show()
        app.exec()
        return

    except ImportError:
        print("[nova_qt] PyQt6-WebEngine not installed — using Qt widget fallback.")
        print("[nova_qt] For modern UI: python -m pip install pywebview")

    except Exception as e:
        print(f"[nova_qt] QWebEngineView failed: {e}")

    # ── 3. Native Qt widget window ────────────────────────────────────────────
    from PyQt6.QtGui import QFont
    from .theme  import apply_palette, STYLESHEET
    from .window import NovaWindow

    print("[nova_qt] Using Qt widget window (fallback).")
    app.setStyle("Fusion")
    apply_palette(app)
    app.setStyleSheet(STYLESHEET)
    app.setFont(QFont("Segoe UI", 10))

    window = NovaWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    # Standalone: start server then open window
    import threading, time

    def _start_server():
        import asyncio, uvicorn
        sys.path.insert(0, os.path.join(_general, "nova_body"))
        from nova_chat.server import app
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="warning")
        server = uvicorn.Server(config)
        loop.run_until_complete(server.serve())

    srv = threading.Thread(target=_start_server, daemon=True)
    srv.start()

    import socket
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            s = socket.create_connection(("127.0.0.1", 8765), 0.5)
            s.close()
            break
        except OSError:
            time.sleep(0.3)

    run_qt_window()
