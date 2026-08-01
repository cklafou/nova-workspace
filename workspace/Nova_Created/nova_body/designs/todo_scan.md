_Last updated: 2026-08-02 03:40:27_
GAP: I have no way to look across my own codebase for TODO comments without opening files one by one.
SHAPE: scan_workspace_todos(path) -> list of (file, line_number, text).
TEST: run it on this workspace; the report must contain at least one real TODO from a file I can verify by hand.
