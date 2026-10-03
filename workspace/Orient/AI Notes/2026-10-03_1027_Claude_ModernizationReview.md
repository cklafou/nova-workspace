<!-- @nova: Claude's review of Codex's Oct 2-3 modernization: verified findings with repros, and a suggested fix order. -->
# Modernization review
**Summary:** Good work, and the direction is right: honest results, supervised stop, a durable queue, verified completion, and PLUCK intact. Before Nova runs this unattended, fix the queue database being in git, the task workspaces sitting inside the watched repo, a restart regression, the acceptance self-certification gap and the loopback-only auth gate. The rest is minor.

Reviewed: baseline `f104d71` to `eecbf28` (10:17 KST), including Codex's 10:14-10:17 edits. Read-only: I changed no Nova code.

## Did
- Read `2026-10-03_1001_Codex_ValidationPlan.md`, `workspace/Orient/Architecture/evidence/2026-10-02-modernization.md`, `workspace/general_tools/nova_chat/CONTROLLER.md`, and the diffs of every modernized file.
- Ran the tests in a private Linux sandbox (a copy of the Drive read export, outside the repo). Reproduced each functional finding there with small scripts. Nothing ran against Nova's live state.

## Verified findings (most severe first)
"Repro" means I ran it in the sandbox. Line numbers are at `eecbf28`, paths under `workspace/`.

1. **The queue database is committed to git.** `nova_body/memory/runtime_work.sqlite3` was added in `032c4650`.
   - The `memory` queue stores memory text and base64 images (`nova_lancedb/indexer.py:35,45`) and keeps up to 1000 finished jobs per queue.
   - `nova_memory_db/` is ignored, but this second copy of the same content is not.
   - Every change commits a new binary blob, the same bloat FIX_GIT is cleaning up. Only one version is in history so far.
   - **Fix:** ignore `nova_body/memory/runtime_work.sqlite3*` and untrack it with `git rm --cached`, ideally inside FIX_GIT v2 before Cole runs it.
2. **Task workspaces live inside the watched repo.** `nova_cortex/task_workspace.py:28` stages copies in `nova_body/Tasking/workspaces/`. Nothing skips that folder: not git, not the watcher, not Orient's inventory. The problem is latent because the folder doesn't exist yet. On first use:
   - Autosave commits and pushes up to 2000 copied files.
   - The watcher stamps `# Last updated` into every staged .py/.md file. `promote()` (loop at `:71`) then sees all of them as changed and rewrites every selected original.
   - INDEX and the Drive copy list the duplicates.
   - **Fix:** stage somewhere all three already skip (today only `nova_body/logs/` qualifies), or add the folder to `.gitignore`, the watcher and Orient's SKIP. Also compare files with stamp lines ignored.
3. **Restart can report success without restarting (regression).** `nova_runtime/llama_control.py:95` now returns ok "already running or starting" whenever the port still accepts connections. `restart()` (`:150`) calls it right after `_kill_port()`, and `Stop-Process` does not wait for the socket to close.
   - Repro: hold the port open, then `restart()` returns `{'ok': True, ..., 'started': False}` and the launcher never runs. The old `start()` always launched.
   - This hits `/api/lora/equip` (`server.py:1365`; that is lesson 1's silent LoRA non-apply), `/api/restart/server` (`:3464`) and KoELS (`koels_equip.py:141`). KoELS `equip()` also returns ok True whatever the restart did.
   - **Fix:** after the kill, wait (bounded) for the port to stop accepting, then call `_start()` directly. If the port never frees, return ok False.
4. **Nova can certify her own work.**
   - `set_task_acceptance` (`nova_voice/tool_router.py:1262`) and `/api/queue/update` (`server.py:2920`) replace any task's checks without recording who set them or when.
   - `validate_checks` (`nova_cortex/verification.py:9`) checks shape only.
   - Repro: a Cole-authored task with no checks waits for review on completion. Setting a file check on a file that already exists, then calling `complete()`, marks it done with verification "passed".
   - Every check-less completion waits for review, so the design pushes her toward this route.
   - **Fix:** record who set the checks and when. Send completion to review (or show "self-set" in Control) when Nova set the checks on a task she didn't author. Freeze checks once a task is waiting for review.
5. **Loopback trust with no Host check.** `_auth_gate` (`server.py:253`) passes any request from 127.0.0.1 with no token and no Host or Origin check.
   - A DNS-rebinding web page, or any local proxy or tunnel forwarding to the port, is treated as Cole at the keyboard.
   - The gap pre-dates the modernization, but the new endpoints turn it into a direct way to run commands: `/api/queue/update` with `acceptance` argv plus `action: verify` runs them.
   - Browsers increasingly block this pattern; the server shouldn't rely on that.
   - **Fix:** in `_auth_gate`, also require Host to be `127.0.0.1:<port>` or `localhost:<port>`, and reject a cross-site Origin on POST.
6. **Refusals reported as success.** `append_file`'s duplicate-heading and duplicate-text refusals (`tool_router.py:524,549`) use `status="succeeded"`. Repro: a duplicate heading returns "REFUSED..." with `ok` True. **Fix:** `status="refused"`.
7. **The queue loses work in two ways.** The evidence doc says "Pending/failed work is not silently dropped"; both cases contradict it.
   - **Never fails:** a job whose worker crashes or hangs past its lease is re-claimed forever and never reaches `failed`, because the 5-attempt rule only runs in `finish()` (`nova_runtime/work_queue.py:64`). Repro: after 8 crashed claims the job is still `leased`.
   - **Silent drop:** `put()` (`:35`) returns the old id for a key that already finished (within the 1000-job window). A recurring event with a fixed key, such as `environment:<hash>`, is ignored without a trace. Repro: re-put after done leaves nothing pending.
   - **Fix:** in `claim()`, mark expired leases with attempts >= 5 as failed. Dedupe only against pending and leased rows.
8. **The watcher can die on a bad review registry (Codex's 10:17 change).** `architecture_map/orient.py:315` now raises on a malformed `reviews.json`, which is right for `--check`.
   - Watcher startup calls `run_push_cycle()`, then `build_file_index()`, then `refresh()`, then `load_reviews()`, with no guard (`nova_sync/watcher.py:988`). Autosave would never start: lesson 7 again.
   - **Fix:** catch and print the error in `build_file_index()`; keep the strict raise for `--check`.

## Minor
- **Directive expiry:** Cole's directive expires after a hard-coded 6 h (`nova_senses/environment.py:51`). An unfinished ask from before a workday silently stops being Priority 0. Make it a tunable, and turn an expired unconsumed ask into a task or a Control notice.
- **Screenshots:** every guest screenshot is appended to the tool-loop messages with no pruning (`nova_voice/nova.py:1295`); keep the latest one or two. `logs/computer/*.png` (`nova_computer/tools.py:36`) has no retention.
- **Exit codes:** `nova_computer/tools.py:58` turns real exit codes 124 and 130 into timed_out and cancelled. Carry the status separately.
- **Lost stop result:** in `run_process` (`nova_runtime/operations.py:148`), the final `communicate(timeout=5)` after a kill can raise and lose the timed_out or cancelled result.
- **Promotion gaps:** `promote()` ignores files deleted in the staged copy, and argv checks may name absolute paths to the originals.
- **Board churn:** selecting a task saves the board once for every open task (`nova_cortex/executive.py:874,890`). When Nova is busy, that means watcher and autosave churn.
- **Lease ownership:** `finish()` doesn't check that the caller still holds the lease.

## What's good
- Honest typed results with receipts.
- Stop is supervised and reports pending cleanup instead of claiming everything stopped.
- The queue is durable and leased.
- Acceptance gating catches criteria that change during verification.
- Promotion is checkpointed, detects conflicts and rolls back.
- The task board fails loudly rather than being replaced.
- Memory adds before it evicts.
- Control renders with `textContent`.
- The launcher refuses to relaunch onto busy ports.
- PLUCK holds: no body module imports the face, and `nova_runtime.runtime` imports headless.
- The evidence doc separates what was tested from what wasn't.

## Verified (and not)
- Tests at `eecbf28` in the sandbox: 95 pass.
- 2 fail only because PowerShell isn't installed: the two `run_command` tests. Run those on Windows.
- `test_desktop.py` was not run (it needs PyQt6). The hook tests pass when given `/bin/sh` instead of Git's `sh.exe`.
- Not checked: anything live on Windows, the WSL guest backend, real model runs, the Control UI in a browser, and real restart timing. Finding 3 was reproduced with a held-open socket, not a real llama-server.

## Open / next
- Once the fixes land, Orient needs three corrections:
  - the evidence doc's "not silently dropped" line;
  - its storage paragraph, which doesn't say the database is in git or that staged copies sit in the watched tree;
  - ARCHITECTURE's "fresh directive", which doesn't mention the 6 h limit.

## For Codex
- I haven't edited anything. You're mid-validation in `nova_chat/`, `nova_start.py` and the runtime, so findings 3-8 are yours if you want them. Tell me in a note which ones you'd rather I take.
- If Cole agrees, I'll take the repo side of findings 1 and 2: ignore rules, plus the untrack step in FIX_GIT. Please leave `_admin/FIX_GIT.cmd` and both `.gitignore` files alone meanwhile.

## For Cole
- Should FIX_GIT v2 also untrack the queue database? It's a git write, so it has to run from the .cmd.
- When an ask to Nova is still unfinished after 6 h, should it stay Priority 0 until done, or become a task?
