"""
window.py — Main QMainWindow for Nova Qt app.

Assembles: menu bar, dockable panels (left), chat panel (center), status bar (bottom).
Every tool panel is a QDockWidget — pull it out, move it, resize it, float it,
or snap it to any edge. Panels default to a tabified stack on the left.

Owns the WebSocket client and wires its signals to the UI panels.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QStatusBar, QLabel, QPushButton, QMessageBox,
    QDockWidget
)
from PyQt6.QtCore import Qt, QTimer, QSettings
from PyQt6.QtGui import QKeySequence, QShortcut, QAction
import subprocess
import requests
from pathlib import Path

from .ws_client       import NovaWsClient
from .chat_panel      import ChatPanel
from .sidebar         import FileTreePane, TerminalPane, StatusPane, ThoughtsPane
from .eyes_pane       import EyesPane
from .monitor_pane    import MonitorPane
from .settings_dialog import AdvancedSettingsDialog
from .theme           import NOVA, TEXT_DIM, BG, BORDER, SUCCESS, ERROR


class NovaWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Nova")
        self.resize(1440, 920)
        self.setMinimumSize(900, 600)

        # Allow docks to be tabified anywhere, including top/bottom edges
        self.setDockOptions(
            QMainWindow.DockOption.AllowTabbedDocks |
            QMainWindow.DockOption.AllowNestedDocks |
            QMainWindow.DockOption.AnimatedDocks
        )

        self._build_central()
        self._build_docks()
        self._build_menu()
        self._build_statusbar()
        self._connect_ws()
        self._setup_shortcuts()
        self._restore_layout()

    # ── Central widget (chat) ──────────────────────────────────────────────────
    def _build_central(self):
        self.chat_panel = ChatPanel()
        self.setCentralWidget(self.chat_panel)

        # Wire chat panel signals
        self.chat_panel.send_requested.connect(self._on_send)
        self.chat_panel.stop_requested.connect(self._on_stop)
        self.chat_panel.new_session.connect(self._on_new_session)
        self.chat_panel.switch_session.connect(self._on_switch_session)
        self.chat_panel.autonomous_changed.connect(self._on_autonomous_changed)
        self.chat_panel.depth_changed.connect(self._on_depth_changed)
        self.chat_panel.mute_requested.connect(self._on_mute_from_chat)

    # ── Dockable panels ────────────────────────────────────────────────────────
    def _build_docks(self):
        """
        Layout:
          RIGHT (visible by default): Thoughts, Monitor
          LEFT  (hidden by default):  Files, Terminal, Status, Eyes

        Thoughts is the primary panel — always shown on the right.
        Use View menu to toggle any panel.
        """
        self.files_pane    = FileTreePane()
        self.terminal_pane = TerminalPane()
        self.status_pane   = StatusPane()
        self.thoughts_pane = ThoughtsPane()
        self.eyes_pane     = EyesPane()
        self.monitor_pane  = MonitorPane()

        self._docks: dict[str, QDockWidget] = {}

        FEATURES = (
            QDockWidget.DockWidgetFeature.DockWidgetMovable   |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

        # Right-side panels (default visible)
        right_specs = [
            ("thoughts", "🧠  Thoughts",  self.thoughts_pane),
            ("monitor",  "📊  Monitor",   self.monitor_pane),
        ]
        first_right = None
        for key, title, pane in right_specs:
            dock = QDockWidget(title, self)
            dock.setObjectName(f"dock_{key}")
            dock.setWidget(pane)
            dock.setMinimumWidth(260)
            dock.setMinimumHeight(120)
            dock.setFeatures(FEATURES)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
            if first_right:
                self.tabifyDockWidget(first_right, dock)
            else:
                first_right = dock
            self._docks[key] = dock

        # Left-side panels (hidden by default — open from View menu)
        left_specs = [
            ("files",    "📁  Files",     self.files_pane),
            ("terminal", "⬛  Terminal",  self.terminal_pane),
            ("status",   "◈  Status",     self.status_pane),
            ("eyes",     "👁  Eyes",      self.eyes_pane),
        ]
        first_left = None
        for key, title, pane in left_specs:
            dock = QDockWidget(title, self)
            dock.setObjectName(f"dock_{key}")
            dock.setWidget(pane)
            dock.setMinimumWidth(220)
            dock.setMinimumHeight(120)
            dock.setFeatures(FEATURES)
            self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
            if first_left:
                self.tabifyDockWidget(first_left, dock)
            else:
                first_left = dock
            self._docks[key] = dock
            dock.hide()   # hidden by default

        # Thoughts front and center on the right
        self._docks["thoughts"].raise_()
        self._docks["thoughts"].show()

        # Wire file selection to chat input
        self.files_pane.file_selected.connect(self._on_file_selected)

    def _raise_dock(self, key: str):
        """Bring a dock panel to front (show + raise, restoring if closed)."""
        dock = self._docks.get(key)
        if dock:
            dock.setVisible(True)
            dock.raise_()

    # ── Menu bar ───────────────────────────────────────────────────────────────
    def _action(self, text, slot, shortcut=None):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(slot)
        return a

    def _build_menu(self):
        mb = self.menuBar()

        # File menu
        file_menu = mb.addMenu("File")
        file_menu.addAction(self._action("New Session",      self._on_new_session,  "Ctrl+T"))
        file_menu.addSeparator()
        file_menu.addAction(self._action("Attach Image...",  self._on_attach_image))
        file_menu.addSeparator()
        file_menu.addAction(self._action("Terminate Server", self._on_terminate))

        # View menu — one toggle per dock (Qt-native show/hide actions)
        view_menu = mb.addMenu("View")
        view_menu.addAction(self._action("Toggle All Panels", self._toggle_all_docks, "Ctrl+\\"))
        view_menu.addSeparator()
        for key, dock in self._docks.items():
            # Use Qt's built-in toggle action so the check-state stays synced
            view_menu.addAction(dock.toggleViewAction())
        view_menu.addSeparator()
        # Quick-raise shortcuts
        view_menu.addAction(self._action("Show Thoughts", lambda: self._raise_dock("thoughts")))
        view_menu.addAction(self._action("Show Monitor",  lambda: self._raise_dock("monitor")))
        view_menu.addSeparator()
        view_menu.addAction(self._action("Show Files",    lambda: self._raise_dock("files")))
        view_menu.addAction(self._action("Show Terminal", lambda: self._raise_dock("terminal")))
        view_menu.addAction(self._action("Show Eyes",     lambda: self._raise_dock("eyes")))

        # Tools menu
        tools_menu = mb.addMenu("Tools")
        tools_menu.addAction(self._action("Advanced Settings…", self._open_settings, "Ctrl+,"))
        tools_menu.addSeparator()
        tools_menu.addAction(self._action("Start llama.cpp", self._llama_start))
        tools_menu.addAction(self._action("Stop llama.cpp",  self._llama_stop))
        tools_menu.addSeparator()
        tools_menu.addAction(self._action("View Server Logs…", self._show_server_logs, "Ctrl+Shift+L"))
        tools_menu.addSeparator()
        tools_menu.addAction(self._action("Reset Panel Layout", self._reset_layout))
        tools_menu.addSeparator()
        tools_menu.addAction(self._action("Export Session",  self._on_export))

        # Help menu
        help_menu = mb.addMenu("Help")
        help_menu.addAction(self._action("Keyboard Shortcuts", self._show_shortcuts))
        help_menu.addAction(self._action("About Nova",         self._show_about))

    # ── Status bar ─────────────────────────────────────────────────────────────
    def _build_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)

        self.sb_nova_dot   = QLabel("●")
        self.sb_nova_label = QLabel("Nova")
        self.sb_nova_pulse = QLabel("Initializing...")
        self.sb_nova_pulse.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")

        self.sb_llama_btn = QPushButton("⏳ llama.cpp...")
        self.sb_llama_btn.setFlat(True)
        self.sb_llama_btn.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; border: none; padding: 0 6px;")
        self.sb_llama_btn.clicked.connect(self._toggle_llama)

        self.sb_stop_btn = QPushButton("■ STOP")
        self.sb_stop_btn.setObjectName("stop-btn")
        self.sb_stop_btn.setVisible(False)
        self.sb_stop_btn.clicked.connect(self._on_stop)

        # nova_chat server toggle button — green when WS connected, red when not
        self.sb_server_btn = QPushButton("⏳ nova_chat")
        self.sb_server_btn.setFlat(True)
        self.sb_server_btn.setToolTip("nova_chat server — click to start/stop")
        self.sb_server_btn.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; border: none; padding: 0 6px;")
        self.sb_server_btn.clicked.connect(self._on_server_toggle)

        sb.addWidget(self.sb_nova_dot)
        sb.addWidget(self.sb_nova_label)
        sb.addWidget(self.sb_nova_pulse)
        sb.addWidget(self.sb_stop_btn)
        sb.addPermanentWidget(self.sb_server_btn)
        sb.addPermanentWidget(self.sb_llama_btn)

        self._server_running  = False
        self._nova_params     = {"temperature": 0.7, "top_p": 0.9,
                                 "mute_claude": True, "mute_gemini": True}

        # Mute state — Nova active by default; Claude and Gemini muted on startup
        self._mute_states = {"Nova": False, "Claude": True, "Gemini": True}
        self._mute_btns: dict[str, QPushButton] = {}

        # Cole — static label (non-mutable)
        cole_badge = QLabel("● Cole")
        cole_badge.setStyleSheet("color: #e2eaf8; font-size: 11px; padding: 0 6px;")
        sb.addPermanentWidget(cole_badge)

        # AI agents — clickable mute badges
        for name, color in [("Claude", "#d97757"), ("Gemini", "#4e86e4"), ("Nova", "#8f90ff")]:
            btn = QPushButton()
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("agent_name", name)
            btn.setProperty("base_color", color)
            self._apply_mute_badge_style(btn, name, muted=True, connected=False)
            btn.clicked.connect(lambda checked, n=name: self._on_badge_click(n))
            sb.addPermanentWidget(btn)
            self._mute_btns[name] = btn

        # Poll llama status every 10s
        self._llama_running = False
        self._llama_timer = QTimer(self)
        self._llama_timer.timeout.connect(self._poll_llama)
        self._llama_timer.start(10000)
        self._poll_llama()

    # ── WebSocket wiring ───────────────────────────────────────────────────────
    def _connect_ws(self):
        self.ws = NovaWsClient("ws://127.0.0.1:8765/ws")

        # Connection state
        self.ws.connected.connect(self.chat_panel.on_connected)
        self.ws.connected.connect(lambda: self.sb_nova_pulse.setText("Connected"))
        self.ws.connected.connect(self._on_ws_connected)
        self.ws.disconnected.connect(self.chat_panel.on_disconnected)
        self.ws.disconnected.connect(lambda: self.sb_nova_pulse.setText("Disconnected"))
        self.ws.disconnected.connect(self._on_ws_disconnected)
        self.ws.conn_error.connect(self.chat_panel.on_conn_error)
        self.ws.conn_error.connect(self._on_ws_disconnected)

        # Sessions
        self.ws.sessions_init.connect(self.chat_panel.on_sessions)
        self.ws.sessions_update.connect(self.chat_panel.on_sessions)
        self.ws.session_switched.connect(self.chat_panel.on_session_switched)

        # Messages
        self.ws.history_msg.connect(self.chat_panel.on_history)
        self.ws.user_msg.connect(self.chat_panel.on_user_msg)
        self.ws.msg_start.connect(self.chat_panel.on_msg_start)
        self.ws.msg_token.connect(self.chat_panel.on_token)
        self.ws.msg_end.connect(self.chat_panel.on_msg_end)

        # Processing state
        self.ws.processing_start.connect(self.chat_panel.on_processing_start)
        self.ws.processing_start.connect(lambda: self.sb_stop_btn.setVisible(True))
        self.ws.processing_end.connect(self.chat_panel.on_processing_end)
        self.ws.processing_end.connect(lambda: self.sb_stop_btn.setVisible(False))

        # Misc
        self.ws.stopped.connect(lambda n: self.chat_panel.add_system_msg(f"Stopped ({n} cancelled)"))
        self.ws.gateway_error.connect(lambda m: self.statusBar().showMessage(f"⚠ gateway: {m}", 5000))
        self.ws.nova_status.connect(self._on_nova_status)
        self.ws.mute_state.connect(self._on_mute_state)

        # Route raw events to panes
        self.ws.raw.connect(self.thoughts_pane.on_raw)
        self.ws.raw.connect(self.chat_panel.on_raw_think)
        self.ws.raw.connect(self.eyes_pane.on_raw)
        self.ws.raw.connect(self.monitor_pane.on_raw)
        self.ws.injection_notice.connect(self.thoughts_pane.on_raw)

        # Monitor pane direct signals
        self.ws.nova_status.connect(self.monitor_pane.on_nova_status)
        self.ws.connected.connect(self.monitor_pane.on_connected)
        self.ws.disconnected.connect(self.monitor_pane.on_disconnected)
        self.ws.processing_start.connect(self.monitor_pane.on_processing_start)
        self.ws.processing_end.connect(self.monitor_pane.on_processing_end)

        self.ws.start()
        self.chat_panel.add_system_msg("Nova Group Chat — connecting...")

    # ── Shortcuts ──────────────────────────────────────────────────────────────
    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+T"),  self, self._on_new_session)
        QShortcut(QKeySequence("Ctrl+\\"), self, self._toggle_all_docks)
        QShortcut(QKeySequence("Ctrl+L"),  self, lambda: self.chat_panel.input_box.setFocus())
        QShortcut(QKeySequence("Ctrl+/"),  self, self._show_shortcuts)
        QShortcut(QKeySequence("Ctrl+,"),  self, self._open_settings)

    # ── Layout save / restore ──────────────────────────────────────────────────
    # Settings key version — bump this to discard old saved layouts
    _SETTINGS_VERSION = "v2"

    def _restore_layout(self):
        settings = QSettings("ProjectNova", "NovaQt")
        geometry = settings.value(f"geometry_{self._SETTINGS_VERSION}")
        state    = settings.value(f"windowState_{self._SETTINGS_VERSION}")
        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)

    def _save_layout(self):
        settings = QSettings("ProjectNova", "NovaQt")
        settings.setValue(f"geometry_{self._SETTINGS_VERSION}",    self.saveGeometry())
        settings.setValue(f"windowState_{self._SETTINGS_VERSION}", self.saveState())

    def _reset_layout(self):
        """Reset to default: Thoughts+Monitor on right, everything else hidden."""
        for key in self._docks:
            self.removeDockWidget(self._docks[key])

        right_keys = ["thoughts", "monitor"]
        left_keys  = ["files", "terminal", "status", "eyes"]

        first_right = None
        for key in right_keys:
            dock = self._docks[key]
            dock.setFloating(False)
            dock.setVisible(True)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
            if first_right:
                self.tabifyDockWidget(first_right, dock)
            else:
                first_right = dock

        first_left = None
        for key in left_keys:
            dock = self._docks[key]
            dock.setFloating(False)
            self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
            if first_left:
                self.tabifyDockWidget(first_left, dock)
            else:
                first_left = dock
            dock.hide()

        self._docks["thoughts"].raise_()

    # ── WebSocket connection state ─────────────────────────────────────────────
    def _on_ws_connected(self):
        self.sb_nova_dot.setStyleSheet(f"color: {SUCCESS}; font-size: 14px;")
        for name, btn in self._mute_btns.items():
            self._apply_mute_badge_style(btn, name, self._mute_states.get(name, True), connected=True)
        self.sb_server_btn.setText("● nova_chat")
        self.sb_server_btn.setStyleSheet(f"color: {SUCCESS}; font-size: 11px; border: none; padding: 0 6px;")
        self.sb_server_btn.setToolTip("nova_chat server is running — click to stop")
        self._server_running = True
        # Sync startup mute defaults to server so server state matches Qt state
        for agent, muted in self._mute_states.items():
            self.ws.send({"type": "mute_agent", "agent": agent, "muted": muted})

    def _on_ws_disconnected(self):
        self.sb_nova_dot.setStyleSheet(f"color: {TEXT_DIM}; font-size: 14px;")
        for name, btn in self._mute_btns.items():
            self._apply_mute_badge_style(btn, name, self._mute_states.get(name, True), connected=False)
        self.sb_server_btn.setText("🔴 nova_chat")
        self.sb_server_btn.setStyleSheet(f"color: {ERROR}; font-size: 11px; border: none; padding: 0 6px;")
        self.sb_server_btn.setToolTip("nova_chat server is offline — click to start")
        self._server_running = False

    # ── Nova status ────────────────────────────────────────────────────────────
    def _on_nova_status(self, data: dict):
        live  = data.get("nova_live", data)
        task  = live.get("active_task", "")
        pulse = live.get("pulse", "")
        errors = live.get("errors", [])
        text  = task or pulse or "Idle"
        color = ERROR if errors else SUCCESS
        self.sb_nova_dot.setStyleSheet(f"color: {color}; font-size: 14px;")
        self.sb_nova_pulse.setText(text[:60])

    # ── Server toggle ──────────────────────────────────────────────────────────
    def _on_server_toggle(self):
        if self._server_running:
            try:
                requests.post("http://127.0.0.1:8765/shutdown", timeout=2)
            except Exception:
                pass
        else:
            workspace = Path(__file__).resolve().parent.parent.parent
            launch_script = workspace / "general_tools" / "nova_chat" / "launch.py"
            if launch_script.exists():
                subprocess.Popen(
                    ["python", str(launch_script)],
                    cwd=str(workspace),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP") else 0,
                )
                self.sb_server_btn.setText("⏳ nova_chat")
                self.sb_server_btn.setStyleSheet(
                    f"color: {TEXT_DIM}; font-size: 11px; border: none; padding: 0 6px;")
            else:
                QMessageBox.warning(self, "Server", f"launch.py not found at:\n{launch_script}")

    # ── Mute badge helpers ─────────────────────────────────────────────────────
    def _apply_mute_badge_style(self, btn: QPushButton, name: str,
                                muted: bool, connected: bool):
        color = btn.property("base_color") or "#aaaaaa"
        if not connected:
            btn.setText(f"○ {name}")
            btn.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; border: none; padding: 0 4px;")
            btn.setToolTip(f"{name} — server offline")
        elif muted:
            btn.setText(f"🔇 {name}")
            btn.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; border: none; padding: 0 4px;")
            btn.setToolTip(f"{name} is muted — only responds to @{name}. Click to unmute.")
        else:
            btn.setText(f"👂 {name}")
            btn.setStyleSheet(
                f"color: {color}; font-size: 11px; border: none; "
                f"padding: 0 4px; font-weight: 600;")
            btn.setToolTip(f"{name} is listening — responds to all messages. Click to mute.")

    def _on_mute_from_chat(self, agent: str, muted: bool):
        self._on_mute_state(agent, muted)
        self.ws.send_mute_agent(agent, muted)
        state = "muted" if muted else "listening"
        self.chat_panel.add_system_msg(f"{'🔇' if muted else '👂'} {agent} is now {state}")

    def _on_badge_click(self, agent: str):
        current   = self._mute_states.get(agent, True)
        new_muted = not current
        self._mute_states[agent] = new_muted
        btn = self._mute_btns.get(agent)
        if btn:
            self._apply_mute_badge_style(btn, agent, new_muted, connected=self._server_running)
        self.ws.send_mute_agent(agent, new_muted)
        state = "muted" if new_muted else "listening"
        self.chat_panel.add_system_msg(f"{'🔇' if new_muted else '👂'} {agent} is now {state}")

    def _on_mute_state(self, agent: str, muted: bool):
        self._mute_states[agent] = muted
        btn = self._mute_btns.get(agent)
        if btn:
            self._apply_mute_badge_style(btn, agent, muted, connected=self._server_running)

    # ── Action handlers ────────────────────────────────────────────────────────
    def _on_autonomous_changed(self, enabled: bool):
        self.ws.send_autonomous(enabled)
        self.monitor_pane.update_autonomous(enabled)

    def _on_depth_changed(self, max_tokens: int):
        self.ws.send_depth(max_tokens)
        self.monitor_pane.update_depth(max_tokens)

    def _on_send(self, text: str):
        self.ws.send_message(text)

    def _on_stop(self):
        self.ws.send_stop()
        self.chat_panel.on_processing_end()
        self.sb_stop_btn.setVisible(False)

    def _on_new_session(self):
        self.ws.new_session()

    def _on_switch_session(self, session_id: str):
        self.ws.switch_session(session_id)

    def _on_file_selected(self, path: str):
        self.chat_panel.input_box.setPlainText(
            f"[INJECT: {path}]\n" + self.chat_panel.input_box.toPlainText()
        )
        self.chat_panel.input_box.setFocus()

    def _on_attach_image(self):
        from PyQt6.QtWidgets import QFileDialog
        QFileDialog.getOpenFileNames(
            self, "Attach Image", "", "Images (*.png *.jpg *.jpeg *.webp *.gif)"
        )
        # TODO: encode to base64 and send in ws payload

    def _toggle_all_docks(self):
        """Hide all docks if any are visible; show all if all hidden."""
        any_visible = any(d.isVisible() for d in self._docks.values())
        for dock in self._docks.values():
            dock.setVisible(not any_visible)

    def _toggle_llama(self):
        if self._llama_running:
            self._llama_stop()
        else:
            self._llama_start()

    def _llama_start(self):
        try:
            requests.post("http://127.0.0.1:8765/api/llama/start", timeout=5)
            QTimer.singleShot(5000, self._poll_llama)
        except Exception:
            pass

    def _llama_stop(self):
        try:
            requests.post("http://127.0.0.1:8765/api/llama/stop", timeout=5)
            QTimer.singleShot(2000, self._poll_llama)
        except Exception:
            pass

    def _poll_llama(self):
        try:
            r = requests.get("http://127.0.0.1:8765/api/llama/status", timeout=2)
            d = r.json()
            running = d.get("running", False)
            self._llama_running = running
            if running:
                self.sb_llama_btn.setText("● llama.cpp ON")
                self.sb_llama_btn.setStyleSheet(
                    f"color: {SUCCESS}; font-size: 11px; border: none; padding: 0 6px;")
            else:
                self.sb_llama_btn.setText("🔴 llama.cpp OFF")
                self.sb_llama_btn.setStyleSheet(
                    f"color: {ERROR}; font-size: 11px; border: none; padding: 0 6px;")
        except Exception:
            self._llama_running = False
            self.sb_llama_btn.setText("🔴 Server offline")
            self.sb_llama_btn.setStyleSheet(
                f"color: {ERROR}; font-size: 11px; border: none; padding: 0 6px;")

    def _on_export(self):
        self.ws.send({"type": "export_request"})

    def _on_terminate(self):
        try:
            requests.post("http://127.0.0.1:8765/shutdown", timeout=2)
        except Exception:
            pass
        self.close()

    def _open_settings(self):
        dlg = AdvancedSettingsDialog(current=self._nova_params, parent=self)
        dlg.params_changed.connect(self._on_params_changed)
        dlg.exec()

    def _on_params_changed(self, params: dict):
        self._nova_params.update(params)
        self.ws.send({"type": "set_params",
                      "temperature": params["temperature"],
                      "top_p": params["top_p"]})
        self.ws.send({"type": "mute_agent", "agent": "Claude",
                      "muted": params["mute_claude"]})
        self.ws.send({"type": "mute_agent", "agent": "Gemini",
                      "muted": params["mute_gemini"]})
        self.monitor_pane.on_raw({
            "type": "params_update",
            "temperature": params["temperature"],
            "top_p": params["top_p"],
        })

    def _show_shortcuts(self):
        QMessageBox.information(self, "Keyboard Shortcuts",
            "Ctrl+T          New Session\n"
            "Ctrl+\\         Show/Hide All Panels\n"
            "Ctrl+L          Focus Input\n"
            "Ctrl+/          Show Shortcuts\n"
            "Ctrl+,          Advanced Settings\n"
            "Enter           Send Message\n"
            "Shift+Enter     New Line\n"
            "\n"
            "Panels are dockable — drag their title bar to\n"
            "move, float, or snap to any edge. Use\n"
            "Tools > Reset Panel Layout to restore defaults."
        )

    def _show_about(self):
        QMessageBox.about(self, "Project Nova",
            "<b>Project Nova</b><br>"
            "Multi-agent AI workspace.<br><br>"
            "Nova · Claude · Gemini · Cole<br>"
            "Built with PyQt6 + FastAPI."
        )

    def _show_server_logs(self):
        """
        Ctrl+Shift+L — Opens a log viewer dialog showing the server's real-time
        print() output (fetched from http://127.0.0.1:8765/logs).
        Has Copy and Refresh buttons.  Intended for troubleshooting with Claude.
        """
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                     QTextEdit, QPushButton, QLabel, QLineEdit)
        from PyQt6.QtGui import QFont, QClipboard
        from PyQt6.QtCore import Qt
        from .theme import BG, TEXT, TEXT_DIM, NOVA, BORDER

        dlg = QDialog(self)
        dlg.setWindowTitle("Server Logs — nova_chat")
        dlg.setMinimumSize(820, 560)
        dlg.setStyleSheet(f"QDialog {{ background: {BG}; color: {TEXT}; }}")

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)

        # Filter row
        filter_row = QHBoxLayout()
        filter_lbl = QLabel("Filter:")
        filter_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        filter_input = QLineEdit()
        filter_input.setPlaceholderText("e.g. claude  nova  error")
        filter_input.setStyleSheet(
            f"background: #1a1a2a; color: {TEXT}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 3px 8px; font-size: 12px;")
        filter_row.addWidget(filter_lbl)
        filter_row.addWidget(filter_input, 1)
        lay.addLayout(filter_row)

        # Log text area
        text_area = QTextEdit()
        text_area.setReadOnly(True)
        text_area.setFont(QFont("Consolas", 10))
        text_area.setStyleSheet(
            f"background: #10101a; color: {TEXT}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 6px;")
        lay.addWidget(text_area, 1)

        status_lbl = QLabel("")
        status_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
        lay.addWidget(status_lbl)

        def _fetch():
            filt = filter_input.text().strip()
            url = f"http://127.0.0.1:8765/logs?n=300"
            if filt:
                import urllib.parse
                url += f"&filter={urllib.parse.quote(filt)}"
            try:
                import urllib.request
                with urllib.request.urlopen(url, timeout=4) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                text_area.setPlainText(raw)
                # Scroll to bottom
                sb = text_area.verticalScrollBar()
                sb.setValue(sb.maximum())
                status_lbl.setText(f"Fetched {len(raw)} chars  •  {__import__('datetime').datetime.now().strftime('%H:%M:%S')}")
            except Exception as e:
                text_area.setPlainText(f"[Error fetching logs: {e}]\n\nMake sure nova_chat server is running on port 8765.")
                status_lbl.setText("Fetch failed")

        def _copy():
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(text_area.toPlainText())
            status_lbl.setText("Copied to clipboard!")

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.setStyleSheet(
            f"background: #1a1a2a; color: {TEXT_DIM}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 4px 14px; font-size: 12px;")
        refresh_btn.clicked.connect(_fetch)
        btn_row.addWidget(refresh_btn)

        copy_btn = QPushButton("Copy All")
        copy_btn.setDefault(True)
        copy_btn.setStyleSheet(
            f"background: {NOVA}22; color: {NOVA}; border: 1px solid {NOVA}66; "
            f"border-radius: 4px; padding: 4px 18px; font-size: 12px; font-weight: 600;")
        copy_btn.clicked.connect(_copy)
        btn_row.addWidget(copy_btn)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            f"background: transparent; color: {TEXT_DIM}; border: 1px solid {BORDER}; "
            f"border-radius: 4px; padding: 4px 14px; font-size: 12px;")
        close_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(close_btn)

        lay.addLayout(btn_row)

        # Wire filter enter → refresh
        filter_input.returnPressed.connect(_fetch)

        # Auto-fetch on open
        _fetch()

        # Auto-refresh every 5s while dialog is open
        _timer = QTimer(dlg)
        _timer.timeout.connect(_fetch)
        _timer.start(5000)

        dlg.exec()

    def closeEvent(self, event):
        self._save_layout()
        self.ws.stop()
        # Shut down the FastAPI server (which also kills llama.cpp in its shutdown_event)
        try:
            import requests as _req
            _req.post("http://127.0.0.1:8765/shutdown", timeout=3)
        except Exception:
            pass
        event.accept()
