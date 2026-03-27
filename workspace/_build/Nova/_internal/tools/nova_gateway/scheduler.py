"""
nova_gateway/scheduler.py
===========================
APScheduler-based cron replacement for OpenClaw's scheduler.

What this does (plain English):
  OpenClaw has a built-in scheduler that fires Nova's "System Health Check"
  every 30 minutes. This module does the same thing using APScheduler,
  a Python library designed exactly for this.

  When the health check fires, it calls the agent_loop with a special
  "cron" trigger so Nova knows it's a scheduled check (not a user message).
  Nova reads HEARTBEAT.md to know what to do during a health check.

Requirements:
  pip install apscheduler

To add more scheduled jobs in the future, just add another entry to
nova_gateway.json under "cron" and register it in _register_jobs() below.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, TYPE_CHECKING

from .config import cfg

if TYPE_CHECKING:
    from .tool_executor import ToolExecutor

log = logging.getLogger(__name__)

# ── Try importing APScheduler ────────────────────────────────────────────────
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    log.warning(
        "APScheduler not installed. Cron jobs disabled. "
        "Install with: pip install apscheduler"
    )


# ── Scheduler wrapper ─────────────────────────────────────────────────────────

class NovaScheduler:
    """
    Wraps APScheduler and registers Nova's cron jobs.

    Usage (called by gateway.py):
        scheduler = NovaScheduler(executor)
        scheduler.start()
        # ... runs in background ...
        scheduler.stop()
    """

    def __init__(self, executor: "ToolExecutor"):
        self.executor  = executor
        self._scheduler: Optional["AsyncIOScheduler"] = None
        self._nova_status_summary: str = ""

    def update_nova_status(self, summary: str) -> None:
        """Called by gateway.py's polling loop to keep status fresh."""
        self._nova_status_summary = summary

    def start(self) -> None:
        """Start the scheduler. Non-blocking — runs jobs in the background."""
        if not APSCHEDULER_AVAILABLE:
            log.error("APScheduler not available — cron jobs disabled.")
            return

        self._scheduler = AsyncIOScheduler()
        self._register_jobs()
        self._scheduler.start()
        log.info("Scheduler started.")

    def stop(self) -> None:
        """Shut down the scheduler cleanly."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            log.info("Scheduler stopped.")

    # ── Job registration ─────────────────────────────────────────────────────

    def _register_jobs(self) -> None:
        """Register all cron jobs from config."""
        health_cfg = cfg.cron.get("health_check", {})
        if health_cfg.get("enabled", True):
            interval_min = int(health_cfg.get("interval_min", 30))
            self._scheduler.add_job(
                self._run_health_check,
                trigger=IntervalTrigger(minutes=interval_min),
                id="health_check",
                name="System Health Check",
                replace_existing=True,
                misfire_grace_time=120,   # run up to 2 min late if system was busy
            )
            log.info("Registered health check every %d minutes.", interval_min)

        # Future jobs can be added here:
        # self._scheduler.add_job(self._run_daily_summary, ...)

    # ── Job handlers ─────────────────────────────────────────────────────────

    async def _run_health_check(self) -> None:
        """
        Fire the health check agent run.
        This is exactly what OpenClaw's "System Health Check" cron job does.

        APScheduler runs this job in a background task. If this coroutine raises,
        APScheduler logs the exception but continues running the scheduler.
        Errors are logged and not re-raised to prevent scheduler disruption.
        """
        health_cfg = cfg.cron.get("health_check", {})
        message    = health_cfg.get(
            "message",
            "Perform system health check — verify all components are functioning properly.",
        )

        log.info("Cron: firing health check")

        try:
            from .agent_loop import run_agent
            result = await run_agent(
                text=message,
                source="cron",
                executor=self.executor,
                nova_status_summary=self._nova_status_summary,
            )
            if result.ok:
                log.info(
                    "Health check complete: %d tool calls, %.1fs",
                    result.tool_calls_made, result.duration_s,
                )
            else:
                log.error("Health check agent error: %s", result.error)
        except Exception as e:
            # APScheduler will log this exception. Do not re-raise to keep scheduler alive.
            log.error("Health check crashed: %s", e, exc_info=True)

    async def trigger_health_check_now(self) -> None:
        """Manually trigger a health check immediately (used by gateway HTTP API)."""
        log.info("Manual health check triggered via API")
        await self._run_health_check()


# ── Standalone runner ─────────────────────────────────────────────────────────

def create_scheduler(executor: "ToolExecutor") -> "NovaScheduler":
    """
    Create a NovaScheduler instance. Called by gateway.py.
    Call .start() to begin running jobs in the background.
    """
    return NovaScheduler(executor)


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    if not APSCHEDULER_AVAILABLE:
        print("APScheduler not installed. Run: pip install apscheduler")
    else:
        from .tool_executor import ToolExecutor

        async def test():
            executor  = ToolExecutor()
            scheduler = NovaScheduler(executor)
            scheduler.start()
            print("Scheduler running. Triggering health check immediately...")
            await scheduler.trigger_health_check_now()
            scheduler.stop()

        asyncio.run(test())
