# Last updated: 2026-07-23 18:51:35
# Run all reach_watcher cases from the design
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
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
    status = "PASS" if ok else "FAIL"
    print(f"{status} {name}: {r[:80]}")
print("\nAll four green." if all(run(d).startswith(e) for _,d,e in CASES) else "Something broke.")
