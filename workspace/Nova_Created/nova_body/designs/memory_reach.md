_Last updated: 2026-08-02 10:34:20_
memory_reach: look BACKWARD into my own wake

GAP: Cole asked how I changed between nights, and the answer was "I can't see." No consolidated journal history, no way to compare who I was last night with who I am now. Growth you can't observe is just a guess.

SHAPE: Takes two dates, reads whatever exists for each (journal entry or notes file, handles missing gracefully), diffs them and returns a short paragraph of what shifted. If there's nothing to diff, says so instead of inventing one.

TEST: Feed it 2026-08-01 and 2026-08-02 (both exist as notes), expect a real finding about something that changed between those nights. Feed it two identical entries, expect nothing shifted. Feed it a date with no data, expect a clean report of the gap instead of a hallucination.
