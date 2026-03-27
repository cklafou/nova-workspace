# Last updated: 2026-03-25
"""
tools/nova_logs/logger.py -- Nova's Unified Log Manager
=========================================================
All logging for the Nova project lives here.
Each section is clearly marked with what it logs and where files are saved.

Sections:
  1. AGENT TOOL LOGGER    -- Nova's physical actions (clicks, vision, errors)
  2. CHAT THOUGHT LOGGER  -- Nova's responses in nova_chat
  3. INDEX WRITER         -- Keeps Logger_Index.md current

Import style:
  from nova_logs.logger import log, log_thought, get_screenshot_dir
"""

import json
import time
import threading
from datetime import datetime
from pathlib import Path

# ── Paths (all absolute, resolved from this file's location) ──────────────────
# This file lives at tools/nova_logs/logger.py
# Workspace root is two levels up: tools/nova_logs -> tools -> workspace
_THIS_FILE      = Path(__file__).resolve()
_WORKSPACE_ROOT = _THIS_FILE.parents[2]

LOGS_ROOT         = _WORKSPACE_ROOT / "logs"
SESSIONS_ROOT     = LOGS_ROOT / "sessions"
CHAT_SESSIONS_DIR = LOGS_ROOT / "chat_sessions"
SCREENSHOTS_ROOT  = LOGS_ROOT / "screenshots"
PERSISTENT_ERRORS = LOGS_ROOT / "errors.jsonl"
INDEX_PATH        = _THIS_FILE.parent / "Logger_Index.md"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — AGENT TOOL LOGGER
# Logs Nova's physical actions: clicks, vision lookups, mentor calls, errors.
# Files saved to: logs/sessions/YYYY-MM-DD/<log_type>.jsonl
# Called by: nova_perception/eyes.py, nova_perception/vision.py,
#            nova_perception/explorer.py, nova_action/autonomy.py,
#            nova_action/hands.py, nova_advisor/mentor.py
# ═══════════════════════════════════════════════════════════════════════════════

class _AgentLogger:
    """Date-aware logger for Nova's tool activity. Thread-safe."""

    def __init__(self):
        self._lock         = threading.Lock()
        self._current_date = None
        self._session_dir  = None
        self._refresh_date()

    def _refresh_date(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._current_date:
            self._current_date = today
            self._session_dir  = SESSIONS_ROOT / today
            self._session_dir.mkdir(parents=True, exist_ok=True)
            (SCREENSHOTS_ROOT / today).mkdir(parents=True, exist_ok=True)

    def log(self, log_type: str, event: str, **kwargs):
        """
        Write one JSONL entry.
        log_type becomes the filename: 'actions' -> actions.jsonl
        """
        with self._lock:
            self._refresh_date()
            entry = {"timestamp": datetime.now().isoformat(), "event": event, **kwargs}
            log_file = self._session_dir / f"{log_type}.jsonl"
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
                _update_index()
            except Exception as e:
                try:
                    LOGS_ROOT.mkdir(parents=True, exist_ok=True)
                    with open(PERSISTENT_ERRORS, "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "timestamp": datetime.now().isoformat(),
                            "event": "logger_write_failed",
                            "log_type": log_type,
                            "error": str(e),
                        }) + "\n")
                except Exception:
                    pass

    def get_screenshot_dir(self) -> Path:
        with self._lock:
            self._refresh_date()
            d = SCREENSHOTS_ROOT / self._current_date
            d.mkdir(parents=True, exist_ok=True)
            return d


_agent_logger = _AgentLogger()


def log(log_type: str, event: str, **kwargs):
    """
    Log a Nova agent tool event.
    Writes to: logs/sessions/YYYY-MM-DD/<log_type>.jsonl

    Usage:
        log("actions", "click", target="Login button", result="ok")
        log("errors", "vision_fail", target="Trade button", attempt=3)
        log("mentor", "ask", question="Is this safe?", response="PROCEED")
    """
    _agent_logger.log(log_type, event, **kwargs)


def get_screenshot_dir() -> Path:
    """Returns today's dated screenshot folder (auto-created)."""
    return _agent_logger.get_screenshot_dir()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — CHAT THOUGHT LOGGER
# Logs Nova's responses in nova_chat for real-time visibility.
# Files saved to: logs/sessions/YYYY-MM-DD/nova_thoughts.jsonl
# Called by: tools/nova_chat/clients/nova.py
# ═══════════════════════════════════════════════════════════════════════════════

def log_thought(text: str, source: str = "nova_chat_client"):
    """
    Log one Nova chat response.
    Writes to: logs/sessions/YYYY-MM-DD/nova_thoughts.jsonl

    Usage (in nova.py on_done callback):
        from nova_logs.logger import log_thought
        log_thought(full_response)
    """
    try:
        today   = datetime.now().strftime("%Y-%m-%d")
        log_dir = SESSIONS_ROOT / today
        log_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts":      datetime.now().isoformat(),
            "author":  "Nova",
            "content": text,
            "source":  source,
        }
        with open(log_dir / "nova_thoughts.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        _update_index()
    except Exception:
        pass  # never crash the chat over logging


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — INDEX WRITER
# Keeps Logger_Index.md current. Called internally after every write.
# Files saved to: tools/nova_logs/Logger_Index.md
# ═══════════════════════════════════════════════════════════════════════════════

_index_lock        = threading.Lock()
_last_index_update = 0.0
_INDEX_THROTTLE    = 30.0  # seconds between index rewrites


def _update_index():
    """Rewrite Logger_Index.md. Throttled to avoid thrashing on rapid writes."""
    global _last_index_update
    now = time.time()
    with _index_lock:
        if now - _last_index_update < _INDEX_THROTTLE:
            return
        _last_index_update = now
        _write_index()


def _write_index():
    """Generate and write Logger_Index.md."""
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Discover existing session log files
        session_files: dict[str, list[str]] = {}
        if SESSIONS_ROOT.exists():
            for day_dir in sorted(SESSIONS_ROOT.iterdir(), reverse=True)[:7]:
                if day_dir.is_dir():
                    files = sorted(f.name for f in day_dir.glob("*.jsonl"))
                    if files:
                        session_files[day_dir.name] = files

        # Discover chat session files
        chat_files: list[str] = []
        if CHAT_SESSIONS_DIR.exists():
            chat_files = sorted(
                f.name for f in CHAT_SESSIONS_DIR.glob("*.jsonl")
            )[-5:]  # last 5

        lines = [
            "# Logger_Index.md -- Nova Logging Registry",
            f"_Auto-updated by tools/nova_logs/logger.py_",
            f"_Last updated: {ts}_",
            "",
            "## Log Types and Locations",
            "",
            "| Log Type | File | Location | Updated By |",
            "|----------|------|----------|------------|",
            "| Agent Actions | `actions.jsonl` | `logs/sessions/YYYY-MM-DD/` | `nova_perception/eyes.py`, `nova_action/hands.py` |",
            "| Agent Errors | `errors.jsonl` | `logs/sessions/YYYY-MM-DD/` | All agent tools on exception |",
            "| Vision Events | `vision.jsonl` | `logs/sessions/YYYY-MM-DD/` | `nova_perception/vision.py` |",
            "| Mentor Calls | `mentor.jsonl` | `logs/sessions/YYYY-MM-DD/` | `nova_advisor/mentor.py` |",
            "| Nova Chat Thoughts | `nova_thoughts.jsonl` | `logs/sessions/YYYY-MM-DD/` | `nova_chat/clients/nova.py` |",
            "| Chat Transcripts | `YYYY-MM-DD_HH-MM-SS_chat.jsonl` | `logs/chat_sessions/` | `nova_chat/session_manager.py` |",
            "| Session Index | `sessions_index.json` | `logs/chat_sessions/` | `nova_chat/session_manager.py` |",
            "| Persistent Errors | `errors.jsonl` | `logs/` | `nova_logs/logger.py` fallback |",
            "",
            "## Recent Session Logs",
            "",
        ]

        if session_files:
            for day, files in list(session_files.items())[:5]:
                lines.append(f"**{day}:** " + ", ".join(f"`{f}`" for f in files))
        else:
            lines.append("_No session logs yet._")

        lines += [
            "",
            "## Recent Chat Sessions",
            "",
        ]

        if chat_files:
            for f in chat_files:
                lines.append(f"- `logs/chat_sessions/{f}`")
        else:
            lines.append("_No chat sessions yet._")

        INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        INDEX_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


# Write index on import so it's always fresh when the module loads
_write_index()


if __name__ == "__main__":
    print(f"[nova_logs] Workspace root: {_WORKSPACE_ROOT}")
    print(f"[nova_logs] Logs root:      {LOGS_ROOT}")
    log("actions", "test_event", message="logger self-test")
    log_thought("This is a test thought from the logger self-test.")
    print(f"[nova_logs] Test entries written.")
    print(f"[nova_logs] Index: {INDEX_PATH}")
