# Last updated: 2026-05-08
"""
nova_cortex/vigilance.py — Nova's Reticular Activating System
==============================================================
The vigilance system controls Nova's sleep/wake cycle. It runs as a
background thread and operates in two tiers:

  TIER 1 — 30-second adaptive alerting (lightweight, rule-based)
    - Polls nova_status.json every 30 seconds
    - Checks for urgent signals: unread messages, error spikes, task deadlines
    - If threshold crossed: emits WAKE signal → triggers cortex
    - If quiet: stays silent, no Nova tokens consumed

  TIER 2 — 4-minute sensory sweep (active perception)
    - Every 4 minutes, Nova actively perceives her environment
    - Calls nova_senses (eyes, proprioception) to read current state
    - Calls prefrontal_cortex.orient() to self-assess
    - Issues WAKE or SLEEP decision based on what she finds

SLEEP/WAKE Protocol
-------------------
  WAKE  — Nova is active. The cortex (circadian, agent_loop) processes turns.
  SLEEP — Nova is passive. Vigilance still runs; cortex pauses.

  Nova issues WAKE herself when she decides action is needed.
  Nova issues SLEEP herself when there's nothing requiring attention.
  Cole can force WAKE at any time by sending a message.

Wire-up (in server.py or gateway.py startup):
    from nova_cortex.vigilance import NovaVigilance
    vigilance = NovaVigilance()
    vigilance.start()   # non-blocking background thread
    # ...
    vigilance.stop()

Built: 2026-05-08 (Step 4 of anatomical restructure, session 11)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────

_WORKSPACE = Path(__file__).resolve().parents[3]   # nova_cortex/ → nova_tools/ → workspace
_STATUS_PATH   = _WORKSPACE / "memory" / "nova_status.json"
_HEARTBEAT_PATH = _WORKSPACE / "memory" / "HEARTBEAT.md"

# ── Tuning constants ──────────────────────────────────────────────────────────

TIER1_INTERVAL_S     = 30    # seconds between lightweight alerting polls
TIER2_INTERVAL_S     = 240   # seconds between full sensory sweeps (4 min)
MIN_INTERVAL_S       = 5     # floor — never poll faster than this
MAX_INTERVAL_S       = 120   # ceiling — never sleep longer than 2 min

# Error rate that triggers an immediate WAKE (errors per minute)
ERROR_RATE_THRESHOLD = 2.0

# How many consecutive quiet polls before interval is doubled (backoff)
QUIET_POLLS_BEFORE_BACKOFF = 3


# ── Signal types ──────────────────────────────────────────────────────────────

WAKE  = "WAKE"
SLEEP = "SLEEP"


# ── NovaVigilance ─────────────────────────────────────────────────────────────

class NovaVigilance:
    """
    Nova's reticular activating system.

    Runs two background threads:
      - _tier1_loop: lightweight 30-second status poll
      - _tier2_loop: full 4-minute sensory sweep

    Calls on_wake(reason) when Nova should activate.
    Calls on_sleep(reason) when Nova can stand down.

    Both callbacks are optional — vigilance is useful even without them
    (it will log the signals and update its own state).

    Usage:
        def wake_handler(reason):
            print(f"Nova waking: {reason}")
            # trigger cortex, send to agent_loop, etc.

        v = NovaVigilance(on_wake=wake_handler)
        v.start()
    """

    def __init__(
        self,
        on_wake:  Optional[Callable[[str], None]] = None,
        on_sleep: Optional[Callable[[str], None]] = None,
    ):
        self.on_wake  = on_wake  or (lambda reason: log.info("WAKE: %s", reason))
        self.on_sleep = on_sleep or (lambda reason: log.info("SLEEP: %s", reason))

        self._state          = SLEEP       # current state
        self._running        = False
        self._t1: Optional[threading.Thread] = None
        self._t2: Optional[threading.Thread] = None
        self._lock           = threading.Lock()

        # Adaptive interval (Tier 1 adjusts based on activity level)
        self._current_interval = TIER1_INTERVAL_S
        self._quiet_streak     = 0

        # Last seen error count (for rate calculation)
        self._last_error_count  = 0
        self._last_error_time   = time.monotonic()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start both polling loops as daemon threads. Non-blocking."""
        if self._running:
            log.warning("NovaVigilance.start() called but already running.")
            return
        self._running = True
        self._t1 = threading.Thread(
            target=self._tier1_loop, name="vigilance-tier1", daemon=True
        )
        self._t2 = threading.Thread(
            target=self._tier2_loop, name="vigilance-tier2", daemon=True
        )
        self._t1.start()
        self._t2.start()
        log.info(
            "NovaVigilance started. Tier1=%ds Tier2=%ds",
            TIER1_INTERVAL_S, TIER2_INTERVAL_S,
        )

    def stop(self) -> None:
        """Signal both loops to exit. Returns immediately."""
        self._running = False
        log.info("NovaVigilance stopping.")

    def force_wake(self, reason: str = "manual override") -> None:
        """External call to force WAKE state (e.g. user sent a message)."""
        self._transition(WAKE, reason)

    def force_sleep(self, reason: str = "manual override") -> None:
        """External call to force SLEEP state."""
        self._transition(SLEEP, reason)

    @property
    def state(self) -> str:
        return self._state

    # ── Tier 1: Lightweight alerting ──────────────────────────────────────────

    def _tier1_loop(self) -> None:
        """Poll nova_status.json on an adaptive interval. Rule-based decisions."""
        log.debug("Tier1 loop started.")
        while self._running:
            try:
                self._tier1_check()
            except Exception as e:
                log.warning("Tier1 check error: %s", e)

            # Adaptive sleep: back off when quiet, tighten when active
            sleep_s = self._current_interval
            elapsed = 0.0
            step    = 1.0
            while self._running and elapsed < sleep_s:
                time.sleep(step)
                elapsed += step
        log.debug("Tier1 loop exited.")

    def _tier1_check(self) -> None:
        """Read nova_status.json and decide whether to emit a signal."""
        status = self._read_nova_status()
        if status is None:
            # Status file missing — don't panic, just stay quiet
            self._quiet_streak += 1
            self._maybe_backoff()
            return

        signals: list[str] = []

        # ── Rule 1: Unread messages waiting ───────────────────────────────────
        unread = status.get("unread_messages", 0)
        if isinstance(unread, int) and unread > 0:
            signals.append(f"{unread} unread message(s)")

        # ── Rule 2: Active task stuck or timed out ────────────────────────────
        task = status.get("current_task")
        if task:
            started_iso = status.get("task_started_at")
            if started_iso:
                try:
                    started = datetime.fromisoformat(started_iso)
                    age_min = (datetime.now(timezone.utc) - started).total_seconds() / 60
                    if age_min > 10:
                        signals.append(f"task '{task}' running {age_min:.0f}min — possible stall")
                except Exception:
                    pass

        # ── Rule 3: Error rate spike ──────────────────────────────────────────
        errors = status.get("error_count", 0)
        now    = time.monotonic()
        elapsed = max(now - self._last_error_time, 1.0)
        rate    = (errors - self._last_error_count) / (elapsed / 60.0)
        self._last_error_count = errors
        self._last_error_time  = now
        if rate >= ERROR_RATE_THRESHOLD:
            signals.append(f"error spike: {rate:.1f} errors/min")

        # ── Rule 4: Explicit WAKE request written to status ───────────────────
        if status.get("wake_request"):
            signals.append(f"wake_request: {status['wake_request']}")

        if signals:
            self._quiet_streak = 0
            self._current_interval = TIER1_INTERVAL_S   # reset to normal
            self._transition(WAKE, "; ".join(signals))
        else:
            self._quiet_streak += 1
            self._maybe_backoff()
            if self._state == WAKE:
                self._transition(SLEEP, "all quiet (tier1)")

    def _maybe_backoff(self) -> None:
        """Gradually double the poll interval when nothing is happening."""
        if self._quiet_streak >= QUIET_POLLS_BEFORE_BACKOFF:
            new_interval = min(self._current_interval * 2, MAX_INTERVAL_S)
            if new_interval != self._current_interval:
                log.debug(
                    "Tier1 backoff: interval %ds → %ds (quiet streak %d)",
                    self._current_interval, new_interval, self._quiet_streak,
                )
                self._current_interval = new_interval

    # ── Tier 2: Full sensory sweep ────────────────────────────────────────────

    def _tier2_loop(self) -> None:
        """Every 4 minutes: call senses + orient(), make a WAKE/SLEEP decision."""
        log.debug("Tier2 loop started.")
        # Offset Tier2 by half the interval so it doesn't coincide with Tier1 startup
        time.sleep(TIER2_INTERVAL_S // 2)
        while self._running:
            try:
                self._tier2_sweep()
            except Exception as e:
                log.warning("Tier2 sweep error: %s", e)

            elapsed = 0.0
            while self._running and elapsed < TIER2_INTERVAL_S:
                time.sleep(1.0)
                elapsed += 1.0
        log.debug("Tier2 loop exited.")

    def _tier2_sweep(self) -> None:
        """
        Full sensory sweep — the most expensive path.

        Imports senses lazily so vigilance can start even if pywinauto / vision
        dependencies aren't available in the current environment.
        """
        findings: list[str] = []

        # ── System state (proprioception) ─────────────────────────────────────
        try:
            import sys as _sys
            _ws_tools = str(Path(__file__).resolve().parents[2])
            if _ws_tools not in _sys.path:
                _sys.path.insert(0, _ws_tools)
            from nova_senses.proprioception import NovaExplorer
            explorer = NovaExplorer()
            # Just check if we can get basic system info
            findings.append("proprioception: available")
        except Exception as e:
            findings.append(f"proprioception: unavailable ({e})")

        # ── Screen state (eyes) ───────────────────────────────────────────────
        try:
            from nova_senses.eyes import NovaEyes
            # We don't take a screenshot here — too expensive at 4-min intervals
            # Just verify vision system is loadable
            findings.append("eyes: available")
        except Exception as e:
            findings.append(f"eyes: unavailable ({e})")

        # ── Cortex self-assessment ────────────────────────────────────────────
        try:
            from nova_cortex.prefrontal_cortex import orient
            briefing = orient()
            if briefing:
                word_count = len(briefing.split())
                findings.append(f"orient: {word_count} words")
                # Simple heuristic: if orient returned substantial content, Nova has
                # pending context that may need attention
                if word_count > 100:
                    self._transition(WAKE, f"orient returned {word_count}-word briefing")
                    return
        except Exception as e:
            findings.append(f"orient: unavailable ({e})")

        # ── Heartbeat file check ──────────────────────────────────────────────
        try:
            if _HEARTBEAT_PATH.exists():
                age_s = time.time() - _HEARTBEAT_PATH.stat().st_mtime
                age_min = age_s / 60
                if age_min > 35:
                    findings.append(f"HEARTBEAT.md stale: {age_min:.0f}min")
                    self._transition(WAKE, f"HEARTBEAT.md not updated in {age_min:.0f}min")
                    return
        except Exception:
            pass

        log.debug("Tier2 sweep complete: %s", "; ".join(findings))
        # If we get here with no WAKE triggers, go/stay SLEEP
        self._transition(SLEEP, f"tier2 sweep clean ({len(findings)} checks)")

    # ── State machine ─────────────────────────────────────────────────────────

    def _transition(self, new_state: str, reason: str) -> None:
        """Emit a signal only when state actually changes."""
        with self._lock:
            if self._state == new_state:
                return
            self._state = new_state

        log.info("[vigilance] %s — %s", new_state, reason)
        if new_state == WAKE:
            try:
                self.on_wake(reason)
            except Exception as e:
                log.error("on_wake callback error: %s", e)
        else:
            try:
                self.on_sleep(reason)
            except Exception as e:
                log.error("on_sleep callback error: %s", e)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _read_nova_status(self) -> Optional[dict]:
        """Read nova_status.json, return dict or None on failure."""
        try:
            if not _STATUS_PATH.exists():
                return None
            return json.loads(_STATUS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return None


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    print("NovaVigilance test mode — running for 90 seconds.")
    print("Ctrl+C to stop early.\n")

    def on_wake(reason):
        print(f"  >>> WAKE: {reason}")

    def on_sleep(reason):
        print(f"  <<< SLEEP: {reason}")

    v = NovaVigilance(on_wake=on_wake, on_sleep=on_sleep)
    v.start()

    try:
        for i in range(90):
            time.sleep(1)
            if i == 20:
                print("\n[test] Injecting forced WAKE...")
                v.force_wake("test override at t=20s")
            if i == 40:
                print("\n[test] Injecting forced SLEEP...")
                v.force_sleep("test override at t=40s")
    except KeyboardInterrupt:
        pass

    v.stop()
    print("\nTest complete.")
