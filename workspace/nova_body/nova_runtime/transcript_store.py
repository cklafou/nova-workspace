# Last updated: 2026-06-22 18:56:08
# @nova: Runtime transcript store — her runtime's own view of the conversation.
#        A face WRITES messages in (append); her runtime READS them (has_unread_cole,
#        recent) to perceive whether Cole has spoken, WITHOUT depending on the chat
#        server's in-memory state. Backed by JSONL so it survives restart and a face
#        detaching/reattaching. This is seam #4 of the runtime extraction — the quiet
#        one — so the "did Cole speak / have I answered" rule is made race-proof here.
"""
nova_runtime/transcript_store.py

The hard problem (auditor's flagged seam): the runtime must know "has Cole spoken that
I haven't answered?" without drifting from what the face actually recorded. Position-based
logic ("is the last Cole message after my last message?") breaks in one quiet way: if Cole
sends a message WHILE Nova is mid-answer, his message lands in the log *after* her answer,
so position-logic thinks she already answered it — and she silently never does.

The fix: don't infer "answered" from position. Track an explicit, runtime-owned marker
`attended_through` = the highest Cole sequence number Nova has actually attended with a
SUBSTANTIVE reply. The daemon advances it (only on a real answer, only up to the latest
Cole message that existed when the tick BEGAN). Then:

        has_unread_cole()  ==  last Cole seq  >  attended_through

This one rule is correct for every case we care about:
  • normal Q→A           — answer advances the marker past Cole's msg → not unread.
  • hollow/empty answer  — marker NOT advanced (no substantive reply) → still unread → retry.
  • message mid-tick     — marker only reaches the tick-start latest, so a msg that arrived
                           during the tick stays unread → she wakes to it (the quiet bug, fixed).
  • rapid messages       — all logged in order; one answer advances the marker to the latest.
  • restart / detach     — both the log and the marker are persisted, so she resumes without
                           re-answering old messages or losing new ones.

Concurrency note: a single in-process daemon is serialised by the host's `is_processing`
guard, so two ticks never answer at once. This store adds the cross-tick / cross-restart
correctness on top of that.
"""

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)


class TranscriptStore:
    def __init__(self, log_path, state_path=None):
        """log_path  — JSONL of messages (the durable conversation; the face appends here).
        state_path — runtime-owned sidecar holding `attended_through` (defaults next to log)."""
        self.log_path = Path(log_path)
        self.state_path = Path(state_path) if state_path else \
            self.log_path.with_name(self.log_path.stem + ".runtime_state.json")
        self._lock = threading.Lock()
        self.messages: list[dict] = []
        self.attended_through: int = -1     # highest Cole seq answered substantively
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    # ── load / persist ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Read the message log + the attended marker from disk (resume after restart)."""
        self.messages = []
        if self.log_path.exists():
            with open(self.log_path, encoding="utf-8") as f:
                for seq, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        m = json.loads(line)
                        m["seq"] = seq          # seq = position in the durable log
                        self.messages.append(m)
                    except Exception:
                        continue
        if self.state_path.exists():
            try:
                self.attended_through = int(json.loads(
                    self.state_path.read_text(encoding="utf-8")).get("attended_through", -1))
            except Exception:
                self.attended_through = -1

    def reload_from_disk(self) -> None:
        """Re-read the log so the runtime sees messages a separate face process appended.
        Cheap enough to call before each unread check; keeps runtime and face in sync."""
        with self._lock:
            self._load()

    def _persist_state(self) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"attended_through": self.attended_through}, indent=2),
                       encoding="utf-8")
        tmp.replace(self.state_path)            # atomic

    # ── write (face side) ─────────────────────────────────────────────────────────

    def append(self, author: str, content: str, directed_at=None, images=None) -> dict:
        """Record one message. Returns it (with its assigned seq). The face calls this;
        the runtime only reads."""
        with self._lock:
            seq = len(self.messages)
            msg = {"seq": seq, "timestamp": datetime.now().isoformat(),
                   "author": author, "content": content, "directed_at": directed_at}
            if images:
                msg["images"] = images
            self.messages.append(msg)
            # Persist the message itself WITHOUT the runtime-only "seq" field, so the log
            # stays compatible with the existing chat transcript format (seq is derived).
            on_disk = {k: v for k, v in msg.items() if k != "seq"}
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(on_disk, ensure_ascii=False) + "\n")
        return msg

    # ── read (runtime side) ───────────────────────────────────────────────────────

    @staticmethod
    def is_substantive(msg: dict, author: str) -> bool:
        """True if `msg` is a real, content-bearing turn by `author` (think-only or empty
        turns don't count — the empty-bubble lesson). Used by the daemon to decide whether
        a wake actually produced an answer worth advancing the marker for."""
        if msg.get("author") != author:
            return False
        stripped = _THINK_RE.sub("", msg.get("content", "") or "")
        return bool(stripped.strip())

    def last_seq(self, author: str) -> int:
        """Seq of the most recent message by `author`, or -1 if none."""
        for m in reversed(self.messages):
            if m.get("author") == author:
                return m["seq"]
        return -1

    def latest_seq(self) -> int:
        """Seq of the most recent message of any author, or -1 if empty."""
        return self.messages[-1]["seq"] if self.messages else -1

    def has_unread_cole(self, speaker: str = "Cole") -> bool:
        """THE rule: is there a `speaker` message newer than what Nova has attended?
        Pure position is deliberately NOT used — see module docstring."""
        return self.last_seq(speaker) > self.attended_through

    def mark_attended_through(self, seq: int) -> None:
        """Daemon calls this AFTER a substantive answer, passing the latest Cole seq that
        existed when the tick began (NOT the current latest — a message that arrived mid-tick
        must stay unread). Monotonic; never moves backward."""
        with self._lock:
            if seq > self.attended_through:
                self.attended_through = seq
                self._persist_state()

    def recent(self, n: int = 14) -> list[dict]:
        """The last n messages, oldest→newest — the perception the daemon hands cognition."""
        return self.messages[-n:]
