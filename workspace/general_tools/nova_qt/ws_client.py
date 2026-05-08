"""
ws_client.py — WebSocket client thread for Nova Qt app.

Runs in a QThread. Emits Qt signals for every message type so the
UI thread can update safely. Handles reconnection automatically.

Signal mapping (matches server.py broadcast types exactly):
  history_msg     ← "history"          (past messages on connect)
  user_msg        ← "user_message"     (Cole/Nova/System posting)
  msg_start       ← "message_start"    (AI starting to respond)
  msg_token       ← "token"            (streaming token)
  msg_end         ← "message_end"      (AI response complete)
  sessions_init   ← "sessions_init"
  sessions_update ← "sessions_updated"
  session_switched← "session_switched" (tab switch + history reload)
  processing_start← "processing_start"
  processing_end  ← "processing_end"
  stopped         ← "stopped"
  injection_notice← "injection_notice"
  gateway_error   ← "gateway_error"
  raw             ← everything else
"""
import json
import time
import threading
from PyQt6.QtCore import QThread, pyqtSignal

try:
    import websocket  # websocket-client
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False


class NovaWsClient(QThread):
    """
    Persistent WebSocket connection to nova_chat server (ws://127.0.0.1:8765/ws).
    All server→client messages are parsed and re-emitted as typed Qt signals.
    """

    # ── Connection signals ────────────────────────────────────────────────────
    connected       = pyqtSignal()
    disconnected    = pyqtSignal()
    conn_error      = pyqtSignal(str)

    # ── Message signals (server → UI) ─────────────────────────────────────────
    history_msg     = pyqtSignal(dict)   # {author, content, id, timestamp}
    user_msg        = pyqtSignal(dict)   # {author, content, id, timestamp, ...}
    msg_start       = pyqtSignal(dict)   # {author, id}  — AI starting a response
    msg_token       = pyqtSignal(dict)   # {author, token, id}
    msg_end         = pyqtSignal(dict)   # {author, id}  — AI response done

    # ── Session signals ───────────────────────────────────────────────────────
    sessions_init    = pyqtSignal(list)   # list of session dicts
    sessions_update  = pyqtSignal(list)
    session_switched = pyqtSignal(dict)   # {session_id, sessions, history}

    # ── Processing state ──────────────────────────────────────────────────────
    processing_start = pyqtSignal()
    processing_end   = pyqtSignal()
    stopped          = pyqtSignal(int)   # cancelled count

    # ── Misc ──────────────────────────────────────────────────────────────────
    injection_notice = pyqtSignal(dict)
    gateway_error    = pyqtSignal(str)
    nova_status      = pyqtSignal(dict)
    mute_state       = pyqtSignal(str, bool)  # agent_name, is_muted
    raw              = pyqtSignal(dict)  # catch-all for unhandled types

    # ── Init ──────────────────────────────────────────────────────────────────
    def __init__(self, url="ws://127.0.0.1:8765/ws", parent=None):
        super().__init__(parent)
        self.url = url
        self._ws = None
        self._stop_flag = threading.Event()

    # ── Thread entry ──────────────────────────────────────────────────────────
    def run(self):
        if not WS_AVAILABLE:
            self.conn_error.emit("websocket-client not installed. Run: pip install websocket-client")
            return

        while not self._stop_flag.is_set():
            try:
                self._ws = websocket.WebSocketApp(
                    self.url,
                    on_open    = self._on_open,
                    on_message = self._on_message,
                    on_error   = self._on_error,
                    on_close   = self._on_close,
                )
                self._ws.run_forever(ping_interval=60, ping_timeout=45)
            except Exception as e:
                self.conn_error.emit(str(e))

            if not self._stop_flag.is_set():
                time.sleep(2)   # reconnect delay

    def stop(self):
        self._stop_flag.set()
        if self._ws:
            self._ws.close()

    # ── Send ──────────────────────────────────────────────────────────────────
    def send(self, payload: dict):
        if self._ws and self._ws.sock:
            try:
                self._ws.send(json.dumps(payload))
            except Exception:
                pass

    def send_message(self, content: str, images: list = None, telemetry: str = ""):
        payload = {"type": "message", "content": content}
        if images:
            payload["images"] = images
        if telemetry:
            payload["telemetry"] = telemetry
        self.send(payload)

    def send_stop(self):
        self.send({"type": "stop"})

    def send_autonomous(self, enabled: bool):
        self.send({"type": "autonomous_toggle", "enabled": enabled})

    def send_depth(self, max_tokens: int):
        """Tell the server how many tokens Nova should generate (depth slider)."""
        self.send({"type": "set_depth", "max_tokens": max_tokens})

    def send_mute_agent(self, agent: str, muted: bool):
        """Mute or unmute an agent. Muted agents only respond when @mentioned."""
        self.send({"type": "mute_agent", "agent": agent, "muted": muted})

    def new_session(self):
        self.send({"type": "new_session"})

    def switch_session(self, session_id: str):
        self.send({"type": "switch_session", "session_id": session_id})

    # ── WS callbacks (called from ws thread — only emit signals here) ─────────
    def _on_open(self, ws):
        self.connected.emit()

    def _on_close(self, ws, code, msg):
        self.disconnected.emit()

    def _on_error(self, ws, err):
        self.conn_error.emit(str(err))

    def _on_message(self, ws, raw_msg):
        try:
            data = json.loads(raw_msg)
        except Exception:
            return

        t = data.get("type", "")

        # ── History (sent on connect for past messages) ────────────────────────
        if t == "history":
            self.history_msg.emit(data)

        # ── Live chat messages ─────────────────────────────────────────────────
        elif t == "user_message":
            self.user_msg.emit(data)

        elif t == "message_start":
            self.msg_start.emit(data)

        elif t == "token":
            self.msg_token.emit(data)

        elif t == "message_end":
            self.msg_end.emit(data)

        # ── Session management ─────────────────────────────────────────────────
        elif t == "sessions_init":
            self.sessions_init.emit(data.get("sessions", []))

        elif t == "sessions_updated":
            self.sessions_update.emit(data.get("sessions", []))

        elif t == "session_switched":
            # Emit sessions list for tab update AND full data for history reload
            self.sessions_init.emit(data.get("sessions", []))
            self.session_switched.emit(data)

        # ── Processing state ───────────────────────────────────────────────────
        elif t == "processing_start":
            self.processing_start.emit()

        elif t == "processing_end":
            self.processing_end.emit()

        elif t == "stopped":
            self.stopped.emit(data.get("cancelled", 0))

        # ── Misc ───────────────────────────────────────────────────────────────
        elif t == "injection_notice":
            self.injection_notice.emit(data)

        elif t == "gateway_error":
            self.gateway_error.emit(data.get("message", ""))

        elif t == "nova_status":
            self.nova_status.emit(data)

        elif t == "mute_state":
            agent = data.get("agent", "")
            muted = bool(data.get("muted", True))
            if agent:
                self.mute_state.emit(agent, muted)

        # status, blocked, export_ready, think_*, nova_progress, etc. → raw
        else:
            self.raw.emit(data)
