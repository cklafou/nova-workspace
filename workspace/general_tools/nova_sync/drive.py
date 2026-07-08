# Last updated: 2026-07-09 05:14:59
"""
drive.py -- Google Drive Workspace Mirror for Gemini Live Access
================================================================
Maintains an exact mirror of the workspace in Google Drive using diff-based sync.
Only uploads new/changed files and deletes removed ones -- never rebuilds from scratch.
Each file is uploaded as a native Google Doc so Gemini's Personal Context tool can
read it directly (Gemini cannot reliably fetch raw GitHub URLs, so Drive is the
channel that keeps it able to see Project Nova).

Restored + cleaned 2026-05-26: descriptions and section order updated to the current
architecture (nova_body / general_tools / SELF), excludes widened to skip churny
runtime data (logs/, audit_queue.json) and large binaries (models/, llama/).

Drive structure:
    Nova_Workspace/              <-- shared folder (ROOT_FOLDER_ID)
        GEMINI_INDEX.md          <-- Gemini's session manifest (rewritten every sync)
        workspace/               <-- exact clone of local workspace/
            memory/ ...
            nova_body/ ...
            general_tools/ ...
            SELF/ ...

Gemini permanent folder:
    https://drive.google.com/drive/folders/1GLW6qVm5PHp_xnSlEXlnZIBhhmixzFya

Trigger: nova_sync/watcher.py calls sync_to_drive() inside run_push_cycle(), so the
Drive mirror updates every time the GitHub push does -- both at once.
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

# Folders searched for the OAuth client-secret file. Google downloads it with a
# long default name (client_secret_<id>.apps.googleusercontent.com.json), so we
# match by pattern across these dirs rather than requiring an exact filename.
CLIENT_SECRETS_DIRS = [
    Path.home() / "OneDrive" / "Documents",
    Path.home() / "Documents",
    Path.home() / "Downloads",
    Path.home() / "Desktop",
]
CLIENT_SECRETS_PATHS = [d / "client_secrets.json" for d in CLIENT_SECRETS_DIRS]

SCOPES = ["https://www.googleapis.com/auth/drive"]

# Drive's API throws transient 500/503/rate-limit errors under load. The client
# retries these automatically with randomized exponential backoff when execute()
# is given num_retries — so a single blip mid-resync no longer aborts the run.
API_RETRIES = 5

# Never mirror: VCS internals, caches, screenshots, build output, model weights
# (models/ is sealed and 18GB+), and the llama runtime binaries.
EXCLUDE_DIRS     = {".git", "__pycache__", "node_modules", "screenshots",
                    "_build", "models", "llama"}
# Path-prefix excludes (relative to workspace root). logs/ is pure runtime churn
# and would re-trigger a sync every cycle, so it stays out of Gemini's mirror.
EXCLUDE_SUBPATHS = {"logs", "nova_body/backups", "general_tools/backups",
                    "agents/main/sessions"}
INCLUDE_EXTENSIONS = {".py", ".md", ".json", ".jsonl", ".txt", ".cmd", ".ps1", ".html"}
# Files that must never be uploaded -- secrets, sync bookkeeping, or large/churny data.
EXCLUDE_FILES    = {
    ".drive_sync_cache.json",
    "nova_config.json",         # local settings (may hold machine-specific config)
    "nova_drive_token.json",    # OAuth token -- must never leave the local machine
    "client_secrets.json",      # OAuth client secret
    "audit_queue.json",         # large, high-churn runtime queue -- not useful to Gemini
}
# Directory-name PREFIXES to skip (dynamic names that an exact match can't catch).
# The Nova app runs a Chrome --app window with a per-pid profile dir
# (.nova_app_profile_<pid>) created inside the workspace. Its files are locked
# SQLite/JSON; trying to read one to upload it HANGS the sync and locked the server
# (Cole, 2026-05-26). They're also worthless to Gemini. Skip any path part starting
# with one of these prefixes.
EXCLUDE_DIR_PREFIXES = (".nova_app_profile",)


# -- Auth ---------------------------------------------------------------------

def _get_client_secrets():
    # 1) exact name in the known dirs (back-compat)
    for p in CLIENT_SECRETS_PATHS:
        if p.exists():
            return p
    # 2) Google's default download name, anywhere in the known dirs (newest wins)
    matches = []
    for d in CLIENT_SECRETS_DIRS:
        if d.is_dir():
            matches += list(d.glob("client_secret*.json"))
    if matches:
        return max(matches, key=lambda p: p.stat().st_mtime)
    return None


def _connect():
    creds = None
    secrets_path = _get_client_secrets()
    if not secrets_path:
        print("[drive] ERROR: client_secrets.json not found in Documents/Downloads/Desktop.")
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
        if any(part.startswith(EXCLUDE_DIR_PREFIXES) for part in parts):
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
    results = service.files().list(q=query, fields="files(id)").execute(num_retries=API_RETRIES)
    files = results.get("files", [])

    if files:
        folder_id = files[0]["id"]
    else:
        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = service.files().create(body=metadata, fields="id").execute(num_retries=API_RETRIES)
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
    results = service.files().list(q=query, fields="files(id)").execute(num_retries=API_RETRIES)
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
        ).execute(num_retries=API_RETRIES)
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
        ).execute(num_retries=API_RETRIES)
        file_id = result["id"]
        _file_id_cache[f"{parent_id}/{name}"] = file_id
        return file_id


def _delete_file(service, file_id):
    try:
        service.files().delete(fileId=file_id).execute(num_retries=API_RETRIES)
    except Exception as e:
        print(f"[drive] Warning: could not delete file {file_id}: {e}")


# -- Gemini Index -------------------------------------------------------------

# Descriptions keyed by filename -- current architecture (nova_body/general_tools/SELF).
# Anything not listed falls back to a generic "<EXT> file" description.
FILE_DESCRIPTIONS = {
    # Root workspace files
    "AGENTS.md":       "Operating rules and agent behavior definitions",
    "NOVA.md":         "Nova's identity, soul, personality, and values",
    "TOOLS.md":        "Tool reference and exec patterns",
    "README.md":       "Project overview",
    # memory/
    "STATUS.md":       "Current project state and mission -- READ FIRST",
    "JOURNAL.md":      "Nova's running session log -- READ SECOND",
    "COLE.md":         "Who Cole is and Nova's notes about him",
    "Design_Principles.md": "Living best-practices Nova learns from (suggestions, not hard rules)",
    "cole_intent.json": "Latest standing directive from Cole (chat -> autonomy)",
    "autonomy_state.json": "Nova's persisted wake/sleep + focus + reflection state",
    "touch_state.json": "Touch sense snapshot -- what is interacting with Nova right now",
    # SELF/ (self-model)
    "00_START_HERE.md": "Auto-generated entry point into Nova's self-model",
    "01_identity.md":  "Who Nova is -- core identity",
    "02_how_i_work.md": "Operating rules, Priority 0, yield protocol, autonomy flow",
    "03_body_manifest.md": "Nova's body architecture (senses, cortex, motor)",
    "manifest.json":   "Generated body manifest -- parts, refs, drift flags",
    # general_tools/nova_sync
    "watcher.py":      "GitHub push + Drive sync + backup. Modes: --push, --pup, --full",
    "drive.py":        "Google Drive diff-based mirror for Gemini (this system)",
    "backup.py":       "Session snapshots on boot, weekly full backups",
    "dir_patch.py":    "Import-path auditor -- scans .py/.md for stale references",
    "build_manifest.py": "Regenerates SELF/ body manifest from the live tree",
    # general_tools/nova_chat (the chat server + clients)
    "server.py":       "Nova Chat FastAPI/WebSocket server + autonomy daemon",
    "tool_router.py":  "Safe tool dispatch for Nova (read/write/list/run + task board)",
    "transcript.py":   "Chat transcript -> model messages builder",
    "workspace_context.py": "Builds Nova's on-demand context block",
    # nova_body/nova_cortex
    "executive.py":    "Two-phase wake: reflect -> decide -> execute; board actions",
    "tasking.py":      "Id-keyed task board (status + progress log)",
    # nova_body/nova_senses
    "clock.py":        "Time-sense: stamps, since-human, scheduling helpers",
    "environment.py":  "Senses Cole's directive/typing + workspace change fingerprint",
    "touch.py":        "Touch sense -- what is interacting with Nova (viewers, agents)",
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
    lines.append("Run these steps at the start of every session in order:")
    lines.append("")
    lines.append("```")
    lines.append("Step 1: @Google Drive: Search for the folder 'Nova_Workspace'")
    lines.append("Step 2: @Google Drive: Search for 'workspace/general_tools/nova_sync/GEMINI_INDEX.md'")
    lines.append("Step 3: Use the Search Key column below for all subsequent file lookups.")
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
    lines.append("| NOVA.md | `workspace/NOVA.md` | Nova's identity and values |")
    lines.append("| 00_START_HERE.md | `workspace/SELF/core/00_START_HERE.md` | Entry into Nova's self-model |")
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
        if any(part.startswith(EXCLUDE_DIR_PREFIXES) for part in parts):
            continue
        if any(rel_str.startswith(sub) for sub in EXCLUDE_SUBPATHS):
            continue
        if path.suffix.lower() not in INCLUDE_EXTENSIONS:
            continue
        if path.name in EXCLUDE_FILES or path.name == "GEMINI_INDEX.md":
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

    # Other sections, in a friendly order
    section_order = ["memory", "SELF", "nova_body", "general_tools", "Tasking", "skills"]
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
    results = service.files().list(q=query, fields="files(id)").execute(num_retries=API_RETRIES)
    existing = results.get("files", [])

    if existing:
        service.files().update(fileId=existing[0]["id"], media_body=media).execute(num_retries=API_RETRIES)
    else:
        service.files().create(
            body={"name": "GEMINI_INDEX.md", "parents": [root_folder_id]},
            media_body=media,
            fields="id"
        ).execute(num_retries=API_RETRIES)

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
            print("[drive] No changes detected -- Drive already up to date.")
            _write_gemini_index(service, ROOT_FOLDER_ID)
            return True

        print(f"[drive] Syncing at {timestamp}: {len(to_upload)} to upload, {len(to_delete)} to delete...")

        uploaded = 0
        failed = 0
        for rel_str in to_upload:
            path = WORKSPACE_DIR / rel_str.replace("/", "\\")
            parts = Path(rel_str).parts
            try:
                content = path.read_text(encoding="utf-8")
            except Exception as e:
                content = f"[could not read: {e}]"
            try:
                parent_id = _ensure_folder_path(service, parts, workspace_id)
                _upsert_file(service, parts[-1], content, parent_id)
            except Exception as e:
                # One file failing (even after the client's backoff retries) must NOT
                # abort the whole resync. Leave it out of the cache so it's retried on
                # the next run, and keep going.
                failed += 1
                print(f"[drive]   SKIP (upload failed, will retry next run): {rel_str} -- {e}")
                continue
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
        msg = f"[drive] Done: {uploaded} uploaded, {deleted} deleted"
        if failed:
            msg += f", {failed} skipped (transient errors — will retry next run)"
        print(msg + ".")
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
    Run: python general_tools/nova_sync/drive.py --full
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
            ).execute(num_retries=API_RETRIES)
            files = results.get("files", [])
            if files:
                print("[drive] Deleting old workspace/ folder...")
                service.files().delete(fileId=files[0]["id"]).execute(num_retries=API_RETRIES)
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
