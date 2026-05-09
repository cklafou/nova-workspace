"""
webview_window.py — Nova Chat rendered via QWebEngineView (Chromium).

Replaces the native Qt widget window with a full HTML/CSS/JS render of
http://127.0.0.1:8765 — the nova_chat FastAPI server's index.html.

Why this approach:
  Native Qt widgets can't match modern web UI quality. Switching to
  QWebEngineView gives us full CSS variables, animations, flexbox/grid,
  WebSocket, and fetch — so the carefully designed index.html is what
  the user actually sees.

Install requirement (one-time):
  pip install PyQt6-WebEngine
  (also handled by Install_Nova_Qt.cmd)
"""

from PyQt6.QtWidgets import QMainWindow, QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings
from PyQt6.QtCore import QUrl, Qt, QTimer, QSize
from PyQt6.QtGui import QKeySequence, QShortcut, QIcon


CHAT_URL = "http://127.0.0.1:8765"


class NovaWebWindow(QMainWindow):
    """
    Thin native Qt shell around a QWebEngineView.

    The window provides OS-native chrome (title bar, minimize/maximize/close,
    taskbar icon, window snapping). Everything inside the window is rendered
    by the Chromium engine from the nova_chat server's HTML/CSS/JS.
    """

    def __init__(self, url: str = CHAT_URL):
        super().__init__()
        self._url = url
        self.setWindowTitle("Project Nova")
        self.resize(1440, 920)
        self.setMinimumSize(960, 640)

        # ── WebEngine profile — disable disk cache so index.html edits are live ──
        profile = QWebEngineProfile.defaultProfile()
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
        )

        # ── Settings ──────────────────────────────────────────────────────────────
        settings = profile.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)

        # ── WebView ───────────────────────────────────────────────────────────────
        self._view = QWebEngineView()
        # Enable right-click context menu (Copy / Paste / Inspect)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self._view.setUrl(QUrl(url))
        self._view.titleChanged.connect(self._on_title_changed)
        self._view.loadFinished.connect(self._on_load_finished)

        # Dark background while the page loads so there's no white flash
        self._view.setStyleSheet("background: #080810;")
        self._view.page().setBackgroundColor(Qt.GlobalColor.transparent)

        self.setCentralWidget(self._view)

        # ── Keyboard shortcuts ────────────────────────────────────────────────────
        QShortcut(QKeySequence("F5"),       self, self._reload)
        QShortcut(QKeySequence("Ctrl+R"),   self, self._reload)
        QShortcut(QKeySequence("Ctrl+W"),   self, self.close)
        QShortcut(QKeySequence("F12"),      self, self._open_devtools)
        QShortcut(QKeySequence("Ctrl+F12"), self, self._open_devtools)

    # ── Private helpers ───────────────────────────────────────────────────────────

    def _on_title_changed(self, title: str):
        self.setWindowTitle(title or "Project Nova")

    def _on_load_finished(self, ok: bool):
        if not ok:
            # Server may not be ready yet — retry after 1s
            QTimer.singleShot(1000, lambda: self._view.setUrl(QUrl(self._url)))

    def _reload(self):
        self._view.reload()

    def _open_devtools(self):
        """Open Chromium DevTools in a separate window (useful for debugging)."""
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView as _V
            dev = _V()
            self._view.page().setDevToolsPage(dev.page())
            dev.resize(1200, 800)
            dev.setWindowTitle("Nova DevTools")
            dev.show()
            self._devtools = dev   # keep reference
        except Exception:
            pass

    # ── Window events ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        """Shut down the nova_chat server on window close."""
        try:
            import requests as _req
            _req.post("http://127.0.0.1:8765/shutdown", timeout=2)
        except Exception:
            pass
        event.accept()
