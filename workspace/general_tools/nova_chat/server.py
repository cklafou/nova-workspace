# @nova: Nova's voice — chat server (FastAPI/WebSocket on :8765), cross-AI @mention routing to Claude/Gemini, and the runtime host that fires her body's autonomy faculty (nova_cortex.executive).
"""
Nova Group Chat - FastAPI WebSocket Server
Handles real-time streaming from all three AIs concurrently.
Nova can POST messages via /nova-message endpoint.
Context exports available via /export endpoint.
"""
import os
import json
import asyncio
import uuid
import time
from pathlib import Path
import sys
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from nova_chat.transcript import Transcript
from nova_chat.session_manager import SessionManager
from nova_chat.orchestrator import parse_directed, should_respond, build_response_queue, is_ncl_message
from nova_chat.context_export import export_session
from nova_chat.workspace_context import WorkspaceContext
import nova_chat.clients.claude as claude_client
import nova_chat.clients.gemini as gemini_client
import nova_chat.clients.nova as nova_client
from nova_chat.nova_bridge import handle_nova_message, parse_actions

# ── In-memory log ring buffer ─────────────────────────────────────────────────
# Captures all print() output from the server process so /logs can return it
# without any git-sync delay.  Keeps the last LOG_RING_SIZE lines.
import collections as _collections
import threading as _threading

LOG_RING_SIZE  = 1000
_log_ring: _collections.deque = _collections.deque(maxlen=LOG_RING_SIZE)
_log_lock  = _threading.Lock()

class _TeeStream:
    """Wraps sys.stdout/sys.stderr, writes to original stream AND _log_ring."""
    def __init__(self, original):
        self._orig = original
        self._buf  = ""

    def write(self, text):
        self._orig.write(text)
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line:   # skip blank lines
                entry = f"{datetime.now().strftime('%H:%M:%S')}  {line}"
                with _log_lock:
                    _log_ring.append(entry)

    def flush(self):
        self._orig.flush()

    def fileno(self):
        return self._orig.fileno()

    def isatty(self):
        return False

    def reconfigure(self, **kwargs):
        # Forward reconfigure() calls to the underlying stream.
        # Some modules call sys.stdout.reconfigure(encoding='utf-8') at import
        # time; _TeeStream must not swallow that call or it raises AttributeError.
        if hasattr(self._orig, "reconfigure"):
            self._orig.reconfigure(**kwargs)

    def __getattr__(self, name):
        # Catch-all: delegate any other stream attributes (e.g. encoding,
        # errors, buffer) to the underlying stream so _TeeStream is a
        # transparent wrapper for code that probes stream capabilities.
        return getattr(self._orig, name)

sys.stdout = _TeeStream(sys.stdout)
sys.stderr = _TeeStream(sys.stderr)

try:
    from nova_lancedb.indexer import get_indexer
    memory_indexer = get_indexer()
    memory_indexer.start()
except ImportError:
    memory_indexer = None
    print("[server] WARNING: nova_memory not found. Persistent memory indexing disabled.")

app = FastAPI()

@app.on_event("shutdown")
async def shutdown_event():
    if memory_indexer:
        memory_indexer.stop()
    # Kill llama-server on port 8080 so it doesn't outlive the Nova process
    try:
        import subprocess as _sp
        _sp.run(
            ["powershell", "-Command",
             "Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | "
             "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"],
            capture_output=True, text=True, timeout=8,
        )
        print("[shutdown] llama-server on port 8080 stopped.")
    except Exception as e:
        print(f"[shutdown] llama stop error: {e}")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

try:
    session_mgr = SessionManager()  # persistent sessions, resumes last
except Exception as e:
    print(f"[server] SessionManager init error: {e} -- starting fresh")
    from nova_chat.session_manager import SessionManager as _SM
    session_mgr = _SM.__new__(_SM)
    from nova_chat.session_manager import SESSIONS_DIR
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_mgr._index = {}
    session_mgr._active_id = ""
    session_mgr._active_transcript = None
    session_mgr.new_session()

workspace = WorkspaceContext()  # lazy: loads memory/ now, indexes disk on first message

# Nova identity (AGENTS.md, NOVA.md, TOOLS.md) is now injected inside
# workspace_context.build_nova_context_block() so it works for both the live
# server and the compiled Nova.exe without any extra init here.

connected_clients: list[WebSocket] = []
active_tasks: list[asyncio.Task] = []
is_processing: bool = False
_stop_requested = asyncio.Event()  # set by STOP; cleared at start of every new response

# ── Cole message queue ────────────────────────────────────────────────────────
# When Cole sends a message while AIs are processing, we queue it instead of
# dropping it. The queue is drained as soon as is_processing becomes False.
# Each entry: {"content": str, "full_context_content": str, "directed_at": list,
#              "images": list, "msg": dict}
_cole_message_queue: list[dict] = []

_eyes_running: bool = False        # tracks desktop streaming state
# 1.3 -- Nova status cache: polled every 30s, injected silently into AI context
nova_status_cache: dict = {"summary": "", "updated_at": 0.0}

# P3 — System metrics cache (CPU, RAM, VRAM) — updated every 10s
_sys_metrics: dict = {}
# P4 — User typing state (updated via WS, written to interrupt_inbox.json)
_user_typing: bool = False
_user_typing_since: float = 0.0

# ── Nova rate-limit failsafe ────────────────────────────────────────────────
# TEMPORARY — see orchestrator.py for the full explanation.
# Short version: prevents runaway Nova loops from burning Claude/Gemini API
# credits. Remove _NOVA_RATE_LIMIT check in /api/inject_message once Nova's
# autonomy loop is proven stable. — Cole & Claude, 2026-03-28
_NOVA_RATE_WINDOW = 60    # seconds
_NOVA_RATE_LIMIT  = 4     # max Nova-initiated messages allowed per window
_nova_msg_times: list[float] = []   # rolling timestamps of Nova inject calls
nova_throttled:  bool = False       # True = Nova is currently muted by failsafe

# ── Autonomous mode + inference params ────────────────────────────────────────
autonomous_mode:    bool  = False   # OFF by default — Cole enables Autonomous Mode in the UI when ready to let Nova run
_nova_temperature:  float = 0.7    # adjustable via set_params WS message
_nova_top_p:        float = 0.9

# ── Mute state per agent ──────────────────────────────────────────────────────
_mute_states: dict = {"Nova": False, "Claude": True, "Gemini": True}

# ── Active model per agent (runtime-switchable) ───────────────────────────────
_active_models: dict = {"Claude": claude_client.MODEL, "Gemini": gemini_client.MODEL}

# ── Phase 4A.5 — Inbox routing ────────────────────────────────────────────────
# Regex: matches messages that start with [TaskId] where TaskId is a word starting
# with a letter followed by alphanumeric chars / underscores.
# These are module response messages that should be routed to Tasking/Master_Inbox/.
# Examples: "[Research_0328] Here is my analysis..."
#           "[TradeCheck_0328] @eyes result: ..."
import re as _re
_TASK_ID_RE = _re.compile(r'^\[([A-Za-z][A-Za-z0-9_]{2,})\]', _re.MULTILINE)

# Workspace root for inbox writes (3 levels up: nova_chat/ → tools/ → workspace/)
_INBOX_WORKSPACE = Path(__file__).resolve().parent.parent.parent


def _maybe_route_inbox(author: str, content: str) -> None:
    """
    Phase 4A.5 — Inbox routing.

    If `content` starts with a [TaskId] pattern, write it to
    Tasking/Master_Inbox/ so the heartbeat cycle can route it to the
    correct Thought folder on the next tick.

    File name: {timestamp}_{author}_{task_id}.md
    Called synchronously from message-saving code paths (non-blocking I/O only).
    """
    m = _TASK_ID_RE.match(content.strip())
    if not m:
        return                     # Not a task response — ignore

    task_id = m.group(1)
    inbox   = _INBOX_WORKSPACE / "Tasking" / "Master_Inbox"

    try:
        inbox.mkdir(parents=True, exist_ok=True)
        from datetime import datetime as _dt
        ts    = _dt.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_author = _re.sub(r'[^\w]', '', author)[:20] or "unknown"
        fname = f"{ts}_{safe_author}_{task_id}.md"
        text  = (
            f"# Inbox Item: [{task_id}]\n\n"
            f"- **Author:** {author}\n"
            f"- **Timestamp:** {_dt.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"- **Task ID:** {task_id}\n\n"
            f"## Message\n\n{content}\n"
        )
        (inbox / fname).write_text(text, encoding="utf-8")
    except Exception as _e:
        print(f"[inbox] Failed to write Master_Inbox item: {_e}")


class HeartbeatContext:
    """
    Ephemeral transcript for autonomous heartbeat ticks.

    Contains NO chat history — only the single heartbeat tick message.
    This is the architectural fix for the re-processing bug (Task 5):
    when Nova's autonomous context is built from HeartbeatContext instead
    of the full session transcript, she never sees Cole's old messages
    and cannot re-answer them on every tick.

    Workspace context (identity files, memory) is still injected via the
    workspace_context kwarg, so Nova has everything she needs to work.
    """
    def __init__(self, tick_content: str):
        self._tick = tick_content

    def to_messages(self, ai_name: str, system_prefix: str = "",
                    workspace_context: str = "") -> list[dict]:
        sys_content = system_prefix.strip()
        if workspace_context:
            sys_content += (
                f"\n\n--- WORKSPACE CONTEXT ---\n{workspace_context}\n--- END CONTEXT ---"
            )
        return [
            {"role": "system", "content": sys_content},
            {"role": "user",   "content": self._tick},
        ]


def _should_agent_respond(agent: str, content: str) -> bool:
    """
    Returns True if the agent should respond to this message.
    - Unmuted agents respond to everything.
    - Muted agents only respond when @AgentName appears in the message.
    """
    if not _mute_states.get(agent, True):
        return True   # unmuted - respond to all
    # Muted - check for direct mention
    import re as _re
    return bool(_re.search(rf'@{_re.escape(agent)}', content, _re.IGNORECASE))


# ── HTTP endpoints ─────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Trigger workspace index build and background monitors after server is ready."""
    # Autonomy on/off lives in Nova's body (nova_cortex.executive), persisted across
    # restarts. Load it so the UI + per-turn flag reflect her real state on boot.
    global autonomous_mode
    try:
        from nova_cortex import executive
        autonomous_mode = executive.autonomy_enabled()
    except Exception as _e:
        print(f"[autonomy] could not load autonomy state: {_e}")

    async def _bg_index():
        import asyncio as _aio
        await _aio.sleep(1)  # let server fully start first
        try:
            loop = _aio.get_event_loop()
            await loop.run_in_executor(None, workspace._refresh)
            print("[workspace] background index ready")
        except Exception as e:
            print(f"[workspace] background index error: {e}")
        # Refresh Nova's Body Manifest on boot so her self-model
        # (SELF/core/03_body_manifest.md) is current regardless of the (manual)
        # watcher. Runs off the event loop; failure is non-fatal.
        try:
            def _regen_manifest():
                import build_manifest as _bm
                _bm.main()
            await _aio.get_event_loop().run_in_executor(None, _regen_manifest)
            print("[manifest] startup regen complete")
        except Exception as e:
            print(f"[manifest] startup regen skipped: {e}")

    async def _bg_eyes_stream():
        """
        Capture Nova's desktop at ~5fps and broadcast JPEG frames to all
        WebSocket clients as {"type": "eyes_frame", "data": <base64>, "mouse": [xf, yf]}.
        Only runs while _eyes_running is True; sleeps otherwise.
        """
        import base64, io
        try:
            import pyautogui
            from PIL import Image
            _EYES_AVAILABLE = True
        except ImportError:
            _EYES_AVAILABLE = False

        while True:
            if not _eyes_running:
                await asyncio.sleep(0.5)
                continue

            if not _EYES_AVAILABLE:
                await broadcast({"type": "eyes_frame", "error": "pyautogui not installed"})
                await asyncio.sleep(5)
                continue

            try:
                # Capture and downscale (1280 wide max -- keeps bandwidth sane)
                screenshot = pyautogui.screenshot()
                sw, sh = screenshot.size
                scale = min(1280 / sw, 720 / sh, 1.0)
                if scale < 1.0:
                    nw = int(sw * scale)
                    nh = int(sh * scale)
                    screenshot = screenshot.resize((nw, nh), Image.LANCZOS)
                else:
                    nw, nh = sw, sh

                buf = io.BytesIO()
                screenshot.save(buf, format="JPEG", quality=55, optimize=True)
                data_b64 = base64.b64encode(buf.getvalue()).decode()

                # Mouse position as fractions of ORIGINAL screen size
                mx, my = pyautogui.position()
                mouse_frac = [round(mx / sw, 4), round(my / sh, 4)]

                await broadcast({
                    "type":      "eyes_frame",
                    "data":      data_b64,
                    "mouse":     mouse_frac,
                    "timestamp": __import__("time").time(),
                })
            except Exception as _e:
                pass   # never crash the loop

            await asyncio.sleep(0.2)   # 5fps

    async def _bg_nova_status_poll():
        """
        1.3 -- Poll nova_status.json every 30s and cache for silent AI injection.
        Runs forever in background. Updates nova_status_cache global.
        """
        import asyncio as _aio
        await _aio.sleep(2)  # slight offset from index build
        while True:
            try:
                from nova_cortex.nova_status import read_summary
                summary = read_summary()
                nova_status_cache["summary"] = summary
                nova_status_cache["updated_at"] = __import__('time').time()
            except Exception as e:
                nova_status_cache["summary"] = f"[nova_status unavailable: {e}]"
            await _aio.sleep(30)

    async def _bg_transcript_flush():
        """
        Flush the active session transcript to disk every 60 seconds.
        Guards against individual _persist() failures leaving messages only
        in memory.  flush_all() uses atomic temp-file swap so it's safe to
        call while the session is active.
        """
        import asyncio as _aio
        await _aio.sleep(60)
        while True:
            try:
                if session_mgr.active:
                    session_mgr.active.flush_all()
            except Exception as _e:
                print(f"[server] periodic flush error: {_e}")
            await _aio.sleep(60)

    async def _bg_llama_autostart():
        """Auto-launch start_llama.cmd on startup if llama-server isn't already running."""
        import asyncio as _aio, urllib.request as _ur, os as _os
        await _aio.sleep(3)  # let server fully initialize first
        try:
            with _ur.urlopen("http://127.0.0.1:8080/health", timeout=1) as _r:
                if _r.status == 200:
                    print("[llama] already running on port 8080 — skipping auto-start")
                    return
        except Exception:
            pass  # not running — fall through to launch
        _ws = _os.environ.get("NOVA_WORKSPACE") or str(Path(__file__).resolve().parent.parent.parent)
        _cmd = Path(_ws) / "start_llama.cmd"
        if _cmd.exists():
            try:
                _os.startfile(str(_cmd))
                print(f"[llama] auto-started: {_cmd}")
            except Exception as _e:
                print(f"[llama] auto-start failed: {_e}")
        else:
            print(f"[llama] start_llama.cmd not found at {_cmd} — skipping auto-start")

    async def _bg_sys_metrics():
        """P3 — Poll CPU, RAM, VRAM every 10s and include in nova_status broadcasts."""
        import asyncio as _aio
        import time as _t
        await _aio.sleep(5)
        while True:
            try:
                import psutil as _ps
                _sys_metrics['cpu_pct']  = round(_ps.cpu_percent(interval=None), 1)
                vm = _ps.virtual_memory()
                _sys_metrics['ram_gb']   = round(vm.used / (1024**3), 1)
                _sys_metrics['ram_total']= round(vm.total / (1024**3), 1)
            except Exception:
                pass
            try:
                import subprocess as _sp
                r = _sp.run(
                    ['nvidia-smi','--query-gpu=memory.used,memory.total','--format=csv,noheader,nounits'],
                    capture_output=True, text=True, timeout=3
                )
                if r.returncode == 0:
                    parts = r.stdout.strip().split(',')
                    if len(parts) == 2:
                        used_mb  = int(parts[0].strip())
                        total_mb = int(parts[1].strip())
                        _sys_metrics['vram']     = f"{used_mb//1024}/{total_mb//1024} GB"
                        _sys_metrics['vram_pct'] = round(used_mb/total_mb*100, 1)
            except Exception:
                pass
            await _aio.sleep(10)

    asyncio.ensure_future(_bg_index())
    asyncio.ensure_future(_bg_eyes_stream())
    asyncio.ensure_future(_bg_nova_status_poll())
    asyncio.ensure_future(_bg_transcript_flush())
    asyncio.ensure_future(_bg_llama_autostart())
    asyncio.ensure_future(_bg_sys_metrics())
    # Persistent sleep/wake autonomy daemon (replaces per-message heartbeat loop)
    asyncio.ensure_future(autonomy_daemon())
    # Shut the stack down when the app window closes (last WS client gone)
    asyncio.ensure_future(_window_close_watchdog())


@app.get("/")
async def index():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


class NovaMessage(BaseModel):
    content: str
    directed_at: list[str] = []  # empty = all respond


@app.post("/nova-message")
async def nova_message(msg: NovaMessage):
    """
    Nova's autonomy loop calls this endpoint when she needs help.
    Usage from nova_motor/motor_cortex.py:
        import requests
        requests.post("http://127.0.0.1:8765/nova-message", json={
            "content": "Stuck on 'Trade Button' after 3 attempts. Screen shows...",
            "directed_at": ["Claude"]  # or [] for all
        })
    Returns the first complete AI response as JSON.
    """
    content = msg.content.strip()
    if not content:
        return JSONResponse({"error": "empty message"}, status_code=400)

    directed_at = msg.directed_at or parse_directed(content)
    transcript_msg = session_mgr.active.add("Nova", content, directed_at or None)

    # Broadcast to any open browser sessions
    await broadcast({
        "type": "user_message",
        "author": "Nova",
        "content": content,
        "id": transcript_msg["id"],
        "timestamp": transcript_msg["timestamp"],
        "directed_at": directed_at,
        "source": "api",
    })

    # Collect responses
    responses = {}
    status = await get_status()

    async def collect_response(ai_name, client_mod):
        tokens = []
        msg_id = str(uuid.uuid4())[:8]

        await broadcast({"type": "message_start", "author": ai_name, "id": msg_id})

        async def on_token(t):
            tokens.append(t)
            await broadcast({"type": "token", "author": ai_name, "token": t, "id": msg_id})

        async def on_done(full):
            session_mgr.active.add(ai_name, full)
            responses[ai_name] = full
            await broadcast({"type": "message_end", "author": ai_name, "id": msg_id, "content": full})

        async def on_error(err):
            responses[ai_name] = f"[error: {err}]"
            await broadcast({"type": "error", "author": ai_name, "message": err, "id": msg_id})

        if ai_name == "Gemini":
            await _run_gemini_response(on_token, on_done, on_error)
        else:
            await client_mod.stream_response(session_mgr.active, on_token, on_done, on_error)

    tasks = []
    if should_respond("Claude", directed_at) and status.get("Claude"):
        tasks.append(collect_response("Claude", claude_client))
    if should_respond("Gemini", directed_at) and status.get("Gemini"):
        tasks.append(collect_response("Gemini", gemini_client))

    if tasks:
        await asyncio.gather(*tasks)

    return JSONResponse({
        "message_id": transcript_msg["id"],
        "responses": responses,
        "responders": list(responses.keys()),
    })


@app.get("/export")
async def export_context():
    """
    Export the current session as context files for browser Claude/Gemini.
    Files saved to logs/chat_sessions/exports/.
    Returns the export content directly.
    """
    result = export_session()
    if "error" in result:
        return JSONResponse({"error": result["error"]}, status_code=404)
    return JSONResponse({
        "session_id": result["session_id"],
        "message_count": result["message_count"],
        "claude_path": result["claude_path"],
        "gemini_path": result["gemini_path"],
        "claude_export": result["claude_export"],
        "gemini_export": result["gemini_export"],
    })


@app.get("/status")
async def status_endpoint():
    """Check which AIs are online + workspace context summary."""
    status = await get_status()
    status["workspace_context"] = workspace.get_file_list_summary()
    return JSONResponse(status)


@app.get("/sessions")
async def list_sessions():
    """List all sessions with metadata."""
    return JSONResponse({
        "sessions": session_mgr.get_all_meta(),
        "active_id": session_mgr.active_id,
    })


@app.post("/sessions/new")
async def api_new_session():
    """Create a new session and make it active."""
    global is_processing, workspace
    for task in active_tasks:
        if not task.done():
            task.cancel()
    active_tasks.clear()
    is_processing = False
    session_id = session_mgr.new_session()
    workspace.reload()
    await broadcast({
        "type": "session_switched",
        "session_id": session_id,
        "sessions": session_mgr.get_all_meta(),
        "history": [],
    })
    return JSONResponse({"session_id": session_id})


@app.post("/sessions/switch/{session_id}")
async def switch_session(session_id: str):
    """Switch to a different session (Cole only)."""
    global is_processing
    for task in active_tasks:
        if not task.done():
            task.cancel()
    active_tasks.clear()
    is_processing = False

    ok = session_mgr.switch_session(session_id)
    if not ok:
        return JSONResponse({"error": "session not found"}, status_code=404)

    # Offload heavy workspace reload to background thread
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, workspace.reload)
    
    history = [
        {"author": m["author"], "content": m["content"],
         "id": m["id"], "timestamp": m["timestamp"]}
        for m in session_mgr.active.get_recent(100)
    ]
    await broadcast({
        "type": "session_switched",
        "session_id": session_id,
        "sessions": session_mgr.get_all_meta(),
        "history": history,
    })

    # Auto-reinject disabled: build_nova_context_block() now always injects
    # memory/ files (STATUS.md, JOURNAL.md, COLE.md) as grounding context on
    # every turn. The old auto-reinject was adding giant System messages to the
    # transcript which Nova saw as repeated system prompts. Use 'Re-orient Nova'
    # button on the dashboard to manually reinject if needed.

    return JSONResponse({"session_id": session_id, "message_count": len(history)})


@app.post("/sessions/rename/{session_id}")
async def rename_session(session_id: str, body: dict = Body(...)):
    """Rename a session."""
    name = body.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "name required"}, status_code=400)
    ok = session_mgr.rename_session(session_id, name)
    if not ok:
        return JSONResponse({"error": "session not found"}, status_code=404)
    await broadcast({"type": "sessions_updated", "sessions": session_mgr.get_all_meta()})
    return JSONResponse({"ok": True})


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session permanently (cannot delete active)."""
    ok = session_mgr.delete_session(session_id)
    if not ok:
        return JSONResponse({"error": "cannot delete active session or not found"}, status_code=400)
    await broadcast({"type": "sessions_updated", "sessions": session_mgr.get_all_meta()})
    return JSONResponse({"ok": True})


@app.post("/sessions/{session_id}/archive")
async def archive_session(session_id: str):
    """Move a session to logs/chat_sessions/archives/ (cannot archive active)."""
    ok = session_mgr.archive_session(session_id)
    if not ok:
        return JSONResponse({"error": "cannot archive active session or not found"}, status_code=400)
    await broadcast({"type": "sessions_updated", "sessions": session_mgr.get_all_meta()})
    return JSONResponse({"ok": True})



@app.post("/stop")
async def stop_endpoint():
    """Cancel all in-flight AI response tasks immediately."""
    global is_processing
    _stop_requested.set()          # signal token handlers to abort mid-stream
    cancelled = 0
    for task in active_tasks:
        if not task.done():
            task.cancel()
            cancelled += 1
    active_tasks.clear()
    is_processing = False
    await broadcast({"type": "stopped", "cancelled": cancelled})
    return JSONResponse({"cancelled": cancelled})


@app.post("/new-session")
async def new_session_endpoint():
    """Clear the current transcript and start a fresh session."""
    global is_processing
    # Cancel any running tasks first
    for task in active_tasks:
        if not task.done():
            task.cancel()
    active_tasks.clear()
    is_processing = False
    # Start fresh transcript (old one stays on disk as a log)
    session_id = session_mgr.new_session()
    workspace.reload()
    history = []
    await broadcast({
        "type": "session_switched",
        "session_id": session_id,
        "sessions": session_mgr.get_all_meta(),
        "history": history,
    })
    # Auto-inject context so Nova starts oriented in every new session too.
    # Auto-reinject disabled: memory files now always included via build_nova_context_block().
    # Use 'Re-orient Nova' on dashboard for manual reinject.
    return JSONResponse({"status": "new session started", "session_id": session_id})


# ── Internal helpers ───────────────────────────────────────────────────────────

async def broadcast(data: dict):
    """Broadcast a message to all connected WebSocket clients.

    Silently removes any clients that disconnect during send (swallows exceptions).
    This is intentional: network disconnects are ephemeral and don't block message flow
    to other clients; dead connections are cleaned up immediately.
    """
    msg = json.dumps(data)
    dead = []
    for ws in connected_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            # Connection lost; mark for cleanup and continue broadcasting to others
            dead.append(ws)
    for ws in dead:
        connected_clients.remove(ws)


async def get_status() -> dict:
    nova_online = await nova_client.is_available()
    return {
        "Claude": claude_client.is_available(),
        "Gemini": gemini_client.is_available(),
        "Nova": nova_online,
    }


async def _run_gemini_response(on_token, on_done, on_error,
                               workspace_context: str = "",
                               images: list = None):
    """Run Gemini sync SDK in thread pool. Passes images for vision support."""
    loop = asyncio.get_event_loop()
    full_response = ""
    error_msg = None

    def gemini_sync():
        nonlocal full_response, error_msg
        try:
            from nova_chat.clients.gemini import call_gemini_sync
            system_prompt = session_mgr.active.format_for_ai(
                "Gemini", gemini_client.SYSTEM_PREFIX, workspace_context=workspace_context
            )
            prompt = f"{system_prompt}\n\nPlease respond to the conversation above."
            full_response = call_gemini_sync(prompt, images=images)
        except Exception as e:
            error_msg = str(e)

    await loop.run_in_executor(None, gemini_sync)

    if error_msg:
        await on_error(error_msg)
    else:
        # Simulate streaming by word-chunking
        words = full_response.split(" ")
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            await on_token(token)
            await asyncio.sleep(0.008)
        await on_done(full_response)


async def run_ai_response(ai_name: str, client_mod, msg_id: str,
                          latest_message: str = "",
                          images: list = None,
                          hb_ctx=None,
                          cole_pending: bool = True,
                          auto_log_path=None) -> str:
    """
    Stream one AI response, broadcast tokens, and return the full response text.
    The return value lets callers (e.g. _run_response_queue) inspect Nova's
    response for @mentions without re-reading the transcript.

    images: list of {dataUrl, name} dicts from the triggering Cole message.
            Passed through to AI clients that support vision (Claude, Gemini, Nova).

    hb_ctx: if provided (HeartbeatContext), this is an autonomous heartbeat tick.
            The ephemeral context is used instead of session_mgr.active, and Nova's
            response is NOT added to the chat transcript (Task 5+4 fix).
    cole_pending: only meaningful when hb_ctx is set. If True, Nova is responding
            to a new Cole message and her reply DOES go to chat as normal.
            If False, this is a silent work tick — reply goes to autonomy log only.
    auto_log_path: pathlib.Path to the daily autonomy tick log file.
    """
    # Determine the transcript object to use (ephemeral HB ctx vs full session)
    _transcript = hb_ctx if hb_ctx is not None else session_mgr.active
    _is_hb_tick = hb_ctx is not None
    _silent_tick = _is_hb_tick and not cole_pending   # True = don't touch chat
    # Update workspace context based on what was mentioned in the message
    # Offload to background thread to prevent event loop freeze
    if latest_message:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, workspace.update_for_message, latest_message)

    # Nova uses a slim context block — her local model has a 32K token window.
    # Memory files + manifest already arrive via CONTEXT REFRESH in chat history.
    # Claude/Gemini get the full block (200K/1M token windows).
    if ai_name == "Nova":
        # New semantic memory layer: find most relevant past knowledge
        loop = asyncio.get_event_loop()
        memory_ctx = await loop.run_in_executor(None, workspace.build_nova_memory_context, latest_message)

        on_demand_ctx = workspace.build_nova_context_block()
        ws_context = f"{memory_ctx}\n{on_demand_ctx}" if memory_ctx else on_demand_ctx

        # Identity files (AGENTS.md, NOVA.md, TOOLS.md) are now injected inside
        # build_nova_context_block() so they work across all launch paths.
    else:
        # build_context_block performs several read_text calls; offload to be safe
        loop = asyncio.get_event_loop()
        ws_context = await loop.run_in_executor(None, workspace.build_context_block)

        # Prepend Nova's live status for Claude/Gemini only
        if nova_status_cache.get("summary"):
            status_block = (
                "\n--- NOVA LIVE STATUS (auto-injected, do not mention unless relevant) ---\n"
                + nova_status_cache["summary"]
                + "\n--- END NOVA STATUS ---\n"
            )
            ws_context = status_block + ws_context

    import time as _time
    _gen_start = _time.time()
    # Silent autonomous ticks use autonomous_start (invisible to chat bubble renderer)
    _start_event = "autonomous_start" if _silent_tick else "message_start"
    await broadcast({"type": _start_event, "author": ai_name, "id": msg_id})
    # Emit generation_start so Thoughts pane can show "Nova is generating..." indicator
    if ai_name == "Nova":
        await broadcast({"type": "generation_start", "author": ai_name, "id": msg_id,
                         "ts": _gen_start})

    _result: list[str] = []  # capture full text so we can return it
    _think_started = [False]  # tracks whether think_start has been broadcast

    # ── Real-time activity tracking (deduped across progress + on_done) ──────
    import re as _re
    _seen_activity_keys: set = set()
    _ACTIVITY_PATTERNS = [
        ("exec",    r'\[EXEC:\s*([^\]]{1,80})\]'),
        ("write",   r'\[WRITE:\s*([^\]]{1,80})\]'),
        ("read",    r'\[READ:\s*([^\]]{1,80})\]'),
        ("ncl",     r'@(mentor|eyes|browser|coder|memory|voice|thinkorswim)\b'),
    ]

    async def _emit_new_activities(text: str) -> list:
        """Scan text for directive patterns; broadcast any not yet seen. Returns new items."""
        new_items = []
        for dtype, pattern in _ACTIVITY_PATTERNS:
            for m in _re.finditer(pattern, text, _re.IGNORECASE):
                detail = m.group(1).strip() if dtype != "ncl" else f"@{m.group(1)} dispatched"
                key = (dtype, detail)
                if key not in _seen_activity_keys:
                    _seen_activity_keys.add(key)
                    new_items.append((dtype, detail))
                    await broadcast({"type": "nova_activity", "id": msg_id,
                                     "directive": dtype, "detail": detail})
        return new_items

    async def on_token(token):
        if _stop_requested.is_set():
            raise asyncio.CancelledError("STOP requested by user")
        # Silent autonomous ticks stream to autonomous_token (Monitor pane) not chat
        _tok_type = "autonomous_token" if _silent_tick else "token"
        await broadcast({"type": _tok_type, "author": ai_name, "token": token, "id": msg_id})

    async def on_think_token(token):
        """Broadcasts think_start once, then think_token for each token.
        Only wired for Nova — Claude/Gemini handle their own thinking display."""
        if not _think_started[0]:
            _think_started[0] = True
            await broadcast({"type": "think_start", "author": ai_name, "id": msg_id})
        await broadcast({"type": "think_token", "author": ai_name, "token": token, "id": msg_id})

    async def on_progress(chars: int, think_chars: int, elapsed: float, partial_content: str):
        """Called every ~2s from nova.py during llama.cpp generation.
        Broadcasts live stats to the Thoughts pane and scans for early activity."""
        total   = chars + think_chars
        rate    = round(chars / elapsed, 1) if elapsed > 0 else 0
        await broadcast({
            "type":        "nova_progress",
            "id":          msg_id,
            "chars":       chars,
            "think_chars": think_chars,
            "total_chars": total,
            "tokens_est":  total // 4,
            "elapsed":     round(elapsed, 1),
            "rate":        rate,            # content chars/sec
        })
        # Real-time activity scan on partial content (deduped — won't re-emit in on_done)
        await _emit_new_activities(partial_content)

    async def on_done(full):
        _result.append(full)
        elapsed = round(_time.time() - _gen_start, 1)
        # Close the think block if one was opened
        if _think_started[0]:
            await broadcast({"type": "think_end", "author": ai_name, "id": msg_id,
                             "elapsed": elapsed})

        # ── Routing: silent autonomous tick vs. normal chat response ───────────
        if _silent_tick:
            # ── Autonomous work tick — never touches the chat transcript ────────
            # Write to the daily autonomy tick log
            if auto_log_path:
                try:
                    import json as _aj
                    _aentry = {
                        "type":      "response",
                        "timestamp": datetime.now().isoformat(),
                        "content":   full,
                    }
                    with open(auto_log_path, "a", encoding="utf-8") as _alf:
                        _alf.write(_aj.dumps(_aentry, ensure_ascii=False) + "\n")
                except Exception as _le:
                    print(f"[autonomous] tick log write failed: {_le}")

            # Broadcast as autonomous_output for the monitoring pane (not chat)
            await broadcast({"type": "autonomous_output", "author": ai_name,
                             "id": msg_id, "content": full})

            # "FOR COLE:" prefix promotes that section to the chat transcript
            _FC_MARKER = "FOR COLE:"
            _fc_idx = full.upper().find(_FC_MARKER)
            if _fc_idx >= 0:
                _cole_part = full[_fc_idx + len(_FC_MARKER):].strip()
                if _cole_part:
                    _cmsg = session_mgr.active.add(ai_name, _cole_part)
                    session_mgr.update_meta_from_message(_cmsg)
                    if memory_indexer:
                        memory_indexer.add_message(_cole_part, ai_name, session_mgr.active_id)
                    await broadcast({"type": "message_end", "author": ai_name,
                                     "id": msg_id + "_cole", "content": _cole_part})
        else:
            # ── Normal path — add response to chat transcript ────────────────────
            msg = session_mgr.active.add(ai_name, full)
            session_mgr.update_meta_from_message(msg)

            # --- Index for semantic memory ---
            if memory_indexer:
                memory_indexer.add_message(full, ai_name, session_mgr.active_id)

            await broadcast({"type": "message_end", "author": ai_name, "id": msg_id, "content": full})
            if ai_name == "Nova":
                # Refresh her time-sense so "since you last stirred" reflects THIS reply,
                # not a stale autonomy wake (fixes her thinking minutes passed after a
                # 3-second-old response). Also re-baselines the change fingerprint.
                try:
                    from nova_cortex import executive
                    executive.note_activity()
                except Exception:
                    pass

        # Phase 4A.5 — Route module responses with [TASK_ID] to Master_Inbox
        _maybe_route_inbox(ai_name, full)
        # If Nova wrote action directives, forward them via nova_bridge
        if ai_name == "Nova":
            # Final activity scan catches anything missed between last progress ping and done
            new_activity = await _emit_new_activities(full)
            had_activity = len(_seen_activity_keys) > 0
            # Emit final stats + generation_end
            final_chars = len(full)
            await broadcast({
                "type":        "nova_progress",
                "id":          msg_id,
                "chars":       final_chars,
                "think_chars": 0,
                "total_chars": final_chars,
                "tokens_est":  final_chars // 4,
                "elapsed":     elapsed,
                "rate":        round(final_chars / elapsed, 1) if elapsed > 0 else 0,
                "final":       True,
            })
            await broadcast({"type": "generation_end", "author": ai_name, "id": msg_id,
                             "elapsed": elapsed, "had_activity": had_activity})

            bridge_results = await handle_nova_message(full)
            for result in bridge_results:
                await broadcast({
                    "type": "injection_notice",
                    "path": result,
                    "recipients": "nova_bridge",
                })
                # Mirror bridge output to the Terminal panel so exec results are visible
                await broadcast({"type": "terminal_output", "line": result})

    async def on_error(err):
        # Close any open UI state before broadcasting the error:
        # • think_end  — closes the Thoughts pane "thinking..." spinner
        # • generation_end — resets the Monitor / vigilance indicator
        # • message_end — finalizes the dangling message bubble so the UI
        #   doesn't show an empty half-rendered assistant bubble after the error
        if _think_started[0]:
            await broadcast({"type": "think_end", "author": ai_name, "id": msg_id, "elapsed": 0})
        if ai_name == "Nova":
            import time as _t2
            await broadcast({"type": "generation_end", "author": ai_name, "id": msg_id,
                             "elapsed": round(_t2.time() - _gen_start, 1),
                             "had_activity": False})
        await broadcast({"type": "message_end", "author": ai_name, "id": msg_id,
                         "content": f"⚠ {err}"})
        await broadcast({"type": "error", "author": ai_name, "message": err, "id": msg_id})

    async def on_tool_executed_cb(tool_name: str, tool_input: dict,
                                  result: str, is_error: bool, duration_ms: float):
        """Fires tool_executed WS event so the Tools tab shows the call live (Task 2)."""
        await broadcast({
            "type":        "tool_executed",
            "tool":        tool_name,
            "input":       tool_input,
            "result":      result,
            "error":       is_error,
            "duration_ms": round(duration_ms),
        })

    if ai_name == "Gemini":
        await _run_gemini_response(on_token, on_done, on_error, ws_context, images=images)
    elif ai_name == "Nova":
        # Nova supports <think> tag parsing — pass on_think_token and on_progress.
        # Use _transcript (HeartbeatContext for HB ticks, session_mgr.active for normal).
        await client_mod.stream_response(
            _transcript, on_token, on_done, on_error,
            on_think_token=on_think_token,
            on_progress=on_progress,
            on_tool_executed=on_tool_executed_cb,
            workspace_context=ws_context, images=images,
            autonomous=autonomous_mode or _is_hb_tick,
            temperature=_nova_temperature,
            top_p=_nova_top_p,
        )
    else:
        await client_mod.stream_response(
            _transcript, on_token, on_done, on_error,
            workspace_context=ws_context, images=images
        )

    return _result[0] if _result else ""


# ── Client dispatch map ───────────────────────────────────────────────────────
# Used by _run_response_queue to look up the right client module by name.
CLIENT_MAP = {
    "Claude": claude_client,
    "Gemini": gemini_client,
    "Nova":   nova_client,
}


async def _run_response_queue(queue: list, content: str,
                              images: list = None) -> None:
    """
    Execute AI responses SEQUENTIALLY in queue order.

    Each AI sees all previous responses already saved in the transcript
    before it generates its own reply.  Nova is always last so she reads
    the full picture — including any mentor responses — before deciding
    what to say.

    After Nova's response is saved, her text is scanned for @mentions.
    If she tagged Claude or Gemini, those AIs run a one-level follow-up
    round so they can see Nova's message and respond to it.
    This is the mechanism for Nova's smart escalation to mentors.

    images: passed through to run_ai_response for vision support.
            Only the originating Cole message carries images; follow-up rounds
            (Nova→listeners) don't repeat the same images.

    NOTE: Exceptions are NOT caught here — they bubble up to the caller
    (_queued_run) which has a try/finally to reset is_processing.
    """
    for ai_name in queue:
        if ai_name not in CLIENT_MAP:
            continue
        client_mod = CLIENT_MAP[ai_name]
        msg_id = str(uuid.uuid4())[:8]
        response_text = await run_ai_response(ai_name, client_mod, msg_id, content,
                                              images=images)

        # After Nova responds: check if she @mentioned any listeners.
        # If so, run a follow-up round (one level — no further recursion).
        # Follow-up rounds don't carry the original images (they're Nova→listener).
        if ai_name == "Nova" and response_text:
            nova_mentions = parse_directed(response_text)
            follow_ups = [n for n in nova_mentions if n in ("Claude", "Gemini")]
            if follow_ups:
                fu_status = await get_status()
                for fu_name in follow_ups:
                    if fu_status.get(fu_name):
                        await run_ai_response(
                            fu_name, CLIENT_MAP[fu_name],
                            str(uuid.uuid4())[:8], response_text
                        )


# ── WebSocket ──────────────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════════════════
# TOOLS PANEL ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

WORKSPACE_ROOT = (
    Path(os.environ["NOVA_WORKSPACE"])
    if "NOVA_WORKSPACE" in os.environ
    else Path(__file__).parent.parent.parent
)
TEXT_EXTS      = {".py", ".md", ".json", ".jsonl", ".txt", ".ps1", ".cmd",
                  ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env"}
EXCLUDE_DIRS   = {"__pycache__", ".git", "node_modules", ".clawhub",
                  "backups"}


@app.get("/api/files/tree")
async def files_tree():
    """Return workspace directory tree as nested JSON."""
    def _build(path: Path, depth: int = 0) -> dict | None:
        if depth > 5:
            return None
        name = path.name
        if name.startswith(".") or name in EXCLUDE_DIRS:
            return None
        if path.is_dir():
            children = []
            try:
                for child in sorted(path.iterdir(),
                                    key=lambda p: (p.is_file(), p.name.lower())):
                    node = _build(child, depth + 1)
                    if node:
                        children.append(node)
            except PermissionError:
                pass
            return {"name": name, "type": "dir", "children": children,
                    "path": str(path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")}
        else:
            return {"name": name, "type": "file",
                    "ext": path.suffix.lower(),
                    "path": str(path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")}

    tree = _build(WORKSPACE_ROOT)
    return JSONResponse(tree or {})


@app.get("/api/files/read")
async def files_read(path: str):
    """Read a file's content (text files only)."""
    try:
        target = (WORKSPACE_ROOT / path).resolve()
        # Safety: must stay inside workspace
        target.relative_to(WORKSPACE_ROOT.resolve())
        if target.suffix.lower() not in TEXT_EXTS:
            return JSONResponse({"error": "binary or unknown file type"}, status_code=400)
        content = target.read_text(encoding="utf-8", errors="replace")
        if len(content) > 50_000:
            content = content[:50_000] + "\n\n[... truncated at 50k chars ...]"
        return JSONResponse({"path": path, "content": content})
    except (ValueError, FileNotFoundError) as e:
        return JSONResponse({"error": str(e)}, status_code=404)


@app.post("/api/files/inject")
async def files_inject(body: dict = Body(...)):
    """
    Pin a file into the workspace context for the session.
    Does NOT spam the chat with file contents -- broadcasts a quiet notice instead.
    """
    path      = body.get("path", "")
    label     = body.get("label", path)
    directed  = body.get("directed_at", [])  # optional: ["Claude"] etc.
    if not path:
        return JSONResponse({"error": "path required"}, status_code=400)
    try:
        ok, _ = workspace.pin_file(path)
        if not ok:
            return JSONResponse({"error": f"Could not read: {path}"}, status_code=404)
        # Who will receive it?
        status = await get_status()
        active_ais = [ai for ai in ["Claude", "Gemini", "Nova"] if status.get(ai)]
        recipients = directed if directed else active_ais
        recipients_str = ", ".join(recipients) if recipients else "all AIs"
        # Quiet notice -- not logged to session transcript
        await broadcast({
            "type": "injection_notice",
            "path": label,
            "recipients": recipients_str,
        })
        return JSONResponse({"ok": True, "recipients": recipients_str})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/terminal/run")
async def terminal_run(body: dict):
    """Run a PowerShell/cmd command from workspace root. 30s timeout."""
    import subprocess as sp
    cmd = body.get("cmd", "").strip()
    if not cmd:
        return JSONResponse({"error": "no command"}, status_code=400)

    try:
        if sys.platform == "win32":
            proc = sp.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True, text=True, timeout=30,
                cwd=str(WORKSPACE_ROOT), encoding="utf-8", errors="replace"
            )
        else:
            proc = sp.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=30, cwd=str(WORKSPACE_ROOT),
                encoding="utf-8", errors="replace"
            )
        stdout = proc.stdout[-8000:] if proc.stdout else ""
        stderr = proc.stderr[-2000:] if proc.stderr else ""
        return JSONResponse({
            "stdout": stdout,
            "stderr": stderr,
            "returncode": proc.returncode,
        })
    except sp.TimeoutExpired:
        return JSONResponse({"error": "command timed out (30s)", "stdout": "", "stderr": ""}, status_code=408)
    except Exception as e:
        return JSONResponse({"error": str(e), "stdout": "", "stderr": ""}, status_code=500)


@app.get("/api/nova/status")
async def nova_status():
    """Read live Nova status files including nova_status.json."""
    def _read(rel: str) -> str:
        p = WORKSPACE_ROOT / rel
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""

    import time as _time
    heartbeat = _read("HEARTBEAT.md")
    status    = _read("memory/STATUS.md")

    # 1.3 -- Include live nova_status.json for the persistent status bar
    live_status = {}
    try:
        ns_path = WORKSPACE_ROOT / "nova_status.json"
        if ns_path.exists():
            live_status = json.loads(ns_path.read_text(encoding="utf-8"))
    except Exception:
        pass

    # P3 — Merge live system metrics into nova_live so pollMonitor picks them up
    live_status.update({k: v for k, v in _sys_metrics.items()})

    return JSONResponse({
        "heartbeat":   heartbeat[:3000],
        "status":      status[:4000],
        "timestamp":   _time.time(),
        "nova_live":   live_status,          # pulse, active_task, errors, last_run + sys metrics
        "status_cache": nova_status_cache.get("summary", ""),
    })




@app.get("/api/logs/stream")
async def logs_stream(
    file: str = "latest",
    request: Request = None,
):
    """
    Server-Sent Events endpoint — streams a log file live.
    ?file=latest  -> auto-picks today's newest session log
    ?file=path    -> specific relative path under workspace logs/
    """
    from fastapi.responses import StreamingResponse
    from fastapi import Request
    import time as _time

    LOG_ROOT = WORKSPACE_ROOT / "logs"

    def _resolve_log() -> Path | None:
        if file == "latest":
            # Find newest .jsonl in logs/sessions/ for today
            today = __import__('datetime').date.today().strftime("%Y-%m-%d")
            candidates = []
            for p in LOG_ROOT.rglob("*.jsonl"):
                if any(skip in p.parts for skip in ["backups", "chat_sessions"]):
                    continue
                if today in str(p) or p.stat().st_mtime > _time.time() - 86400:
                    candidates.append(p)
            if not candidates:
                return None
            return max(candidates, key=lambda p: p.stat().st_mtime)
        else:
            # Support absolute paths and workspace-relative paths
            abs_p = Path(file)
            if abs_p.is_absolute() and abs_p.exists():
                return abs_p
            p = (WORKSPACE_ROOT / file).resolve()
            try:
                p.relative_to(WORKSPACE_ROOT)
                return p if p.exists() else None
            except ValueError:
                return None

    async def event_generator():
        log_path = _resolve_log()
        if not log_path:
            yield "data: [no log file found]\n\n"
            return

        yield f"data: [streaming: {log_path.relative_to(WORKSPACE_ROOT)}]\n\n"

        # Read existing content first
        try:
            content = log_path.read_text(encoding="utf-8", errors="replace")
            for line in content.splitlines():
                if line.strip():
                    yield f"data: {line}\n\n"
                    await asyncio.sleep(0)
        except Exception as e:
            yield f"data: [read error: {e}]\n\n"
            return

        # Tail the file for new lines
        last_size = log_path.stat().st_size
        while True:
            await asyncio.sleep(0.5)
            try:
                current_size = log_path.stat().st_size
                if current_size > last_size:
                    with open(log_path, encoding="utf-8", errors="replace") as f:
                        f.seek(last_size)
                        new_content = f.read()
                    for line in new_content.splitlines():
                        if line.strip():
                            yield f"data: {line}\n\n"
                    last_size = current_size
                # Heartbeat every 5s to keep connection alive
                yield "data: \n\n"
            except Exception:
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/logs/list")
async def logs_list():
    """List available log files (sessions + chat sessions)."""
    import time as _time
    LOG_ROOT = WORKSPACE_ROOT / "logs"
    files = []
    for p in sorted(LOG_ROOT.rglob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True):
        if "backups" in p.parts:
            continue
        rel = str(p.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
        files.append({
            "path":     rel,
            "name":     p.name,
            "size":     p.stat().st_size,
            "modified": _time.strftime("%H:%M:%S", _time.localtime(p.stat().st_mtime)),
        })
    return JSONResponse({"files": files[:30]})  # most recent 30






@app.get("/logs")
async def logs_tail(n: int = 200, filter: str = ""):
    """
    Return the last N lines from the server's in-memory log ring buffer.

    This gives real-time troubleshooting access without any git-sync delay.
    Captures all print() output from server.py and every imported module.

    Query params:
      ?n=200          — number of lines (default 200, max 1000)
      ?filter=claude  — optional substring filter (case-insensitive)

    Returns plain text so it can be read easily in a browser or via WebFetch.
    """
    n = min(max(1, n), LOG_RING_SIZE)
    with _log_lock:
        lines = list(_log_ring)

    if filter:
        fl = filter.lower()
        lines = [l for l in lines if fl in l.lower()]

    tail = lines[-n:]
    text = "\n".join(tail)
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        f"=== Nova Chat Server Log (last {len(tail)} lines) ===\n"
        f"Timestamp: {datetime.now().isoformat()}\n"
        f"Filter: {filter or '(none)'}\n"
        f"{'='*50}\n"
        f"{text}\n",
        media_type="text/plain",
    )


@app.get("/logs/json")
async def logs_tail_json(n: int = 200, filter: str = ""):
    """Same as /logs but returns JSON array for programmatic access."""
    n = min(max(1, n), LOG_RING_SIZE)
    with _log_lock:
        lines = list(_log_ring)

    if filter:
        fl = filter.lower()
        lines = [l for l in lines if fl in l.lower()]

    return JSONResponse({
        "lines":     lines[-n:],
        "total":     len(lines),
        "timestamp": datetime.now().isoformat(),
    })


@app.post("/api/nova/bridge")
async def nova_bridge_endpoint(body: dict = Body(...)):
    """
    Manually forward an instruction via Nova's bridge (nova_bridge.py).
    Body: {"instruction": "write this file...", "action_type": "write|exec|read"}
    """
    from nova_chat.nova_bridge import execute_action
    action_type = body.get("action_type", "exec")
    instruction = body.get("instruction", "")
    path        = body.get("path", "")
    content     = body.get("content", "")
    cmd         = body.get("cmd", instruction)

    action = {"type": action_type, "path": path, "content": content, "cmd": cmd}
    result = await execute_action(action)
    await broadcast({"type": "injection_notice", "path": result, "recipients": "nova_bridge"})
    return JSONResponse({"result": result})



# ── Git branch indicator ─────────────────────────────────────────────────────

@app.get("/api/git/branch")
async def git_branch():
    """Return current git branch name for the workspace status bar."""
    import subprocess as _sp
    try:
        result = _sp.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=3,
            cwd=str(WORKSPACE_ROOT), encoding="utf-8", errors="replace"
        )
        branch = result.stdout.strip()
        if branch and result.returncode == 0:
            # Also get short status (number of modified/staged files)
            status = _sp.run(
                ["git", "status", "--short"],
                capture_output=True, text=True, timeout=3,
                cwd=str(WORKSPACE_ROOT), encoding="utf-8", errors="replace"
            )
            changed = len([l for l in (status.stdout or "").splitlines() if l.strip()])
            return JSONResponse({"branch": branch, "changed": changed})
    except Exception:
        pass
    return JSONResponse({"branch": "", "changed": 0})


# ── llama.cpp server (local inference) ──────────────────────────────────────

@app.get("/api/llama/status")
async def llama_status():
    """Check if llama-server is running on port 8080."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=1) as resp:
            if resp.status == 200:
                return JSONResponse({"running": True})
    except Exception:
        pass
    return JSONResponse({"running": False})


@app.post("/api/eyes/start")
async def eyes_start():
    """Begin streaming Nova's desktop to connected WebSocket clients at ~5fps."""
    global _eyes_running
    _eyes_running = True
    return {"status": "started"}

@app.post("/api/eyes/stop")
async def eyes_stop():
    """Stop the desktop screenshot stream."""
    global _eyes_running
    _eyes_running = False
    return {"status": "stopped"}


# ── Task Queue API  (/api/queue/*) ─────────────────────────────────────────────
# Reads/writes Tasking/priority.md so Cole can add tasks from the UI and Nova
# picks them up on the next heartbeat tick.
# ──────────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────
# AUTONOMY: sleep/wake daemon + faithful-executor queue persistence
# (added 2026-05-23 — replaces the per-message heartbeat loop in _queued_run)
# ──────────────────────────────────────────────────────────────────────────────
import time as _time

_COLE_INTENT_FILE = Path(WORKSPACE_ROOT) / "memory" / "cole_intent.json"
def _mirror_cole_intent(text: str) -> None:
    """Persist Cole's last non-trivial instruction so it survives the cold
    context of a heartbeat tick. Written by the WS receive path."""
    try:
        _COLE_INTENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {"text": text, "ts": datetime.now().isoformat(), "consumed": False}
        tmp = _COLE_INTENT_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        import os as _os
        _os.replace(tmp, _COLE_INTENT_FILE)
    except Exception as _e:
        print(f"[autonomy] cole_intent write failed: {_e}")


async def emit_event(event: str, text: str, level: str = "info", **extra) -> None:
    """Broadcast a clean, human-readable lifecycle event to the UI (type
    'nova_event') and append it to a structured daily event log. This is the
    feed behind the chat window's 'Live Logs' panel (clean view)."""
    payload = {"type": "nova_event", "event": event, "text": text,
               "level": level, "ts": datetime.now().isoformat()}
    if extra:
        payload.update(extra)
    try:
        await broadcast(payload)
    except Exception:
        pass
    try:
        ev_dir = Path(WORKSPACE_ROOT) / "logs" / "events"
        ev_dir.mkdir(parents=True, exist_ok=True)
        with open(ev_dir / f"events-{datetime.now().strftime('%Y-%m-%d')}.jsonl",
                  "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _has_unread_cole() -> bool:
    """True if Cole's last message comes after Nova's last message."""
    try:
        msgs = session_mgr.active.messages
    except Exception:
        return False
    li_c = next((i for i in range(len(msgs) - 1, -1, -1)
                 if msgs[i]["author"] == "Cole"), None)
    li_n = next((i for i in range(len(msgs) - 1, -1, -1)
                 if msgs[i]["author"] == "Nova"), None)
    return li_c is not None and (li_n is None or li_n < li_c)


# ── Task state: server-owned status + running progress log ──────────────────--
# priority.md stays the human-readable queue; this sidecar holds the machine
# state (status + a timestamped log of what Nova did each tick) so she has
# memory across cold ticks and the SERVER keeps status honest.
async def _window_close_watchdog():
    """Shut the whole stack down shortly after the last UI window disconnects,
    so closing the app actually stops Nova (closing the Chrome --app window drops
    the WebSocket). A page reload reconnects within a couple seconds and cancels
    the pending shutdown, so reloads don't kill the server."""
    await asyncio.sleep(5)            # let the server boot before arming
    had_client = False
    empty_since = None
    while True:
        await asyncio.sleep(3)
        if connected_clients:
            had_client = True
            empty_since = None
            continue
        if not had_client:
            continue                 # no window has opened yet — stay up
        if empty_since is None:
            empty_since = _time.monotonic()
        elif _time.monotonic() - empty_since >= 8:
            print("[server] App window closed (no UI for 8s) — shutting down the stack.")
            import os as _os, signal as _sig
            _os.kill(_os.getpid(), _sig.SIGTERM)
            return


async def autonomy_daemon():
    """Persistent sleep/wake cognition loop. Lives for the whole server while
    autonomous_mode is ON. Replaces the per-message heartbeat loop.

    States: ASLEEP -> (two-stage wake gate) -> JUDGE -> ENGAGE/OBSERVE -> ASLEEP.
    Stage 1 (cheap, no model): env changed OR interval elapsed OR observe-dwell
    OR Cole pending. Stage 2: a model wake-tick where Nova exercises judgment.
    Cole speaking is the highest-priority wake (Priority 0)."""
    global is_processing
    # Drive Nova's body-resident executive faculty. The judgment — whether to wake,
    # and what to do or whether to rest — is entirely hers, in nova_cortex.executive.
    # This host only provides the clock tick, the model call, and her voice. Autonomy
    # on/off is body state; the UI button merely flips executive.set_autonomy().
    from nova_cortex import executive
    await asyncio.sleep(2)

    while True:
        if not executive.autonomy_enabled():
            await asyncio.sleep(2)
            continue

        await asyncio.sleep(3)                       # ASLEEP — cheap poll, no model
        if _stop_requested.is_set() or is_processing:
            continue

        cole_pending = _has_unread_cole()            # host reads the live transcript
        should, reason = executive.should_wake(cole_pending)
        if not should:
            continue
        try:
            if not (await get_status()).get("Nova"):
                await asyncio.sleep(5)
                continue
        except Exception:
            await asyncio.sleep(5)
            continue

        await emit_event("wake", f"Nova woke — {reason}")

        # ── Her judgment (held under is_processing for mutual exclusion) ──
        is_processing = True
        await broadcast({"type": "processing_start"})
        try:
            situation = executive.build_situation(cole_pending, reason)
            reply = await run_ai_response(
                "Nova", CLIENT_MAP["Nova"], str(uuid.uuid4())[:8], situation,
                hb_ctx=HeartbeatContext(situation), cole_pending=cole_pending) or ""
            outcome = executive.apply_decision(reply, cole_pending=cole_pending)
            await emit_event("autonomy", outcome["summary"])
        except asyncio.CancelledError:
            pass
        except Exception as _e:
            print(f"[autonomy] tick error: {_e}")
        finally:
            is_processing = False
            await broadcast({"type": "processing_end"})


@app.get("/api/queue")
async def queue_get():
    """Return Nova's task board (nova_cortex.tasking) — the id-keyed source of truth."""
    try:
        from nova_cortex import tasking
        return JSONResponse({"tasks": list(tasking.all_tasks().values())})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/queue/add")
async def queue_add(body: dict = Body(...)):
    """Add a task to Nova's board."""
    title    = (body.get("title") or "").strip()
    priority = int(body.get("priority", 3))
    notes    = (body.get("notes") or "").strip()
    if not title:
        return JSONResponse({"error": "title required"}, status_code=400)
    try:
        from nova_cortex import tasking
        tid = tasking.create(title, notes, priority)
        return JSONResponse({"ok": True, "id": tid, "title": title, "priority": priority})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/queue/complete")
async def queue_complete(body: dict = Body(...)):
    """Mark a board task done (by id)."""
    tid = (body.get("id") or body.get("raw") or "").strip()
    try:
        from nova_cortex import tasking
        return JSONResponse({"ok": tasking.complete(tid, "")})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/queue/cancel")
async def queue_cancel(body: dict = Body(...)):
    """Abandon a board task (by id)."""
    tid = (body.get("id") or body.get("raw") or "").strip()
    try:
        from nova_cortex import tasking
        return JSONResponse({"ok": tasking.abandon(tid, "cancelled via UI")})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/eyes/status")
async def eyes_status():
    return {"running": _eyes_running}

@app.post("/api/llama/start")
async def llama_start():
    """Launch start_llama.cmd in a new console window."""
    import subprocess
    _workspace = (
        os.environ.get("NOVA_WORKSPACE")
        or str(Path(__file__).resolve().parent.parent.parent)
    )
    cmd_path = Path(_workspace) / "start_llama.cmd"
    if not cmd_path.exists():
        return JSONResponse({"ok": False, "error": f"start_llama.cmd not found at {cmd_path}"}, status_code=500)
    try:
        # os.startfile is equivalent to double-clicking the .cmd file —
        # opens a new console window reliably without pywebview/subprocess flag issues
        import os as _os
        _os.startfile(str(cmd_path))
        return JSONResponse({"ok": True, "message": "llama-server starting on port 8080..."})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/llama/stop")
async def llama_stop():
    """Kill the llama-server process listening on port 8080."""
    import subprocess
    try:
        subprocess.run(
            ["powershell", "-Command",
             "Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | "
             "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"],
            capture_output=True, text=True, timeout=10
        )
        return JSONResponse({"ok": True, "message": "llama-server stopped."})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/run-tool")
async def run_tool(body: dict = Body(...)):
    """Run a workspace tool command and return its output."""
    import subprocess
    cmd = body.get("cmd", "").strip()
    if not cmd:
        return JSONResponse({"error": "No command provided"}, status_code=400)
    # Safety: only allow python commands pointing into tools/
    allowed_prefixes = ("python tools/", "python -c ")
    if not any(cmd.startswith(p) for p in allowed_prefixes):
        return JSONResponse({"error": "Only python tools/ commands are permitted"}, status_code=403)
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=30, cwd=str(WORKSPACE_ROOT),
            encoding="utf-8", errors="replace"
        )
        output = (result.stdout or "") + (result.stderr or "")
        return JSONResponse({"output": output.strip(), "returncode": result.returncode})
    except subprocess.TimeoutExpired:
        return JSONResponse({"error": "Command timed out (30s)"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/inject_message")
async def inject_message(body: dict):
    """
    Inject a message into the active Nova Chat session from an external source.
    Used by Nova's NCL dispatch (injector.py) and her motor tool_executor so she
    can post to the group chat from her own tools.

    Body: { "author": "Nova", "content": "message text" }

    Rate-limited for Nova: see _NOVA_RATE_LIMIT / _NOVA_RATE_WINDOW globals.
    Returns 429 if Nova exceeds the rate limit (failsafe tripped).
    """
    global nova_throttled, _nova_msg_times, is_processing

    author  = body.get("author", "Nova").strip() or "Nova"
    content = body.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content required")

    # ── Nova rate-limit failsafe ──────────────────────────────────────────────
    if author == "Nova":
        now = time.time()
        # Evict timestamps outside the rolling window
        _nova_msg_times = [t for t in _nova_msg_times if now - t < _NOVA_RATE_WINDOW]

        if len(_nova_msg_times) >= _NOVA_RATE_LIMIT:
            # Failsafe tripped: mute Nova, cancel in-flight tasks, warn UI
            nova_throttled = True
            for task in active_tasks:
                if not task.done():
                    task.cancel()
            active_tasks.clear()
            is_processing = False
            await broadcast({
                "type": "nova_throttled",
                "limit": _NOVA_RATE_LIMIT,
                "window": _NOVA_RATE_WINDOW,
                "message": (
                    f"⚠ Nova rate-limit tripped: {_NOVA_RATE_LIMIT}+ messages in "
                    f"{_NOVA_RATE_WINDOW}s. Nova auto-stopped to protect API budget. "
                    f"Send any message to Nova Chat to reset."
                ),
            })
            raise HTTPException(
                status_code=429,
                detail=f"Nova throttled — exceeded {_NOVA_RATE_LIMIT} messages/{_NOVA_RATE_WINDOW}s",
            )

        _nova_msg_times.append(now)
        nova_throttled = False   # within limits — clear any previous throttle flag

    # ── Deliver message ───────────────────────────────────────────────────────
    msg = session_mgr.active.add(author, content)
    session_mgr.update_meta_from_message(msg)

    # --- Index for semantic memory ---
    if memory_indexer:
        memory_indexer.add_message(content, author, session_mgr.active_id)

    await broadcast({
        "type":      "user_message",
        "author":    author,
        "content":   content,
        "id":        msg["id"],
        "timestamp": msg["timestamp"],
    })

    # Phase 4A.5 — Route module responses with [TASK_ID] header to Master_Inbox.
    # Injected messages can also be module responses (e.g. @eyes posts its result
    # back to Nova Chat via inject_message with a [task_id] prefix).
    _maybe_route_inbox(author, content)

    # Execute any nova_bridge directives Nova wrote (e.g. [EXEC:], [WRITE:], [READ:])
    if author == "Nova":
        bridge_results = await handle_nova_message(content)
        for br in bridge_results:
            await broadcast({
                "type":   "bridge_result",
                "result": br,
                "msg_id": msg["id"],
            })

    # ── NCL dispatch: detect and execute Nova Command Language module calls ────
    # If Nova's message contains NCL module calls (@eyes, @coder, etc. with
    # structural tokens like [[]], (()), <<>>), dispatch them asynchronously.
    # This runs as a fire-and-forget task — the endpoint returns immediately
    # and module results are posted back to Nova Chat when ready.
    if author == "Nova" and is_ncl_message(content):
        try:
            from nova_chat.nova_lang import parse_ncl
            _ncl = parse_ncl(content)
            if _ncl:
                from injector import NCLInjector
                _injector = NCLInjector()

                async def _ncl_dispatch():
                    try:
                        results = await _injector.execute(_ncl)
                        print(f"[NCL] dispatch complete: {len(results)} chain(s)")
                    except Exception as _e:
                        print(f"[NCL] dispatch task error: {_e}")

                _ncl_task = asyncio.create_task(_ncl_dispatch())
                active_tasks.append(_ncl_task)

                def _ncl_cleanup(fut):
                    try:
                        if _ncl_task in active_tasks:
                            active_tasks.remove(_ncl_task)
                    except Exception:
                        pass

                _ncl_task.add_done_callback(_ncl_cleanup)
                print(f"[NCL] dispatched task for: {content[:80]}")
        except Exception as _ncl_err:
            print(f"[NCL] Failed to dispatch NCL call: {_ncl_err}")

    # ── Trigger Claude / Gemini if @mentioned in the injected message ─────────
    # Nova writes "@Claude ..." in her message → Claude gets triggered.
    # Uses the same sequential queue as Cole's messages.
    # Nova is excluded from auto-triggering here (no recursion on inject).
    if not nova_throttled:
        _directed = parse_directed(content)
        # Only trigger listener AIs (not Nova again — she just spoke)
        _listener_directed = [n for n in _directed if n in ("Claude", "Gemini")]
        if _listener_directed:
            _ai_status = await get_status()
            # Build a listeners-only queue (no Nova at end — she already sent)
            _listener_queue = [n for n in ("Claude", "Gemini")
                               if n in _listener_directed and _ai_status.get(n)]
            if _listener_queue:
                is_processing = True

                async def _inject_listener_run():
                    """Run listener queue with proper exception handling."""
                    global is_processing
                    try:
                        await _run_response_queue(_listener_queue, content)
                    except asyncio.CancelledError:
                        pass  # absorb so finally can broadcast processing_end cleanly
                    except Exception as e:
                        print(f"[chat] Error in injected listener queue: {e}")
                    finally:
                        is_processing = False
                        await broadcast({"type": "processing_end"})

                _t = asyncio.create_task(_inject_listener_run())
                active_tasks.append(_t)

                # Clean up task reference when done (robust callback)
                def _task_cleanup(fut):
                    """Remove task from active_tasks even if callback raises."""
                    try:
                        if _t in active_tasks:
                            active_tasks.remove(_t)
                    except Exception:
                        # Prevent callback exceptions from bubbling up
                        pass

                _t.add_done_callback(_task_cleanup)

    return {"ok": True, "id": msg["id"], "author": author, "chars": len(content)}


@app.post("/api/reinject_context")
async def reinject_context():
    """
    Mid-session context refresh (the 'Refresh Context' button).

      1. PURGE prior CONTEXT REFRESH system messages from the active session so
         stale/old context can't linger or pile up. The conversation (Cole + Nova
         messages) is kept untouched.
      2. RE-INJECT a concise re-orientation note plus the architecture files that
         are NOT already injected fresh every turn by build_nova_context_block().
         That per-turn block always injects AGENTS/NOVA/TOOLS + memory
         (STATUS/JOURNAL/COLE), so re-dumping them here would double ~30K chars and
         blow Nova's 32K window — we deliberately skip them.
      3. KEEP chat history so the session continues seamlessly — Nova just becomes
         aware of the current architecture and disregards retired approaches.

    Returns: { ok, purged, files_injected, chars }
    """
    # Files build_nova_context_block() already injects every turn — skip to avoid bloat.
    _ALREADY_PER_TURN = {"agents.md", "nova.md", "tools.md",
                         "status.md", "journal.md", "cole.md"}

    # Re-inject the deep reference docs from SELF/reference (NCL grammar, upgrade
    # protocol, heartbeat). SELF/core (identity, how-I-work, body manifest, tools &
    # voice) is already injected fresh every turn, so here we only surface the
    # on-demand reference layer that isn't normally in context.
    _WORKSPACE = Path(__file__).resolve().parent.parent.parent
    inject_paths = sorted((_WORKSPACE / "SELF" / "reference").glob("*.md"))

    # 1) Purge stale CONTEXT REFRESH blocks from history (keep the conversation).
    purged = 0
    try:
        kept = []
        for m in session_mgr.active.messages:
            c = (m.get("content") or "").lstrip()
            if m.get("author") == "System" and c.startswith("# CONTEXT REFRESH"):
                purged += 1
                continue
            kept.append(m)
        if purged:
            session_mgr.active.messages[:] = kept
            try:
                session_mgr.active.flush_all()
            except Exception:
                pass
    except Exception as _pe:
        print(f"[reinject] purge failed: {_pe}")

    # 2) Build a concise refresh block (skip per-turn-injected identity/memory).
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    sections = [
        f"# CONTEXT REFRESH — {ts}",
        "_Your self-model — SELF/core/ (identity, how-you-work, body manifest, tools & "
        "voice) — and your memory files (STATUS/COLE/JOURNAL) are reloaded fresh from "
        "disk every turn, current as of now. Re-orient to the CURRENT system they "
        "describe and DISREGARD any earlier messages in this session that assumed older "
        "or retired architecture. The conversation continues unchanged._",
    ]
    injected = 0
    for path in inject_paths:
        if path.name.lower() in _ALREADY_PER_TURN:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                sections.append(f"## [{path.name}]\n{text}")
                injected += 1
        except Exception as _fe:
            print(f"[reinject] skipped {path.name}: {_fe}")

    block = "\n\n---\n\n".join(sections)
    chars = len(block)

    msg = session_mgr.active.add("System", block)
    session_mgr.update_meta_from_message(msg)
    await broadcast({
        "type":      "user_message",
        "author":    "System",
        "content":   block,
        "id":        msg["id"],
        "timestamp": msg["timestamp"],
    })

    print(f"[reinject] refreshed: purged {purged} stale block(s), "
          f"injected {injected} extra file(s), {chars} chars")
    return JSONResponse({"ok": True, "purged": purged, "files_injected": injected, "chars": chars})


@app.post("/shutdown")
async def shutdown_endpoint():
    """Gracefully shut down the server."""
    import threading, os, signal
    def _kill():
        import time as _t; _t.sleep(0.3)
        os.kill(os.getpid(), signal.SIGTERM)
    threading.Thread(target=_kill, daemon=True).start()
    return JSONResponse({"status": "shutting down"})

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global is_processing, autonomous_mode, _mute_states  # declared once at top
    await ws.accept()
    connected_clients.append(ws)

    # Send status, sessions, and history on connect
    status = await get_status()
    await ws.send_text(json.dumps({"type": "status", "participants": status}))

    # Sync autonomous mode state so UI toggle reflects the true server state
    await ws.send_text(json.dumps({
        "type": "autonomous_state",
        "enabled": autonomous_mode,
    }))

    # Sync mute states so participant bar shows correct muted/unmuted for each agent
    for _agent, _muted in _mute_states.items():
        await ws.send_text(json.dumps({"type": "mute_state", "agent": _agent, "muted": _muted}))

    # Send full sessions list for tab rendering
    await ws.send_text(json.dumps({
        "type": "sessions_init",
        "sessions": session_mgr.get_all_meta(),
        "active_id": session_mgr.active_id,
    }))

    for msg in session_mgr.active.get_recent(100):
        hist_payload = {
            "type": "history",
            "author": msg["author"],
            "content": msg["content"],
            "id": msg["id"],
            "timestamp": msg["timestamp"],
        }
        if msg.get("images"):
            hist_payload["images"] = msg["images"]
        await ws.send_text(json.dumps(hist_payload))

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)

            if data.get("type") == "ping":
                status = await get_status()
                await ws.send_text(json.dumps({"type": "status", "participants": status}))
                continue

            if data.get("type") == "switch_session":
                session_id = data.get("session_id", "")
                if session_id:
                    for task in active_tasks:
                        if not task.done():
                            task.cancel()
                    active_tasks.clear()
                    is_processing = False
                    ok = session_mgr.switch_session(session_id)
                    if ok:
                        workspace.reload()
                        history = []
                        for m in session_mgr.active.get_recent(100):
                            h = {"author": m["author"], "content": m["content"],
                                 "id": m["id"], "timestamp": m["timestamp"]}
                            if m.get("images"):
                                h["images"] = m["images"]
                            history.append(h)
                        await broadcast({
                            "type": "session_switched",
                            "session_id": session_id,
                            "sessions": session_mgr.get_all_meta(),
                            "history": history,
                        })
                continue

            if data.get("type") == "stop":
                _stop_requested.set()  # signal all token handlers to abort
                cancelled = 0
                for task in active_tasks:
                    if not task.done():
                        task.cancel()
                        cancelled += 1
                active_tasks.clear()
                is_processing = False
                await broadcast({"type": "stopped", "cancelled": cancelled})
                continue

            if data.get("type") == "new_session":
                for task in active_tasks:
                    if not task.done():
                        task.cancel()
                active_tasks.clear()
                is_processing = False
                session_id = session_mgr.new_session()
                workspace.reload()
                await broadcast({
                    "type": "session_switched",
                    "session_id": session_id,
                    "sessions": session_mgr.get_all_meta(),
                    "history": [],
                })
                continue

            if data.get("type") == "export_request":
                # Browser requested context export
                result = export_session()
                await ws.send_text(json.dumps({
                    "type": "export_ready",
                    "claude_export": result.get("claude_export", ""),
                    "gemini_export": result.get("gemini_export", ""),
                    "claude_path": result.get("claude_path", ""),
                    "gemini_path": result.get("gemini_path", ""),
                    "message_count": result.get("message_count", 0),
                }))
                continue

            if data.get("type") == "set_depth":
                global _depth_max_tokens
                _depth_max_tokens = int(data.get("max_tokens", 0))
                continue

            if data.get("type") == "autonomous_toggle":
                autonomous_mode = bool(data.get("enabled", False))
                # Autonomy is body state — the button only flips the body's switch.
                try:
                    from nova_cortex import executive
                    executive.set_autonomy(autonomous_mode)
                except Exception as _e:
                    print(f"[autonomy] set_autonomy failed: {_e}")
                status_text = "ON" if autonomous_mode else "OFF"
                _amsg = session_mgr.active.add("System",
                    f"[Autonomous Mode: {status_text}]")
                await broadcast({
                    "type": "user_message",
                    "author": "System",
                    "content": f"[Autonomous Mode: {status_text}]",
                    "id": _amsg["id"],
                    "timestamp": _amsg["timestamp"],
                })
                continue

            if data.get("type") == "set_params":
                global _nova_temperature, _nova_top_p
                if "temperature" in data:
                    _nova_temperature = float(data["temperature"])
                if "top_p" in data:
                    _nova_top_p = float(data["top_p"])
                continue

            if data.get("type") == "mute_agent":
                agent  = data.get("agent", "")
                muted  = bool(data.get("muted", True))
                if agent in _mute_states:
                    _mute_states[agent] = muted
                    await broadcast({"type": "mute_state", "agent": agent, "muted": muted})
                continue

            if data.get("type") == "user_typing":
                # P4 — Cole is typing a response; write state to interrupt_inbox.json
                # so checkin.py can warn Nova to pause before her next action tick.
                global _user_typing, _user_typing_since
                import time as _tz
                _now_tz            = _tz.time()
                _user_typing       = bool(data.get("typing", False))
                _user_typing_since = _now_tz if _user_typing else _user_typing_since
                try:
                    inbox_path = WORKSPACE_ROOT / "memory" / "interrupt_inbox.json"
                    inbox_path.parent.mkdir(parents=True, exist_ok=True)
                    existing = {}
                    if inbox_path.exists():
                        try: existing = json.loads(inbox_path.read_text(encoding="utf-8"))
                        except Exception: pass
                    existing["is_typing"]     = _user_typing
                    existing["typing_since"]  = _user_typing_since
                    # last_typed_at persists even after debounce clears is_typing,
                    # giving checkin.py a 30s window to detect recent typing activity.
                    if _user_typing:
                        existing["last_typed_at"] = _now_tz
                    # Atomic write: write to .tmp then rename, so readers never see
                    # a half-written file (write_text truncates before writing).
                    _inbox_tmp = inbox_path.with_suffix(".tmp")
                    _inbox_tmp.write_text(json.dumps(existing, indent=2), encoding="utf-8")
                    import os as _os
                    _os.replace(_inbox_tmp, inbox_path)
                except Exception as _e:
                    print(f"[typing] inbox write failed: {_e}")
                continue

            if data.get("type") == "set_model":
                global _active_models
                agent = data.get("agent", "")
                model = data.get("model", "").strip()
                if agent and model:
                    _active_models[agent] = model
                    if agent == "Claude":
                        claude_client.set_model(model)
                    elif agent == "Gemini":
                        gemini_client.set_model(model)
                    await broadcast({"type": "model_changed", "agent": agent, "model": model})
                    print(f"[model] {agent} → {model}")
                continue

            if data.get("type") == "message":
                content = data.get("content", "").strip()
                images  = data.get("images", [])  # [{dataUrl, name}]
                telemetry = data.get("telemetry", "").strip()
                
                if not content and not images:
                    continue

                full_context_content = content
                if telemetry:
                    full_context_content = f"[System Telemetry (Invisible to user UI)]\n{telemetry}\n[End Telemetry]\n\n{content}"

                # Cole sending a message resets the Nova throttle and rate window
                global nova_throttled, _nova_msg_times
                if nova_throttled:
                    nova_throttled = False
                    _nova_msg_times = []
                    await broadcast({"type": "nova_unthrottled"})

                directed_at = parse_directed(content)

                # Append the telemetry-bundled content to the Backend Transcript so AIs see it
                msg = session_mgr.active.add("Cole", full_context_content, directed_at or None,
                                             images=images)
                session_mgr.update_meta_from_message(msg)

                # --- Index for semantic memory ---
                if memory_indexer:
                    memory_indexer.add_message(full_context_content, "Cole", session_mgr.active_id)
                    for img in images or []:
                        # Index each image by dataUrl (base64) and name
                        memory_indexer.add_image(
                            img.get("dataUrl"),
                            caption=f"Image from Cole: {img.get('name', 'unnamed')}",
                            filename=img.get("name", "screenshot.png"),
                            session_id=session_mgr.active_id
                        )

                # Broadcast the CLEAN content back to the UI so Cole doesn't see the telemetry
                await broadcast({
                    "type": "user_message",
                    "author": "Cole",
                    "content": content,
                    "id": msg["id"],
                    "timestamp": msg["timestamp"],
                    "directed_at": directed_at,
                    "images": images,
                })

                # Mirror Cole's instruction into working memory so the autonomy
                # daemon can pick it up on its next wake (survives cold tick context).
                _mirror_cole_intent(content)
                await emit_event("cole_message", "Cole sent a message")

                # ── Queue while processing; drain after ───────────────────────
                # Instead of dropping Cole's message with "blocked", queue it.
                # The queue is drained at the end of _queued_run (below).
                if is_processing:
                    _cole_message_queue.append({
                        "content":              content,
                        "full_context_content": full_context_content,
                        "directed_at":          directed_at,
                        "images":               images or [],
                        "msg":                  msg,
                    })
                    await ws.send_text(json.dumps({
                        "type":    "queued",
                        "count":   len(_cole_message_queue),
                        "reason":  "Nova is responding — your message is queued and will be delivered next.",
                    }))
                    continue

                status = await get_status()
                if not directed_at:
                    # No @mentions: only online + unmuted agents respond.
                    # _mute_states[name] = False means UNMUTED (will respond).
                    # _mute_states[name] = True  means MUTED   (silent unless @mentioned).
                    # Use canonical response order: Claude → Gemini → Nova.
                    queue = [
                        name for name in ("Claude", "Gemini", "Nova")
                        if status.get(name) and not _mute_states.get(name, True)
                    ]
                else:
                    # Explicit @mentions bypass mute — direct mentions always work.
                    queue = build_response_queue(directed_at, status)

                if queue:
                    _stop_requested.clear()    # reset stop flag for this new generation
                    is_processing = True
                    await broadcast({"type": "processing_start"})

                    # Capture queue, content, and images at definition time
                    _q = list(queue)    # make a copy
                    _c = content
                    _imgs = images or []   # images from this Cole message

                    # Snapshot message count + original task before this run
                    _run_start_idx    = len(session_mgr.active.messages)
                    _original_task    = _c   # Cole's triggering message

                    async def _queued_run():
                        global is_processing
                        try:
                            await _run_response_queue(_q, _c, images=_imgs or None)

                            # ── Autonomous cognition now lives in autonomy_daemon() ──────
                            # _queued_run only produces the direct response to Cole now;
                            # the persistent sleep/wake daemon owns all background ticking.
                            _auto_ticks = 0

                            # ── Post-run log export ───────────────────────────────────────
                            # Write everything that happened in this run to a standalone
                            # file so it's easy to find and read after any test.
                            # Both autonomous and regular runs get exported — small files,
                            # no hunting through the main session transcript.
                            try:
                                import json as _json
                                from pathlib import Path as _Path
                                _runs_dir = _Path(WORKSPACE_ROOT) / "logs" / "autonomy_runs"
                                _runs_dir.mkdir(parents=True, exist_ok=True)
                                _ts = __import__('datetime').datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                                _mode = "auto" if _auto_ticks > 0 else "manual"
                                _run_path = _runs_dir / f"{_ts}_{_mode}_{_auto_ticks}ticks.jsonl"
                                _new_msgs = session_mgr.active.messages[_run_start_idx:]
                                with open(_run_path, "w", encoding="utf-8") as _rf:
                                    for _m in _new_msgs:
                                        _rf.write(_json.dumps(_m, ensure_ascii=False) + "\n")
                                print(f"[autonomous] Run log → {_run_path.name} ({len(_new_msgs)} messages)")
                            except Exception as _log_e:
                                print(f"[autonomous] Run log export failed: {_log_e}")

                        except asyncio.CancelledError:
                            pass
                        except Exception as e:
                            print(f"[chat] Error in response queue: {e}")
                        finally:
                            is_processing = False
                            await broadcast({"type": "processing_end"})

                            # ── Drain Cole's message queue ─────────────────────────────
                            # If Cole sent messages while we were processing, deliver the
                            # most recent one now. Earlier ones are already in the transcript.
                            if not _cole_message_queue:
                                await broadcast({"type": "queue_cleared"})
                            if _cole_message_queue:
                                _queued = _cole_message_queue[-1]
                                _cole_message_queue.clear()
                                print(f"[queue] Delivering {1} queued Cole message")
                                _qdir  = _queued.get("directed_at") or []
                                _qstat = await get_status()
                                if not _qdir:
                                    _qqueue = [
                                        n for n in ("Claude", "Gemini", "Nova")
                                        if _qstat.get(n) and not _mute_states.get(n, True)
                                    ]
                                else:
                                    _qqueue = build_response_queue(_qdir, _qstat)
                                if _qqueue:
                                    _stop_requested.clear()
                                    is_processing = True
                                    await broadcast({"type": "processing_start"})
                                    _qq2   = list(_qqueue)
                                    _qc2   = _queued["content"]
                                    _qimgs = _queued.get("images", [])
                                    _run_start_idx2 = len(session_mgr.active.messages)
                                    async def _drain_run():
                                        global is_processing
                                        try:
                                            await _run_response_queue(_qq2, _qc2,
                                                                       images=_qimgs or None)
                                        except asyncio.CancelledError:
                                            pass
                                        except Exception as _de:
                                            print(f"[queue] Drain error: {_de}")
                                        finally:
                                            is_processing = False
                                            await broadcast({"type": "processing_end"})
                                    asyncio.ensure_future(_drain_run())

                    task = asyncio.ensure_future(_queued_run())
                    active_tasks.append(task)
                    # Do NOT await task here — awaiting blocks the receive loop so
                    # WebSocket "stop" messages can never arrive while generation is
                    # running.  ensure_future already schedules it; the while loop
                    # continues to ws.receive_text() and processes stop/ping/etc.

    except WebSocketDisconnect:
        pass  # client closed the tab or lost connection — normal, not an error
    finally:
        if ws in connected_clients:
            connected_clients.remove(ws)
