#!/usr/bin/env python3
"""
REFERENT CHECK — does Nova talk ABOUT the person she is talking TO?

THE BUG (2026-07-19)
    "Forty-six is the number Cole heard me say earlier."      <- said straight to Cole
    "Cole caught it faster than I did, which is why he's better at this."
    "More of mine than Cole has, because he doesn't have a reason to be gentle."

    Not a personality flaw and not a model deficiency. Her context carried the LIVE turn and
    her ARCHIVED memory in byte-identical shape — both rendered "Cole: <text>" — so a message
    being spoken TO her looked exactly like a month-old record ABOUT her. The natural completion
    register for "Cole: ..." is narration, so she narrated. She even derived a coping rule for it
    in her own reflection: "third-person Cole is Claude, first-person Cole is Cole."

    Fixed by (a) directional live labels "Name -> you:", (b) an explicit ARCHIVE ONLY header on
    memory blocks, (c) a WHO YOU ARE TALKING TO section in her system prompt.

WHAT THIS DOES
    Scans chat sessions and flags Nova replies that refer to the CURRENT SPEAKER in the third
    person. Vocative address ("Nice catch, Cole.") is correct and is NOT flagged — the error is
    only ever talking ABOUT the person you are answering.

    Third person about someone NOT in the exchange is also correct and not flagged: if Cole asks
    about Claude, "he" is Claude and that is fine.

USAGE
    python _admin/referent_check.py                 # all sessions
    python _admin/referent_check.py --since 2026-07-19
    python _admin/referent_check.py --json out.json

EXIT  0 = clean.  1 = at least one referent error found.
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import re
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
SESSIONS = WS / "logs" / "chat_sessions"

# A name used as DIRECT ADDRESS — correct, never flagged.
#   "..., Cole."  |  "Cole, look at this"  |  "Hey Cole"  |  "Thanks Cole"
VOCATIVE_BEFORE = re.compile(
    r"([,;:—–-]\s*$)|(\b(hey|hi|yo|ok|okay|yeah|yep|nope|no|thanks|thank you|sorry|"
    r"look|listen|honestly|alright|right|well|man|dude)\s+$)", re.IGNORECASE)
VOCATIVE_AFTER = re.compile(r"^\s*[,.!?…]|^\s*$")

# A name used REFERENTIALLY — "Cole said", "Cole's board", "told Cole", "than Cole"
REFERENTIAL_AFTER = re.compile(
    r"^\s*('s\b|s'\b|\s+(is|was|are|were|has|have|had|does|did|do|"
    r"said|says|told|tells|heard|hears|asked|asks|wants|wanted|built|builds|caught|catches|"
    r"made|makes|gave|gives|thinks|thought|knows|knew|likes|liked|calls|called|"
    r"left|came|comes|went|goes|keeps|kept|spent|spends|needs|needed|"
    r"would|will|can|could|should|might|'ll\b|'d\b|'s\b))", re.IGNORECASE)
REFERENTIAL_BEFORE = re.compile(
    r"\b(to|for|with|from|about|than|like|told|asked|gave|showed|and|or|"
    r"because|since|while|what|that)\s+$", re.IGNORECASE)

# Third-person pronouns that, in a reply to a single addressee, almost certainly mean the addressee.
PRONOUN_RE = re.compile(r"\b(he|him|his|she|her|hers)\b", re.IGNORECASE)

# Names of the other participants — a third-person pronoun near one of these is legitimately
# about THEM, not about the addressee, so we don't flag it.
OTHERS = ("claude", "gemini", "nova", "opus", "fable")


def strip_noise(text: str) -> str:
    """Drop tool-call fences and result placeholders; they are machinery, not speech."""
    t = re.sub(r"```[a-zA-Z]*\s*.*?```", " ", text, flags=re.DOTALL)
    t = re.sub(r"\[`[^`]+` resulted in \d+ bytes\.\]", " ", t)
    t = re.sub(r"^\s*\[[^\]\n]{1,60}\]\s*$", " ", t, flags=re.MULTILINE)
    return t


def referent_errors(reply: str, speaker: str) -> list[str]:
    """Sentences in `reply` that refer to `speaker` in the third person."""
    text = strip_noise(reply)
    first = speaker.split()[0]
    hits = []
    for sent in re.split(r"(?<=[.!?])\s+|\n+", text):
        s = sent.strip()
        if not s:
            continue
        flagged = False
        for m in re.finditer(rf"\b{re.escape(first)}\b", s, re.IGNORECASE):
            before, after = s[:m.start()], s[m.end():]
            if VOCATIVE_BEFORE.search(before) or VOCATIVE_AFTER.match(after):
                continue                                    # direct address — fine
            if REFERENTIAL_AFTER.match(after) or REFERENTIAL_BEFORE.search(before):
                flagged = True
        # A bare he/him in a sentence that names no one else, inside a reply to one person,
        # is very likely the addressee being talked about.
        if not flagged and PRONOUN_RE.search(s) and not any(o in s.lower() for o in OTHERS):
            if re.search(rf"\b{re.escape(first)}\b", s, re.IGNORECASE):
                flagged = True
        if flagged:
            hits.append(s[:260])
    return hits


def load(path: str) -> list:
    op = gzip.open if path.endswith(".gz") else open
    try:
        with op(path, "rt", encoding="utf-8", errors="replace") as f:
            return [json.loads(l) for l in f if l.strip()]
    except Exception:
        return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="YYYY-MM-DD")
    ap.add_argument("--json")
    a = ap.parse_args()

    files = sorted(glob.glob(str(SESSIONS / "*_chat.jsonl*")))
    total_replies, errors = 0, []
    for path in files:
        rows = load(path)
        for i, m in enumerate(rows):
            if m.get("author") != "Nova":
                continue
            ts = str(m.get("timestamp", ""))
            if a.since and ts[:10] < a.since:
                continue
            prev = next((rows[j] for j in range(i - 1, -1, -1)
                         if rows[j].get("author") not in (None, "Nova", "System")), None)
            if not prev:
                continue
            speaker = prev.get("author", "")
            total_replies += 1
            for bad in referent_errors(str(m.get("content", "")), speaker):
                errors.append({"file": os.path.basename(path), "ts": ts,
                               "speaker": speaker, "sentence": bad})

    print(f"Scanned {total_replies} Nova replies across {len(files)} sessions"
          + (f" since {a.since}" if a.since else ""))
    print(f"Referent errors (third person about the person she is answering): {len(errors)}")
    rate = (100.0 * len(errors) / total_replies) if total_replies else 0.0
    print(f"Rate: {rate:.1f}% of replies\n")
    for e in errors[-25:]:
        print(f"  [{e['ts'][:19]}] replying to {e['speaker']}:")
        print(f"      {e['sentence']}")
    if a.json:
        Path(a.json).write_text(json.dumps(
            {"replies": total_replies, "errors": errors, "rate_pct": round(rate, 2)},
            indent=2), encoding="utf-8")
        print(f"\nwrote {a.json}")
    if errors:
        print("\n  Each of these was said straight to the person being described in third person.")
        print("  If these are all dated BEFORE the 2026-07-19 fix, that is expected — compare")
        print("  with --since to measure the fix rather than the history.")
    else:
        print("  Clean — every reply addressed its speaker in the second person.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
