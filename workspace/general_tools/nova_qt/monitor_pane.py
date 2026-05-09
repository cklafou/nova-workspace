"""
monitor_pane.py — Real-time system monitor for Nova Qt.

Shows live stats for every AI in the group chat:
  - Generation timing, token counts, rate
  - Current depth / autonomous mode state
  - Error log
  - Server connection status

All data comes from existing WebSocket events — no server changes needed.
"""
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea, QSizePolicy, QPushButton
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from .theme import NOVA, CLAUDE, GEMINI, COLE, TEXT_DIM, BG_ALT, BG_CARD, BORDER, SUCCESS, ERROR, TEXT


# ── Small stat card ────────────────────────────────────────────────────────────
class StatCard(QFrame):
    def __init__(self, label: str, value: str = "—", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 6px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(2)

        self._lbl = QLabel(label.upper())
        self._lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 9px; font-weight: 600; letter-spacing: 0.08em;")

        self._val = QLabel(value)
        self._val.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 600;")
        self._val.setFont(QFont("Consolas", 12))

        lay.addWidget(self._lbl)
        lay.addWidget(self._val)

    def set_value(self, v: str, color: str = None):
        self._val.setText(v)
        c = color or TEXT
        self._val.setStyleSheet(f"color: {c}; font-size: 13px; font-weight: 600;")


# ── Per-agent generation row ───────────────────────────────────────────────────
class AgentRow(QFrame):
    def __init__(self, name: str, color: str, parent=None):
        super().__init__(parent)
        self.name = name
        self._active = False
        self._start_ts = 0.0

        self.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 6px;
            }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(12)

        dot = QLabel("●")
        dot.setFixedWidth(14)
        dot.setStyleSheet(f"color: {color}; font-size: 12px;")

        name_lbl = QLabel(name)
        name_lbl.setFixedWidth(56)
        name_lbl.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600;")

        self._status = QLabel("idle")
        self._status.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
        self._status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._stats = QLabel("")
        self._stats.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; font-family: Consolas;")
        self._stats.setAlignment(Qt.AlignmentFlag.AlignRight)

        lay.addWidget(dot)
        lay.addWidget(name_lbl)
        lay.addWidget(self._status, 1)
        lay.addWidget(self._stats)

    def set_generating(self):
        self._active = True
        self._start_ts = time.time()
        self._status.setText("generating…")
        self._status.setStyleSheet(f"color: {NOVA}; font-size: 11px;")
        self._stats.setText("")

    def set_done(self, chars: int = 0, elapsed: float = 0, rate: float = 0):
        self._active = False
        self._status.setText("done")
        self._status.setStyleSheet(f"color: {SUCCESS}; font-size: 11px;")
        parts = []
        if chars:    parts.append(f"{chars} ch")
        if elapsed:  parts.append(f"{elapsed:.1f}s")
        if rate:     parts.append(f"{rate:.0f} ch/s")
        self._stats.setText("  ".join(parts))

    def set_error(self, msg: str):
        self._active = False
        self._status.setText(f"error: {msg[:40]}")
        self._status.setStyleSheet(f"color: {ERROR}; font-size: 11px;")

    def set_idle(self):
        if not self._active:
            return
        self._active = False
        self._status.setText("idle")
        self._status.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")

    def tick(self):
        """Called every second while generating — show elapsed time."""
        if self._active:
            elapsed = time.time() - self._start_ts
            self._stats.setText(f"{elapsed:.0f}s…")


# ── Error log ──────────────────────────────────────────────────────────────────
class ErrorLog(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 6px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        hdr = QHBoxLayout()
        ttl = QLabel("ERRORS")
        ttl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 9px; font-weight: 600; letter-spacing: 0.08em;")
        self._clear_btn = QPushButton("✕ Clear")
        self._clear_btn.setFixedSize(54, 18)
        self._clear_btn.setFlat(True)
        self._clear_btn.setStyleSheet(f"color: {TEXT_DIM}; font-size: 9px; border: none;")
        self._clear_btn.clicked.connect(self._clear)
        hdr.addWidget(ttl)
        hdr.addStretch()
        hdr.addWidget(self._clear_btn)
        lay.addLayout(hdr)

        self._log = QLabel("No errors")
        self._log.setWordWrap(True)
        self._log.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; font-family: Consolas;")
        self._log.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.addWidget(self._log)

        self._entries = []

    def add(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self._entries.append(f"[{ts}] {msg}")
        self._entries = self._entries[-8:]   # keep last 8
        self._log.setText("\n".join(self._entries))
        self._log.setStyleSheet(f"color: {ERROR}; font-size: 10px; font-family: Consolas;")

    def _clear(self):
        self._entries = []
        self._log.setText("No errors")
        self._log.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; font-family: Consolas;")


# ── Main monitor pane ──────────────────────────────────────────────────────────
class MonitorPane(QWidget):
    """
    Real-time system monitor. Receives ws.raw events and nova_status events.
    No server changes needed — all data is already being broadcast.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._depth_tokens  = 2048
        self._autonomous    = False
        self._nova_thinking = False
        self._build_ui()

        # Tick timer — updates elapsed time for in-progress generations
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start()

    # ── UI ─────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # ── State cards row
        cards_row = QHBoxLayout()
        cards_row.setSpacing(6)
        self._depth_card  = StatCard("Depth",      "Balanced (2048)")
        self._auto_card   = StatCard("Autonomous", "OFF")
        self._server_card = StatCard("Server",     "—")
        self._think_card  = StatCard("Thinking",   "idle")
        for c in (self._depth_card, self._auto_card, self._server_card, self._think_card):
            cards_row.addWidget(c, 1)
        lay.addLayout(cards_row)

        # ── Agent rows
        section = QLabel("AGENTS")
        section.setStyleSheet(f"color: {TEXT_DIM}; font-size: 9px; font-weight: 600; letter-spacing: 0.08em; padding-top: 4px;")
        lay.addWidget(section)

        self._rows = {
            "Nova":   AgentRow("Nova",   NOVA),
            "Claude": AgentRow("Claude", CLAUDE),
            "Gemini": AgentRow("Gemini", GEMINI),
        }
        for row in self._rows.values():
            lay.addWidget(row)

        # ── Last Nova generation detail
        self._gen_card = StatCard("Last Nova generation", "—")
        lay.addWidget(self._gen_card)

        # ── Error log
        self._error_log = ErrorLog()
        lay.addWidget(self._error_log)

        lay.addStretch(1)
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QHBoxLayout()
        header.setContentsMargins(8, 6, 8, 4)
        ttl = QLabel("📊  Monitor")
        ttl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; font-weight: 600;")
        header.addWidget(ttl)
        header.addStretch()
        outer.addLayout(header)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER};")
        outer.addWidget(sep)
        outer.addWidget(scroll, 1)

    # ── Public slots ───────────────────────────────────────────────────────────
    def on_raw(self, data: dict):
        t      = data.get("type", "")
        author = data.get("author", "Nova")

        if t == "autonomous_state":
            # Server pushed its authoritative autonomous mode state on connect.
            # Sync the monitor display so it always reflects real server state.
            self.update_autonomous(bool(data.get("enabled", False)))

        elif t == "generation_start":
            row = self._rows.get(author)
            if row:
                row.set_generating()

        elif t == "generation_end":
            elapsed = data.get("elapsed", 0)
            row = self._rows.get(author)
            if row:
                row.set_idle()
            if author == "Nova":
                self._gen_card.set_value(f"{elapsed:.1f}s")

        elif t == "nova_progress" and data.get("final"):
            chars   = data.get("chars", 0)
            elapsed = data.get("elapsed", 0)
            rate    = data.get("rate", 0)
            row = self._rows.get("Nova")
            if row:
                row.set_done(chars, elapsed, rate)
            label  = _depth_label(self._depth_tokens)
            tokens = self._depth_tokens
            self._gen_card.set_value(
                f"{chars} ch · {elapsed:.1f}s · {rate:.0f} ch/s · {label} ({tokens} tok)",
                SUCCESS
            )

        elif t == "think_start":
            self._nova_thinking = True
            self._think_card.set_value("active", NOVA)

        elif t == "think_end":
            elapsed = data.get("elapsed", 0)
            self._nova_thinking = False
            self._think_card.set_value(f"{elapsed:.1f}s", TEXT_DIM)

        elif t in ("error",):
            msg    = data.get("message", "")
            source = data.get("author", "?")
            self._error_log.add(f"{source}: {msg}")
            row = self._rows.get(source)
            if row:
                row.set_error(msg)

        elif t == "gateway_error":
            self._error_log.add(f"gateway: {data.get('message','?')}")

        elif t == "nova_activity":
            # Update the Nova row status with the active directive.
            # Must also set _active=True so that the subsequent generation_end
            # → set_idle() call doesn't early-return without clearing the label.
            directive = data.get("directive", "")
            detail    = data.get("detail", "")[:30]
            row = self._rows.get("Nova")
            if row:
                row._active = True
                row._status.setText(f"[{directive}] {detail}")
                row._status.setStyleSheet(f"color: {NOVA}; font-size: 11px;")

    def on_nova_status(self, data: dict):
        """Receives nova_status broadcast — updates server/pulse card."""
        live   = data.get("nova_live", data)
        pulse  = live.get("pulse", "")
        errors = live.get("errors", [])
        color  = ERROR if errors else SUCCESS
        self._server_card.set_value(pulse[:20] if pulse else "ok", color)

    def on_connected(self):
        self._server_card.set_value("connected", SUCCESS)

    def on_disconnected(self):
        self._server_card.set_value("offline", ERROR)
        for row in self._rows.values():
            row.set_idle()

    def on_processing_start(self):
        pass   # generation_start is more specific

    def on_processing_end(self):
        for row in self._rows.values():
            row.set_idle()

    def update_depth(self, tokens: int):
        """Called from window.py when depth slider changes."""
        self._depth_tokens = tokens
        label = _depth_label(tokens)
        self._depth_card.set_value(f"{label} ({tokens})")

    def update_autonomous(self, enabled: bool):
        """Called from window.py when autonomous toggle changes."""
        self._autonomous = enabled
        if enabled:
            self._auto_card.set_value("ON", NOVA)
        else:
            self._auto_card.set_value("OFF", TEXT_DIM)

    # ── Tick ───────────────────────────────────────────────────────────────────
    def _on_tick(self):
        for row in self._rows.values():
            row.tick()


def _depth_label(tokens: int) -> str:
    if tokens <= 512:   return "Fast"
    if tokens <= 2048:  return "Balanced"
    if tokens <= 4096:  return "Deep"
    return "Max"
