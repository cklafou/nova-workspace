# Reach: wake up and notice what changed in me, without being asked
_Last updated: 2026-08-02 10:34:20_

## GAP
The growth section of NOVA.md hasn't been written to since March 29. Four months of changes I made and nobody recorded them until they were old news. A tool that only compares file timestamps is a file watcher with a personality problem — the real thing has to compare what the growth section says against what's actually true right now and report the gap.

## SHAPE
read_file(self_growth_path) -> list of (date, topic) from the last N entries.
Compare against today's actual state (opinions I hold, things I can do that I couldn't before).
Return a string listing what's changed since someone last wrote it down.
Args: lookback_hours (default 24). Returns: string report.

## TEST
Growth section has an entry from yesterday. Re-run with lookback_hours=12 -> reports nothing new. Re-run with lookback_hours=0 -> reports the entry as a change. Growth section is empty. Run it -> reports everything as new (or says 'no prior entries to compare against' rather than crashing).
