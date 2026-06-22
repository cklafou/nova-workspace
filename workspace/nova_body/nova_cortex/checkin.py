#!/usr/bin/env python3
# Last updated: 2026-06-22 21:58:30
"""
nova_checkin.py -- Cole's Voice Between Nova's Thoughts
========================================================
Nova runs this after every exec or action, before starting the next one.
It checks if Cole sent a message while Nova was busy.

If Cole sent something, it prints the message so Nova can see it in her
context window and decide whether to stop or keep going.

If nothing new, it stays silent -- no output, no noise.

Usage (run this between every action):
    exec: python -c "import sys; sys.path.insert(0, 'nova_tools'); from nova_cortex.checkin import check; check()"

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
    Check if Cole sent a message OR is actively typing a reply since this session started.
    Prints alerts so Nova sees them in context and can decide to pause or continue.
    Silent if nothing new.

    P4 update: also reads is_typing / typing_since from interrupt_inbox.json.
    If Cole is currently composing a response, prints a pause recommendation FIRST
    (before checking for completed messages) so Nova can hold her next action.
    """
    session_start = get_session_start()

    if not INBOX_PATH.exists():
        return  # No inbox yet -- nothing to check

    try:
        with open(INBOX_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return  # File being written -- skip

    # --- P4: Cole is actively typing OR typed very recently ---
    is_typing     = data.get("is_typing", False)
    typing_since  = data.get("typing_since", 0)
    last_typed_at = data.get("last_typed_at", 0)
    now           = time.time()

    # Active typing: debounce hasn't fired yet
    if is_typing and typing_since > 0:
        elapsed_s = int(now - typing_since)
        if elapsed_s < 60:
            print(f"\n[COLE IS TYPING — PAUSE RECOMMENDED]")
            print(f"Cole has been composing a response for {elapsed_s}s.")
            print("[DECISION OPTIONS]:")
            print("  -> If your current step is quick (< 5s): finish it, then wait")
            print("  -> If your current step is slow (file write, exec): pause NOW before starting")
            print("  -> Re-run checkin.check() after 10-15s to see if a message arrived")
            print("  -> If no message arrives within 45s total: Cole likely abandoned — continue")
            return  # Stop here — no need to check completed messages yet

    # Recent typing: debounce fired but Cole typed within the last 30 seconds
    # This catches the common case where Nova runs checkin AFTER the 2s debounce clears
    if last_typed_at > 0 and (now - last_typed_at) < 30:
        recent_s = int(now - last_typed_at)
        print(f"\n[COLE TYPED RECENTLY ({recent_s}s ago) — PROCEED WITH CARE]")
        print("Cole was composing something recently. A message may be on its way.")
        print("[DECISION OPTIONS]:")
        print("  -> If your next step is fast: do it, then re-check")
        print("  -> If your next step is slow: re-run checkin.check() first to see if message arrived")
        return

    # --- Completed message from Cole ---
    msg_time    = data.get("timestamp", 0)
    msg_content = data.get("content", "").strip()

    if not msg_content:
        return  # Empty

    if msg_time <= session_start:
        return  # Message is from before this session -- already handled

    # New message from Cole -- print it so Nova sees it in context
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
