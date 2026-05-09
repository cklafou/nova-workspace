"""
sidebar.py — Left tools panel (file tree, terminal, status, thoughts).

QTabWidget with four panes. Can be shown/hidden via toggle.
New panes (voice, SD, Suno, etc.) just need to be added as new tabs.
"""
import json
import requests
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QTextEdit, QTextBrowser, QLineEdit, QPushButton,
    QLabel, QSizePolicy, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QTextCursor

from .theme import NOVA, TEXT_DIM, BG_ALT, BORDER, SUCCESS, ERROR, BG_CARD, TEXT
from .eyes_pane    import EyesPane
from .monitor_pane import MonitorPane


BASE_URL = "http://127.0.0.1:8765"


# ── File tree pane ─────────────────────────────────────────────────────────────
class FileTreePane(QWidget):
    file_selected = pyqtSignal(str)   # emits path when user clicks a file

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter files...")
        self.search.setStyleSheet(f"""
            QLineEdit {{
                background: {BG_ALT};
                border: none;
                border-bottom: 1px solid {BORDER};
                border-radius: 0;
                padding: 6px 10px;
                color: #f0f0f0;
                font-size: 12px;
            }}
        """)
        self.search.textChanged.connect(self._filter)
        lay.addWidget(self.search)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setAnimated(True)
        self.tree.itemClicked.connect(self._on_item_click)
        lay.addWidget(self.tree, 1)

        self._load_tree()

    def _load_tree(self):
        self.tree.clear()
        try:
            r = requests.get(f"{BASE_URL}/api/files/tree", timeout=3)
            data = r.json()
            self._build_node(data, self.tree.invisibleRootItem())
        except Exception as e:
            item = QTreeWidgetItem(["⚠ " + str(e)])
            item.setForeground(0, __import__("PyQt6.QtGui", fromlist=["QColor"]).QColor(ERROR))
            self.tree.addTopLevelItem(item)

    def _build_node(self, node, parent):
        if not node:
            return
        name = node.get("name", "")
        ntype = node.get("type", "file")
        path = node.get("path", "")

        icon = "📁 " if ntype == "dir" else "📄 "
        item = QTreeWidgetItem([icon + name])
        item.setData(0, Qt.ItemDataRole.UserRole, path)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, ntype)

        if isinstance(parent, QTreeWidget):
            parent.addTopLevelItem(item)
        else:
            parent.addChild(item)

        for child in node.get("children", []):
            self._build_node(child, item)

    def _on_item_click(self, item, col):
        ntype = item.data(0, Qt.ItemDataRole.UserRole + 1)
        path  = item.data(0, Qt.ItemDataRole.UserRole)
        if ntype == "file" and path:
            self.file_selected.emit(path)

    def _filter(self, text):
        text = text.lower()
        def _show(item):
            visible = text in item.text(0).lower()
            for i in range(item.childCount()):
                if _show(item.child(i)):
                    visible = True
            item.setHidden(not visible)
            return visible
        for i in range(self.tree.topLevelItemCount()):
            _show(self.tree.topLevelItem(i))


# ── Terminal pane ──────────────────────────────────────────────────────────────
class TerminalPane(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 11))
        self.output.setStyleSheet(f"""
            QTextEdit {{
                background: #050508;
                color: #d4d4d4;
                border: none;
                font-family: "JetBrains Mono", "Consolas", monospace;
                font-size: 12px;
            }}
        """)
        lay.addWidget(self.output, 1)

        cmd_row = QHBoxLayout()
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Enter command...")
        self.cmd_input.setStyleSheet(f"""
            QLineEdit {{
                background: #050508;
                border: none;
                border-top: 1px solid {BORDER};
                color: #d4d4d4;
                font-family: "Consolas", monospace;
                font-size: 12px;
                padding: 6px 8px;
            }}
        """)
        self.cmd_input.returnPressed.connect(self._run)
        cmd_row.addWidget(self.cmd_input, 1)

        run_btn = QPushButton("▶")
        run_btn.setFixedWidth(32)
        run_btn.clicked.connect(self._run)
        cmd_row.addWidget(run_btn)
        lay.addLayout(cmd_row)

    def _run(self):
        cmd = self.cmd_input.text().strip()
        if not cmd:
            return
        self.output.append(f'<span style="color:{NOVA}">❯ {cmd}</span>')
        self.cmd_input.clear()
        try:
            r = requests.post(
                f"{BASE_URL}/api/run-tool",
                json={"command": cmd, "cwd": ""},
                timeout=30
            )
            d = r.json()
            out = d.get("output", "") or d.get("error", "(no output)")
            self.output.append(f'<pre style="color:#d4d4d4;margin:0">{out}</pre>')
        except Exception as e:
            self.output.append(f'<span style="color:{ERROR}">Error: {e}</span>')


# ── Status pane ────────────────────────────────────────────────────────────────
class StatusPane(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # llama.cpp card
        self._llama_card = self._make_card("⚙ llama.cpp")
        self.llama_status = QLabel("Checking...")
        self.llama_status.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        self.llama_start_btn = QPushButton("▶ Start")
        self.llama_stop_btn  = QPushButton("■ Stop")
        for btn in (self.llama_start_btn, self.llama_stop_btn):
            btn.setFixedHeight(28)
        self.llama_start_btn.clicked.connect(self._llama_start)
        self.llama_stop_btn.clicked.connect(self._llama_stop)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.llama_start_btn)
        btn_row.addWidget(self.llama_stop_btn)
        self._llama_card.layout().addWidget(self.llama_status)
        self._llama_card.layout().addLayout(btn_row)
        lay.addWidget(self._llama_card)

        # STATUS.md card
        self._status_card = self._make_card("◈ Nova Status")
        self.status_text = QTextBrowser()
        self.status_text.setFont(QFont("Consolas", 11))
        self.status_text.setFixedHeight(200)
        self.status_text.setStyleSheet(f"background: {BG_ALT}; border: none; font-size: 11px;")
        refresh_btn = QPushButton("↺ Refresh")
        refresh_btn.setFixedHeight(26)
        refresh_btn.clicked.connect(self._load_status)
        self._status_card.layout().addWidget(self.status_text)
        self._status_card.layout().addWidget(refresh_btn)
        lay.addWidget(self._status_card)

        lay.addStretch(1)

        # Poll llama status every 10s
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_llama)
        self._timer.start(10000)
        self._poll_llama()

    def _make_card(self, title: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        ttl = QLabel(title)
        ttl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; font-weight: 600; letter-spacing: 0.06em;")
        lay.addWidget(ttl)
        return card

    def _poll_llama(self):
        try:
            r = requests.get(f"{BASE_URL}/api/llama/status", timeout=2)
            d = r.json()
            running = d.get("running", False)
            color   = SUCCESS if running else ERROR
            label   = "● Online" if running else "● Offline"
            self.llama_status.setText(label)
            self.llama_status.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600;")
        except Exception:
            # nova_chat server unreachable — show red, not ambiguous Unknown
            self.llama_status.setText("● Server offline")
            self.llama_status.setStyleSheet(f"color: {ERROR}; font-size: 12px; font-weight: 600;")

    def _llama_start(self):
        try:
            requests.post(f"{BASE_URL}/api/llama/start", timeout=5)
            QTimer.singleShot(5000, self._poll_llama)
        except Exception:
            pass

    def _llama_stop(self):
        try:
            requests.post(f"{BASE_URL}/api/llama/stop", timeout=5)
            QTimer.singleShot(2000, self._poll_llama)
        except Exception:
            pass

    def _load_status(self):
        try:
            r = requests.post(
                f"{BASE_URL}/api/run-tool",
                json={"command": "type memory\\STATUS.md", "cwd": ""},
                timeout=10
            )
            d = r.json()
            self.status_text.setPlainText((d.get("output") or "")[:3000])
        except Exception as e:
            self.status_text.setPlainText(f"Error: {e}")


# ── Thought card widget ────────────────────────────────────────────────────────
class ThoughtCard(QFrame):
    """
    A single Thought shown in the Thoughts panel.
    Displays: priority badge · name · summary · plan progress bar.
    """

    # Priority label → (badge color, bg tint)
    _P_STYLES = {
        1: ("#f87171", "#f871711a"),   # critical — red
        2: ("#facc15", "#facc151a"),   # high     — yellow
        3: (NOVA,     f"{NOVA}1a"),    # medium   — purple
        4: ("#6b7280", "#6b72801a"),   # low      — grey
    }

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self._id = data.get("id", "")
        self._update_style(data)
        self._build(data)

    def _update_style(self, data: dict):
        pnum   = max(1, min(4, data.get("priority_num", 3)))
        color, bg = self._P_STYLES.get(pnum, (NOVA, f"{NOVA}1a"))
        self._p_color = color
        self.setStyleSheet(f"""
            QFrame {{
                background: {bg};
                border: 1px solid {color}44;
                border-left: 3px solid {color};
                border-radius: 6px;
            }}
        """)

    def _build(self, data: dict):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        # Row 1: badge + name
        header = QHBoxLayout()
        header.setSpacing(8)

        pnum   = max(1, min(4, data.get("priority_num", 3)))
        p_labels = {1: "CRITICAL", 2: "HIGH", 3: "MEDIUM", 4: "LOW"}
        badge = QLabel(f"P{pnum}")
        badge.setFixedWidth(52)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"""
            QLabel {{
                background: {self._p_color}33;
                color: {self._p_color};
                border: 1px solid {self._p_color}66;
                border-radius: 3px;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 0.08em;
                padding: 1px 4px;
            }}
        """)

        name_lbl = QLabel(data.get("id", "—"))
        name_lbl.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: 600;")
        name_lbl.setWordWrap(False)

        status = data.get("status", "active")
        status_dot = QLabel("●")
        dot_color = SUCCESS if status == "active" else (
            "#facc15" if status in ("blocked", "suspended") else TEXT_DIM
        )
        status_dot.setStyleSheet(f"color: {dot_color}; font-size: 9px;")
        status_dot.setToolTip(status.capitalize())

        header.addWidget(badge)
        header.addWidget(name_lbl, 1)
        header.addWidget(status_dot)
        lay.addLayout(header)

        # Row 2: summary
        summary = data.get("summary", "")
        if summary:
            s_lbl = QLabel(summary)
            s_lbl.setWordWrap(True)
            s_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
            lay.addWidget(s_lbl)

        # Row 3: plan progress bar
        plan_total = data.get("plan_total", 0)
        plan_done  = data.get("plan_done", 0)
        if plan_total > 0:
            progress_row = QHBoxLayout()
            progress_row.setSpacing(6)

            bar_bg = QFrame()
            bar_bg.setFixedHeight(3)
            bar_bg.setStyleSheet(f"background: {BORDER}; border-radius: 2px;")

            pct = int((plan_done / plan_total) * 100)
            bar_fill = QFrame(bar_bg)
            bar_fill.setFixedHeight(3)
            bar_fill.setStyleSheet(f"background: {self._p_color}; border-radius: 2px;")
            # Width set on first paint — use a timer to get the real width
            bar_bg._fill = bar_fill
            bar_bg._pct  = pct
            bar_bg.resizeEvent = lambda e, b=bar_bg: self._resize_bar(b, e)

            step_lbl = QLabel(f"{plan_done}/{plan_total}")
            step_lbl.setFixedWidth(36)
            step_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            step_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 9px;")

            progress_row.addWidget(bar_bg, 1)
            progress_row.addWidget(step_lbl)
            lay.addLayout(progress_row)

        # Row 4: last updated
        updated = data.get("last_updated", "")
        if updated:
            u_lbl = QLabel(updated)
            u_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 9px; opacity: 0.7;")
            lay.addWidget(u_lbl)

    @staticmethod
    def _resize_bar(bar_bg, event):
        """Resize the fill bar proportionally when the container is resized."""
        QFrame.resizeEvent(bar_bg, event)
        fill = getattr(bar_bg, '_fill', None)
        pct  = getattr(bar_bg, '_pct', 0)
        if fill is not None:
            w = max(0, int(bar_bg.width() * pct / 100))
            fill.setGeometry(0, 0, w, 3)

    def thought_id(self) -> str:
        return self._id


# ── Thoughts pane ──────────────────────────────────────────────────────────────
class ThoughtsPane(QWidget):
    """
    Two-section panel:
      TOP    — structured Thought cards, polled from gateway /api/thoughts every 10s
      BOTTOM — live activity log from WS events (think tokens, tool calls, etc.)
    """

    GATEWAY_URL = "http://127.0.0.1:18790"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, ThoughtCard] = {}   # id → widget

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setContentsMargins(10, 6, 8, 6)
        ttl = QLabel("🧠  Thoughts")
        ttl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; font-weight: 600; letter-spacing: 0.06em;")
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
        header.addWidget(ttl)
        header.addStretch()
        header.addWidget(self._status_lbl)
        lay.addLayout(header)

        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER};")
        lay.addWidget(sep)

        # ── Thought cards scroll area ───────────────────────────────────────────
        self._cards_scroll = QScrollArea()
        self._cards_scroll.setWidgetResizable(True)
        self._cards_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._cards_scroll.setMinimumHeight(120)
        self._cards_scroll.setMaximumHeight(400)

        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(8, 8, 8, 8)
        self._cards_layout.setSpacing(6)
        self._cards_layout.addStretch(1)

        self._empty_lbl = QLabel("No active Thoughts")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; font-style: italic;")
        self._cards_layout.insertWidget(0, self._empty_lbl)

        self._cards_scroll.setWidget(self._cards_container)
        lay.addWidget(self._cards_scroll)

        # Separator between cards and log
        sep2 = QLabel()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background: {BORDER};")
        lay.addWidget(sep2)

        # ── Activity log ────────────────────────────────────────────────────────
        log_header = QHBoxLayout()
        log_header.setContentsMargins(10, 4, 8, 4)
        log_ttl = QLabel("Activity")
        log_ttl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px; font-weight: 600; letter-spacing: 0.06em;")
        clear_btn = QPushButton("✕")
        clear_btn.setFixedSize(22, 18)
        clear_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {TEXT_DIM}; border: none; font-size: 10px; }} QPushButton:hover {{ color: #f0f0f0; }}")
        clear_btn.setToolTip("Clear activity log")
        clear_btn.clicked.connect(self._clear)
        log_header.addWidget(log_ttl)
        log_header.addStretch()
        log_header.addWidget(clear_btn)
        lay.addLayout(log_header)

        self.output = QTextBrowser()
        self.output.setStyleSheet(f"""
            QTextBrowser {{
                background: {BG_ALT};
                border: none;
                font-family: "JetBrains Mono", "Consolas", monospace;
                font-size: 10px;
                color: #8080a0;
                padding: 4px 8px;
            }}
        """)
        lay.addWidget(self.output, 1)

        # ── Poll gateway every 10s ─────────────────────────────────────────────
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_thoughts)
        self._poll_timer.start(10000)
        QTimer.singleShot(1500, self._poll_thoughts)   # first poll shortly after startup

    # ── Thought card management ────────────────────────────────────────────────
    def _poll_thoughts(self):
        """Fetch /api/thoughts from gateway and refresh cards."""
        try:
            r = requests.get(f"{self.GATEWAY_URL}/api/thoughts", timeout=3)
            if not r.ok:
                return
            data = r.json()
        except Exception:
            return

        active = data.get("active", [])
        active_ids = {t["id"] for t in active}

        # Remove cards no longer active
        for tid in list(self._cards.keys()):
            if tid not in active_ids:
                card = self._cards.pop(tid)
                self._cards_layout.removeWidget(card)
                card.deleteLater()

        # Add/update cards
        for thought in active:
            tid = thought["id"]
            if tid not in self._cards:
                card = ThoughtCard(thought)
                # Insert before the trailing stretch
                idx = self._cards_layout.count() - 1
                self._cards_layout.insertWidget(idx, card)
                self._cards[tid] = card
            # (For now: recreate to update. Future: diff and patch in place.)

        has_cards = bool(self._cards)
        self._empty_lbl.setVisible(not has_cards)

        # Update status label
        n = len(active)
        pq = data.get("priority_queue", {})
        p1 = len(pq.get("p1", []))
        if n == 0:
            self._status_lbl.setText("idle")
        elif p1 > 0:
            self._status_lbl.setText(f"{n} active · {p1} critical")
            self._status_lbl.setStyleSheet("color: #f87171; font-size: 10px;")
        else:
            self._status_lbl.setText(f"{n} active")
            self._status_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")

    # ── Activity log helpers ───────────────────────────────────────────────────
    def append_thought(self, text: str, color: str = None):
        color = color or TEXT_DIM
        self.output.append(f'<span style="color:{color}">{text}</span>')
        sb = self.output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear(self):
        self.output.clear()

    # Called by ws_client raw signal — handles actual server type names
    def on_raw(self, data: dict):
        t = data.get("type", "")

        if t == "generation_start":
            author = data.get("author", "Nova")
            self.append_thought(f"\n⚡ {author} generating...", NOVA)

        elif t == "think_start":
            self.append_thought("💭 [thinking...]", "#9090cc")

        elif t == "think_token":
            token = data.get("token", "")
            if token:
                cursor = self.output.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.output.setTextCursor(cursor)
                self.output.insertPlainText(token)
                sb = self.output.verticalScrollBar()
                sb.setValue(sb.maximum())

        elif t == "think_end":
            elapsed = data.get("elapsed", 0)
            self.append_thought(f"\n[thinking done — {elapsed}s]", TEXT_DIM)

        elif t == "nova_progress":
            if data.get("final"):
                chars   = data.get("chars", 0)
                elapsed = data.get("elapsed", 0)
                rate    = data.get("rate", 0)
                self.append_thought(f"✓ {chars} chars · {elapsed}s · {rate} ch/s", SUCCESS)

        elif t == "nova_activity":
            directive = data.get("directive", "")
            detail    = data.get("detail", "")
            self.append_thought(f"⚡ [{directive}] {detail}", NOVA)

        elif t == "generation_end":
            elapsed = data.get("elapsed", 0)
            self.append_thought(f"✓ Done — {elapsed}s\n", SUCCESS)

        elif t == "injection_notice":
            path = data.get("path", "")
            who  = data.get("recipients", "")
            self.append_thought(f"📎 inject → {path} ({who})", TEXT_DIM)

        elif t == "error":
            msg    = data.get("message", "")
            author = data.get("author", "")
            self.append_thought(f"❌ {author}: {msg}", ERROR)

        elif t == "thought_update":
            # Server can push thought updates directly over WS too
            self._poll_thoughts()


# ── Assembled sidebar ──────────────────────────────────────────────────────────
class Sidebar(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(220)
        self.setMaximumWidth(520)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setDocumentMode(True)

        self.file_pane     = FileTreePane()
        self.terminal_pane = TerminalPane()
        self.status_pane   = StatusPane()
        self.thoughts_pane = ThoughtsPane()
        self.eyes_pane     = EyesPane()
        self.monitor_pane  = MonitorPane()

        self.tabs.addTab(self.file_pane,     "📁 Files")
        self.tabs.addTab(self.terminal_pane, "⬛ Terminal")
        self.tabs.addTab(self.status_pane,   "◈ Status")
        self.tabs.addTab(self.thoughts_pane, "🧠 Thoughts")
        self.tabs.addTab(self.eyes_pane,     "👁 Eyes")
        self.tabs.addTab(self.monitor_pane,  "📊 Monitor")

        self.file_pane.file_selected.connect(self.file_selected)

        lay.addWidget(self.tabs, 1)

    def add_pane(self, title: str, widget: QWidget):
        """Plug in a new panel — voice, SD, Suno, etc."""
        self.tabs.addTab(widget, title)
