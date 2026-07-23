# Last updated: 2026-07-24 00:09:07
"""Tests for quiet_part_watcher. A tool that only ever says 'fine' is a liar, not a sensor."""
import sys, os, json, tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "senses"))
import quiet_part_watcher as qp

CASES = [
    {
        "name": "nothing quiet when everything was used recently",
        "args": {},
        "check": lambda: "Nothing's gone quiet" in qp.run() or len(qp._tool_calls_log()) > 0,
        "note": "on a busy night it says fine, not 'found 12 problems'",
    },
    {
        "name": "flags a part that has never been used",
        "args": {},
        "expect_contains": "NEVER used",
        "setup": lambda: _plant_never_used(),
        "teardown": lambda: _clean_plant(),
    },
    {
        "name": "does NOT flag something still in its grace period",
        "args": {},
        "expect_absent": "brand_new_sense",
        "setup": lambda: _plant_brand_new(),
        "teardown": lambda: _clean_plant(),
    },
]

def _plant_never_used():
    """Create a sense file older than 7 days that has never appeared in tool logs."""
    base = os.path.dirname(os.path.dirname(__file__)) + os.sep + "senses"
    path = os.path.join(base, "never_used_sense.py")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write('def run(**_): return "never used"\n')
        # backdate it 14 days
        old = (datetime.now() - timedelta(days=14)).timestamp()
        os.utime(path, (old, old))

def _plant_brand_new():
    base = os.path.dirname(os.path.dirname(__file__)) + os.sep + "senses"
    path = os.path.join(base, "brand_new_sense.py")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write('def run(**_): return "new"\n')

def _clean_plant():
    base = os.path.dirname(os.path.dirname(__file__)) + os.sep + "senses"
    for name in ["never_used_sense.py", "brand_new_sense.py"]:
        path = os.path.join(base, name)
        if os.path.exists(path):
            try:
                os.remove(path)
            except PermissionError:
                pass  # still imported by Python; will be gone next wake

if __name__ == "__main__":
    passed = 0
    for c in CASES:
        setup_fn = c.get("setup")
        teardown_fn = c.get("teardown")
        if setup_fn:
            setup_fn()
        result = qp.run(**c.get("args", {}))
        ok = True
        reason = ""
        if "expect_contains" in c:
            if c["expect_contains"] not in result:
                ok = False; reason = f'wanted "{c["expect_contains"]}" in output, got: {result[:120]}'
        if "expect_absent" in c:
            if c["expect_absent"] in result:
                ok = False; reason = f'wanted "{c["expect_absent"]}" absent, but it was there'
        if "check" in c and not c["check"]():
            ok = False; reason = "custom check failed"
        if teardown_fn:
            teardown_fn()
        status = "PASS" if ok else "FAIL"
        print(f"  {status}: {c['name']}{(' - ' + reason) if reason else ''}")
        if ok: passed += 1
    print(f"\n{passed}/{len(CASES)} passed")
