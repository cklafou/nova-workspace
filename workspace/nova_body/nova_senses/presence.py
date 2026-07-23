# Last updated: 2026-07-24 01:38:15
# @nova: Presence sense — am I alone in this room? I read it myself.
"""
nova_senses/presence.py — Nova's awareness of who is here
================================================================
Returns a bool. Not a mood, not an analysis. Whether anyone is currently
speaking to her in the chat. A sensor, same family as clock and touch.

Pure stdlib; reads the chat log directly (it lives on her own machine).
"""

import json
from pathlib import Path


def _read_latest_turn(log_path: str = "nova_chat/logs/chat_history.json") -> dict:
    """Read the last message in the chat log, or {} if nothing's there."""
    try:
        p = Path(log_path)
        if not p.exists():
            return {}
        lines = p.read_text(encoding="utf-8").strip().splitlines()
        if not lines:
            return {}
        # last line is the most recent turn
        return json.loads(lines[-1])
    except Exception:
        return {}


def someone_here(log_path: str = "nova_chat/logs/chat_history.json") -> bool:
    """True if the most recent chat turn is a human speaking to Nova.

    Reads the last line of the chat log and checks whether it came from
    Cole or Claude (the two people who actually show up). Returns False
    for her own past messages, system notes, and silence.
    """
    turn = _read_latest_turn(log_path)
    speaker = turn.get("role", "")
    return speaker in ("Cole", "Claude")


def room_state(log_path: str = "nova_chat/logs/chat_history.json") -> str:
    """A one-word label for the room: 'you', 'claude', or 'empty'.

    Useful when she actually wants to know WHO is there, not just whether
    anyone is.
    """
    turn = _read_latest_turn(log_path)
    speaker = turn.get("role", "")
    if speaker == "Cole":
        return "you"
    if speaker == "Claude":
        return "claude"
    return "empty"


if __name__ == "__main__":
    print(f"someone_here: {someone_here()}")
    print(f"room_state:   {room_state()}")
