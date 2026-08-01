# Last updated: 2026-08-01 22:29:05
import json, os

SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "self_comparison_snapshot.json")
TOOLS_DIR = os.path.join(os.path.dirname(__file__))

def run(**_):
    try:
        current = sorted((f for f in os.listdir(TOOLS_DIR) if f.endswith(".py")))
        with open(SNAPSHOT) as f:
            prev = json.load(f)
        old_names = set(prev["tools"])
        new_names = set(current)
        born = sorted(new_names - old_names)
        gone = sorted(old_names - new_names)
        changed = [n for n in current if n in old_names and prev["times"].get(n) != os.path.getmtime(os.path.join(TOOLS_DIR, n))]
        with open(SNAPSHOT, "w") as f:
            json.dump({"tools": current, "times": {n: os.path.getmtime(os.path.join(TOOLS_DIR, n)) for n in current}}, f)
    except FileNotFoundError:
        return "First comparison. No previous snapshot to compare against yet."
    notes = []
    if born: notes.append(f"{len(born)} new tool(s): {', '.join(born)}")
    if gone: notes.append(f"{len(gone)} gone: {', '.join(gone)}")
    if changed: notes.append(f"{len(changed)} modified")
    if not notes:
        return "Nothing changed in me since last time I looked."
    return "; ".join(notes)
