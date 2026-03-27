#!/usr/bin/env python3
"""
nova_explorer.py — Nova's UI Explorer
========================================
This module uses Windows accessibility APIs (via pywinauto) to find
UI elements on screen with EXACT pixel coordinates. No screenshots,
no vision API calls, no guessing.

This replaces vision-based element finding for any app that exposes
its UI through Windows UI Automation. That includes most native apps,
browsers, and many Java apps (with Java Access Bridge enabled).

For apps where pywinauto can't see elements (custom-rendered UIs,
some games), Nova falls back to nova_vision.py (Claude-based).

How it fits into the system:
  nova_explorer.py → finds UI elements via accessibility API  ← YOU ARE HERE
  nova_vision.py   → screen verification + vision fallback
  nova_hands.py    → physical mouse/keyboard control
  nova_autonomy.py → the action loop (find, click, verify)
  nova_mentor.py   → Nova's teacher (advises when stuck)

Requirements:
  pip install pywinauto
"""

import time
from typing import Optional, Tuple, List, Dict
from pywinauto import Desktop, Application
from pywinauto.findwindows import ElementNotFoundError

# Central log manager
try:
    from nova_logs.logger import log
except ImportError:
    try:
    from nova_logs.logger import log
except ImportError:
    from nova_memory.logger import log


class NovaExplorer:
    """
    NovaExplorer finds UI elements using Windows accessibility APIs.

    Unlike vision-based finding (sending screenshots to an AI and hoping
    it guesses the right coordinates), pywinauto reads the actual UI tree
    that Windows maintains. Coordinates are exact, every time, instantly.

    Basic usage:
        explorer = NovaExplorer()

        # Find a button by name in any window
        btn = explorer.find_element("Five", window_title="Calculator")
        if btn:
            print(f"Button center: ({btn['center_x']}, {btn['center_y']})")

        # List all buttons in a window
        buttons = explorer.list_elements("Calculator", control_type="Button")
        for b in buttons:
            print(f"{b['name']}: ({b['center_x']}, {b['center_y']})")

        # Find any window by partial title
        windows = explorer.list_windows()
    """

    def __init__(self):
        # Use UIA backend — it's the modern Windows accessibility API
        # and works with most apps including UWP, WPF, and Win32.
        self.backend = "uia"
        print("[explorer] NovaExplorer initialized. Using Windows UI Automation.")

    # ── Window discovery ───────────────────────────────────────────────────────

    def list_windows(self) -> List[Dict]:
        """
        List all visible windows on the desktop.

        Returns a list of dicts with window title, handle, and rectangle.
        Useful for Nova to understand what's on screen without a screenshot.

        Example:
            windows = explorer.list_windows()
            for w in windows:
                print(f"{w['title']} — at ({w['left']}, {w['top']})")
        """
        desktop = Desktop(backend=self.backend)
        windows = []

        for win in desktop.windows():
            try:
                title = win.window_text()
                if not title or not win.is_visible():
                    continue
                rect = win.rectangle()
                windows.append({
                    "title": title,
                    "handle": win.handle,
                    "left": rect.left,
                    "top": rect.top,
                    "right": rect.right,
                    "bottom": rect.bottom,
                    "width": rect.right - rect.left,
                    "height": rect.bottom - rect.top,
                })
            except Exception:
                continue

        print(f"[explorer] Found {len(windows)} visible windows.")
        return windows

    def find_window(self, title_contains: str):
        """
        Connect to a window by partial title match.

        Args:
            title_contains: Substring to match against window titles.
                            Case-insensitive. Example: "Calculator", "ThinkOrSwim"

        Returns:
            A pywinauto WindowSpecification object, or None if not found.

        Example:
            win = explorer.find_window("Calculator")
            if win:
                buttons = win.descendants(control_type="Button")
        """
        try:
            app = Application(backend=self.backend).connect(
                title_re=f".*{title_contains}.*",
                timeout=3
            )
            window = app.window(title_re=f".*{title_contains}.*")
            title = window.window_text()
            print(f"[explorer] Connected to: '{title}'")
            return window
        except ElementNotFoundError:
            print(f"[explorer] No window found matching '{title_contains}'.")
            return None
        except Exception as e:
            print(f"[explorer] Error connecting to '{title_contains}': {e}")
            return None

    # ── Element finding ────────────────────────────────────────────────────────

    def find_element(
        self,
        name: str,
        window_title: str = None,
        control_type: str = None,
        window=None,
    ) -> Optional[Dict]:
        """
        Find a single UI element by name. Returns its center coordinates.

        This is the primary method nova_autonomy.py uses instead of
        vision-based locate_ui_element. Exact coordinates, zero API calls.

        Args:
            name:          The element's accessible name (what pywinauto sees).
                           Examples: "Five", "Plus", "Login", "Submit Order"
                           Use list_elements() first to see what names are available.

            window_title:  Which window to search in. Partial match.
                           Example: "Calculator", "ThinkOrSwim"
                           If None, searches the focused window.

            control_type:  Optional filter. Examples: "Button", "Edit", "Text"
                           If None, searches all control types.

            window:        Optional — pass a pywinauto window object directly
                           if you already have one from find_window().

        Returns:
            Dict with element info if found:
                {
                    "name": "Five",
                    "control_type": "Button",
                    "center_x": 2254,
                    "center_y": 808,
                    "left": 2199, "top": 766, "right": 2310, "bottom": 850
                }
            None if element is not found.
        """
        # Get the window to search in
        win = window or (self.find_window(window_title) if window_title else None)
        if win is None:
            print(f"[explorer] No window to search in.")
            return None

        try:
            # Build search criteria
            criteria = {"title": name}
            if control_type:
                criteria["control_type"] = control_type

            element = win.child_window(**criteria)
            rect = element.rectangle()

            result = {
                "name": name,
                "control_type": control_type or element.element_info.control_type,
                "center_x": (rect.left + rect.right) // 2,
                "center_y": (rect.top + rect.bottom) // 2,
                "left": rect.left,
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom,
            }

            print(f"[explorer] Found '{name}' at ({result['center_x']}, {result['center_y']})")
            log("actions", "element_found", target=name,
                coords=f"({result['center_x']},{result['center_y']})",
                method="pywinauto")
            return result

        except ElementNotFoundError:
            print(f"[explorer] Element '{name}' not found in window.")
            return None
        except Exception as e:
            print(f"[explorer] Error finding '{name}': {e}")
            return None

    def find_element_flexible(
        self,
        name: str,
        window_title: str,
        control_type: str = None,
    ) -> Optional[Dict]:
        """
        Find an element with flexible name matching.

        Tries exact match first, then searches all elements for a partial
        case-insensitive match. Useful when you don't know the exact
        accessible name (e.g. "5" vs "Five" vs "five" vs "Number 5").

        Args:
            name:          What to search for. Can be partial.
            window_title:  Which window to search in.
            control_type:  Optional filter by control type.

        Returns:
            Same dict as find_element(), or None.
        """
        # Try exact match first
        result = self.find_element(name, window_title=window_title,
                                   control_type=control_type)
        if result:
            return result

        # Exact match failed — do a fuzzy search
        print(f"[explorer] Exact match failed for '{name}'. Trying fuzzy search...")
        win = self.find_window(window_title)
        if not win:
            return None

        name_lower = name.lower()
        elements = win.descendants(control_type=control_type) if control_type else win.descendants()

        for el in elements:
            try:
                el_name = el.window_text()
                if not el_name:
                    continue

                # Check if the search term is contained in the element name
                # or the element name is contained in the search term
                if (name_lower in el_name.lower() or
                    el_name.lower() in name_lower):
                    rect = el.rectangle()
                    result = {
                        "name": el_name,
                        "control_type": el.element_info.control_type,
                        "center_x": (rect.left + rect.right) // 2,
                        "center_y": (rect.top + rect.bottom) // 2,
                        "left": rect.left,
                        "top": rect.top,
                        "right": rect.right,
                        "bottom": rect.bottom,
                    }
                    print(f"[explorer] Fuzzy matched '{name}' -> '{el_name}' at "
                          f"({result['center_x']}, {result['center_y']})")
                    log("actions", "element_found", target=name, matched=el_name,
                        coords=f"({result['center_x']},{result['center_y']})",
                        method="pywinauto_fuzzy")
                    return result
            except Exception:
                continue

        print(f"[explorer] No element matching '{name}' found anywhere in '{window_title}'.")
        return None

    # ── Element listing ────────────────────────────────────────────────────────

    def list_elements(
        self,
        window_title: str,
        control_type: str = None,
        window=None,
    ) -> List[Dict]:
        """
        List all elements (or elements of a specific type) in a window.

        This is Nova's way of "looking around" a window to see what's available.
        Much faster and more accurate than asking a vision model to describe
        the screen.

        Args:
            window_title: Which window to list elements from.
            control_type: Optional filter. "Button", "Edit", "Text", "MenuItem", etc.
            window:       Optional pre-connected window object.

        Returns:
            List of dicts, each with name, control_type, center_x, center_y, and rect.
        """
        win = window or self.find_window(window_title)
        if not win:
            return []

        elements = []
        descendants = win.descendants(control_type=control_type) if control_type else win.descendants()

        for el in descendants:
            try:
                el_name = el.window_text()
                if not el_name:
                    continue
                rect = el.rectangle()
                elements.append({
                    "name": el_name,
                    "control_type": el.element_info.control_type,
                    "center_x": (rect.left + rect.right) // 2,
                    "center_y": (rect.top + rect.bottom) // 2,
                    "left": rect.left,
                    "top": rect.top,
                    "right": rect.right,
                    "bottom": rect.bottom,
                })
            except Exception:
                continue

        print(f"[explorer] Found {len(elements)} elements in '{window_title}'"
              + (f" (type: {control_type})" if control_type else ""))
        return elements

    # ── Accessibility tree dump ────────────────────────────────────────────────

    def dump_tree(self, window_title: str, max_depth: int = 3) -> str:
        """
        Dump the accessibility tree of a window as a readable string.

        This is the diagnostic tool for checking whether pywinauto can
        see an app's UI elements. Run this on ThinkOrSwim, Chrome, or
        any app to see what Nova has access to.

        Args:
            window_title: Which window to dump. Partial match.
            max_depth:    How deep to traverse the tree. Default 3.
                          Higher = more detail but more output.

        Returns:
            A formatted string showing the element hierarchy.

        Example:
            tree = explorer.dump_tree("ThinkOrSwim")
            print(tree)
        """
        win = self.find_window(window_title)
        if not win:
            return f"No window found matching '{window_title}'"

        lines = []
        self._walk_tree(win, lines, depth=0, max_depth=max_depth)
        result = "\n".join(lines)
        print(f"[explorer] Tree dump: {len(lines)} elements found.")
        return result

    def _walk_tree(self, element, lines, depth, max_depth):
        """Recursively walk the UI tree and collect element info."""
        if depth > max_depth:
            return

        try:
            name = element.window_text() or "(unnamed)"
            ctrl = element.element_info.control_type
            rect = element.rectangle()
            cx = (rect.left + rect.right) // 2
            cy = (rect.top + rect.bottom) // 2

            indent = "  " * depth
            lines.append(f"{indent}[{ctrl}] '{name}' — center ({cx}, {cy})")

            for child in element.children():
                self._walk_tree(child, lines, depth + 1, max_depth)
        except Exception:
            pass


# ── Standalone test / diagnostic tool ──────────────────────────────────────────

if __name__ == "__main__":
    """
    Run this file to explore any window's UI tree:
        python tools/nova_explorer.py

    If a window title is passed as an argument, it dumps that window's tree.
    Otherwise, it lists all visible windows.

    Examples:
        python tools/nova_explorer.py                    # list all windows
        python tools/nova_explorer.py Calculator         # dump Calculator tree
        python tools/nova_explorer.py ThinkOrSwim        # dump ThinkOrSwim tree
    """
    import sys

    explorer = NovaExplorer()

    if len(sys.argv) > 1:
        # Dump the tree for the specified window
        target = " ".join(sys.argv[1:])
        print(f"\n=== UI Tree Dump: '{target}' ===\n")
        tree = explorer.dump_tree(target, max_depth=4)
        print(tree)

        print(f"\n=== Buttons in '{target}' ===\n")
        buttons = explorer.list_elements(target, control_type="Button")
        for b in buttons:
            print(f"  {b['name']:<25} center=({b['center_x']:>5}, {b['center_y']:>5})  "
                  f"rect=({b['left']}, {b['top']}, {b['right']}, {b['bottom']})")
    else:
        # List all visible windows
        print("\n=== Visible Windows ===\n")
        windows = explorer.list_windows()
        for w in windows:
            print(f"  {w['title'][:50]:<50}  ({w['width']}x{w['height']}) at ({w['left']}, {w['top']})")
        print(f"\nTo dump a window's tree: python tools/nova_explorer.py <window title>")

