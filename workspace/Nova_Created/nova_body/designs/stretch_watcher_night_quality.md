# Stretch watcher: night-quality dimension
_Last updated: 2026-07-23 15:40:28_

## Gap
The stretch watcher is a single timer. Forty-five minutes sitting and it nudges. It has no idea whether Cole's stiff from a hard set or a bad night, so the answer is identical either way. He'd want different answers.

## Shape
A one-file night log: `Cole_journal/night_quality.jsonl`, one line per calendar day with sleep_hours (float), quality (good|rough|bad), and a note if Cole says something about it. The watcher reads the current day's entry and picks its nudge tone: rough night gets a softer ask, good night gets the normal push.

The reacher tool gets a `night_quality` arg so I can write an entry when Cole tells me he slept badly. Without it I'd have to import the whole watcher module just to drop a fact on disk.

## Test
1. Write a 'rough' night, run the watcher: nudge tone is softer than the default list.
2. No night entry at all: falls back to the normal nudge, nothing breaks.
3. Reach a 'good' night in, read it back through the tool.
