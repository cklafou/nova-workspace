# Last updated: 2026-07-21 12:58:18
"""RETENTION — the thing that stops logs/ growing forever.

WHY (2026-07-20, Cole: "take logs")
    Nothing in this project has ever rotated a log. Findings from the audit:
      - logs/nova_launcher.log reached 5.6 MB / 52,436 lines spanning a full week
      - logs/llama/ accumulated a file per day, 12 MB
      - logs/backups/sessions/ was at 30 zips and climbing
      - generation_trace.jsonl and tool_calls.jsonl grow without bound
    The 07-02 passover already warned "launcher log accumulates across days — grep errors by
    TODAY's date". That is a workaround for a missing policy, written down instead of fixed.

WHAT IT IS NOT
    It is not a purge. `logs/sessions/` is HER — read by nova_logs/logger.py,
    nova_memory/log_reader.py, server.py and nova_sync/backup.py. I came within one command
    of treating it as stale duplication of chat_sessions/ before checking who reads it. It is
    explicitly excluded here and must stay that way.

THE RULE THIS OBEYS
    JANITORIAL.md: **never delete — quarantine.** Old logs are gzipped in place first (a
    week of llama logs compresses to almost nothing), and only when a category is still over
    its cap does anything MOVE, and then to _admin/Trash/, never to /dev/null. Two of her
    thought logs were destroyed by a careless move loop on 07-14; that is the standing reason
    this file is careful.

WIRED TO BOOT
    Called from NovaLauncher on startup. Deliberately not a daemon and not a cron: the audit
    queue and the journal both failed as "someone will run it eventually", and boot is the one
    moment guaranteed to happen. Rotation is cheap and idempotent, so running it every start
    costs nothing.
"""
from __future__ import annotations

import gzip
import os
import pathlib
import shutil
import time

_HERE = pathlib.Path(__file__).resolve()
_WS = pathlib.Path(os.environ.get("NOVA_WORKSPACE", str(_HERE.parent.parent.parent)))
_LOGS = _WS / "logs"
_QUARANTINE = _WS / "_admin" / "Trash" / "log_rotation"

# NEVER touched. Hers, or actively load-bearing.
_UNTOUCHABLE = {"sessions", "chat_sessions", "runtime", "events"}

# (subpath, glob, gzip_after_days, keep_at_most, budget_bytes)
#
# ── CAP ON BYTES, NOT ON FILE COUNT (2026-07-20) ────────────────────────────────────────
# The first version capped launcher/ at 10 files. The dry run showed it would quarantine ~90
# boot records — to reclaim nothing, because the whole directory is 212 KB. Two months of
# diagnostic history destroyed for no space saved, which is the opposite of the trade.
#
# So: gzip is the primary tool (a text log compresses ~90%), and the count cap only engages
# when a directory is ALSO over its byte budget. A small, old, compressed directory is not a
# problem and gets left alone. Only genuinely large ones get trimmed, oldest first.
_POLICY = [
    ("llama",            "*.log",        2,  10,  20_000_000),
    ("llama",            "*.jsonl",      2,  10,  20_000_000),
    ("launcher",         "*",            3, 200,  20_000_000),
    ("comfy",            "*",            3,  60,  10_000_000),
    ("backups/sessions", "*.zip",      999,  20,  10_000_000),   # already compressed
    ("backups/weekly",   "*",          999,   8,  10_000_000),
    ("autonomy_runs",    "*.jsonl",     14, 800,  20_000_000),
]

# Single files that grow without bound: roll when larger than this, keep N rolls.
_ROLLING = [("generation_trace.jsonl", 5_000_000, 3),
            ("tool_calls.jsonl",       5_000_000, 3),
            ("nova_launcher.log",      5_000_000, 3),
            ("access.jsonl",           5_000_000, 3),
            ("ping_claude.log",        1_000_000, 2)]


def _quarantine(p: pathlib.Path) -> bool:
    """Move, never delete. Preserves the folder shape so it can be put straight back."""
    try:
        rel = p.relative_to(_WS)
        dst = _QUARANTINE / rel.parent
        dst.mkdir(parents=True, exist_ok=True)
        target = dst / p.name
        if target.exists():
            target = dst / f"{p.stem}_{int(time.time())}{p.suffix}"
        shutil.move(str(p), str(target))
        return True
    except Exception:
        return False


def _gzip_in_place(p: pathlib.Path) -> bool:
    """Compress, then QUARANTINE the original. Never unlink.

    ── THE BUG THIS FIXES, WHICH I WROTE (2026-07-20) ─────────────────────────────────
    First version ended with `p.unlink()`. On this mount unlink raises PermissionError, so
    the sequence was: write the .gz (succeeds) → unlink (throws) → `except: return False`.
    Result: 19 .gz files created, every original still on disk, and the function reporting
    that nothing happened. Data silently duplicated while the summary said `gzipped: 0`.

    A partial success reported as a no-op is the exact failure GOTCHAS.md opens with, and
    it was sitting inside the module whose own docstring cites that rule.

    Unlink was the wrong call regardless of the mount: JANITORIAL.md says quarantine, never
    destroy. The original now MOVES to _admin/Trash/ — recoverable, and it works on both a
    restricted mount and a normal filesystem.
    """
    gz = p.with_suffix(p.suffix + ".gz")
    try:
        if not gz.exists():
            with open(p, "rb") as fi, gzip.open(gz, "wb", compresslevel=6) as fo:
                shutil.copyfileobj(fi, fo)
        # Only retire the original once the .gz is on disk and non-empty.
        if gz.is_file() and gz.stat().st_size > 0:
            return _quarantine(p)
        return False
    except Exception:
        return False


def run(dry_run: bool = False) -> dict:
    """Rotate. Returns a summary. NEVER raises — a retention failure must not block a boot."""
    out = {"gzipped": [], "quarantined": [], "rolled": [], "errors": []}
    try:
        if not _LOGS.is_dir():
            return out
        now = time.time()

        for sub, pattern, gz_days, keep, budget in _POLICY:
            d = _LOGS / sub
            if not d.is_dir() or sub.split("/")[0] in _UNTOUCHABLE:
                continue
            try:
                files = sorted([f for f in d.glob(pattern) if f.is_file()],
                               key=lambda f: f.stat().st_mtime, reverse=True)
            except Exception as e:
                out["errors"].append(f"{sub}: {e}")
                continue

            # 1. compress anything older than the threshold (keeps the data, drops the bytes)
            for f in files:
                if f.suffix == ".gz":
                    continue
                try:
                    if (now - f.stat().st_mtime) > gz_days * 86400:
                        if dry_run or _gzip_in_place(f):
                            out["gzipped"].append(str(f.relative_to(_WS)))
                except Exception as e:
                    out["errors"].append(f"{f.name}: {e}")

            # 2. Trim ONLY if the directory is over BOTH its byte budget and its file cap.
            #    Compression usually gets us under budget on its own, and a small directory of
            #    old records is history, not clutter.
            try:
                files = sorted([f for f in d.glob("*") if f.is_file()],
                               key=lambda f: f.stat().st_mtime, reverse=True)
                total = sum(f.stat().st_size for f in files)
                if total > budget and len(files) > keep:
                    for f in files[keep:]:
                        if dry_run or _quarantine(f):
                            out["quarantined"].append(str(f.relative_to(_WS)))
                elif dry_run and len(files) > keep:
                    out.setdefault("under_budget_kept", []).append(
                        f"{sub}: {len(files)} files / {total//1024}KB — under {budget//1024//1024}MB budget, left alone")
            except Exception as e:
                out["errors"].append(f"{sub} cap: {e}")

        # 3. single unbounded files — roll at size, keep N
        for name, max_bytes, keep in _ROLLING:
            f = _LOGS / name
            try:
                if not f.is_file() or f.stat().st_size < max_bytes:
                    continue
                if dry_run:
                    out["rolled"].append(name)
                    continue
                stamp = time.strftime("%Y%m%d_%H%M%S")
                rolled = f.with_name(f"{f.stem}_{stamp}{f.suffix}")
                shutil.move(str(f), str(rolled))
                _gzip_in_place(rolled)
                out["rolled"].append(name)
                olds = sorted(_LOGS.glob(f"{f.stem}_*{f.suffix}*"),
                              key=lambda p: p.stat().st_mtime, reverse=True)
                for old in olds[keep:]:
                    _quarantine(old)
            except Exception as e:
                out["errors"].append(f"{name}: {e}")
    except Exception as e:
        out["errors"].append(f"fatal: {e}")
    return out


if __name__ == "__main__":
    import json as _j
    import sys as _s
    r = run(dry_run="--apply" not in _s.argv)
    print(("DRY RUN — nothing touched. Use --apply to act.\n"
           if "--apply" not in _s.argv else "APPLIED\n"))
    print(_j.dumps({k: (v if len(v) < 12 else v[:12] + [f"...+{len(v)-12} more"])
                    for k, v in r.items()}, indent=2))
