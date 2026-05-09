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

_eyes_running: bool = False        # tracks desktop streaming state
# 1.3 -- Nova status cache: polled every 30s, injected silently into AI context
nova_status_cache: dict = {"summary": "", "updated_at": 0.0}

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
autonomous_mode:    bool  = True    # ON by default — Nova is always aware; disable only during patches
_nova_temperature:  float = 0.7    # adjustable via set_params WS message
_nova_top_p:        float = 0.9

# ── Mute state per agent ──────────────────────────────────────────────────────
_mute_states: dict = {"Nova": False, "Claude": False, "Gemini": False}

# ── Active model per agent (runtime-switchable) ───────────────────────────────
_active_models: dict = {"Claude": claude_client.MODEL, "Gemini": gemini_client.MODEL}

# ── Phase 4A.5 — Inbox routing ────────────────────────────────────────────────
# Regex: matches messages that start with [TaskId] where TaskId is a word starting
# with a letter followed by alphanumeric chars / underscores.
# These are module response messages that should be routed to Thoughts/Master_Inbox/.
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
    Thoughts/Master_Inbox/ so the heartbeat cycle can route it to the
    correct Thought folder on the next tick.

    File name: {timestamp}_{author}_{task_id}.md
    Called synchronously from message-saving code paths (non-blocking I/O only).
    """
    m = _TASK_ID_RE.match(content.strip())
    if not m:
        return                     # Not a task response — ignore

    task_id = m.group(1)
    inbox   = _INBOX_WORKSPACE / "Thoughts" / "Master_Inbox"

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
    async def _bg_index():
        import asyncio as _aio
        await _aio.sleep(1)  # let server fully start first
        try:
            loop = _aio.get_event_loop()
            await loop.run_in_executor(None, workspace._refresh)
            print("[workspace] background index ready")
        except Exception as e:
            print(f"[workspace] background index error: {e}")

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

    async def _bg_gateway_error_watch():
        """
        1.4 -- Tail nova_gateway log for ERROR lines.
        Surfaces new errors into nova_chat as a system notice (not a chat message).
        Runs forever in background.
        """
        import asyncio as _aio
        import pathlib as _pl
        import time as _t

        await _aio.sleep(3)
        # nova_gateway writes logs to workspace/logs/gateway/ (our stack)
        _WORKSPACE = _pl.Path(__file__).resolve().parent.parent.parent
        LOG_DIR = _WORKSPACE / "logs" / "gateway"
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        last_error_seen = ""
        last_pos = 0

        while True:
            try:
                today = __import__('datetime').date.today().strftime("%Y-%m-%d")
                log_path = LOG_DIR / f"gateway-{today}.log"
                if log_path.exists():
                    size = log_path.stat().st_size
                    if size > last_pos:
                        with open(log_path, encoding="utf-8", errors="replace") as f:
                            f.seek(last_pos)
                            new_lines = f.read()
                        last_pos = size
                        for line in new_lines.splitlines():
                            if ("ERROR" in line or "error" in line.lower()) and "ImportError" not in line:
                                if line != last_error_seen and len(line.strip()) > 10:
                                    last_error_seen = line
                                    # Update nova_status gateway error field
                                    try:
                                        from nova_cortex.nova_status import update_gateway
                                        update_gateway(running=True, last_error=line.strip()[-200:])
                                    except Exception:
                                        pass
                                    # Broadcast a quiet system notice to the UI
                                    await broadcast({
                                        "type": "gateway_error",
                                        "message": line.strip()[-200:],
                                    })
            except Exception:
                pass
            await _aio.sleep(10)  # check gateway log every 10s

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

    asyncio.ensure_future(_bg_index())
    asyncio.ensure_future(_bg_eyes_stream())
    asyncio.ensure_future(_bg_nova_status_poll())
    asyncio.ensure_future(_bg_gateway_error_watch())
    asyncio.ensure_future(_bg_transcript_flush())
    asyncio.ensure_future(_bg_llama_autostart())


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


def _build_discord_context_block(n: int = 15) -> str:
    """
    Read recent nova_gateway session JSONL files and return a formatted block
    showing recent Discord activity. Injected into all AIs' workspace context
    so Nova Chat participants have cross-session awareness of Discord conversations.

    Reads the 3 most recent gateway_sessions, extracts up to n user/assistant
    message pairs (skipping tool results), and formats them for system prompt
    injection. Silent on any error — cross-session context is best-effort.
    """
    try:
        gateway_dir = WORKSPACE_ROOT / "logs" / "gateway_sessions"
        if not gateway_dir.exists():
            return ""
        all_files = sorted(
            gateway_dir.rglob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:3]
        if not all_files:
            return ""
        collected: list[str] = []
        for path in all_files:
            session_lines: list[str] = []
            trigger = "discord"
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    for raw in fh:
                        raw = raw.strip()
                        if not raw:
                            continue
                        try:
                            entry = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        etype = entry.get("type", "")
                        if etype == "session":
                            trigger = entry.get("trigger", "discord")
                            continue
                        if etype != "message":
                            continue
                        role    = entry.get("role", "")
                        content = (entry.get("content") or "").strip()[:400]
                        ts      = (entry.get("timestamp") or "")[:16]
                        if not content:
                            continue
                        if role == "user":
                            session_lines.append(f"  [{ts}] Discord: {content}")
                        elif role == "assistant":
                            session_lines.append(f"  [{ts}] Nova: {content}")
            except Exception:
                continue
            if session_lines:
                collected.extend(session_lines[-6:])   # last 6 lines per session
        if not collected:
            return ""
        lines_to_show = collected[-n:]
        return (
            "\n--- RECENT DISCORD ACTIVITY (cross-session awareness, do not repeat unless asked) ---\n"
            + "\n".join(lines_to_show)
            + "\n--- END DISCORD ACTIVITY ---\n"
        )
    except Exception:
        return ""


async def run_ai_response(ai_name: str, client_mod, msg_id: str,
                          latest_message: str = "",
                          images: list = None) -> str:
    """
    Stream one AI response, broadcast tokens, and return the full response text.
    The return value lets callers (e.g. _run_response_queue) inspect Nova's
    response for @mentions without re-reading the transcript.

    images: list of {dataUrl, name} dicts from the triggering Cole message.
            Passed through to AI clients that support vision (Claude, Gemini, Nova).
    """
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

        # Cross-session awareness: inject recent Discord activity (Claude/Gemini only)
        discord_ctx = _build_discord_context_block()
        if discord_ctx:
            ws_context = discord_ctx + ws_context

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
    await broadcast({"type": "message_start", "author": ai_name, "id": msg_id})
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
        ("discord", r'\[DISCORD:\s*([^\]]{1,80})\]'),
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
        await broadcast({"type": "token", "author": ai_name, "token": token, "id": msg_id})

    async def on_think_token(token):
        """Broadcasts think_start once, then think_token for each token.
        Only wired for Nova — Claude/Gemini handle their own thinking display."""
        if not _think_started[0]:
            _think_started[0] = True
            await broadcast({"type": "think_start", "author": ai_name, "id": msg_id})
        await broadcast({"type": "think_token", "author": ai_name, "token": token, "id": msg_id})

    async def on_progress(chars: int, think_chars: int, elapsed: float, partial_content: str):
        """Called every ~2s from nova.py during ExLlamaV2 generation.
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
        msg = session_mgr.active.add(ai_name, full)
        session_mgr.update_meta_from_message(msg)

        # --- Index for semantic memory ---
        if memory_indexer:
            memory_indexer.add_message(full, ai_name, session_mgr.active_id)

        await broadcast({"type": "message_end", "author": ai_name, "id": msg_id, "content": full})
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
        await broadcast({"type": "error", "author": ai_name, "message": err, "id": msg_id})

    if ai_name == "Gemini":
        await _run_gemini_response(on_token, on_done, on_error, ws_context, images=images)
    elif ai_name == "Nova":
        # Nova supports <think> tag parsing — pass on_think_token and on_progress
        await client_mod.stream_response(
            session_mgr.active, on_token, on_done, on_error,
            on_think_token=on_think_token,
            on_progress=on_progress,
            workspace_context=ws_context, images=images,
            autonomous=autonomous_mode,
            temperature=_nova_temperature,
            top_p=_nova_top_p,
        )
    else:
        await client_mod.stream_response(
            session_mgr.active, on_token, on_done, on_error,
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

    return JSONResponse({
        "heartbeat":   heartbeat[:3000],
        "status":      status[:4000],
        "timestamp":   _time.time(),
        "nova_live":   live_status,          # pulse, active_task, errors, gateway, last_run
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






@app.get("/api/logs/nova_gateway")
async def nova_gateway_sessions(limit: int = 20):
    """
    List nova_gateway session files for the dashboard.
    Tries nova_gateway HTTP API first, falls back to reading files directly.
    """
    import urllib.request, json as _json, pathlib, time as _t
    # Try nova_gateway API (it's running on 18790)
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:18790/api/sessions", timeout=2)
        data = _json.loads(resp.read())
        return JSONResponse({"sessions": data.get("sessions", [])[:limit]})
    except Exception:
        pass
    # Fallback: read from workspace/logs/gateway_sessions/ directly
    ws = Path(__file__).resolve().parent.parent.parent
    sessions_dir = ws / "logs" / "gateway_sessions"
    sessions = []
    if sessions_dir.exists():
        for p in sorted(sessions_dir.rglob("*.jsonl"),
                        key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
            try:
                with open(p, encoding="utf-8") as f:
                    header = _json.loads(f.readline())
                sessions.append({
                    "id":        header.get("id", p.stem),
                    "trigger":   header.get("trigger", "?"),
                    "timestamp": header.get("timestamp", ""),
                    "messages":  sum(1 for _ in open(p)),
                    "size_kb":   p.stat().st_size // 1024,
                })
            except Exception:
                pass
    return JSONResponse({"sessions": sessions})


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



@app.get("/api/gateway/status")
async def gateway_status():
    """Check if nova_gateway is running by hitting its /health endpoint on port 18790.
    Only a valid HTTP 200 from nova_gateway counts — raw TCP or legacy port 18789
    are no longer accepted as proof of a running gateway."""
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:18790/health", timeout=1) as resp:
            if resp.status == 200:
                return JSONResponse({"running": True, "port": 18790, "stack": "nova_gateway"})
    except Exception:
        pass
    return JSONResponse({"running": False})


@app.post("/api/gateway/start")
async def gateway_start():
    """Start nova_gateway in a new visible terminal.
    When running inside Nova.exe (sys.frozen) the gateway is already managed
    in-process by NovaLauncher — starting a second copy would conflict."""
    import subprocess, sys as _sys
    if getattr(_sys, 'frozen', False):
        return JSONResponse({
            "ok": False,
            "message": "Gateway is managed by Nova.exe. Restart the app to restart the gateway."
        })
    # Resolve workspace root — works whether server.py runs from source or a
    # plain python launch (not frozen).  NOVA_WORKSPACE env var wins if set.
    _workspace = (
        os.environ.get("NOVA_WORKSPACE")
        or str(Path(__file__).resolve().parent.parent.parent)
    )
    _runner = Path(_workspace) / "nova_gateway_runner.py"
    if not _runner.exists():
        return JSONResponse({
            "ok": False,
            "error": f"nova_gateway_runner.py not found at {_runner}"
        }, status_code=500)
    try:
        subprocess.Popen(
            ["powershell", "-NoExit", "-Command",
             f"cd '{_workspace}'; python nova_gateway_runner.py"],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            close_fds=True,
        )
        return JSONResponse({"ok": True, "message": "Nova Gateway starting on port 18790..."})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/gateway/stop")
async def gateway_stop():
    """Stop nova_gateway via its HTTP API, or kill the process."""
    import subprocess, urllib.request
    try:
        # Graceful: POST to nova_gateway shutdown endpoint
        urllib.request.urlopen(
            urllib.request.Request("http://127.0.0.1:18790/shutdown",
                                   method="POST"), timeout=3
        )
        return JSONResponse({"ok": True, "message": "Nova Gateway stopped."})
    except Exception:
        pass
    try:
        # Fallback: kill by port
        subprocess.run(
            ["powershell", "-Command",
             "Get-NetTCPConnection -LocalPort 18790 -ErrorAction SilentlyContinue | "
             "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"],
            capture_output=True, text=True, timeout=10
        )
        return JSONResponse({"ok": True, "message": "Nova Gateway process killed."})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)



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


@app.post("/api/gateway/health-check")
async def proxy_health_check():
    """Proxy: fire nova_gateway health check. Avoids CORS on direct browser calls."""
    import urllib.request as _ur
    try:
        resp = _ur.urlopen(
            _ur.Request("http://127.0.0.1:18790/api/cron/health", method="POST"),
            timeout=5
        )
        import json as _j
        return JSONResponse(_j.loads(resp.read()))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Gateway unreachable: {e}")


@app.post("/api/gateway/trigger")
async def proxy_trigger(body: dict = Body(...)):
    """Proxy: send a manual trigger to nova_gateway. Avoids CORS on direct calls."""
    import urllib.request as _ur, json as _j
    text   = body.get("text", "").strip()
    source = body.get("source", "manual")
    if not text:
        raise HTTPException(status_code=400, detail="'text' required")
    payload = _j.dumps({"text": text, "source": source}).encode()
    try:
        resp = _ur.urlopen(
            _ur.Request("http://127.0.0.1:18790/api/trigger",
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST"),
            timeout=120
        )
        return JSONResponse(_j.loads(resp.read()))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Gateway unreachable: {e}")


@app.post("/api/inject_message")
async def inject_message(body: dict):
    """
    Inject a message into the active Nova Chat session from an external source.
    Used by the gateway so Nova can post to the group chat from Discord.

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

    # Execute any nova_bridge directives Nova wrote (e.g. [EXEC:], [DISCORD:])
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
                        raise  # don't catch cancellation
                    except Exception as e:
                        print(f"[chat] Error in injected listener queue: {e}")
                    finally:
                        is_processing = False

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


@app.get("/api/chat/recent")
async def chat_recent(n: int = 40):
    """
    Return the last N messages from the active Nova Chat session as formatted text.

    Used by nova_gateway so Nova has full awareness of the Nova Chat session
    when responding via Discord or any other external source.  Lightweight
    plain-text format so it slots cleanly into a system prompt.

    Query param:  ?n=40  (default 40 messages)
    Returns: { session_id, message_count, formatted }
    """
    if session_mgr.active is None or not session_mgr.active_id:
        return JSONResponse({
            "session_id":    session_mgr.active_id or "",
            "message_count": 0,
            "formatted":     "(no active session)",
        })
    messages = session_mgr.active.get_recent(n)
    lines = []
    for msg in messages:
        ts = msg["timestamp"][11:16]   # HH:MM
        directed = ""
        if msg.get("directed_at"):
            directed = f" [@{', @'.join(msg['directed_at'])}]"
        # Omit raw image data — note presence only
        content = msg["content"]
        if msg.get("images"):
            content += f" [+ {len(msg['images'])} image(s)]"
        lines.append(f"[{ts}] {msg['author']}{directed}: {content}")
    return JSONResponse({
        "session_id":    session_mgr.active_id,
        "message_count": len(messages),
        "formatted":     "\n".join(lines) if lines else "(no messages yet)",
    })


@app.post("/api/reinject_context")
async def reinject_context():
    """
    Re-inject all nova_gateway.json inject_files into the active session as a
    fresh context block.  Called by the 'Re-orient Nova' button on the landing
    page and automatically on session switch so Nova always has current files.

    Reads each file fresh from disk (captures any changes since last boot),
    builds a compact CONTEXT REFRESH block, and posts it as a System message
    into the active session.  Nova reads it like any other chat message.

    Returns: { ok, files_injected, skipped, chars }
    """
    try:
        from gateway_config import load as _load_gw_cfg
        _cfg = _load_gw_cfg()
        inject_paths = _cfg.inject_files(heartbeat=False)
    except Exception as _e:
        print(f"[reinject] config load failed: {_e} — using fallback list")
        _WORKSPACE = Path(__file__).resolve().parent.parent.parent
        _FALLBACK = [
            "AGENTS.md", "NOVA.md", "TOOLS.md",
            "NCL_MASTER.md", "memory/STATUS.md", "memory/COLE.md",
            "Thoughts/priority.md", "Thoughts/THOUGHT_TEMPLATE.md",
        ]
        inject_paths = [_WORKSPACE / p for p in _FALLBACK if (_WORKSPACE / p).exists()]

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    sections = [f"# CONTEXT REFRESH — {ts}\n_Nova's workspace files re-injected from disk._"]
    injected, skipped = 0, 0

    for path in inject_paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                sections.append(f"## [{path.name}]\n{text}")
                injected += 1
            else:
                skipped += 1
        except Exception as _fe:
            print(f"[reinject] skipped {path.name}: {_fe}")
            skipped += 1

    if injected == 0:
        return JSONResponse({"ok": False, "error": "No files could be read", "files_injected": 0})

    block = "\n\n---\n\n".join(sections)
    chars = len(block)

    # Deliver as a System message so it's clearly labelled in the chat
    msg = session_mgr.active.add("System", block)
    session_mgr.update_meta_from_message(msg)
    await broadcast({
        "type":      "user_message",
        "author":    "System",
        "content":   block,
        "id":        msg["id"],
        "timestamp": msg["timestamp"],
    })

    print(f"[reinject] Context refresh: {injected} files, {chars} chars ({skipped} skipped)")
    return JSONResponse({"ok": True, "files_injected": injected, "skipped": skipped, "chars": chars})


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
    global is_processing, autonomous_mode  # declared once at top
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
                global _mute_states
                agent  = data.get("agent", "")
                muted  = bool(data.get("muted", True))
                if agent in _mute_states:
                    _mute_states[agent] = muted
                    await broadcast({"type": "mute_state", "agent": agent, "muted": muted})
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

                # Reject new messages while AIs are still responding
                if is_processing:
                    await ws.send_text(json.dumps({
                        "type": "blocked",
                        "reason": "AIs are still responding. Press STOP to interrupt."
                    }))
                    continue

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

                status = await get_status()
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

                            # ── Autonomous heartbeat loop ──────────────────────────────────
                            # When autonomous_mode is ON, Nova drives herself indefinitely.
                            # After each response the server sends a minimal [HEARTBEAT N]
                            # tick — Nova reads HEARTBEAT.md, checks Thoughts/priority.md
                            # and Master_Inbox, and decides what to do next on her own.
                            #
                            # Stop conditions (in priority order):
                            #   1. Cole toggles autonomous_mode OFF
                            #   2. Cole presses STOP (_stop_requested)
                            #   3. nova_status.json pulse == "Idle"  (silent completion)
                            #   4. Nova replies with IDLE or AUTONOMOUS_COMPLETE (explicit)
                            #   5. Safety backstop: 500 ticks (emergency only)
                            # ─────────────────────────────────────────────────────────────
                            _TICK_SAFETY = 500   # emergency backstop — not expected to hit
                            _auto_ticks  = 0
                            _ns_path     = Path(WORKSPACE_ROOT) / "nova_status.json"

                            while (autonomous_mode
                                   and not _stop_requested.is_set()
                                   and _auto_ticks < _TICK_SAFETY):

                                _auto_ticks += 1
                                await asyncio.sleep(2.5)   # let UI settle; respect rate limits

                                if not autonomous_mode or _stop_requested.is_set():
                                    break

                                nova_avail = await get_status()
                                if not nova_avail.get("Nova"):
                                    print("[autonomous] Nova offline — halting heartbeat loop")
                                    break

                                # ── Silent completion: check nova_status.json pulse ────────
                                # Nova writes pulse="Idle" via nova_cortex.nova_status.update()
                                # when she finishes her work.  No announcement needed.
                                if _ns_path.exists():
                                    try:
                                        _ns_data = json.loads(
                                            _ns_path.read_text(encoding="utf-8"))
                                        if str(_ns_data.get("pulse", "")).lower() == "idle":
                                            print(f"[autonomous] Nova pulse=Idle — "
                                                  f"silent stop after tick {_auto_ticks - 1}")
                                            _auto_ticks -= 1   # don't count the check tick
                                            break
                                    except Exception:
                                        pass

                                # ── Minimal heartbeat tick ─────────────────────────────────
                                # Just [HEARTBEAT N] — Nova reads HEARTBEAT.md to decide
                                # what to do.  No task context injected; her Thoughts hold it.
                                tick_content = f"[HEARTBEAT {_auto_ticks}]"
                                _tmsg = session_mgr.active.add("System", tick_content)
                                await broadcast({
                                    "type":      "user_message",
                                    "author":    "System",
                                    "content":   tick_content,
                                    "id":        _tmsg["id"],
                                    "timestamp": _tmsg["timestamp"],
                                })

                                # Run Nova's response, then honour any @mentions she makes
                                nova_reply = await run_ai_response(
                                    "Nova", CLIENT_MAP["Nova"],
                                    str(uuid.uuid4())[:8], tick_content,
                                )

                                # Fire @mention follow-ups so Gemini/Claude can respond
                                if nova_reply and not _stop_requested.is_set():
                                    _nova_mentions = parse_directed(nova_reply)
                                    _follow_ups = [n for n in _nova_mentions
                                                   if n in ("Claude", "Gemini")]
                                    if _follow_ups:
                                        _fu_status = await get_status()
                                        _fu_queue  = [n for n in _follow_ups
                                                      if _fu_status.get(n)]
                                        if _fu_queue:
                                            await _run_response_queue(_fu_queue, nova_reply)

                                # Explicit stop signals (fallback — silent pulse is preferred)
                                if nova_reply and any(phrase in nova_reply for phrase in (
                                    "AUTONOMOUS_COMPLETE",
                                    "HEARTBEAT_OK",
                                    "IDLE",
                                )):
                                    print(f"[autonomous] Nova explicit stop — "
                                          f"tick {_auto_ticks}")
                                    break

                            if _auto_ticks >= _TICK_SAFETY:
                                print(f"[autonomous] Safety backstop hit ({_TICK_SAFETY} ticks)")

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

                    task = asyncio.ensure_future(_queued_run())
                    active_tasks.append(task)
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass  # task was cancelled by a /stop request — that's fine

    except WebSocketDisconnect:
        pass  # client closed the tab or lost connection — normal, not an error
    finally:
        if ws in connected_clients:
            connected_clients.remove(ws)
