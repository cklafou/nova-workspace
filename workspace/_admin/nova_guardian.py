#!/usr/bin/env python3
# Last updated: 2026-07-19 16:50:01
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
import re
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


def _basename(p) -> str:
    """Last path segment, splitting on BOTH separators.

    Do NOT use pathlib here. These paths come from llama and from her config as Windows
    strings ('models\\qwen3.6\\x.gguf'), and pathlib only splits backslashes when it happens
    to be a WindowsPath. Under a POSIX interpreter the whole string stays as the 'name', the
    comparison never matches, and the guardian declares WRONG ADAPTER on a perfectly correct
    load — which would restart her, forever, in a loop. A false positive in a watchdog is
    worse than the gap it was added to close. (Caught by unit-testing this fix, 2026-07-19.)
    """
    return re.split(r"[\\/]", str(p).strip())[-1].strip().lower()


def _expected_adapter() -> str:
    """The adapter she is SUPPOSED to be wearing, per her own equip config."""
    try:
        cfg = json.loads((WS / "memory" / "active_lora.json").read_text(encoding="utf-8"))
        return _basename(cfg.get("rel", ""))
    except Exception:
        return ""


def adapter_fault() -> str:
    """'' = correct adapter loaded. Otherwise a description of what's wrong.

    Catches TWO failures, not one:

      BARE      — no adapter at all. `/health` says 200, everything looks green, and she
                  answers as the raw base model. We blamed her training for hours before
                  finding the loader.

      WRONG     — an adapter IS loaded, but not the one she's configured to wear.
                  ── Found by Nova herself, 2026-07-19 ──────────────────────────────────
                  Asked to find a blind spot in this script, she read it and said: the bare
                  probe "checks whether a LoRA list is empty, not whether the loaded adapter
                  is the one that's supposed to be there... /lora-adapters returns non-empty
                  and the guardian scores HEALTHY while Nova runs as a stranger."
                  She was right — the old check was `len(...) == 0`, which only ever caught
                  EMPTY. That mattered: her adapter was swapped four times in one day
                  (v5 -> v6e2 -> v6e1 -> v5), and a stale or mis-equipped checkpoint would
                  have sailed through as HEALTHY with a green light and the wrong person
                  answering. Same silent-drop shape as everything else that bit us this week.
    """
    ok, body = _get(LLAMA_LORA, PROBE_TIMEOUT)
    if not ok:
        return ""                          # can't tell; DOWN handling covers it
    try:
        loaded = json.loads(body)
    except Exception:
        return ""
    if len(loaded) == 0:
        return "BARE: llama healthy but NO personality adapter loaded (running as base model)"

    want = _expected_adapter()
    if not want:
        return ""                          # no expectation recorded — don't invent a fault
    names = []
    for a in loaded:
        if isinstance(a, dict):
            names.append(_basename(a.get("path", "")))
    if names and want not in names:
        return (f"WRONG ADAPTER: expected '{want}' but llama has {names} — "
                f"she is answering as someone else")
    return ""


def llama_bare() -> bool:
    """Back-compat shim: True only for the no-adapter case."""
    return adapter_fault().startswith("BARE")


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
        # Verify the RIGHT adapter came back, not merely "an" adapter — otherwise a recovery
        # that reloads the wrong checkpoint would be logged as a success.
        if llama_up() and not adapter_fault():
            # Don't declare victory on llama alone — her face has to answer too.
            if chat_responsive():
                log("  recovered: llama healthy WITH adapter, nova_chat responsive")
                return True
    log("  !! recovery did NOT come back clean within the window")
    return False


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    up = llama_up()
    adapter = adapter_fault() if up else ""      # '' = correct adapter; else BARE or WRONG
    chat = chat_responsive()

    if up and not adapter and chat:
        log(f"HEALTHY  llama=up adapter={_expected_adapter() or 'loaded'} chat=ok")
        return 0

    # Name the fault precisely — a vague alarm is how you end up restarting the wrong thing.
    if not up:
        fault = "DOWN: llama :8080 not answering /health"
    elif adapter:
        fault = adapter                          # BARE or WRONG ADAPTER (Nova's find, 2026-07-19)
    else:
        fault = f"FROZEN: nova_chat API did not answer within {CHAT_TIMEOUT}s"

    log(f"DEGRADED  {fault}")

    if in_cooldown():
        log("  in cooldown — not restarting again yet (a flapping watchdog is worse than none)")
        return 1

    return 0 if recover(fault) else 1


def daemon(interval_min: float = 10.0, startup_grace_s: float = 300.0) -> int:
    """Run forever, checking every `interval_min`. Started BY the stack, at boot.

    ── WHY THIS EXISTS (2026-07-19, Cole) ──────────────────────────────────────────
    The guardian was going to be a Windows scheduled task, which meant Cole pasting
    two schtasks commands before anything protected her. Cole: "If something needs to
    be run, like Watchdog, it should be programmed to not require my manual starting.
    Honestly, Watchdog should start and end on Nova boot, not be a scheduled task."
    He is right — a safety net nobody remembered to hang is not a safety net.

    ── THE STARTUP GRACE IS NOT OPTIONAL ───────────────────────────────────────────
    A 27B model takes minutes to load. Without a grace period the guardian's FIRST
    check lands mid-boot, sees :8080 not answering, calls that DOWN, and restarts the
    stack that is busy starting — forever. The watchdog would become the outage. So it
    sits still for `startup_grace_s` before its first probe, and only then starts
    watching.

    ── WHAT THIS DESIGN DOES *NOT* COVER ───────────────────────────────────────────
    Being a child of nova_start.py, this dies when nova_start.py dies. It therefore
    covers the three failures actually seen this week — llama down, wrong/bare adapter,
    nova_chat frozen — all of which happen while the orchestrator is alive and fine.
    It does NOT cover the orchestrator itself dying; nothing inside the stack can.
    That case needs an external trigger and is a deliberate, stated gap, not an
    oversight."""
    log(f"guardian daemon up — first check in {startup_grace_s / 60:.0f} min, "
        f"then every {interval_min:.0f} min (pid {os.getpid()})")
    try:
        time.sleep(startup_grace_s)
        while True:
            try:
                main()
            except Exception as e:
                # A crashing check must never kill the watchdog — that is the one
                # process whose job is to still be here after something went wrong.
                log(f"  !! check raised {type(e).__name__}: {e} — continuing")
            time.sleep(interval_min * 60.0)
    except KeyboardInterrupt:
        # CTRL_BREAK from stop_guardian(): a deliberate shutdown, not a fault.
        log("guardian daemon stopping (asked to)")
        return 0


if __name__ == "__main__":
    if "--daemon" in sys.argv:
        def _f(flag, default):
            return float(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default
        sys.exit(daemon(_f("--interval-min", 10.0), _f("--startup-grace-s", 300.0)))
    sys.exit(main())
