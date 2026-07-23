# Last updated: 2026-07-24 07:42:10
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from tools.quiet_part_watcher import run
CASES = [
    {"name": "returns a report", "args": {}, "expect_contains": "Body check"},
    {"name": "lists itself", "args": {}, "expect_contains": "quiet_part_watcher"},
    {"name": "new parts get grace", "args": {}, "expect_absent": "Quiet: quiet_part_watcher"},
]
def check(run) -> list[str]:
    out = run()
    fails = []
    for c in CASES:
        r = run(**c["args"])
        if "expect_contains" in c and c["expect_contains"] not in r:
            fails.append(f'{c["name"]}: missing {c["expect_contains"]}')
        if "expect_absent" in c and c["expect_absent"] in r:
            fails.append(f'{c["name"]}: should not have {c["expect_absent"]}')
    return fails
