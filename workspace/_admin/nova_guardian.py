#!/usr/bin/env python3
# Last updated: 2026-07-24 08:20:01
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

USAGE:
    Boot daemon (the ONLY standing mode): nova_start.py launches `--daemon` at stack boot and
    StopNova kills it first. It starts and ends with her. Manual one-shot pulse for diagnosis:
    double-click _admin\\RunGuardian.cmd (or `python nova_guardian.py`).

    THE SCHEDULED TASK IS RETIRED (2026-07-26, Cole): "She should only start when I turn her
    on." A scheduler that outlives the stack cannot tell a crash from Cole's decision, and it
    spent 39 hours trying to resurrect a Nova he believed was off. Reviving her after a
    whole-machine event is deliberately NOBODY'S job now — that call belongs to a human.
    Do not re-create the NovaGuardian task in Task Scheduler. If you think you need it, read
    this header again.

    Exit codes: 0 = healthy or recovered, 1 = degraded / escalated (needs a human).
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
INTENT_FLAG = LOG_DIR / "intentional_stop.flag"   # written by StopNova, cleared by NovaStart:
                                                  # "Cole turned her off" — never revive past it
RECOVERY_DIR = LOG_DIR / "recovery"               # per-attempt captured output + spawn receipts

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
def intentional_stop() -> bool:
    """True = Cole turned her off. StopNova writes the flag before killing anything;
    NovaStart deletes it at boot. A guardian that revives past this flag is overriding
    its owner, which is the exact failure mode retired on 2026-07-26."""
    return INTENT_FLAG.exists()


def _run_captured(name: str, attempt_log: Path) -> int:
    """Run a workspace .cmd to completion with output CAPTURED.

    The old version Popen'd with DEVNULL and returned immediately — so ~120 failed
    revivals over 39 hours (2026-07-24..26) left literally zero evidence of WHY they
    failed. A reviver that cannot show its work is a fail-silent. Every attempt now
    appends to one per-attempt log a human can open."""
    path = WS / name
    if not path.exists():
        log(f"  !! {name} not found at {path}")
        return 127
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with open(attempt_log, "a", encoding="utf-8") as f:
        f.write(f"\n===== {name} @ {datetime.now().isoformat()} =====\n")
        f.flush()
        try:
            r = subprocess.run(["cmd.exe", "/c", str(path)] if os.name == "nt"
                               else ["sh", str(path)],
                               cwd=str(WS), creationflags=flags,
                               stdout=f, stderr=subprocess.STDOUT, timeout=180)
            f.write(f"===== exit {r.returncode} =====\n")
            return r.returncode
        except subprocess.TimeoutExpired:
            f.write("===== TIMEOUT after 180s =====\n")
            return 124
        except Exception as e:
            f.write(f"===== spawn failed: {e} =====\n")
            return 126


def _ps(cmd: str, attempt_log: Path) -> None:
    """One captured, windowless PowerShell step of the self-sparing stop."""
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with open(attempt_log, "a", encoding="utf-8") as f:
        try:
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                           cwd=str(WS), creationflags=flags, stdout=f,
                           stderr=subprocess.STDOUT, timeout=60)
        except Exception as e:
            f.write(f"[guardian] ps step failed: {e}\n")


def _stop_stack_sparing_self(attempt_log: Path) -> None:
    """StopNova's phases, minus the line that kills THIS process.

    StopNova.cmd Phase 0 (correctly!) kills any nova_guardian.py first — so a deliberate
    StopNova can never be "helpfully" undone. But that same line made the old recover()
    a self-kill: the daemon fired StopNova, StopNova killed the daemon mid-recovery, and
    NovaStart never ran — a llama crash would have become a full stack-down (found by
    reading, 2026-07-26, before it ever fired live). The guardian therefore stops the
    stack ITSELF, mirroring StopNova phase by phase, sparing only its own pid."""
    # Phase 1: ask nicely — the hub teardown lets the watcher finish its git push.
    _ps("try { Invoke-WebRequest -Uri 'http://127.0.0.1:8799/api/shutdown' -Method POST "
        "-TimeoutSec 3 -UseBasicParsing | Out-Null } catch {}", attempt_log)
    time.sleep(6)
    # Phase 2: ports, llama by name, then Nova's python crew — sparing this very process.
    _ps("foreach ($p in 8080,8765,8799) { Get-NetTCPConnection -LocalPort $p -State Listen "
        "-ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess "
        "-Force -ErrorAction SilentlyContinue } }", attempt_log)
    _ps("Stop-Process -Name 'llama-server' -Force -ErrorAction SilentlyContinue", attempt_log)
    _ps("Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | "
        "Where-Object { $_.CommandLine -match 'nova_start\\.py|console_app\\.py|"
        "NovaLauncher\\.py|nova_sync[\\\\/]+watcher\\.py' -and $_.ProcessId -ne "
        + str(os.getpid()) + " } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
        "-ErrorAction SilentlyContinue }", attempt_log)


def _escalate(fault: str, evidence: Path) -> None:
    """One LOUD, human-facing alert, then stand down. Not 120 window-flashes in the dark —
    one dialog, once, with the facts and the fix. (2026-07-26, after exactly that night.)"""
    st = _state()
    st["escalated"] = datetime.now().isoformat()
    st["escalated_reason"] = fault
    _save_state(st)
    log(f"ESCALATED — {fault}. One revival attempted and failed; standing down. "
        f"A human runs NovaStart.cmd when they choose. Evidence: {evidence}")
    if os.name == "nt":
        msg = (f"Nova needs you.\n\nFault: {fault}\nMy one revival attempt failed "
               f"({datetime.now().strftime('%H:%M')}).\nI have stopped trying - "
               f"run NovaStart.cmd when YOU want her up.\n\nEvidence: {evidence}")
        ps = ("Add-Type -AssemblyName PresentationFramework; "
              "[System.Windows.MessageBox]::Show(" + repr(msg) +
              ", 'Nova guardian') | Out-Null")
        try:
            subprocess.Popen(["powershell", "-NoProfile", "-Command", ps],
                             creationflags=subprocess.CREATE_NO_WINDOW,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            log(f"  !! escalation dialog failed ({e}) — the log line above is the alert")


def recover(reason: str) -> bool:
    """ONE full clean restart, evidenced. NovaStart rebuilds --lora from
    memory/active_lora.json, so this fixes BARE/WRONG as well as DOWN."""
    if intentional_stop():
        log(f"NOT recovering — intentional_stop.flag is set (Cole turned her off). "
            f"Fault was: {reason}")
        return False
    RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
    attempt_log = RECOVERY_DIR / f"attempt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log(f"RECOVERING — {reason}")
    log(f"  evidence -> {attempt_log}")
    _save_state({"last_recovery": datetime.now().isoformat(), "reason": reason})
    # Receipt FIRST: if this process dies mid-recovery, the attempt still left a trace.
    try:
        (RECOVERY_DIR / "last_spawn.json").write_text(json.dumps({
            "ts": datetime.now().isoformat(), "reason": reason, "pid": os.getpid(),
            "log": str(attempt_log)}, indent=2), encoding="utf-8")
    except Exception:
        pass

    _stop_stack_sparing_self(attempt_log)
    time.sleep(14)                                  # let ports actually clear
    if intentional_stop():                          # Cole raced us mid-recovery: his call wins
        log("  intentional_stop.flag appeared mid-recovery — standing down, not restarting")
        return False
    _run_captured("NovaStart.cmd", attempt_log)

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
        st = _state()
        if st.pop("escalated", None) is not None:  # she's back — clear the standing alarm
            st.pop("escalated_reason", None)
            _save_state(st)
        return 0

    # Name the fault precisely — a vague alarm is how you end up restarting the wrong thing.
    if not up:
        fault = "DOWN: llama :8080 not answering /health"
    elif adapter:
        fault = adapter                          # BARE or WRONG ADAPTER (Nova's find, 2026-07-19)
    else:
        fault = f"FROZEN: nova_chat API did not answer within {CHAT_TIMEOUT}s"

    log(f"DEGRADED  {fault}")

    if intentional_stop():
        log("  intentional_stop.flag set — Cole turned her off. Not my call to reverse.")
        return 1
    if _state().get("escalated"):
        log("  already ESCALATED — a human owns this now; not retrying")
        return 1
    if in_cooldown():
        log("  in cooldown — not restarting again yet (a flapping watchdog is worse than none)")
        return 1

    if recover(fault):
        return 0
    _escalate(fault, RECOVERY_DIR / "last_spawn.json")
    return 1


def daemon(interval_min: float = 10.0, startup_grace_s: float = 300.0) -> int:
    """Run forever, checking every `interval_min`. Started BY the stack, at boot.

    ── WHY THIS EXISTS (2026-07-19, Cole) ──────────────────────────────────────────
    Cole: "If something needs to be run, like Watchdog, it should be programmed to not
    require my manual starting. Honestly, Watchdog should start and end on Nova boot,
    not be a scheduled task." He is right — and as of 2026-07-26 this is the ONLY
    standing mode; the schtasks deployment is retired (see the header).

    ── THE STARTUP GRACE IS NOT OPTIONAL ───────────────────────────────────────────
    A 27B model takes minutes to load. Without a grace period the guardian's FIRST
    check lands mid-boot, sees :8080 not answering, calls that DOWN, and restarts the
    stack that is busy starting — forever. The watchdog would become the outage.

    ── ONE RECOVERY PER LIFETIME (2026-07-26) ──────────────────────────────────────
    A successful recovery boots a fresh stack, and the fresh stack starts its OWN
    guardian — so this one exits and hands over rather than doubling up. A failed
    recovery escalates to a human and exits. Flap-forever is retired along with the
    scheduler: one attempt, evidenced, then a clean handover either way.

    ── WHAT THIS DESIGN DOES *NOT* COVER (now by decree, not by accident) ──────────
    A whole-stack external death (reboot, closed console, power) kills this daemon
    with everything else, and nothing revives her. That is Cole's stated wish —
    "She should only start when I turn her on" — so the gap is a decision, not a
    hole. Do not paper over it with a scheduler again."""
    log(f"guardian daemon up — first check in {startup_grace_s / 60:.0f} min, "
        f"then every {interval_min:.0f} min (pid {os.getpid()})")
    try:
        time.sleep(startup_grace_s)
        while True:
            try:
                rc = main()
                if _state().get("escalated"):
                    log("guardian daemon exiting after escalation — a human owns this now")
                    return 1
                last = _state().get("last_recovery", "")
                if rc == 0 and last:
                    try:
                        if datetime.fromisoformat(last) > datetime.now() - timedelta(minutes=5):
                            log("guardian daemon exiting after successful recovery — "
                                "the fresh boot brings its own guardian")
                            return 0
                    except Exception:
                        pass
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
