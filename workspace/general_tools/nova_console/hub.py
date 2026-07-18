# Last updated: 2026-07-19 00:07:26
# @nova: Nova Console — the log hub. Captures every child process's output into in-memory
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
        # PIDs of Nova's process tree roots. The console app's stray-window janitor asks for these
        # so it can tell "a console owned by Nova" from "Cole's own terminal" — we must never hide
        # a window that isn't ours.
        self.pids: list[int] = []

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

            def do_POST(self):
                u = urlparse(self.path)
                if u.path == "/api/show":
                    hub._show_req = True
                    return self._send({"ok": True})
                if u.path == "/api/shutdown":
                    hub._shutdown_req = True
                    return self._send({"ok": True, "message": "graceful shutdown requested"})
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
            except Exception:
                pass
