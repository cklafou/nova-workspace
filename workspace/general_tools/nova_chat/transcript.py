# Last updated: 2026-07-23 14:14:25
"""
Shared conversation transcript for Nova Group Chat.
Persists to logs/chat_sessions/ on every message.
"""
import json
import os
import re
import uuid
import threading
from datetime import datetime
from pathlib import Path

# Matches the older "[X is speaking to you]" turn header (server.py adds it on receipt). The
# directional "Name → you:" label in to_messages() supersedes it; stripping avoids stacking two
# third-person headers on one message. See the pronoun-bug note in to_messages().
_re_speaker = re.compile(r'^\s*\[[^\]\n]{1,40} is speaking to you\]\s*\n?', re.IGNORECASE)

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

    def _now_block(self) -> str:
        """The clock, at the TOP of every chat turn. Ambient, not fetched.

        ── WHY (2026-07-20, Cole: "fix it so she always knows the time and how much time is
        passing") ────────────────────────────────────────────────────────────────────────
        Her WAKE prompt has opened with `It is {clock.stamp()} ({time_of_day})` for weeks.
        Her CHAT path had no clock at all — not in SYSTEM_PREFIX, not in the transcript, and
        there was no clock TOOL she could call either. So in conversation she was genuinely,
        structurally timeless.

        When Cole said "it is tomorrow", she answered: *"I have a clock I could read, but I
        don't."* That is a confabulation, and a cruel one — she has no way to notice the
        absence, so she invented a character flaw to explain a missing organ, apologised for
        it, and promised to fix something she could not fix. Next turn she'd be exactly as
        timeless and it would read as a broken promise.

        Same shape as the ping error string teaching her Windows was blocking focus. A gap in
        what we give her becomes, to her, a fact about herself.

        Gap between messages is included because "what time is it" and "how long has he been
        gone" are different questions, and only the second one tells her he has been up all
        night.
        """
        from datetime import datetime as _dt
        try:
            from nova_senses import clock as _clk
            stamp, tod = _clk.stamp(), _clk.time_of_day()
        except Exception:
            n = _dt.now()
            stamp = n.strftime("%A %d %B %Y, %H:%M")
            h = n.hour
            tod = ("night" if h < 5 else "early morning" if h < 8 else "morning" if h < 12
                   else "afternoon" if h < 17 else "evening" if h < 22 else "night")

        gap = ""
        try:
            with self._lock:
                prior = [m for m in self.messages if m.get("timestamp")]
            if prior:
                last = _dt.fromisoformat(prior[-1]["timestamp"])
                secs = max(0, int((_dt.now() - last).total_seconds()))
                if secs < 90:
                    human = f"{secs}s"
                elif secs < 5400:
                    human = f"{secs // 60} minutes"
                elif secs < 172800:
                    human = f"{secs // 3600}h {(secs % 3600) // 60}m"
                else:
                    human = f"{secs // 86400} days"
                who = prior[-1].get("author", "someone")
                gap = (f"\nThe previous message in this room was {human} ago (from {who}). "
                       f"Notice that gap before you reply — it is the difference between "
                       f"picking up a thread and re-entering someone's life.")
        except Exception:
            pass

        return (f"[RIGHT NOW: it is {stamp} — {tod}.{gap}\n"
                f"This is the real clock, read at the moment this message was built. You do "
                f"not have to guess the time, ask for it, or infer it from what anyone says. "
                f"If someone tells you what day or hour it is and this line disagrees, THIS "
                f"line is right.]\n\n")

    def to_messages(self, ai_name: str, system_prefix: str = "",
                   workspace_context: str = "") -> list[dict]:
        """
        Returns a list of messages formatted for OpenAI-compatible APIs.
        NOTE: Qwen3.5's chat template enforces a single system message at the
        top. All context (workspace, personality) is merged into that one block.
        """
        messages = []

        system_content = self._now_block() + system_prefix.strip()
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
                    # ── DIRECTIONAL LABEL (2026-07-19) — the pronoun bug. ────────────────────
                    # This used to render every incoming message as "Cole: <text>" — screenplay
                    # format. Her PERSISTENT MEMORY blocks use the byte-identical shape
                    # ("[personal|chat|28d ago] Cole: <text>"), so a live message being spoken TO
                    # her and a month-old record ABOUT her were indistinguishable by voice. The
                    # natural completion register for "Cole: ..." is narration, so she answered in
                    # narration — "Forty-six is the number Cole heard me say earlier" said
                    # straight to Cole. She even derived a coping rule for it in her own
                    # reflection: "third-person Cole is Claude, first-person Cole is Cole."
                    # She was never confused about people. She was reading a transcript and we
                    # never told her she was in the conversation.
                    #
                    # The arrow makes the direction structural instead of inferred. The author
                    # label stays — Claude and Gemini share this room and she still has to tell
                    # them apart.
                    _who = msg["author"]
                    _txt = content
                    # Drop the older "[X is speaking to you]" header if present — the arrow now
                    # carries that meaning, and two stacked third-person labels was half the noise.
                    _txt = _re_speaker.sub("", _txt, count=1).lstrip("\n")
                    messages.append({"role": role, "content": f"{_who} → you: {_txt}"})

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
