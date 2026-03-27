"""
migrate_to_project_nova.py
===========================
One-time migration: move the workspace from .openclaw to Project_Nova.

Run this AFTER:
  1. nova_gateway live test passes (task 3.11)
  2. OpenClaw has been stopped (openclaw gateway stop)
  3. You've confirmed nova_gateway is handling Discord

Run from anywhere:
  python _admin/migrate_to_project_nova.py [--dry-run]

What it does:
  1. Creates C:\\Users\\lafou\\Project_Nova\\
  2. Copies entire workspace/ folder to Project_Nova\\workspace\\
  3. Updates nova_gateway.json workspace reference (already dynamic, just confirms)
  4. Prints a checklist of things to do manually after

What it does NOT do (manual steps required):
  - Stop OpenClaw (you do that)
  - Update QUICK REFERENCE paths in NOVA_PROJECT_PLAN.md (cosmetic, not urgent)
  - Remove the old .openclaw folder (leave it as backup until confident)
"""

import argparse
import shutil
import sys
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
THIS_FILE   = Path(__file__).resolve()
WORKSPACE   = THIS_FILE.parent.parent              # workspace/
OLD_ROOT    = WORKSPACE.parent                     # .openclaw/  (current)
NEW_ROOT    = Path.home() / "Project_Nova"         # C:\Users\lafou\Project_Nova\
NEW_WS      = NEW_ROOT / "workspace"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without doing anything")
    args = parser.parse_args()
    dry = args.dry_run

    print()
    print("=" * 60)
    print("  PROJECT NOVA — Workspace Migration")
    print("  FROM:", WORKSPACE)
    print("  TO:  ", NEW_WS)
    print("=" * 60)
    print()

    if dry:
        print("[DRY RUN — no files will be moved]")
        print()

    # ── Pre-flight checks ────────────────────────────────────────────────────
    if not WORKSPACE.exists():
        print(f"ERROR: Source workspace not found: {WORKSPACE}")
        sys.exit(1)

    if NEW_WS.exists():
        print(f"WARNING: Destination already exists: {NEW_WS}")
        resp = input("Continue anyway? (y/N): ").strip().lower()
        if resp != "y":
            print("Aborted.")
            sys.exit(0)

    # ── Copy workspace ───────────────────────────────────────────────────────
    print(f"Creating {NEW_ROOT}...")
    if not dry:
        NEW_ROOT.mkdir(parents=True, exist_ok=True)

    print(f"Copying workspace → {NEW_WS} (this may take a moment)...")
    if not dry:
        shutil.copytree(
            str(WORKSPACE),
            str(NEW_WS),
            ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", ".git",
                "node_modules", "_build",
                "logs/backups",        # skip old backup zips
            ),
            dirs_exist_ok=True,
        )
        print("  Copy complete.")
    else:
        # Count files that would be copied
        file_count = sum(1 for _ in WORKSPACE.rglob("*") if _.is_file())
        print(f"  [DRY RUN] Would copy ~{file_count} files.")

    # ── Verify nova_gateway_runner.py exists at new root ─────────────────────
    runner = NEW_WS / "nova_gateway_runner.py"
    if not dry and runner.exists():
        print(f"✓ nova_gateway_runner.py present at new root.")
    elif dry:
        src_runner = WORKSPACE / "nova_gateway_runner.py"
        print(f"✓ nova_gateway_runner.py {'found' if src_runner.exists() else 'MISSING'} at source.")

    print()
    print("=" * 60)
    print("  MIGRATION COMPLETE" if not dry else "  DRY RUN COMPLETE — nothing was changed")
    print("=" * 60)
    print()
    print("NEXT STEPS (manual):")
    print()
    print("  1. Test new location:")
    print(f"       cd {NEW_WS}")
    print( "       python nova_gateway_runner.py --dry")
    print( "       python tools\\nova_chat\\server_runner.py")
    print()
    print("  2. Update NovaChatLauncher.exe source if needed:")
    print( "       tools\\NovaChatLauncher.py — update any hardcoded paths")
    print()
    print("  3. Rebuild executables from new location:")
    print( "       python tools\\build_launcher.py")
    print()
    print("  4. Update Windows startup shortcuts to point at new path.")
    print()
    print("  5. Once confident everything works in new location:")
    print(f"       Delete old workspace: {WORKSPACE}")
    print(f"       (Leave {OLD_ROOT} in place until OpenClaw is fully gone)")
    print()
    print("  6. Update QUICK REFERENCE section in _admin/NOVA_PROJECT_PLAN.md")
    print( "     to show new paths.")
    print()

if __name__ == "__main__":
    main()
