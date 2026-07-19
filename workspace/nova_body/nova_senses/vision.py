#!/usr/bin/env python3
# Last updated: 2026-07-20 02:46:44
"""
nova_vision.py — Nova's Eyes
==============================
This module gives Nova the ability to SEE the screen.

It does two main things:
  1. Takes screenshots of the current screen state
  2. Sends those screenshots to Claude (Anthropic) to:
     a) Answer YES/NO questions about what's on screen (verify_ui_state)
     b) Describe what's visible (describe_screen)
     c) Find UI elements as a fallback when pywinauto can't see them

Uses Claude Haiku 4.5 for vision tasks — fast, cheap, and follows
instructions better than Gemini Flash for structured responses.

How it fits into the system:
  nova_hands.py    -> physical mouse/keyboard control
  nova_vision.py   -> sees the screen, finds UI elements  ← YOU ARE HERE
  nova_autonomy.py -> the action loop (click, verify, retry)
  nova_mentor.py   -> Nova's teacher (advises when Nova is stuck)
"""

import os
import io
import json
import time
import base64
import urllib.request
import pyautogui
from pathlib import Path
from typing import Optional, Tuple

# Central log manager — handles dated folders automatically
try:
    from nova_logs.logger import log, get_screenshot_dir
except ImportError:
    try:
        from nova_logs.logger import log, get_screenshot_dir
    except ImportError:
        def log(*args, **kwargs): pass
        def get_screenshot_dir():
            from pathlib import Path
            return Path("logs") / "screenshots"

# Detect screen dimensions as reported by pyautogui (used for mouse movement).
# NOTE: This may differ from actual screenshot pixel dimensions due to Windows DPI scaling.
# pyautogui.size() returns the coordinate space for moveTo()/click().
# pyautogui.screenshot() may capture at different dimensions.
SCREEN_W, SCREEN_H = pyautogui.size()

# ── HER OWN EYES, LOCALLY (2026-07-19) ──────────────────────────────────────────────────────
# This used to call the Anthropic API (claude-haiku) for every screen look. Cole, 2026-07-19:
# "I don't want the APIs being used" → then "She has her multimodal model. She should be using
# that." He's right, and it's strictly better than removing sight:
#
#   • Her llama.cpp server already boots with models/qwen3.6/mmproj-F16.gguf — the multimodal
#     projector. Qwen 3.6 can SEE. That capability was loaded into VRAM and going unused while
#     she paid a second company to look at her own screenshots.
#   • The wire already existed: nova_chat/clients/nova.py sends images to this exact endpoint as
#     OpenAI-style image_url parts. This is a swap of destination, not a new capability.
#
# So her sight is now free, private, offline, and hers — and it survives the pluck, because it
# depends on her own model server rather than someone else's billing account.
VISION_URL = os.environ.get("NOVA_LLAMA_URL", "http://127.0.0.1:8080") + "/v1/chat/completions"
VISION_MODEL = "local-qwen3.6-mmproj"      # label only; llama.cpp serves whatever is loaded

# How many times to retry an API call if it fails
MAX_RETRIES = 3

# How long to wait between retries (seconds)
RETRY_DELAY = 1.5


class NovaVision:
    """
    NovaVision is Nova's visual perception system.

    Uses Claude Haiku 4.5 for screen understanding — verifying actions worked,
    describing screen state, and as a fallback element finder when pywinauto
    can't access an app's accessibility tree.

    Basic usage:
        vision = NovaVision()

        # Take a screenshot
        shot = vision.take_screenshot()

        # Ask a YES/NO question about the screen
        is_open = vision.verify_ui_state(shot, "Is ThinkOrSwim open?")

        # Describe what's on screen
        desc = vision.describe_screen(shot)
    """

    def __init__(self):
        # No API key, no account, no bill. Her sight runs on her own model server — the same
        # llama.cpp instance that thinks her thoughts, with the mmproj already loaded.
        # If that server is down her eyes are shut, which is correct: her sight should fail
        # when SHE is down, not when someone else's service is.
        print(f"[vision] Local eyes via {VISION_URL} (Qwen 3.6 + mmproj). "
              f"Screen: {SCREEN_W}x{SCREEN_H}")

    # ── Screenshot ─────────────────────────────────────────────────────────────

    def take_screenshot(self, region: Optional[Tuple[int, int, int, int]] = None, save: bool = False):
        """
        Take a screenshot of the full screen or a specific region.

        Args:
            region: Optional (x, y, width, height) to capture just part of screen.
            save:   If True, saves the screenshot to today's dated folder.
                    Default False — hover images saved separately by nova_autonomy.

        Returns:
            A PIL Image object containing the screenshot.
        """
        shot = pyautogui.screenshot(region=region)

        if save:
            shot_dir = get_screenshot_dir()
            path = shot_dir / f"shot_{int(time.time())}.png"
            shot.save(path)

        return shot

    # ── Internal: convert image for Claude API ─────────────────────────────────

    def _shot_to_base64(self, shot) -> str:
        """Convert a PIL Image to a base64 string for Claude's vision API."""
        buf = io.BytesIO()
        shot.save(buf, format="PNG")
        return base64.standard_b64encode(buf.getvalue()).decode("utf-8")

    # ── Internal: call Claude API ──────────────────────────────────────────────

    def _call_claude(self, shot, prompt: str, as_json: bool = False):
        """
        Send a screenshot and prompt to HER OWN multimodal model. Retry up to MAX_RETRIES.

        (Name kept as _call_claude on purpose — it is called from several places in eyes.py and
        elsewhere, and a rename mid-session is how you break a working limb at 21:30. The
        destination changed on 2026-07-19; the signature deliberately did not.)

        Args:
            shot:    PIL Image — the screenshot to send
            prompt:  The question or instruction
            as_json: If True, tries to parse the response as JSON.

        Returns:
            Parsed JSON if as_json=True, raw string if False, None on failure.
        """
        img_b64 = self._shot_to_base64(shot)

        # OpenAI-compatible multimodal shape — exactly what llama.cpp serves with an mmproj
        # loaded, and the same wire nova_chat/clients/nova.py already uses for her chat images.
        payload = {
            "model": VISION_MODEL,
            "max_tokens": 1024,
            "temperature": 0.2,          # description, not invention
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                ],
            }],
        }

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    VISION_URL,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                text = (data.get("choices", [{}])[0]
                            .get("message", {})
                            .get("content", "") or "").strip()
                if not text:
                    raise ValueError("empty response from local vision model")

                if not as_json:
                    return text

                # Strip markdown fencing if the model wraps JSON in a code block
                clean = text.strip("`").lstrip("json").strip()
                return json.loads(clean)

            except json.JSONDecodeError as e:
                print(f"[vision] JSON parse error (attempt {attempt}): {e}")
                print(f"[vision] Raw response was: {text!r}")
            except Exception as e:
                print(f"[vision] local vision error (attempt {attempt}): {e}")

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

        # Say WHY, not just that it failed. Her eyes now depend on her own model server, so the
        # overwhelmingly likely cause is that llama-server isn't up — which is fixable by her.
        print(f"[vision] all retries exhausted against {VISION_URL} — is llama-server running "
              f"on :8080 with models/qwen3.6/mmproj-F16.gguf loaded?")
        return None

    # ── Element location (fallback — prefer pywinauto) ─────────────────────────

    def locate_ui_element(
        self,
        screenshot,
        element_description: str,
    ) -> Optional[Tuple[int, int]]:
        """
        Ask Claude to find a UI element on screen and return its center coordinates.

        NOTE: This is a FALLBACK method. Prefer pywinauto for element finding —
        it gives exact pixel coordinates instantly with zero API calls.
        Only use this when pywinauto can't see the element (e.g. custom-rendered
        UIs, Java apps without accessibility bridge, or web content).

        Returns coordinates in IMAGE SPACE (matching screenshot pixels).
        Use image_to_screen() to convert to pyautogui mouse coordinates.
        """
        img_w, img_h = screenshot.size

        prompt = (
            f"This screenshot is {img_w}x{img_h} pixels. "
            f"Find the CENTER pixel of: '{element_description}'. "
            "Return ONLY a valid JSON array: [X, Y] in pixel coordinates. "
            "No markdown. No explanation. Example: [1234, 567]"
        )

        coords = self._call_claude(screenshot, prompt, as_json=True)

        if not isinstance(coords, list) or len(coords) != 2:
            print(f"[vision] Invalid coordinates for '{element_description}': {coords}")
            return None

        x, y = int(coords[0]), int(coords[1])

        if not (0 <= x <= img_w and 0 <= y <= img_h):
            print(f"[vision] Coordinates ({x},{y}) outside image bounds ({img_w}x{img_h}). Rejected.")
            return None

        print(f"[vision] Located '{element_description}' at ({x}, {y}) [image: {img_w}x{img_h}]")
        return (x, y)

    # ── State verification ─────────────────────────────────────────────────────

    def verify_ui_state(self, screenshot, question: str) -> bool:
        """
        Ask Claude a YES/NO question about what is currently on screen.

        This is how Nova confirms her actions worked. After clicking something,
        she takes a new screenshot and asks "Did that work?"

        Args:
            screenshot: PIL Image — the current screen state to evaluate.
            question:   A YES/NO question about the screen.

        Returns:
            True if Claude answers YES, False otherwise.
        """
        print(f"[vision] Verifying: {question}")

        prompt = f"Answer ONLY with the word YES or NO. {question}"
        response = self._call_claude(screenshot, prompt, as_json=False)

        if response is None:
            print("[vision] Verification failed — no response from Claude.")
            return False

        result = response.strip().upper()
        print(f"[vision] Claude answered: {result}")
        return "YES" in result

    # ── Utility ────────────────────────────────────────────────────────────────

    def get_screen_dimensions(self) -> Tuple[int, int]:
        """Returns pyautogui's screen dimensions (used for mouse movement)."""
        return (SCREEN_W, SCREEN_H)

    def image_to_screen(self, img_x: int, img_y: int, screenshot) -> Tuple[int, int]:
        """
        Convert image-space coordinates to pyautogui screen-space coordinates.

        Due to Windows DPI scaling, screenshots may be captured at different
        dimensions than what pyautogui.size() reports.

        Args:
            img_x, img_y: Coordinates in image space
            screenshot:   The PIL Image the coordinates came from

        Returns:
            (screen_x, screen_y) in pyautogui space for mouse movement
        """
        img_w, img_h = screenshot.size
        scale_x = SCREEN_W / img_w
        scale_y = SCREEN_H / img_h

        screen_x = int(img_x * scale_x)
        screen_y = int(img_y * scale_y)

        if scale_x != 1.0 or scale_y != 1.0:
            print(f"[vision] DPI scaling: image ({img_w}x{img_h}) -> screen ({SCREEN_W}x{SCREEN_H}), "
                  f"factor={scale_x:.3f}x{scale_y:.3f}")
            print(f"[vision] Converted ({img_x},{img_y}) -> ({screen_x},{screen_y})")

        return (screen_x, screen_y)

    def describe_screen(self, screenshot=None) -> str:
        """
        Ask Claude to describe what is currently on screen in plain English.
        Useful for debugging or when Nova needs to understand her surroundings.
        """
        if screenshot is None:
            screenshot = self.take_screenshot()

        img_w, img_h = screenshot.size
        prompt = (
            f"This screenshot is {img_w}x{img_h} pixels. "
            "In 2-3 sentences, describe what application and UI state is "
            "currently visible on screen."
        )
        return self._call_claude(screenshot, prompt, as_json=False) or "[no description available]"


# ── Standalone test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Run this file directly to test Nova's vision system:
        python tools/nova_vision.py

    It will take a screenshot and ask Claude to describe what it sees.
    """
    print("=== NovaVision Self-Test ===")
    v = NovaVision()

    w, h = v.get_screen_dimensions()
    print(f"Screen dimensions: {w}x{h}")

    print("Taking screenshot...")
    shot = v.take_screenshot()

    print("Asking Claude to describe the screen...")
    desc = v.describe_screen(shot)
    print(f"\nClaude sees: {desc}")

    print("Vision system test complete.")


