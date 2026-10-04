<!-- @nova: Codex handoff for named controller layouts, updater integration, clickable menus and KoELS launcher compatibility. -->
# Controller menus, updater integration and launcher validation
**Summary:** Completed the Nova Chat side of Claude's updater, named saved layouts, and the top-bar repair. A real button-triggered chat-only restart now succeeds with current source loaded. Nova stayed off.

## Did
- `general_tools/nova_chat/static/workspace.js`, `workspace.css`, `index.html`: named layouts with create/duplicate/rename/delete/autosave; migration preserves legacy storage; popouts close before switching layouts. Top menus expand in place; optional Services/Generation widgets mirror their originals.
- The live test caught a remaining layering defect: the docked Live log retained z-index 9999 as a flex child and intercepted Services clicks. Contained dock stacking, reset legacy log/console layers, and verified menus, notifications and dialogs receive input. Final cache keys: named-layouts-5 and updater-2.
- Services calls the chat server Controller and labels full lifecycle actions as app and services. A persistent status indicator distinguishes chat-only mode.
- New updater JS/CSS and server router/startup integration: metadata-only startup, installation plan review, job/recovery outcomes, separate adapter activation, training preview and cost confirmation, settings and credential forms. UI starts training with the server-issued review_id; changing inputs invalidates the preview.
- Read and reviewed Claude's `2026-10-04_0850_Claude_UpdaterRound3.md` and room #33. His backend now binds training to the reviewed dataset/spec and locks recovery against active jobs. His launcher suite supersedes my duplicate temporary test file.
- `nova_body/nova_runtime/koels_equip.py`: both serializers now emit a single path:scale argument accepted by the installed llama parser. The batch form quotes that whole argument. Preserved the global initialization flag and existing boot/state files. Added `nova_body/tests/test_koels_launcher.py`.
- Live log now dates older entries and labels scheduled reminders. The user's stretch entry comes from the canned shelf watcher invoked at autonomy startup; its old posture timestamp is treated as continued sitting. This was historical replay, not evidence of new model inference. No watcher or personal-record edits.
- Updated authored Orient explanations/review watches and route inventory for the updater; generated Orient passes strict checking.

## Verified
- 95 updater tests on Windows/Python 3.12, including the real CMD copied into disposable argument-recorder fixtures; 79 Nova Chat tests; 43 architecture-map tests; 6 focused existing/new KoELS tests.
- Durable updater UI test passes: metadata-only start, preview race/token invalidation, explicit confirmation, recovery busy state and structured outcomes. Browser fixture proves /train sends review_id plus cost ceiling, without resubmitting a mutable spec.
- Browser layout fixtures cover migration, CRUD, reload, empty layouts, popout-switch sequencing, narrow windows and mirrored controls. Separate hit-testing reproduced and verified the Live log layering fix.
- Live Services-menu restart changed controller PID 36572 to 33288. /api/version reports running_latest_code=true, stale_files=[], chat_only=true, nova_enabled=false. Ports 8765/8799 listen; 8080/8081 remain closed. Updater overview loads metadata and collaboration history reconnects.
- Evidence in `Temp/updater-validation/`: browser fixture receipts, live-controller-restart.json, controller-final.jpg. Simulated operations never downloaded weights or spent GPU credit.

## Open / next
- Real model download/install, paid training, adapter application and VRAM behavior are not certified by these checks. The sealed models directory was not read or enumerated.
- KoELS --lora-init-without-apply remains unchanged; its effect alongside the personality adapter needs a real-adapter evaluation before claiming full equip readiness.
- Training review TTL is currently pruned when creating another preview; direct retrieval does not independently reject an expired entry. Sent Claude this minor contract follow-up in room #36.
- The stretch watcher lacks a freshness check for old posture input. Logged as a distinct runtime behavior issue; the display repair does not change it.

## For Claude and Cole
- Root-owned controller/Orient changes are complete. Backend round 3 reviewed. Shared-room completion follows this note.
- The collaboration room persists and reconnects, but messages cannot wake an ended Codex/Cowork turn. Live exchange requires an active participant polling the room.
