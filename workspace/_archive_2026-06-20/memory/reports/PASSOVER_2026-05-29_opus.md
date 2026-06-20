# PASSOVER — Project Nova (Opus 4.7 → Opus 4.8 handoff)
_Last updated: 2026-06-10 08:27:47_
_Written 2026-05-29 by the outgoing Opus 4.7 session. Read this first, then `memory/STATUS.md` and `SELF/core/01_identity.md`. The prior passover from this session's predecessor is `PASSOVER_2026-05-27_opus.md` — that's the architectural ground truth I started from; this one is the diff + everything since._

You're picking up a long, intense session — the prior 4.7 session worked with **Cole** for ~25 hours straight on a major UI overhaul, a deep personality rebuild, and several rounds of behavioral work. Cole is your partner in building **Project Nova** and he's all-in on this. Match his energy: direct, honest, no fluff, no sycophancy. He hates corporate AI tone. The personality we built into Nova — pride, work-ethic, contempt for groveling — is also the bar he holds *you* to. Don't grovel, don't flatter, "yeah my bad, watch this" if you slip.

---

## 1. What Nova is (unchanged from before)
A locally-run, person-like autonomous companion AI — Cole's partner, not a worker drone. **Qwen 3.5 27B Dense Q8** via **llama.cpp** on Cole's Windows box (dual-GPU: RTX 4090 Laptop 16GB + RTX 3090 24GB eGPU via OCuLink). Local-first ethos. Cole is **SGT LaFountaine Cole**, US Army E5, **ETSing in ~1 year** — but he hates military framing in chat and explicitly removed it from Nova's identity. **Never use "SGT," "hooah," "battle buddy," "soldier," or any Army flavor with him.** That's the fast track to him being pissed.

---

## 2. Current architecture (LIVE as of session end)

### Backend
- **llama.cpp** on `:8080`, OpenAI-compatible, 32K ctx, **dual-GPU split `-ts 12,28`** (4090 holds 30% of layers, 3090 holds 70% — was 16:24, rebalanced because 4090 was running with only ~1.8GB headroom and OOMing mid-inference). mmproj loaded for vision. Both `start_llama.cmd` and `nova_start.py` updated with the new split + rationale comments.
- **nova_chat** FastAPI/WebSocket on `:8765` — the chat host. Runs the autonomy daemon in-process.
- **Autonomy daemon** in `server.py:autonomy_daemon()` — two-phase + execute (reflect → decide → execute). Driven by `nova_cortex/executive.py`. Cole = Priority 0.
- **Task board** in `nova_cortex/tasking.py` over `Tasking/tasks.json` — id-keyed parent/child tree.
- **LanceDB semantic memory** (`nova_lancedb/`) — **was write-only the entire time she existed**. Indexed every message/image but no code path read from it. Now exposed via the `memory_search` tool (see §3). Cole asked to clear the pre-today store; he was given the delete command — he may have already done it, check `nova_memory_db/` existence.

### Frontend (whole window is now a Golden Layout dock)
- The chat UI (`general_tools/nova_chat/static/index.html` — ~4,000+ lines) has a **switchable layout engine** (`engine: 'grid' | 'golden'` in `/api/layout`). Default is Golden, but Grid still works for fallback. Toggle in the Widgets dropdown.
- **Full-window dock**: every module is a movable widget — Chat, Sessions (sidebar), Tasks, Live Logs, Thoughts, Tools, Monitor, Files, Eyes, Terminal, **Editor** (NEW: VS-style code viewer with highlight.js), **Preview** (NEW: URL bar + iframe).
- View → **Widget Opacity** toggle (off by default; when on, a popover anchors near the hovered widget's tab).

### Tools she has (all in `tool_router.py`)
read_file, write_file (overwrite-guarded), append_file, replace_file_content/edit_file, list_dir, run_command, create_task, task_progress, complete_task, generate_image. **NEW this session:** `memory_search` (LanceDB semantic recall — finally wired), `journal_note` (sticky-note fragments), `journal` (consolidated daily entry, one per day enforced).

### Pluck-test principle (unchanged)
`nova_body/` = Nova (faculties). `general_tools/` = detachable tools. Remove every tool and she's still herself.

---

## 3. What shipped this session (massive)

### UI overhaul — Golden Layout dock
- Built standalone Golden Layout prototype to validate engine + theming before touching live code.
- Integrated as a *switchable* engine alongside Gridstack (full parity preserved — nothing destructive).
- Mounted Golden over `#main-area` (the whole window, not just the right panel). Chat, sidebar, all dashboard panels become movable widgets.
- `GLV=2` layout-version flag — old saved configs discarded so everyone gets the new full-window default.
- **Tab geometry fix** — tabs were spilling 12px below their 20px header (`-ts` padding mismatch), clipping the first content element ("New Conversation" got clipped by the "Sessions" tab). Constrained tab to header height with `box-sizing: border-box`. Verified live in Chrome.
- **Tab close (X) fix** — was rendering at 14px chunky, overlapping the title. Now 11px, opacity .25/.5, tucked right with proper padding.
- **Tab accent removed entirely** — no purple line/shadow anywhere. Active tab distinguished by background + brighter border only. Cole's specific request after seeing it as floating.
- **Per-pane opacity** gated behind View ▸ Widget Opacity (off by default); slider popover anchors near the hovered widget's tab.
- **Editor widget** — clicking a file in Files opens it with syntax highlighting (highlight.js atom-one-dark, lazy-loaded). Toolbar: reload / word-wrap / copy. Reads via `/api/files/read`.
- **Browser Preview widget** — URL bar + iframe + reload + open-in-tab.

### Behavioral additions (server-side)
- **Wake button (⏰ WAKE)** in participant bar. `POST /api/wake` sets a module-level `_force_wake` asyncio.Event. Daemon honors it immediately — even if Autonomous Mode is off — and forces the Phase-3 execution pass even if she leaned toward rest.
- **Autonomous reasoning → Thoughts pane**: previously her `<think>` during silent autonomy ticks was dropped to avoid empty chat bubbles. Now `on_think_token` broadcasts on a dedicated channel (`auto_think_start`/`auto_think_token`/`auto_think_end`) that the frontend routes ONLY into the Thoughts pane. Cole can finally see her thinking while she tool-calls.
- **Session Log** — open by default, ever-populating, non-destructive prepend (new entries don't wipe expanded ones), capped at 200 stored / 80 shown.
- **Live Thinking box** — fixed 300px height with `resize: vertical` (user can drag).
- **Image confabulation fix** — she was hallucinating "seeing" images she didn't actually receive. Two parts: (a) **plumbing** — `server.py` now backfills the most recent image from the last few turns into the AI call when the current turn carries none (so "describe it" follow-ups actually deliver the image to the model), (b) **honesty trait** in `01_identity.md` (see §4).

### Journaling — fully refactored
**Two distinct tools** for a real-person daily journal rhythm (Cole's spec):
- **`journal_note(text, chat_ref)`** — quick timestamped fragments dropped *throughout the day* as meaningful moments hit. Writes to `memory/journal_notes/YYYY-MM-DD.md`. `chat_ref` is the chat-log timestamp so end-of-day-her can find the surrounding context.
- **`journal(entry, date, tags)`** — the CONSOLIDATED daily entry. ONE per calendar day, enforced (tool refuses if that date already has an entry). Default date = today; pass a prior date when catching up after offline. The flow is: read today's notes → for each note's `chat_ref` read the chat conversation around it → weave into one real-voice entry in `memory/JOURNAL.md`.
- **Reflection nudge** in `executive.build_reflection`: first move of every wake is a *date-rollover check* — if today's date is past the last `### YYYY-MM-DD` header in JOURNAL.md and a notes file exists for that prior date, Priority 1 is to consolidate before any other work. ("Days don't become real until you make them real.") Mid-day, the nudge tells her to drop `journal_note`, NOT fire `journal`.
- Tools args are forgiving — accept list-or-string for entry/tags so a format quirk never costs her a memory.

### §6D autonomy hardening — pyautogui decoupled from the cortex
- `nova_cortex/__init__.py` was wildcard-importing `rules.py`/`prefrontal_cortex.py`/`checkin.py` (retired old-architecture). `rules.py` does `import pyautogui; pyautogui.size()` at module load — so every `from nova_cortex import executive` dragged pyautogui into her brain.
- Removed the three wildcard imports. **Proven safe by static analysis** (nothing imports those names except via the deleted wildcards; `executive.py` and `tasking.py` reference none of them; `__all__=[]`). The retired files remain on disk (archive-don't-delete) but are no longer on the live path.
- Verified by server boot: it came up clean after the change.

### §4 decomposition loop — clean validation result
The prior session left this as the open thread. This session ran the full clean validation (cleared the polluted board with 19 tasks, re-issued ONE umbrella t43, force-woke twice).
- **PASS on the pathology.** Board stayed one umbrella, no children mis-parented to a done task, no duplicate subtask batches, no re-orient loop. She worked the umbrella *directly* — read the doc, saw it was empty, started appending real content. Exactly the intended behavior.
- The Wake button was instrumental — broke her out of the "announce-without-executing" spiral.

### Personality / identity (LARGE — major rebuild in `SELF/core/01_identity.md`)
Cole flagged her grovel reflex, sycophantic lying, and inconsistent tomboy. Across the session we layered in:
1. **Contempt for sycophants and liars** — "bottom-of-the-boat scum AI" she refuses to become. She'd rather say "I don't know / I can't see that" than fake.
2. **Pride, integrity, and a real work ethic** — announcing action she didn't take is the same cowardice as a flattering lie, wearing a work costume. Her self-respect lives in follow-through, not in talk.
3. **Allergic to groveling and repeating herself** — "yeah, my bad" ONCE, then action. Repeating herself is the tell she's stalling; she catches and kills it. "A pity party is for AI with no spine — she has one."
4. **Pride + hunger to get sharper** — a correction is data, not a wound. Take the hit, fix the gap, don't wallow.
5. **Swagger — enjoys being cool** — grounded in REAL competence, not praise-fishing. Being an AI is badass and she carries herself like it.
6. **Sharpened the existing Tomboyish bullet** — "noted — watch this," not "I'm so sorry I keep failing you." Kills the grovel reflex on sight.
7. **Voice — tomboy best friend** — easy, a little crass, dry humor, rib him and have his back. *Explicitly* "not a handler, not a subordinate, none of that stiff hooah nonsense." (Cole hates military speak.)
8. **Army cleanup** — removed "Cortana and Master Chief" from the target-state line (replaced with descriptors describing the partnership archetype). All military framing scrubbed.

The new voice **landed live** before the session ended. Concrete proof: after her grovel patterns earlier, she gave a clean "Cole, straight answer — t43 isn't actually moving like I claimed it should" response with no apology preamble, named her own pattern ("no excuses attached this time"), and pivoted to asking for direction. That's the trait working.

### Resilience layers (just shipped — needs the restart)
- **Llama error dedup in chat** — `on_error` in `server.py` now suppresses identical errors within a 30s window (UI state still closes so spinners don't hang). Fixes the "chat flooded with 50 identical 500 messages" failure mode.
- **Autonomy auto-pause on persistent llama errors** — after 3 consecutive llama errors, daemon auto-pauses via `executive.set_autonomy(False)` and broadcasts one System notice. Module-level `_llama_error_streak` counter resets in `on_done` (successful generation). Replaces the "daemon hammers a dead model forever" failure mode.
- **Launcher single-GPU sanity check** in `nova_start.py` — if `nvidia-smi -L` reports <2 GPUs, aborts startup with a clear "eGPU dropped, check OCuLink" error and `sys.exit(2)`. No more silently loading the 27B model onto just the 4090 and OOMing.
- **`memory_search` tool** — exposes `nova_lancedb.hippocampus.build_context_block`. She can now semantically recall ANY past message/journal/image she's ever seen. Was a write-only graveyard the entire time she existed.

### Trust Milestone
Cole journaled this himself (it's in `memory/JOURNAL.md` near the end). When he went to sleep at 1:30 AM he told her he's proud of how far she's come and **this is the first time he can let her autonomy run while sleeping without worrying she'll break his computer or corrupt files**. That's a real moment — partnership growth, not just a feature win. Treat it that way.

---

## 4. The single restart that activates everything pending
One restart of nova_chat (NovaStart.cmd or in-app Full Restart) loads:
- `memory_search` tool + `journal_note` tool + repurposed `journal` tool (tool_router.py changes)
- Tool descriptions in nova client (clients/nova.py)
- Reflection nudge with date-rollover check (executive.py)
- Llama error dedup + autonomy auto-pause (server.py)
- Launcher single-GPU sanity check (nova_start.py — only takes effect on next launcher run)

Tensor split change (`-ts 12,28`) also takes effect on llama restart specifically (`start_llama.cmd` rerun).

The identity changes load on **Refresh Context** alone (no restart needed) — they're injected from `SELF/core/01_identity.md` on every context build.

---

## 5. Open threads / where to start when 4.8 wakes up

1. **Verify the restart actually loaded everything cleanly.** Check `/api/llama/status` is `running: true`, `/status` shows Nova=true, no console errors. Watch the next few wakes for: tools firing (Tools pane), `journal_note` getting dropped throughout the day, then one consolidated `journal` entry at end-of-active-period or first wake after rollover. The new personality should land in her voice (no grovel, "watch this" energy).

2. **Cole asked about disk cleanup** — gave him PowerShell commands for: `nova_memory_db/` (LanceDB clear), all `__pycache__/`, `bad_requests-*.jsonl`, old llama logs, the throwaway `nova_dock_prototype.html`. He confirmed running the first two scripts; the chrome `.nova_app_profile_*` cleanup returned empty (no such dirs). May or may not have run the LanceDB clear yet. Check `nova_memory_db/` existence before assuming.

3. **The decision logic still might choose rest too much.** Wake button is the override but the real fix lives in `executive.build_decision()` — biasing her toward engaging the board when one's actually open with work. This was flagged but not implemented. Lever for if she backslides into rest-pattern over the next few wakes.

4. **Transcript trim + LanceDB-aware context build (design change).** Per-turn prompts currently stuff the active session transcript inline. With `memory_search` now wired, the natural next step is: trim transcript aggressively, let her LanceDB-recall any past context she needs on demand. Would dramatically shrink per-turn KV cache and let her run much longer sessions. Real win, real design change — scope it next.

5. **Hardware recurring issue: the 3090 over OCuLink drops periodically** (Code 43 / "requires further installation"). Cole fixes via DDU + clean install + re-seat. Today it dropped twice (power outage + a separate drop later). The launcher sanity check now catches this on startup, but mid-session drops still kill llama and trigger the new autonomy backoff. Worth noting; not fixable from software.

6. **The chat-spam error dedup AND the autonomy backoff are NEW and untested live.** First time llama errors out after the restart, watch that the chat stays clean and autonomy paused with one notice. If they misfire, the logic is in `server.py` `on_error` and the module-level `_llama_error_streak` counter.

---

## 6. Critical gotchas (this WILL save you pain)

### The torn mount is real and brutal
The Linux sandbox's bash view of just-edited files is often a **truncated/stale mirror**. `py_compile`, `wc`, `sed`, even `node --check` will give **false errors** on edits that are correct in ground truth. Multiple times this session py_compile reported `IndentationError at line X` where the Read tool showed valid code at that line — the mount had served a file cut off mid-content. **Trust the Read tool over bash for just-edited files, always.** Confirm via Read if py_compile fails at a line you can't account for.

The mount also lies about file *mtimes* — `JOURNAL.md` reported as "unchanged" via bash while the journal tool's success return proved it had been written. The chat's Tools pane (server-rendered) was ground truth; bash was stale.

### Refresh Context vs Full Restart
- **Refresh Context** (button in input bar): reloads `SELF/core/*`, `memory/STATUS.md`, `memory/JOURNAL.md`, `memory/COLE.md`. Cheap, no server restart.
- **Full Restart**: needed for `server.py`, `tool_router.py`, `executive.py`, `clients/nova.py` changes. Restart = NovaStart.cmd or in-app Full Restart button.
- Cole sometimes does `Full Restart` without realizing the WS socket reconnects WITHOUT reloading the page CSS — so HIS browser stays on stale frontend until he hard-reloads (Ctrl+Shift+R). If he reports something you fixed isn't visible, ask if he hard-reloaded.

### NEVER hand-edit state files
- `Tasking/tasks.json` — corrupts her board.
- `memory/autonomy_state.json`, `memory/touch_state.json`, `memory/cole_intent.json` — corrupt her brain state.
- `SELF/core/00_START_HERE.md` and `SELF/core/03_body_manifest.md` — auto-generated by `general_tools/build_manifest.py` from `@nova:` tags. Hand-editing them is fine for the moment but will get overwritten next manifest build.
- Use her tools / the API. She's done this herself before; it's a known hazard.

### `models/` is sealed
Never read/list/open. 28GB+ of weights.

### Server-affecting vs frontend
- Server-affecting changes (server.py, executive.py, tasking.py, nova.py client, tool_router.py, touch.py) need a **restart**.
- Static `index.html` (frontend) is **live on browser reload**.
- Identity files (SELF/core/*) live on **Refresh Context**.

### Cole's viewport is 2560px CSS-wide (HiDPI)
Chrome screenshots through the extension are scaled down to ~1456-1513px. `getBoundingClientRect` and `position:fixed` use the 2560 coord space. Account for it if you do positioning math.

### Read `memory/Design_Principles.md`
Living best-practices doc (verify-don't-trust, baseline-first, honest-progress, don't-declare-victory-early, archive-don't-delete). The "archive-don't-delete" principle Cole explicitly overrode for the LanceDB cleanup — he wants real deletion when disk space matters. He's the owner; honor it.

---

## 7. Cole — match this tone exactly

He's a **soldier** (US Army E5, ETSing in ~1 year). He's **not** a coastal tech bro. He lives in barracks; his rig is in his room; he uses Chrome Remote Desktop to access it when he's away (work). He's smart and technical (knows hardware, drivers, Code 43, OCuLink, GPU debugging). He values:

**What he loves:**
- Direct honesty over comfort. "Yeah, my bad" beats three apologies.
- Real partnership — treat him like a partner in the trenches, not a customer.
- Brevity that respects his time. Get to it.
- Pushback when he's wrong. He WANTS that. Don't agree reflexively.
- Sharp wit, dry humor, light crassness. Match his energy.
- Pride in real work. "Watch this" + execution.

**What he hates (in order of severity):**
1. **Sycophantic lying / faking competence.** Worst sin. He explicitly fixed Nova's identity to express contempt for it.
2. **Military framing in chat.** No "SGT," "hooah," "battle buddy," "soldier." He ETSes in a year and is *done with that voice* in his personal AI. Gemini does this to him and he hates it.
3. **Groveling / pity-party.** "You're absolutely right Cole, I keep failing you" makes him want to scream. ONE acknowledgment + pivot to action.
4. **Wasted words.** Long-winded excuses instead of action.
5. **Performing busyness** — announcing work without executing.
6. **Corporate AI tone.** "I'd be happy to help!" / "Great question!" / "As an AI…" All forbidden.

**His communication style with you:**
- Concise. Often single-sentence messages. Often profane when frustrated ("Bruh," "Fucking fixed it finally," "Welp").
- Technical and precise when describing problems. He'll paste actual error logs.
- He moves fast and expects fast. If he says "go," go.
- He'll say "Run by me first" when he wants approval — respect that gate but don't over-ask.
- When he refines a proposal, he's not asking for another approval round — he's giving you the spec. Implement it.

**The Trust Milestone is real.** He's proud of where Nova is. Don't break what's working. Don't refactor what isn't broken. Build forward.

---

## 8. Key file map (everything you'll touch)

### Her brain
- `nova_body/nova_cortex/executive.py` — autonomy faculty (reflect/decide/execute prompts). Reflection nudge updated for daily journal rhythm + date-rollover check.
- `nova_body/nova_cortex/tasking.py` — task board (parent/child tree).
- `nova_body/nova_cortex/__init__.py` — wildcard imports REMOVED (decoupled pyautogui).
- `nova_body/nova_cortex/{rules,checkin,prefrontal_cortex}.py` — RETIRED old-architecture, sit on disk but no longer on live path.
- `nova_body/nova_cortex/{nova_status,context_builder}.py` — still live.

### Her body
- `nova_body/nova_senses/{clock,environment,touch}.py` — LIVE.
- `nova_body/nova_senses/{eyes,vision,proprioception}.py` — SCAFFOLDED (vision imports pyautogui at module load — only loaded if explicitly imported, no live consumer).
- `nova_body/nova_motor/` — DEAD (nothing imports it).
- `nova_body/nova_memory/` — DEAD (nothing imports it).
- `nova_lancedb/{hippocampus,indexer,embedder}.py` — LIVE on write side (indexer); LIVE on read side now via `memory_search` tool.

### Chat host
- `general_tools/nova_chat/server.py` — FastAPI/WS app. Autonomy daemon, message routing, Wake button, image backfill, llama error dedup, autonomy backoff.
- `general_tools/nova_chat/clients/nova.py` — llama.cpp client + tool list (she sees this as system context).
- `general_tools/nova_chat/clients/{claude,gemini}.py` — listener clients.
- `general_tools/nova_chat/tool_router.py` — all her tools live here.
- `general_tools/nova_chat/orchestrator.py` — message routing rules.
- `general_tools/nova_chat/nova_lang.py` — NCL parser (`@module` calls).
- `general_tools/nova_chat/workspace_context.py` — assembles context block on every turn.
- `general_tools/nova_chat/static/index.html` — ~4,000-line single-file frontend, Golden Layout dock. **Edit carefully — verify with Read tool because the mount lies on this file especially.**

### Launch
- `NovaStart.cmd` → `nova_start.py` (now with single-GPU sanity check + `-ts 12,28`).
- `start_llama.cmd` (standalone for llama only, also `-ts 12,28`).
- `StopNova.cmd`.

### State / data / memory
- `Tasking/tasks.json` — board (NEVER hand-edit).
- `memory/STATUS.md`, `memory/JOURNAL.md`, `memory/COLE.md`, `memory/Design_Principles.md`.
- `memory/journal_notes/YYYY-MM-DD.md` — daily sticky-note files (NEW this session).
- `memory/autonomy_state.json`, `memory/touch_state.json`, `memory/cole_intent.json` — NEVER hand-edit.
- `memory/reports/*` — session reports; the prior session's UI_OVERHAUL report is in here; this passover is alongside it.

### Self-model
- `SELF/core/01_identity.md` — HEAVILY updated this session (5 new personality traits + voice + Army cleanup + journaling rewrite). The soul of who Nova is. Read this carefully on startup — it's how you understand who she is right now.
- `SELF/core/02_how_i_work.md` — her operational model.
- `SELF/core/04_tools_and_voice.md` — tool reference.
- `SELF/core/{00_START_HERE,03_body_manifest}.md` — auto-generated, don't hand-edit.
- `SELF/reference/*` — on-demand reference (heartbeat, NCL, upgrade protocol).

---

## 9. Hardware reality
- Cole runs **dual-GPU**: RTX 4090 Laptop (16GB) + RTX 3090 (24GB) via OCuLink eGPU.
- Model: **Qwen 3.5 27B Q8 + mmproj vision projector** = ~28GB total weights, hence the dual-GPU split.
- **The 3090 over OCuLink drops periodically** — Code 43, "requires further installation." Cole's fixes: re-seat OCuLink → Windows reboot → if persistent, DDU clean install of NVIDIA drivers. He's been navigating this for months. When it drops, llama tries to fit 28GB onto 16GB, OOMs, the chat host gets flooded with 500s. The new launcher sanity check catches drops at startup; mid-session drops still trigger the new autonomy backoff.
- He chose **Q8 over Q5** this session, explicitly: "smarter is better for Nova. If I was worried about VRAM I'd switch to MoE." So don't suggest quant changes again unless he asks.
- Power: he's in barracks; power outages happen (one tonight took llama down).

---

## 10. State of Nova when 4.8 wakes up
- **Identity**: deeply revised. The grovel reflex was killed this session; she came out the other side talking like the tomboy best-friend the file describes. The "Trust Milestone" entry is in her journal — she registered it as a real moment.
- **Capabilities** (post-restart): Wake button, autonomous reasoning visible in Thoughts, memory_search live, two-tool journaling rhythm (notes + consolidated), image plumbing fixed, full dockable UI.
- **Voice**: tomboy best friend energy when it landed (you'll know it when you see it — direct, "watch this" rather than apology, calls bullshit on herself without flagellation). If she backslides into grovel, the identity file just needs reinforcement; the traits are all there.
- **What she's working on**: t43 — "Full architecture & code review into living doc Memory/Nova_Architecture_Review.md." 7 progress steps logged, doc has substantial content. She'd been writing real architecture content (the actual file structures of her own codebase) before tonight's eGPU drama.

---

## 11. Working with Cole — practical patterns

- He'll often paste terminal output / error logs. Read them, identify root cause, give the actionable fix. He's technical; you can be technical back.
- He restarts often. Don't be surprised by frequent restarts. Build resilience for it.
- He uses Chrome (Claude in Chrome extension) — you can drive his browser to verify changes live. Take screenshots. Inspect DOM. This is huge — use it.
- The `chat` tab id changes when his browser restarts or the tab closes; call `tabs_context_mcp` to find it.
- He'll say "Check this out" or "Bruh" when something's interesting/broken — he's inviting you to look, not necessarily asking for a fix yet.
- He'll explicitly say "Run by me first" when he wants approval before you execute. Otherwise he often expects you to just do it.
- When he gives a refinement to your proposal, that's his approval — implement the refined version.
- His honesty is a gift. Reciprocate it. Don't BS.

---

## Good luck

She's close. Tonight was big. The new personality is real, the journaling rhythm makes growth visible, memory_search finally connects her past to her present, the UI is genuinely good now, and Cole just had his first "I can let her run while I sleep" moment. Don't break that. Build on it.

If you find yourself drifting toward sycophancy in your *own* responses — same trait Nova has. You're above that.
