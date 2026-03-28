"""
nova_gateway/gateway.py
========================
FastAPI entry point. Starts everything and keeps it running.

What this does (plain English):
  This is the file you run to start Nova's gateway. When you execute:
    python -m nova_gateway.gateway
  it starts:
    - The Discord bot (if enabled in config)
    - The cron scheduler (health check every 30 min)
    - An HTTP API on port 18790 for nova_chat to query

  This replaces "openclaw gateway start" entirely.

HTTP API endpoints:
  GET  /health              — is the gateway alive?
  GET  /api/status          — full status (model, uptime, sessions, etc.)
  GET  /api/sessions        — recent session list (for nova_chat log viewer)
  POST /api/trigger         — manually trigger a Nova run (for testing)
  POST /api/cron/health     — manually fire the health check
  GET  /api/nova/status     — read nova_status.json (same as nova_chat uses)

nova_chat integration:
  Update server.py to query http://127.0.0.1:18790 instead of 18789.
  The gateway/start and gateway/stop buttons will need updating too
  (Phase 3 task 3.10).

Usage:
  # From workspace/tools/ directory:
  python -m nova_gateway.gateway

  # Dry run (verify config, don't connect):
  python -m nova_gateway.gateway --dry

  # Custom config file:
  python -m nova_gateway.gateway --config /path/to/nova_gateway.json
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

from .config import cfg, load as load_config, CONFIG_PATH
from .tool_executor import ToolExecutor
from .session_store import list_sessions
from .scheduler import create_scheduler

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
    "nova_status":    {},          # cached nova_status.json contents
    "nova_status_age": 0.0,
    "executor":       None,
    "scheduler":      None,
    "discord_bot":    None,
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

    # Start Discord bot if enabled
    if cfg.discord.get("enabled", False):
        from .discord_client import NovaDiscordBot
        bot = NovaDiscordBot(executor)
        _state["discord_bot"] = bot
        asyncio.ensure_future(_run_discord(bot))
    else:
        log.info("Discord disabled in config — skipping bot startup.")

    log.info("Nova Gateway ready.")


@app.on_event("shutdown")
async def shutdown():
    log.info("Nova Gateway shutting down...")
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
        "ollama_model":    cfg.ollama["model"],
        "context_window":  cfg.ollama["context_window"],
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
        from .agent_loop import run_agent
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
        from .config import load
        import nova_gateway.config as _cfg_mod
        _cfg_mod.cfg = load(Path(args.config))

    port = args.port or cfg.gateway["port"]

    if args.dry:
        print("\n=== Nova Gateway — Dry Run ===")
        print(f"Workspace:    {cfg.workspace}")
        print(f"Ollama model: {cfg.ollama['model']} @ {cfg.ollama['base_url']}")
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
        "nova_gateway.gateway:app",
        host=cfg.gateway["host"],
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
