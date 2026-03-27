#!/usr/bin/env python3
"""
nova_hands.py — Nova's Hands
==============================
This module handles all physical mouse and keyboard control.
It uses pyautogui to move the mouse, click, and type on the real screen.

Think of this as Nova's nervous system for physical actions.
Her brain (nova_autonomy.py) decides WHAT to do.
Her eyes (nova_vision.py) decide WHERE to do it.
Her hands (this file) actually DO it.

How it fits into the system:
  nova_hands.py    → physical mouse/keyboard control  ← YOU ARE HERE
  nova_vision.py   → sees the screen, finds UI elements
  nova_autonomy.py → the action loop (click, verify, retry)
  nova_mentor.py   → Nova's teacher (advises when Nova is stuck)
"""

import sys
import time
import pyautogui
from pathlib import Path

# Add the workspace to Python's search path
# so other Nova modules can be imported from anywhere
workspace = Path.cwd()
sys.path.insert(0, str(workspace))
sys.path.insert(0, str(workspace / "tools"))

# ── Safety settings ────────────────────────────────────────────────────────────
# FAILSAFE: If pyautogui's failsafe is enabled, moving the mouse to the
# very top-left corner of the screen (0, 0) will throw an exception and
# stop all automation. This is a backup emergency stop.
# The primary kill switch is Left-CTRL x3 (defined in nova_rules.py).
pyautogui.FAILSAFE = True

# How long pyautogui waits between each action by default (in seconds).
# 0.1 = 100ms pause between actions. Prevents Nova from acting too fast
# for the screen to keep up.
pyautogui.PAUSE = 0.1


class NovaHands:
    """
    NovaHands controls the physical mouse and keyboard.

    All coordinates are in pixels, matching the real screen resolution.
    Make sure the DPI fix in nova_autonomy.py has run before using this,
    so Windows reports real pixel coordinates instead of scaled ones.

    Basic usage:
        hands = NovaHands()

        # Move mouse to a position
        hands.move_to(960, 540)

        # Click at a position
        hands.move_and_click(960, 540, label="center of screen")

        # Type some text
        hands.type_text("hello world")
    """

    def __init__(self):
        """Set up Nova's hands and confirm the screen dimensions."""
        self.screen_width, self.screen_height = pyautogui.size()
        print(f"[hands] NovaHands initialized. Screen: {self.screen_width}x{self.screen_height}")

    # ── Mouse movement ─────────────────────────────────────────────────────────

    def move_to(self, x: int, y: int, duration: float = 0.4):
        """
        Move the mouse cursor to (x, y) smoothly.

        This is the primary method nova_autonomy.py uses to position
        the mouse before clicking. The smooth movement (duration) makes
        it look natural and gives the UI time to respond (like hover states).

        Args:
            x:        Horizontal pixel coordinate (left = 0)
            y:        Vertical pixel coordinate (top = 0)
            duration: How long the movement takes in seconds.
                      0.4 = smooth and visible. 0.0 = instant jump.

        Returns:
            True if successful, False if an error occurred.

        Example:
            hands.move_to(1440, 900)  # move to center of 2880x1800 screen
        """
        print(f"[hands] Moving mouse to ({x}, {y})...")
        try:
            pyautogui.moveTo(x, y, duration=duration)
            print(f"[hands] Mouse moved to ({x}, {y}).")
            return True
        except Exception as e:
            print(f"[hands] Move failed: {e}")
            return False

    def move_mouse(self, coordinates: tuple, duration: float = 0.4):
        """
        Move mouse using a (x, y) tuple. Kept for backwards compatibility.

        nova_autonomy.py uses move_to(x, y) directly.
        This method exists so older code that passes a tuple still works.

        Args:
            coordinates: (x, y) tuple
            duration:    Movement duration in seconds

        Example:
            hands.move_mouse((960, 540))
        """
        x, y = coordinates
        return self.move_to(x, y, duration=duration)

    # ── Mouse clicking ─────────────────────────────────────────────────────────

    def move_and_click(self, x: int, y: int, label: str = "", duration: float = 0.4):
        """
        Move to (x, y) and click. This is the primary click method.

        nova_autonomy.py calls this after confirming the mouse is in the
        right place (the ALIGN step). The label is just for logging.

        Args:
            x:        Horizontal pixel coordinate
            y:        Vertical pixel coordinate
            label:    Optional description for logging. Example: "Login button"
            duration: Mouse movement duration in seconds

        Returns:
            True if successful, False if an error occurred.

        Example:
            hands.move_and_click(960, 540, label="Login button")
        """
        log_label = f"'{label}'" if label else f"({x}, {y})"
        print(f"[hands] Clicking {log_label} at ({x}, {y})...")
        try:
            pyautogui.moveTo(x, y, duration=duration)
            time.sleep(0.1)  # tiny pause between move and click feels more natural
            pyautogui.click()
            print(f"[hands] Clicked {log_label} successfully.")
            return True
        except Exception as e:
            print(f"[hands] Click failed on {log_label}: {e}")
            return False

    def click(self, coordinates: tuple, duration: float = 0.4):
        """
        Click using a (x, y) tuple. Kept for backwards compatibility.

        Args:
            coordinates: (x, y) tuple
            duration:    Mouse movement duration in seconds

        Example:
            hands.click((960, 540))
        """
        x, y = coordinates
        return self.move_and_click(x, y, duration=duration)

    def right_click(self, x: int, y: int, duration: float = 0.4):
        """
        Move to (x, y) and right-click (opens context menus).

        Args:
            x, y:     Pixel coordinates
            duration: Mouse movement duration in seconds

        Example:
            hands.right_click(960, 540)
        """
        print(f"[hands] Right-clicking at ({x}, {y})...")
        try:
            pyautogui.moveTo(x, y, duration=duration)
            time.sleep(0.1)
            pyautogui.rightClick()
            print(f"[hands] Right-clicked at ({x}, {y}).")
            return True
        except Exception as e:
            print(f"[hands] Right-click failed: {e}")
            return False

    def double_click(self, x: int, y: int, duration: float = 0.4):
        """
        Move to (x, y) and double-click (opens files, apps, etc.)

        Args:
            x, y:     Pixel coordinates
            duration: Mouse movement duration in seconds

        Example:
            hands.double_click(960, 540)
        """
        print(f"[hands] Double-clicking at ({x}, {y})...")
        try:
            pyautogui.moveTo(x, y, duration=duration)
            time.sleep(0.1)
            pyautogui.doubleClick()
            print(f"[hands] Double-clicked at ({x}, {y}).")
            return True
        except Exception as e:
            print(f"[hands] Double-click failed: {e}")
            return False

    # ── Keyboard typing ────────────────────────────────────────────────────────

    def type_text(self, text: str, interval: float = 0.05):
        """
        Type a string of text using the keyboard.

        This types into whatever field or application currently has focus.
        Make sure to click the target field first with move_and_click()
        before calling this.

        Args:
            text:     The text to type. Example: "myemail@example.com"
            interval: How long to pause between each character in seconds.
                      0.05 = 50ms per character. Slower = more reliable
                      on systems that can't keep up with fast typing.

        Returns:
            True if successful, False if an error occurred.

        Example:
            hands.move_and_click(500, 300, label="username field")
            time.sleep(0.3)
            hands.type_text("myemail@example.com")
        """
        print(f"[hands] Typing: '{text[:20]}{'...' if len(text) > 20 else ''}'")
        try:
            pyautogui.typewrite(text, interval=interval)
            print(f"[hands] Typed successfully.")
            return True
        except Exception as e:
            print(f"[hands] Typing failed: {e}")
            return False

    def press_key(self, key: str):
        """
        Press a single keyboard key.

        Useful for Enter, Escape, Tab, arrow keys, etc.
        For a full list of valid key names, see:
        https://pyautogui.readthedocs.io/en/latest/keyboard.html

        Args:
            key: Key name as a string. Examples:
                 'enter', 'escape', 'tab', 'space',
                 'up', 'down', 'left', 'right',
                 'ctrl', 'alt', 'shift', 'delete'

        Returns:
            True if successful, False if an error occurred.

        Example:
            hands.press_key('enter')   # press Enter
            hands.press_key('escape')  # press Escape
        """
        print(f"[hands] Pressing key: '{key}'")
        try:
            pyautogui.press(key)
            print(f"[hands] Key '{key}' pressed.")
            return True
        except Exception as e:
            print(f"[hands] Key press failed: {e}")
            return False

    def hotkey(self, *keys):
        """
        Press a keyboard shortcut (multiple keys at once).

        Args:
            *keys: Key names to press simultaneously.

        Returns:
            True if successful, False if an error occurred.

        Example:
            hands.hotkey('ctrl', 'c')   # Copy
            hands.hotkey('ctrl', 'v')   # Paste
            hands.hotkey('alt', 'tab')  # Switch windows
            hands.hotkey('win', 'd')    # Show desktop
        """
        key_combo = " + ".join(keys)
        print(f"[hands] Pressing hotkey: {key_combo}")
        try:
            pyautogui.hotkey(*keys)
            print(f"[hands] Hotkey {key_combo} pressed.")
            return True
        except Exception as e:
            print(f"[hands] Hotkey failed: {e}")
            return False

    # ── Screen info ────────────────────────────────────────────────────────────

    def get_screen_size(self):
        """
        Returns the screen dimensions as (width, height).

        Example:
            width, height = hands.get_screen_size()
            print(f"Screen is {width}x{height}")
        """
        return (self.screen_width, self.screen_height)

    def get_mouse_position(self):
        """
        Returns the current mouse cursor position as (x, y).

        Useful for debugging — see where the mouse actually is.

        Example:
            x, y = hands.get_mouse_position()
            print(f"Mouse is at ({x}, {y})")
        """
        pos = pyautogui.position()
        return (pos.x, pos.y)


# ── Standalone test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Run this file directly to test Nova's hands:
        python tools/nova_hands.py

    The mouse will move to the center of your screen and back.
    If you see it move physically, the hands are working.
    """
    print("=== NovaHands Self-Test ===")
    hands = NovaHands()

    w, h = hands.get_screen_size()
    print(f"Screen: {w}x{h}")

    cx, cy = w // 2, h // 2
    print(f"Moving mouse to screen center ({cx}, {cy})...")
    hands.move_to(cx, cy)
    time.sleep(0.5)

    print("Moving to top-left corner...")
    hands.move_to(200, 200)
    time.sleep(0.5)

    print("Moving back to center...")
    hands.move_to(cx, cy)

    x, y = hands.get_mouse_position()
    print(f"Final mouse position: ({x}, {y})")
    print("NovaHands self-test complete.")
