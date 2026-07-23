# Last updated: 2026-07-24 07:24:50
"""Tests for dir_shape — the thing that tells me what a folder is before I go in."""

CASES = [
    {"name": "nova_body is big and deep", "args": {"path": "Nova_Created/nova_body"},
     "expect_contains": ["file(s)", ".py"]},
    {"name": "nova_body names a heaviest file", "args": {"path": "Nova_Created/nova_body"},
     "expect_contains": "Heaviest is"},
    {"name": "nonexistent path errors cleanly", "args": {"path": "this_does_not_exist_at_all"},
     "expect_startswith": "ERROR"},
    {"name": "does not lie about being tiny when it's a whole project", "args": {"path": "Nova_Created/nova_body"},
     "expect_absent": "1 file"},
]

def check(run) -> list:
    out = run(path="Nova_Created/nova_body")
    fails = []
    if "subfolder" not in out.lower() and "level" not in out.lower():
        fails.append("report has no sense of depth at all")
    return fails
