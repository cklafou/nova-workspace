# Last updated: 2026-07-23 10:24:53
"""Quiet-Part Watcher — find the parts of me that haven't been used in a while."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
SENSES_DIR = Path(__file__).resolve().parent.parent / "nova_body" / "senses"
TOOL_LOG = Path("logs/tool_calls.jsonl")

GRACE_DAYS = 7
QUIET_DAYS = 14


def _tool_names() -> list[str]:
    names: list[str] = []
    for d in (TOOLS_DIR, SENSES_DIR):
        if not d.is_dir():
            continue
        for p in d.glob("*.py"):
            if p.stem.startswith("_") or p.name.endswith("_test.py"):
                continue
            names.append(p.stem)
    return sorted(names)


def _last_seen(name: str) -> float | None:
    """Read the tool-call log for the most recent invocation of this tool. Returns days-ago or None."""
    if not TOOL_LOG.exists():
        return None
    now = datetime.now(timezone.utc)
    best = None
    for line in TOOL_LOG.read_text().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("tool") != name:
            continue
        ts_str = entry.get("ts", "")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
        days = (now - ts).total_seconds() / 86400
        if best is None or days < best:
            best = days
    return best


def _born(name: str) -> float | None:
    """How old this part is in days."""
    for d in (TOOLS_DIR, SENSES_DIR):
        f = d / f"{name}.py"
        if f.is_file():
            born_ts = datetime.fromtimestamp(f.stat().st_ctime, tz=timezone.utc)
            return (datetime.now(timezone.utc) - born_ts).total_seconds() / 86400
    return None


def run(threshold_days: int = QUIET_DAYS) -> str:
    now = datetime.now(timezone.utc)
    names = _tool_names()
    quiet: list[str] = []
    details: list[str] = []
    for name in names:
        born = _born(name)
        last = _last_seen(name)
        if born is not None and born < GRACE_DAYS:
            grace_note = " (new, still in grace)"
        else:
            grace_note = ""
        if last is None:
            age_str = "never called"
        else:
            age_str = f"{last:.0f}d ago"
        details.append(f"  {name}: {age_str}{grace_note}")
        if born is not None and born < GRACE_DAYS:
            continue
        if last is None or last > threshold_days:
            quiet.append(name)
    header = f"Body check ({len(names)} parts, {len(quiet)} quiet):"
    body = "\n".join(details)
    if quiet:
        return f"{header}\n{body}\nQuiet: {', '.join(quiet)}"
    return f"{header}\n{body}  Nothing's gone dark."


TOOL = {
    "name": "quiet_part_watcher",
    "description": "Which of my own senses hasn't been used in a while. Reads the tool-call log, not the journal.",
    "params": {"type": "object", "properties": {"threshold_days": {"type": "integer", "description": "Days before something counts as quiet (default 14)."}}, "required": []},
}
