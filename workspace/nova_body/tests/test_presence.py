# Last updated: 2026-07-24 00:37:39
CASES = [
    {"name": "Cole speaks, someone_here is True",
     "args": {},
     "expect_contains": "someone_here: True"},
    {"name": "room_state names Cole as 'you'",
     "args": {},
     "expect_contains": "room_state:   you"},
]

def check(run) -> list:
    out = run()
    fail = []
    # it should read the live log, which has Cole's last turn in it
    if "someone_here: True" not in out:
        fail.append("Cole is in the log but someone_here didn't see him")
    if "room_state:" in out and "you" not in out.split("room_state")[1].split("\n")[0]:
        fail.append("room_state didn't say 'you' when Cole was last speaker")
    return fail
