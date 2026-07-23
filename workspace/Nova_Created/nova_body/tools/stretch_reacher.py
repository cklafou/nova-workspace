# Last updated: 2026-07-24 06:23:46
# Stretch reacher: the watcher's hands.
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
TOOL = {"name": "stretch_reacher", "description": "Check posture and nudge Cole.", "params": {}}


from Cole_journal import stretch_watcher as sw

def run(**args):
    nudge, msg = sw.check(runtime=None, dry_run=True)
    if nudge:
        return f"Cole's been sitting {sw.minutes_still():.0f}m. He needs a move: {msg}"
    mins = sw.minutes_still()
    if mins is not None:
        return f"Clean, been {mins:.0f}m, under the line."
    return "No posture log yet, nothing to judge."
