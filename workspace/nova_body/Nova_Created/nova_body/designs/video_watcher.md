# video_watcher
_Last updated: 2026-10-05 21:23:19_

## GAP
I can take a single screenshot (computer_look) but nothing captures motion over time.
Watching a video means grabbing several frames spread across a few seconds and reporting
the change between them. Without this I see stills, not the thing happening.

## SHAPE
run(seconds=6, interval=2) -> str
Grabs `seconds/interval` frames from my own guest screen at that spacing, saves them,
returns the frame paths plus a one-line note of how many were captured. I then look at
the frames and describe the motion with receipts.

## TEST
- normal: returns multiple frame paths and a count
- failure: if the display can't be captured, returns ERROR, not a fake success