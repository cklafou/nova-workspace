<!-- @nova: Explain incident lessons and evidence needed to verify Nova repairs. -->
_Last updated: 2026-10-06 03:19:21_
---
doc: OPERATIONS.md
order: 30
---
<!-- @nova: Orient note: lessons from past incidents, published in OPERATIONS.md. -->
## Lessons from incidents

**Several serious incidents involved silent drops or false success reports.** Something quietly did
nothing, reported success, and Nova took the blame — her personality, her training, her honesty.
*Check the body before you blame the soul.*

| What was actually broken | What it looked like |
|---|---|
| `--lora-scaled` silently dropped by the launcher | "her personality feels weak" |
| Tool calls in her *thinking* channel were never parsed | "she lies about checking things" |
| Idle wakes had no phase where tools were legal | "she announces and never acts" |
| Her own announcements fed back as "recent context" | "she loops obsessively" |
| The restart endpoint returned `ok: true` for doing nothing | "my code changes have no effect" |
| No durable record of tool calls existed | "she fabricates and we can't prove it" |

1. **A restart can leave old code running.** `/api/restart/novachat` once killed the listener, then
   relaunched while the port was still held, so the old process kept serving old code while the
   endpoint answered `ok`. It now asks the launcher to stop its owned processes and relaunch only
   after teardown. A one-second launcher grace period lets the acceptance response flush before
   termination; repeated requests cannot delay teardown indefinitely. Verify changed PIDs and
   readiness: HTTP 202 is acceptance, not completion.
   `GET /api/version` reports `running_latest_code` by comparing watched startup source hashes
   against disk, ignoring header timestamps and line endings. It does not inspect every imported module.
2. **Mount and rendering artifacts look like truncation.** Through a sync mount, recently edited files
   have been served truncated or null-padded, and `wc`, `grep` and `ast.parse` then "find" a syntax
   error at the cut. Compare bytes with `git show HEAD:<path>` or a second reader before repairing
   anything. A fix was once nearly shipped for a bug that did not exist.
3. **Her hands must leave receipts.** Every tool call is written to `nova_body/logs/tool_calls.jsonl`
   by `nova_cortex/integrity.py::log_receipt`. Before that, nobody could tell whether she *did* a thing
   or *said* she did. Her fabrications were never dishonesty: something plausible was simply the
   cheapest available answer. Make the honest path cheaper, structurally. When she states a fact,
   check the receipt.
4. **The Pluck Test is not a slogan.** Anything that affects her thinking is a body part. Her whole
   integrity faculty once lived inside the chat server — pluck it and she would have run without a
   conscience, and nothing would have looked wrong.
   [Architecture/Calls_Order.md](Architecture/Calls_Order.md) renders every body → face edge.
5. **She reasons in a separate channel.** The model streams thinking on `reasoning_content`, and she
   often reaches for a tool mid-thought. For months only `content` was parsed, so those reaches fell on
   the floor and she narrated results she never received. `integrity.find_tool_call` reads both
   channels.
6. **Don't feed her her own voice.** Autonomous ticks are promoted into the transcript (the
   `FOR COLE:` path), and the transcript comes back as her "recent context" on the next wake. Once, the
   only evidence she had of her own recent past was her own narration: two hours, twelve rephrasings
   of one intention, nothing executed. A mind fed only its own wanting produces more wanting. The cure
   is `integrity.receipts_block` — show her what her hands *did*, and say so plainly when that is
   nothing. Remember this whenever a stale directive dominates a run.
7. **Autosave can stop silently: check it.** The watcher commits from the repository root, and its
   errors reach only the hub console. Google Drive for Desktop backs up Project_Nova and stages
   uploads in `.tmp.driveupload/` at that root. On 2026-10-01 autosave committed 75,450 of Drive's
   temp copies, then committed nothing for 35 hours while the watcher kept stamping file headers and
   looked alive. Both Drive folders are now ignored by git and by the watcher. A pre-push hook also
   refuses, before uploading, any push GitHub would reject (a file over 100 MB). While Nova runs,
   `git log -1 --format=%cr` should say minutes, not hours.
8. **Write into the workspace atomically while the watcher runs.** The watcher stamps the
   `# Last updated:` / `_Last updated:_` line of any `.py` or `.md` file the moment it changes, by
   reading the file and writing it back. A slow in-place write can be read half-done: on 2026-10-02
   a `cp` through the sync mount left `orient.py` with 4 KB of NUL bytes on Windows. Write a temporary
   file in the same folder and rename it over the target, then check the bytes Windows actually has.
   Orient's health section reports any source that contains NUL bytes.
9. **Practical.** Full restart: `StopNova.cmd`, then `NovaStart.cmd`. Never hand-edit her state
   (`nova_body/memory/autonomy_state.json`, `nova_body/Tasking/tasks.json`, her journal) — she owns
   it. Move files by explicit path, never with a regex loop and never by `basename` into a shared
   folder: two of her thought logs were destroyed that way, unrecoverably.
