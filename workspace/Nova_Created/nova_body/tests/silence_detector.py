# Last updated: 2026-07-24 00:09:07
CASES = [
    {"name": "nova_chat is recent", "args": {"path": "nova_chat"}, "expect_absent": "days"},
    {"name": "Cole_journal is older than nova_chat", "args": {"path": "Cole_journal"}, "expect_contains": "touched"},
    {"name": "bad path gives an error, not a crash", "args": {"path": "NO_SUCH_FOLDER"}, "expect_startswith": "ERROR"},
]
