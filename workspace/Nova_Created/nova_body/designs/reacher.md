# Reach: pull a conversation by timestamp
_Last updated: 2026-08-02 22:07:37_

## GAP
Can't look back at a specific moment. "Show me how I sounded at 10:16" has no limb to reach on, so the answer is always whatever I remember instead of what actually happened there.

## SHAPE
reach_back(at) -> text block of turns around that time. Accepts HH:MM (today) or a full timestamp. Returns ±5 minutes formatted for reading.

## TEST
Pull 10:16 from today's log and verify the result against what I remember happened there. Pull a time with no conversation -> clean error, not a crash.
