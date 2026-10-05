# @nova: Sanitize delivered text and serialize interruptible speech with explicit playback outcomes.
"""voice_gateway/speech.py — speakable text and ordered, interruptible playback.

speech_text() removes what must never be read aloud: tool markers ("[`computer_look` resulted in
130 bytes.]"), code, raw URLs and markdown. SpeechPlayer speaks queued units one at a time through
the TTS backend in a worker thread, emits backend-reported playback events (not measured sound),
and interrupt() drops queued units and stops the current one where the backend supports stop().
busy() is the half-duplex gate: while she speaks (plus a short tail) the mic is not listening, so
her own voice can never be transcribed and sent back as Cole's words.
"""
from __future__ import annotations

import asyncio
import inspect
import re
import time
from dataclasses import dataclass, field

_TOOL_MARKER = re.compile(r"[ \t]*\[`[^`\n]+` resulted in \d+ bytes\.\][ \t]*")
_FENCE = re.compile(r"```.*?(?:```|\Z)", re.S)
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_MD_LINK = re.compile(r"\[([^\]]+)\]\((?:[^)]*)\)")
_URL = re.compile(r"\bhttps?://[^\s)>\]]+")
_TABLE_RULE = re.compile(r"^[ \t]*\|?[ \t:-]*-{3,}[ \t:|-]*\|?[ \t]*$", re.M)


def speech_text(text: str) -> str:
    """The delivered words minus scaffolding, code and markup. Never adds words of its own,
    except "a link" in place of a raw URL (reading a URL aloud is noise, not content)."""
    t = _TOOL_MARKER.sub(" ", text or "")
    t = _FENCE.sub(" ", t)
    t = re.sub(r"`([^`\n]*)`", r"\1", t)
    t = _MD_IMAGE.sub(r"\1", t)
    t = _MD_LINK.sub(r"\1", t)
    t = _URL.sub("a link", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"__(.+?)__", r"\1", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])", r"\1", t)
    t = re.sub(r"^[ \t]{0,3}#{1,6}[ \t]+", "", t, flags=re.M)
    t = re.sub(r"^[ \t]*[-*+•][ \t]+", "", t, flags=re.M)
    t = _TABLE_RULE.sub("", t)
    t = re.sub(r"^[ \t]*\|(.*)\|[ \t]*$", lambda m: ", ".join(c.strip() for c in m.group(1).split("|")), t, flags=re.M)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" ?\n ?", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


@dataclass
class Utterance:
    text: str
    message_id: str = ""
    request_id: str = ""
    run_id: str = ""
    index: int = 0
    audit: dict = field(default_factory=dict)


class SpeechPlayer:
    """One worker, one queue. Create inside a running event loop and call start()."""

    def __init__(self, tts, body, tail_s: float = 0.4, on_idle=None):
        self.tts, self.body, self.tail_s, self.on_idle = tts, body, tail_s, on_idle
        self.current: Utterance | None = None
        self._queue: asyncio.Queue | None = None
        self._task = None
        self._epoch = 0
        self._closed = False
        self._last_end = float("-inf")

    def start(self) -> "SpeechPlayer":
        if self._closed or self._task is not None:
            raise RuntimeError("speech player is closed or already started")
        self._queue = asyncio.Queue()
        self._task = asyncio.get_running_loop().create_task(self._run())
        return self

    async def close(self):
        """Invalidate work before cancelling its awaiter; to_thread cannot stop synthesis.

        Backend cancellation prevents an in-flight synthesis from starting playback later.
        The backend may finish its computation after this method returns.
        """
        if not self._closed:
            self._closed = True
            self.interrupt("close")
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def say(self, utterance: Utterance) -> None:
        if self._closed or self._queue is None:
            raise RuntimeError("speech player is closed or not started")
        self._queue.put_nowait((self._epoch, utterance))

    def active(self) -> bool:
        """Speaking now, or units waiting to be spoken."""
        return self.current is not None or (self._queue is not None and not self._queue.empty())

    def busy(self) -> bool:
        """active(), or inside the tail after the last unit (the half-duplex mic gate)."""
        return self.active() or time.monotonic() - self._last_end < self.tail_s

    def interrupt(self, reason: str) -> int:
        """Drop every queued unit and stop the current one. Returns how many units were cut."""
        self._epoch += 1
        dropped = 0
        while self._queue is not None:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            self._queue.task_done()
            dropped += 1
        cut = self.current
        if cut is not None:
            stop = getattr(self.tts, "stop", None)
            if callable(stop):
                try:
                    stop()
                except Exception as error:
                    self.body.emit("diagnostic", level="warn", message=f"TTS stop failed: {error}")
        if dropped or cut is not None:
            self.body.emit("interrupt", reason=reason, dropped=dropped,
                           cut_message_id=cut.message_id if cut else "", cut_unit=cut.index if cut else None)
        return dropped + (1 if cut is not None else 0)

    async def drain(self) -> None:
        if self._queue is not None:
            await self._queue.join()

    async def _run(self):
        loop = asyncio.get_running_loop()
        hooks = _hooks(self.tts)
        while True:
            epoch, u = await self._queue.get()
            try:
                if epoch != self._epoch:
                    continue
                self.current = u
                ids = dict(message_id=u.message_id, request_id=u.request_id, run_id=u.run_id, unit=u.index)
                stale = lambda e=epoch: e != self._epoch
                started = []

                def _started(clock):
                    if started or stale():
                        return
                    started.append(clock)
                    self.body.emit("caption", text=u.text, audit=dict(u.audit), clock=clock, **ids)
                    self.body.emit("speech", phase="start", clock=clock, **ids)

                self.body.emit("state", state="speaking", message_id=u.message_id, request_id=u.request_id,
                               run_id=u.run_id)
                self.body.emit("speech", phase="requested", **ids)
                if "on_playback" not in hooks:
                    _started("requested")             # backend can't say when audio starts
                outcome = None
                result = None
                try:
                    result = await asyncio.to_thread(
                        _speak, self.tts, u.text, stale,
                        lambda: loop.call_soon_threadsafe(_started, "playback"), hooks)
                    await asyncio.sleep(0)  # receive a pending playback-start callback first
                except asyncio.CancelledError:
                    self.body.emit("speech", phase="end", outcome="cut" if started else "skipped", **ids)
                    raise
                except Exception as error:
                    outcome = "error"
                    self.body.emit("diagnostic", level="error", message=f"TTS failed: {type(error).__name__}: {error}")
                details = {}
                if isinstance(result, dict) and result.get("clock") == "process":
                    details["clock"] = "process"  # subprocess completion is not an audio clock
                if outcome is None:
                    if stale():
                        outcome = "cut" if started else "skipped"
                    elif isinstance(result, dict) and result.get("outcome") in ("completed", "no_audio", "skipped", "cut"):
                        outcome = result["outcome"]
                    elif started:
                        outcome = "played" if "playback" in started else "completed"
                    else:
                        outcome = "no_audio"
                self.body.emit("speech", phase="end", outcome=outcome, **details, **ids)
            finally:
                self.current = None
                self._last_end = time.monotonic()
                self._queue.task_done()
                if self._queue.empty() and callable(self.on_idle):
                    try:
                        self.on_idle()
                    except Exception:
                        pass


def _hooks(tts) -> set:
    try:
        params = inspect.signature(tts.speak).parameters
    except (TypeError, ValueError):
        return set()
    return {name for name in ("should_stop", "on_playback") if name in params}


def _speak(tts, text, should_stop, on_playback, hooks):
    """Call the backend with whatever cancellation and playback hooks it supports. A unit cut
    during synthesis never starts playing; on_playback marks successful audio API submission, not measured audible output."""
    kwargs = {}
    if "should_stop" in hooks:
        kwargs["should_stop"] = should_stop
    elif should_stop():
        return
    if "on_playback" in hooks:
        kwargs["on_playback"] = on_playback
    return tts.speak(text, **kwargs)
