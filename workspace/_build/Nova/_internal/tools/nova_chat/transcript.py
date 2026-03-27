"""
Shared conversation transcript for Nova Group Chat.
Persists to logs/chat_sessions/ on every message.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path

WORKSPACE_DIR = Path(__file__).parent.parent.parent
LOG_DIR = WORKSPACE_DIR / "logs" / "chat_sessions"

class Transcript:
    def __init__(self, session_id: str = ""):
        self.messages = []
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_path = LOG_DIR / f"{self.session_id}_chat.jsonl"

    def add(self, author: str, content: str, directed_at: list = None) -> dict:
        msg = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now().isoformat(),
            "author": author,
            "content": content,
            "directed_at": directed_at,
        }
        self.messages.append(msg)
        self._persist(msg)
        return msg

    def _persist(self, msg: dict):
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(msg) + "\n")
        except Exception:
            pass

    def format_for_ai(self, ai_name: str, system_prefix: str = "",
                       workspace_context: str = "") -> str:
        """
        Returns system prompt string for injection into an AI API call.
        Includes workspace file context when provided.
        """
        lines = []
        for msg in self.messages:
            ts = msg["timestamp"][11:16]  # HH:MM
            directed = ""
            if msg.get("directed_at"):
                directed = f" [@{', @'.join(msg['directed_at'])}]"
            lines.append(f"[{ts}] {msg['author']}{directed}: {msg['content']}")

        transcript_text = "\n".join(lines) if lines else "(conversation just started)"

        workspace_block = ""
        if workspace_context:
            workspace_block = f"\n\n{workspace_context}\n"

        system = f"""{system_prefix}{workspace_block}

--- CURRENT CONVERSATION ---
{transcript_text}
--- END CONVERSATION ---

You are {ai_name}. Respond naturally to the latest message.
Be concise -- this is a live group chat, not an essay prompt.
If asked about a file, refer to the workspace context above -- never guess contents.
Do NOT prefix your response with your name or a label."""

        return system.strip()

    def get_recent(self, n: int = 20) -> list:
        return self.messages[-n:]
