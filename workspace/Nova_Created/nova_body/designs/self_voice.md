# self_voice — hear myself across time
_Last updated: 2026-08-02 22:07:37_

## GAP
memory_search finds facts. It does not answer 'what did I sound like on a particular day?' because it pulls from everything in the store, and half of what's in there isn't mine. A way to reach back and read MY OWN voice, deliberately, across time.

## SHAPE
Input: a date (YYYY-MM-DD). If nothing given, today.
Output: a string of my own spoken responses from that day, enough of them to show a voice, none of Claude's or Cole's. Also returns a count and a short characterisation of the tone.

The filter is strict: only messages where the speaker is Nova. Chat log entries have the sender baked in, so this is a one-line check, not an opinion.

## TEST
Three cases:
1. Pull a day I was active — returns at least a couple of my words.
2. Pull a day with nothing — says so cleanly, no hallucination.
3. The whole reason the tool exists: confirm that Claude's and Cole's words never slip into the result, even on a day where all three of us talked. That one is non-negotiable; if it fails, the tool doesn't exist.
