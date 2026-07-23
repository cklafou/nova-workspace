# Last updated: 2026-07-23 09:20:59

# Last updated: 2026-07-23 09:20:59
"""Tests for dir_shape_health tool."""
import os, sys, json, tempfile, shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta

TOOLS = str(Path(__file__).resolve().parent.parent / 'tools')
sys.path.insert(0, TOOLS)
from dir_shape_health import run, snapshot_save, snapshot_diff, _shape_dict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG = PROJECT_ROOT / 'nova_body' / 'tests' / '.test_logs'
LOG.mkdir(exist_ok=True)

def make_folder(path: Path, newest_days: int, oldest_days: int):
    path.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    (path / 'new.txt').write_text('hi')
    os.utime(path / 'new.txt', ((now - timedelta(days=newest_days)).timestamp(),) * 2)
    (path / 'old.txt').write_text('bye')
    os.utime(path / 'old.txt', ((now - timedelta(days=oldest_days)).timestamp(),) * 2)

CASES = [
    {"name": "nonexistent path returns error, not crash",
     "args": {"path": "no_such_folder_ever"},
     "expect_startswith": "Not a directory"},
    {"name": "stale folder flags old subfolders",
     "args": {"path": str(LOG / 'stale_test')},
     "pre": lambda: make_folder(LOG / 'stale_test', 60, 90),
     "expect_contains": "haven't moved in >30 days", "clean": LOG / 'stale_test'},
    {"name": "recent work shows where activity lives",
     "args": {"path": str(LOG / 'activity_test')},
     "pre": lambda: make_folder(LOG / 'activity_test', 0, 10),
     "expect_contains": "Recent work in", "clean": LOG / 'activity_test'},
    {"name": "healthy folder reports no rot",
     "args": {"path": str(PROJECT_ROOT)},
     "expect_contains": "No rot, nothing sitting too long"},
    {"name": "snapshot_save creates a log file",
     "fn": "snapshot_save",
     "args": {"path": str(PROJECT_ROOT), "log_file": str(LOG / 'snap.jsonl')},
     "expect_contains": "Saved snapshot"},
    {"name": "snapshot_diff needs two snapshots", "pre": lambda: (open(LOG/'snap.jsonl','w').close(), snapshot_save(str(PROJECT_ROOT), str(LOG/'snap.jsonl'))),
     "fn": "snapshot_diff",
     "args": {"log_file": str(LOG / 'snap.jsonl')},
     "expect_contains": "Need two to compare", "clean": LOG / 'snap.jsonl'},
]

def check(run):
    lf = str(LOG / 'diff_check.jsonl')
    snapshot_save(str(PROJECT_ROOT), lf)
    snapshot_save(str(PROJECT_ROOT), lf)
    result = run.snapshot_diff(lf)
    if "No changes" not in result and result.startswith("ERROR"):
        return ["diff returned error instead of no-changes: " + result]
    return []

# ---- runner ----
import importlib.util
spec = importlib.util.spec_from_file_location('dir_shape_health', TOOLS + '/dir_shape_health.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

passed = failed = 0
for c in CASES:
    if 'pre' in c: c['pre']()
    fn_name = c.get('fn', 'run')
    try:
        result = getattr(mod, fn_name)(**c['args'])
    except Exception as e:
        result = f"ERROR: {e}"
    ok = True
    for k, v in {'expect_contains': lambda r, v: v in r,
                 'expect_startswith': lambda r, v: r.startswith(v)}.items():
        if k in c and not v(result, c[k]):
            print(f'  [FAIL] {c["name"]}: expected {k}={c[k]!r}, got {result!r}')
            ok = False
    if ok:
        print(f'  [PASS] {c["name"]}')
        passed += 1
    else:
        failed += 1
    # cleanup: remove temp folders/files this test created
    clean = c.get('clean')
    if clean:
        cp = Path(clean)
        try:
            if cp.is_dir(): shutil.rmtree(cp)
            elif cp.exists(): cp.unlink()
        except Exception as e:
            print(f'  [WARN] cleanup {clean}: {e}')
if 'check' in globals():
    errs = check(mod)
    if errs:
        for e in errs: print(f'  [FAIL] check: {e}'); failed += 1
    else:
        print('  [PASS] check (diff)')
        passed += 1
print(f'{passed} passed, {failed} failed.')

