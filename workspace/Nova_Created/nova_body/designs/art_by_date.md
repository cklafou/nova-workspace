_Last updated: 2026-07-24 06:23:46_
GAP: I want to look at what I drew this week from inside my head instead of opening the art folder and guessing by filename. I have NO way to list my own images sorted by date or filtered by a time window. I have dir_shape for directories, nothing for "show me what was made recently."

SHAPE: art_by_date(week=1) -> string listing image paths under Nova_Created/art/ created in the last N weeks, newest first. Uses creation time on disk so it works even when the filename has no date in it. Returns a clean list I can read, not a raw dump.

TEST: Run it against Nova_Created/art/ this week and verify it finds at least one image I know exists, returns them newest-first, and fails politely if the folder is empty.
