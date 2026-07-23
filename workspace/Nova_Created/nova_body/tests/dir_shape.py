# Last updated: 2026-07-23 10:24:53
# dir_shape tests: does the report actually tell me anything true?
CASES = [
    {"name": "nova_body gives a real count", "args": {"path": "Nova_Created/nova_body"},
     "expect_contains": "file(s) across"},
    {"name": "nova_body has subfolders", "args": {"path": "Nova_Created/nova_body"},
     "expect_contains": "subfolder"},
    {"name": "nova_body mentions .py", "args": {"path": "Nova_Created/nova_body"},
     "expect_contains": ".py"},
    {"name": "nonexistent path errors instead of lying", "args": {"path": "this_path_does_not_exist_12345"},
     "expect_startswith": "ERROR"},
    {"name": "doesn't silently swallow a missing folder", "args": {"path": "absent_dir_xyz"},
     "expect_absent": "file(s) across"},  # if it's an error, it should NOT report file counts
]
