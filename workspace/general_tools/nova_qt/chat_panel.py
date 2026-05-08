"""
chat_panel.py — Main chat display + input for Nova Qt app.

Layout:
  ┌─ ChatPanel (QWidget, VBox) ─────────────────┐
  │  session_bar  (SessionTabBar)                │
  │  scroll area  → _msg_container               │
  │    MessageWidget × N                         │
  │  conn_label   (QLabel — status indicator)    │
  │  input_row    (HBox)                         │
  │    input_box  (ChatInput)                    │
  │    stop_btn   (QPushButton — hidden)         │
  │    send_btn   (QPushButton)                  │
  └──────────────────────────────────────────────┘
"""
import time
import re
import requests
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QTextEdit, QPushButton, QLabel, QSizePolicy, QTabBar, QScrollArea,
    QInputDialog, QMenu, QMessageBox, QSlider, QFrame, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSizeF, QPointF, QEvent
from PyQt6.QtGui import QTextCursor, QKeyEvent, QFont, QAction

from .theme import NOVA, CLAUDE, GEMINI, COLE, TEXT_DIM, BG_ALT, BORDER, ERROR, BG
from . import markdown as md

BASE_URL = "http://127.0.0.1:8765"


# ── Inline thinking block (Nova only) ─────────────────────────────────────────
class ThinkingBlock(QWidget):
    """
    Collapsible inline panel that shows Nova's <think> content above her reply.
    Mimics Claude's expandable "thinking" section.

    States:
      hidden       — default; no think content has arrived yet
      active       — think_start fired; streaming tokens; shows spinner text
      finished     — think_end fired; shows "💭 Thought for Xs ▶ expand"
      expanded     — user clicked; shows the raw monospace thought content
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._raw_think = ""
        self._elapsed   = 0.0
        self._active    = False
        self._expanded  = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(56, 2, 12, 4)   # align with message body (avatar=32 + spacing=12 + 12)
        lay.setSpacing(2)

        self._toggle_btn = QPushButton("💭  Thinking…")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                color: #7070bb;
                font-size: 11px;
                font-style: italic;
                padding: 1px 0;
                border: none;
                background: transparent;
            }}
            QPushButton:hover {{ color: #9090dd; text-decoration: underline; }}
        """)
        self._toggle_btn.clicked.connect(self._on_toggle)
        lay.addWidget(self._toggle_btn)

        # Expandable content — monospace grey block
        self._content = QTextBrowser()
        self._content.setReadOnly(True)
        self._content.setFrameShape(QFrame.Shape.NoFrame)
        self._content.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._content.setStyleSheet(f"""
            QTextBrowser {{
                background: {BG_ALT};
                border: 1px solid {BORDER};
                border-radius: 4px;
                font-family: "JetBrains Mono", "Consolas", monospace;
                font-size: 10px;
                color: #6868a8;
                padding: 6px 8px;
            }}
        """)
        self._content.setMaximumHeight(220)
        self._content.setVisible(False)
        lay.addWidget(self._content)

        self.setVisible(False)   # hidden until think_start

    # ── Public API ─────────────────────────────────────────────────────────────
    def start_thinking(self):
        """Called when think_start arrives — show the block in active state."""
        self._active = True
        self._toggle_btn.setText("💭  Thinking…")
        self.setVisible(True)

    def append_think_token(self, token: str):
        """Called for each think_token; updates the live expanded view if open."""
        self._raw_think += token
        if self._expanded:
            cursor = self._content.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._content.setTextCursor(cursor)
            self._content.insertPlainText(token)
            sb = self._content.verticalScrollBar()
            sb.setValue(sb.maximum())

    def finish_thinking(self, elapsed: float):
        """Called on think_end — collapse to summary state."""
        self._active  = False
        self._elapsed = elapsed
        secs = f"{elapsed:.1f}s" if elapsed > 0 else "—"
        self._toggle_btn.setText(f"💭  Thought for {secs}   ▶")
        # Sync content widget with full accumulated text
        if self._expanded:
            self._content.setPlainText(self._raw_think)

    # ── Toggle expand/collapse ─────────────────────────────────────────────────
    def _on_toggle(self):
        if self._active:
            # While still thinking, toggle live preview
            self._expanded = not self._expanded
            self._content.setPlainText(self._raw_think)
            self._content.setVisible(self._expanded)
            return

        self._expanded = not self._expanded
        secs = f"{self._elapsed:.1f}s" if self._elapsed > 0 else "—"
        if self._expanded:
            self._content.setPlainText(self._raw_think)
            self._content.setVisible(True)
            self._toggle_btn.setText(f"💭  Thought for {secs}   ▼")
        else:
            self._content.setVisible(False)
            self._toggle_btn.setText(f"💭  Thought for {secs}   ▶")


# ── Message bubble widget ──────────────────────────────────────────────────────
class MessageWidget(QWidget):
    """
    One chat message: avatar + role header + HTML body.

    Text sizing:
      The QTextBrowser computes its height based on its viewport width.
      We override resizeEvent to recalculate height whenever the widget
      is laid out or resized by the splitter.

    Streaming strategy:
      - append_token(t)  — fast path: append plain text, no markdown re-render
      - finalize()       — render full content as markdown once streaming ends
    """

    resend_requested = pyqtSignal(str)   # emitted when user picks "Resend" from context menu

    def __init__(self, role: str, content: str = "", parent=None):
        super().__init__(parent)
        self.role = role
        self._raw = content          # accumulates plain text during streaming
        self._finalized = False
        self._token_count = 0        # track tokens for throttling

        color = md.role_color(role)
        initial = role[0].upper() if role else "?"

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 6, 12, 6)
        outer.setSpacing(12)
        outer.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Avatar circle
        avatar = QLabel(initial)
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(f"""
            QLabel {{
                background: {color}22;
                color: {color};
                border: 1px solid {color}55;
                border-radius: 16px;
                font-size: 12px;
                font-weight: 700;
            }}
        """)

        # Content column
        col = QVBoxLayout()
        col.setSpacing(2)
        col.setContentsMargins(0, 0, 0, 0)

        header = QLabel(f'<span style="color:{color};font-weight:600">{role}</span>')
        header.setTextFormat(Qt.TextFormat.RichText)

        self.body = QTextBrowser()
        self.body.setOpenExternalLinks(True)
        self.body.setReadOnly(True)
        self.body.setFrameShape(QTextBrowser.Shape.NoFrame)
        self.body.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.body.setStyleSheet("background: transparent; color: #f0f0f0;")

        # Forward resize events from the body so parent can recalculate
        self.body.resizeEvent = self._body_resized

        # Right-click context menu (Cole messages get "Resend" option)
        if role == "Cole":
            self.body.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.body.customContextMenuRequested.connect(self._show_context_menu)

        col.addWidget(header)
        col.addWidget(self.body)

        outer.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(col, 1)

        # Periodic markdown re-render during streaming (every 1.5 s)
        self._rerender_timer = QTimer(self)
        self._rerender_timer.setInterval(1500)
        self._rerender_timer.timeout.connect(self._streaming_rerender)

        # Debounced height-fit timer (collapses many token calls into one)
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(80)
        self._fit_timer.timeout.connect(self._fit_height)

        # Render initial content if any
        if content:
            self._render(content)

    # ── Resize handling ───────────────────────────────────────────────────────
    def _body_resized(self, event):
        """Called when QTextBrowser is resized — schedule a height recalculation."""
        QTextBrowser.resizeEvent(self.body, event)
        if not self._fit_timer.isActive():
            self._fit_timer.start()

    def _fit_height(self):
        """Resize the body to exactly contain its document content.

        Uses setTextWidth() which forces a *synchronous* reflow of the
        QTextDocument before we read its height.  The old setPageSize()
        approach triggered an async relayout, so document().size().height()
        was often stale and the body got locked at the wrong (too-small)
        height via setFixedHeight — clipping everything that didn't fit.
        """
        vw = self.body.viewport().width()
        if vw <= 10:
            # Widget not yet painted — retry after the next event-loop tick
            self._fit_timer.start()
            return
        doc = self.body.document()
        doc.setTextWidth(vw)                        # synchronous reflow
        doc_h = int(doc.size().height())
        h = max(doc_h + 8, 24)
        if self.body.height() != h:
            self.body.setFixedHeight(h)
            self.body.updateGeometry()              # tell parent layout to adjust

    # ── Rendering ─────────────────────────────────────────────────────────────
    def _render(self, text: str):
        """Render text as markdown HTML and schedule a height fit."""
        if not text:
            return
        html = md.render(text)
        # Preserve scroll position so in-progress renders don't jump
        sb   = self.body.verticalScrollBar()
        prev = sb.value()
        self.body.setHtml(html)
        sb.setValue(prev)
        if not self._fit_timer.isActive():
            self._fit_timer.start()

    def _streaming_rerender(self):
        """Periodic re-render called every 1.5 s while streaming.
        Gives the user formatted markdown rather than raw asterisks/hashes."""
        if not self._finalized and self._raw:
            self._render(self._raw)

    # ── Streaming API ─────────────────────────────────────────────────────────
    def append_token(self, token: str):
        """Accumulate a streaming token.
        The periodic _rerender_timer fires every 1.5 s to re-render the
        accumulated text as formatted markdown, giving live visual feedback
        without an expensive re-render on every single token."""
        self._raw += token
        self._token_count += 1

        # Start periodic markdown re-render on first token
        if self._token_count == 1:
            self._rerender_timer.start()
            # Show the first token immediately so the bubble doesn't look empty
            self._render(self._raw)

    def finalize(self):
        """Called when message_end arrives — stop streaming timers, full render."""
        self._rerender_timer.stop()
        if not self._finalized:
            self._finalized = True
            self._render(self._raw)

    # ── Full-replace API (for history / non-streaming) ─────────────────────────
    def set_content(self, text: str):
        self._raw = text
        self._finalized = True
        self._rerender_timer.stop()
        self._render(text)

    # ── Context menu (Cole messages only) ─────────────────────────────────────
    def _show_context_menu(self, pos):
        """Right-click context menu on Cole's messages: Resend + Copy."""
        menu = QMenu(self.body)

        resend_act = menu.addAction("↺  Resend")
        resend_act.setToolTip("Re-send this message (useful when Nova was offline)")
        menu.addSeparator()
        copy_act = menu.addAction("⎘  Copy")

        chosen = menu.exec(self.body.mapToGlobal(pos))
        if chosen == resend_act:
            self.resend_requested.emit(self._raw)
        elif chosen == copy_act:
            QApplication.clipboard().setText(self._raw)


# ── Input box (Enter to send, Shift+Enter for newline) ────────────────────────
class ChatInput(QTextEdit):
    submit = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(
            "Message everyone — or @Claude @Gemini @Nova to direct   ·   Enter to send   ·   Shift+Enter for newline"
        )
        self.setMinimumHeight(44)
        self.setMaximumHeight(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.document().contentsChanged.connect(self._auto_resize)

    def _auto_resize(self):
        doc_h = int(self.document().size().height()) + 18
        self.setFixedHeight(min(max(doc_h, 44), 140))

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key.Key_Return and not (e.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.submit.emit()
        else:
            super().keyPressEvent(e)


# ── Session tab bar ────────────────────────────────────────────────────────────
class SessionTabBar(QTabBar):
    new_session_requested  = pyqtSignal()
    rename_session_requested = pyqtSignal(int)   # tab index
    delete_session_requested = pyqtSignal(int)   # tab index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(False)
        self.setExpanding(False)
        self.setDrawBase(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setStyleSheet(f"""
            QTabBar::tab {{
                padding: 5px 14px;
                font-size: 12px;
                border: none;
                border-top: 2px solid transparent;
                background: transparent;
                color: #6b7280;
            }}
            QTabBar::tab:selected {{
                color: {NOVA};
                border-top: 2px solid {NOVA};
                background: rgba(143,144,255,0.06);
            }}
            QTabBar::tab:hover:!selected {{ color: #f0f0f0; }}
            QTabBar::tab:last {{
                color: #4b5563;
                font-size: 16px;
                padding: 2px 10px;
            }}
        """)
        self._add_plus_tab()

    def _add_plus_tab(self):
        idx = self.addTab("+")
        self.setTabToolTip(idx, "New session (Ctrl+T)")

    def mousePressEvent(self, e):
        idx = self.tabAt(e.pos())
        if idx == self.count() - 1:   # "+" tab
            self.new_session_requested.emit()
        else:
            super().mousePressEvent(e)

    def _show_context_menu(self, pos):
        idx = self.tabAt(pos)
        if idx < 0 or idx == self.count() - 1:
            return   # clicked on "+" or empty area

        menu = QMenu(self)
        rename_act = menu.addAction("✏ Rename session")
        menu.addSeparator()
        delete_act = menu.addAction("🗑 Delete session")
        delete_act.setEnabled(self.count() > 2)   # can't delete last real session

        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == rename_act:
            self.rename_session_requested.emit(idx)
        elif chosen == delete_act:
            self.delete_session_requested.emit(idx)


# ── Main chat panel ────────────────────────────────────────────────────────────
class ChatPanel(QWidget):
    """
    The central chat UI.  Owns session bar, message list, input, send/stop buttons.
    Does NOT own the WebSocket — receives data via slots, emits actions via signals.
    """
    send_requested     = pyqtSignal(str)         # text content
    stop_requested     = pyqtSignal()
    new_session        = pyqtSignal()
    switch_session     = pyqtSignal(str)         # session_id
    autonomous_changed = pyqtSignal(bool)        # autonomous mode toggled
    depth_changed      = pyqtSignal(int)         # max_tokens value changed
    mute_requested     = pyqtSignal(str, bool)   # agent, muted — from @mute/@unmute commands

    # Pattern: @mute[Name] or @unmute[Name] (case-insensitive, brackets optional)
    _MUTE_RE   = re.compile(r'@mute\[?(\w+)\]?',   re.IGNORECASE)
    _UNMUTE_RE = re.compile(r'@unmute\[?(\w+)\]?', re.IGNORECASE)
    _AI_AGENTS = {"nova", "claude", "gemini"}

    # Depth-slider stops: Fast / Balanced / Deep / Max
    _DEPTH_LABELS  = ["Fast", "Balanced", "Deep", "Max"]
    _DEPTH_TOKENS  = [512,    2048,        4096,   8192]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sessions: list = []
        self._current_session_id: str = ""
        self._streaming: dict = {}      # msg_id → MessageWidget
        self._think_blocks: dict = {}   # msg_id → ThinkingBlock (Nova only)
        self._processing = False
        self._rebuilding_tabs = False   # guard against switch loop
        self._at_bottom = True         # auto-scroll state
        self._autonomous = False       # autonomous mode off by default
        self._depth_tokens = 2048      # Balanced by default

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Session tab bar
        self.session_bar = SessionTabBar()
        self.session_bar.new_session_requested.connect(self.new_session)
        self.session_bar.currentChanged.connect(self._on_tab_changed)
        self.session_bar.rename_session_requested.connect(self._on_rename_session)
        self.session_bar.delete_session_requested.connect(self._on_delete_session)
        root.addWidget(self.session_bar)

        # Hairline separator
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER};")
        root.addWidget(sep)

        # Scrollable message area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.installEventFilter(self)   # for resize → reposition button

        self._msg_container = QWidget()
        self._msg_container.setStyleSheet(f"background: {BG};")
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(0, 8, 0, 8)
        self._msg_layout.setSpacing(2)
        self._msg_layout.addStretch(1)   # pushes messages to top

        self.scroll.setWidget(self._msg_container)
        root.addWidget(self.scroll, 1)

        # Connect scrollbar to track user position
        sb = self.scroll.verticalScrollBar()
        sb.valueChanged.connect(self._on_scroll_changed)

        # Floating "scroll to bottom" button — child of scroll area viewport
        self._scroll_btn = QPushButton("▼", self.scroll.viewport())
        self._scroll_btn.setFixedSize(34, 34)
        self._scroll_btn.setVisible(False)
        self._scroll_btn.setToolTip("Scroll to bottom")
        self._scroll_btn.setStyleSheet(f"""
            QPushButton {{
                background: {NOVA};
                color: #ffffff;
                border: none;
                border-radius: 17px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: #a0a1ff;
            }}
        """)
        self._scroll_btn.clicked.connect(self._jump_to_bottom)
        self._scroll_btn.raise_()

        # Connection status
        self.conn_label = QLabel("connecting...")
        self.conn_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.conn_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; padding: 2px;")
        root.addWidget(self.conn_label)

        # Input row
        input_row = QHBoxLayout()
        input_row.setContentsMargins(12, 8, 12, 12)
        input_row.setSpacing(8)

        self.input_box = ChatInput()
        self.input_box.submit.connect(self._on_send)
        input_row.addWidget(self.input_box, 1)

        self.stop_btn = QPushButton("■ STOP")
        self.stop_btn.setObjectName("stop-btn")
        self.stop_btn.setFixedWidth(80)
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._on_stop)
        input_row.addWidget(self.stop_btn)

        self.send_btn = QPushButton("▶ Send")
        self.send_btn.setObjectName("send-btn")
        self.send_btn.setFixedWidth(80)
        self.send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self.send_btn)

        root.addLayout(input_row)

        # ── Bottom controls: depth slider (left) + autonomous toggle (right) ─────
        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(12, 0, 12, 8)
        controls_row.setSpacing(10)

        # Depth slider + labels
        depth_wrap = QWidget()
        depth_wrap.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        depth_vlay = QVBoxLayout(depth_wrap)
        depth_vlay.setContentsMargins(0, 0, 0, 0)
        depth_vlay.setSpacing(1)

        self._depth_slider = QSlider(Qt.Orientation.Horizontal)
        self._depth_slider.setRange(0, len(self._DEPTH_TOKENS) - 1)
        self._depth_slider.setValue(1)   # Balanced (2048) default
        self._depth_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._depth_slider.setTickInterval(1)
        self._depth_slider.setFixedWidth(190)
        self._depth_slider.setFixedHeight(18)
        self._depth_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self._depth_slider.setToolTip("Nova response depth — controls max tokens")
        self._depth_slider.valueChanged.connect(self._on_depth_changed)
        self._depth_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 3px; background: #2a2a3a; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #8f90ff; border: none;
                width: 13px; height: 13px; margin: -5px 0; border-radius: 7px;
            }
            QSlider::sub-page:horizontal {
                background: #5a5aee; border-radius: 2px;
            }
        """)
        depth_vlay.addWidget(self._depth_slider)

        lbl_row = QHBoxLayout()
        lbl_row.setContentsMargins(0, 0, 0, 0)
        lbl_row.setSpacing(0)
        for i, lbl_text in enumerate(self._DEPTH_LABELS):
            lbl = QLabel(lbl_text)
            if i == 0:
                align = Qt.AlignmentFlag.AlignLeft
            elif i == len(self._DEPTH_LABELS) - 1:
                align = Qt.AlignmentFlag.AlignRight
            else:
                align = Qt.AlignmentFlag.AlignCenter
            lbl.setAlignment(align)
            lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 9px;")
            lbl_row.addWidget(lbl, 1)
        depth_vlay.addLayout(lbl_row)

        controls_row.addWidget(depth_wrap)
        controls_row.addStretch(1)

        # Autonomous mode toggle pill
        self.auto_btn = QPushButton("⚡  Autonomous  OFF")
        self.auto_btn.setCheckable(True)
        self.auto_btn.setChecked(False)
        self.auto_btn.setFixedHeight(24)
        self.auto_btn.setFixedWidth(172)
        self.auto_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_auto_style(False)
        self.auto_btn.clicked.connect(self._on_autonomous_toggle)
        controls_row.addWidget(self.auto_btn)

        root.addLayout(controls_row)

    # ── Event filter — reposition floating button on scroll area resize ───────
    def eventFilter(self, obj, event):
        if obj is self.scroll and event.type() == QEvent.Type.Resize:
            self._reposition_scroll_btn()
        return super().eventFilter(obj, event)

    def _reposition_scroll_btn(self):
        """Keep the down-arrow button anchored 16px from bottom-right of viewport."""
        vp = self.scroll.viewport()
        btn = self._scroll_btn
        btn.move(
            vp.width()  - btn.width()  - 16,
            vp.height() - btn.height() - 16,
        )

    # ── Scroll tracking ───────────────────────────────────────────────────────
    def _on_scroll_changed(self, value: int):
        """Called whenever the vertical scrollbar moves.
        Updates _at_bottom and shows/hides the down-arrow button."""
        sb = self.scroll.verticalScrollBar()
        at_bottom = (sb.maximum() - value) < 50
        if at_bottom != self._at_bottom:
            self._at_bottom = at_bottom
            self._scroll_btn.setVisible(not at_bottom)

    def _jump_to_bottom(self):
        """User clicked the down-arrow button — jump to bottom and resume auto-scroll."""
        self._at_bottom = True
        self._scroll_btn.setVisible(False)
        sb = self.scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _scroll_to_bottom(self):
        """Scroll to bottom, but only if the user hasn't scrolled up."""
        if not self._at_bottom:
            return
        sb = self.scroll.verticalScrollBar()
        QTimer.singleShot(50, lambda: sb.setValue(sb.maximum()))

    # ── Public slots — connection ─────────────────────────────────────────────
    def on_connected(self):
        self.conn_label.setText("")
        self.conn_label.setVisible(False)

    def on_disconnected(self):
        self.conn_label.setText("⚠ disconnected — reconnecting...")
        self.conn_label.setStyleSheet(f"color: {ERROR}; font-size: 11px; padding: 2px;")
        self.conn_label.setVisible(True)

    def on_conn_error(self, msg: str):
        self.conn_label.setText(f"⚠ {msg}")
        self.conn_label.setStyleSheet(f"color: {ERROR}; font-size: 11px; padding: 2px;")
        self.conn_label.setVisible(True)

    # ── Public slots — sessions ───────────────────────────────────────────────
    def on_sessions(self, sessions: list):
        """Update session tabs from sessions_init / sessions_updated signal."""
        self._sessions = sessions
        self._rebuild_session_tabs()

    def on_session_switched(self, data: dict):
        """
        session_switched: server confirmed a session change.
        Clears messages and replays history from the payload.
        Guarded to prevent the tab-rebuild from triggering another switch.
        """
        sessions       = data.get("sessions", [])
        history        = data.get("history", [])
        new_session_id = data.get("session_id", "")

        # Update state BEFORE rebuilding tabs so _on_tab_changed won't re-fire
        self._current_session_id = new_session_id
        self._sessions = sessions

        self._rebuild_session_tabs()
        self._clear_messages()

        for msg in history:
            author  = msg.get("author", "?")
            content = msg.get("content", "")
            if content:
                self._add_message_widget(author, content)

    # ── Public slots — messages ───────────────────────────────────────────────
    def on_history(self, data: dict):
        """'history' messages arrive on initial connect — one per past message."""
        author  = data.get("author", "?")
        content = data.get("content", "")
        if content:
            self._add_message_widget(author, content)

    def on_user_msg(self, data: dict):
        """
        'user_message' — Cole, Nova (injected), or System posting.
        Cole's own messages are shown optimistically in _on_send — skip echo.
        """
        author  = data.get("author", "?")
        content = data.get("content", "")
        if author == "Cole":
            return   # already shown locally
        if content:
            self._add_message_widget(author, content)

    def on_msg_start(self, data: dict):
        """'message_start' — create an empty bubble so user sees immediate feedback.
        For Nova, also create a ThinkingBlock (hidden until think_start arrives)."""
        author = data.get("author", "Nova")
        msg_id = data.get("id", "")

        # Thinking block — Nova only, hidden by default
        if author == "Nova" and msg_id:
            tb = ThinkingBlock()
            self._insert_widget(tb)
            self._think_blocks[msg_id] = tb

        w = MessageWidget(author)
        self._insert_widget(w)
        if msg_id:
            self._streaming[msg_id] = w

    def on_token(self, data: dict):
        """'token' — append a streaming token."""
        msg_id = data.get("id", "")
        token  = data.get("token", "")
        author = data.get("author", "Nova")
        if not token:
            return
        if msg_id in self._streaming:
            self._streaming[msg_id].append_token(token)
        else:
            # Fallback: create bubble on first token if message_start was missed
            w = MessageWidget(author)
            self._insert_widget(w)
            w.append_token(token)
            if msg_id:
                self._streaming[msg_id] = w
        self._scroll_to_bottom()

    def on_msg_end(self, data: dict):
        """'message_end' — streaming complete, render full markdown.

        If the server includes the final cleaned 'content' (which for autonomous
        tool-call chains replaces the streaming placeholder text), use set_content()
        to show the authoritative version instead of finalizing the raw token stream.
        """
        msg_id = data.get("id", "")
        w = self._streaming.pop(msg_id, None)
        if w:
            final_content = data.get("content", "")
            if final_content:
                w.set_content(final_content)
            else:
                w.finalize()
            self._scroll_to_bottom()

    # ── Public slots — processing ─────────────────────────────────────────────
    def on_processing_start(self):
        self._processing = True
        self.send_btn.setEnabled(False)
        self.stop_btn.setVisible(True)

    def on_processing_end(self):
        self._processing = False
        self.send_btn.setEnabled(True)
        self.stop_btn.setVisible(False)

    def add_system_msg(self, text: str):
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; padding: 4px;")
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, label)
        self._scroll_to_bottom()

    # ── Public slot — inline think events ────────────────────────────────────
    def on_raw_think(self, data: dict):
        """
        Handles think_start / think_token / think_end from the ws raw signal.
        Routes events to the ThinkingBlock that was pre-created in on_msg_start.
        All other raw message types are intentionally ignored here.
        """
        t      = data.get("type", "")
        msg_id = data.get("id", "")
        block  = self._think_blocks.get(msg_id)
        if not block:
            return

        if t == "think_start":
            block.start_thinking()
            self._scroll_to_bottom()

        elif t == "think_token":
            token = data.get("token", "")
            if token:
                block.append_think_token(token)

        elif t == "think_end":
            elapsed = data.get("elapsed", 0)
            block.finish_thinking(float(elapsed))
            self._scroll_to_bottom()

    # ── Session rename / delete ───────────────────────────────────────────────
    def _on_rename_session(self, tab_idx: int):
        if tab_idx >= len(self._sessions):
            return
        session = self._sessions[tab_idx]
        sid = session.get("session_id", "")
        old = session.get("name") or session.get("label") or f"Session {tab_idx + 1}"
        name, ok = QInputDialog.getText(self, "Rename Session", "New name:", text=old)
        if not ok or not name.strip():
            return
        try:
            requests.post(f"{BASE_URL}/sessions/rename/{sid}",
                          json={"name": name.strip()}, timeout=5)
            # Update local state immediately so UI is snappy
            session["name"] = name.strip()
            self.session_bar.setTabText(tab_idx, name.strip())
        except Exception as e:
            self.add_system_msg(f"Rename failed: {e}")

    def _on_delete_session(self, tab_idx: int):
        if tab_idx >= len(self._sessions):
            return
        session = self._sessions[tab_idx]
        sid   = session.get("session_id", "")
        label = session.get("name") or session.get("label") or f"Session {tab_idx + 1}"
        reply = QMessageBox.question(
            self, "Delete Session",
            f"Delete \"{label}\"? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            requests.delete(f"{BASE_URL}/sessions/{sid}", timeout=5)
        except Exception as e:
            self.add_system_msg(f"Delete failed: {e}")

    # ── Internal helpers ───────────────────────────────────────────────────────
    def _add_message_widget(self, author: str, content: str):
        w = MessageWidget(author, content)
        if author == "Cole":
            w.resend_requested.connect(self._on_resend)
        self._insert_widget(w)

    def _on_resend(self, text: str):
        """Resend a Cole message without creating a duplicate local bubble."""
        if not text:
            return
        self.add_system_msg("↺ Resending…")
        self.send_requested.emit(text)

    def _insert_widget(self, widget: QWidget):
        idx = self._msg_layout.count() - 1   # before trailing stretch
        self._msg_layout.insertWidget(idx, widget)
        self._scroll_to_bottom()

    def _apply_auto_style(self, enabled: bool):
        """Style the autonomous toggle pill based on current state."""
        if enabled:
            self.auto_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {NOVA}22;
                    color: {NOVA};
                    border: 1px solid {NOVA}88;
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0 10px;
                    letter-spacing: 0.03em;
                }}
                QPushButton:hover {{ background: {NOVA}44; }}
            """)
        else:
            self.auto_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {TEXT_DIM};
                    border: 1px solid {BORDER};
                    border-radius: 12px;
                    font-size: 11px;
                    padding: 0 10px;
                    letter-spacing: 0.03em;
                }}
                QPushButton:hover {{ color: #f0f0f0; border-color: #555; }}
            """)

    def _on_depth_changed(self, position: int):
        """Slider moved — emit the new max_tokens value."""
        tokens = self._DEPTH_TOKENS[position]
        self._depth_tokens = tokens
        # Update slider tooltip to show current token budget
        label = self._DEPTH_LABELS[position]
        self._depth_slider.setToolTip(f"Nova depth: {label} ({tokens} max tokens)")
        self.depth_changed.emit(tokens)

    def _on_autonomous_toggle(self, checked: bool):
        self._autonomous = checked
        self.auto_btn.setText("⚡  Autonomous  ON " if checked else "⚡  Autonomous  OFF")
        self._apply_auto_style(checked)
        self.autonomous_changed.emit(checked)

    def _on_send(self):
        text = self.input_box.toPlainText().strip()
        if not text or self._processing:
            return

        # Intercept @mute / @unmute commands — handle locally, don't send to chat
        mute_match   = self._MUTE_RE.fullmatch(text)
        unmute_match = self._UNMUTE_RE.fullmatch(text)
        if mute_match or unmute_match:
            agent_raw = (mute_match or unmute_match).group(1)
            agent = agent_raw.capitalize()
            if agent.lower() in self._AI_AGENTS:
                muted = bool(mute_match)
                self.input_box.clear()
                self.mute_requested.emit(agent, muted)
                return   # handled — don't send as a chat message

        self.input_box.clear()
        self._add_message_widget("Cole", text)
        # Sending a message re-enables auto-scroll
        self._at_bottom = True
        self._scroll_btn.setVisible(False)
        self.send_requested.emit(text)

    def _on_stop(self):
        self.stop_requested.emit()
        self.on_processing_end()

    def _on_tab_changed(self, index: int):
        """User clicked a session tab — request server to switch."""
        if self._rebuilding_tabs:
            return   # tab changed because we rebuilt, not because user clicked
        if index == self.session_bar.count() - 1:
            return   # "+" tab
        if index >= len(self._sessions):
            return
        sid = self._sessions[index].get("session_id", "")
        if sid and sid != self._current_session_id:
            self._current_session_id = sid   # optimistic update prevents loop
            self.switch_session.emit(sid)
            # History and final tab state will update via on_session_switched

    def _rebuild_session_tabs(self):
        """Rebuild all session tabs. Guarded to prevent currentChanged→switch loop."""
        self._rebuilding_tabs = True
        self.session_bar.blockSignals(True)

        while self.session_bar.count() > 1:
            self.session_bar.removeTab(0)
        for i, s in enumerate(self._sessions):
            label = s.get("name") or s.get("label") or f"Session {i + 1}"
            self.session_bar.insertTab(i, label)

        # Highlight the active session
        for i, s in enumerate(self._sessions):
            if s.get("session_id") == self._current_session_id:
                self.session_bar.setCurrentIndex(i)
                break

        self.session_bar.blockSignals(False)
        self._rebuilding_tabs = False

    def _clear_messages(self):
        """Remove all message widgets (including ThinkingBlocks), keep the trailing stretch."""
        while self._msg_layout.count() > 1:
            item = self._msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._streaming.clear()
        self._think_blocks.clear()
        # Reset scroll state when clearing (new session)
        self._at_bottom = True
        self._scroll_btn.setVisible(False)
