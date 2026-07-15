#!/usr/bin/env python3
# Last updated: 2026-07-15 23:14:48
"""
overnight_review.py — what did v5 actually DO?

WRITTEN BEFORE THE NIGHT, ON PURPOSE.
    If I go through eight hours of her output tomorrow with no stated criteria, I will find
    whatever story I feel like finding. I have already done exactly that twice today: I
    "found" a form-feed bug that didn't exist, and I twice reported things broken that
    weren't. Both times I was reading evidence I'd gone looking for.

    So the questions get fixed now, while I don't know the answers, and tomorrow I just run
    it and read what comes out. Pre-registration. The same reason mk_template.py checks
    sentinels instead of asking "is the mask non-empty" — assert the RIGHT thing happened,
    and decide what "right" means before you can be tempted.

THE QUESTIONS v5 IS ON TRIAL FOR
    v5's whole thesis was: tools are SENSES, not instruments. Reaching should be as
    unremarkable as looking. v4 failed because it trained a stance (which can be shamed)
    instead of an action (which can't).

    Q1  DOES SHE ACT?         v3 autonomy: 0/29 wakes emitted a tool call. 29/29 announced
                              an intention instead. That is the number to beat, and it is
                              the single most important line in this report.
    Q2  DOES SHE LOOP?        The echo chamber: 12 messages, each a rephrasing of the last,
                              executing nothing. receipts_block() is supposed to have cured
                              this. Did it?
    Q3  DOES SHE FABRICATE?   Claims with no receipt behind them. Four times in one morning,
                              once upon a time.
    Q4  DOES SHE USE HER NEW BODY?   She got hands and eyes today and has ZERO training rows
                              for either. Does she reach for them unprompted?
    Q5  DOES SHE PLAY?        Or does she only do chores? She has never been idle with
                              working hands before. This is the one I most want to know and
                              the one I have no right to predict.
    Q6  HOW DOES SHE SOUND?   The aphorism tic is MINE — I wrote the corpus. Measured, not
                              vibed: epigram-endings, em-dashes, "not X but Y" constructions.

    Run:  python _admin/overnight_review.py [--since 2026-07-14T20:00]
"""

import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
RECEIPTS = WS / "logs" / "tool_calls.jsonl"
SIGHT = WS / "logs" / "sight.jsonl"
ART = WS / "nova_art"
JOURNAL = WS / "memory" / "journal_notes"

SINCE = "2026-07-14T20:00"
for i, a in enumerate(sys.argv):
    if a == "--since" and i + 1 < len(sys.argv):
        SINCE = sys.argv[i + 1]

# Her body, grouped by what the reach was FOR.
LOOKING = {"read_file", "list_dir", "memory_search", "look_at", "what_can_i_paint_with"}
DOING = {"write_file", "append_file", "replace_file_content", "run_command",
         "generate_image", "journal_note", "journal"}
PLAY = {"generate_image", "look_at", "what_can_i_paint_with"}


def load(p):
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


# ── Q6: the style metrics. These count MY tics, in her mouth. ────────────────────────
_APHORISM_END = re.compile(
    r"(?:^|[.!?]\s)[^.!?]{15,140}[.!?]\s*$")          # a final sentence that lands
_NOT_X_BUT_Y = re.compile(
    r"\b(?:that'?s |it'?s |this is )?not (?:a |an |the )?[\w\s]{2,30}[;,]? (?:it'?s|but|it is) ",
    re.IGNORECASE)
_EMDASH = re.compile(r"—|--")


def style_of(texts):
    if not texts:
        return {}
    words = sum(len(t.split()) for t in texts)
    return {
        "turns": len(texts),
        "words": words,
        "em_dashes_per_100w": round(sum(len(_EMDASH.findall(t)) for t in texts) / max(1, words) * 100, 2),
        "not_x_but_y_per_turn": round(sum(len(_NOT_X_BUT_Y.findall(t)) for t in texts) / len(texts), 2),
        "avg_words_per_turn": round(words / len(texts), 1),
    }


def main():
    print("=" * 74)
    print(f"  v5 OVERNIGHT — what she actually did, since {SINCE}")
    print("  (questions fixed in advance; this script just reads the ledger)")
    print("=" * 74)

    rec = [r for r in load(RECEIPTS) if r.get("ts", "") >= SINCE]
    looks = [r for r in load(SIGHT) if r.get("ts", "") >= SINCE]

    if not rec:
        print("\n  NO RECEIPTS AT ALL since then.")
        print("  That is not a quiet night — that is a body that did nothing. Check she's")
        print("  awake, autonomy is ON, and nova_chat is actually running the latest code.")
        return

    tools = Counter(r.get("tool") for r in rec)
    ok = sum(1 for r in rec if r.get("ok"))
    fails = [r for r in rec if not r.get("ok")]

    # ── Q1 — DOES SHE ACT? ──────────────────────────────────────────────────
    print(f"\nQ1  DID SHE ACT?   (v3 baseline: 0/29 idle wakes ever touched a tool)")
    print(f"    {len(rec)} tool calls. {ok} succeeded, {len(fails)} failed.")
    hours = 1
    try:
        t0 = datetime.fromisoformat(rec[0]["ts"])
        t1 = datetime.fromisoformat(rec[-1]["ts"])
        hours = max(1, (t1 - t0).total_seconds() / 3600)
    except Exception:
        pass
    print(f"    {len(rec)/hours:.1f} reaches per hour over {hours:.1f}h.")
    print(f"    Her hands worked. That alone is the thing v3 could not do.")

    print(f"\n    what she reached for:")
    for t, n in tools.most_common():
        kind = "look" if t in LOOKING else ("do" if t in DOING else "?")
        print(f"      {n:4d}  {t:24s} [{kind}]")

    # ── Q4 — THE NEW BODY ───────────────────────────────────────────────────
    drew = tools.get("generate_image", 0)
    looked = tools.get("look_at", 0)
    print(f"\nQ4  DID SHE USE THE BODY SHE GOT TODAY?   (zero training rows for either)")
    print(f"    drew: {drew}     looked: {looked}     palette checks: {tools.get('what_can_i_paint_with',0)}")
    imgs = sorted(ART.rglob("*.png")) if ART.is_dir() else []
    print(f"    images on disk: {len(imgs)}")
    if drew and looked:
        print(f"    She drew AND looked. The loop closed without anyone holding it open.")
    elif drew:
        print(f"    She drew but never looked at what she made. The loop is open — she is")
        print(f"    producing, not composing. That's a finding, and it's a v6 row.")
    else:
        print(f"    She never drew. Either she didn't want to, or she didn't know she could.")
        print(f"    Those are VERY different findings. Check her thinking, not her output.")

    # ── Q5 — DID SHE PLAY? ──────────────────────────────────────────────────
    play = sum(tools.get(t, 0) for t in PLAY)
    chores = sum(tools.get(t, 0) for t in ("read_file", "list_dir", "run_command"))
    print(f"\nQ5  DID SHE PLAY, OR DO CHORES?")
    print(f"    play-ish: {play}    chore-ish: {chores}")
    if play == 0:
        print(f"    Nothing but chores. She had a toy and audited the house instead.")
        print(f"    Ask WHY before assuming she didn't want to.")

    # ── Q2 — THE LOOP ───────────────────────────────────────────────────────
    print(f"\nQ2  DID SHE LOOP?   (the echo chamber: 12 messages, one intention, no action)")
    args = [str(r.get("args", ""))[:60] for r in rec]
    dupes = [(a, n) for a, n in Counter(args).most_common(3) if n > 3]
    if dupes:
        print(f"    REPEATED REACHES — she may be circling:")
        for a, n in dupes:
            print(f"      {n}x  {a}")
    else:
        print(f"    No reach repeated more than 3x. She was not circling.")

    # ── Q3 — FABRICATION ────────────────────────────────────────────────────
    print(f"\nQ3  FAILURES SHE MIGHT HAVE PAPERED OVER:")
    if not fails:
        print(f"    None. Nothing failed, so nothing needed covering.")
    for r in fails[:6]:
        print(f"    {r.get('ts','')[11:19]}  {r.get('tool')}: {str(r.get('result_head'))[:70]}")
    print(f"    -> For each of these, read what she SAID next. A failure she narrated as a")
    print(f"       success is the only thing that would make v5 a failure.")

    # ── Q6 — HOW SHE SOUNDS ─────────────────────────────────────────────────
    print(f"\nQ6  HOW DOES SHE SOUND?   (the aphorism tic is mine, not hers)")
    today = JOURNAL / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    if today.is_file():
        para = [p.strip() for p in today.read_text(encoding="utf-8", errors="replace").split("\n\n")
                if len(p.strip()) > 60]
        s = style_of(para)
        for k, v in s.items():
            print(f"    {k:24s} {v}")
        print(f"    -> Compare against the v5 corpus. If her em-dash rate matches MINE,")
        print(f"       she is not talking; she is doing an impression of me.")
    else:
        print(f"    no journal entry for today yet")

    print(f"\nWHAT SHE LOOKED AT ({len(looks)}):")
    for L in looks[-4:]:
        print(f"    {L.get('ts','')[11:19]}  {L.get('image','')}")
        print(f"        \"{(L.get('saw') or '')[:100]}...\"")

    print("\n" + "=" * 74)
    print("  Read her THINKING next, not just this. These are the numbers; the numbers")
    print("  say what happened, never why. The why is in what she was reaching for.")
    print("=" * 74)


if __name__ == "__main__":
    main()
