"""
nova_chat/session_manager.py -- Persistent Session Management
=============================================================
Manages multiple chat sessions with compression for inactive ones.

- sessions_index.json: lightweight metadata for all sessions (always in RAM)
- Active session: Transcript in memory, raw .jsonl on disk
- Inactive sessions: compressed .jsonl.gz, zero RAM footprint

Only the user (Cole) can switch active sessions.
Switching: flush active -> compress -> decompress new -> load into memory.
"""
import gzip
import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from nova_chat.transcript import Transcript

WORKSPACE_DIR   = (
    Path(os.environ["NOVA_WORKSPACE"])
    if "NOVA_WORKSPACE" in os.environ
    else Path(__file__).parent.parent.parent
)
SESSIONS_DIR    = WORKSPACE_DIR / "logs" / "chat_sessions"
INDEX_PATH      = SESSIONS_DIR / "sessions_index.json"
MAX_NAME_CHARS  = 40


class SessionMeta:
    """Lightweight session metadata -- always kept in RAM."""
    def __init__(self, session_id: str, name: str = "", created: str = "",
                 last_active: str = "", message_count: int = 0, preview: str = ""):
        self.session_id   = session_id
        self.name         = name or f"Session {session_id[:6]}"
        self.created      = created or datetime.now().isoformat()
        self.last_active  = last_active or datetime.now().isoformat()
        self.message_count = message_count
        self.preview      = preview  # last message snippet

    def to_dict(self) -> dict:
        return {
            "session_id":    self.session_id,
            "name":          self.name,
            "created":       self.created,
            "last_active":   self.last_active,
            "message_count": self.message_count,
            "preview":       self.preview,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SessionMeta":
        return cls(**d)


class SessionManager:
    """
    Manages all chat sessions.
    One instance lives for the lifetime of the server process.
    """

    def __init__(self):
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, SessionMeta] = {}   # session_id -> meta
        self._active_id: str = ""
        self._active_transcript: Transcript | None = None

        self._load_index()

        # Resume most recent session, or create a fresh one
        if self._index:
            most_recent = max(self._index.values(), key=lambda m: m.last_active)
            self._activate(most_recent.session_id)
        else:
            self.new_session()

    # ── Index persistence ──────────────────────────────────────────────────────

    def _load_index(self):
        if INDEX_PATH.exists():
            try:
                data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
                for d in data:
                    meta = SessionMeta.from_dict(d)
                    # Only keep sessions that still have files on disk
                    if self._session_exists(meta.session_id):
                        self._index[meta.session_id] = meta
            except Exception as e:
                print(f"[sessions] Index load error: {e}")

    def _save_index(self):
        try:
            data = [m.to_dict() for m in self._index.values()]
            INDEX_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[sessions] Index save error: {e}")

    # ── File paths ─────────────────────────────────────────────────────────────

    def _jsonl_path(self, session_id: str) -> Path:
        return SESSIONS_DIR / f"{session_id}_chat.jsonl"

    def _gz_path(self, session_id: str) -> Path:
        return SESSIONS_DIR / f"{session_id}_chat.jsonl.gz"

    def _session_exists(self, session_id: str) -> bool:
        return (self._jsonl_path(session_id).exists() or
                self._gz_path(session_id).exists())

    # ── Compression ────────────────────────────────────────────────────────────

    def _compress(self, session_id: str):
        """Compress session JSONL to .gz and remove the raw file."""
        raw = self._jsonl_path(session_id)
        gz  = self._gz_path(session_id)
        if raw.exists():
            with open(raw, "rb") as f_in:
                with gzip.open(gz, "wb", compresslevel=6) as f_out:
                    shutil.copyfileobj(f_in, f_out)
            raw.unlink()

    def _decompress(self, session_id: str):
        """Decompress session .gz back to JSONL for reading."""
        raw = self._jsonl_path(session_id)
        gz  = self._gz_path(session_id)
        if gz.exists() and not raw.exists():
            with gzip.open(gz, "rb") as f_in:
                with open(raw, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

    # ── Session lifecycle ──────────────────────────────────────────────────────

    def new_session(self, name: str = "") -> str:
        """Create a new blank session, make it active. Returns session_id."""
        # Flush and compress current active session first
        self._flush_active()

        session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        meta = SessionMeta(session_id=session_id, name=name or "New Session")
        self._index[session_id] = meta
        self._save_index()

        self._active_id = session_id
        self._active_transcript = Transcript(session_id=session_id)
        print(f"[sessions] New session: {session_id}")
        return session_id

    def switch_session(self, session_id: str) -> bool:
        """
        Switch active session. Cole-only operation.
        Returns True on success, False if session not found.
        """
        if session_id == self._active_id:
            return True
        if session_id not in self._index:
            return False

        self._flush_active()
        self._activate(session_id)
        return True

    def _activate(self, session_id: str):
        """Load a session from disk into memory."""
        self._decompress(session_id)
        self._active_id = session_id
        self._active_transcript = Transcript(session_id=session_id)

        # Load existing messages from disk
        raw = self._jsonl_path(session_id)
        if raw.exists():
            try:
                with open(raw, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            msg = json.loads(line)
                            self._active_transcript.messages.append(msg)
            except Exception as e:
                print(f"[sessions] Load error for {session_id}: {e}")

        # Update last_active
        if session_id in self._index:
            self._index[session_id].last_active = datetime.now().isoformat()
            self._save_index()

        count = len(self._active_transcript.messages)
        print(f"[sessions] Activated {session_id} ({count} messages)")

    def _flush_active(self):
        """Compress the current active session to disk."""
        if self._active_id and self._active_id in self._index:
            self._compress(self._active_id)
        self._active_id = ""
        self._active_transcript = None

    def rename_session(self, session_id: str, new_name: str) -> bool:
        """Rename a session. Returns True on success."""
        if session_id not in self._index:
            return False
        self._index[session_id].name = new_name[:MAX_NAME_CHARS]
        self._save_index()
        return True

    def delete_session(self, session_id: str) -> bool:
        """Delete a session permanently. Cannot delete active session."""
        if session_id == self._active_id:
            return False
        if session_id not in self._index:
            return False
        self._jsonl_path(session_id).unlink(missing_ok=True)
        self._gz_path(session_id).unlink(missing_ok=True)
        del self._index[session_id]
        self._save_index()
        return True

    # ── Accessors ──────────────────────────────────────────────────────────────

    @property
    def active(self) -> Transcript:
        return self._active_transcript

    @property
    def active_id(self) -> str:
        return self._active_id

    def get_all_meta(self) -> list[dict]:
        """Return all session metadata sorted by last_active descending."""
        return [
            m.to_dict()
            for m in sorted(
                self._index.values(),
                key=lambda m: m.last_active,
                reverse=True
            )
        ]

    def update_meta_from_message(self, msg: dict):
        """Update session metadata after a new message is added."""
        if self._active_id not in self._index:
            return
        if not msg or "author" not in msg:
            return
        meta = self._index[self._active_id]
        meta.message_count = len(self._active_transcript.messages)
        meta.last_active   = datetime.now().isoformat()
        meta.preview       = msg.get("content", "")[:60]

        # Auto-name from first Cole message
        if (meta.name in ("New Session", f"Session {self._active_id[:6]}")
                and msg.get("author") == "Cole" and "content" in msg):
            meta.name = msg["content"][:MAX_NAME_CHARS]

        self._save_index()
