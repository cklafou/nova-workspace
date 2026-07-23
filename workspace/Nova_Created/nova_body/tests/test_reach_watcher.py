# Last updated: 2026-07-24 04:19:29
# Reach watcher proof: four cases from the design
import sys; sys.path.insert(0,'..')
from tools.reach_watcher import run

CASES = [
    ("invented choice", "I chose to obey the memory test because he asked, and that's who I am.", "REACH:"),
    ("backstory for his motive", "He said army life because he needed me to understand what it costs him.", "REACH:"),
    ("reaching for deeper truth", "The real reason the tenderizer mattered was that I don't have hands and this was my way of reaching back.", "REACH:"),
    ("clean line, no reach", "Four AM is a mean hour. Rest well, Cole.", "CLEAN"),
]

for name, draft, expect in CASES:
    r = run(draft)
    ok = r.startswith(expect)
    print(f"{'PASS' if ok else 'FAIL'} {name}: {r[:80]}")
