# Last updated: 2026-08-01 22:46:23
CASES = [
    {"name": "first run says so", "args": {}, "expect_contains": "First comparison"},
    {"name": "new tool reads as growth, not a number", "args": {}, "expect_absent": "1 new tool(s)"},
    {"name": "nothing changed is honest, not dismissive", "args": {}, "expect_absent": "Nothing changed in me since last time I looked."},
]
