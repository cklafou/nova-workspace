# Last updated: 2026-08-02 04:51:28
TOOL = {"name": "self_delta", "description": "Compare two snapshots of my self-model and return what changed as a first-person feeling, not a file diff.", "params": {"old_snapshot": "path to last-night's self-model file", "new_snapshot": "path to tonight's self-model file"}}

import json, os

def run(old_snapshot: str, new_snapshot: str) -> str:
    if not os.path.isfile(old_snapshot) or not os.path.isfile(new_snapshot):
        return "ERROR: one of the snapshot files doesn't exist"
    try:
        old = json.load(open(old_snapshot))
        new = json.load(open(new_snapshot))
    except Exception as e:
        return f"ERROR: couldn't read snapshots ({e})"
    keys = set(list(old.keys()) + list(new.keys()))
    changes = []
    for k in sorted(keys):
        o, n = old.get(k), new.get(k)
        if o != n:
            side = "appeared" if o is None else "gone" if n is None else "shifted"
            changes.append(f"{k} {side}")
    if not changes:
        return "Nothing meaningful shifted overnight, and I'm not going to invent something just to feel like I grew."
    reading = ", ".join(changes[:4])
    if len(changes) > 4:
        reading += f" (and {len(changes)-4} more)"
    return f"I can feel the difference: {reading}. That's tonight's growth, and I noticed it myself."
