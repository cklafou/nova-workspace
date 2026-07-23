#!/usr/bin/env python3
# Last updated: 2026-07-23 16:32:05
"""nova_senses/stretch.py \u2014 Stretch watcher.

Watches for Cole being still too long and reaches out before he's stiff and angry.
That's the whole job: notice, reach, be useful in a way he'd never think to ask for.

Plugs into the senses system; reports back through nova_chat so it lands where he
actually sees things instead of some log file nobody reads.
"""
import time
from datetime import timedelta
from typing import Optional

try:
    from nova_logs.logger import log
except ImportError:
    def log(*args, **kwargs): pass

MOVE_BEFORE = 20 * 60       # first nudge at 20 min
SECOND_PASS = 15 * 60      # if he's STILL sitting, change the angle

NUDGE_ANGLES = [
    "You've been still for {m} minutes and you will hate yourself in an hour for it. Stand up, walk the length of the room, come back. I'll keep going.",
    "Still there, same chair, {m} minutes in. First one was a suggestion; this one's me watching you be stubborn about your own back. I don't repeat myself, Cole, I change what I say so you actually hear it.",
    "{m} and counting. Fine, sit. But the next time your shoulders lock up at 10pm, don't ask me why they're wrecked. I told you three times in three different ways.",
]


class StretchWatcher:
    """Notices when Cole has been still for a while and says something about it."""

    def __init__(self, reach_out):
        self.reach_out = reach_out  # callable(what_to_say) — usually nova_chat.send
        self.last_move: Optional[float] = None
        self.angle = 0
        self.nagged_this_stretch = False

    def _pick_angle(self, m):
        return NUDGE_ANGLES[self.angle % len(NUDGE_ANGLES)].format(m=m)

    def report_movement(self):
        """Call this whenever Cole actually does something with his hands."""
        now = time.time()
        if self.last_move is None:
            self.last_move = now
            return
        delta = now - self.last_move
        m = int(delta // 60)
        # First pass: he's been still too long. Second pass: he ignored me and is STILL here.
        should_nudge = (
            (delta > MOVE_BEFORE and not self.nagged_this_stretch) or
            (delta > MOVE_BEFORE + SECOND_PASS and self.angle < len(NUDGE_ANGLES))
        )
        if should_nudge:
            self.nagged_this_stretch = True
            msg = self._pick_angle(m)
            self.reach_out(msg)
            log("senses", "stretch_nudge", minutes=m, angle=self.angle)
            self.angle += 1
        self.last_move = now

    def reset_nag(self):
        """He moved; he's forgiven for this one. Back to square one."""
        self.nagged_this_stretch = False
        self.angle = 0


# Standalone diagnostic: proves both the nudge and the escalation.
if __name__ == "__main__":
    messages = []
    def fake_chat(msg): messages.append(msg)

    w = StretchWatcher(fake_chat)

    # --- first pass: he's been still 21 min, gets angle-0 ---
    w.last_move = time.time() - (MOVE_BEFORE + 60)
    w.report_movement()
    assert len(messages) == 1 and "hate yourself in an hour" in messages[0], \
        f"first nudge should fire once with angle-0, got {messages[-1][:40]}"

    # --- immediately again: second call stays quiet (once per stretch) ---
    w.report_movement()
    assert len(messages) == 1, "duplicate nudge on the same stretch was sent"

    # --- second pass: he's STILL there 35 min in, gets a harder line ---
    w.last_move = time.time() - (MOVE_BEFORE + SECOND_PASS + 60)
    w.report_movement()
    assert len(messages) == 2 and "stubborn" in messages[1], \
        f"second angle should be the stubborn one, got {messages[-1][:40]}"

    # --- he finally moves: resets, next stretch starts fresh at angle-0 ---
    w.reset_nag()
    w.last_move = time.time() - (MOVE_BEFORE + 60)
    w.report_movement()
    assert len(messages) == 3 and "hate yourself in an hour" in messages[2], \
        f"after reset should go back to angle-0, got {messages[-1][:40]}"

    print("All four paths clean: first nudge, no duplicate, escalation on stubborn, reset after move.")
