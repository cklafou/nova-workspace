"""
general_tools/gateway.py
========================
FastAPI entry point. Starts everything and keeps it running.
(Dissolved from nova_gateway package, 2026-05-08.)

What this does (plain English):
  This is the file you run to start Nova's gateway. Launch via:
    python general_tools/nova_gateway_runner.py [--dry] [--port 18790]
  It starts:
    - The Discord bot (if enabled in config)
    - The cron scheduler (health check every 30 min)
    - An HTTP API on port 18790 for nova_chat to query

  This replaces "openclaw gateway start" entirely.

HTTP API endpoints:
  GET  /health              — is the gateway alive?
  GET  /api/status          — full status (model, uptime, sessions, etc.)
  GET  /api/sessions        — recent session list (for nova_chat log viewer)
  GET  /api/thoughts        — live Thoughts panel data (active cards + priority queue)
  POST /api/trigger         — manually trigger a Nova run (for testing)
  POST /api/cron/health     — manually fire the health check
  GET  /api/nova/status     — read nova_status.json (same as nova_chat uses)

nova_chat integration:
  server.py queries http://127.0.0.1:18790 for gateway status.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from gateway_config import cfg, load as load_config, CONFIG_PATH
from nova_motor.tool_executor import ToolExecutor
from nova_memory.session_store import list_sessions   # nova_body/nova_memory — session manager
from nova_cortex.circadian import create_scheduler

log = logging.getLogger(__name__)

# ── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Nova Gateway",
    description="Python replacement for the OpenClaw gateway daemon",
    version="0.1.0",
)

# Allow nova_chat (port 8765) and NovaLauncher to call gateway endpoints
# directly from the browser without CORS errors.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8765", "http://localhost:8765",
                   "http://127.0.0.1:8766", "null"],  # "null" covers file:// and pywebview
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Shared state ─────────────────────────────────────────────────────────────
_state = {
    "started_at":     time.time(),
    "discord_ready":  False,
    "scheduler_ready": False,
    "vigilance_ready": False,
    "nova_status":    {},          # cached nova_status.json contents
    "nova_status_age": 0.0,
    "executor":       None,
    "scheduler":      None,
    "discord_bot":    None,
    "vigilance":      None,
}


# ── Startup / shutdown ───────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    log.info("Nova Gateway starting up (port %d)...", cfg.gateway["port"])

    # Shared tool executor
    executor = ToolExecutor()
    _state["executor"] = executor

    # Start scheduler
    scheduler = create_scheduler(executor)
    scheduler.start()
    _state["scheduler"]      = scheduler
    _state["scheduler_ready"] = True

    # Start nova_status polling
    asyncio.ensure_future(_poll_nova_status())

    # Start NovaVigilance — sleep/wake monitor that drives the background autonomy loop.
    # on_wake delegates to the scheduler's trigger_health_check_now(), which runs the
    # full Thoughts cycle (priority.md → Master_Inbox routing → agent_loop).
    try:
        from nova_cortex.vigilance import NovaVigilance

        def _on_wake(reason: str) -> None:
            log.info("[vigilance] WAKE: %s — triggering Thoughts cycle", reason)
            sched = _state.get("scheduler")
            if sched is not None:
                loop = asyncio.get_event_loop()
                loop.call_soon_threadsafe(
                    asyncio.ensure_future,
                    sched.trigger_health_check_now()
                )
            else:
                log.warning("[vigilance] WAKE fired but scheduler not ready — skipping")

        def _on_sleep(reason: str) -> None:
            log.info("[vigilance] SLEEP: %s", reason)

        vigilance = NovaVigilance(on_wake=_on_wake, on_sleep=_on_sleep)
        vigilance.start()
        _state["vigilance"] = vigilance
        _state["vigilance_ready"] = True
        log.info("NovaVigilance started — sleep/wake monitoring active.")
    except Exception as e:
        log.warning("NovaVigilance failed to start: %s", e)

    # Start Discord bot if enabled
    if cfg.discord.get("enabled", False):
        from discord_client import NovaDiscordBot
        bot = NovaDiscordBot(executor)
        _state["discord_bot"] = bot
        asyncio.ensure_future(_run_discord(bot))
    else:
        log.info("Discord disabled in config — skipping bot startup.")

    log.info("Nova Gateway ready.")


@app.on_event("shutdown")
async def shutdown():
    log.info("Nova Gateway shutting down...")
    if _state["vigilance"]:
        _state["vigilance"].stop()
    if _state["scheduler"]:
        _state["scheduler"].stop()
    if _state["discord_bot"]:
        await _state["discord_bot"].stop()


async def _run_discord(bot) -> None:
    """Run Discord bot as a background task."""
    try:
        await bot.start()
        _state["discord_ready"] = True
    except Exception as e:
        log.error("Discord bot failed: %s", e, exc_info=True)
        _state["discord_ready"] = False


async def _poll_nova_status() -> None:
    """
    Background task: read nova_status.json every 30s and cache it.
    This keeps the /api/nova/status endpoint fast and provides fresh
    data for the Discord bot and scheduler to inject into agent runs.
    """
    nova_status_path = cfg.workspace / "nova_status.json"
    while True:
        try:
            if nova_status_path.exists():
                data = json.loads(nova_status_path.read_text(encoding="utf-8"))
                _state["nova_status"]     = data
                _state["nova_status_age"] = time.time()
                summary = _build_status_summary(data)
                # Keep scheduler and discord bot in sync
                if _state["scheduler"]:
                    _state["scheduler"].update_nova_status(summary)
                if _state["discord_bot"]:
                    _state["discord_bot"].update_nova_status(summary)
        except Exception as e:
            log.warning("nova_status.json read error: %s", e)
        await asyncio.sleep(30)


def _build_status_summary(data: dict) -> str:
    """Build a one-paragraph status summary from nova_status.json."""
    pulse   = data.get("pulse", "unknown")
    summary = data.get("summary", "")
    task    = data.get("active_task", {})
    errors  = data.get("errors", [])

    parts = [f"Nova status: {pulse}."]
    if summary:
        parts.append(summary)
    if task and task.get("id"):
        parts.append(f"Active task: {task.get('description', task['id'])}.")
    if errors:
        parts.append(f"Recent errors: {len(errors)}.")
    return " ".join(parts)


# ── HTTP API ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Simple liveness check."""
    return {"ok": True, "service": "nova-gateway"}


@app.get("/api/status")
async def status():
    """Full gateway status."""
    uptime_s = int(time.time() - _state["started_at"])
    discord_bot = _state.get("discord_bot")
    discord_ready = getattr(discord_bot, "_ready", False) if discord_bot else False
    return {
        "ok":              True,
        "uptime_s":        uptime_s,
        "discord_ready":   discord_ready,
        "scheduler_ready": _state["scheduler_ready"],
        "discord_enabled": cfg.discord.get("enabled", False),
        "nova_model":      "nova-qwen35-27b",
        "context_window":  cfg.inference["context_window"],
        "gateway_port":    cfg.gateway["port"],
        "nova_status_age": int(time.time() - _state["nova_status_age"])
            if _state["nova_status_age"] else None,
    }


@app.post("/shutdown")
async def shutdown_endpoint():
    """Graceful shutdown — called by nova_chat gateway stop button."""
    import os, signal
    log.info("Shutdown requested via API.")
    asyncio.ensure_future(_delayed_shutdown())
    return {"ok": True, "message": "Shutting down..."}

async def _delayed_shutdown():
    await asyncio.sleep(0.5)
    import os, signal
    os.kill(os.getpid(), signal.SIGTERM)


@app.get("/api/sessions")
async def sessions(limit: int = 50):
    """List recent Nova sessions (for nova_chat log viewer)."""
    return {"sessions": list_sessions(limit=limit)}


@app.get("/api/nova/status")
async def nova_status():
    """Return cached nova_status.json contents."""
    return {
        "nova_live":   _state["nova_status"],
        "age_s":       int(time.time() - _state["nova_status_age"])
            if _state["nova_status_age"] else None,
    }


@app.get("/api/thoughts")
async def thoughts_status():
    """
    Return a structured snapshot of Nova's Thoughts system for nova_chat UI.

    Scans workspace/Tasking/ for active thought folders, parses each master.md,
    and also returns the priority queue summary from priority.md.

    Response shape:
    {
        "active": [
            {
                "id": "TASK_NAME",
                "status": "active" | "blocked" | "suspended" | ...,
                "priority": "critical" | "high" | "medium" | "low",
                "priority_num": 0-4,
                "summary": "first line of Context section",
                "plan_total": 5,
                "plan_done": 2,
                "last_updated": "2026-05-09 14:22",
                "folder": "Tasking/TASK_NAME/"
            },
            ...
        ],
        "finished_recent": [...],   # last 5 from Finished/
        "priority_queue": {         # parsed from priority.md
            "p0": bool,
            "p1": [...],
            "p2": [...],
            "p3": [...],
            "p4": [...],
            "blocked": [...],
            "suspended": [...],
        },
        "scanned_at": 1234567890
    }
    """
    import re as _re

    thoughts_root = cfg.workspace / "Thoughts"
    if not thoughts_root.exists():
        return {"active": [], "finished_recent": [], "priority_queue": {}, "scanned_at": int(time.time())}

    PRIORITY_MAP = {"critical": 1, "high": 2, "medium": 3, "low": 4, "urgent": 1}

    def _parse_master(md_path: Path, folder_name: str) -> dict:
        """Parse a master.md file into a thought card dict."""
        try:
            text = md_path.read_text(encoding="utf-8")
        except Exception:
            return None

        # Extract bold field values: **Field:** value
        def _field(name: str) -> str:
            m = _re.search(rf'\*\*{name}:\*\*\s*(.+)', text, _re.IGNORECASE)
            return m.group(1).strip() if m else ""

        status       = _field("Status") or "unknown"
        priority_str = _field("Priority").split("|")[0].strip().lower()
        task_id      = _field("Task ID") or folder_name
        last_updated = _field("Last Updated") or _field("Created") or ""

        # Context: first non-empty line after the "## Context" header
        ctx_m = _re.search(r'##\s+Context\s*\n+_(.*?)_', text, _re.DOTALL)
        if not ctx_m:
            ctx_m = _re.search(r'##\s+Context\s*\n+(.*?)(?:\n\n|\n##)', text, _re.DOTALL)
        summary = ""
        if ctx_m:
            raw = ctx_m.group(1).strip()
            # Take the first sentence / first 120 chars
            first = raw.split('\n')[0].strip()
            summary = first[:120] if first and first not in ("_", "—") else ""

        # If no context, fall back to the line after the title
        if not summary:
            lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith('#')]
            if lines:
                summary = lines[0][:120]

        # Count plan checkboxes
        plan_items = _re.findall(r'- \[( |x|X)\]', text)
        plan_total = len(plan_items)
        plan_done  = sum(1 for c in plan_items if c.lower() == 'x')

        return {
            "id":          task_id,
            "status":      status.lower(),
            "priority":    priority_str,
            "priority_num": PRIORITY_MAP.get(priority_str, 3),
            "summary":     summary,
            "plan_total":  plan_total,
            "plan_done":   plan_done,
            "last_updated": last_updated,
            "folder":      f"Tasking/{folder_name}/",
        }

    # ── Scan active thoughts (direct children of Tasking/) ──────────────────
    skip_dirs = {"Finished", "Master_Inbox"}
    active = []
    for entry in sorted(thoughts_root.iterdir()):
        if not entry.is_dir() or entry.name in skip_dirs:
            continue
        master = entry / "master.md"
        if not master.exists():
            continue
        card = _parse_master(master, entry.name)
        if card:
            active.append(card)

    # Sort by priority_num then name
    active.sort(key=lambda c: (c["priority_num"], c["id"]))

    # ── Scan recently finished thoughts ───────────────────────────────────────
    finished_recent = []
    for bucket in ("completed_success", "completed_fail", "cancelled"):
        bucket_dir = thoughts_root / "Finished" / bucket
        if not bucket_dir.exists():
            continue
        for entry in sorted(bucket_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not entry.is_dir():
                continue
            master = entry / "master.md"
            if not master.exists():
                continue
            card = _parse_master(master, entry.name)
            if card:
                card["bucket"] = bucket
                finished_recent.append(card)
            if len(finished_recent) >= 5:
                break
        if len(finished_recent) >= 5:
            break

    # ── Parse priority.md ─────────────────────────────────────────────────────
    priority_queue: dict = {}
    pmd = thoughts_root / "priority.md"
    if pmd.exists():
        try:
            ptext = pmd.read_text(encoding="utf-8")

            def _pq_section(label: str) -> list[str]:
                """Extract bullet items from a named priority section."""
                m = _re.search(rf'##\s+{label}.*?\n(.*?)(?:\n##|\Z)', ptext, _re.DOTALL | _re.IGNORECASE)
                if not m:
                    return []
                block = m.group(1)
                items = _re.findall(r'[-*]\s+(.+)', block)
                # Filter out placeholder lines
                return [i.strip() for i in items if i.strip() and "None active" not in i]

            priority_queue = {
                "p0_active": bool(_re.search(r'COLE SPEAKS', ptext, _re.IGNORECASE)),
                "p1": _pq_section(r'PRIORITY 1[^#]*'),
                "p2": _pq_section(r'PRIORITY 2[^#]*'),
                "p3": _pq_section(r'PRIORITY 3[^#]*'),
                "p4": _pq_section(r'PRIORITY 4[^#]*'),
                "blocked":   _pq_section(r'BLOCKED[^#]*'),
                "suspended": _pq_section(r'SUSPENDED[^#]*'),
            }
        except Exception as e:
            log.warning("priority.md parse error: %s", e)

    return {
        "active":         active,
        "finished_recent": finished_recent,
        "priority_queue": priority_queue,
        "scanned_at":     int(time.time()),
    }


@app.get("/api/files")
async def list_files():
    """
    Return a shallow-depth file tree of the workspace for nova_chat's Files panel.
    Returns: { "tree": [ { "name": str, "type": "dir"|"file", "children": [...] } ] }
    """
    import os as _os

    def _scan(path, depth=0, max_depth=3):
        items = []
        try:
            entries = sorted(_os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return items
        for e in entries:
            # Skip hidden files/dirs and __pycache__
            if e.name.startswith('.') or e.name == '__pycache__':
                continue
            if e.is_dir():
                children = _scan(e.path, depth + 1, max_depth) if depth < max_depth else []
                items.append({"name": e.name, "type": "dir", "children": children})
            else:
                items.append({"name": e.name, "type": "file"})
        return items

    tree = _scan(cfg.workspace)
    return {"tree": tree, "root": str(cfg.workspace)}


@app.get("/api/logs")
async def get_logs(lines: int = 200):
    """
    Return the last N lines from Nova's log file for the Logs viewer in nova_chat.
    """
    import os as _os

    # Try common log locations
    candidates = [
        cfg.workspace / "logs" / "nova.log",
        cfg.workspace / "nova.log",
        cfg.workspace.parent / "nova.log",
    ]
    log_path = None
    for c in candidates:
        if c.exists():
            log_path = c
            break

    if not log_path:
        return {"lines": ["(no log file found — expected workspace/logs/nova.log)"], "path": None}

    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        return {"lines": [l.rstrip() for l in all_lines[-lines:]], "path": str(log_path)}
    except Exception as e:
        return {"lines": [f"Error reading log: {e}"], "path": str(log_path)}


@app.get("/api/llama/status")
async def llama_status():
    """Return llama.cpp server status."""
    import urllib.request as _ur
    try:
        with _ur.urlopen("http://127.0.0.1:8080/health", timeout=1) as r:
            running = r.status < 400
    except Exception:
        running = False
    return {"running": running, "status": "running" if running else "offline"}


@app.post("/api/llama/toggle")
async def llama_toggle():
    """Attempt to toggle the llama.cpp server (start if offline, no-op if running)."""
    import urllib.request as _ur
    try:
        with _ur.urlopen("http://127.0.0.1:8080/health", timeout=1) as r:
            running = r.status < 400
    except Exception:
        running = False
    if running:
        return {"message": "llama.cpp is already running on port 8080"}
    return {"message": "llama.cpp not running — start it manually via llama_server.exe or llama.bat"}


@app.patch("/sessions/{session_id}")
async def rename_session(session_id: str, body: dict):
    """Rename a chat session (nova_chat UI calls this from session rename UI)."""
    new_name = (body.get("name") or "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="name required")
    # Forward to nova_chat server if accessible
    import urllib.request as _ur, json as _json, urllib.error as _ue
    try:
        req = _ur.Request(
            f"http://127.0.0.1:8765/sessions/{session_id}",
            data=_json.dumps({"name": new_name}).encode(),
            headers={"Content-Type": "application/json"},
            method="PATCH",
        )
        with _ur.urlopen(req, timeout=2) as r:
            return _json.loads(r.read())
    except _ue.HTTPError as e:
        if e.code == 404:
            raise HTTPException(status_code=404, detail="session not found")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        raise HTTPException(status_code=503, detail="nova_chat not reachable")


@app.post("/api/trigger")
async def manual_trigger(body: dict):
    """
    Manually trigger a Nova agent run. Useful for testing without Discord.

    Body: {"text": "your message here", "source": "manual"}
    """
    text   = body.get("text", "").strip()
    source = body.get("source", "manual")

    if not text:
        raise HTTPException(status_code=400, detail="'text' field required")

    executor = _state["executor"]
    if executor is None:
        raise HTTPException(status_code=503, detail="Gateway not fully started")

    log.info("Manual trigger: %s", text[:80])

    try:
        from nova_cortex.agent_loop import run_agent
        result = await run_agent(
            text=text,
            source=source,
            executor=executor,
            nova_status_summary=_build_status_summary(_state["nova_status"]),
        )
        return {
            "ok":             result.ok,
            "text":           result.text,
            "session_id":     result.session_id,
            "tool_calls":     result.tool_calls_made,
            "tokens":         result.total_tokens,
            "duration_s":     result.duration_s,
            "error":          result.error,
        }
    except Exception as e:
        log.error("Manual trigger failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cron/health")
async def cron_health():
    """Manually fire the health check job."""
    scheduler = _state["scheduler"]
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not running")
    asyncio.ensure_future(scheduler.trigger_health_check_now())
    return {"ok": True, "message": "Health check triggered (running in background)"}


class _DiscordSendBody(BaseModel):
    text: str
    channel_id: Optional[int] = None


@app.post("/api/discord/send")
async def discord_send(body: _DiscordSendBody):
    """Send a message to Discord from nova_chat or any internal caller.

    Body: { "text": "message text", "channel_id": 12345 }
    channel_id is optional — falls back to the first allowlisted channel.
    """
    bot = _state.get("discord_bot")
    # Use bot._ready (set in on_ready event); _state["discord_ready"] was broken
    # because it was set after bot.start() returns, which never happens while running
    if bot is None or not getattr(bot, "_ready", False):
        raise HTTPException(status_code=503, detail="Discord bot not connected")

    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    channel_id = body.channel_id
    if channel_id is None:
        # Try allowlist first (static config), then fall back to the channel learned
        # from the most recent incoming DM (no allowlist needed for DM-only setups)
        allowlist = cfg.discord.get("allowlist", [])
        if allowlist:
            channel_id = int(allowlist[0])
        elif getattr(bot.executor, "_default_channel", None):
            channel_id = bot.executor._default_channel
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No send channel known — add a channel ID to allowlist in "
                    "nova_gateway.json, or send the bot a DM first so it can learn your channel ID"
                )
            )

    try:
        await bot._send_message(channel_id, text)
        return {"ok": True, "channel_id": channel_id, "chars": len(text)}
    except Exception as e:
        log.error("discord_send failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Nova Gateway")
    parser.add_argument(
        "--dry", action="store_true",
        help="Verify config only, don't start connections"
    )
    parser.add_argument(
        "--config", type=str, default=None,
        help="Path to nova_gateway.json (default: workspace/nova_gateway.json)"
    )
    parser.add_argument(
        "--port", type=int, default=None,
        help="Override gateway port from config"
    )
    args = parser.parse_args()

    # Configure logging — console + daily rotating file in logs/gateway/
    from datetime import date
    import logging.handlers

    log_dir = cfg.workspace / "logs" / "gateway"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (existing behaviour)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_fmt)

    # File handler — rolls at midnight, keeps 7 days of history
    log_file = log_dir / f"gateway-{date.today()}.log"
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_file, when="midnight", backupCount=7, encoding="utf-8"
    )
    file_handler.setFormatter(log_fmt)
    # Ensure the rolled files also match the gateway-YYYY-MM-DD.log naming
    file_handler.suffix = "%Y-%m-%d"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Load config
    if args.config:
        from gateway_config import load
        import gateway_config as _cfg_mod
        _cfg_mod.cfg = load(Path(args.config))

    port = args.port or cfg.gateway["port"]

    if args.dry:
        print("\n=== Nova Gateway — Dry Run ===")
        print(f"Workspace:    {cfg.workspace}")
        print(f"Nova model:   nova-qwen35-27b (via nova_chat @ localhost:8765)")
        print(f"Gateway port: {port}")
        print(f"Discord:      {'ENABLED' if cfg.discord.get('enabled') else 'DISABLED'}")
        print(f"Cron:         {'ENABLED' if cfg.cron.get('health_check', {}).get('enabled') else 'DISABLED'}")
        print("\nInject files:")
        for p in cfg.inject_files():
            exists = "✓" if p.exists() else "✗ MISSING"
            print(f"  {exists}  {p.name}")
        print("\nConfig OK — exiting (dry run).")
        sys.exit(0)

    print()
    print("=" * 52)
    print("  NOVA GATEWAY  --  http://127.0.0.1:" + str(port))
    print("  Replaces OpenClaw gateway on port 18789.")
    print("  Close this window to stop.")
    print("=" * 52)
    print()

    uvicorn.run(
        "gateway:app",
        host=cfg.gateway["host"],
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
