"""
eyes_pane.py — Nova's live desktop view panel.

Displays a ~5fps JPEG stream of what Nova sees on-screen, with a mouse
cursor overlay showing her pointer position. Independent of Cole's own
mouse — both can operate simultaneously (dual-cursor).

Activation: clicking Start fires POST /api/eyes/start on the nova_chat
server, which launches a background screenshot task. Frames arrive over
the existing WebSocket as {"type": "eyes_frame", ...} broadcasts and are
routed here via the ws.raw signal → on_raw() slot.
"""
import base64
import time
import requests
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QBrush

from .theme import NOVA, TEXT_DIM, BG_ALT, BORDER, SUCCESS, ERROR

BASE_URL = "http://127.0.0.1:8765"


class EyesPane(QWidget):
    """
    Live desktop feed.

    Server sends:
      {"type": "eyes_frame", "data": "<base64 jpeg>",
       "mouse": [x_frac, y_frac], "timestamp": <float>}

    mouse coords are normalized (0.0–1.0) relative to the full screenshot
    size, so they scale correctly when the pane is resized.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._streaming        = False
        self._last_frame_ts    = 0.0
        self._fps_frame_count  = 0
        self._current_pixmap   = None   # last rendered QPixmap (for resize)
        self._mouse_frac       = None   # (x_frac, y_frac) or None

        self._build_ui()

    # ── UI ─────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        header = QHBoxLayout()
        header.setContentsMargins(8, 6, 8, 6)
        header.setSpacing(8)

        ttl = QLabel("👁  Nova Eyes")
        ttl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; font-weight: 600;")
        header.addWidget(ttl)
        header.addStretch()

        self._fps_label = QLabel("")
        self._fps_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
        header.addWidget(self._fps_label)

        self._toggle_btn = QPushButton("▶  Start")
        self._toggle_btn.setFixedSize(72, 24)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_btn_style(active=False)
        self._toggle_btn.clicked.connect(self._on_toggle)
        header.addWidget(self._toggle_btn)

        lay.addLayout(header)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER};")
        lay.addWidget(sep)

        # Frame canvas
        self._canvas = FrameCanvas()
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay.addWidget(self._canvas, 1)

        # Action strip — shows Nova's last directive
        self._action_label = QLabel("")
        self._action_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._action_label.setStyleSheet(f"""
            QLabel {{
                background: #0a0a14;
                color: {NOVA};
                font-size: 10px;
                font-family: "Consolas", monospace;
                padding: 0 8px;
                border-top: 1px solid {BORDER};
            }}
        """)
        self._action_label.setFixedHeight(20)
        lay.addWidget(self._action_label)

        # FPS counter — updates once per second
        self._fps_timer = QTimer(self)
        self._fps_timer.setInterval(1000)
        self._fps_timer.timeout.connect(self._tick_fps)

    # ── Public slot — WS raw events ────────────────────────────────────────────
    def on_raw(self, data: dict):
        """Receives all raw WS events; filters to eyes_frame and nova_activity."""
        t = data.get("type", "")

        if t == "eyes_frame":
            b64   = data.get("data", "")
            mouse = data.get("mouse")   # [x_frac, y_frac] or None
            if b64:
                self._render_frame(b64, mouse)

        elif t == "nova_activity":
            directive = data.get("directive", "")
            detail    = data.get("detail", "")
            self._action_label.setText(f"⚡ [{directive}] {detail}")

    # ── Frame rendering ────────────────────────────────────────────────────────
    def _render_frame(self, b64: str, mouse):
        try:
            raw_bytes = base64.b64decode(b64)
        except Exception:
            return

        pix = QPixmap()
        if not pix.loadFromData(raw_bytes, "JPEG"):
            return

        mouse_frac = None
        if mouse and len(mouse) == 2:
            mouse_frac = (float(mouse[0]), float(mouse[1]))

        self._canvas.set_frame(pix, mouse_frac)

        self._fps_frame_count += 1
        self._last_frame_ts = time.time()

    # ── Streaming control ──────────────────────────────────────────────────────
    def _on_toggle(self):
        if self._streaming:
            self._stop()
        else:
            self._start()

    def _start(self):
        try:
            requests.post(f"{BASE_URL}/api/eyes/start", timeout=3)
        except Exception as e:
            self._canvas.set_message(f"⚠ Server error: {e}")
            return
        self._streaming = True
        self._apply_btn_style(active=True)
        self._canvas.set_message("Connecting…")
        self._fps_timer.start()

    def _stop(self):
        try:
            requests.post(f"{BASE_URL}/api/eyes/stop", timeout=3)
        except Exception:
            pass
        self._streaming = False
        self._fps_timer.stop()
        self._fps_label.setText("")
        self._apply_btn_style(active=False)
        self._canvas.set_message("Feed stopped — click ▶ Start")
        self._action_label.setText("")

    # ── FPS counter ────────────────────────────────────────────────────────────
    def _tick_fps(self):
        fps = self._fps_frame_count
        self._fps_frame_count = 0
        stalled = self._streaming and (time.time() - self._last_frame_ts) > 3
        if stalled:
            self._fps_label.setStyleSheet(f"color: {ERROR}; font-size: 10px;")
            self._fps_label.setText("stalled")
        elif fps > 0:
            self._fps_label.setStyleSheet(f"color: {SUCCESS}; font-size: 10px;")
            self._fps_label.setText(f"{fps} fps")
        else:
            self._fps_label.setText("")

    # ── Button style ───────────────────────────────────────────────────────────
    def _apply_btn_style(self, active: bool):
        if active:
            self._toggle_btn.setText("■  Stop")
            self._toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {NOVA}22;
                    color: {NOVA};
                    border: 1px solid {NOVA}66;
                    border-radius: 4px;
                    font-size: 10px;
                }}
                QPushButton:hover {{ background: {NOVA}44; }}
            """)
        else:
            self._toggle_btn.setText("▶  Start")
            self._toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {TEXT_DIM};
                    border: 1px solid {BORDER};
                    border-radius: 4px;
                    font-size: 10px;
                }}
                QPushButton:hover {{ color: #f0f0f0; border-color: #555; }}
            """)


class FrameCanvas(QWidget):
    """
    Custom widget that paints the JPEG frame + mouse cursor overlay.
    Using paintEvent rather than a QLabel so we control exact pixel placement
    of the cursor dot and can repaint on resize without re-decoding the image.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap     = None
        self._mouse_frac = None   # (x_frac, y_frac)
        self._message    = "No feed — click ▶ Start"
        self.setStyleSheet(f"background: {BG_ALT};")

    def set_frame(self, pixmap: QPixmap, mouse_frac):
        self._pixmap     = pixmap
        self._mouse_frac = mouse_frac
        self._message    = None
        self.update()   # trigger paintEvent

    def set_message(self, text: str):
        self._pixmap  = None
        self._message = text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if self._pixmap is None:
            # Show placeholder text
            painter.fillRect(0, 0, w, h, QColor(BG_ALT))
            if self._message:
                painter.setPen(QColor(TEXT_DIM))
                painter.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, self._message)
            painter.end()
            return

        # Scale pixmap to fit, centred
        scaled = self._pixmap.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x_off = (w - scaled.width())  // 2
        y_off = (h - scaled.height()) // 2

        painter.fillRect(0, 0, w, h, QColor(BG_ALT))
        painter.drawPixmap(x_off, y_off, scaled)

        # Mouse cursor overlay
        if self._mouse_frac:
            mx = x_off + int(self._mouse_frac[0] * scaled.width())
            my = y_off + int(self._mouse_frac[1] * scaled.height())

            # White halo
            painter.setPen(QPen(QColor(255, 255, 255, 160), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPoint(mx, my), 9, 9)

            # Nova-coloured centre dot
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(NOVA)))
            painter.drawEllipse(QPoint(mx, my), 4, 4)

        painter.end()
