# Project Nova — Code & Directory Review
**Reviewer:** Claude (Opus) · **Date:** 2026-05-23
**Scope:** workspace tree, active code paths, config, security, and forward direction.
Model weights (`models/`) were intentionally not opened (sealed).

---

## 0. Executive summary

The system is in good working shape after today's session — the launcher, app window,
live logs, sleep/wake autonomy, and queue persistence are all verified live. The issues
below are mostly *accumulated drift and clutter*, not active breakage. The single most
important finding is a **documentation/implementation conflict** that is very likely
contributing to Nova's confused tasking behavior. Everything else is cleanup and
forward-looking polish.

Priority legend: 🔴 fix soon · 🟠 worth doing · 🟢 nice-to-have.

---

## 1. 🔴 Biggest issue: Nova's instructions describe a DIFFERENT system than the one she runs

`BOOTUP/HEARTBEAT.md`, and the autonomy/tasking sections of `BOOTUP/AGENTS.md` and
`BOOTUP/NOVA.md`, still describe the **legacy model**:

- a multi-step "Thoughts cycle" (Step 1 Orient → Step 2 Process Master_Inbox → … → Step 5),
- "Yield Protocol: one action per turn, check in after each exec,"
- manual reading and editing of `priority.md`.

But the server now drives autonomy with a **completely different protocol**: a cold
sleep/wake tick that hands her one task + its progress log and asks for a single step
reported as a `TASK_PROGRESS` block, with `DECISION: ENGAGE/OBSERVE/SLEEP`. These two
models conflict. Nova is effectively reading one rulebook while being quizzed on another.

This is almost certainly part of why "she keeps seeing tasks and goes to sleep" — her
base instructions point her at a Master_Inbox/Thoughts ritual that no longer matches the
tick she's actually answering.

**Recommendation (high value):** rewrite `BOOTUP/HEARTBEAT.md` and the autonomy sections
of `AGENTS.md`/`NOVA.md` to describe the *current* model (sleep/wake, one step per tick,
`TASK_PROGRESS`, server owns status). Remove or rewrite the old "Thoughts cycle" steps.
This is a docs change, not code — low risk, high payoff. I can do this next if you want.

Related: the `cron.health_check` message (now disabled) and several docs still reference
the old "Thoughts cycle" — fold them into the same rewrite.

---

## 2. Errors & latent bugs

- 🟠 **`nova_launcher.log` is append-only and never rotated** — it's already ~736 KB with
  entries back to May 8. It will grow unbounded. Add date-stamped rotation (the autonomy
  logs already date-stamp; the launcher log should too) or a size cap.
- 🟠 **Console-close shutdown is not guaranteed.** `nova_start.py`'s `finally` (stop llama,
  shutdown gateway) runs on normal exit and Ctrl+C, but Windows closing a console with the
  "X" sends `CTRL_CLOSE_EVENT` and Python's `finally` may not complete — leaving
  `llama-server` running. Consider a `signal`/`SetConsoleCtrlHandler` hook, or a small
  "Stop Nova" script that kills port 8080/8765 owners.
- 🟠 **The 400 from llama-server** seen during testing is now captured to
  `logs/llama/bad_requests-<date>.jsonl` (added today). When it recurs, inspect
  `total_chars` — the likely cause is a tick whose context exceeds the 32 K window. If so,
  trim what's injected into ticks (see §6).
- 🟢 **Redundant status field.** `priority.md` carries a human `Status:` sub-bullet that the
  new `task_state.json` now supersedes; the two can diverge (the markdown one won't
  auto-update). Decide on one source of truth (see §5/§6).
- 🟢 **`_parse_queue` is whitespace-fragile** — it keys off `"- "`/`"* "` line prefixes and
  exact section headers. It works today but will silently miss/duplicate tasks if the
  markdown format drifts. A structured store would remove this class of bug (see §6).

No syntax errors or import failures were found in the active paths.

---

## 3. Redundant / outdated files (cleanup checklist)

🔴 / 🟠 Safe to delete or archive:

- `general_tools/nova_chat/server.py.bak_20260523_034130` — today's backup; delete once
  you're confident in the current `server.py`.
- `general_tools/nova_chat/static/index_backup.html` — old UI snapshot, **tracked in git**.
  Delete (git history already preserves it).
- `.nova_app_profile_2740/` — leftover Chrome profile from a launch (lots of browser junk).
  The launcher now auto-cleans these on the next run, but this one can be deleted now.
- `build_exe/` (`dist/`, `work/`, `NovaStart.spec`) — PyInstaller build artifacts; regenerated
  by `build_nova_start.cmd`. Gitignore and/or delete.
- `PATCHES/*.ps1` — one-off patch scripts (`patch_autonomous_behavior`, `patch_claude_client`,
  `patch_depth_server`, `patch_eyes_server`, `patch_mute_system`, `patch_nova_payload`,
  `patch_workspace_context`, `apply_bootup_reorganization`). These were applied long ago.
  Move them to `PATCHES/Archived/` (which already exists) to declutter the root of `PATCHES`.

🟢 Stale references (no dead code, but misleading — they contradict reality):

- **ExLlamaV2 mentions** in `gateway.py` (incl. the cosmetic model label `"nova-exllamav2"`),
  `nova_chat/server.py`, `orchestrator.py`, `nova_motor/tool_executor.py`,
  `nova_cortex/context_builder.py`, `nova_memory/session_store.py`, `orient.py`, `AGENTS.md`,
  `ORIENT.md`, and the `.aignore` comment. The backend is **llama.cpp**; these are leftover
  comments/labels from an architecture that was never deployed. A find-and-replace
  (ExLlamaV2 → llama.cpp, `nova-exllamav2` → e.g. `nova-qwen`) removes a recurring source of
  confusion for both Nova and future sessions.
- `ORIENT.md` was last auto-updated 2026-05-09 and predates the launcher, app window, and
  autonomy rework. Worth a refresh so the "master reference" is actually current.

🟢 Duplicate entry points:

- `general_tools/nova_chat/launch.py` + `server_runner.py` are the *older* browser-tab launch
  path; `NovaLauncher.py` + `NovaStart.cmd`/`.exe` are the current one. Keep one canonical
  path and mark the other clearly deprecated (or delete) so it's obvious which to use.

🟢 Parallel task representations:

- Tasks now live in **four** places: `priority.md` (queue), `Tasking/task_state.json` (new
  state), `Tasking/tasks/<TASK_ID>/master.md` (per-task dirs Nova creates), and
  `Tasking/Finished/{completed_success,completed_fail,cancelled}/` (archive). This overlap is
  confusing and easy to let drift. Pick the canonical pair (`priority.md` + `task_state.json`)
  and either retire or auto-populate the others (see §6).

🟢 Handoff accumulation:

- `_admin/passover/` has 7 dated handoff folders back to March. Fine as history; consider
  keeping the latest 1–2 and zipping the rest.

---

## 4. Security & config

- 🔴 **Live Discord bot token sits in plaintext in `nova_gateway.json`**, which is **not in
  `.gitignore`**. It isn't currently committed (the file is untracked), but a single
  `git add .` would commit the secret. You already keep a sanitized `nova_gateway - tokenless.json`
  (which *is* tracked) — formalize that:
  1. Add `nova_gateway.json` to `.gitignore`.
  2. Better still, load the token from an environment variable / `.env` (already gitignored)
     instead of the JSON, so the runtime config carries no secret at all.
  3. Since the token has been sitting in a non-ignored file, consider rotating it in the
     Discord developer portal to be safe.
- 🟠 **`.gitignore` doesn't cover `.nova_app_profile*`** — add `.nova_app_profile*/` so the
  Chrome junk can never be committed.
- 🟢 **API keys:** `nova_chat/check_keys.py` implies Claude/Gemini keys live somewhere — confirm
  they're sourced from `.env`/environment and never from a tracked file.

---

## 5. Code structure & maintainability

- 🟠 **`server.py` is a 3,066-line monolith.** It now holds WebSocket handling, ~30 HTTP
  routes, the autonomy daemon, the task/queue logic, logging, llama control, and more. It
  works, but it's the hardest file to reason about and the riskiest to change (today's
  edits had to thread carefully around it). Over time, extract cohesive modules — e.g.
  `autonomy.py` (daemon + tick + task state), `queue.py` (`_parse_queue`/`_write_task`/
  `_complete_task` + state), `events.py` (`emit_event` + log endpoints). No rush; do it
  incrementally with the server able to run between steps.
- 🟢 **No automated tests.** The fragile bits (queue parsing, `TASK_PROGRESS`/`TASK_INTENT`
  block extraction, the wake-gate logic) are exactly what unit tests protect well, and
  they're pure functions — easy to test. A tiny `tests/` with a dozen cases would catch
  format-drift regressions cheaply.
- 🟢 **`nova_body` wiring audit.** The body modules (`vigilance.py`, `agent_loop.py`,
  `prefrontal_cortex.py`, `circadian.py`, `goals.py`, etc.) are referenced in various places,
  but the May handoff noted some are "built but not connected" (e.g. `vigilance.py` into
  gateway startup). Worth a focused pass to confirm which are live, which are orphaned, and
  which the new autonomy daemon should be calling.

---

## 6. Future direction & suggested next implementations

In rough priority order:

1. 🔴 **Align Nova's docs with the new autonomy model** (§1). Until her `BOOTUP` instructions
   match the `TASK_PROGRESS`/sleep-wake reality, behavior will stay inconsistent. Highest
   leverage change available right now.
2. 🟠 **Make `task_state.json` the single source of truth, render `priority.md` from it.**
   Right now the server reads the human markdown and keeps a parallel JSON. Flipping it —
   JSON is canonical, `priority.md` is a generated human view — removes the divergence risk,
   kills the whitespace-fragile parser, and lets you safely add fields (steps, deadlines,
   owners) later. The `Tasking/tasks/` and `Finished/` folders can then be auto-maintained
   from the same store.
3. 🟠 **Trim tick context to fit the 32 K window reliably.** If the 400s recur, the tick is
   probably overflowing context. Give heartbeat ticks a deliberately slim context (the
   task + progress + Cole-intent only) rather than the full inject set — this also makes her
   cheaper and faster per wake.
4. 🟠 **Robust shutdown / a "Stop Nova" affordance** (§2) so closing the window or console
   never orphans `llama-server`.
5. 🟢 **Log hygiene:** date-stamp + rotate `nova_launcher.log`, and add a retention sweep for
   `logs/backups` (3.1 MB and growing) and `logs/chat_sessions`.
6. 🟢 **Finish the vision path:** `TASK_MM_0513` (download moondream2) is queued; `eyes.py`'s
   `describe()` depends on it. Good first real autonomous task to watch end-to-end once §1 is
   done.
7. 🟢 **Surface task state in the UI:** you now have `task_state.json` with per-task progress.
   A small "Tasks" panel (or feeding it into the existing Thoughts pane) would let you watch
   queued → in_progress → done with the step log, instead of reading the file.
8. 🟢 **A self-improvement loop that actually closes:** the `JOURNAL.md` correction notes
   added today are a seed. Periodically feeding recent corrections back to Nova ("here's a
   pattern in how you've been failing") is a concrete, on-mission step toward the
   self-improving agent goal.

---

## 7. Suggested quick-win cleanup (when convenient)

Low-risk, high-tidiness, in order:

1. Add to `.gitignore`: `nova_gateway.json`, `.nova_app_profile*/`, `build_exe/`.
2. Delete: `server.py.bak_*`, `static/index_backup.html`, `.nova_app_profile_2740/`.
3. Move `PATCHES/*.ps1` → `PATCHES/Archived/`.
4. Find-replace ExLlamaV2 → llama.cpp (comments/labels) across the ~10 files in §3.
5. Rewrite `BOOTUP/HEARTBEAT.md` + autonomy sections of `AGENTS.md`/`NOVA.md` (§1).
6. Refresh `ORIENT.md` to reflect the launcher + autonomy rework.

I can take any of these on — §1 (doc/model alignment) and item 2's deletions are the ones
I'd recommend doing first, since the first directly affects how Nova behaves and the second
is pure clutter removal.
