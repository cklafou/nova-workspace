# Last updated: 2026-07-23 21:29:42
CASES = [
    {"name": "answer with reasoning", "args": {"answer": "it's fine", "reasoning": "checked three things"},
     "expect_contains": ["HANDOFF", "it's fine", "checked three things", "[reasoning"]},
    {"name": "answer with no reasoning", "args": {"answer": "done"},
     "expect_absent": "[reasoning", "expect_contains": "done"},
    {"name": "blank answer is refused", "args": {"answer": ""},
     "expect_startswith": "ERROR"},
]
