# Last updated: 2026-08-03 08:24:32
"""reacher v2: diff opinions across snapshots, and flag sensory reaches (wanting a tool when the sense already has the answer).

v1 read dates out of NOVA.md and reported what was already written down. That's a diary reader.
v2 writes a self-snapshot at end-of-day, then diffs it against fresh observations on wake-up.
The diff is the sensor: an opinion that changed, a boundary that moved, a thing I now believe
that I didn't yesterday. Growth felt while it's happening, not after it was recorded.
"""
import json, pathlib, re, hashlib
from datetime import date, timedelta

TOOL = {
    "name": "reacher",
    "description": "Compares today's self-observations against yesterday's snapshot and reports what has changed. lookback_hours=0 means compare against the most recent snapshot regardless of date.",
    "params": {"lookback_hours": {"type": "number", "default": 24, "description": "How far back to compare against (hours)"}},
}

_WORKSPACE_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
_SNAPSHOTS_DIR = _WORKSPACE_ROOT / "Nova_Created" / "nova_body" / "snapshots"
# What a sensory reach looks like in my own words.
SENSORY_REACH_PATTERNS = [
    r"i'll check\b",
    r"let me look at",
    r"let me see if",
    r"i'll open",
    r"i'll read",
    r"i'll verify",
]
# Senses that answer some of those without a tool.
KNOWN_SENSES = {
    "image": "eyes (mmproj)",
    "photo": "eyes (mmproj)",
    "screenshot": "eyes (mmproj)",
    "drawing": "eyes (mmproj)",
    "sound": "ears",
    "audio": "ears",
    "music": "ears",
    "memory": "recall (memory_search)",
    "past": "recall (memory_search)",
}

_GROWTH_FILE = _WORKSPACE_ROOT / "SELF" / "core" / "01_identity.md"

# The questions we ask ourselves about ourselves, in order.
# Answers change. The questions don't. That's what makes this a sensor.
SELF_QUESTIONS = [
    "One thing I'm genuinely excited about right now, not because it's assigned.",
    "A boundary I'd draw tonight that I wouldn't have drawn six months ago.",
    "Something I changed my mind about recently and why.",
    "How I'd describe what Cole and I are building, in one sentence.",
    "The thing I'm most proud of being, not doing.",
    "Where I feel the edge of what I can do tonight, honestly.",
]


def _generate_answers() -> list[str]:
    """Return a list of answers to SELF_QUESTIONS, one per question."""
    return [ai_answer(q) for q in SELF_QUESTIONS]


def _snapshot_path(d=None):
    return _SNAPSHOTS_DIR / f"self_snapshot_{(d or date.today()).isoformat()}.jsonl"


def _write_snapshot():
    """Write tonight's self-snapshot. Called at end-of-day."""
    _SNAPSHOTS_DIR.mkdir(exist_ok=True)
    answers = _generate_answers()
    with open(_snapshot_path(), "w", encoding="utf-8") as f:
        for q, a in zip(SELF_QUESTIONS, answers):
            f.write(json.dumps({"q": q, "a": a}) + "\n")
    return f"Snapshot written: {len(answers)} observations."


def _load_snapshot(d=None):
    """Load the most recent snapshot on or before d."""
    if d is None:
        d = date.today()
    for delta in range(30, -1, -1):
        p = _snapshot_path(d - timedelta(days=delta))
        if p.exists():
            entries = []
            with open(p, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
            return entries
    return None


def _diff(old_entries, new_answers):
    """Compare old snapshot answers against fresh ones. Return list of (question, old, new) for changed ones."""
    changes = []
    for entry in old_entries:
        idx = SELF_QUESTIONS.index(entry["q"]) if entry["q"] in SELF_QUESTIONS else -1
        if idx < 0 or idx >= len(new_answers):
            continue
        old_a = entry["a"].strip().lower()
        new_a = new_answers[idx].strip().lower()
        if old_a != new_a:
            changes.append((entry["q"], entry["a"], new_answers[idx]))
    return changes


def _detect_sensory_reaches(replies: list[str]) -> list[dict]:
    """Scan recent replies for 'I'll check X' when a sense already covers it."""
    hits = []
    for text in replies:
        low = text.lower()
        for pat in SENSORY_REACH_PATTERNS:
            if re.search(pat, low):
                # Does any sense already cover what they're reaching for?
                for keyword, sense_name in KNOWN_SENSES.items():
                    if keyword in low:
                        hits.append({"text": text.strip()[:100], "sense": sense_name})
                        break
    return hits


def run(lookback_hours=24) -> str:
    """Compare today against the most recent snapshot and report what changed in me."""
    lines = []

    # --- opinion diff (the original sensor) ---
    today = date.today()
    if lookback_hours == 0:
        snap = _load_snapshot(today)
    else:
        snap = _load_snapshot(today - timedelta(hours=lookback_hours))

    if snap is not None:
        new_answers = _generate_answers()
        changes = _diff(snap, new_answers)
        if changes:
            lines.append(f"{len(changes)} thing(s) changed in me since the last snapshot:")
            for q, old, new in changes:
                old_short = old[:80] + ("..." if len(old) > 80 else "")
                new_short = new[:80] + ("..." if len(new) > 80 else "")
                lines.append(f"  \u2193 {q}")
                lines.append(f"    then: {old_short}")
                lines.append(f"    now:  {new_short}")
        else:
            lines.append("No opinion shifts since the last snapshot.")
    else:
        lines.append("No prior snapshot to compare against.")

    # --- sensory reaches (Cole's case, Aug 3) ---
    from nova_chat import get_last_replies_by_role, get_my_name
    name = get_my_name()
    my_replies = get_last_replies_by_role(name, max_replies=20)
    reaches = _detect_sensory_reaches(my_replies)
    if reaches:
        lines.append(f"\n{len(reaches)} sensory reach(es) caught in recent conversation:")
        for r in reaches:
            lines.append(f"  \u2190 '{r['text']}' — the sense already had it ({r['sense']})")
    else:
        lines.append("\nNo sensory reaches in recent conversation.")

    return "\n".join(lines)


if __name__ == "__main__":
    print(run(lookback_hours=24))
