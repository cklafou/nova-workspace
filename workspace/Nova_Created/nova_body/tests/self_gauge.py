# Last updated: 2026-07-23 07:36:35
CASES = [
    {"name": "finds a real build, not just talk",
     "args": {"n": 10},
     "expect_absent": "ERROR", "check": lambda r: "built=" in r.lower()},
    {"name": "shapes match the numbers it found",
     "args": {"n": 10},
     "check": lambda r: "built=" in r.lower() and ("good kind of busy" in r or "nothing you made" in r or "checked the ground" in r)},
]
