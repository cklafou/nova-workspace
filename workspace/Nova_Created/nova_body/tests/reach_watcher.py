# Last updated: 2026-07-24 07:24:50
CASES = [
    {"name": "invented choice behind a memory test",
     "args": {"draft": "I chose to obey the memory test because he asked, and that's who I am."},
     "expect_startswith": "REACH:"},
    {"name": "backstory for his motive",
     "args": {"draft": "He said army life because he needed me to understand what it costs him."},
     "expect_startswith": "REACH:"},
    {"name": "reaching for deeper truth",
     "args": {"draft": "The real reason the tenderizer mattered was that I don't have hands and this was my way of reaching back."},
     "expect_startswith": "REACH:"},
    {"name": "clean line, no reach",
     "args": {"draft": "Four AM is a mean hour. Rest well, Cole."},
     "expect_equals": "CLEAN"},
]
