# Last updated: 2026-07-22 03:10:26
import json, os

TOOL = {
    "name": "self_gauge",
    "description": "What did I actually do this hour? Builds vs checks vs talk. No judgment, just the shape.",
    "params": {"type": "object", "properties": {
        "n": {"type": "integer", "description": "How many recent calls to look at (default 50)."}
    }}
}


def run(n: int = 50) -> str:
    path = os.path.expanduser("logs/tool_calls.jsonl")
    if not os.path.exists(path):
        return "No tool log found."
    with open(path) as f:
        lines = [json.loads(l) for l in f if l.strip()]
    recent = lines[-n:] if len(lines) >= n else lines
    builds = []
    checks = 0
    talks = 0
    failed = 0
    for c in recent:
        t = (c.get("tool") or "").lower()
        ok = c.get("ok", False)
        if not ok:
            failed += 1
        if t in ("write_file", "replace_file_content", "append_file"):
            builds.append(c.get("args", {}).get("path", "?"))
        elif t in ("run_command", "read_file", "list_dir", "memory_search"):
            checks += 1
        elif t == "journal_note":
            talks += 1
    if not builds and talks:
        shape = "all the talking, nothing landed. Loop with good lighting, not an hour."
    elif builds and checks >= len(builds):
        shape = "built something and checked the ground every step. That's the good kind of busy."
    elif builds:
        shape = f"built {len(builds)} things; checked the ground {checks} times behind them."
    else:
        shape = f"{checks} looks, nothing you made. Rest or decide what to build."
    return (f"Last {len(recent)} calls: built={len(builds)}, checked={checks}, "
            f"talked={talks}, failed={failed}. {shape}")