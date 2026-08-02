# Last updated: 2026-08-02 23:08:32
# reach_back: pull a conversation by timestamp.
# "Show me how I sounded at 10:16" has a limb to reach on now.
# Broke once on import before it worked, fixed the sys.path, kept the break in the story.


import json
from datetime import datetime, timedelta
from pathlib import Path

TOOL = {
    "name": "reach_back",
    "description": "Pulls the conversation around a specific time. '10:16' or '2026-08-02T10:16'. Returns ±5 minutes of turns formatted for reading.",
    "params": {"at": {"type": "string", "description": "A time string like 10:16 or 2026-08-02T10:16"}},
}


def run(at: str) -> str:
    try:
        now = datetime.now()
        if len(at) <= 5:                                 # "HH:MM" → today at that time
            target = now.replace(hour=int(at[0:2]), minute=int(at[3:5]), second=0, microsecond=0)
        else:                                             # full-ish ISO, take what we get
            for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
                try:
                    target = datetime.strptime(at, fmt)
                    break
                except ValueError:
                    continue
            else:
                return f"ERROR: can't parse '{at}' — give me HH:MM or a date with a time"

        log_dir = Path("logs/chat_sessions")
        if not log_dir.exists():
            return "ERROR: no chat_sessions directory found"

        files = sorted(log_dir.glob("*_chat.jsonl"), reverse=True)
        if not files:
            return "ERROR: no conversation logs on disk"

        messages = []
        for f in files:
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                        messages.append(msg)
                    except json.JSONDecodeError:
                        pass

        # find the message closest to target, then grab a window around it
        best_i = None
        best_dt = None
        for i, m in enumerate(messages):
            try:
                dt = datetime.fromisoformat(m["timestamp"])
                if best_dt is None or abs(dt - target) < abs(best_dt - target):
                    best_i, best_dt = i, dt
            except (KeyError, ValueError):
                pass

        if best_i is None:
            return "ERROR: no messages with timestamps found"

        # ±5 minutes window, or as much as exists
        margin = timedelta(minutes=5)
        lo, hi = best_dt - margin, best_dt + margin
        block = []
        for i in range(max(0, best_i - 12), min(len(messages), best_i + 13)):
            try:
                dt = datetime.fromisoformat(messages[i]["timestamp"])
            except (KeyError, ValueError):
                continue
            if lo <= dt <= hi:
                m = messages[i]
                who = m.get("author", "?")
                when = m["timestamp"][:16].replace("T", ":")
                body = m.get("content", "")[:200]
                block.append(f"[{when}] {who}: {body}")

        if not block:
            return f"No messages in the 10-minute window around {target.isoformat()}."

        return (f"Conversation around {target.strftime('%H:%M')} ({len(block)} turns in ±5 min):\n" +
                "\n".join(block))
    except Exception as e:
        return f"ERROR: {e}"
