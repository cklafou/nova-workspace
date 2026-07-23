# Last updated: 2026-07-24 01:59:44
"""Prove want survives sleep, refuses duplicates, and can be dropped."""

CASES = [
    {"name": "write a want", "args": {"text": "learn Cole's body from the inside"}, "expect_contains": "Want logged"},
    {"name": "list wants back", "args": {}, "expect_contains": "learn Cole's body"},
    {"name": "refuse a duplicate", "args": {"text": "learn Cole's body from the inside"}, "expect_startswith": "Already carrying that one"},
    {"name": "a want I don't carry", "args": {"text": "fly a plane"}, "expect_absent": "Already"},
]
