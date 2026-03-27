# Last updated: 2026-03-20 21:24:54
"""
nova_backup.py -- Automated Workspace Backup System
=====================================================
Two backup types:

1. SESSION SNAPSHOT (runs on every nova_watcher boot)
   - Zips critical memory files only (STATUS, JOURNAL, COLE, HEARTBEAT, FILE_INDEX)
   - Stored in logs/backups/sessions/YYYY-MM-DD_HH-MM_session.zip
   - Keeps last 30 session snapshots, auto-prunes older ones
   - Fast -- only a few KB per snapshot

2. WEEKLY FULL BACKUP (runs every Sunday automatically)
   - Zips entire workspace excluding noise (node_modules, __pycache__, screenshots etc)
   - Stored in logs/backups/weekly/YYYY-MM-DD_weekly.zip
   - Keeps last 4 weekly backups, auto-prunes older ones
   - Also pushes to Google Drive backups/ folder if nova_drive is available

Usage (called by nova_watcher.py on boot):
    from nova_sync.backup import run_backup
    run_backup()

Manual full backup:
    python tools/nova_sync/backup.py --full

Restore from backup:
    python tools/nova_sync/backup.py --list
    python tools/nova_sync/backup.py --restore <zip_path>
"""

import sys
import zipfile
import traceback
from pathlib import Path
from datetime import datetime

# -- Config -------------------------------------------------------------------

WORKSPACE_DIR = Path(__file__).parent.parent.parent
BACKUP_DIR = WORKSPACE_DIR / "logs" / "backups"
SESSION_BACKUP_DIR = BACKUP_DIR / "sessions"
WEEKLY_BACKUP_DIR = BACKUP_DIR / "weekly"

# Critical files for session snapshots
SESSION_SNAPSHOT_FILES = [
    "memory/STATUS.md",
    "memory/JOURNAL.md",
    "memory/COLE.md",
    "memory/session_start.json",
    "tools/nova_sync/FILE_INDEX.md",
    "tools/nova_sync/FILE_INDEX_LINK.md",
    "AGENTS.md",
    "BOOTSTRAP.md",
    "SOUL.md",
    "TOOLS.md",
    "USER.md",
    "IDENTITY.md",
]

EXCLUDE_DIRS = {
    ".git", "__pycache__", "node_modules", ".clawhub",
    "screenshots", "backups",
}
EXCLUDE_SUBPATHS = {
    "logs/screenshots",
    "tools/backups",
    "agents/main/sessions",
}
INCLUDE_EXTENSIONS = {
    ".py", ".md", ".json", ".jsonl", ".txt", ".cmd", ".ps1"
}

MAX_SESSION_BACKUPS = 30
MAX_WEEKLY_BACKUPS = 4


def session_snapshot():
    SESSION_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    zip_path = SESSION_BACKUP_DIR / f"{timestamp}_session.zip"

    backed_up = 0
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel_str in SESSION_SNAPSHOT_FILES:
                path = WORKSPACE_DIR / Path(rel_str)
                if path.exists():
                    zf.write(path, rel_str)
                    backed_up += 1
            today = datetime.now().strftime("%Y-%m-%d")
            mentor_log = WORKSPACE_DIR / "logs" / "sessions" / today / "mentor.jsonl"
            if mentor_log.exists():
                zf.write(mentor_log, f"logs/sessions/{today}/mentor.jsonl")
                backed_up += 1

        size_kb = zip_path.stat().st_size // 1024
        print(f"[backup] Session snapshot: {zip_path.name} ({backed_up} files, {size_kb}KB)")
        _prune_backups(SESSION_BACKUP_DIR, "session.zip", MAX_SESSION_BACKUPS)
        _push_to_drive(zip_path, folder_name="sessions")
        return True

    except Exception as e:
        print(f"[backup] Session snapshot failed: {e}")
        return False


def weekly_backup(force=False):
    today = datetime.now()
    is_sunday = today.weekday() == 6

    if not force and not is_sunday:
        return False

    WEEKLY_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = today.strftime("%Y-%m-%d")
    zip_path = WEEKLY_BACKUP_DIR / f"{timestamp}_weekly.zip"

    if zip_path.exists() and not force:
        print(f"[backup] Weekly backup already exists for today.")
        return True

    print(f"[backup] Running weekly full backup...")
    backed_up = 0
    skipped = 0

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(WORKSPACE_DIR.rglob("*")):
                if not path.is_file():
                    continue
                try:
                    rel = path.relative_to(WORKSPACE_DIR)
                    rel_str = str(rel).replace("\\", "/")
                    parts = rel.parts
                except ValueError:
                    continue

                if any(excl in parts for excl in EXCLUDE_DIRS):
                    skipped += 1
                    continue
                if any(rel_str.startswith(sub) for sub in EXCLUDE_SUBPATHS):
                    skipped += 1
                    continue
                if path.suffix.lower() not in INCLUDE_EXTENSIONS:
                    skipped += 1
                    continue

                zf.write(path, rel_str)
                backed_up += 1

        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"[backup] Weekly backup: {zip_path.name} ({backed_up} files, {size_mb:.1f}MB)")
        _prune_backups(WEEKLY_BACKUP_DIR, "weekly.zip", MAX_WEEKLY_BACKUPS)
        _push_to_drive(zip_path, folder_name="weekly")
        return True

    except Exception as e:
        print(f"[backup] Weekly backup failed: {e}")
        traceback.print_exc()
        return False


def _prune_backups(directory, suffix, keep):
    backups = sorted(directory.glob(f"*{suffix}"))
    if len(backups) > keep:
        for old in backups[:len(backups) - keep]:
            old.unlink()
            print(f"[backup] Pruned old backup: {old.name}")


def _push_to_drive(zip_path, folder_name="weekly"):
    try:
        sys.path.insert(0, str(WORKSPACE_DIR / "tools"))
        from nova_sync.drive import _connect, _get_or_create_folder, ROOT_FOLDER_ID
        import io
        from googleapiclient.http import MediaIoBaseUpload

        service = _connect()
        if not service:
            return

        backup_folder_id = _get_or_create_folder(service, "backups", ROOT_FOLDER_ID)
        target_folder_id = _get_or_create_folder(service, folder_name, backup_folder_id)

        query = f"name='{zip_path.name}' and '{target_folder_id}' in parents and trashed=false"
        results = service.files().list(q=query, fields="files(id)").execute()
        existing = results.get("files", [])

        media = MediaIoBaseUpload(
            io.BytesIO(zip_path.read_bytes()),
            mimetype="application/zip",
            resumable=False
        )

        if existing:
            service.files().update(fileId=existing[0]["id"], media_body=media).execute()
        else:
            service.files().create(
                body={"name": zip_path.name, "parents": [target_folder_id]},
                media_body=media, fields="id"
            ).execute()

        print(f"[backup] Pushed {zip_path.name} to Drive backups/{folder_name}/")

    except Exception as e:
        print(f"[backup] Drive push skipped: {e}")


def run_backup():
    session_snapshot()
    weekly_backup()


def list_backups():
    print("\n=== Session Snapshots ===")
    if SESSION_BACKUP_DIR.exists():
        snapshots = sorted(SESSION_BACKUP_DIR.glob("*session.zip"))
        for s in snapshots[-10:]:
            print(f"  {s.name} ({s.stat().st_size // 1024}KB)")
        if not snapshots:
            print("  None yet.")
    else:
        print("  None yet.")

    print("\n=== Weekly Backups ===")
    if WEEKLY_BACKUP_DIR.exists():
        weeklies = sorted(WEEKLY_BACKUP_DIR.glob("*weekly.zip"))
        for w in weeklies:
            print(f"  {w.name} ({w.stat().st_size / (1024*1024):.1f}MB)")
        if not weeklies:
            print("  None yet.")
    else:
        print("  None yet.")
    print()


def restore_backup(zip_path_str):
    zip_path = Path(zip_path_str)
    if not zip_path.exists():
        print(f"[backup] File not found: {zip_path}")
        return False
    print(f"[backup] Restoring from {zip_path.name}...")
    print(f"[backup] WARNING: This will overwrite current workspace files.")
    confirm = input("[backup] Type YES to confirm: ")
    if confirm.strip() != "YES":
        print("[backup] Restore cancelled.")
        return False
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(WORKSPACE_DIR)
    print(f"[backup] Restore complete.")
    return True


if __name__ == "__main__":
    if "--list" in sys.argv:
        list_backups()
    elif "--restore" in sys.argv:
        idx = sys.argv.index("--restore")
        if idx + 1 < len(sys.argv):
            restore_backup(sys.argv[idx + 1])
        else:
            print("Usage: python nova_sync/backup.py --restore <zip_path>")
    elif "--full" in sys.argv:
        print("Running forced full weekly backup...")
        weekly_backup(force=True)
    else:
        print("Running standard backup (session snapshot + weekly if Sunday)...")
        run_backup()
