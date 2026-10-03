<!-- @nova: Record the in-progress v17 eyelid shape rebuild and keep the prior verified runtime distinct. -->
# Blink rebuild
**Summary:** The user rejected v16's visually compressed blink. v17 is a separate working copy and is not exported or verified yet.

## Did / why
- Retained v16 and its checkpoint. Copied its editable Cubism project to `workspace/nova_body/SELF/Avatar/Live2D/rig/Nova_FRONT_v17.cmo3`.
- Prepared v17 source with viewer-left sclera coverage extended beneath the inner upper lash; native source replacement is underway.
- The current blink's parent deformer compresses foreground lashes along with the white aperture. Rebuilding authored eyelid shapes is required; merely retiming the motion is insufficient.

## Verified
- Inspected actual neutral and no-iris v16 renders plus native Cubism close-up. The approved open-eye placement is the starting point.
- Consulted official Cubism facial-expression and deform-path instructions. No claim of inspecting Crelly's private rig.

## Open / next
- Remove the foreground lashes from the shrinking parent, author changing lash curvature/thickness and aperture coverage through closure, inspect motion at natural speed and slowly, then export/install and checkpoint.
- Only avatar files are in scope. No unrelated Nova runtime or personal-state changes.
