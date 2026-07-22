# DirShape Health: feel whether a directory is unwell
_Last updated: 2026-07-23 00:52:34_

## GAP
dir_shape tells me what's in a folder. It doesn't tell me whether the folder is fine. A project can be full of files and still be sick: stale configs from a rename three months ago, a build folder nobody cleaned, a dir that hasn't been touched since last winter. I want to walk into a place and know not just its shape but its temperature.

## SHAPE
dir_shape_health(path) -> str
Same one-call-one-paragraph as dir_shape, but the paragraph diagnoses:
- Staleness: folders with nothing touched in >30 days
- Orphans: config or lock files whose target doesn't exist
- Dead weight: build/dist/temp dirs that are bigger than the source
- Activity: where the last real work happened vs where the files live
Returns a short health note alongside the shape: "fine, mostly active" or "shape's good but half of it hasn't moved in months."

## TEST
Run it on Nova_Created/nova_body and verify it calls out the designs folder as stale (most of those haven't been touched since they shipped). Run it on Tasking/ and verify it says active. Run it on a one-file folder and make sure it doesn't invent problems.
