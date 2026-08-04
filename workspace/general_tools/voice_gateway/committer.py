# Last updated: 2026-08-05 08:11:24
# @nova-adjacent: voice_gateway — the sentence-committer. PURE PYTHON, no audio, no models,
#   no network: this is the one piece that carries real design intelligence, so it is the one
#   piece with unit tests (test_committer.py). Everything else is an adapter around it.
"""
committer.py — turn a stream (or a finished block) of Nova's text into SPEAKABLE units.

Why this exists
---------------
A voice reply cannot be a single 300-character blob handed to TTS — the listener waits for the
whole thing to synthesize before hearing a word, and the prosody of one giant utterance is flat.
Speech is sentences. This committer watches text arrive and emits a unit the moment a sentence
is complete, so TTS can speak sentence 1 while sentence 2 is still being written.

Two feed modes (the gateway chooses; default is the SAFE one):
  - "final":  feed() is called ONCE with the whole message_end content. The committer just
              splits it into sentences for natural TTS pacing. SAFE because the text has already
              passed Nova's witness gate server-side before message_end fired — nothing unaudited
              is ever spoken. This is the v1 default.
  - "stream": feed() is called with tokens AS they generate. First audio is far faster, but a
              sentence can be spoken BEFORE the witness has audited the full draft. Only sound
              for register "voice_fast" (casual turns the gateway flagged claim-free) or once a
              parallel/sentence-level witness exists. Opt-in via config.

The claim gate
--------------
An optional callable claim_gate(text)->bool marks a unit as claim-bearing (a number, a name, a
receipt-class assertion). In "final" mode this is advisory metadata (the whole reply was already
audited). In "stream" mode a future version can HOLD claim units until a sentence-level witness
clears them; v1 does not hold — it tags, so the gateway/logs can see what would have been held.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# A sentence terminator: . ! ? … (and repeats like ?! or ...), optionally followed by a closing
# quote or bracket, then whitespace or end-of-string. We do NOT break inside "3.5", "e.g.", or a
# mid-word ellipsis with no following space — those are the classic false boundaries.
_TERMINATOR = re.compile(
    r'(?<![A-Z])'                     # not right after a lone capital (initials: "J. Smith")
    r'[.!?…]+'                    # one or more terminators
    r'["\'”’)\]]*'          # optional closing quotes/brackets
    r'(?=\s|$)'                        # must be followed by whitespace or end
)
# Abbreviations that end in '.' but do NOT end a sentence.
_ABBREV = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "e.g", "i.e",
    "no", "fig", "gen", "col", "inc", "ltd", "co", "u.s", "a.m", "p.m", "approx",
}
# Soft clause boundaries — used only to avoid a very long first sentence delaying first audio.
_SOFT = re.compile(r'[,;:—–]\s')


@dataclass
class CommitUnit:
    text: str
    index: int
    is_claim: bool = False
    soft: bool = False          # True if flushed at a clause boundary, not a sentence end
    final: bool = False         # True if flushed by flush() at end-of-stream


@dataclass
class SentenceCommitter:
    """Accumulates text; emits CommitUnits at sentence (or, under pressure, clause) boundaries.

    min_chars       a candidate sentence shorter than this is held and merged forward, so
                    "Yeah." "No." fragments don't each become their own choppy utterance —
                    UNLESS it is the only thing said (flush emits whatever remains).
    max_buffer      if the buffer grows past this with no sentence end in sight, flush at the
                    last soft clause boundary so first audio is not hostage to one long sentence.
    claim_gate      optional callable(text)->bool tagging claim-bearing units.
    """
    min_chars: int = 7
    max_buffer: int = 220
    claim_gate: object = None
    _buf: str = ""
    _emitted: int = 0
    units: list = field(default_factory=list)

    # ── public API ───────────────────────────────────────────────────────────────────────
    def feed(self, text: str) -> list:
        """Add text; return any units that just became complete (possibly empty)."""
        if not text:
            return []
        self._buf += text
        out = []
        while True:
            unit = self._pop_ready()
            if unit is None:
                break
            out.append(unit)
        return out

    def flush(self) -> list:
        """End of stream: emit whatever remains as a final unit (even if short)."""
        rest = self._buf.strip()
        self._buf = ""
        if not rest:
            return []
        u = self._make(rest, final=True)
        return [u]

    # ── internals ────────────────────────────────────────────────────────────────────────
    def _pop_ready(self):
        """Pop one complete sentence from the front of the buffer, or None."""
        boundary = self._first_real_boundary(self._buf)
        if boundary is not None:
            head, self._buf = self._buf[:boundary], self._buf[boundary:]
            head = head.strip()
            # Merge tiny fragments forward: a SINGLE short word ("Yeah." "No." "Hmm.") with
            # more text behind it merges into the next sentence instead of becoming a choppy
            # stub. A multi-word short sentence ("Hey Cole." "Ship it?") is real speech and
            # stands on its own — the space is the tell.
            if len(head) < self.min_chars and " " not in head and self._buf.strip():
                self._buf = head + " " + self._buf.lstrip()
                return None
            if head:
                return self._make(head)
            return None
        # No sentence end. If the buffer is over budget, soft-flush at a clause boundary so a
        # long first sentence does not delay first audio.
        if len(self._buf) >= self.max_buffer:
            soft = self._last_soft_boundary(self._buf[: self.max_buffer])
            if soft is not None and soft >= self.min_chars:
                head, self._buf = self._buf[:soft], self._buf[soft:]
                head = head.strip()
                if head:
                    return self._make(head, soft=True)
        return None

    def _first_real_boundary(self, s: str):
        """Index just AFTER the first genuine sentence terminator, or None. Skips abbreviations
        and decimals."""
        for m in _TERMINATOR.finditer(s):
            end = m.end()
            # decimal like 3.5 — terminator sits between two digits
            if m.start() > 0 and end < len(s) and s[m.start() - 1].isdigit() and s[end:end + 1].isdigit():
                continue
            # abbreviation — the word right before the dot is a known abbrev
            word = re.search(r'([A-Za-z.]+)$', s[: m.start() + 1])
            if word and word.group(1).rstrip('.').lower() in _ABBREV:
                continue
            return end
        return None

    def _last_soft_boundary(self, s: str):
        idx = None
        for m in _SOFT.finditer(s):
            idx = m.end()
        return idx

    def _make(self, text: str, soft: bool = False, final: bool = False) -> CommitUnit:
        is_claim = False
        if self.claim_gate is not None:
            try:
                is_claim = bool(self.claim_gate(text))
            except Exception:
                is_claim = False
        u = CommitUnit(text=text, index=self._emitted, is_claim=is_claim, soft=soft, final=final)
        self._emitted += 1
        self.units.append(u)
        return u


def commit_block(text: str, **kw) -> list:
    """Convenience for 'final' mode: split a finished block into units in one call."""
    c = SentenceCommitter(**kw)
    out = c.feed(text)
    out += c.flush()
    return out
