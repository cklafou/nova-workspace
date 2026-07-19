# zzmeasure
_Last updated: 2026-07-20 04:31:28_

## GAP
I kept wanting a quick line count and was shelling out to PowerShell each time, which cost a tool loop and sometimes timed out on big trees.

## SHAPE
run(path:str) -> str. Returns '<n> lines'. Missing file returns an ERROR string.

## TEST
nova_config.json returns a positive count; a bogus path returns ERROR, never raises.
