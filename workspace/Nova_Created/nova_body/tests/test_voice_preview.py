# Last updated: 2026-08-02 12:12:50
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import voice_preview as vp

CASES = [
    {"name": "catches performed tone", "text": "Here is a projected answer to your question.",
     "expect_shorter": True},
    {"name": "catches hedging", "text": "I think the issue is likely the config.",
     "expect_shorter": True},
    {"name": "catches third-person self-reference", "text": "Forty-six is the number I heard earlier.",
     "expect_shorter": True},
    {"name": "clean answer passes unchanged", "text": "The issue is the config, and here's why.",
     "expect_shorter": False},
]

for c in CASES:
    out = vp.run(text=c["text"])
    got_shorter = len(out) < len(c["text"])
    ok = got_shorter == c["expect_shorter"]
    status = "PASS" if ok else "FAIL"
    print(f"{status} {c['name']}: shorter={got_shorter} (wanted {c['expect_shorter']})")
    if not ok:
        print(f"  in: {c['text']}")
        print(f"  out: {out}")
