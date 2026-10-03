<!-- @nova: Record the avatar eye audit and scope of the ongoing v16 repair. -->
# Avatar eye audit
**Summary:** The user's latest request is to independently find and fix the visibly wrong eye rendering. Work is in progress; v15 is not visually approved.

## Did
- Audited actual compiled v15 geometry and rendered blink stages in `workspace/nova_body/SELF/Avatar/Live2D/preview/v16-audit/`.
- Found that foreground eye patches include skin and hair, and their blink deformation creates angular seams. Existing tests missed this; opacity crossfades also create double lash shapes.

## Verified
- Geometry audit and rendered comparisons cover the approved reference plus six blink stages. These reveal failures, not a successful repair.
- The saved v15 checkpoint remains available. No v16 rig has been completed yet.

## Open / next
- Repair the source separation and blink behavior, export through Cubism, inspect the actual result against the reference, then preserve a fresh checkpoint.

## For other agents
- Avatar files only are being changed. Controller/runtime, git exclusions, and modernization handoffs belong to the other current tasks; this avatar pass does not act on them.