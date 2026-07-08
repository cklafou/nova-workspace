# Last updated: 2026-07-08 21:01:20
"""
Shared conversation transcript for Nova Group Chat.
Persists to logs/chat_sessions/ on every message.
"""
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
LOG_DIR = WORKSPACE_DIR / "logs" / "chat_sessions"

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
            images: list = None) -> dict:
        msg = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now().isoformat(),
            "author": author,
            "content": content,
            "directed_at": directed_at,
        }
        if images:
            msg["images"] = images   # [{dataUrl, name}] — stored as base64 in JSONL
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

    def to_messages(self, ai_name: str, system_prefix: str = "",
                   workspace_context: str = "") -> list[dict]:
        """
        Returns a list of messages formatted for OpenAI-compatible APIs.
        NOTE: Qwen3.5's chat template enforces a single system message at the
        top. All context (workspace, personality) is merged into that one block.
        """
        messages = []

        system_content = system_prefix.strip()
        if workspace_context:
            system_content += f"\n\n--- WORKSPACE CONTEXT ---\n{workspace_context}\n--- END CONTEXT ---"
        messages.append({"role": "system", "content": system_content})

        for msg in self.messages:
            role = "assistant" if msg["author"] == ai_name else "user"
            content = msg["content"]

            # Formatting for Nova's internal pattern-matching
            if ai_name == "Nova" and msg["author"] == "Nova":
                import re as _re
                content = _re.sub(r'\[EXEC:[^\]]*\]', '[Nova ran a command]',
                                  content, flags=_re.IGNORECASE)
                content = _re.sub(r'\[WRITE:[^\]]*\].*?\[/WRITE\]', '[Nova wrote a file]',
                                  content, flags=_re.DOTALL | _re.IGNORECASE)
                content = _re.sub(r'\[READ:[^\]]*\]', '[Nova read a file]',
                                  content, flags=_re.IGNORECASE)

            if msg.get("images"):
                user_content = [{"type": "text", "text": content}]
                for img in msg["images"]:
                    user_content.append({"type": "image_url", "image_url": {"url": img["dataUrl"]}})
                messages.append({"role": role, "content": user_content})
            else:
                # User messages get author labels (Cole/Claude/Gemini need disambiguation).
                # Assistant messages (Nova's own turns) must NOT be prefixed — the chat
                # template already marks them as assistant, and prefixing trains the model
                # to start its own replies with "Nova:".
                if role == "assistant":
                    messages.append({"role": role, "content": content})
                else:
                    messages.append({"role": role, "content": f"{msg['author']}: {content}"})

        return messages

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
