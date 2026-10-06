# @nova: Nova Console — the log hub. Captures every child process's output into in-memory
# Last updated: 2026-10-06 03:19:20
# ring buffers and serves them over a tiny local HTTP API, so the stack can run with ZERO
# popup cmd windows while everything stays visible in one place.
#
# WHY: NovaStart used to spawn 4+ separate consoles (launcher, llama-server, NovaLauncher,
# watcher) — plus another every time llama restarted. They're now spawned with CREATE_NO_WINDOW
# and piped in here instead.
#
# Two capture modes:
#   attach_pipe(name, proc)  — pump a child's stdout/stderr (we own the process)
#   tail_file(name, glob)    — tail the newest file matching a glob. Used for llama-server,
#                              because LlamaControl restarts it OUT OF BAND (LoRA equip /
#                              Full Restart), so a pipe we opened would go dead. Tailing the
#                              log file survives those restarts.
#
# The HTTP API is consumed by BOTH the standalone console app and the Nova Chat widget, so the
# two can never show different data.

import json
import threading
import time
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

try:
    from . import plainspeak
except ImportError:                    # run as a loose script, not a package
    import plainspeak

HUB_PORT = 8799
MAX_LINES = 4000          # per stream ring buffer
_CONTROL_BODY_LIMIT = 4096
_CONTROL_BODY_TIMEOUT = 2.0


class _Stream:
    def __init__(self, name: str, label: str, order: int):
        self.name = name
        self.label = label
        self.order = order
        self.lines = deque(maxlen=MAX_LINES)   # (seq, ts, text, plain)
        self.seq = 0
        self.lock = threading.Lock()
        self.alive = False

    def write(self, text: str) -> None:
        text = (text or "").rstrip("\r\n")
        if not text:
            return
        # Translate ONCE at write time, not per request — the UI polls constantly.
        # plain() returns None when we have no rule, and the UI then shows the raw line:
        # we never invent a translation just to have something friendly to display.
        try:
            p = plainspeak.plain(text)
        except Exception:
            p = None
        with self.lock:
            self.seq += 1
            self.lines.append((self.seq, datetime.now().strftime("%H:%M:%S"), text, p))

    def since(self, n: int):
        with self.lock:
            return [
                {"seq": s, "ts": t, "text": x, "plain": p}
                for (s, t, x, p) in self.lines if s > n
            ], self.seq


class LogHub:
    def __init__(self, workspace: Path):
        self.ws = Path(workspace)
        self.streams: dict[str, _Stream] = {}
        self._order = 0
        self._httpd = None
        self._stop = threading.Event()
        # Set by POST /api/show (the Nova Chat widget's "Open window" button); the console app
        # polls GET /api/show-pending and raises itself. This is how the widget can summon the
        # desktop window out of the tray.
        self._show_req = False
        # Set by POST /api/shutdown (StopNova.cmd). nova_start.py watches this and runs its normal
        # graceful teardown — which matters because stop_watcher() sends CTRL_BREAK so the watcher
        # can finish its git push instead of leaving a stale .git/index.lock behind. A blunt
        # taskkill cannot do that, which is why StopNova asks nicely FIRST.
        self._shutdown_req = False
        self._restart_req = False
        self._lifecycle_lock = threading.Lock()
        self._lifecycle_ready_at = None
        self._nova_mode = None
        # PIDs of Nova's process tree roots. The console app's stray-window janitor asks for these
        # so it can tell "a console owned by Nova" from "Cole's own terminal" — we must never hide
        # a window that isn't ours.
        self.pids: list[int] = []

    def request_lifecycle(self, action: str):
        """Acknowledge one pending action; repeated clicks cannot race shutdown/restart."""
        with self._lifecycle_lock:
            if self._nova_mode is not None and self._nova_mode.snapshot()["pending"]:
                return {"ok": False, "error": "A Nova mode change is pending."}, 409
            pending = "restart" if self._restart_req else "shutdown" if self._shutdown_req else None
            if pending and pending != action:
                return {"ok": False, "error": f"{pending} is already pending"}, 409
            if pending is None:
                # Chat-only teardown is fast enough to kill the proxy before its 202
                # reaches the caller. Give the first accepted request a bounded grace
                # period; retries cannot keep postponing shutdown.
                self._lifecycle_ready_at = time.monotonic() + 1.0
            self._restart_req = action == "restart"
            self._shutdown_req = True
            return {"ok": True, "accepted": True, "action": action,
                    "message": f"Launcher accepted {action}; app and services will stop together."}, 202

    def configure_nova(self, chat_only, handler):
        from .lifecycle import NovaModeState
        with self._lifecycle_lock:
            self._nova_mode = NovaModeState(chat_only, handler)

    def nova_status(self):
        if self._nova_mode is None:
            return {"ok": False, "state": "error", "pending": False, "target": None,
                    "chat_only": None, "message": "Launcher mode control is not ready.",
                    "error": "Launcher mode control is not ready."}
        return self._nova_mode.snapshot()

    def request_nova(self, action):
        if action not in ("start", "stop"):
            return {"ok": False, "error": "Unknown Nova lifecycle action."}, 400
        with self._lifecycle_lock:
            if self._shutdown_req or self._restart_req:
                return {"ok": False, "error": "App shutdown or restart is already pending."}, 409
            if self._nova_mode is None:
                return self.nova_status(), 503
            return self._nova_mode.request(action == "stop")

    def process_nova_request(self):
        return self._nova_mode.process() if self._nova_mode is not None else False

    def lifecycle_ready(self) -> bool:
        """A pending action may tear down after its original acknowledgement grace."""
        with self._lifecycle_lock:
            return (self._shutdown_req and self._lifecycle_ready_at is not None
                    and time.monotonic() >= self._lifecycle_ready_at)

    # ── stream registry ───────────────────────────────────────────────────────
    def add_stream(self, name: str, label: str) -> _Stream:
        self._order += 1
        st = _Stream(name, label, self._order)
        self.streams[name] = st
        return st

    def write(self, name: str, text: str) -> None:
        st = self.streams.get(name)
        if st is None:
            st = self.add_stream(name, name.title())
        st.write(text)

    # ── capture: pipe (we own the process) ────────────────────────────────────
    def attach_pipe(self, name: str, proc, also_file: Path | None = None) -> None:
        st = self.streams.get(name) or self.add_stream(name, name.title())
        st.alive = True

        def _pump():
            fh = None
            try:
                if also_file:
                    also_file.parent.mkdir(parents=True, exist_ok=True)
                    fh = open(also_file, "a", encoding="utf-8", errors="replace")
                for raw in iter(proc.stdout.readline, b""):
                    if self._stop.is_set():
                        break
                    line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    st.write(line)
                    if fh:
                        fh.write(line + "\n")
                        fh.flush()
            except Exception as e:
                st.write(f"[hub] pipe closed: {e}")
            finally:
                st.alive = False
                if fh:
                    try:
                        fh.close()
                    except Exception:
                        pass

        threading.Thread(target=_pump, name=f"hub-pipe-{name}", daemon=True).start()

    # ── capture: tail newest file matching a glob (survives out-of-band restarts) ──
    def tail_file(self, name: str, directory: Path, pattern: str = "*.log") -> None:
        st = self.streams.get(name) or self.add_stream(name, name.title())

        def _tail():
            cur, fh, pos, first = None, None, 0, True
            while not self._stop.is_set():
                try:
                    directory.mkdir(parents=True, exist_ok=True)
                    files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime)
                    newest = files[-1] if files else None
                    if newest and newest != cur:
                        if fh:
                            try:
                                fh.close()
                            except Exception:
                                pass
                        cur = newest
                        fh = open(cur, "r", encoding="utf-8", errors="replace")
                        # FIRST attach: skip to the end so we don't dump the whole day's history.
                        # A LATER switch means llama RESTARTED into a fresh log (LoRA equip / Full
                        # Restart) — read that one from byte 0, or we'd miss the boot lines that
                        # were written before we noticed the file. (Caught in test: the restart
                        # content was silently skipped.)
                        if first:
                            fh.seek(0, 2)
                            first = False
                        else:
                            fh.seek(0)
                        pos = fh.tell()
                        st.write(f"[hub] following {cur.name}")
                        st.alive = True
                    if fh:
                        fh.seek(pos)
                        for line in fh:
                            st.write(line)
                        pos = fh.tell()
                except Exception as e:
                    st.write(f"[hub] tail error: {e}")
                time.sleep(0.6)

        threading.Thread(target=_tail, name=f"hub-tail-{name}", daemon=True).start()

    # ── HTTP API (consumed by the console app AND the Nova Chat widget) ───────
    def serve(self, port: int = HUB_PORT) -> None:
        hub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):        # silence stdlib access logging
                pass

            def _send(self, obj, code=200):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                # CORS: the Nova Chat page is served from :8765, this API is :8799.
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.end_headers()

            def _read_control_body(self):
                """Consume one bounded JSON object before acknowledging a control action.

                HTTP/1.0 closes after the response. Leaving the POST body unread can
                reset that connection on Windows, even after the action was accepted.
                Empty bodies remain supported for StopNova.cmd's legacy POST.
                """
                def reject(code, message):
                    self._send({"ok": False, "error": message}, code)
                    return False

                lengths = self.headers.get_all("Content-Length", [])
                if self.headers.get("Transfer-Encoding"):
                    return reject(400, "Control requests do not support Transfer-Encoding.")
                raw_length = lengths[0].strip() if len(lengths) == 1 else "0"
                if len(lengths) > 1 or not raw_length.isascii() or not raw_length.isdecimal():
                    return reject(400, "Control requests require a valid Content-Length.")
                if len(raw_length) > 10 or int(raw_length) > _CONTROL_BODY_LIMIT:
                    return reject(413, "Control request body exceeds 4096 bytes.")
                length = int(raw_length)
                previous_timeout = self.connection.gettimeout()
                try:
                    self.connection.settimeout(_CONTROL_BODY_TIMEOUT)
                    body = self.rfile.read(length)
                except TimeoutError:
                    return reject(408, "Control request body timed out; no action was accepted.")
                except OSError:
                    return False  # Disconnected peer; never dispatch a partial request.
                finally:
                    self.connection.settimeout(previous_timeout)
                if len(body) != length:
                    return reject(400, "Control request body is incomplete; no action was accepted.")
                if body:
                    def invalid_constant(value):
                        raise ValueError("Nonstandard JSON constant")
                    try:
                        value = json.loads(body.decode("utf-8"), parse_constant=invalid_constant)
                    except (UnicodeDecodeError, ValueError):
                        return reject(400, "Control request body must be a JSON object.")
                    if not isinstance(value, dict):
                        return reject(400, "Control request body must be a JSON object.")
                return True

            def do_POST(self):
                u = urlparse(self.path)
                if u.path in ("/api/nova/start", "/api/nova/stop", "/api/shutdown", "/api/restart"):
                    if not self._read_control_body():
                        return
                if u.path in ("/api/nova/start", "/api/nova/stop"):
                    # The same-origin Nova Chat proxy is the public entry point. Do not
                    # expose a cross-site form/JavaScript path that starts GPU services.
                    host = self.headers.get("Host", "").lower()
                    allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
                    if self.client_address[0] != "127.0.0.1" or host not in allowed or self.headers.get("Origin") \
                            or any(self.headers.get(key) for key in ("Forwarded", "X-Forwarded-For", "X-Forwarded-Host")) \
                            or self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                        return self._send({"ok": False, "error": "Use Nova Chat's local lifecycle controls."}, 403)
                    result, code = hub.request_nova(u.path.rsplit("/", 1)[-1])
                    return self._send(result, code)
                if u.path == "/api/show":
                    hub._show_req = True
                    return self._send({"ok": True})
                if u.path in ("/api/shutdown", "/api/restart"):
                    result, code = hub.request_lifecycle(u.path.rsplit("/", 1)[-1])
                    return self._send(result, code)
                if u.path == "/api/write":
                    # The console app's janitor reports stray windows here, so they land in the
                    # SAME stream set the widget reads. One source of truth, as everywhere else.
                    try:
                        n = int(self.headers.get("Content-Length", 0))
                        d = json.loads(self.rfile.read(n) or b"{}")
                        hub.write(d.get("stream", "strays"), d.get("text", ""))
                        return self._send({"ok": True})
                    except Exception as e:
                        return self._send({"error": str(e)}, 400)
                return self._send({"error": "not found"}, 404)

            def do_GET(self):
                u = urlparse(self.path)
                q = parse_qs(u.query)
                if u.path == "/api/nova/status":
                    return self._send(hub.nova_status(), 200 if hub._nova_mode is not None else 503)
                if u.path == "/health":
                    return self._send({"ok": True})
                if u.path == "/api/show-pending":
                    pending, hub._show_req = hub._show_req, False
                    return self._send({"show": pending})
                if u.path == "/api/pids":
                    return self._send({"pids": hub.pids})
                if u.path == "/api/streams":
                    return self._send({"streams": [
                        {"name": s.name, "label": s.label, "alive": s.alive, "seq": s.seq}
                        for s in sorted(hub.streams.values(), key=lambda s: s.order)
                    ]})
                if u.path == "/api/log":
                    name = (q.get("stream") or [""])[0]
                    since = int((q.get("since") or ["0"])[0])
                    st = hub.streams.get(name)
                    if st is None:
                        return self._send({"error": "no such stream"}, 404)
                    lines, seq = st.since(since)
                    return self._send({"stream": name, "lines": lines, "seq": seq,
                                       "alive": st.alive})
                return self._send({"error": "not found"}, 404)

        self._httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        threading.Thread(target=self._httpd.serve_forever,
                         name="hub-http", daemon=True).start()

    def shutdown(self) -> None:
        self._stop.set()
        if self._httpd:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception:
                pass
