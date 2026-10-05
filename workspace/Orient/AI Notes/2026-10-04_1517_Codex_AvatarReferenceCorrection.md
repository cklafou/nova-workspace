<!-- @nova: Record the paused v18 art rebuild, rejected eye studies, and reference-matching correction. -->
# Avatar reference correction in progress
**Summary:** The generated v18 head/iris studies did not match Cole's A3 eye reference or preserve the approved frontal face proportions. They are drafts only and have not replaced v17 in Cubism or VTube Studio.

## Did
- Added a Core-based head validator in `workspace/nova_body/SELF/Avatar/Live2D/tooling/validate_head_v18.py`; v17 baseline evaluated 97 poses and correctly failed missing separate hair/ears and no-op X/Y head parameters.
- Prepared a draft separated head PSD and source previews under `Live2D/source/` and `Live2D/preview/v18/`. Stopped assembly after visual review found proportion drift and segmentation defects.
- Held generated standalone iris studies out of the model. Cole explicitly rejected them and requires the A3 reference's oval iris/pupil, color, fine ring, and whole-face fit.

## Verified
- Existing v17 is preserved. No v18 native project or runtime export has been completed.
- Draft eye centers approximately match the approved frontal coordinates, but the chin is 10.8 model canvas pixels too low. This is not a proportion match.
- The reference's eye design is being inspected using unchanged enlarged source crops. The draft introduced a rounder iris, rounder pupil and unsupported highlights.

## Open / next
- Correct the existing eye artwork from measured reference contours and colors, preserving the approved frontal face landmarks; compare the result in the whole face before importing.
- Draft v18 PSD is NOT import-ready. It contains hair matte noise, a brow seam and stray collar pixels. Preserve v17 clothes and their layer order.
- Head X/Y, separated hair/ears, native rigging, tracking mappings and full animation quality remain outstanding. Do not present source art or offline renders as VTube Studio tracking validation.