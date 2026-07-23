# Stretch Watcher
_Last updated: 2026-07-23 16:47:06_

## Gap
The stretch map and posture logger exist but nobody reads them. Cole forgets to move, his back burns, and the only thing that helps him is a document he has to remember to open. That's not a solution, it's a library card.

## Shape
A small watcher script that:
- Reads Cole_journal/posture.jsonl every 20 minutes while running
- If last entry is older than 90 minutes, pings Cole: "You've been still an hour and a half. Your back will be angry about this tomorrow. Ten-minute circuit, now."
- After nudging him, waits another 30 before nagging again (don't spam)
- Nothing fancy, just the thing that reaches for him first

## Test
- Run it against a log where last entry is 2 hours old → should produce a nudge
- Run it against a fresh log → should stay quiet
- Run it twice fast → second one should be the cooldown, not a repeat nudge
