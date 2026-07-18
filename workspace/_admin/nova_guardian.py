#!/usr/bin/env python3
# Last updated: 2026-07-19 08:20:01
"""
nova_guardian.py — deterministic self-healing life-support. NO LLM. NO TOKENS.

WHY THIS EXISTS (2026-07-19, Cole):
    We ran an hourly *LLM* watchdog overnight. It cost a fortune and fixed nothing, for two
    structural reasons:

      1. EVERY SCHEDULED RUN IS A COLD SESSION. Nothing carries over, so each run re-reads a
         large prompt and re-derives the whole stack from scratch — an expensive
         re-familiarisation, every hour, usually to conclude "fine".
      2. IT HAD NO HANDS. `request_access` is refused inside a scheduled run, and Nova's own
         API was frozen — the one thing it needed to fix. It watched her be dead for six hours
         and wrote essays about it.

    A watchdog does not need judgment. It needs a pulse check and a power switch. That is a
    script, not a language model. This runs locally with real permissions, finishes in seconds,
    costs nothing, and — unlike the scheduled agent — can actually restart her.

    Escalate to a human only when it genuinely cannot recover.

THE THREE FAILURES THIS CATCHES (all observed 2026-07-18/19):
    DOWN   — llama :8080 not answering /health at all. She cannot think.
    BARE   — llama IS healthy but /lora-adapters == []. She loaded with NO personality adapter
             and is running as the raw base model. THIS IS THE WORST ONE because nothing looks
             broken: the service is green, she just answers like a stranger, and you blame her
             training. Health checks that only ping /health miss it completely.
    FROZEN — nova_chat serves its page but its API hangs past the timeout. She is unreachable,
             and every remote recovery route (her own endpoints) is dead with her.

WHAT IT DELIBERATELY DOES NOT DO:
    No autonomy toggling, no task-board edits, no journal writes, no code changes. Her state
    files are hers. NovaStart already restores autonomy from her persisted state, so a clean
    restart resumes whatever she was doing. Life-support only: is she breathing, and is she
    herself.

SAFETY: a COOLDOWN prevents restart loops. If it just restarted her, it will not restart her
    again until the cooldown expires — a flapping watchdog is worse than none.

USAGE (Windows Task Scheduler, every 10 minutes):
    schtasks /create /tn "NovaGuardian" /tr "pythonw C:\\Users\\lafou\\Project_Nova\\workspace\\_admin\\nova_guardian.py" /sc minute /mo 10 /f
    Exit codes: 0 = healthy or recovered, 1 = degraded and could NOT recover (needs a human).
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
LOG_DIR = WS / "_admin" / "autonomy_watch"
LOG_FILE = LOG_DIR / "guardian.log"
STATE_FILE = LOG_DIR / "guardian_state.json"      # OURS, not hers — cooldown bookkeeping only

LLAMA_HEALTH = "http://127.0.0.1:8080/health"
LLAMA_LORA = "http://127.0.0.1:8080/lora-adapters"
CHAT_API = "http://127.0.0.1:8765/api/llama/status"

# nova_chat's API hanging IS the frozen signature. Keep this tight: a healthy call returns in
# milliseconds, so anything past a few seconds is already pathological.
CHAT_TIMEOUT = 8
PROBE_TIMEOUT = 5

COOLDOWN_MIN = 20          # never restart twice inside this window
BOOT_WAIT_S = 240          # a 27B model load can take a couple of minutes
POLL_S = 5


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _get(url: str, timeout: int):
    """Return (ok, body). Never raises — a probe that throws is just a failed probe."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return (r.status == 200, r.read().decode("utf-8", "replace"))
    except Exception:
        return (False, "")


# ── the three probes ──────────────────────────────────────────────────────────
def llama_up() -> bool:
    return _get(LLAMA_HEALTH, PROBE_TIMEOUT)[0]


def llama_bare() -> bool:
    """True = healthy but NO personality adapter loaded.

    This is the silent one. `/health` says 200 and everything looks fine; she just isn't
    herself. Checking only /health is how she ran as the base model for hours and we blamed
    the training instead of the loader."""
    ok, body = _get(LLAMA_LORA, PROBE_TIMEOUT)
    if not ok:
        return False                      # can't tell; DOWN handling covers it
    try:
        return len(json.loads(body)) == 0
    except Exception:
        return False


def chat_responsive() -> bool:
    return _get(CHAT_API, CHAT_TIMEOUT)[0]


# ── cooldown bookkeeping (our own file, never hers) ───────────────────────────
def _state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(d: dict) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")
    except Exception:
        pass


def in_cooldown() -> bool:
    last = _state().get("last_recovery", "")
    if not last:
        return False
    try:
        return datetime.fromisoformat(last) > datetime.now() - timedelta(minutes=COOLDOWN_MIN)
    except Exception:
        return False


# ── recovery ──────────────────────────────────────────────────────────────────
def _run_cmd(name: str) -> None:
    """Fire a workspace .cmd and return immediately (they manage their own lifecycle)."""
    path = WS / name
    if not path.exists():
        log(f"  !! {name} not found at {path}")
        return
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    subprocess.Popen(["cmd.exe", "/c", str(path)], cwd=str(WS), creationflags=flags,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def recover(reason: str) -> bool:
    """Full clean restart. NovaStart rebuilds --lora from memory/active_lora.json, which is the
    path known to load her personality correctly — so this fixes BARE as well as DOWN."""
    log(f"RECOVERING — {reason}")
    _save_state({"last_recovery": datetime.now().isoformat(), "reason": reason})

    _run_cmd("StopNova.cmd")
    time.sleep(20)                                  # let ports actually clear
    _run_cmd("NovaStart.cmd")

    deadline = time.time() + BOOT_WAIT_S
    while time.time() < deadline:
        time.sleep(POLL_S)
        if llama_up() and not llama_bare():
            # Don't declare victory on llama alone — her face has to answer too.
            if chat_responsive():
                log("  recovered: llama healthy WITH adapter, nova_chat responsive")
                return True
    log("  !! recovery did NOT come back clean within the window")
    return False


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    up = llama_up()
    bare = llama_bare() if up else False
    chat = chat_responsive()

    if up and not bare and chat:
        log("HEALTHY  llama=up adapter=loaded chat=ok")
        return 0

    # Name the fault precisely — a vague alarm is how you end up restarting the wrong thing.
    if not up:
        fault = "DOWN: llama :8080 not answering /health"
    elif bare:
        fault = "BARE: llama healthy but /lora-adapters is empty — running with NO personality"
    else:
        fault = f"FROZEN: nova_chat API did not answer within {CHAT_TIMEOUT}s"

    log(f"DEGRADED  {fault}")

    if in_cooldown():
        log("  in cooldown — not restarting again yet (a flapping watchdog is worse than none)")
        return 1

    return 0 if recover(fault) else 1


if __name__ == "__main__":
    sys.exit(main())
