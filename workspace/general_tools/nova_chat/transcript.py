# @nova: Persist shared chat transcripts and assemble current requests with stable cacheable instructions.
# Last updated: 2026-10-05 18:30:24
"""
Shared conversation transcript for Nova Group Chat.
Persists to logs/chat_sessions/ on every message.
"""

# Body-owned paths also work when this tool is launched directly.
import sys as _nova_path_sys
from pathlib import Path as _NovaPath
_nova_path_sys.path.insert(0, str(_NovaPath(__file__).resolve().parents[2] / 'nova_body'))
from nova_paths import body_path
import json
import os
import uuid
import threading
from datetime import datetime
from pathlib import Path

WORKSPACE_DIR = (
    Path(os.environ["NOVA_WORKSPACE"])
    if "NOVA_WORKSPACE" in os.environ
    else Path(__file__).parent.parent.parent
)
LOG_DIR = body_path('logs', workspace=WORKSPACE_DIR) / "chat_sessions"

# Visible at startup in server logs — confirms path is correct
print(f"[transcript] LOG_DIR = {LOG_DIR}")


class Transcript:
    def __init__(self, session_id: str = ""):
        self.messages = []
        self._lock = threading.Lock()         # serialises file writes across threads
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_path = LOG_DIR / f"{self.session_id}_chat.jsonl"
        self._fail_count = 0                  # consecutive persist failures
        print(f"[transcript] Session '{self.session_id}' → {self.log_path}")

    # ── Message add ────────────────────────────────────────────────────────────

    def add(self, author: str, content: str, directed_at: list = None,
            images: list = None, response_metadata: dict = None) -> dict:
        msg = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now().isoformat(),
            "author": author,
            "content": content,
            "directed_at": directed_at,
        }
        if images:
            msg["images"] = images   # [{dataUrl, name}] — stored as base64 in JSONL
        if isinstance(response_metadata, dict):
            # Store only public response attribution, never raw transport payloads or content twice.
            meta = {}
            for key in ("id", "run_id", "turn_id"):
                value = response_metadata.get(key)
                if isinstance(value, str) and 0 < len(value) <= 128:
                    meta[key] = value
            for key in ("segment_index", "input_revision"):
                value = response_metadata.get(key)
                if type(value) is int and value >= (1 if key == "segment_index" else 0):
                    meta[key] = value
            delivery = response_metadata.get("delivery")
            if isinstance(delivery, str) and delivery in {"delivered", "cancelled", "error", "empty", "suppressed", "unsolicited"}:
                meta["delivery"] = delivery
            requests, replies = response_metadata.get("request_ids"), response_metadata.get("reply_to_ids")
            if (isinstance(requests, list) and isinstance(replies, list) and len(requests) == len(replies) <= 512
                    and all(value is None or isinstance(value, str) and 0 < len(value) <= 128 for value in requests)
                    and all(isinstance(value, str) and 0 < len(value) <= 128 for value in replies)):
                meta.update(request_ids=list(requests), reply_to_ids=list(replies))
            audit = response_metadata.get("audit")
            if isinstance(audit, dict):
                meta["audit"] = {"status": audit.get("status") if isinstance(audit.get("status"), str) and audit.get("status") in
                    {"PASS", "CONCERN", "INCOMPLETE", "ERROR", "NOT_RUN"} else "NOT_RUN"}
                for key, cap in (("reason", 2000), ("source", 80), ("turn_id", 128)):
                    value = audit.get(key)
                    if isinstance(value, str): meta["audit"][key] = value[:cap]
                if type(audit.get("input_revision")) is int and audit["input_revision"] >= 0:
                    meta["audit"]["input_revision"] = audit["input_revision"]
            if meta:
                msg["response_metadata"] = meta
        with self._lock:
            self.messages.append(msg)
        self._persist(msg)
        return msg

    # ── Persistence ────────────────────────────────────────────────────────────

    def _persist(self, msg: dict):
        """
        Append one message to the JSONL log file.

        Never silently suppresses errors — every failure is printed so it
        shows up in the server ring buffer (/logs endpoint).

        After 3 consecutive failures, falls back to flush_all() which rewrites
        the entire file from in-memory messages using an atomic temp-file swap.
        Messages are always safe in self.messages even if disk writes fail.
        """
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)  # re-create if deleted
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")
            self._fail_count = 0
        except Exception as e:
            self._fail_count += 1
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[transcript] PERSIST ERROR #{self._fail_count} @ {ts}: {e!r}")
            print(f"[transcript]   path={self.log_path}")
            if self._fail_count >= 3:
                print(f"[transcript] 3 consecutive failures — attempting flush_all() recovery")
                self.flush_all()

    def flush_all(self):
        """
        Rewrite the entire JSONL log file from in-memory messages.

        Uses a temp file + atomic rename so a crash mid-write never corrupts
        an existing log.  Safe to call at any time.  Called automatically
        after 3 consecutive _persist failures, and by SessionManager on
        session activation to recover any messages that didn't make it to disk.
        """
        tmp = self.log_path.with_suffix(".tmp")
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with self._lock:
                snapshot = list(self.messages)
            with open(tmp, "w", encoding="utf-8") as f:
                for m in snapshot:
                    f.write(json.dumps(m, ensure_ascii=False) + "\n")
            tmp.replace(self.log_path)   # atomic on Windows (Python 3.3+)
            self._fail_count = 0
            print(f"[transcript] flush_all() OK — {len(snapshot)} messages → {self.log_path}")
        except Exception as e:
            print(f"[transcript] flush_all() FAILED: {e!r}")
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass

    # ── Read helpers ───────────────────────────────────────────────────────────

    def get_messages_since_last_response(self, ai_name: str) -> list:
        """
        Return all messages after the last message authored by ai_name.
        Returns all messages if ai_name has never spoken in this session.
        Used to build the catch-up context block for listener AIs.
        """
        last_idx = -1
        for i, msg in enumerate(self.messages):
            if msg["author"] == ai_name:
                last_idx = i
        if last_idx == -1:
            return list(self.messages)
        return self.messages[last_idx + 1:]

    def _now_block(self) -> str:
        """Keep the face's overridable clock hook while the body owns its wording."""
        from nova_runtime.conversation_context import now_block
        return now_block(self)

    def to_messages(self, ai_name: str, system_prefix: str = "",
                    workspace_context: str = "") -> list[dict]:
        """Delegate shared formatting; self._now_block remains monkeypatchable."""
        from nova_runtime.conversation_context import to_messages
        return to_messages(self, ai_name, system_prefix, workspace_context)

    def format_for_ai(self, ai_name: str, system_prefix: str = "",
                       workspace_context: str = "") -> str:
        """
        Legacy string-based format for AI clients that don't support structured message lists.
        """
        msgs = self.to_messages(ai_name, system_prefix, workspace_context)
        lines = []
        for m in msgs:
            content = m["content"]
            if isinstance(content, list):
                content = next((c["text"] for c in content if c["type"] == "text"), "")
            lines.append(f"### {m['role'].upper()}\n{content}")
        return "\n\n".join(lines)

    def get_recent(self, n: int = 20) -> list:
        return self.messages[-n:]
