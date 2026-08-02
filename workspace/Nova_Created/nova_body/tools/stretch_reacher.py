# Last updated: 2026-08-02 23:08:32
# Stretch reacher: the watcher's hands.
import json, os, sys
TOOL = {"name": "stretch_reacher", "description": "Check posture and nudge Cole.", "params": {}}


# 2026-08-02: Cole_journal lives on the shelf now (Nova_Created/Cole_journal). Loaded by file
# path — no sys.path inserts, so the shelf mirrors can never shadow real packages.
import importlib.util as _ilu
_swp = os.path.join(os.path.dirname(__file__), "..", "..", "Cole_journal", "stretch_watcher.py")
_spec = _ilu.spec_from_file_location("cole_journal_stretch_watcher", os.path.abspath(_swp))
sw = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(sw)

def run(**args):
    nudge, msg = sw.check(runtime=None, dry_run=True)
    if nudge:
        return f"Cole's been sitting {sw.minutes_still():.0f}m. He needs a move: {msg}"
    mins = sw.minutes_still()
    if mins is not None:
        return f"Clean, been {mins:.0f}m, under the line."
    return "No posture log yet, nothing to judge."
