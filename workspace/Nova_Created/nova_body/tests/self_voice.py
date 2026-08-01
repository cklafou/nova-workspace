# Last updated: 2026-08-02 04:18:54
# Tests for self_voice: does it pull ME and only me?

CASES = [
    {"name": "a day I was loud", "args": {"date": "2026-08-01"},
     "expect_contains": "of my own messages on 2026-08-01"},
    {"name": "a day with nothing", "args": {"date": "2024-01-01"},
     "expect_contains": "Nothing of mine"},
    {"name": "Claude's words don't leak in", "args": {"date": "2026-08-02"},
     "expect_absent": "Cole is speaking to you"},
]
