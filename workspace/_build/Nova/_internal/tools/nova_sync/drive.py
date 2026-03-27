# Last updated: 2026-03-21 12:40:32
"""
nova_drive.py -- Google Drive Workspace Mirror for Gemini Live Access
======================================================================
Maintains an exact mirror of the workspace in Google Drive using diff-based sync.
Only uploads new/changed files and deletes removed ones -- never rebuilds from scratch.

Drive structure:
    Nova_Workspace/              <-- shared folder (ROOT_FOLDER_ID)
        GEMINI_INDEX.md          <-- Gemini's session manifest (written here on every sync)
        workspace/               <-- exact clone of local workspace/
            memory/
                STATUS.md
                JOURNAL.md
            tools/
                nova_sync/
                    watcher.py
                    ...

Gemini permanent folder:
    https://drive.google.com/drive/folders/1GLW6qVm5PHp_xnSlEXlnZIBhhmixzFya
"""

import io
import json
import hashlib
import traceback
from pathlib import Path
from datetime import datetime

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    DRIVE_AVAILABLE = True
except ImportError:
    DRIVE_AVAILABLE = False

# -- Config -------------------------------------------------------------------

WORKSPACE_DIR = Path(__file__).parent.parent.parent
SYNC_DIR      = Path(__file__).parent
ROOT_FOLDER_ID = "1GLW6qVm5PHp_xnSlEXlnZIBhhmixzFya"
WORKSPACE_FOLDER_NAME = "workspace"

# Sync cache lives in nova_sync/ alongside the other sync infrastructure
SYNC_CACHE_PATH = SYNC_DIR / ".drive_sync_cache.json"

CLIENT_SECRETS_PATHS = [
    Path.home() / "OneDrive" / "Documents" / "client_secrets.json",
    Path.home() / "Documents" / "client_secrets.json",
]

SCOPES = ["https://www.googleapis.com/auth/drive"]

EXCLUDE_DIRS     = {".git", "__pycache__", "node_modules", ".clawhub", "screenshots", "_build"}
EXCLUDE_SUBPATHS = {"logs/screenshots", "tools/backups", "agents/main/sessions"}
INCLUDE_EXTENSIONS = {".py", ".md", ".json", ".jsonl", ".txt", ".cmd", ".ps1"}
# Files that must never be uploaded to Drive — contain secrets or are too large.
EXCLUDE_FILES    = {
    ".drive_sync_cache.json",
    "nova_gateway.json",        # contains Discord bot token
    "openclaw.json",            # contains Discord bot token
    "nova_drive_token.json",    # OAuth token — shouldn't leave local machine
    "client_secrets.json",      # OAuth client secret
}


# -- Auth ---------------------------------------------------------------------

def _get_client_secrets():
    for p in CLIENT_SECRETS_PATHS:
        if p.exists():
            return p
    return None


def _connect():
    creds = None
    secrets_path = _get_client_secrets()
    if not secrets_path:
        print("[drive] ERROR: client_secrets.json not found.")
        return None

    token_path = secrets_path.parent / "nova_drive_token.json"

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("[drive] Opening browser for one-time Google login...")
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("drive", "v3", credentials=creds)


# -- Local file scanning ------------------------------------------------------

def _file_checksum(path):
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except Exception:
        return None


def _scan_local_files():
    files = {}
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
            continue
        if any(rel_str.startswith(sub) for sub in EXCLUDE_SUBPATHS):
            continue
        if path.suffix.lower() not in INCLUDE_EXTENSIONS:
            continue
        if path.name in EXCLUDE_FILES:
            continue

        checksum = _file_checksum(path)
        if checksum:
            files[rel_str] = checksum
    return files


def _load_sync_cache():
    try:
        if SYNC_CACHE_PATH.exists():
            return json.loads(SYNC_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_sync_cache(cache):
    try:
        SYNC_CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[drive] Warning: could not save sync cache: {e}")


# -- Drive file/folder management ---------------------------------------------

_folder_id_cache = {}


def _get_or_create_folder(service, name, parent_id):
    cache_key = f"{parent_id}/{name}"
    if cache_key in _folder_id_cache:
        return _folder_id_cache[cache_key]

    query = (f"name='{name}' and mimeType='application/vnd.google-apps.folder' "
             f"and '{parent_id}' in parents and trashed=false")
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])

    if files:
        folder_id = files[0]["id"]
    else:
        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = service.files().create(body=metadata, fields="id").execute()
        folder_id = folder["id"]

    _folder_id_cache[cache_key] = folder_id
    return folder_id


def _ensure_folder_path(service, parts, root_id):
    current_id = root_id
    for part in parts[:-1]:
        current_id = _get_or_create_folder(service, part, current_id)
    return current_id


_file_id_cache = {}


def _get_existing_file(service, name, parent_id):
    cache_key = f"{parent_id}/{name}"
    if cache_key in _file_id_cache:
        return _file_id_cache[cache_key]

    query = (f"name='{name}' and '{parent_id}' in parents and trashed=false "
             f"and mimeType!='application/vnd.google-apps.folder'")
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])
    file_id = files[0]["id"] if files else None
    if file_id:
        _file_id_cache[cache_key] = file_id
    return file_id


def _upsert_file(service, name, content, parent_id):
    """
    Upload a file as a native Google Docs document.
    Uploading with mimeType=application/vnd.google-apps.document while
    providing text/plain content causes Google to convert it server-side.
    This makes all files immediately visible to Gemini's Personal Context tool.
    """
    media = MediaIoBaseUpload(
        io.BytesIO(content.encode("utf-8")),
        mimetype="text/plain",   # content encoding -- plain text input
        resumable=False
    )
    existing_id = _get_existing_file(service, name, parent_id)
    if existing_id:
        # Update content -- keep existing Docs format
        service.files().update(
            fileId=existing_id,
            media_body=media
        ).execute()
        return existing_id
    else:
        # Create as native Google Doc so Gemini can find it immediately
        result = service.files().create(
            body={
                "name": name,
                "parents": [parent_id],
                "mimeType": "application/vnd.google-apps.document",
            },
            media_body=media,
            fields="id"
        ).execute()
        file_id = result["id"]
        _file_id_cache[f"{parent_id}/{name}"] = file_id
        return file_id


def _delete_file(service, file_id):
    try:
        service.files().delete(fileId=file_id).execute()
    except Exception as e:
        print(f"[drive] Warning: could not delete file {file_id}: {e}")


# -- Gemini Index -------------------------------------------------------------

# Descriptions keyed by filename -- updated to reflect package structure
FILE_DESCRIPTIONS = {
    # Root workspace files
    "AGENTS.md":       "Nova's operating rules and agent behavior definitions",
    "BOOTSTRAP.md":    "Boot sequence Nova follows on every OpenClaw start",
    "SOUL.md":         "Nova's identity, values, and growth framework",
    "TOOLS.md":        "How to use all tools, method reference, exec patterns",
    "USER.md":         "Who Cole is -- personality, background, preferences",
    "IDENTITY.md":     "Nova's self-definition document",
    "HEARTBEAT.md":    "Current heartbeat state",
    "README.md":       "Project overview",
    # Memory files
    "STATUS.md":       "Current project state and mission -- READ FIRST",
    "JOURNAL.md":      "Nova's running session log -- READ SECOND",
    "COLE.md":         "Cole's notes and Nova's observations about Cole",
    "FILE_INDEX.md":   "Full workspace file listing with GitHub URLs (for Claude)",
    "FILE_INDEX_LINK.md": "Claude's bootstrap URL pointer",
    "session_start.json": "Current session start timestamp",
    # nova_sync package
    "watcher.py":      "GitHub sync + Drive sync + backup. Modes: --push, --pup, --full",
    "drive.py":        "Google Drive diff-based sync (this system)",
    "backup.py":       "Session snapshots on boot, weekly full backups on Sundays",
    "dir_patch.py":    "Import path auditor -- scans .py and .md for stale references",
    # nova_memory package
    "logger.py":       "Dated log folder manager",
    "journal.py":      "Append-only JOURNAL.md writer with sanitize()",
    "log_reader.py":   "Reads session logs -- summarize_today(), get_failures()",
    "status.py":       "STATUS.md proposed-changes updater",
    "state.py":        "Pre-condition state checking before any action",
    # nova_advisor package
    "mentor.py":       "Claude Sonnet + Haiku advisor -- GROWTH MODE, gatekeeper",
    # nova_action package
    "autonomy.py":     "FIND->COMMIT->VERIFY action loop with interrupt polling",
    "hands.py":        "Mouse/keyboard control via pyautogui + pynput",
    "verify.py":       "Action verification helpers",
    # nova_perception package
    "eyes.py":         "Unified vision -- pywinauto first, Claude Haiku fallback",
    "explorer.py":     "pywinauto accessibility API wrapper -- exact UI coordinates",
    "vision.py":       "Claude Haiku screen verification and description",
    "vision_backup.py": "Backup vision implementation using basic image matching",
    # nova_core package
    "rules.py":        "Immutable operating directives and yield protocol",
    "brain.py":        "Companion-first cognitive router",
    "checkin.py":      "Inter-turn message listener and session init",
    # Misc tools
    "nova_stress_tester.py": "Failure mode testing framework",
    "nova_patch.py":   "Post-restructure import patcher and test runner",
    "nova_restructure.py": "One-time package migration script (keep for reference)",
}


def _build_gemini_index_content() -> str:
    """
    Build the GEMINI_INDEX.md content as a manifest table.
    Uses full relative paths (workspace/...) as deterministic search keys.
    Also writes a local copy to nova_sync/ for backup and Claude visibility.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append("# GEMINI_INDEX.md -- Nova Workspace Session Manifest")
    lines.append(f"_Last updated: {timestamp}_")
    lines.append("")
    lines.append("## INITIALIZATION PROTOCOL")
    lines.append("Run these three steps at the start of every session in order:")
    lines.append("")
    lines.append("```")
    lines.append("Step 1: @Google Drive: Search for the folder 'Nova_Workspace'")
    lines.append("Step 2: @Google Drive: Search for 'workspace/tools/nova_sync/GEMINI_INDEX.md'")
    lines.append("Step 3: Refer to the Search Key column below for all subsequent file lookups.")
    lines.append("```")
    lines.append("")
    lines.append("**Rule: Never guess a path. Only search using the exact string in the Search Key column.**")
    lines.append("")
    lines.append("## START HERE EVERY SESSION")
    lines.append("")
    lines.append("| File | Search Key | Description |")
    lines.append("|------|-----------|-------------|")
    lines.append("| STATUS.md | `workspace/memory/STATUS.md` | Current project state -- READ FIRST |")
    lines.append("| JOURNAL.md | `workspace/memory/JOURNAL.md` | Nova's session log -- READ SECOND |")
    lines.append("| COLE.md | `workspace/memory/COLE.md` | Who Cole is and Nova's notes |")
    lines.append("| TOOLS.md | `workspace/TOOLS.md` | Tool reference and exec patterns |")
    lines.append("| BOOTSTRAP.md | `workspace/BOOTSTRAP.md` | Session startup sequence |")
    lines.append("")

    # Build full manifest table by scanning workspace
    sections = {}

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
            continue
        if any(rel_str.startswith(sub) for sub in EXCLUDE_SUBPATHS):
            continue
        if path.suffix.lower() not in INCLUDE_EXTENSIONS:
            continue
        if path.name == "GEMINI_INDEX.md":
            continue

        search_key = f"workspace/{rel_str}"
        desc = FILE_DESCRIPTIONS.get(path.name, f"{path.suffix.upper()[1:]} file")

        section = parts[0] if len(parts) > 1 else "root"
        if section not in sections:
            sections[section] = []
        sections[section].append((path.name, search_key, desc))

    # Root files first
    if "root" in sections:
        lines.append("## Root Files")
        lines.append("")
        lines.append("| Filename | Search Key | Description |")
        lines.append("|----------|-----------|-------------|")
        for fname, key, desc in sections["root"]:
            lines.append(f"| {fname} | `{key}` | {desc} |")
        lines.append("")

    # Other sections
    section_order = ["memory", "tools", "logs", "skills"]
    other_sections = [s for s in sorted(sections) if s not in ("root",) + tuple(section_order)]

    for section in section_order + other_sections:
        if section not in sections or section == "root":
            continue
        lines.append(f"## {section}/")
        lines.append("")
        lines.append("| Filename | Search Key | Description |")
        lines.append("|----------|-----------|-------------|")
        for fname, key, desc in sections[section]:
            lines.append(f"| {fname} | `{key}` | {desc} |")
        lines.append("")

    lines.append("---")
    lines.append("_This manifest is auto-generated on every Drive sync by nova_sync/drive.py._")
    lines.append("_Do not edit manually -- changes will be overwritten._")

    return "\n".join(lines)


def _write_gemini_index(service, root_folder_id):
    """
    Write GEMINI_INDEX.md to root of Nova_Workspace on Drive.
    Also saves a local copy to nova_sync/ for Claude visibility and backups.
    """
    index_content = _build_gemini_index_content()

    # Save local copy to nova_sync/
    local_index = SYNC_DIR / "GEMINI_INDEX.md"
    try:
        local_index.write_text(index_content, encoding="utf-8")
    except Exception as e:
        print(f"[drive] Warning: could not save local GEMINI_INDEX.md: {e}")

    # Write to Drive root
    media = MediaIoBaseUpload(
        io.BytesIO(index_content.encode("utf-8")),
        mimetype="text/plain",
        resumable=False
    )

    query = f"name='GEMINI_INDEX.md' and '{root_folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id)").execute()
    existing = results.get("files", [])

    if existing:
        service.files().update(fileId=existing[0]["id"], media_body=media).execute()
    else:
        service.files().create(
            body={"name": "GEMINI_INDEX.md", "parents": [root_folder_id]},
            media_body=media,
            fields="id"
        ).execute()

    print("[drive] GEMINI_INDEX.md updated (Drive root + local nova_sync/ copy).")


# -- Main sync ----------------------------------------------------------------

def sync_to_drive():
    if not DRIVE_AVAILABLE:
        print("[drive] Missing libraries. Run:")
        print("[drive]   pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        return False

    try:
        service = _connect()
        if not service:
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        workspace_id = _get_or_create_folder(service, WORKSPACE_FOLDER_NAME, ROOT_FOLDER_ID)
        local_files  = _scan_local_files()
        sync_cache   = _load_sync_cache()

        to_upload = [r for r, c in local_files.items()
                     if r not in sync_cache or sync_cache[r] != c]
        to_delete = [r for r in sync_cache if r not in local_files]

        if not to_upload and not to_delete:
            print(f"[drive] No changes detected -- Drive already up to date.")
            _write_gemini_index(service, ROOT_FOLDER_ID)
            return True

        print(f"[drive] Syncing at {timestamp}: {len(to_upload)} to upload, {len(to_delete)} to delete...")

        uploaded = 0
        for rel_str in to_upload:
            path = WORKSPACE_DIR / rel_str.replace("/", "\\")
            parts = Path(rel_str).parts
            try:
                content = path.read_text(encoding="utf-8")
            except Exception as e:
                content = f"[could not read: {e}]"
            parent_id = _ensure_folder_path(service, parts, workspace_id)
            _upsert_file(service, parts[-1], content, parent_id)
            sync_cache[rel_str] = local_files[rel_str]
            uploaded += 1
            print(f"[drive]   UPLOAD: {rel_str}")

        deleted = 0
        for rel_str in to_delete:
            parts = Path(rel_str).parts
            try:
                parent_id = _ensure_folder_path(service, parts, workspace_id)
                file_id = _get_existing_file(service, parts[-1], parent_id)
                if file_id:
                    _delete_file(service, file_id)
                del sync_cache[rel_str]
                deleted += 1
                print(f"[drive]   DELETE: {rel_str}")
            except Exception as e:
                print(f"[drive] Warning: could not delete {rel_str}: {e}")

        _save_sync_cache(sync_cache)
        print(f"[drive] Done: {uploaded} uploaded, {deleted} deleted.")
        _write_gemini_index(service, ROOT_FOLDER_ID)
        return True

    except Exception as e:
        print(f"[drive] Sync failed: {e}")
        traceback.print_exc()
        return False


def full_resync():
    """
    Force a full resync by clearing the cache and re-uploading everything.
    Use this if Drive gets out of sync or after manual Drive changes.
    Run: python tools/nova_sync/drive.py --full
    """
    print("[drive] Full resync requested -- clearing cache...")
    if SYNC_CACHE_PATH.exists():
        SYNC_CACHE_PATH.unlink()
    try:
        service = _connect()
        if service:
            results = service.files().list(
                q=f"name='{WORKSPACE_FOLDER_NAME}' and '{ROOT_FOLDER_ID}' in parents and trashed=false",
                fields="files(id)"
            ).execute()
            files = results.get("files", [])
            if files:
                print("[drive] Deleting old workspace/ folder...")
                service.files().delete(fileId=files[0]["id"]).execute()
    except Exception as e:
        print(f"[drive] Warning during cleanup: {e}")
    return sync_to_drive()


if __name__ == "__main__":
    import sys
    if "--full" in sys.argv:
        print("Running full resync...")
        success = full_resync()
    else:
        print("Running diff-based sync...")
        success = sync_to_drive()
    print("Success!" if success else "Failed -- check errors above.")
