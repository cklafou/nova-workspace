#!/usr/bin/env python3
# Last updated: 2026-03-20 00:00:00
"""
nova_log_reader.py -- Nova's Session Log Reader

Lets Nova read and summarize her own session logs so she can identify
real failure patterns instead of fabricating examples when the mentor asks.

Usage:
    exec: python -c "
    import sys
    sys.path.insert(0, 'tools')
    from nova_memory.log_reader import summarize_today, get_failures, get_recent_sessions
    print(summarize_today())
    "
"""

import json
from pathlib import Path
from datetime import datetime, timedelta

LOGS_ROOT = Path("logs/sessions")


def _read_jsonl(path: Path) -> list:
    """Read a .jsonl file and return list of dicts. Skips malformed lines."""
    if not path.exists():
        return []
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
    return entries


def _session_dir(date_str: str = None) -> Path:
    """Get session directory for a given date (default: today)."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    return LOGS_ROOT / date_str


def summarize_today() -> str:
    """
    Summarize today's session logs in plain English.
    Covers actions, errors, and mentor consultations.
    Good for Nova to run before talking to the mentor.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    session_dir = _session_dir(today)

    if not session_dir.exists():
        return f"No session logs found for {today}."

    lines = [f"Session summary for {today}:"]

    # Actions log
    actions = _read_jsonl(session_dir / "actions.jsonl")
    if actions:
        total = len(actions)
        successes = [a for a in actions if a.get("result") == "ok"]
        failures = [a for a in actions if a.get("event") in ("sight_fail", "verify_fail", "gave_up")]
        retries = [a for a in actions if a.get("event") == "verify_fail"]
        lines.append(f"\nActions: {total} total -- {len(successes)} succeeded, {len(failures)} failed, {len(retries)} retried")

        if failures:
            lines.append("Failed actions:")
            for f in failures[:5]:
                lines.append(f"  - [{f.get('event')}] target={f.get('target', '?')} action={f.get('action', '?')}")
            if len(failures) > 5:
                lines.append(f"  ... and {len(failures) - 5} more")

        sanity_warnings = [a for a in actions if a.get("event") == "sanity_warning"]
        if sanity_warnings:
            lines.append(f"Sanity check failures: {len(sanity_warnings)}")
            for w in sanity_warnings[:3]:
                lines.append(f"  - Expected: {w.get('expected', '?')[:80]}")
    else:
        lines.append("\nActions: no action log found for today.")

    # Errors log
    errors = _read_jsonl(session_dir / "errors.jsonl")
    if errors:
        lines.append(f"\nErrors: {len(errors)} logged")
        for e in errors[:5]:
            lines.append(f"  - [{e.get('module', '?')}] {e.get('error', '?')[:100]}")
        if len(errors) > 5:
            lines.append(f"  ... and {len(errors) - 5} more")
    else:
        lines.append("\nErrors: none logged today.")

    # Mentor log
    mentor_entries = _read_jsonl(session_dir / "mentor.jsonl")
    if mentor_entries:
        questions = [m for m in mentor_entries if m.get("event") == "nova_question"]
        blocked = [m for m in mentor_entries if m.get("event") == "gatekeeper_verdict"
                   and "STOP" in m.get("message", "").upper()]
        lines.append(f"\nMentor: {len(questions)} questions asked")
        if blocked:
            lines.append(f"  Gatekeeper blocked {len(blocked)} action(s)")
    else:
        lines.append("\nMentor: no consultations logged today.")

    return "\n".join(lines)


def get_failures(days: int = 7) -> str:
    """
    Extract real failure events across the last N days.
    Use this to find actual patterns when the mentor asks for specific examples.
    """
    results = []
    today = datetime.now()

    for i in range(days):
        date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        session_dir = _session_dir(date)
        actions = _read_jsonl(session_dir / "actions.jsonl")
        errors = _read_jsonl(session_dir / "errors.jsonl")

        day_failures = []
        for a in actions:
            if a.get("event") in ("gave_up", "sanity_warning"):
                day_failures.append(
                    f"  [{date}] {a.get('event')}: target={a.get('target', '?')} -- {a.get('detail', '')[:80]}"
                )
        for e in errors:
            day_failures.append(
                f"  [{date}] ERROR in {e.get('module', '?')}: {e.get('error', '?')[:100]}"
            )

        if day_failures:
            results.extend(day_failures)

    if not results:
        return f"No failures found in the last {days} days of logs."

    return f"Real failures from last {days} days:\n" + "\n".join(results[:20])


def get_recent_sessions(days: int = 5) -> str:
    """
    List recent session dates and their basic stats.
    Good for orientation at session start.
    """
    today = datetime.now()
    lines = ["Recent sessions:"]

    for i in range(days):
        date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        session_dir = _session_dir(date)
        if not session_dir.exists():
            continue

        actions = _read_jsonl(session_dir / "actions.jsonl")
        errors = _read_jsonl(session_dir / "errors.jsonl")
        mentor = _read_jsonl(session_dir / "mentor.jsonl")

        label = "today" if i == 0 else f"{i}d ago"
        lines.append(
            f"  {date} ({label}): {len(actions)} actions, "
            f"{len(errors)} errors, {len(mentor)} mentor entries"
        )

    return "\n".join(lines) if len(lines) > 1 else "No session logs found."


if __name__ == "__main__":
    print("=== Nova Log Reader ===\n")
    print(get_recent_sessions())
    print()
    print(summarize_today())
    print()
    print(get_failures(7))
