# @nova: Exchange correlated voice requests and response events with the Nova Chat WebSocket server.
#   send Cole's transcribed speech in with a fresh request_id, receive her reply events out.
#   Speaks the same protocol the browser UI speaks; the server needs no voice-specific code path.
"""voice_gateway/nova_link.py — talk to Nova over her chat WebSocket.

Outbound: {"type":"message","content":<text>,"speaker":"Cole","register":<r>,"request_id":<hex>}
Inbound frames the voice uses (server contract: nova_chat/response_events.py, 2026-10-05):
    user_message   {id, request_id, author, content}   the server's id for an utterance we sent
    queued         {count, reason}                     sent only to this socket
    message_start  {id, run_id, reply_to, request_id, register, author}
    message_end    {..., content, delivery, audit: {status, reason, source}}
    request_end    {request_id, reply_to, register, delivery}  a request dropped before generation
    error          {..., message}
    stopped / stop_pending                             someone stopped her generation
Tokens are ignored: the first stage speaks delivered final text only. Everything else
(status, pipeline, eyes, autonomous_*) is not the voice's business.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

try:
    import websockets
except Exception:  # pragma: no cover - import guard
    websockets = None


@dataclass
class NovaEvent:
    kind: str                       # ack | queued | start | end | request_end | error | stopped
    message_id: str = ""
    request_id: str = ""
    reply_to: str = ""
    run_id: str = ""
    register: str = ""
    author: str = ""
    text: str = ""                  # end: delivered content; error: message; ack: utterance
    delivery: str | None = None     # end/request_end; None on an end means old schema
    audit: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


_KINDS = {"user_message": "ack", "queued": "queued", "message_start": "start", "message_end": "end",
          "request_end": "request_end", "error": "error", "stopped": "stopped", "stop_pending": "stopped"}


def _text(value) -> str:
    return value if isinstance(value, str) else ""


def parse_event(frame, author: str = "Nova") -> NovaEvent | None:
    """One server frame -> NovaEvent, or None when the voice has no business with it.

    A missing audit is NOT_RUN, never PASS. A missing `delivery` on message_end stays None so the
    session can refuse to speak old-schema ends (their error path ends with a diagnostic)."""
    if not isinstance(frame, dict):
        return None
    kind = _KINDS.get(frame.get("type"))
    if kind is None:
        return None
    if kind in ("start", "end", "error") and frame.get("author") != author:
        return None
    ev = NovaEvent(kind=kind, message_id=_text(frame.get("id")), request_id=_text(frame.get("request_id")),
                   reply_to=_text(frame.get("reply_to")), run_id=_text(frame.get("run_id")),
                   register=_text(frame.get("register")), author=_text(frame.get("author")), raw=frame)
    if kind == "end":
        ev.text = _text(frame.get("content"))
        ev.delivery = frame["delivery"] if isinstance(frame.get("delivery"), str) else None
        audit = frame.get("audit") if isinstance(frame.get("audit"), dict) else {}
        ev.audit = {"status": _text(audit.get("status")) or "NOT_RUN",
                    "reason": _text(audit.get("reason")),
                    "source": _text(audit.get("source")) or "none"}
    elif kind == "request_end":
        ev.delivery = _text(frame.get("delivery")) or "unavailable"
    elif kind == "error":
        ev.text = _text(frame.get("message"))
    elif kind == "ack":
        ev.text = _text(frame.get("content"))
    return ev


def new_request_id() -> str:
    return uuid.uuid4().hex


class NovaLink:
    def __init__(self, url: str, speaker: str = "Cole", register: str = "voice", author: str = "Nova"):
        if websockets is None:
            raise RuntimeError(
                "the 'websockets' package is required: pip install websockets "
                "(see general_tools/voice_gateway/requirements.txt)")
        self.url = url
        self.speaker = speaker
        self.register = register
        self.author = author
        self._ws = None

    async def __aenter__(self):
        self._ws = await websockets.connect(self.url, max_size=8 * 1024 * 1024)
        return self

    async def __aexit__(self, *exc):
        try:
            if self._ws:
                await self._ws.close()
        except Exception:
            pass

    async def say(self, text: str, request_id: str | None = None) -> str:
        """Send one utterance as the speaker. Register the request_id BEFORE calling this, so the
        server's acknowledgement can never outrun the pending entry that should catch it."""
        request_id = request_id or new_request_id()
        await self._ws.send(json.dumps({"type": "message", "content": text, "speaker": self.speaker,
                                        "register": self.register, "request_id": request_id}))
        return request_id

    async def stop(self) -> None:
        """Ask the server to stop the current generation (the UI's stop button)."""
        await self._ws.send(json.dumps({"type": "stop"}))

    async def events(self):
        """Async-generate NovaEvents until the socket closes."""
        async for raw in self._ws:
            try:
                frame = json.loads(raw)
            except Exception:
                continue
            ev = parse_event(frame, self.author)
            if ev is not None:
                yield ev
