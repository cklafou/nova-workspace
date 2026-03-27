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
from pathlib import Path
import sys
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from nova_chat.transcript import Transcript
from nova_chat.session_manager import SessionManager
from nova_chat.orchestrator import parse_directed, should_respond
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
                            if "ERROR" in line or "error" in line.lower() and "ImportError" not in line:
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
    return JSONResponse({"status": "new session started", "session_id": session_id})


# ── Internal helpers ───────────────────────────────────────────────────────────

async def broadcast(data: dict):
    msg = json.dumps(data)
    dead = []
    for ws in connected_clients:
        try:
            await ws.send_text(msg)
        except Exception:
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


async def _run_gemini_response(on_token, on_done, on_error, workspace_context: str = ""):
    """Run Gemini sync SDK in thread pool."""
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
            full_response = call_gemini_sync(prompt, workspace_context)
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
                          latest_message: str = ""):
    """Stream one AI response and broadcast tokens, with workspace context."""
    # Update workspace context based on what was mentioned in the message
    if latest_message:
        workspace.update_for_message(latest_message)
    ws_context = workspace.build_context_block()

    # 1.3 -- Silently prepend Nova's live status to workspace context (no chat message)
    if nova_status_cache.get("summary"):
        status_block = (
            "\n--- NOVA LIVE STATUS (auto-injected, do not mention unless relevant) ---\n"
            + nova_status_cache["summary"]
            + "\n--- END NOVA STATUS ---\n"
        )
        ws_context = status_block + ws_context

    await broadcast({"type": "message_start", "author": ai_name, "id": msg_id})

    async def on_token(token):
        await broadcast({"type": "token", "author": ai_name, "token": token, "id": msg_id})

    async def on_done(full):
        msg = session_mgr.active.add(ai_name, full)
        session_mgr.update_meta_from_message(msg)
        await broadcast({"type": "message_end", "author": ai_name, "id": msg_id})
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
        await _run_gemini_response(on_token, on_done, on_error, ws_context)
    else:
        await client_mod.stream_response(
            session_mgr.active, on_token, on_done, on_error, workspace_context=ws_context
        )


# ── WebSocket ──────────────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════════════════
# TOOLS PANEL ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

WORKSPACE_ROOT = Path(__file__).parent.parent.parent
TEXT_EXTS      = {".py", ".md", ".json", ".jsonl", ".txt", ".ps1", ".cmd",
                  ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env"}
EXCLUDE_DIRS   = {"__pycache__", ".git", "node_modules", ".clawhub",
                  "backups", "sessions"}


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
    # Fallback: read from workspace/sessions/ directly
    ws = Path(__file__).resolve().parent.parent.parent
    sessions_dir = ws / "sessions"
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
        await ws.send_text(json.dumps({
            "type": "history",
            "author": msg["author"],
            "content": msg["content"],
            "id": msg["id"],
            "timestamp": msg["timestamp"],
        }))

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
                if not content:
                    continue
                # Reject new messages while AIs are still responding
                if is_processing:
                    await ws.send_text(json.dumps({
                        "type": "blocked",
                        "reason": "AIs are still responding. Press STOP to interrupt."
                    }))
                    continue

                directed_at = parse_directed(content)
                msg = session_mgr.active.add("Cole", content, directed_at or None)
                session_mgr.update_meta_from_message(msg)

                await broadcast({
                    "type": "user_message",
                    "author": "Cole",
                    "content": content,
                    "id": msg["id"],
                    "timestamp": msg["timestamp"],
                    "directed_at": directed_at,
                })

                status = await get_status()
                tasks = []
                if should_respond("Claude", directed_at) and status.get("Claude"):
                    tasks.append(run_ai_response("Claude", claude_client, str(uuid.uuid4())[:8], content))
                if should_respond("Gemini", directed_at) and status.get("Gemini"):
                    tasks.append(run_ai_response("Gemini", gemini_client, str(uuid.uuid4())[:8], content))
                if should_respond("Nova", directed_at) and status.get("Nova"):
                    tasks.append(run_ai_response("Nova", nova_client, str(uuid.uuid4())[:8], content))

                if tasks:
                    is_processing = True
                    await broadcast({"type": "processing_start"})
                    gathered = asyncio.gather(*tasks)
                    task = asyncio.ensure_future(gathered)
                    active_tasks.append(task)
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    finally:
                        if task in active_tasks:
                            active_tasks.remove(task)
                        is_processing = False
                        await broadcast({"type": "processing_end"})

    except WebSocketDisconnect:
        if ws in connected_clients:
            connected_clients.remove(ws)
    except Exception as e:
        print(f"[chat] WebSocket error: {e}")
        if ws in connected_clients:
            connected_clients.remove(ws)
