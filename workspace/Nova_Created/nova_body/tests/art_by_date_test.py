# Last updated: 2026-07-23 12:30:45
CASES = [
    {"name": "finds recent images", "args": {"week": 2}, "expect_contains": "image"},
    {"name": "returns newest first", "args": {"week": 4}, "expect_contains": ".png"},
    {"name": "rejects zero weeks", "args": {"week": 0}, "expect_startswith": "ERROR"},
    {"name": "rejects non-number", "args": {"week": "abc"}, "expect_startswith": "ERROR"},
]
