# Last updated: 2026-10-05 21:33:05
# @nova: Queue acknowledged Nova mode changes and replace owned services while keeping the controller window and console alive.
from __future__ import annotations

import threading
import time


class NovaModeState:
    """A single launcher-consumed request; acknowledgements precede worker shutdown."""
    def __init__(self, chat_only, handler, clock=time.monotonic):
        self.chat_only = bool(chat_only)
        self.handler, self.clock = handler, clock
        self._lock = threading.RLock()
        self._target = None
        self._taken = False
        self._ready_at = None
        self.error = None

    def snapshot(self):
        with self._lock:
            pending = self._target is not None
            state = ("stopping" if self._target else "starting") if pending else (
                "error" if self.error else "off" if self.chat_only else "on")
            message = ("Stopping Nova; the controller window stays open." if self._target else
                       "Starting Nova; the controller will reconnect.") if pending else (
                self.error or ("Nova is off. Chat and collaboration remain available." if self.chat_only else
                               "Nova is on."))
            return {"ok": not bool(self.error), "state": state, "pending": pending,
                    "target": ("off" if self._target else "on") if pending else None,
                    "chat_only": self.chat_only, "message": message, "error": self.error}

    def request(self, chat_only):
        with self._lock:
            if self._target is not None:
                if self._target != chat_only:
                    return {**self.snapshot(), "ok": False, "error": "A different Nova mode change is pending."}, 409
                return {**self.snapshot(), "accepted": True}, 202
            if self.chat_only == chat_only and not self.error:
                return {**self.snapshot(), "accepted": False}, 200
            self._target = bool(chat_only)
            self._taken = False
            self._ready_at = self.clock() + 1.0
            self.error = None
            return {**self.snapshot(), "accepted": True}, 202

    def process(self):
        with self._lock:
            if self._target is None or self._taken or self.clock() < self._ready_at:
                return False
            target = self._target
            self._taken = True
        try:
            result = self.handler(target)
            chat_only = bool(result["chat_only"])
            error = result.get("error")
        except Exception as exc:
            chat_only, error = self.chat_only, str(exc) or type(exc).__name__
        with self._lock:
            self.chat_only, self.error = chat_only, error
            self._target, self._ready_at = None, None
            self._taken = False
        return True


class NovaServiceSwitch:
    """Own only the five replaceable services, never the app window or console."""
    ORDER = ("guardian", "watcher", "nova", "llama", "witness")

    def __init__(self, services, *, start, stop, verify_down, set_mode, wait_model,
                 wait_worker, wait_witness, publish, cancelled=lambda: False):
        self.services = services
        self.start, self.stop = start, stop
        self.verify_down, self.set_mode = verify_down, set_mode
        self.wait_model, self.wait_worker, self.wait_witness = wait_model, wait_worker, wait_witness
        self.publish, self.cancelled = publish, cancelled
        self.chat_only = True

    def _down(self):
        for name in self.ORDER:
            process = self.services.get(name)
            self.stop[name](process)
            if process is not None and process.poll() is None:
                try:
                    process.wait(timeout=3)
                except Exception:
                    pass
                if process.poll() is None:
                    raise RuntimeError(f"{name} did not stop; mode change was not continued.")
            self.services[name] = None
        self.verify_down()
        self.publish()

    def _up(self, chat_only):
        self.set_mode(chat_only)
        self.chat_only = chat_only
        if self.cancelled():
            raise RuntimeError("App shutdown requested during the mode change.")
        if not chat_only:
            self.services["llama"] = self.start["llama"]()
            if not self.wait_model():
                raise RuntimeError("Nova's model did not become ready.")
            if self.cancelled():
                raise RuntimeError("App shutdown requested during model loading.")
            self.services["witness"] = self.start["witness"]()
        self.services["nova"] = self.start["nova"]()
        if not self.wait_worker(chat_only):
            raise RuntimeError("The controller worker did not become ready in the requested mode.")
        if not chat_only:
            if self.services["witness"] is not None:
                self.wait_witness()  # Witness availability is fail-open, as at ordinary launch.
            if self.cancelled():
                raise RuntimeError("App shutdown requested while starting Nova.")
            self.services["watcher"] = self.start["watcher"]()
            self.services["guardian"] = self.start["guardian"]()
        self.publish()

    def __call__(self, chat_only):
        try:
            self._down()
            self._up(chat_only)
            return {"chat_only": chat_only}
        except (Exception, SystemExit) as exc:
            error = str(exc) or type(exc).__name__
            # A failed startup must release VRAM and restore the usable chat-only face.
            try:
                self._down()
                self._up(True)
            except (Exception, SystemExit) as recovery:
                return {"chat_only": self.chat_only,
                        "error": f"{error} Chat-only recovery also failed: {recovery}"}
            return {"chat_only": True, "error": f"{error} Nova is off; the chat-only controller was restored."}
