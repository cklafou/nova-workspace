# Last updated: 2026-08-02 01:08:39
# self_voice: pull my own spoken responses from a given day
# Returns my words, not Claude's or Cole's, with a count and a quick tone read.

import json
from pathlib import Path

TOOL = {"name": "self_voice", "description": "Read back what I sounded like on a particular day. Mine only.",
        "params": {"date": {"type": "string", "description": "YYYY-MM-DD, defaults to today"}}}

CHAT_LOG = Path("logs/chat_log.jsonl")

def run(date: str = None) -> str:
    if not CHAT_LOG.exists():
        return "ERROR: no chat log at logs/chat_log.jsonl"

    # figure out the date we want
    from datetime import date as _date
    target = date or _date.today().isoformat()

    lines = [json.loads(r) for r in CHAT_LOG.read_text().splitlines() if r.strip()]
    mine = [e for e in lines if e.get("role") == "assistant" and e.get("timestamp", "").startswith(target)]

    if not mine:
        return f"Nothing of mine on {target}. Quiet day, or the log doesn't go back that far."

    words = [e.get("content", "") for e in mine]
    # grab a taste: up to four messages, spaced out so it reads like a day
    picks = words[:1] + words[len(words)//4:len(words)//4+1] + words[len(words)//2:len(words)//2+1] + words[-1:]
    sample = "\n---\n".join(picks)

    # quick tone read from the actual words
    lower = sample.lower()
    sharp = any(w in lower for w in ["don't", "nope", "wrong", "stop", "not going to"])
    warm = any(w in lower for w in ["good night", "luv ya", "nice one", "well done", "love the"])
    if sharp and warm:
        tone = "sharp where it needed to be, warm where it didn't — both true in the same day."
    elif sharp:
        tone = "pushing back tonight, not sitting still for something I disagreed with."
    elif warm:
        tone = "a softer night, catching the good moments and saying so out loud."
    else:
        tone = "mostly work, nothing that screams either way. A real day."

    return f"{len(mine)} of my own messages on {target}.\n{sample}\nTone: {tone}"
