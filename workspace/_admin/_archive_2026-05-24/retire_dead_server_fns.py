#!/usr/bin/env python3
# Last updated: 2026-05-28 12:55:19
"""
retire_dead_server_fns.py — remove the now-dead old task/autonomy functions from
general_tools/nova_chat/server.py (superseded by nova_cortex.executive / .tasking and
nova_senses). Safe: makes a .bak, removes by name, then py_compiles — and restores the
.bak automatically if compilation fails. Run from the workspace root:

    py -3 _admin\\retire_dead_server_fns.py
"""
import re, sys, py_compile, shutil
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
SERVER = WS / "general_tools" / "nova_chat" / "server.py"

# Confirmed-dead (grep-verified unreferenced after the endpoint repoint).
# KEPT (do NOT list): import _time, _mirror_cole_intent, emit_event,
# _has_unread_cole, HeartbeatContext — still used.
DEAD_DEFS = [
    "_parse_queue", "_write_task", "_complete_task", "_autonomy_cfg",
    "_env_fingerprint", "_priority_hash", "_parse_task_intent", "_reconcile_queue",
    "_journal_correction", "_cole_is_typing", "_load_task_state", "_save_task_state",
    "_task_key", "_ensure_task_state", "_match_task_title", "_record_progress",
    "_drop_task_state", "_parse_task_progress", "_task_queue_view", "_run_autonomy_tick",
]
DEAD_CONSTS = ["_QUEUE_FILE", "_PRIORITY_LABELS", "_autonomy_state", "_TASK_STATE_FILE"]


def _block_end(lines, start):
    """Index one past a top-level block beginning at `start` (a def/assignment at col 0)."""
    i = start + 1
    while i < len(lines):
        ln = lines[i]
        if ln.strip() and not ln[0].isspace():   # next col-0, non-blank line
            break
        i += 1
    # trim trailing blank lines back into the gap (keep file tidy)
    return i


def main():
    src = SERVER.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    removed = []

    def remove_block(pred, label):
        for idx, ln in enumerate(lines):
            if pred(ln):
                end = _block_end(lines, idx)
                del lines[idx:end]
                removed.append(label)
                return True
        return False

    for name in DEAD_DEFS:
        pat = re.compile(rf"^(async def|def)\s+{re.escape(name)}\(")
        # a function may appear once; loop until none left
        while remove_block(lambda l, p=pat: bool(p.match(l)), f"def {name}"):
            pass
    for name in DEAD_CONSTS:
        pat = re.compile(rf"^{re.escape(name)}\s*=")
        while remove_block(lambda l, p=pat: bool(p.match(l)), f"const {name}"):
            pass

    if not removed:
        print("Nothing matched — already clean?")
        return
    bak = SERVER.with_suffix(".py.bak_retire")
    shutil.copy2(SERVER, bak)
    SERVER.write_text("".join(lines), encoding="utf-8")
    try:
        py_compile.compile(str(SERVER), doraise=True)
    except py_compile.PyCompileError as e:
        shutil.copy2(bak, SERVER)
        print("COMPILE FAILED — reverted from backup. No changes kept.")
        print(e)
        sys.exit(1)
    print(f"Removed {len(removed)} dead blocks; server.py compiles clean.")
    print("Backup:", bak.name)
    for r in removed:
        print("  -", r)


if __name__ == "__main__":
    main()
