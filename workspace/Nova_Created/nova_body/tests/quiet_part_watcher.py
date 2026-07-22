# Last updated: 2026-07-23 01:58:48
"""Tests for quiet_part_watcher."""
import importlib.util, sys
from pathlib import Path

TOOLS = str(Path(__file__).resolve().parent.parent / 'tools')
spec = importlib.util.spec_from_file_location('quiet_part_watcher', TOOLS + '/quiet_part_watcher.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

CASES = [
    {
        "name": "a tool used today shows as recently used",
        "args": {"threshold_days": 7},
        "expect_contains": "dir_shape_health",  # I used it this hour
    },
    {
        "name": "a new tool in grace period is NOT flagged as quiet",
        "args": {"threshold_days": 7},
        "expect_absent": "Quiet: stretch_reacher",  # never called but brand-new, should not be quiet
    },
    {
        "name": "the report lists all parts, not just the quiet ones",
        "args": {"threshold_days": 7},
        "check": lambda r: [] if ("Body check (14 parts" in r or "Body check (15 parts" in r) else [f"wrong part count: {r[:60]}"],
    },
]

passed = failed = 0
for c in CASES:
    result = mod.run(**c["args"])
    ok = True
    for k, v in {'expect_contains': lambda r, v: v in r,
                 'expect_absent': lambda r, v: v not in r}.items():
        if k in c and not v(result, c[k]):
            print(f'  [FAIL] {c["name"]}: expected {k}={c[k]!r}')
            print(f'         got: {result[:120]}')
            ok = False
    if "check" in c:
        errs = c["check"](result)
        if errs:
            for e in errs:
                print(f'  [FAIL] {c["name"]}: {e}')
            ok = False
    if ok:
        print(f'  [PASS] {c["name"]}')
        passed += 1
    else:
        failed += 1
print(f'{passed} passed, {failed} failed.')
