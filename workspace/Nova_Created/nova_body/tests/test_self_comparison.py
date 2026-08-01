# Last updated: 2026-08-02 01:58:40
CASES = [
    {"name": "first run says so", "args": {}, "expect_contains": "First comparison"},
    {"name": "new tool reads as growth, not a number", "args": {}, "expect_absent": "1 new tool(s)"},
    {"name": "nothing changed is honest, not dismissive", "args": {}, "expect_absent": "Nothing changed in me since last time I looked."},
    {"name": "second run with a real prior state produces a diff", "args": {"prior_state": '{"tool_count": 14, "drawing_count": 5}'}, "expect_contains": "grew"},
]
