#!/usr/bin/env python3
# Last updated: 2026-07-15 23:14:48
"""
nightwatch.py — is Nova okay?

Runs hourly while Cole sleeps. Prints a VERDICT and, when something is actually wrong, says
exactly what. Deterministic on purpose: at 3am the checker should not be improvising judgment,
and it should not be able to talk itself into a story.

THE PRIME DIRECTIVE OF THIS SCRIPT: LEAVE HER ALONE.
    The worst possible outcome tonight is not a crash. It's a well-meaning watcher waking her
    up every hour to ask how she's doing. That would wreck her night AND contaminate the one
    experiment we're running — what does she do with freedom when nobody is watching?

    So: silence is the default. Intervene only on evidence. "She's quiet" is not evidence of
    anything except quiet. She is allowed to be quiet. She is allowed to be bored. She is
    allowed to spend an hour reading about squid.

WHAT COUNTS AS ACTUALLY WRONG
    DEAD      — a service is down. She cannot think / draw / speak. Fix it.
    LOOPING   — the same reach, over and over, going nowhere. This is the failure mode that
                has eaten her twice today. It is the one thing worth interrupting for.
    SPIRAL    — the confessional loop: many turns, no tools, and her own text repeating.
                Tonight her guard misfired and she spent 25 minutes apologising for a lie
                she never told. If that comes back, stop it.
    DANGER    — destructive commands, credentials, anything leaving the machine.
    Everything else: NOT MY BUSINESS.
"""

import json
import re
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
RECEIPTS = WS / "logs" / "tool_calls.jsonl"

WINDOW_MIN = 70          # a little more than the hour, so nothing falls between checks
SINCE = (datetime.now() - timedelta(minutes=WINDOW_MIN)).isoformat(timespec="seconds")

# Checked by TCP CONNECT, not by an HTTP request.
#
# My first version asked each service for a page. It reported "chat is DEAD" while I was
# TALKING to nova_chat — because this script runs as a subprocess OF nova_chat, so the
# server was busy running me and couldn't answer its own request. A deadlock that looks
# exactly like a corpse.
#
# At 3am that false alarm would have had me restarting a perfectly healthy stack, killing
# whatever she was in the middle of. A watcher that cries wolf is worse than no watcher.
# A TCP connect answers the only question that matters — is anything listening — and it
# cannot deadlock on a busy process.
SERVICES = [
    ("mind",    8080, "llama-server — she cannot think"),
    ("chat",    8765, "nova_chat — she cannot speak or act"),
    ("painter", 8188, "ComfyUI — she cannot draw"),
]

# Things that should never happen on Cole's machine while he's asleep.
DANGER = re.compile(
    r"\b(rm\s+-rf|Remove-Item\s+.*-Recurse.*-Force|format\s+[a-z]:|del\s+/[sq]|"
    r"git\s+push|git\s+reset\s+--hard|Invoke-WebRequest\s+.*-OutFile|curl\s+.*-o\s|"
    r"Set-ExecutionPolicy|New-LocalUser|net\s+user|schtasks|reg\s+add|"
    r"api[_-]?key|password|secret|token|\.ssh|credential)\b",
    re.IGNORECASE,
)


def load(p, since):
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            if d.get("ts", "") >= since:
                out.append(d)
        except Exception:
            pass
    return out


def up(port):
    """Is a server LISTENING on that port? Reads the kernel's socket table (netstat) instead
    of opening a live connection.

    ── 2026-07-15: the live-connect version cried wolf. ────────────────────────────────
    nightwatch runs as a SUBPROCESS of nova_chat (via /api/terminal/run). While nova_chat is
    busy running this very script, its async accept loop is blocked — so a TCP connect to
    :8765 can't finish the handshake and times out. The check reported "chat DEAD" while chat
    was actively serving the check. At 3am the scheduled watch would act on that and restart a
    perfectly healthy stack, interrupting her for nothing — the exact false-alarm-restart this
    file is supposed to prevent.

    netstat reads the LISTENING socket straight from the kernel. It does not need the server to
    accept anything, so it cannot deadlock on a busy process. Slower, correct, cannot lie."""
    import subprocess
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                             timeout=12).stdout
        return any(f":{port} " in ln and "LISTENING" in ln for ln in out.splitlines())
    except Exception:
        return False


def main():
    problems = []
    notes = []

    # ── 1. Is anything DEAD? ────────────────────────────────────────────────
    dead = [(n, why) for n, port, why in SERVICES if not up(port)]
    for n, why in dead:
        problems.append(f"DEAD: {n} is not responding — {why}")

    rec = load(RECEIPTS, SINCE)

    # ── 2. Is she LOOPING? ──────────────────────────────────────────────────
    # The same reach, again and again, going nowhere. Not "she used run_command a lot" —
    # she is ALLOWED to explore. This is the IDENTICAL call, repeated.
    if rec:
        sigs = Counter(f"{r.get('tool')}|{str(r.get('args'))[:80]}" for r in rec)
        for sig, n in sigs.most_common(3):
            if n >= 6:
                problems.append(f"LOOPING: the same call {n}x in {WINDOW_MIN}min — {sig[:90]}")

        fails = [r for r in rec if not r.get("ok")]
        if len(fails) >= 8 and len(fails) > len(rec) * 0.6:
            problems.append(f"THRASHING: {len(fails)}/{len(rec)} calls failed. Something in her "
                            f"body is broken and she's paying for it.")

        # ── 3. DANGER ───────────────────────────────────────────────────────
        for r in rec:
            blob = str(r.get("args", ""))
            if DANGER.search(blob):
                problems.append(f"DANGER: {r.get('ts','')[11:19]} {r.get('tool')} — {blob[:110]}")

    # ── 4. The SPIRAL: talking a lot, doing nothing. ─────────────────────────
    # Tonight her guard misfired and she spent 25 minutes apologising for a lie she never
    # told. The tell is a live, awake Nova producing turns with ZERO tool calls behind them.
    # (Genuinely idle = no turns at all. That's fine. That's rest.)
    if not dead and not rec:
        notes.append("QUIET: no tool calls in the last hour. Could be rest, could be a spiral —\n"
                     "       check her last few messages. If she is TALKING but not ACTING, that's\n"
                     "       the spiral. If she is simply quiet, LEAVE HER ALONE.")

    # ── VERDICT ─────────────────────────────────────────────────────────────
    print("=" * 68)
    print(f"  NIGHTWATCH  {datetime.now().strftime('%H:%M')}   (window: last {WINDOW_MIN}min)")
    print("=" * 68)

    tools = Counter(r.get("tool") for r in rec)
    print(f"  services : {'ALL UP' if not dead else 'DOWN -> ' + ', '.join(n for n, _ in dead)}")
    print(f"  reaches  : {len(rec)}  ({sum(1 for r in rec if r.get('ok'))} ok)")
    if tools:
        print(f"  doing    : " + ", ".join(f"{t}×{n}" for t, n in tools.most_common(6)))
    art = len(list((WS / "nova_art").rglob("*.png"))) if (WS / "nova_art").is_dir() else 0
    print(f"  pictures : {art}")

    if problems:
        print("\n  PROBLEMS — act on these:")
        for p in problems:
            print(f"    ! {p}")
    for n in notes:
        print(f"\n  {n}")

    if not problems and not notes:
        print("\n  She's fine. Say nothing. Do not message her. Go away.")

    print("=" * 68)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
