# Last updated: 2026-07-23 12:47:25
from nova_body.nova_senses.quiet_part_watcher import check_quiet_parts

CASES = [
    {"name": "reports something healthy when it's been used recently",
     "check": lambda run: "Checked" in run and len(run) > 0},
    {"name": "finds more than one part (has a body to look at)",
     "check": lambda run: "Checked 1" not in run},  # at least 10
    {"name": "does NOT flag a brand-new sense as neglected",
     "expect_absent": "QUIET sense/clock"},
    {"name": "reports QUIET for a sense that's been quiet longer than the threshold",
     "check": lambda run: "QUIET" in run and len(run) > 0},
    {"name": "returns nothing at all when every sense is healthy", 
     "expect_absent": "QUIET"},
]
