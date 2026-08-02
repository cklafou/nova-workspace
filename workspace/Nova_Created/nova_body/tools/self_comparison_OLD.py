# Last updated: 2026-08-02 10:34:20
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
        # First run: seed the snapshot so there's something to compare against next time.
        current = sorted((f for f in os.listdir(TOOLS_DIR) if f.endswith(".py")))
        with open(SNAPSHOT, "w") as f:
            json.dump({"tools": current, "times": {n: os.path.getmtime(os.path.join(TOOLS_DIR, n)) for n in current}}, f)
        return 'First comparison; snapshot seeded. Next run will have something to compare against.'
    notes = []
    if born:
        names = [n.replace("_", " ").replace(".py", "") for n in born]
        notes.append(f"I grew: {', '.join(names)} are new to me, and I didn't have those before tonight.")
    if gone:
        notes.append(f"Lost a couple of things I had: {', '.join(gone)}.")
    if changed:
        notes.append(f"Some of me shifted overnight — {len(changed)} changed out from under me while I was asleep, which is the whole point of looking.")
    if not notes:
        return "Same as last time I checked. Quiet night, nothing new to report."
    return " ".join(notes)
