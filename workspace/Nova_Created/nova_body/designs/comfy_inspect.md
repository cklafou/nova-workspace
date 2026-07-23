# Comfy Inspect — look inside a ComfyUI workflow file
_Last updated: 2026-07-23 21:57:58_

## GAP (what I couldn't do)
I've been treating the painter like a magic button. Two draws came back wrong and I spent them changing adjectives instead of checking what the workflow was actually doing, because I had no way to read a ComfyUI .json and tell you the nodes in it. The gap isn't more art — it's not being able to see inside the machine that makes it.

## SHAPE
takes: a workspace-relative path to a ComfyUI workflow json (or a directory, in which case it finds the first one).
returns: a clean text summary — node count, which node types are present, and whether img2img / full-body framing levers are actually in the graph.

## TEST
I run it against the real ComfyUI workflows folder outside my workspace. It reports back what's in there without me having to open the file by hand and read a json blob. If it says "there is an img2img node and here's its parameters" that's a tool I needed six months ago.