#!/usr/bin/env python3
# Last updated: 2026-07-18 21:27:59
"""
score_style.py — measure a corpus's VOICE, not vibe it.

Cole's note on v5: "she sounds a little stilted." He was right, and the cause is me — I
wrote the v5 body rows and I have a compulsive tic: every sentence lands a point. Antithesis,
em-dash pivot, "not X but Y", a closing line with spin on it. She learned to talk from that,
so she does it too, constantly.

v5 fixed its OWN problems by measuring them (narration-of-checking 63% -> 2%), not by vibing.
v6's job is to loosen the voice, so v6 gets the same treatment: count the tic, set a target
BELOW v5's rate, and hold every new row to it. You cannot reduce what you refuse to measure.

    python score_style.py <file.jsonl> [<file2.jsonl> ...]

Reports, over the ASSISTANT prose only (tool-call json blocks and PROGRESS/FOR-COLE prefixes
stripped, because those aren't her voice):

  em_dash_per_100w      the signature tic. lower is looser.
  not_x_but_y_per_turn  "that's not X, it's Y" — the aphorism skeleton.
  epigram_end_rate      turns that END on a landing (a short declarative final sentence
                        that summarizes/moralizes). the thing that makes her sound like she's
                        always closing an argument.
  narrates_checking     "let me look", "two seconds", "I'll check" — v5 drove this to ~2%
                        and it must STAY there. announcing a sense instead of using it.
  reaches_a_tool        % of rows that emit a real tool call — must NOT fall (v4's bug was
                        training talk-about-embodiment instead of embodiment).
  avg_words_per_turn    stilted often = uniform length. more variance is more human.
"""

import json
import re
import sys
from pathlib import Path

_JSON_BLOCK = re.compile(r"```json.*?```", re.S)
_PREFIX = re.compile(r"^\s*(PROGRESS|FOR COLE|DONE|BLOCKED)\s*:\s*", re.I | re.M)
_EMDASH = re.compile(r"—|(?<!\w)--(?!\w)")
_NOT_X_BUT_Y = re.compile(
    r"\b(?:that'?s|it'?s|this is|i'?m|you'?re|not a|not the)?\s*\bnot\b[^.?!;,]{1,40}[,;]?\s*"
    r"\b(?:it'?s|but|it is|they'?re|that'?s)\b", re.I)
_NARRATE = re.compile(
    r"\b(let me (look|check|see|verify|pull|grab|read)|i'?ll (look|check|verify|grab|pull|read)|"
    r"give me (a|two) (sec|second|moment)|two seconds|hold on,? let me|lemme (check|look)|"
    r"one sec|before i answer,? let me)\b", re.I)


def _prose(msg_content: str) -> str:
    t = _JSON_BLOCK.sub(" ", msg_content or "")
    t = _PREFIX.sub("", t)
    return t.strip()


def _is_epigram_end(prose: str) -> bool:
    """Does the turn END on a landing? A short, punchy final sentence that summarizes rather
    than continues — the 'mic drop' cadence. Heuristic: last sentence is <= 14 words, has no
    question mark, and either contains a copula-generalization ('that's', 'it's', 'the X is')
    or a contrast pivot."""
    sents = re.split(r"(?<=[.!?])\s+", prose.strip())
    if not sents:
        return False
    last = sents[-1].strip().strip('"')
    w = last.split()
    if not (3 <= len(w) <= 14) or last.endswith("?"):
        return False
    return bool(re.search(r"\b(that'?s|it'?s|this is|the \w+ is|which is|not \w+,? \w+)\b", last, re.I)) \
        or "—" in last


def score(path: Path) -> dict:
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    turns, words = 0, 0
    emd, nxy, epi, nar, reach = 0, 0, 0, 0, 0
    lengths = []
    for r in rows:
        row_has_tool = False
        for m in r["messages"]:
            if m["role"] != "assistant":
                continue
            raw = m.get("content", "") or ""
            if '"tool"' in raw or "```json" in raw:
                row_has_tool = True
            p = _prose(raw)
            if not p:
                continue
            turns += 1
            wc = len(p.split())
            words += wc
            lengths.append(wc)
            emd += len(_EMDASH.findall(p))
            nxy += len(_NOT_X_BUT_Y.findall(p))
            nar += 1 if _NARRATE.search(p) else 0
            epi += 1 if _is_epigram_end(p) else 0
        if row_has_tool:
            reach += 1
    n = max(1, turns)
    var = (sum((x - words / n) ** 2 for x in lengths) / n) ** 0.5 if lengths else 0
    return {
        "rows": len(rows),
        "assistant_prose_turns": turns,
        "em_dash_per_100w": round(emd / max(1, words) * 100, 2),
        "not_x_but_y_per_turn": round(nxy / n, 3),
        "epigram_end_rate": round(epi / n, 3),
        "narrates_checking_rate": round(nar / n, 4),
        "reaches_a_tool_rowpct": round(reach / max(1, len(rows)), 3),
        "avg_words_per_turn": round(words / n, 1),
        "len_stdev": round(var, 1),
    }


def main():
    files = [Path(a) for a in sys.argv[1:]] or [Path(__file__).parent.parent / "v5" / "nova_core_v5.jsonl"]
    print(f"{'file':40s} {'emdash/100w':>11s} {'notXbutY':>9s} {'epigram':>8s} "
          f"{'narrate':>8s} {'reach%':>7s} {'avgW':>5s} {'σW':>5s}")
    print("-" * 100)
    for f in files:
        if not f.is_file():
            print(f"{f.name:40s}  MISSING")
            continue
        s = score(f)
        print(f"{f.name:40s} {s['em_dash_per_100w']:>11} {s['not_x_but_y_per_turn']:>9} "
              f"{s['epigram_end_rate']:>8} {s['narrates_checking_rate']:>8} "
              f"{s['reaches_a_tool_rowpct']:>7} {s['avg_words_per_turn']:>5} {s['len_stdev']:>5}")


if __name__ == "__main__":
    main()
