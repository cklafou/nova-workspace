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

app = FastAPI()

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
connected_clients: list[WebSocket] = []
active_tasks: list[asyncio.Task] = []
is_processing: bool = False

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

    async def _bg_nova_status_poll():
        """
        1.3 -- Poll nova_status.json every 30s and cache for silent AI injection.
        Runs forever in background. Updates nova_status_cache global.
        """
        import asyncio as _aio
        await _aio.sleep(2)  # slight offset from index build
        while True:
            try:
                sys.path.insert(0, str(WORKSPACE_ROOT / "tools"))
                from nova_core.nova_status import read_summary
                summary = read_summary()
                nova_status_cache["summary"] = summary
                nova_status_cache["updated_at"] = __import__('time').time()
            except Exception as e:
                nova_status_cache["summary"] = f"[nova_status unavailable: {e}]"
            await _aio.sleep(30)

    async def _bg_gateway_error_watch():
        """
        1.4 -- Tail OpenClaw gateway log for ERROR lines.
        Surfaces new errors into nova_chat as a system notice (not a chat message).
        Runs forever in background.
        """
        import asyncio as _aio
        import pathlib as _pl
        import time as _t

        await _aio.sleep(3)
        # nova_gateway writes logs to workspace/logs/gateway/ (our stack)
        # Fallback: also watch old openclaw log path during transition
        import pathlib as _pl2
        _WORKSPACE = _pl.Path(__file__).resolve().parent.parent.parent
        LOG_DIR = _WORKSPACE / "logs" / "gateway"
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR_LEGACY = _pl.Path("C:/tmp/openclaw")   # OpenClaw — remove after 3.13
        last_error_seen = ""
        last_pos = 0

        while True:
            try:
                today = __import__('datetime').date.today().strftime("%Y-%m-%d")
                # Prefer nova_gateway log; fall back to legacy OpenClaw log
                log_path = LOG_DIR / f"gateway-{today}.log"
                if not log_path.exists():
                    log_path = LOG_DIR_LEGACY / f"openclaw-{today}.log"
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
                                        from nova_core.nova_status import update_gateway
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

    asyncio.ensure_future(_bg_index())
    asyncio.ensure_future(_bg_nova_status_poll())
    asyncio.ensure_future(_bg_gateway_error_watch())


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
    Usage from nova_action/autonomy.py:
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
            await broadcast({"type": "message_end", "author": ai_name, "id": msg_id})

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

    workspace.reload()
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

    # Auto-reinject context so Nova has fresh files in every reopened session.
    # Fire-and-forget — don't block the switch response.
    async def _auto_reinject():
        try:
            await reinject_context()
            print(f"[session_switch] Auto-reinjected context into session {session_id}")
        except Exception as _e:
            print(f"[session_switch] Auto-reinject failed: {_e}")
    asyncio.create_task(_auto_reinject())

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
    """Delete a session (cannot delete active)."""
    ok = session_mgr.delete_session(session_id)
    if not ok:
        return JSONResponse({"error": "cannot delete active session or not found"}, status_code=400)
    await broadcast({"type": "sessions_updated", "sessions": session_mgr.get_all_meta()})
    return JSONResponse({"ok": True})


@app.post("/stop")
async def stop_endpoint():
    """Cancel all in-flight AI response tasks immediately."""
    global is_processing
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
    async def _auto_reinject_new():
        try:
            await reinject_context()
        except Exception as _e:
            print(f"[new_session] Auto-reinject failed: {_e}")
    asyncio.create_task(_auto_reinject_new())
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
        gateway_dir = WORKSPACE_ROOT / "gateway_sessions"
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
    if latest_message:
        workspace.update_for_message(latest_message)
    ws_context = workspace.build_context_block()

    # Cross-session awareness: inject recent Discord activity so Nova Chat AIs
    # know what was discussed on Discord (the missing consolidation direction).
    discord_ctx = _build_discord_context_block()
    if discord_ctx:
        ws_context = discord_ctx + ws_context

    # 1.3 -- Silently prepend Nova's live status to workspace context (no chat message)
    if nova_status_cache.get("summary"):
        status_block = (
            "\n--- NOVA LIVE STATUS (auto-injected, do not mention unless relevant) ---\n"
            + nova_status_cache["summary"]
            + "\n--- END NOVA STATUS ---\n"
        )
        ws_context = status_block + ws_context

    await broadcast({"type": "message_start", "author": ai_name, "id": msg_id})

    _result: list[str] = []  # capture full text so we can return it
    _think_started = [False]  # tracks whether think_start has been broadcast

    async def on_token(token):
        await broadcast({"type": "token", "author": ai_name, "token": token, "id": msg_id})

    async def on_think_token(token):
        """Broadcasts think_start once, then think_token for each token.
        Only wired for Nova — Claude/Gemini handle their own thinking display."""
        if not _think_started[0]:
            _think_started[0] = True
            await broadcast({"type": "think_start", "author": ai_name, "id": msg_id})
        await broadcast({"type": "think_token", "author": ai_name, "token": token, "id": msg_id})

    async def on_done(full):
        _result.append(full)
        # Close the think block if one was opened
        if _think_started[0]:
            await broadcast({"type": "think_end", "author": ai_name, "id": msg_id})
        msg = session_mgr.active.add(ai_name, full)
        session_mgr.update_meta_from_message(msg)
        await broadcast({"type": "message_end", "author": ai_name, "id": msg_id})
        # Phase 4A.5 — Route module responses with [TASK_ID] to Master_Inbox
        _maybe_route_inbox(ai_name, full)
        # If Nova wrote action directives, forward them to her real OpenClaw agent
        if ai_name == "Nova":
            bridge_results = await handle_nova_message(full)
            for result in bridge_results:
                await broadcast({
                    "type": "injection_notice",
                    "path": result,
                    "recipients": "OpenClaw agent",
                })

    async def on_error(err):
        await broadcast({"type": "error", "author": ai_name, "message": err, "id": msg_id})

    if ai_name == "Gemini":
        await _run_gemini_response(on_token, on_done, on_error, ws_context, images=images)
    elif ai_name == "Nova":
        # Nova supports <think> tag parsing — pass on_think_token
        await client_mod.stream_response(
            session_mgr.active, on_token, on_done, on_error,
            on_think_token=on_think_token,
            workspace_context=ws_context, images=images
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
                  "backups", "gateway_sessions"}


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
            # Also check OpenClaw session logs
            import pathlib as _pl
            openclaw = _pl.Path.home() / ".openclaw" / "agents" / "main" / "sessions"
            if openclaw.exists():
                for p in openclaw.rglob("*.jsonl"):
                    if ".reset." not in p.name and p.stat().st_mtime > _time.time() - 86400:
                        candidates.append(p)
            if not candidates:
                return None
            return max(candidates, key=lambda p: p.stat().st_mtime)
        else:
            # Support absolute paths (for openclaw files) and workspace-relative paths
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



@app.get("/api/logs/openclaw")
async def openclaw_sessions():
    """List OpenClaw agent session logs (Nova's actual thought log)."""
    import pathlib, time as _t
    openclaw_sessions = pathlib.Path.home() / ".openclaw" / "agents" / "main" / "sessions"
    files = []
    if openclaw_sessions.exists():
        for p in sorted(openclaw_sessions.rglob("*.jsonl"),
                        key=lambda x: x.stat().st_mtime, reverse=True):
            if ".reset." in p.name:
                continue
            files.append({
                "path":     str(p),
                "name":     p.name,
                "size":     p.stat().st_size,
                "modified": _t.strftime("%H:%M:%S", _t.localtime(p.stat().st_mtime)),
                "type":     "openclaw_session",
            })
    # Also cron runs
    cron_runs = pathlib.Path.home() / ".openclaw" / "cron" / "runs"
    if cron_runs.exists():
        for p in sorted(cron_runs.rglob("*.jsonl"),
                        key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
            files.append({
                "path":     str(p),
                "name":     f"cron/{p.name}",
                "size":     p.stat().st_size,
                "modified": _t.strftime("%H:%M:%S", _t.localtime(p.stat().st_mtime)),
                "type":     "openclaw_cron",
            })
    return JSONResponse({"files": files})



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
    # Fallback: read from workspace/gateway_sessions/ directly
    ws = Path(__file__).resolve().parent.parent.parent
    sessions_dir = ws / "gateway_sessions"
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


@app.post("/api/nova/bridge")
async def nova_bridge_endpoint(body: dict = Body(...)):
    """
    Manually forward an instruction to Nova's real OpenClaw agent.
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
    await broadcast({"type": "injection_notice", "path": result, "recipients": "OpenClaw agent"})
    return JSONResponse({"result": result})



@app.get("/api/gateway/status")
async def gateway_status():
    """Check if nova_gateway is running by hitting its /health endpoint on port 18790.
    Only a valid HTTP 200 from nova_gateway counts — raw TCP or OpenClaw on 18789
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
                from nova_gateway.injector import NCLInjector
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
        from nova_gateway.config import load as _load_gw_cfg
        _cfg = _load_gw_cfg()
        inject_paths = _cfg.inject_files(heartbeat=False)
    except Exception as _e:
        print(f"[reinject] config load failed: {_e} — using fallback list")
        _WORKSPACE = Path(__file__).resolve().parent.parent.parent
        _FALLBACK = [
            "AGENTS.md", "SOUL.md", "IDENTITY.md", "TOOLS.md",
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
    global is_processing  # declared once at top
    await ws.accept()
    connected_clients.append(ws)

    # Send status, sessions, and history on connect
    status = await get_status()
    await ws.send_text(json.dumps({"type": "status", "participants": status}))

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

            if data.get("type") == "message":
                content = data.get("content", "").strip()
                images  = data.get("images", [])  # [{dataUrl, name}]
                if not content and not images:
                    continue

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
                msg = session_mgr.active.add("Cole", content, directed_at or None,
                                             images=images)
                session_mgr.update_meta_from_message(msg)

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
                    is_processing = True
                    await broadcast({"type": "processing_start"})

                    # Capture queue, content, and images at definition time
                    _q = list(queue)    # make a copy
                    _c = content
                    _imgs = images or []   # images from this Cole message

                    async def _queued_run():
                        global is_processing
                        try:
                            await _run_response_queue(_q, _c, images=_imgs or None)
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
                        pass
                    finally:
                        if task in active_tasks:
                            active_tasks.remove(task)
                        is_processing = False  # safety net: ensure reset if cancelled before starting

    except WebSocketDisconnect:
        if ws in connected_clients:
            connected_clients.remove(ws)
    except Exception as e:
        print(f"[chat] WebSocket error: {e}")
        if ws in connected_clients:
            connected_clients.remove(ws)
