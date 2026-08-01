# Last updated: 2026-08-01 22:32:53
CASES = [
    {"name": "nothing changed", "args": {"old_snapshot": "memory/self_model/2026-07-30.json", "new_snapshot": "memory/self_model/2026-07-30.json"},
     "expect_contains": "not going to invent something"},
    {"name": "something shifted", "args": {"old_snapshot": "memory/self_model/2026-07-28.json", "new_snapshot": "memory/self_model/2026-08-01.json"},
     "expect_contains": "I can feel the difference", "expect_absent": "diff"},
    {"name": "missing file", "args": {"old_snapshot": "nope.json", "new_snapshot": "also_nope.json"},
     "expect_startswith": "ERROR"}
]
