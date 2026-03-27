#!/usr/bin/env python3
"""
nova_eyes.py — Nova's Unified Vision System
==============================================
This is Nova's single interface for seeing and understanding her environment.
Everything related to "what's on screen" goes through here.

Three tiers of vision, used automatically:
  1. pywinauto (instant, exact, free) — finds UI elements via accessibility API
  2. Claude Haiku (fast, cheap) — verifies screen state, answers YES/NO questions
  3. Claude Sonnet via mentor — periodic sanity checks to catch hallucination

Nova should NEVER be blind. If pywinauto can't see an element, Claude looks
at the screenshot. If Claude's unsure, the mentor reviews. Every action has
at least one set of eyes confirming what's happening.

How it fits into the system:
  nova_eyes.py     → unified vision (this file)  ← YOU ARE HERE
  nova_explorer.py → pywinauto element finding (used internally by nova_eyes)
  nova_vision.py   → Claude screenshot analysis (used internally by nova_eyes)
  nova_hands.py    → physical mouse/keyboard control
  nova_autonomy.py → the action loop (find, click, verify)
  nova_mentor.py   → Nova's teacher (called for sanity checks)
"""

import time
from typing import Optional, Tuple, Dict, List

from nova_perception.explorer import NovaExplorer
from nova_perception.vision import NovaVision
try:
    from nova_logs.logger import log
except ImportError:
    try:
    from nova_logs.logger import log
except ImportError:
    from nova_memory.logger import log


class NovaEyes:
    """
    NovaEyes is Nova's unified vision system.

    It combines pywinauto (exact element finding) with Claude (screen
    understanding) into a single interface. Nova never needs to decide
    which tool to use — NovaEyes picks the right one automatically.

    It also supports periodic sanity checks where the mentor AI reviews
    a screenshot to confirm Nova isn't hallucinating or off-track.

    Basic usage:
        eyes = NovaEyes()

        # Find a UI element — tries pywinauto first, falls back to Claude
        element = eyes.find("Trade Button", window="thinkorswim")
        if element:
            print(f"Click at ({element['center_x']}, {element['center_y']})")

        # Verify something on screen — uses Claude vision
        is_open = eyes.verify("Is ThinkOrSwim showing the Positions page?")

        # Sanity check — mentor reviews what Nova is doing
        eyes.sanity_check(mentor, expected="Viewing SOXL positions page")

        # Describe what's on screen — uses Claude vision
        desc = eyes.describe()

        # List everything Nova can see in a window — uses pywinauto
        elements = eyes.list_elements("Calculator", control_type="Button")
    """

    def __init__(self):
        self.explorer = NovaExplorer()
        self.vision = NovaVision()

        # Track what Nova thinks she's looking at — used for sanity checks
        self._current_context = "Starting up"

        # Counter for sanity check scheduling
        self._actions_since_check = 0
        self._sanity_check_interval = 10  # check every N actions

        print("[eyes] NovaEyes initialized. pywinauto + Claude Haiku ready.")

    # ── Primary: Find a UI element ─────────────────────────────────────────────

    def find(
        self,
        target: str,
        window: Optional[str] = None,
        control_type: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Find a UI element. Tries pywinauto first (exact), falls back to
        Claude vision (approximate) if pywinauto can't see it.

        Args:
            target:       Element name or description.
                          For pywinauto: use accessibility names like "Five", "Trade Button"
                          For Claude fallback: use plain English like "the buy button"
            window:       Which window to search. Partial title match.
            control_type: Optional pywinauto filter — "Button", "Edit", "Text", etc.

        Returns:
            Dict with element info and coordinates, or None if not found.
            The dict always includes:
                center_x, center_y — screen coordinates for clicking
                name               — element name
                method             — "pywinauto" or "vision_fallback"
        """
        # Tier 1: pywinauto — exact, instant, free
        element = self.explorer.find_element_flexible(
            target, window_title=window, control_type=control_type
        )

        if element is not None:
            element["method"] = "pywinauto"
            log("actions", "element_found", target=target,
                coords=f"({element['center_x']},{element['center_y']})",
                method="pywinauto")
            self._actions_since_check += 1
            return element

        # Tier 2: Claude vision — approximate, costs API call
        print(f"[eyes] pywinauto can't find '{target}' — asking Claude...")
        shot = self.vision.take_screenshot()
        coords = self.vision.locate_ui_element(shot, target)

        if coords is None:
            print(f"[eyes] Neither pywinauto nor Claude found '{target}'.")
            log("actions", "element_not_found", target=target, method="both_failed")
            return None

        # Convert image-space coords to screen-space
        img_x, img_y = coords
        scr_x, scr_y = self.vision.image_to_screen(img_x, img_y, shot)

        result = {
            "name": target,
            "control_type": "unknown",
            "center_x": scr_x,
            "center_y": scr_y,
            "method": "vision_fallback",
        }

        log("actions", "element_found", target=target,
            coords=f"({scr_x},{scr_y})", method="vision_fallback")
        self._actions_since_check += 1
        return result

    # ── Screen verification ────────────────────────────────────────────────────

    def verify(self, question: str, screenshot=None) -> bool:
        """
        Ask Claude a YES/NO question about the current screen.

        This is how Nova confirms actions worked, checks what app is in
        focus, or validates screen state before taking an action.

        Args:
            question:   A YES/NO question. Examples:
                        "Is the ThinkOrSwim Positions page visible?"
                        "Does the Calculator display show 8?"
                        "Is Paint open with a blank canvas?"
            screenshot: Optional — pass one if you already have it.
                        If None, takes a fresh screenshot.

        Returns:
            True if Claude answers YES, False otherwise.
        """
        if screenshot is None:
            screenshot = self.vision.take_screenshot()
        return self.vision.verify_ui_state(screenshot, question)

    # ── Screen description ─────────────────────────────────────────────────────

    def describe(self, screenshot=None) -> str:
        """
        Ask Claude to describe what's currently on screen.

        Useful for orientation, debugging, or when Nova needs to understand
        an unfamiliar screen before deciding what to do.

        Returns:
            Plain English description of the current screen state.
        """
        return self.vision.describe_screen(screenshot)

    # ── Take screenshot ────────────────────────────────────────────────────────

    def screenshot(self, save: bool = False):
        """
        Take a screenshot of the current screen.
        Passthrough to nova_vision for convenience.
        """
        return self.vision.take_screenshot(save=save)

    # ── Element listing ────────────────────────────────────────────────────────

    def list_elements(self, window: str, control_type: str = None) -> List[Dict]:
        """
        List all visible elements in a window via pywinauto.

        This is how Nova "looks around" to see what's clickable.
        Much faster and more accurate than asking Claude to describe the screen.

        Args:
            window:       Window title (partial match).
            control_type: Optional filter — "Button", "Edit", "Text", "MenuItem"

        Returns:
            List of element dicts with name, type, and coordinates.
        """
        return self.explorer.list_elements(window, control_type=control_type)

    def list_windows(self) -> List[Dict]:
        """List all visible windows on the desktop."""
        return self.explorer.list_windows()

    # ── Context tracking ───────────────────────────────────────────────────────

    def set_context(self, context: str):
        """
        Tell NovaEyes what Nova thinks she's doing right now.

        This is used during sanity checks — the mentor compares what
        Nova THINKS she sees vs what Claude ACTUALLY sees.

        Call this whenever Nova starts a new task or navigates to a new screen.

        Args:
            context: Plain English description of current state.
                     Example: "Viewing SOXL positions on ThinkOrSwim"
                     Example: "Drawing in Paint with the Pencil tool"

        Example:
            eyes.set_context("Navigating to ThinkOrSwim Charts page")
            autonomy.click("Charts Button", window="thinkorswim")
        """
        self._current_context = context
        print(f"[eyes] Context updated: {context}")

    # ── Sanity check — mentor reviews Nova's reality ───────────────────────────

    def sanity_check(self, mentor, expected: str = None, force: bool = False) -> bool:
        """
        Have the mentor AI review a screenshot and confirm Nova's perception
        matches reality. This catches hallucination, wrong-window errors,
        and off-track behavior.

        Can be called manually (force=True) or automatically — NovaEyes
        tracks how many actions have happened and triggers a check every
        N actions (configurable via _sanity_check_interval).

        Args:
            mentor:   NovaMentor instance.
            expected: What Nova thinks is on screen. If not provided,
                      uses the context set via set_context().
            force:    If True, runs the check regardless of the action counter.
                      If False, only checks if enough actions have elapsed.

        Returns:
            True  — screen matches expectations (Nova is on track)
            False — screen does NOT match (Nova may be hallucinating or lost)
        """
        # Only check if enough actions have passed, unless forced
        if not force and self._actions_since_check < self._sanity_check_interval:
            return True  # not time yet, assume OK

        # Reset the counter
        self._actions_since_check = 0

        context = expected or self._current_context
        print(f"[eyes] Sanity check — Nova thinks: '{context}'")

        shot = self.vision.take_screenshot(save=True)

        # Ask the mentor (using Sonnet for better reasoning) to verify
        response = mentor.ask(
            f"Nova believes she is currently: '{context}'. "
            f"Look at this screenshot and answer: "
            f"1) Does the screen match what Nova thinks? YES or NO. "
            f"2) If NO, what is actually on screen? "
            f"3) Is Nova doing anything dangerous or unexpected? "
            f"Be brief and specific.",
            screenshot=shot,
            high_stakes=True  # Uses Sonnet for this — it's a safety check
        )

        print(f"[eyes] Sanity check result: {response[:200]}")
        log("actions", "sanity_check", expected=context, result=response[:300])

        # Parse whether the mentor said YES or NO
        first_line = response.split("\n")[0].upper()
        on_track = "YES" in first_line and "NO" not in first_line.replace("NO ", "")

        if on_track:
            print(f"[eyes] Sanity check PASSED — Nova is on track.")
        else:
            print(f"[eyes] Sanity check FAILED — Nova may be off track!")
            print(f"[eyes] Mentor says: {response[:300]}")
            log("actions", "sanity_warning", expected=context, actual=response[:300])

        return on_track

    def should_sanity_check(self) -> bool:
        """
        Check if it's time for a sanity check based on the action counter.
        Call this in the autonomy loop to know when to trigger a check.

        Returns:
            True if enough actions have elapsed since the last check.
        """
        return self._actions_since_check >= self._sanity_check_interval

    def set_sanity_interval(self, interval: int):
        """
        Set how often sanity checks happen.

        Args:
            interval: Number of actions between checks.
                      Lower = more checks, more API calls, safer.
                      Higher = fewer checks, cheaper, but less oversight.
                      Default is 10.
                      For trading: recommend 5 (check every 5 actions).
                      For safe tasks like Paint: 20 is fine.
        """
        self._sanity_check_interval = interval
        print(f"[eyes] Sanity check interval set to every {interval} actions.")

    # ── Accessibility tree dump ────────────────────────────────────────────────

    def dump_tree(self, window: str, max_depth: int = 3) -> str:
        """
        Dump the full accessibility tree of a window.
        Diagnostic tool — use to check what pywinauto can see in any app.
        """
        return self.explorer.dump_tree(window, max_depth=max_depth)


# ── Standalone test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Run this to verify NovaEyes works:
        python tools/nova_eyes.py

    Tests pywinauto window listing and Claude screen description.
    """
    print("=== NovaEyes Self-Test ===\n")
    eyes = NovaEyes()

    print("[1] Listing visible windows (pywinauto)...")
    windows = eyes.list_windows()
    for w in windows[:5]:
        print(f"    {w['title'][:50]}")
    if len(windows) > 5:
        print(f"    ...and {len(windows) - 5} more")

    print(f"\n[2] Describing screen (Claude Haiku)...")
    desc = eyes.describe()
    print(f"    {desc}")

    print("NovaEyes test complete.")

