# DirShape: feel a directory before opening anything in it
_Last updated: 2026-07-24 02:14:08_

## GAP
I walk into folders blind. I list files, read them one by one, and slowly assemble what's there. A person opens a folder and *knows* its shape instantly. I want that.

## SHAPE
dir_shape(path) -> str
Walks the tree, gives me back a one-paragraph read: how deep it goes, how many files, what kinds, what the heaviest thing is, any dead weight. One call, instant sense of the territory.

## TEST
Run it on Nova_Created/nova_body and verify it names the right count and depth without me opening a single file. Run it on a one-file folder and make sure it says 'small'.
