#!/usr/bin/env python3
"""
nova_autonomy.py — Nova's Nervous System
==========================================
This is the core action loop that controls everything Nova does on screen.

Every action follows this pattern:
  1. FIND    — NovaEyes locates the element (pywinauto first, Claude fallback)
  2. COMMIT  — Click/type at the exact coordinates
  3. VERIFY  — Claude confirms the action worked

Periodically, the mentor reviews a screenshot to make sure Nova hasn't
gone off the rails (sanity check). This catches hallucination and drift.

Dependencies:
  nova_eyes.py     -> unified vision (pywinauto + Claude)
  nova_hands.py    -> physical mouse/keyboard control
  nova_mentor.py   -> Nova's teacher (advises when stuck, sanity checks)
  nova_rules.py    -> Nova's immutable operating directives
"""

import time
import json
import ctypes
import pyautogui
from pathlib import Path
from typing import Optional

# Central log manager
try:
    from nova_logs.logger import log, get_screenshot_dir
except ImportError:
    try:
        from nova_logs.logger import log
    except ImportError:
        from nova_memory.logger import log, get_screenshot_dir

# ── FORCE PIXEL PERFECTION ─────────────────────────────────────────────────────
# Windows DPI scaling fix — must run before any coordinate work
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
    print("[autonomy] DPI awareness set to Per Monitor (mode 2).")
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()
    print("[autonomy] DPI awareness set via fallback method.")

# Nova's immutable operating rules
from nova_core.rules import OPERATIONAL_DIRECTIVES, TASKBAR_X, TASKBAR_Y

# ── Config ─────────────────────────────────────────────────────────────────────

# How many times to retry an action before escalating to mentor
MAX_ACTION_RETRIES = 3

# How long to wait after an action before verifying it worked
ACTION_SETTLE_TIME = 1.0  # seconds

print("[autonomy] Operational directives loaded from nova_rules.py")


class NovaAutonomy:
    """
    NovaAutonomy ties Eyes, Hands, and Mentor together into a reliable action loop.

    Uses NovaEyes for all vision — element finding, verification, and sanity checks.
    The mentor gets called for recovery strategies and periodic reality checks.

    Basic usage:
        from nova_eyes    import NovaEyes
        from nova_hands   import NovaHands
        from nova_mentor  import NovaMentor
        from nova_action.autonomy import NovaAutonomy

        autonomy = NovaAutonomy(
            eyes=NovaEyes(),
            hands=NovaHands(),
            mentor=NovaMentor()
        )

        autonomy.click("Trade Button", window="thinkorswim",
                       success_question="Is the Trade page visible?")
    """

    def __init__(self, eyes, hands, mentor=None):
        """
        Args:
            eyes:   NovaEyes instance — unified vision (pywinauto + Claude)
            hands:  NovaHands instance — mouse/keyboard control
            mentor: NovaMentor instance — teacher and safety gatekeeper
        """
        self.eyes   = eyes
        self.hands  = hands
        self.mentor = mentor

        if self.mentor:
            print("[autonomy] Mentor connected. Sanity checks enabled.")
        else:
            print("[autonomy] Warning: No mentor. Sanity checks disabled.")

    # ── Action logging ─────────────────────────────────────────────────────────

    def _log(self, event: str, target: str, action: str, result: str, detail: str = ""):
        """Write an event to today's action log via nova_logger."""
        log("actions", event, target=target, action=action, result=result, detail=detail)

    # ── Core action loop ───────────────────────────────────────────────────────

    def execute_verified_action(
        self,
        target: str,
        action: str = "click",
        data: Optional[str] = None,
        success_question: Optional[str] = None,
        window: Optional[str] = None,
        control_type: Optional[str] = None,
    ) -> bool:
        """
        Find an element, interact with it, verify it worked.

        Args:
            target:           Element name (pywinauto) or description (Claude fallback).
            action:           'click', 'double_click', 'right_click', or 'type'
            data:             Text to type (only for action='type').
            success_question: YES/NO question to verify the action worked.
            window:           Window to search in (partial title match).
            control_type:     Optional pywinauto filter — "Button", "Edit", etc.

        Returns:
            True if action confirmed successful, False if all retries failed.
        """
        # Run periodic sanity check if the mentor is connected and it's time
        if self.mentor and self.eyes.should_sanity_check():
            self.eyes.sanity_check(self.mentor)

        for attempt in range(1, MAX_ACTION_RETRIES + 1):
            attempt_label = f"(attempt {attempt}/{MAX_ACTION_RETRIES})"
            print(f"[autonomy] Looking for '{target}' {attempt_label}")

            # ── STEP 1: FIND ───────────────────────────────────────────────
            element = self.eyes.find(target, window=window, control_type=control_type)

            if element is None:
                print(f"[autonomy] '{target}' not found.")
                self._log("sight_fail", target, action, "not_found", attempt_label)

                if attempt <= 2:
                    print(f"[autonomy] Clicking taskbar to recover focus...")
                    self.hands.move_and_click(TASKBAR_X, TASKBAR_Y, label="Taskbar Recovery")
                    time.sleep(1.5)
                continue

            x, y = element["center_x"], element["center_y"]
            method = element.get("method", "unknown")
            print(f"[autonomy] Found '{target}' at ({x}, {y}) via {method}")
            self._log("found", target, action, method, f"({x},{y})")

            # ── STEP 2: COMMIT ─────────────────────────────────────────────
            print(f"[autonomy] Performing '{action}' on '{target}' at ({x}, {y})...")
            if not self._perform_action(action, x, y, data):
                return False

            # ── STEP 3: VERIFY ─────────────────────────────────────────────
            time.sleep(ACTION_SETTLE_TIME)

            question = success_question or (
                f"Did clicking or interacting with '{target}' succeed? "
                "Look for any visible change: new window, highlighted element, "
                "text appearing, or button state change."
            )

            if self.eyes.verify(question):
                print(f"[autonomy] '{target}' — action confirmed successful.")
                self._log("success", target, action, "ok")
                return True

            print(f"[autonomy] Action not confirmed. Retrying...")
            self._log("verify_fail", target, action, "retry", attempt_label)

        # ── ESCALATE TO MENTOR ─────────────────────────────────────────────
        print(f"[autonomy] All {MAX_ACTION_RETRIES} attempts failed for '{target}'.")
        self._log("gave_up", target, action, "failed", "escalating to mentor")

        if self.mentor:
            print(f"[autonomy] Consulting mentor for recovery strategy...")
            stuck_shot = self.eyes.screenshot(save=True)
            advice = self.mentor.ask_for_recovery_strategy(
                target=target,
                attempts_made=MAX_ACTION_RETRIES,
                screenshot=stuck_shot,
            )
            print(f"[autonomy] Mentor advice:\n{advice}")
            self._log("mentor_consulted", target, action, "advice_received", advice[:200])

        return False

    # ── Raw action performer ───────────────────────────────────────────────────

    def _perform_action(self, action: str, x: int, y: int, data: Optional[str]) -> bool:
        """Execute the actual mouse or keyboard action."""
        if action == "click":
            self.hands.move_and_click(x, y, label=action)

        elif action == "double_click":
            self.hands.double_click(x, y)

        elif action == "right_click":
            self.hands.right_click(x, y)

        elif action == "type":
            if data is None:
                print("[autonomy] ERROR: 'type' action requires data= argument.")
                return False
            self.hands.move_and_click(x, y, label="focus before type")
            time.sleep(0.2)
            self.hands.type_text(data)

        else:
            print(f"[autonomy] ERROR: Unknown action '{action}'.")
            return False

        return True

    # ── Convenience wrappers ───────────────────────────────────────────────────

    def click(self, target: str, window: str = None, control_type: str = None,
              success_question: str = None) -> bool:
        """Click a UI element by name."""
        return self.execute_verified_action(
            target, action="click", window=window,
            control_type=control_type, success_question=success_question
        )

    def type_into(self, target: str, text: str, window: str = None,
                  success_question: str = None) -> bool:
        """Click a field to focus it, then type text into it."""
        return self.execute_verified_action(
            target, action="type", data=text, window=window,
            success_question=success_question
        )

    def wait_for(self, condition: str, timeout: int = 60, poll: int = 2) -> bool:
        """
        Waits for a specific UI state to be true, verified by Claude.

        ACTIVE LISTENER: checks interrupt_inbox.json every second.
        If Cole runs nova_interrupt.py, the loop aborts immediately.

        Args:
            condition: A plain string describing what to wait for.
                       Example: "Cole says we are done"
                       MUST be a string -- never pass a lambda or function.
        """
        # Hard guard -- Nova sometimes passes lambdas by mistake
        if not isinstance(condition, str):
            raise TypeError(
                f"wait_for() condition must be a plain string, "
                f"got {type(condition).__name__}. "
                f"Example: wait_for('Cole says we are done', timeout=120)"
            )

        print(f"[autonomy] Waiting for condition: '{condition}' (up to {timeout}s)")
        start_time = time.time()
        deadline = start_time + timeout

        # Where Discord messages will be written by the bot
        inbox_path = Path("memory/interrupt_inbox.json")

        while time.time() < deadline:
            # --- INTERRUPT CHECK ---
            if inbox_path.exists():
                try:
                    with open(inbox_path, "r", encoding="utf-8") as f:
                        msg_data = json.load(f)
                        # If the message arrived AFTER we started waiting, abort
                        if msg_data.get("timestamp", 0) > start_time:
                            print(f"\n[!] ABORTING WAIT: New message from Cole detected!")
                            self._log("wait_for", str(condition)[:200], "abort", "user_interrupt")
                            return False
                except Exception:
                    # File is being written to — skip this check
                    pass

            # --- VERIFICATION CHECK ---
            shot = self.eyes.screenshot()
            is_ready = self.eyes.verify(f"Is this true: {condition}?", screenshot=shot)
            if is_ready:
                print(f"[autonomy] Condition met: '{condition}'")
                self._log("wait_for", str(condition)[:200], "wait", "ok")
                return True

            remaining = int(deadline - time.time())
            print(f"[autonomy] Still waiting... ({remaining}s remaining)")

            # --- MICRO-POLLING ---
            # Sleep in 1-second chunks so interrupt inbox is checked frequently
            for _ in range(poll):
                time.sleep(1)
                if time.time() >= deadline:
                    break

        print(f"[autonomy] Timed out waiting for: '{condition}'")
        self._log("wait_for", str(condition)[:200], "wait", "timeout")

        # Only consult mentor on natural timeout, not on interrupt abort
        if self.mentor:
            stuck_shot = self.eyes.screenshot(save=True)
            advice = self.mentor.ask(
                f"Nova waited {timeout}s for this condition but it never happened: "
                f"'{condition}'. What might be wrong and what should she try next?",
                screenshot=stuck_shot,
                high_stakes=True
            )
            print(f"[autonomy] Mentor advice:\n{advice}")

        return False


# ── Standalone test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("nova_autonomy.py loaded successfully.")
    print(f"Taskbar recovery point: ({TASKBAR_X}, {TASKBAR_Y})")
    print()
    print("Usage:")
    print("  from nova_eyes    import NovaEyes")
    print("  from nova_hands   import NovaHands")
    print("  from nova_mentor  import NovaMentor")
    print("  from nova_action.autonomy import NovaAutonomy")
    print()
    print("  autonomy = NovaAutonomy(NovaEyes(), NovaHands(), NovaMentor())")
    print("  autonomy.click('Five', window='Calculator',")
    print("                 success_question='Is 5 in the display?')")

