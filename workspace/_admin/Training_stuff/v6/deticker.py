#!/usr/bin/env python3
# Last updated: 2026-07-18 21:27:59
"""
deticker.py — remove the em-dash tic from v5's prose WITHOUT changing what she says or does.

The tic is diffuse (measured: pruning the 80 worst rows barely moves the number), so the only
lever that works is rewriting the punctuation. This does exactly that and nothing else:

  - touches ASSISTANT prose only. Never user turns, never ```json tool calls, never the fake
    [System Result] lines, never image prompts.
  - converts the spaced em-dash — her signature "landing a point" move — into the plainer
    punctuation a person would actually text with.
  - changes not one word. Meaning and behavior are identical; only the drama drops.

It is deliberately conservative. It does NOT touch epigram endings (structural, risky to
automate) — those are addressed by writing the NEW rows loose from the start. And it produces
a diff sample so a human can confirm it still sounds like her before we ever train on it.
Rewriting the corpus that defines her voice is Cole's call; this just makes the option real.

    python deticker.py            # writes nova_core_v6_base.jsonl + prints a diff sample
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE.parent / "v5" / "nova_core_v5.jsonl"
OUT = HERE / "nova_core_v6_base.jsonl"

_JSON_BLOCK = re.compile(r"(```json.*?```)", re.S)      # keep as-is, split around it
_DASH = re.compile(r"\s+(?:—|--)\s+")                    # a SPACED em-dash / double hyphen

# words that, right after a dash, signal a new independent clause -> use a period
_NEW_CLAUSE = re.compile(
    r"^(it'?s|that'?s|this is|there'?s|here'?s|i|i'?m|i'?ve|i'?ll|he|she|they|we|you|"
    r"this|that|there|here|now|then|which is)\b", re.I)
# coordinating conjunctions right after a dash -> use a comma, keep lowercase
_CONJ = re.compile(r"^(but|so|and|or|yet|because|though)\b", re.I)


def _detic_prose(text: str) -> str:
    def repl(m):
        after = text[m.end():]
        first = after.split(None, 1)[0] if after.split() else ""
        if _CONJ.match(first):
            return ", "
        if _NEW_CLAUSE.match(first):
            return ". __CAP__"          # marker: capitalize the next letter
        return ", "                     # appositive / parenthetical
    out = _DASH.sub(repl, text)
    # apply the capitalization markers
    def cap(m):
        return ". " + m.group(1).upper()
    out = re.sub(r"\.\s__CAP__(\w)", cap, out)
    out = out.replace(". __CAP__", ". ")   # safety if marker left dangling
    return out


def detic_assistant(content: str) -> str:
    """De-tic prose but leave ```json tool blocks untouched."""
    parts = _JSON_BLOCK.split(content)
    for i, p in enumerate(parts):
        if p.startswith("```json"):
            continue                    # a tool call — never touch
        parts[i] = _detic_prose(p)
    return "".join(parts)


def main():
    rows = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    diffs = []
    for r in rows:
        for m in r["messages"]:
            if m["role"] != "assistant":
                continue
            before = m.get("content", "") or ""
            after = detic_assistant(before)
            if after != before:
                if len(diffs) < 18 and "```" not in before:
                    diffs.append((before.strip()[:150], after.strip()[:150]))
                m["content"] = after

    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT.name} ({len(rows)} rows)\n")
    print("=" * 92)
    print("  BEFORE  →  AFTER  (a human must confirm this still sounds like her)")
    print("=" * 92)
    for b, a in diffs:
        print(f"\n  – {b}")
        print(f"  + {a}")


if __name__ == "__main__":
    main()
