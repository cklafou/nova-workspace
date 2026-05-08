"""
main.py — Entry point for the Nova Qt desktop app.

Usage (dev, no rebuild):
    python general_tools/NovaLauncher.py
    -- or --
    python -m nova_qt.main   (from workspace/)

The server (FastAPI + WS on port 8765) is started by NovaLauncher.py
before this function is called. main() just opens the Qt window.
"""
import sys
import os

# Ensure nova_qt can be imported from workspace/general_tools/
_here = os.path.dirname(os.path.abspath(__file__))
_general = os.path.dirname(_here)
if _general not in sys.path:
    sys.path.insert(0, _general)


def run_qt_window():
    """
    Launch the Nova Qt main window. Blocks until the window is closed.
    Called by NovaLauncher.py after servers are ready.
    """
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QFont
    except ImportError:
        print("PyQt6 not installed. Run: pip install PyQt6")
        print("Falling back to browser...")
        import webbrowser
        webbrowser.open("http://127.0.0.1:8765")
        try:
            input("Nova is running at http://127.0.0.1:8765 — Press Enter to stop.")
        except (RuntimeError, EOFError):
            import time
            while True:
                time.sleep(60)
        return

    from .theme  import apply_palette, STYLESHEET
    from .window import NovaWindow

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Project Nova")
    app.setOrganizationName("Nova")
    app.setStyle("Fusion")   # base style — our stylesheet overrides colors

    apply_palette(app)
    app.setStyleSheet(STYLESHEET)

    # Default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

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

    # Wait for server
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
