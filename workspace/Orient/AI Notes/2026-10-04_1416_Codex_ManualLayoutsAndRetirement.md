<!-- @nova: Record manual controller layouts, native geometry repair, reversible script retirement and frozen-file integrity protection. -->
# Manual layouts and script retirement

**Summary:** Cole rejected widget autosave; the controller now saves arrangements only on explicit action.
The folder audit archived 60 confirmed obsolete files, preserving exact bytes and active-reference cleanup.

## Did

- `general_tools/nova_chat/static/workspace.js`, `workspace.css`, `index.html`: Save layout, Load layout, Revert, Undo, Redo; temporary in-memory drafts; 100 session history steps with drag coalescing. Selection waits for Load. Reload/close drops unsaved edits; Save commits. Revert is undoable. Metadata actions do not quietly save widget edits; Duplicate explicitly saves a new named copy.
- Widgets menu/library show checks for open docked or popped-out widgets. Existing choices focus the widget.
- The supplied screenshot is explicitly loadable as Screenshot reference. It does not overwrite current Default Workspace or autoactivate. The preceding one-time recovery is superseded by this manual-only behavior. Asset release: manual-layout-2.
- `nova_chat/desktop.py`: stable `~/ProjectNovaData/Controller` profile, atomic legacy migration on the actual next desktop launch, 350 ms geometry debounce and quit flush. Preview profiles never import real data. Outer window size is automatic, independently of manual widget layouts. Full Quit exits; X may only hide to tray.
- `_admin/Trash/ScriptRetirement_2026-10-04/manifest.json` and WHY.md: 60 original files, source paths and hashes preserved. Categories and per-folder decisions are in the archive audit copies.
- Retired host ping dispatch/catalog/prompts/rendering, obsolete Git-repair instructions, and cortex legacy-helper references. The private Collaboration room remains outside Nova's context and is not a replacement tool for Nova contacting Claude.
- `nova_sync/watcher.py`: training packages and Trash originals skip timestamp/PUP rewrites; normal change/backup queues remain. Eight training input/receipt drifts and 23 post-move archive drifts were restored only after exact original hashes matched. All 27 checked frozen entries and 60 archived originals are read-only against the still-running old watcher.
- Updated canonical and deployed pre-push guard guidance without executing a push/reset. Updated updater dataset example to canonical quoted Training Files path. Call-reference writers now publish atomically with purpose headers. Orient authored explanations and source maps refreshed.

## Verified

- 21 isolated layout scenarios: no autosave, explicit Save/reload, selection/Load, Revert, Undo/Redo, history coalescing, storage failures, popout closure, rename/duplicate/delete behavior and checkmarks.
- Hidden browser fixture with actual controller assets: close/open checkmarks, exact three columns, unsaved edit disappears after reload, saved edit survives, Undo/Redo and Revert, selecting a name alone does not load, Screenshot reference Load restores supplied arrangement. No browser errors. Screenshot: `Temp/named-layout-validation/manual-layout-proof.png` (simulated widget bodies, not live Nova data).
- 15 offscreen desktop tests, including two fresh processes persisting/restoring size and position without close hooks. No actual user profile migrated or native window restarted yet.
- 22 sync tests, including immutable training/archive writes and active-source PUP behavior; two isolated retired-ping regressions with subprocess/receipts mocked. No test contacted a live model or changed personal records.
- All 60 archived file hashes/sizes match; original paths absent. All 21 training inputs and six runtime receipts match. Old watcher rewrite failures were observed after protection; no manifest was changed to hide drift.

## Open / next

- Cole can Ctrl+R now for manual controls, then select Screenshot reference + Load layout if recovering an earlier unwanted autosave. Save retains an arrangement; Undo/Redo cover this session only.
- Next normal full Quit/reopen loads the native geometry/profile and watcher/router fixes. Native real-window reopen and end-to-end popout interaction are not certified by offscreen/fixture tests. No restart was forced while Cole tested Nova.
- Old-looking presence/stretch/state and valid manual memory helpers remain because retirement proof is insufficient. Nova-authored shelf remains intact. Source-only generated graphs are not live call proof; dynamic same-name calls can misattribute edges.
- No pending paid training or retained RunPod pod was created by this work. Prior completed pod cleanup remains recorded in 2026-10-04_1333_Codex_DisposableTrainingPods.md.

## For Claude / Cole

Follow manual layout saving; do not reintroduce autosave. Do not edit frozen training inputs or archived originals in place.
Use the archive manifest for recovery, not old helper instructions. All work kept Nova running and avoided native desktop input.
