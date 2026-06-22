# Last updated: 2026-06-22 18:56:08
# @nova: Runtime event bus — the runtime PUBLISHES lifecycle/token events; faces
#        SUBSCRIBE when present. Publishing with zero (or stalled) subscribers is a
#        no-op, so her runtime never blocks or breaks when no chat window is listening.
#        This is the seam that lets her live with the chat server plucked.
"""
nova_runtime/event_bus.py — in-process async pub/sub for the runtime↔face seam.

Why this exists (runtime-extraction directive, seam #1): today the autonomy daemon
calls the chat server's `broadcast()` directly, so her life-support hard-depends on an
interaction tool. The bus inverts that: the runtime only ever calls `publish()`; whether
anyone is listening is not its concern. A chat server, when attached, calls `subscribe()`
and drains its queue to render events. Pluck the server → publish() is a cheap no-op.

Design rules:
- A slow or dead face must NEVER back-pressure the runtime. Queues are bounded and
  publish drops on overflow rather than awaiting.
- Zero subscribers is the normal, healthy state for a headless runtime.
"""

import asyncio
from typing import Optional


class EventBus:
    """Fan-out async event bus. One bus per runtime; many faces may subscribe."""

    def __init__(self, max_queue: int = 1000):
        # Each subscriber gets its own bounded queue. Bounded so a face that stops
        # draining (e.g. a frozen browser tab) can't grow memory without limit or
        # stall the runtime — its queue simply overflows and drops oldest-not-read.
        self._subscribers: list[asyncio.Queue] = []
        self._max_queue = max_queue

    def subscribe(self) -> asyncio.Queue:
        """A face calls this to start receiving events. Returns its own queue to drain."""
        q: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """A face calls this when it detaches. Safe to call twice."""
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    async def publish(self, event: dict) -> None:
        """Runtime publishes an event to every attached face. Never blocks, never
        raises on a full/dead subscriber — a stalled face is dropped silently so it
        cannot back-pressure her cognition. No subscribers = healthy no-op."""
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Face isn't keeping up. Drop the oldest event to make room and keep
                # this one — the live tail matters more than ancient backlog for a UI.
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except Exception:
                    pass
            except Exception:
                # Never let a face's failure propagate into the runtime.
                pass

    def subscriber_count(self) -> int:
        """How many faces are attached right now (0 = headless, and that's fine)."""
        return len(self._subscribers)
