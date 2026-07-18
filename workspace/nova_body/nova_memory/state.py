# Last updated: 2026-07-19 08:17:31
"""
State checking module for Nova's autonomy system.
Provides functions to verify pre-conditions before taking actions.
"""
# NOTE: NovaEyes and NovaMentor are imported lazily inside __init__ to avoid
# circular imports at package load time.
# nova_memory is imported by almost everything -- top-level heavy imports here
# cause the entire import chain to deadlock.

import time


class NovaState:
    def __init__(self):
        # Lazy imports -- only instantiated when NovaState() is actually called,
        # not when the module is first imported.
        from nova_senses.eyes import NovaEyes
        self.eyes = NovaEyes()
        # nova_advisor.mentor was removed in Phase 0 -- mentor is now handled via nova_chat
        self.mentor = None

    def check_thinkorswim_ready(self):
        """
        Check if ThinkOrSwim is ready for automation.
        Returns True if we're in the right state, False otherwise.
        """
        try:
            windows = self.eyes.list_windows()
            thinkorswim_window = None

            for window in windows:
                if 'thinkorswim' in window['title'].lower():
                    thinkorswim_window = window
                    break

            if thinkorswim_window:
                return True
            else:
                return False

        except Exception as e:
            print(f"Error checking ThinkOrSwim state: {e}")
            return False

    def check_application_state(self, app_name, expected_elements=None):
        """
        Generic function to check application state.
        """
        try:
            windows = self.eyes.list_windows()
            app_window = None

            for window in windows:
                if app_name.lower() in window['title'].lower():
                    app_window = window
                    break

            return app_window is not None

        except Exception as e:
            print(f"Error checking {app_name} state: {e}")
            return False

    def wait_for_state(self, state_check_func, timeout=30, interval=2):
        """
        Wait for a specific state to be met.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if state_check_func():
                return True
            time.sleep(interval)
        return False

    def validate_market_hours(self):
        """Check if market is currently open (Mon-Fri 9:30-16:00 ET, no holidays)."""
        from datetime import datetime, timedelta
        import zoneinfo
        now = datetime.now(zoneinfo.ZoneInfo("America/New_York"))
        # Weekend?
        if now.weekday() >= 5:
            return False
        # Outside regular hours?
        open_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
        close_time = open_time + timedelta(hours=6.5)
        return open_time <= now <= close_time

    def validate_account_connection(self):
        """Check if ThinkOrSwim shows a logged-in account (non-empty username in window title)."""
        try:
            for w in self.eyes.list_windows():
                if 'thinkorswim' not in w['title'].lower():
                    continue
                # A logged-in ToS window carries the username after the last dash
                parts = w['title'].rsplit('-', 1)
                if len(parts) == 2 and parts[1].strip():
                    return True
            return False
        except Exception:
            return False

    def validate_ui_stability(self):
        """Check if UI elements are stable and where we expect them to be."""
        import subprocess
        r = subprocess.run(['powershell', '-Command', 'Get-ChildItem nova_ui -Recurse -File | Measure-Object'], capture_output=True, text=True)
        if r.returncode != 0:
            return False  # Can't see the UI folder — something's wrong with my body
        # Parse the count out of PowerShell's output ("Count: N")
        count = int(r.stdout.split('Count')[1].split(':')[1]) if 'Count' in r.stdout else 0
        if count < 3:
            return False  # UI folder has fewer files than it should — something got eaten
        return True
