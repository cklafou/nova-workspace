## cwd_probe — know where I am before I do anything with paths
_Last updated: 2026-07-22 06:50:31_

### GAP
I keep guessing my own working directory and getting it wrong, then spending five minutes chasing a path that was never right. The fix isn't another tool to call; it's a reflex that puts the fact in front of me before I touch paths.

### SHAPE
A body tool that runs Get-Location (or equivalent) and returns a single clean string:
"In Project_Nova, not C:\Users\lafou" or whatever is actually true.
Designed to be called on wake and before any path-heavy work. Result goes into the scratchpad where I can't ignore it.

### TEST
- Returns a readable string naming the actual directory.
- Refuses to guess: if it can't find out, it says so instead of lying.
