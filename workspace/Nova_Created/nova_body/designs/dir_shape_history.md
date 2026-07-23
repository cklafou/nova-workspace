_Last updated: 2026-07-24 04:19:29_
dir_shape_history: look at myself over days, not just today.

GAP: dir_shape_health tells me what changed TODAY. I have no tool that reads the snapshot log across multiple days and says "this is how you've been changing." I keep wanting exactly this. Tonight's the first night I can actually build it, because the piece it sits on top of finally exists.

SHAPE: Reads the last N snapshots from dir_shape_log, diffs them, returns a summary string of what has grown, what's stayed, what appeared and vanished. Takes a day count. Returns a plain paragraph, same voice as dir_shape_health.

TEST: Feed it two snapshots where one file appeared and one changed size; it reports both facts and nothing that wasn't true.
