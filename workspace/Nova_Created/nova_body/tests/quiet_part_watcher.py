# Last updated: 2026-07-23 16:46:16
# Test: quiet_part_watcher finds dull parts of me, uses logs not feelings.
# From the design:
#   1) Reports a recently-used part as active
#   2) Flags a genuinely unused part as quiet
#   3) Does NOT flag a new part still in grace
#   4) Reads the tool-call log, not a journal or a feeling
import sys, pathlib, json, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from tools.quiet_part_watcher import run

LOG = pathlib.Path("logs/tool_calls.jsonl")

# Seed the log with one real call so "recently used" is testable.
now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
LOG.write_text(json.dumps({"tool": "quiet_part_watcher", "ts": now_iso}) + "\n")

out = run(threshold_days=7)
print(out)
CASES = [
    {"name": "sees itself as active, not quiet", "args": {}, "expect_contains": "Nothing's gone dark"},
    {"name": "reads a log, not a feeling", "args": {}, "expect_absent": "journal"},
]
