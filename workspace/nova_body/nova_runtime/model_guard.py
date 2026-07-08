# Last updated: 2026-07-09 01:08:03
# @nova: ModelGuard — runtime guard on her model-calling. Two failsafes, both body-owned
#        because they protect HER regardless of which face is attached:
#          1) rate-limit  — caps Nova-initiated messages per window (protects API budget
#                           from a runaway loop).
#          2) error backoff — after N consecutive llama errors, signals "pause autonomy"
#                           so the daemon stops hammering a dead model.
#        Pure decision logic; the caller performs the action (mute / pause / notify).
"""
nova_runtime/model_guard.py — relocated faithfully from general_tools/nova_chat/server.py
(the `_NOVA_RATE_LIMIT`/`_nova_msg_times` failsafe in `/api/inject_message`, and the
`_llama_error_streak`/`_LLAMA_ERROR_BACKOFF` logic in `run_ai_response`'s on_error/on_done).
Behavior unchanged; it just lives in the body and only *decides* — the host still does the
muting/pausing/broadcasting on its say-so.
"""

import time


class ModelGuard:
    def __init__(self, rate_limit: int = 4, rate_window: int = 60, error_backoff: int = 3):
        self.rate_limit = rate_limit       # max Nova-initiated messages per window
        self.rate_window = rate_window     # seconds
        self.error_backoff = error_backoff # consecutive llama errors before pausing autonomy
        self._msg_times: list[float] = []  # rolling timestamps of Nova messages
        self.throttled = False
        self.error_streak = 0

    # ── rate-limit failsafe ───────────────────────────────────────────────────────

    def allow_message(self, now: float = None) -> bool:
        """Call before a Nova-initiated message. Returns False (and sets `throttled`) if she
        has exceeded `rate_limit` messages within the rolling `rate_window`."""
        now = time.time() if now is None else now
        self._msg_times = [t for t in self._msg_times if now - t < self.rate_window]
        if len(self._msg_times) >= self.rate_limit:
            self.throttled = True
            return False
        self._msg_times.append(now)
        self.throttled = False
        return True

    # ── consecutive-llama-error backoff ────────────────────────────────────────────

    @staticmethod
    def is_llama_error(err) -> bool:
        s = str(err).lower()
        return ("llama" in s) or ("streaming error" in s) or ("500 internal server error" in s)

    def record_error(self, err) -> bool:
        """Record a generation error. Returns True EXACTLY when the consecutive-llama-error
        streak first reaches `error_backoff` — the caller should then pause autonomy and post
        one System notice. (Returns False on subsequent errors so the notice fires once.)"""
        if self.is_llama_error(err):
            self.error_streak += 1
            return self.error_streak == self.error_backoff
        return False

    def record_success(self) -> None:
        """A successful generation clears the streak — the model is alive again."""
        self.error_streak = 0

    def reset(self) -> None:
        """Clear the throttle + rate window — e.g. Cole speaking un-mutes her."""
        self._msg_times = []
        self.throttled = False
