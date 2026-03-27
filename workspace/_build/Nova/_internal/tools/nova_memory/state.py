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
        from nova_perception.eyes import NovaEyes
        from nova_advisor.mentor import NovaMentor
        self.eyes = NovaEyes()
        self.mentor = NovaMentor()

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
        """Check if market is currently open."""
        return True  # Placeholder

    def validate_account_connection(self):
        """Check if account is connected and authenticated."""
        return True  # Placeholder

    def validate_ui_stability(self):
        """Check if UI elements are stable and where we expect them to be."""
        return True  # Placeholder
