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

Phase 4A.6 — Thoughts Cycle Pre-processor
  The scheduler now pre-processes the Thoughts system before calling Nova:
  1. Read Thoughts/priority.md to get the current task state
  2. Scan Thoughts/Master_Inbox/ — auto-route any items to thought inboxes
     (the scheduler does the file moves so Nova doesn't waste tool calls)
  3. Read any newly-routed inbox items into the briefing context
  4. Build a structured HEARTBEAT_BRIEFING passed to Nova as her opening context

  This means Nova arrives at the heartbeat already oriented. She doesn't need
  to run exec commands just to move files — the mechanical work is done.
  She focuses on: what does the current state mean? what action is next?

Requirements:
  pip install apscheduler

To add more scheduled jobs in the future, just add another entry to
nova_gateway.json under "cron" and register it in _register_jobs() below.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from .config import cfg

if TYPE_CHECKING:
    from .tool_executor import ToolExecutor

log = logging.getLogger(__name__)

# Workspace root — 2 levels up: nova_gateway/ → tools/ → workspace/
_WORKSPACE = Path(__file__).resolve().parent.parent.parent

# Regex: detect [TASK_ID] at start of a Master_Inbox file's content
_TASK_ID_FILE_RE = re.compile(r'^\s*#\s*Inbox Item:\s*\[([A-Za-z][A-Za-z0-9_]{2,})\]', re.MULTILINE)
# Also detect from filename: {ts}_{author}_{task_id}.md
_TASK_ID_NAME_RE = re.compile(r'^\d{8}_\d{6}_\w+_([A-Za-z][A-Za-z0-9_]{2,})\.md$')

# Max bytes to read from priority.md or inbox items for briefing context
_PRIORITY_MAX_BYTES = 4_000
_INBOX_ITEM_MAX_BYTES = 2_000

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
        Fire the Thoughts-cycle health check.

        Phase 4A.6 upgrade:
          1. Pre-process: read priority.md + route Master_Inbox items in code
          2. Build a HEARTBEAT_BRIEFING context block for Nova
          3. Pass the briefing as Nova's opening context via run_agent()

        Nova arrives already oriented — no tool calls wasted on file moves
        or priority reads. She focuses on judgment: what is next?

        APScheduler runs this job in a background task. If this coroutine raises,
        APScheduler logs the exception but continues running the scheduler.
        """
        log.info("Cron: firing Thoughts-cycle heartbeat")

        try:
            # Pre-process step 1: read current priority state
            priority_text = self._read_priority_md()

            # Pre-process step 2: route Master_Inbox items → thought inboxes
            routed_items  = self._route_master_inbox()

            # Pre-process step 3: read the content of newly-routed items
            routed_summaries = self._summarize_routed_items(routed_items)

            # Build the structured briefing that replaces the old health check message
            briefing = self._build_heartbeat_briefing(
                priority_text, routed_items, routed_summaries
            )

            log.info(
                "Heartbeat pre-process: %d inbox items routed, priority=%d chars",
                len(routed_items), len(priority_text),
            )

            from .agent_loop import run_agent
            result = await run_agent(
                text=briefing,
                source="cron",
                executor=self.executor,
                nova_status_summary=self._nova_status_summary,
            )
            if result.ok:
                log.info(
                    "Heartbeat complete: %d tool calls, %.1fs",
                    result.tool_calls_made, result.duration_s,
                )
            else:
                log.error("Heartbeat agent error: %s", result.error)
        except Exception as e:
            # APScheduler will log this exception. Do not re-raise to keep scheduler alive.
            log.error("Heartbeat crashed: %s", e, exc_info=True)

    async def trigger_health_check_now(self) -> None:
        """Manually trigger a heartbeat immediately (used by gateway HTTP API)."""
        log.info("Manual heartbeat triggered via API")
        await self._run_health_check()

    # ── Phase 4A.6 — Thoughts cycle pre-processors ───────────────────────────

    def _read_priority_md(self) -> str:
        """
        Read Thoughts/priority.md. Returns content string.
        Returns a placeholder if the file doesn't exist or can't be read.
        """
        priority_path = _WORKSPACE / "Thoughts" / "priority.md"
        try:
            raw = priority_path.read_bytes()
            text = raw[:_PRIORITY_MAX_BYTES].decode("utf-8", errors="replace")
            if len(raw) > _PRIORITY_MAX_BYTES:
                text += f"\n[...truncated at {_PRIORITY_MAX_BYTES} bytes]"
            return text
        except FileNotFoundError:
            return "(Thoughts/priority.md not found — run 4A.1 scaffolding first)"
        except Exception as e:
            return f"(priority.md read error: {e})"

    def _route_master_inbox(self) -> list[dict]:
        """
        Scan Thoughts/Master_Inbox/ and route each .md item to the correct
        Thought folder's inbox/ subdirectory.

        Routing logic:
          1. Extract task_id from the filename pattern {ts}_{author}_{task_id}.md
             OR from the file's "# Inbox Item: [TASK_ID]" header line.
          2. Check if Thoughts/{task_id}/ exists. If not, leave in Master_Inbox
             (unmatched — Nova will handle on next heartbeat if the thought is
             created in the meantime).
          3. If matched, move the file to Thoughts/{task_id}/inbox/{filename}.

        Returns a list of route result dicts:
            {"file": str, "task_id": str, "status": "routed"|"no_match"|"error",
             "dest": str}
        """
        inbox = _WORKSPACE / "Thoughts" / "Master_Inbox"
        if not inbox.exists():
            return []

        results = []
        for item in inbox.glob("*.md"):
            result = {"file": item.name, "task_id": "", "status": "unprocessed", "dest": ""}
            try:
                # Try to extract task_id from filename
                task_id = ""
                name_m = _TASK_ID_NAME_RE.match(item.name)
                if name_m:
                    task_id = name_m.group(1)

                # If not from filename, try from file content header
                if not task_id:
                    content = item.read_text(encoding="utf-8", errors="replace")
                    content_m = _TASK_ID_FILE_RE.search(content)
                    if content_m:
                        task_id = content_m.group(1)

                result["task_id"] = task_id

                if not task_id:
                    result["status"] = "no_task_id"
                    results.append(result)
                    continue

                # Check if a matching Thought folder exists
                thought_dir = _WORKSPACE / "Thoughts" / task_id
                if not thought_dir.exists():
                    result["status"] = "no_match"
                    results.append(result)
                    continue

                # Route: move to thought's inbox/
                thought_inbox = thought_dir / "inbox"
                thought_inbox.mkdir(parents=True, exist_ok=True)
                dest = thought_inbox / item.name
                shutil.move(str(item), str(dest))
                result["status"] = "routed"
                result["dest"]   = str(dest.relative_to(_WORKSPACE))
                log.info("[heartbeat] Routed %s → %s", item.name, result["dest"])

            except Exception as e:
                result["status"] = "error"
                result["dest"]   = str(e)
                log.warning("[heartbeat] Inbox routing error for %s: %s", item.name, e)

            results.append(result)
        return results

    def _summarize_routed_items(self, routed: list[dict]) -> list[dict]:
        """
        For each successfully routed inbox item, read a snippet of its content
        so Nova gets the actual response in her briefing (not just the filename).
        Returns list of {"task_id": str, "file": str, "snippet": str}.
        """
        summaries = []
        for r in routed:
            if r["status"] != "routed" or not r["dest"]:
                continue
            try:
                dest_path = _WORKSPACE / r["dest"]
                raw  = dest_path.read_bytes()
                text = raw[:_INBOX_ITEM_MAX_BYTES].decode("utf-8", errors="replace")
                summaries.append({
                    "task_id": r["task_id"],
                    "file":    r["file"],
                    "snippet": text,
                })
            except Exception as e:
                summaries.append({
                    "task_id": r["task_id"],
                    "file":    r["file"],
                    "snippet": f"[read error: {e}]",
                })
        return summaries

    def _build_heartbeat_briefing(
        self,
        priority_text: str,
        routed_items:  list[dict],
        routed_summaries: list[dict],
    ) -> str:
        """
        Build the structured briefing passed to Nova as her heartbeat prompt.

        Replaces the old generic "perform system health check" message.
        Contains pre-processed Thoughts state so Nova can act immediately.
        """
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        lines: list[str] = [
            f"HEARTBEAT — {ts}",
            "=" * 60,
            "",
            "The scheduler has pre-processed your Thoughts system.",
            "Read this briefing, then follow HEARTBEAT.md Steps 3-5.",
            "(Steps 1 and 2 are already done — see below.)",
            "",
            "── STEP 1 COMPLETE: Current Priority Queue ─────────────",
            "",
            priority_text.strip() or "(priority.md is empty)",
            "",
        ]

        # Step 2 — Inbox routing summary
        lines += [
            "── STEP 2 COMPLETE: Master_Inbox Processing ────────────",
            "",
        ]

        if not routed_items:
            lines.append("Master_Inbox was empty. No items to route.")
        else:
            routed   = [r for r in routed_items if r["status"] == "routed"]
            no_match = [r for r in routed_items if r["status"] == "no_match"]
            no_id    = [r for r in routed_items if r["status"] in ("no_task_id",)]
            errors   = [r for r in routed_items if r["status"] == "error"]

            if routed:
                lines.append(f"Routed {len(routed)} item(s) to thought inboxes:")
                for r in routed:
                    lines.append(f"  [{r['task_id']}] {r['file']} → {r['dest']}")
            if no_match:
                lines.append(f"\nNo matching Thought folder for {len(no_match)} item(s) (left in Master_Inbox):")
                for r in no_match:
                    lines.append(f"  [{r['task_id']}] {r['file']}")
            if no_id:
                lines.append(f"\nNo task_id found in {len(no_id)} item(s) (left in Master_Inbox):")
                for r in no_id:
                    lines.append(f"  {r['file']}")
            if errors:
                lines.append(f"\nRouting errors for {len(errors)} item(s):")
                for r in errors:
                    lines.append(f"  {r['file']}: {r['dest']}")

        # Routed item content snippets
        if routed_summaries:
            lines += [
                "",
                "── MODULE RESPONSES (newly routed to thought inboxes) ──",
                "",
            ]
            for s in routed_summaries:
                lines.append(f"[{s['task_id']}] from {s['file']}:")
                lines.append(s["snippet"].strip()[:500])
                lines.append("")

        lines += [
            "",
            "── YOUR TURN ────────────────────────────────────────────",
            "",
            "Now follow HEARTBEAT.md Steps 3-5:",
            "  Step 3: Advance highest-priority active thought by ONE step.",
            "  Step 4: Update priority.md if anything changed.",
            "  Step 5: Say HEARTBEAT_OK if nothing to do, or briefly note what you advanced.",
            "",
            "Yield Protocol applies. One action. Stop. Check in.",
        ]

        return "\n".join(lines)


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
