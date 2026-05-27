#!/usr/bin/env python3
# Last updated: 2026-05-28 02:38:41
# @nova: ORIENT.md updater — refreshes auto-generated sections while preserving hand-written content; to be superseded by SELF/.
"""
orient.py — ORIENT.md updater for Project Nova
================================================
Refreshes the auto-generated sections of ORIENT.md while preserving
all hand-written content.

Auto-updated sections:
  - "Last auto-updated" timestamp in the header
  - Section 10: Infrastructure State table (scans nova_body/ for actual files)
  - Appends newly discovered Python files to the Workspace Map if not already listed

Usage:
    python general_tools/orient.py           # update in place
    python general_tools/orient.py --check   # dry-run: print diff, write nothing
    python general_tools/orient.py --help    # show this help

Run after:
  - Adding new modules to nova_body/ or general_tools/
  - Renaming or deleting source files
  - Changing infrastructure state (something PLANNED becomes ACTIVE, etc.)

Nova should run this at the end of any session where she added files.
Cowork AI should run this before starting any infrastructure task to confirm the
map matches reality.
"""

import sys
import os
import re
import ast
import argparse
import difflib
from pathlib import Path
from datetime import datetime

# ── Resolve workspace root ────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent          # general_tools/
_WS   = _HERE.parent                            # workspace/

ORIENT_PATH = _WS / "ORIENT.md"

# ── Directories and their status tags ─────────────────────────────────────────
# Format: (relative_path, display_label, expected_status)
NOVA_BODY_MODULES = [
    ("nova_body/nova_cortex",       "nova_cortex/",    "PLANNED"),
    ("nova_body/nova_logs",         "nova_logs/",      "PLANNED"),
    ("nova_body/nova_memory",       "nova_memory/",    "PLANNED"),
    ("nova_body/nova_motor",        "nova_motor/",     "PLANNED"),
    ("nova_body/nova_senses",       "nova_senses/",    "PLANNED"),
]

# Key planned files — if they exist, flip to ACTIVE
NOVA_BODY_KEY_FILES = {
    "nova_body/nova_cortex/nova_status.py":  "nova_cortex/nova_status.py",
    "nova_body/nova_cortex/checkin.py":      "nova_cortex/checkin.py",
}


def get_docstring(path: Path) -> str:
    """Extract the first line of the module docstring, or ''."""
    try:
        source = path.read_text(encoding="utf-8-sig", errors="replace")
        tree   = ast.parse(source)
        ds     = ast.get_docstring(tree)
        if ds:
            return ds.split("\n")[0].strip()[:80]
    except Exception:
        pass
    return ""


def scan_nova_body() -> dict:
    """
    Scan nova_body/ and return a dict of what actually exists.
    Returns { rel_path_str: {"has_files": bool, "files": [name, ...]} }
    """
    result = {}
    for rel, label, _ in NOVA_BODY_MODULES:
        abs_path = _WS / rel
        py_files = sorted(p.name for p in abs_path.glob("*.py")) if abs_path.exists() else []
        result[rel] = {
            "label":    label,
            "has_files": bool(py_files),
            "files":    py_files,
        }
    return result


def scan_new_general_tools() -> list[tuple[str, str]]:
    """
    Find Python files in general_tools/ (top-level only) that are not
    already mentioned anywhere in ORIENT.md.
    Returns list of (filename, docstring_first_line).
    """
    if not ORIENT_PATH.exists():
        return []
    current_text = ORIENT_PATH.read_text(encoding="utf-8")
    new_files = []
    for py in sorted((_WS / "general_tools").glob("*.py")):
        if py.name not in current_text:
            ds = get_docstring(py)
            new_files.append((py.name, ds))
    return new_files


def build_state_table(nova_body_scan: dict) -> str:
    """
    Rebuild Section 10 (Infrastructure State) table.
    Detects actual file presence to flip PLANNED → ACTIVE.
    """
    rows = [
        ("nova_chat server",            "✅ ACTIVE",   "Full WebSocket chat, streaming, sessions"),
        ("nova_gateway",                "✅ ACTIVE",   "Discord, scheduler, llama.cpp inference"),
        ("PyQt6 UI (nova_qt)",          "✅ ACTIVE",   "Chat, monitor, eyes, thoughts panes"),
        ("Nova.exe launcher",           "✅ ACTIVE",   "Stub → NovaLauncher.py"),
        ("Autonomous heartbeat loop",   "✅ ACTIVE",   "[HEARTBEAT N], silent idle stop via nova_status.json"),
        ("Thoughts system",             "✅ ACTIVE",   "priority.md, Master_Inbox, Thought folders"),
        ("nova_sync/watcher.py",        "✅ ACTIVE",   "Git push + FILE_INDEX generation"),
        ("nova_sync/drive.py",          "✅ ACTIVE",   "Google Drive mirror"),
    ]

    # nova_body modules — check actual file presence
    for rel, info in nova_body_scan.items():
        label = f"nova_body/{info['label']}"
        if info["has_files"]:
            status = "✅ ACTIVE"
            note   = f"Contains: {', '.join(info['files'][:4])}"
        else:
            status = "🔨 BUILDING"
            note   = "Directories exist, Python files not yet created"
        rows.append((label, status, note))

    # Key planned files
    for rel_path, display in NOVA_BODY_KEY_FILES.items():
        full = _WS / rel_path
        if full.exists():
            ds = get_docstring(full)
            rows.append((display, "✅ ACTIVE", ds or "exists"))
        else:
            rows.append((display, "🔨 PLANNED", "not yet created"))

    # Known ongoing states
    rows += [
        ("Discord 429 rate limit on startup", "⚠️ KNOWN BUG", "Bot rate-limited on login every launch"),
        ("nova_gateway/ (old package)",       "⚠️ LEGACY",    "Dissolved 2026-05-08 to gateway.py; directory kept for imports"),
    ]

    lines = ["| Component | Status | Notes |",
             "|-----------|--------|-------|"]
    for comp, status, note in rows:
        lines.append(f"| {comp} | {status} | {note} |")
    return "\n".join(lines)


def update_orient(dry_run: bool = False) -> bool:
    """
    Load ORIENT.md, update auto-generated sections, write back.
    Returns True if changes were made.
    """
    if not ORIENT_PATH.exists():
        print(f"[orient] ERROR: {ORIENT_PATH} not found. Run from workspace root or general_tools/.")
        return False

    original = ORIENT_PATH.read_text(encoding="utf-8")
    updated  = original

    # ── 1. Update timestamp ───────────────────────────────────────────────────
    today = datetime.now().strftime("%Y-%m-%d")
    updated = re.sub(
        r"_Last auto-updated: \d{4}-\d{2}-\d{2}_",
        f"_Last auto-updated: {today}_",
        updated,
    )

    # ── 2. Rebuild Section 10 table ───────────────────────────────────────────
    nova_body_scan = scan_nova_body()
    new_table      = build_state_table(nova_body_scan)

    # Find the section 10 block: capture section header (group 1) then the
    # full table (group 2) up to the next blank+--- or blank+##.
    # Group 1 stops BEFORE the first pipe so the new table replaces it entirely.
    pattern = re.compile(
        r"(## 10\. Infrastructure State[^\n]*\n\n)(\| Component.*?)(\n\n---|\n\n##)",
        re.DOTALL,
    )
    match = pattern.search(updated)
    if match:
        updated = updated[:match.start(2)] + new_table + updated[match.end(2):]
    else:
        print("[orient] WARNING: Could not locate Section 10 table — skipping table update.")

    # ── 3. Note any new general_tools files not yet in the doc ───────────────
    new_files = scan_new_general_tools()
    if new_files:
        notice = "\n\n> **orient.py notice — undocumented files found in general_tools/:**\n"
        for fn, ds in new_files:
            notice += f"> - `{fn}` — {ds or '(no docstring)'}\n"
        notice += "> Update the Workspace Map section above to document these.\n"
        # Append notice before the final ---
        if notice.strip() not in updated:
            updated = updated.rstrip() + "\n" + notice

    # ── 4. Diff and output ────────────────────────────────────────────────────
    changed = updated != original

    if dry_run:
        if changed:
            diff = difflib.unified_diff(
                original.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile="ORIENT.md (current)",
                tofile="ORIENT.md (proposed)",
            )
            print("".join(diff))
        else:
            print("[orient] No changes — ORIENT.md is already up to date.")
        return changed

    if changed:
        ORIENT_PATH.write_text(updated, encoding="utf-8")
        print(f"[orient] ORIENT.md updated ({today}).")
        if new_files:
            print(f"[orient] NOTE: {len(new_files)} undocumented file(s) found — see notice at bottom of ORIENT.md.")
    else:
        print("[orient] No changes — ORIENT.md is already up to date.")

    return changed


def main():
    parser = argparse.ArgumentParser(
        description="Update ORIENT.md with current workspace state.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Dry-run: print diff but do not write.",
    )
    args = parser.parse_args()

    changed = update_orient(dry_run=args.check)
    sys.exit(0 if not changed or not args.check else 1)


if __name__ == "__main__":
    main()
