# Last updated: 2026-08-02 03:16:36
CASES = [
    {"name": "two real nights", "args": {"before_date": "2026-08-01", "after_date": "2026-08-02"},
     "expect_startswith": None,
     "check": lambda run: ["returned nothing"] if not run or len(run) < 40 else []},
    {"name": "missing night reports the gap", "args": {"before_date": "2025-01-01", "after_date": "2025-01-02"},
     "expect_contains": "Nothing to look at"},
    {"name": "one side missing says so instead of guessing", "args": {"before_date": "2026-08-02", "after_date": "2025-01-01"},
     "expect_contains": "No record for 2025-01-01"},
]
