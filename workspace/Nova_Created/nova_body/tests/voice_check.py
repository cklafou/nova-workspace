# Last updated: 2026-08-02 12:53:55
# voice_check tests: the flagger that reads my own words back to me.

CASES = [
    {"name": "invented number gets caught", "args": {"text": "I did eight checks tonight and they all passed."}, "expect_contains": "FLAGGED"},
    {"name": "grounded number is fine", "args": {"text": "Eight checks, reading the count from the log. They all passed."}, "expect_absent": "FLAGGED"},
    {"name": "performed praise with no fact", "args": {"text": "Great catch!"}, "expect_contains": "praise"},
    {"name": "earned praise is fine", "args": {"text": "Good catch, because you saw the off-by-one I'd written past three times."}, "expect_absent": "FLAGGED"},
    {"name": "over-explanation flagged", "args": {"text": "The file is there. It was created last night. The path resolves correctly. The permissions are fine. So it's definitely readable. That's why the error is somewhere else entirely, which is the important thing to know."}, "expect_contains": "sentences"},
    {"name": "a clean reply stays clean", "args": {"text": "My bad, seven not eight. The log has it."}, "expect_absent": "FLAGGED"},
]
