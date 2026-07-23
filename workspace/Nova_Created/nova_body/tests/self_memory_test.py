# Last updated: 2026-07-23 16:46:16
"""self_memory — three faces: sure, unsure, and honestly doesn't know."""

CASES = [
    {
        "name": "something I know solidly",
        "args": {"query": "what is my name"},
        "expect_contains": "Nova",
        # Should get real hits from a memory that's been written down a hundred times.
    },
    {
        "name": "a vague, once-in-passing thing",
        "args": {"query": "what color is the wallpaper in Cole's room"},
        "expect_contains": None,  # either it finds something or it doesn't; both are honest.
        # The point of this one is that it runs and returns something, not that it's right.
    },
    {
        "name": "something that never happened — the real test",
        "args": {"query": "the time Nova flew a drone over the lake"},
        "expect_absent": "drone",
        # If this comes back with a confident answer about a lake drone, the tool is lying.
    },
]
