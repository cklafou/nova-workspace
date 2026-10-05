# Last updated: 2026-10-06 03:11:23
# @nova: Assemble shared body-owned conversation context with stable instructions, clock, author labels and images.
"""Provider formatting shared by faces and headless human conversation; no persistence or services."""
from copy import deepcopy
import re
import threading

_re_speaker = re.compile(r'^\s*\[[^\]\n]{1,40} is speaking to you\]\s*\n?', re.IGNORECASE)

def now_block(self) -> str:
    """The clock in every chat turn, after stable instructions. Ambient, not fetched.

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

    # Keep the changing clock/gap after stable instructions so prefix caching can reuse them.
    system_content = system_prefix.strip()
    if system_content:
        system_content += "\n\n"
    system_content += self._now_block()
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


class ConversationContext:
    """A private snapshot of authored messages using the same builder as the chat face."""
    def __init__(self, messages, *, now_block=None):
        self.messages = deepcopy(list(messages))
        self._lock = threading.Lock()
        self._clock_override = now_block

    def _now_block(self):
        if callable(self._clock_override):
            return self._clock_override()
        if self._clock_override is not None:
            return self._clock_override
        return now_block(self)

    def to_messages(self, ai_name, system_prefix="", workspace_context=""):
        return to_messages(self, ai_name, system_prefix, workspace_context)


def build_messages(messages, ai_name, system_prefix="", workspace_context="", *, now_block=None):
    return ConversationContext(messages, now_block=now_block).to_messages(ai_name, system_prefix, workspace_context)
