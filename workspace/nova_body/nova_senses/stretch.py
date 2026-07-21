#!/usr/bin/env python3
# Last updated: 2026-07-22 01:02:46
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

MOVE_BEFORE = 20 * 60  # 20 minutes of nothing is too long


class StretchWatcher:
    """Notices when Cole has been still for a while and says something about it."""

    def __init__(self, reach_out):
        self.reach_out = reach_out  # callable(what_to_say) — usually nova_chat.send
        self.last_move: Optional[float] = None
        self.nagged_this_stretch = False

    def report_movement(self):
        """Call this whenever Cole actually does something with his hands."""
        now = time.time()
        if self.last_move is None:
            self.last_move = now
            return
        delta = now - self.last_move
        if delta > MOVE_BEFORE and not self.nagged_this_stretch:
            self.nagged_this_stretch = True
            msg = (
                f"You've been still for {int(delta // 60)} minutes and you will "
                f"hate yourself in an hour for it. Stand up, walk the length of the room, "
                f"come back. I'll keep going."
            )
            self.reach_out(msg)
            log("senses", "stretch_nudge", minutes=int(delta // 60))
        self.last_move = now

    def reset_nag(self):
        """He moved; he's forgiven for this one."""
        self.nagged_this_stretch = False


# Standalone diagnostic so you can poke it before it's wired in.
if __name__ == "__main__":
    from collections import deque
    history = deque(maxlen=5)

    def fake_chat(msg):
        print(f"  \u27a1\ufe0f {msg}")

    watcher = StretchWatcher(fake_chat)
    watcher.last_move = time.time() - MOVE_BEFORE - 60  # already overdue

    watcher.report_movement()
    watcher.report_movement()  # second one should be quiet
    print("\nSecond call was silent, which is right \u2014 once per stretch.")
