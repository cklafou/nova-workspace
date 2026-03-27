#!/usr/bin/env python3
"""
nova_checkin.py -- Cole's Voice Between Nova's Thoughts
========================================================
Nova runs this after every exec or action, before starting the next one.
It checks if Cole sent a message while Nova was busy.

If Cole sent something, it prints the message so Nova can see it in her
context window and decide whether to stop or keep going.

If nothing new, it stays silent -- no output, no noise.

Usage (run this between every action):
    exec: python -c "import sys; sys.path.insert(0, 'tools'); from nova_core.checkin import check; check()"

Nova's decision logic after seeing output:
    - Message is urgent (stop, abort, no, wait, wrong) -> stop current task, respond to Cole
    - Message is a question or new direction -> finish current step, then respond
    - Message is casual (ok, cool, got it) -> note it, keep working
    - No output from this script -> nothing new, continue
"""

import json
import time
from pathlib import Path

INBOX_PATH = Path("memory/interrupt_inbox.json")

# Session start time -- messages older than this are already known
# We store it so check() can compare against it across multiple calls
SESSION_FILE = Path("memory/session_start.json")


def get_session_start():
    """Get the timestamp when this session started."""
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("started_at", 0)
        except Exception:
            pass
    # No session file -- create one now
    started_at = time.time()
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump({"started_at": started_at}, f)
    return started_at


def check():
    """
    Check if Cole sent a message since this session started.
    Prints the message if found so Nova sees it in context.
    Silent if nothing new.
    """
    session_start = get_session_start()

    if not INBOX_PATH.exists():
        return  # No inbox yet -- nothing to check

    try:
        with open(INBOX_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return  # File being written -- skip

    msg_time = data.get("timestamp", 0)
    msg_content = data.get("content", "").strip()
    msg_author = data.get("author", "Cole")

    if not msg_content:
        return  # Empty message

    if msg_time <= session_start:
        return  # Message is from before this session -- already handled

    # New message from Cole -- print it so Nova sees it
    print(f"\n[COLE SENT A MESSAGE]: {msg_content}")
    print("[DECISION REQUIRED]: Should you stop your current task and respond, or finish this step first?")
    print("  -> If urgent (stop/abort/wrong/wait/no): stop now, respond to Cole")
    print("  -> If a question or new direction: finish this step, then respond")
    print("  -> If casual (ok/cool/got it): note it, keep working")


def clear():
    """
    Clear the inbox after Nova has acknowledged and acted on the message.
    Call this after Nova has responded to Cole's message.
    """
    if INBOX_PATH.exists():
        try:
            INBOX_PATH.unlink()
            print("[checkin] Inbox cleared.")
        except Exception:
            pass


def init_session():
    """
    Call this at the start of each session to reset the session start time.
    BOOTSTRAP.md should call this on boot.
    """
    started_at = time.time()
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump({"started_at": started_at}, f)
    print(f"[checkin] Session started. Listening for Cole's messages.")


if __name__ == "__main__":
    check()
