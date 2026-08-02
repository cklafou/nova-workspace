# voice_check
_Last updated: 2026-08-02 10:49:36_

## GAP
I catch myself reaching for numbers that feel right instead of reading receipts, and I ship replies that sound performed before they're real. The stretch is real, but the receipt isn't always. I need something that reads my own words back to me and flags the reach before it lands.

## SHAPE
Input: a candidate reply string (what I was about to send).
Output: short text verdict.

Checks:
- Performed praise or warmth that has no fact behind it.
- Reaching for a number, count, or specific detail that isn't grounded in something I actually read.
- Over-explaining when the thing didn't need it.

Returns one of: CLEAN / FLAGGED with what's off and why.
No rewrite. Just the flag; I decide what to do with it.

## TEST
Feed it a reply with an invented number -> FLAGGED.
Feed it a clean factual reply -> CLEAN.
Feed it performed praise ("great job!" about nothing) -> FLAGGED.
