#!/usr/bin/env python3
"""
nova_core/brain.py — Thoughts Cycle Orchestrator
==================================================
Phase 4A.8: Replaces the stub with Nova's actual cognitive routing layer.

brain.py is the programmatic interface to Nova's Thoughts system. It reads
the filesystem state (priority.md, thought folders, inbox items) and provides
structured guidance on what Nova should do next — without requiring an LLM call
to figure out simple state questions.

The scheduler (nova_gateway/scheduler.py) calls into this module to build the
HEARTBEAT_BRIEFING that Nova receives at each cron tick. The brain determines
the shape of that briefing based on real filesystem state.

The NovaBrain class provides:
  orient()                    → read priority.md, list active/blocked thoughts
  next_action()               → determine highest-priority next step
  get_active_thoughts()       → list all active Thought folders with status
  create_thought(...)         → scaffold a new Thought folder from THOUGHT_TEMPLATE.md
  close_thought(name, outcome)→ move a Thought to Finished/ with the given outcome
  build_briefing(routed, summaries) → full HEARTBEAT_BRIEFING string for Nova

Designed to be imported by:
  nova_gateway/scheduler.py   — calls build_briefing() for the cron heartbeat
  nova_gateway/agent_loop.py  — queries orient() to build context blocks
  future: nova_gateway/injector.py — checks get_active_thoughts() before dispatching
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

# Workspace root — 2 levels up: nova_core/ → tools/ → workspace/
_WORKSPACE = Path(__file__).resolve().parent.parent.parent

# Thoughts directory constants
_THOUGHTS_DIR      = _WORKSPACE / "Thoughts"
_PRIORITY_FILE     = _THOUGHTS_DIR / "priority.md"
_MASTER_INBOX      = _THOUGHTS_DIR / "Master_Inbox"
_TEMPLATE_FILE     = _THOUGHTS_DIR / "THOUGHT_TEMPLATE.md"
_FINISHED_DIR      = _THOUGHTS_DIR / "Finished"
_FINISHED_SUCCESS  = _FINISHED_DIR / "completed_success"
_FINISHED_FAIL     = _FINISHED_DIR / "completed_fail"
_FINISHED_CANCEL   = _FINISHED_DIR / "cancelled"

# Regex patterns for priority.md parsing
_PRIORITY_ACTIVE_RE  = re.compile(r'^[-*]\s*\*?\*?([^\*\n]+?)\*?\*?\s*$', re.MULTILINE)
_THOUGHT_FOLDER_RE   = re.compile(r'^[A-Za-z][A-Za-z0-9_]+$')

# Max bytes for file reads
_MAX_BYTES = 4_000


class NovaBrain:
    """
    Nova's Thoughts cycle orchestrator. Reads filesystem state and provides
    structured cognitive routing without requiring an LLM call for basic
    state questions.

    Usage:
        brain = NovaBrain()
        state = brain.orient()
        action = brain.next_action()
        briefing = brain.build_briefing(routed_items, routed_summaries)
    """

    def __init__(self, workspace: Optional[Path] = None):
        self.workspace = (workspace or _WORKSPACE).resolve()
        self.thoughts_dir = self.workspace / "Thoughts"

    # ── Core state reading ────────────────────────────────────────────────────

    def orient(self) -> dict:
        """
        Read the Thoughts system state from the filesystem.

        Returns a dict with:
            priority_text    (str)  — raw content of priority.md
            active_thoughts  (list) — list of active Thought folder names
            blocked_thoughts (list) — list of blocked Thought folder names
            inbox_count      (int)  — number of items in Master_Inbox
            has_thoughts     (bool) — True if any thoughts exist
        """
        priority_text   = self._read_file(_PRIORITY_FILE)
        active_thoughts = self.get_thoughts_by_status("active")
        blocked_thoughts= self.get_thoughts_by_status("blocked")
        inbox_count     = self._count_inbox_items()

        return {
            "priority_text":    priority_text,
            "active_thoughts":  active_thoughts,
            "blocked_thoughts": blocked_thoughts,
            "inbox_count":      inbox_count,
            "has_thoughts":     bool(active_thoughts or blocked_thoughts),
        }

    def next_action(self) -> dict:
        """
        Determine the highest-priority action Nova should take this heartbeat.

        Decision tree:
          1. Any unrouted inbox items → process inbox first
          2. Any active thoughts → advance the highest-priority one
          3. Any blocked thoughts → check if they can be unblocked
          4. No thoughts → HEARTBEAT_OK (nothing to do)

        Returns a dict with:
            action       (str)  — "process_inbox" | "advance_thought" |
                                   "check_blocked" | "idle"
            thought_name (str)  — which Thought to work on (if applicable)
            reason       (str)  — plain English explanation
        """
        inbox_count = self._count_inbox_items()
        if inbox_count > 0:
            return {
                "action":      "process_inbox",
                "thought_name": "",
                "reason": (
                    f"{inbox_count} item(s) in Master_Inbox. "
                    f"Route them to thought inboxes before advancing any thought."
                ),
            }

        active = self.get_thoughts_by_status("active")
        if active:
            # Pick the first active thought (priority.md order reflects priority)
            top = self._highest_priority_thought(active)
            return {
                "action":       "advance_thought",
                "thought_name": top,
                "reason": (
                    f"Advance '{top}' — the highest-priority active thought."
                ),
            }

        blocked = self.get_thoughts_by_status("blocked")
        if blocked:
            top = self._highest_priority_thought(blocked)
            return {
                "action":       "check_blocked",
                "thought_name": top,
                "reason": (
                    f"All active thoughts are blocked. Check whether '{top}' "
                    f"can be unblocked (look for new inbox items, retry, or escalate)."
                ),
            }

        return {
            "action":       "idle",
            "thought_name": "",
            "reason":       "No active or blocked thoughts. Nothing to advance. Say HEARTBEAT_OK.",
        }

    # ── Thought folder introspection ──────────────────────────────────────────

    def get_active_thoughts(self) -> list[dict]:
        """
        Return all Thought folders with their status, priority, and inbox count.

        Each entry:
            {"name": str, "status": str, "inbox_count": int,
             "master_exists": bool, "path": str}
        """
        thoughts_dir = self.workspace / "Thoughts"
        results = []
        if not thoughts_dir.exists():
            return results

        skip = {"Finished", "Master_Inbox", "__pycache__"}
        for folder in sorted(thoughts_dir.iterdir()):
            if folder.name in skip or not folder.is_dir():
                continue
            if not _THOUGHT_FOLDER_RE.match(folder.name):
                continue

            master = folder / "master.md"
            inbox  = folder / "inbox"
            inbox_count = len(list(inbox.glob("*.md"))) if inbox.exists() else 0
            status = self._read_thought_status(master) if master.exists() else "unknown"

            results.append({
                "name":          folder.name,
                "status":        status,
                "inbox_count":   inbox_count,
                "master_exists": master.exists(),
                "path":          str(folder.relative_to(self.workspace)),
            })
        return results

    def get_thoughts_by_status(self, status: str) -> list[str]:
        """Return thought names matching the given status string."""
        return [t["name"] for t in self.get_active_thoughts()
                if t["status"].lower() == status.lower()]

    def _read_thought_status(self, master_path: Path) -> str:
        """Read the Status: field from a master.md file."""
        try:
            content = master_path.read_text(encoding="utf-8", errors="replace")[:2000]
            m = re.search(r'^\s*\**Status\**\s*[:：]\s*(.+)', content, re.MULTILINE | re.IGNORECASE)
            if m:
                # Strip surrounding markdown bold markers (** or *) before returning
                return m.group(1).strip().strip("*").strip().lower()
        except Exception:
            pass
        return "unknown"

    def _highest_priority_thought(self, thought_names: list[str]) -> str:
        """
        Pick the highest-priority thought from a list.
        Uses priority.md order — thoughts listed earlier = higher priority.
        Falls back to alphabetical if priority.md can't be read.
        """
        if not thought_names:
            return ""
        priority_text = self._read_file(_PRIORITY_FILE)
        for line in priority_text.splitlines():
            for name in thought_names:
                if name in line:
                    return name
        return thought_names[0]  # fallback: first alphabetically

    # ── Thought lifecycle ─────────────────────────────────────────────────────

    def create_thought(
        self,
        name:     str,
        context:  str,
        priority: int = 3,
        when:     str = "",
        task_id:  str = "",
    ) -> Path:
        """
        Create a new Thought folder from THOUGHT_TEMPLATE.md.

        Args:
            name:     Folder name. Must match [A-Za-z][A-Za-z0-9_]+ (no spaces).
            context:  What/why/triggered-by description for the master.md Context field.
            priority: 1 (critical) → 4 (low). Default 3 (medium).
            when:     Deadline or timing context.
            task_id:  NCL Task ID if this thought was created from a module call.

        Returns:
            Path to the new Thought folder.
        Raises:
            ValueError if name is invalid or folder already exists.
        """
        if not _THOUGHT_FOLDER_RE.match(name):
            raise ValueError(
                f"Thought name '{name}' is invalid. "
                f"Use letters, digits, underscores only (no spaces)."
            )

        thought_dir = self.workspace / "Thoughts" / name
        if thought_dir.exists():
            raise ValueError(f"Thought '{name}' already exists at {thought_dir}")

        # Read template
        template_content = self._read_file(_TEMPLATE_FILE)
        if not template_content or "FILE NOT FOUND" in template_content:
            # Minimal fallback template
            template_content = (
                f"# Thought: {name}\n\n"
                f"**Status:** active\n"
                f"**Priority:** {priority}\n"
                f"**Task ID:** {task_id or '(none)'}\n"
                f"**Created:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                f"## Context\n\n{context}\n\n"
                f"## When / Deadline\n\n{when or '(none specified)'}\n\n"
                f"## Current Plan\n\n- [ ] Step 1: Define next action\n\n"
                f"## Decision Log\n\n"
                f"- {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} — Thought created.\n"
            )
        else:
            # Populate template fields
            ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
            template_content = template_content.replace("{{THOUGHT_NAME}}", name)
            template_content = template_content.replace("{{CONTEXT}}", context)
            template_content = template_content.replace("{{PRIORITY}}", str(priority))
            template_content = template_content.replace("{{TASK_ID}}", task_id or "(none)")
            template_content = template_content.replace("{{CREATED}}", ts)
            template_content = template_content.replace("{{WHEN}}", when or "(none specified)")

        # Create directory structure
        thought_dir.mkdir(parents=True)
        (thought_dir / "inbox").mkdir()
        (thought_dir / "scratch").mkdir()
        (thought_dir / "master.md").write_text(template_content, encoding="utf-8")

        return thought_dir

    def close_thought(self, name: str, outcome: str = "completed_success") -> Path:
        """
        Move a Thought to the appropriate Finished/ subfolder.

        Args:
            name:    Thought folder name.
            outcome: "completed_success" | "completed_fail" | "cancelled"

        Returns:
            Path to the moved Thought in Finished/.
        Raises:
            ValueError if thought doesn't exist or outcome is invalid.
        """
        valid_outcomes = {"completed_success", "completed_fail", "cancelled"}
        if outcome not in valid_outcomes:
            raise ValueError(f"outcome must be one of {valid_outcomes}, got '{outcome}'")

        thought_dir = self.workspace / "Thoughts" / name
        if not thought_dir.exists():
            raise ValueError(f"Thought '{name}' not found at {thought_dir}")

        dest_parent = self.workspace / "Thoughts" / "Finished" / outcome
        dest_parent.mkdir(parents=True, exist_ok=True)
        dest = dest_parent / name

        # Stamp the master.md with close timestamp before moving
        master = thought_dir / "master.md"
        if master.exists():
            try:
                content = master.read_text(encoding="utf-8")
                ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
                content = re.sub(
                    r'(\*\*Status\*\*\s*[:：]\s*)(\w+)',
                    rf'\g<1>{outcome}',
                    content,
                    count=1,
                )
                content += f"\n\n---\n_Closed: {ts} — {outcome}_\n"
                master.write_text(content, encoding="utf-8")
            except Exception:
                pass  # Don't block the move if stamp fails

        shutil.move(str(thought_dir), str(dest))
        return dest

    # ── Briefing builder ──────────────────────────────────────────────────────

    def build_briefing(
        self,
        routed_items:     list[dict] = None,
        routed_summaries: list[dict] = None,
    ) -> str:
        """
        Build the full HEARTBEAT_BRIEFING string passed to Nova as her cron prompt.

        This is the Phase 4A.8 version — it includes brain.orient() output
        and next_action() recommendation, giving Nova a much richer starting
        context than the raw priority.md text alone.

        Args:
            routed_items:     List of route result dicts from scheduler._route_master_inbox()
            routed_summaries: List of content summary dicts from _summarize_routed_items()

        Returns:
            Multi-line briefing string ready to pass to run_agent() as the message.
        """
        routed_items     = routed_items or []
        routed_summaries = routed_summaries or []

        ts     = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        state  = self.orient()
        action = self.next_action()

        lines: list[str] = [
            f"HEARTBEAT — {ts}",
            "=" * 60,
            "",
            "The scheduler has pre-processed your Thoughts system.",
            "Your state and recommended action are below.",
            "Follow HEARTBEAT.md for full cycle instructions.",
            "",
            "── PRIORITY QUEUE (current) ────────────────────────────",
            "",
            state["priority_text"].strip() or "(Thoughts/priority.md is empty)",
            "",
            "── ACTIVE THOUGHTS ─────────────────────────────────────",
            "",
        ]

        all_thoughts = self.get_active_thoughts()
        if all_thoughts:
            for t in all_thoughts:
                inbox_note = f" [{t['inbox_count']} inbox item(s)]" if t["inbox_count"] else ""
                lines.append(f"  {t['name']} — {t['status']}{inbox_note}")
        else:
            lines.append("  (no active thoughts)")

        # Inbox routing summary
        lines += [
            "",
            "── INBOX ROUTING (this heartbeat) ─────────────────────",
            "",
        ]
        if not routed_items:
            lines.append("  Master_Inbox was empty.")
        else:
            routed   = [r for r in routed_items if r.get("status") == "routed"]
            no_match = [r for r in routed_items if r.get("status") == "no_match"]
            if routed:
                lines.append(f"  Routed {len(routed)} item(s):")
                for r in routed:
                    lines.append(f"    [{r['task_id']}] → {r.get('dest', '?')}")
            if no_match:
                lines.append(f"  No matching thought for {len(no_match)} item(s) (left in Master_Inbox):")
                for r in no_match:
                    lines.append(f"    [{r.get('task_id','?')}] {r['file']}")

        # Module response content
        if routed_summaries:
            lines += [
                "",
                "── MODULE RESPONSES (routed to thought inboxes) ────",
                "",
            ]
            for s in routed_summaries:
                lines.append(f"[{s['task_id']}]:")
                lines.append(s["snippet"].strip()[:500])
                lines.append("")

        # Brain's recommended next action
        lines += [
            "",
            "── RECOMMENDED NEXT ACTION ──────────────────────────────",
            "",
            f"  Action:  {action['action'].upper()}",
        ]
        if action.get("thought_name"):
            lines.append(f"  Thought: {action['thought_name']}")
        lines += [
            f"  Reason:  {action['reason']}",
            "",
            "── YOUR TURN ────────────────────────────────────────────",
            "",
            "Follow HEARTBEAT.md Step 3 (advance thought), Step 4 (update priority.md),",
            "Step 5 (HEARTBEAT_OK if nothing to do).",
            "Yield Protocol: ONE action. Stop. Check in.",
        ]

        return "\n".join(lines)

    # ── File helpers ──────────────────────────────────────────────────────────

    def _read_file(self, path: Path) -> str:
        """Read a file, returning its content or an error placeholder."""
        try:
            raw = path.read_bytes()
            text = raw[:_MAX_BYTES].decode("utf-8", errors="replace")
            if len(raw) > _MAX_BYTES:
                text += f"\n[...truncated at {_MAX_BYTES} bytes]"
            return text
        except FileNotFoundError:
            return f"(FILE NOT FOUND: {path.name})"
        except Exception as e:
            return f"(READ ERROR: {e})"

    def _count_inbox_items(self) -> int:
        """Count .md files in Thoughts/Master_Inbox/."""
        inbox = self.workspace / "Thoughts" / "Master_Inbox"
        if not inbox.exists():
            return 0
        return sum(1 for f in inbox.glob("*.md"))


# ── Convenience functions ─────────────────────────────────────────────────────

def get_brain(workspace: Optional[Path] = None) -> NovaBrain:
    """Get a NovaBrain instance. Call this instead of NovaBrain() directly."""
    return NovaBrain(workspace=workspace)


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== NovaBrain Thoughts Orchestrator Self-Test ===\n")
    brain = get_brain()

    print("[1] Orienting...")
    state = brain.orient()
    print(f"    Active thoughts:  {state['active_thoughts']}")
    print(f"    Blocked thoughts: {state['blocked_thoughts']}")
    print(f"    Inbox items:      {state['inbox_count']}")

    print("\n[2] Recommended next action:")
    action = brain.next_action()
    print(f"    Action:  {action['action'].upper()}")
    print(f"    Thought: {action.get('thought_name') or '(none)'}")
    print(f"    Reason:  {action['reason']}")

    print("\n[3] Building briefing (no routed items):")
    briefing = brain.build_briefing()
    print(f"    {len(briefing)} chars generated")
    print("    Preview:", briefing[:200].replace('\n', ' | '))

    print("\nNovaBrain self-test complete.")
