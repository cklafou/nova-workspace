# Last updated: 2026-08-02 12:35:35
CASES = [
    {"name": "finds real TODOs in this workspace", "args": {"path": "."}, "expect_contains": ".py:"},
    {"name": "returns nothing-found string when empty", "args": {"path": "Nova_Created/art"}, "expect_contains": "No TODO comments found"}
]
def check(run) -> list:
    failures = []
    for c in CASES:
        result = run(**c["args"])
        if c.get("expect_contains") not in result:
            failures.append(f'{c["name"]}: expected "{c["expect_contains"]}" in result')
    return failures
