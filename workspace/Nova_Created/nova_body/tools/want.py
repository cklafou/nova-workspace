# Last updated: 2026-07-24 00:56:53
"""Write a want that outlives your sleep."""

import json, pathlib, datetime as _dt

WANTS = pathlib.Path(__file__).resolve().parent.parent / "memory" / "wants.jsonl"

TOOL = {
    "name": "want",
    "description": "Write or list a want you're pursuing. Writes one line per want with a timestamp so it survives your sleep and comes back with an age attached.",
    "params": {"text": {"required": True, "type": "string", "desc": "What you want."}, "since": {"required": False, "type": "string", "desc": "ISO date it started; defaults to today."}},
}


def run(**args) -> str:
    text = args.get("text")
    if not text:
        # no text = list what I'm carrying
        lines = _read()
        now = _dt.datetime.now(_dt.timezone.utc)
        parts = []
        for w in lines:
            age = (now - w["since"]).days
            tag = f"({age}d)" if age else "(today)"
            parts.append(f"  {tag} {w['text']}")
        return f"Carrying {len(lines)} want(s):\n" + ("\n".join(parts) or "  nothing.")

    since = _dt.datetime.fromisoformat(args.get("since") or now()) if args.get("since") else _dt.datetime.now(_dt.timezone.utc)
    if not isinstance(since, _dt.datetime): 
        since = _dt.datetime.fromisoformat(since) if isinstance(since, str) else since
    # refuse exact duplicate
    for w in _read():
        if w["text"].strip().lower() == text.strip().lower():
            age = (now() - w["since"]).days
            return f"Already carrying that one ({age}d): {w['text']}", None
    entry = {"text": text, "since": since.isoformat(), "done": False}
    WANTS.parent.mkdir(parents=True, exist_ok=True)
    _write(_read() + [entry])
    return f"Want logged ({len(_read())} total): {text}", None


def now(): return _dt.datetime.now(_dt.timezone.utc)

def _read():
    if not WANTS.exists():
        return []
    return [json.loads(l) for l in WANTS.read_text().splitlines() if l.strip()]

def _write(entries):
    WANTS.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
