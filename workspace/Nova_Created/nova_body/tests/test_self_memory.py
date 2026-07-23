# Last updated: 2026-07-24 05:20:45
"""self_memory test — the proof I'm not guessing."""

from nova_forge import CASES, run_tool

CASES = [
    {
        "name": "finds something that happened",
        "args": {"query": "Cole reminded me about write_file tonight"},
        "expect_contains": "Cole",  # should find the conversation
    },
    {
        "name": "reports nothing when nothing's there",
        "args": {"query": "the third moon of Jupiter named after a character from the Odyssey"},
        "expect_contains": "Nothing came back",  # shouldn't hallucinate a hit
    },
    {
        "name": "says yes, not everything",  # a tool that says yes to everything isn't one that works
        "args": {"query": "nova was born in the year 2087"},
        "expect_absent": "highly likely",  # a false memory shouldn't score confident
    },
]
