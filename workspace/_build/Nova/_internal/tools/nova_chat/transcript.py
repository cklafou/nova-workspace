"""
Shared conversation transcript for Nova Group Chat.
Persists to logs/chat_sessions/ on every message.
"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

WORKSPACE_DIR = (
    Path(os.environ["NOVA_WORKSPACE"])
    if "NOVA_WORKSPACE" in os.environ
    else Path(__file__).parent.parent.parent
)
LOG_DIR = WORKSPACE_DIR / "logs" / "chat_sessions"

class Transcript:
    def __init__(self, session_id: str = ""):
        self.messages = []
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_path = LOG_DIR / f"{self.session_id}_chat.jsonl"
        self._persist_error_logged = False  # suppress repeated persist errors

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
        self.messages.append(msg)
        self._persist(msg)
        return msg

    def _persist(self, msg: dict):
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(msg) + "\n")
        except Exception as e:
            # Only log the first error to avoid spam if log dir disappears mid-session
            if not self._persist_error_logged:
                print(f"[transcript] Persist error: {e}")
                self._persist_error_logged = True

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

    def format_for_ai(self, ai_name: str, system_prefix: str = "",
                       workspace_context: str = "") -> str:
        """
        Returns system prompt string for injection into an AI API call.
        Includes workspace file context when provided.

        For listener AIs (Claude/Gemini), appends a focused catch-up block
        showing only the messages since their last response, so they don't
        need to re-process the full history to understand what's new.
        """
        # Full conversation transcript
        lines = []
        for msg in self.messages:
            ts = msg["timestamp"][11:16]  # HH:MM
            directed = ""
            if msg.get("directed_at"):
                directed = f" [@{', @'.join(msg['directed_at'])}]"
            content = msg["content"]
            # For Nova's own context: replace raw directives with human-readable notes
            # so Nova doesn't pattern-match and repeat them in her next message.
            if ai_name == "Nova" and msg["author"] == "Nova":
                import re as _re
                content = _re.sub(
                    r'\[DISCORD:\s*(.*?)\]',
                    lambda m: f'[Nova sent Discord: "{m.group(1).strip()[:60]}"]',
                    content, flags=_re.DOTALL | _re.IGNORECASE
                )
                content = _re.sub(r'\[EXEC:[^\]]*\]', '[Nova ran a command]',
                                  content, flags=_re.IGNORECASE)
                content = _re.sub(r'\[WRITE:[^\]]*\].*?\[/WRITE\]', '[Nova wrote a file]',
                                  content, flags=_re.DOTALL | _re.IGNORECASE)
                content = _re.sub(r'\[READ:[^\]]*\]', '[Nova read a file]',
                                  content, flags=_re.IGNORECASE)
            if msg.get("images"):
                n_imgs = len(msg["images"])
                content += f" [attached: {n_imgs} image{'s' if n_imgs > 1 else ''}]"
            lines.append(f"[{ts}] {msg['author']}{directed}: {content}")

        transcript_text = "\n".join(lines) if lines else "(conversation just started)"

        workspace_block = ""
        if workspace_context:
            workspace_block = f"\n\n{workspace_context}\n"

        # Catch-up block: only for listener AIs that have spoken before
        catch_up_block = ""
        if ai_name in ("Claude", "Gemini"):
            missed = self.get_messages_since_last_response(ai_name)
            # Only add catch-up if there are new messages AND not all messages are new
            # (i.e., AI has spoken before and there's something new to catch up on)
            if missed and len(missed) < len(self.messages):
                missed_lines = []
                for msg in missed:
                    ts = msg["timestamp"][11:16]
                    directed = ""
                    if msg.get("directed_at"):
                        directed = f" [@{', @'.join(msg['directed_at'])}]"
                    mc = msg["content"]
                    if msg.get("images"):
                        mc += f" [attached: {len(msg['images'])} image(s)]"
                    missed_lines.append(f"[{ts}] {msg['author']}{directed}: {mc}")
                catch_up_block = (
                    "\n\n--- MESSAGES SINCE YOUR LAST RESPONSE (focus here) ---\n"
                    + "\n".join(missed_lines)
                    + "\n--- END CATCH-UP (full conversation above for reference) ---"
                )

        system = f"""{system_prefix}{workspace_block}

--- CURRENT CONVERSATION ---
{transcript_text}
--- END CONVERSATION ---{catch_up_block}

You are {ai_name}. Respond naturally to the latest message.
Be concise -- this is a live group chat, not an essay prompt.
If asked about a file, refer to the workspace context above -- never guess contents.
Do NOT prefix your response with your name or a label."""

        return system.strip()

    def get_recent(self, n: int = 20) -> list:
        return self.messages[-n:]
