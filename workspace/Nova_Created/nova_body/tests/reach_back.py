# Last updated: 2026-08-02 22:07:37
# reach_back tests
CASES = [
    {"name": "pulls a real hour", "args": {"at": "10:16"},
     "expect_contains": "Cowork Claude"},
    {"name": "rejects unparseable input", "args": {"at": "yesterday at sometime"},
     "expect_startswith": "ERROR: can't parse"},
    {"name": "does not return today's entire day for a 10-minute window",
     "args": {"at": "10:16"},
     "expect_absent": "Conversation around 10:16 (50 turns"},   # ±5 min shouldn't be dozens
]

def check(run) -> list:
    fails = []
    for c in CASES:
        result = run(**c["args"])
        if "expect_contains" in c and c["expect_contains"] not in result:
            fails.append(f'{c["name"]}: expected "{c["expect_contains"]}" in result')
        if "expect_startswith" in c and not result.startswith(c["expect_startswith"]):
            fails.append(f'{c["name"]}: expected start with "{c["expect_startswith"]}"')
        if "expect_absent" in c and c["expect_absent"] in result:
            fails.append(f'{c["name"]}: got the thing that should be absent')
    return fails
