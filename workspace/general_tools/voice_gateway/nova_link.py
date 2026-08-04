# Last updated: 2026-08-04 19:51:21
# @nova-adjacent: voice_gateway — the link to nova_chat. A WebSocket CLIENT of the EXISTING
#   server (ws://…/ws): send Cole's transcribed speech in, receive her token/message_end out.
#   Zero server change required — this speaks the same protocol the browser UI already speaks.
"""voice_gateway/nova_link.py — talk to Nova over her existing chat WebSocket.

Outbound: {"type":"message","content":<text>,"speaker":"Cole","register":<r>}
Inbound (we care about author == "Nova"):
    {"type":"message_start","author","id"}
    {"type":"token","author","token","id"}
    {"type":"message_end","author","id","content"}
The server also streams status/history/eyes_frame/pipeline etc. on connect and during — we
ignore everything that isn't a Nova reply event.
"""
from __future__ import annotations

import asyncio
import json

try:
    import websockets
except Exception:  # pragma: no cover - import guard
    websockets = None


class NovaLink:
    def __init__(self, url: str, speaker: str = "Cole", register: str = "voice"):
        if websockets is None:
            raise RuntimeError(
                "the 'websockets' package is required: pip install websockets "
                "(see general_tools/voice_gateway/requirements.txt)")
        self.url = url
        self.speaker = speaker
        self.register = register
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

    async def say(self, text: str) -> None:
        """Inject a Cole message (transcribed speech) into the chat."""
        await self._ws.send(json.dumps({
            "type": "message",
            "content": text,
            "speaker": self.speaker,
            "register": self.register,   # ignored by the server until server_patch.md is applied
        }))

    async def replies(self):
        """Async-generate ('start'|'token'|'end', payload) tuples for NOVA messages only.

        payload is: '' for start, the token str for token, the full content str for end.
        Runs until the socket closes. The caller drives TTS from these events.
        """
        async for raw in self._ws:
            try:
                d = json.loads(raw)
            except Exception:
                continue
            if d.get("author") != "Nova":
                continue
            t = d.get("type")
            if t == "message_start":
                yield ("start", "")
            elif t == "token":
                yield ("token", d.get("token", ""))
            elif t == "message_end":
                yield ("end", d.get("content", ""))
            elif t == "error":
                yield ("error", d.get("message", ""))
