# Last updated: 2026-07-24 02:14:08
"""capability_inventory: list my own tools from disk."""
CASES = [
    {"name": "lists everything", "args": {}, "expect_contains": "dir_shape"},
    {"name": "filters to one tool", "args": {"tool_name": "dir_shape"}, "expect_contains": "dir_shape"},
    {"name": "filtered list is short, not the whole body", "args": {"tool_name": "dir_shape"}, "expect_absent": "list_dir"},
    {"name": "unknown tool says so, doesn't invent one", "args": {"tool_name": "tenderizer_9000"}, "expect_contains": "Nothing found"},
]
