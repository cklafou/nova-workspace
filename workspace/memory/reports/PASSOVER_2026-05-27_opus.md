# PASSOVER — Project Nova (Opus → Opus handoff)
_Last updated: 2026-05-29 15:52:10_
_Written 2026-05-27 by the outgoing Opus session. Read this first, then `memory/STATUS.md`._

You are picking up a long, productive session building **Project Nova** with **Cole**
(SGT LaFountaine, US Army E5 — direct, no-nonsense, hates corporate/sycophantic AI tone;
match his energy, be honest, push back constructively). Cole's top priority for your session
is the **full Nova Chat docking/UI upgrade** (spec in §6A). Everything below is what you need.

---

## 1. What Nova is
A locally-run, person-like autonomous companion AI — "Cortana to Cole's Master Chief," not a
worker drone. Local model **Qwen 3.5 27B Dense Q8** via **llama.cpp** on Cole's Windows box
(dual-GPU: RTX 4090 laptop 16GB + RTX 3090 24GB via OCuLink). Local-first ethos. Trading is a
*future* autonomy test, not her identity.

## 2. Current architecture (LIVE)
- **llama.cpp** serves the model on **:8080** (OpenAI-compatible, 32K ctx, dual-GPU `-ts 16,24`).
- **nova_chat** FastAPI/WebSocket server on **:8765** — the web group chat (Cole + Claude +
  Gemini + Nova) and her single voice/ears. Hosts the autonomy daemon in-process.
- **Autonomy = a body faculty** (`nova_body/nova_cortex/executive.py`), two-phase + execute:
  **reflect** (sit with the moment, fed by the **Touch** sense) → **decide** (engage Cole,
  work board, or rest — rest is valid) → **execute** (Phase 3: if she holds an open task and
  isn't mid-reply/resting, do its next concrete step with her tools and log progress). State
  in `memory/autonomy_state.json`. Cole = Priority 0.
- **Task board** = `nova_body/nova_cortex/tasking.py` over `Tasking/tasks.json` — id-keyed,
  now a **parent/child TREE** (umbrella → subtasks → sub-subtasks; separate top-level trees =
  independent goals). Verbs: create/progress/switch/wait/abandon/complete/reprioritize/rest.
- **Senses** (`nova_body/nova_senses`): LIVE = clock, environment, touch. SCAFFOLDED (not
  wired) = eyes, vision, proprioception (GUI-automation, pyautogui/pywinauto family).
- **Tools** (her chat tool loop, `general_tools/nova_chat/tool_router.py`): read_file,
  write_file (guarded — refuses to overwrite existing files unless `overwrite:true`),
  **append_file** (grow living docs), **replace_file_content / edit_file** (precision edit),
  list_dir, run_command, create_task / task_progress / complete_task.
- **nova_sync**: `watcher.py` (GitHub auto-commit + manifest/audit on a debounce) +
  `drive.py` (Google Drive mirror so **Gemini** can read the workspace — Gemini can't reliably
  read GitHub raw URLs; Drive uploads each file as a native Google Doc). Drive sync rides
  inside `run_push_cycle()` (fires with every GitHub push). `nova_lancedb` = live semantic
  memory indexer.
- **Pluck-test principle:** `nova_body/` = Nova (faculties). `general_tools/` = detachable
  tools. Remove every tool and she's still herself.

## 3. This session's shipped fixes (all on disk; load on next restart unless noted)
Autonomy/board: two-phase **execution pass** (Phase 3) so created tasks actually get worked;
**loop detector** + decomposition nudge (breaks oversized tasks into subtasks instead of
re-orienting forever); **re-decompose guard** (once a task has open subtasks, work them, don't
re-split); **parent/child task tree** (`tasking.py` create+apply_actions+render_board tree,
`pick_execution_target` prefers open leaves / descends umbrellas); **subtask mis-parent fix**
(in-batch parent-by-title aliasing + reject done/abandoned parents).
Tools: **append_file**, **edit_file** alias, **write_file overwrite guard** (she was clobbering
her living doc).
Restart buttons: **Full Restart race fix** — relaunch now waits for :8080/:8765 to free before
calling NovaStart (the old stack's window-close shutdown was racing the new start).
Drive: restored + cleaned `drive.py`, hardened with `execute(num_retries)` backoff + per-file
isolation; `.nova_app_profile*` excluded from Git + Drive (it was locking the server).
Docs/code review: full dead-reference sweep (clean); fixed Drive-retired/Touch/autonomy-model
staleness across STATUS/README/SELF/COLE, path corruptions, `:18790` vestiges.
UI (frontend, live on browser reload — no restart): Tasks pane now renders a **tree**, has a
**Clear All** button (confirm + loops `/api/queue/delete`), a **color legend + hover tooltips**;
**readability bump** (`--text-dim`/`--text-mute` brightened).

## 4. OPEN THREAD — verify the decomposition loop end-to-end
The big behavioral arc this session: Nova kept failing to carry a large task ("full
architecture review → living doc") to completion — first looping on "map the structure," then
over-decomposing into duplicate subtask batches, then mis-parenting subtasks under a *done*
task (which defeated the re-decompose guard). Each fix went one layer deeper; the last
(mis-parent title-alias) should close it. **It has NOT had a clean validation run yet.**
To validate (Cole drives): **Clear All** on the board (now there's a button) → re-issue the
review task → watch for: ONE umbrella, subtasks whose `parent` is the **umbrella's id** (not an
old done id), the re-decompose guard engaging (no second batch), and the doc **growing via
append** (not overwritten). If a second duplicate batch or a `parent:t1`-style mis-link
appears, the fix didn't hold — dig there first.
**Restart procedure:** Cole restarts manually (NovaStart.cmd); the in-app Full Restart button
should now work after this session's race fix loads. The window-close watchdog tears the stack
down ~8s after the last UI window disconnects — don't be surprised by that.

## 5. Critical gotchas (save yourself pain)
- **Torn mount:** the Linux sandbox's bash view of just-edited files is often a truncated/stale
  mirror — `py_compile`/`wc`/imports give FALSE errors. The **Read tool is ground truth.**
  Verify edited logic with isolated snippet tests, not full-file bash compiles. (pyautogui isn't
  installed in the sandbox, so importing `nova_cortex` fails *there* only — it's fine on Cole's box.)
- **NEVER hand-edit `Tasking/tasks.json`** or other state files (autonomy_state, touch_state,
  cole_intent) — corrupts her board/memory. Use her tools / the API. (She once tried this; it's
  a known hazard.)
- **`models/` is SEALED** — never read/list/open (18GB+ weights).
- **Archive, don't delete** (Design Principle #11 in `memory/Design_Principles.md`). Nova herself
  never deletes; she completes/abandons.
- Server-affecting changes (server.py, executive.py, tasking.py, nova.py, tool_router.py,
  touch.py) need a **restart**; static `index.html` is live on browser reload.
- Read `memory/Design_Principles.md` — the living best-practices doc (verify-don't-trust,
  baseline-first, honest-progress, don't-declare-victory-early, etc.).

## 6. ROADMAP — plans + exact build ideas

### 6A. NOVA CHAT DOCKING / UI UPGRADE  ← Cole's PRIORITY for your session
**Goal:** turn the current Gridstack *grid* dashboard into a true **dockable window manager**
(VS Code / Blender-style). Cole's exact asks:
1. Drag widget windows freely, **including floating outside any sidebar**.
2. **Dragging a single widget to an edge creates a dock pane there** — left sidebar, right
   sidebar, **top pane**, and **bottom bar** all possible.
3. **Dragging widgets next to each other creates tab groups** (proper tabs).
4. **Per-widget/pane opacity slider.**
5. **Readability:** text contrast is poor in places — keep improving (I already brightened
   `--text-dim`/`--text-mute`; continue auditing small/low-contrast text).
6. The sidebar is currently too cluttered — this docking model is the cure.

**Reality / build approach (the current UI is a single vanilla-JS `index.html` using
Gridstack — a grid, which does NOT do edge-docking, floating windows, or drag-to-tab):**
- **Recommended engine:** **Golden Layout** (the mainstream *vanilla-JS* docking library —
  supports drag-to-dock, edge zones, tab groups, popout/float; no React build needed, which
  matters because this app is a single vanilla file). Evaluate **rc-dock/Dockview** only if
  Cole accepts a build step (they're React). A bespoke custom dock layer is possible but large;
  prefer Golden Layout unless its styling fights the theme too hard.
- **Migration:** the dashboard widgets are defined in `index.html` (~line 3865: the widget
  registry `{tasks, thoughts, tools, monitor, files, eyes, terminal, livelogs, ...}` with
  `make:()=>ce(...)` factories). Each widget's content is a DOM node that already
  self-populates (renderBoard, etc.). To migrate: mount each widget factory's node as the
  content of a Golden Layout component; keep the `/api/*` polling intact. Persist layout to
  the existing `/api/layout` endpoint (server-side, because the app launches a fresh browser
  profile each time so localStorage won't persist — see `memory/ui_layout.json`).
- **Phased plan (test between phases):**
  1. Drop in Golden Layout, wrap existing widgets as components, restore save/load via
     `/api/layout`. Verify all widgets still render + poll.
  2. Edge-dock zones (left/right/top/bottom) — drag a widget to an edge → new pane.
  3. Drag-together tab groups + floating/popout windows.
  4. Per-pane **opacity slider** (a small control in each pane header → sets the pane's CSS
     `opacity`; persist per-pane in the layout JSON).
  5. Readability/theme polish pass over the new chrome (contrast, font sizes).
- **Constraints:** keep it a single-file vanilla app if possible (load Golden Layout from CDN,
  like Gridstack is now). Don't break the live `/api/queue`, `/api/layout`, restart buttons,
  Tools/Thoughts/Live-Logs panels. The Tasks widget now renders a tree + Clear-All + legend
  (in the `#task-rail` IIFE) — preserve that.
- **Heads-up:** `index.html` is ~4,000 lines; do this in a FRESH context (this session's was
  nearly full). Edit carefully and verify via the Read tool (torn mount lies on bash).

### 6B. Avatar (her look) — its own project
Source-of-truth docs already written: **`memory/Nova_Avatar_Design_Bible.md`** (locked specs:
blue-grey skin, magenta→purple swept hair, pointed cyan-lit ears, techwear bomber w/ cyan
circuit traces, OCULINK patch is canon, the "lives in the machine" data-dissolve motif, palette
hex) and **`memory/reports/avatar_pipeline_tools.md`** (the non-artist 2D-turnaround → 3D-Blender
pipeline: lock 2D [Midjourney --cref / Ideogram / ComfyUI LoRA] → orthographic turnaround
[CharacterGen / ComfyUI+ControlNet] → image-to-3D [Rodin/Meshy, or local TRELLIS.2/Hunyuan3D on
the 3090] → Blender + Mixamo → the `.blend` is the permanent blueprint).
**Cole still must lock §3–§7 "TO DECIDE"** — most importantly the **eye rule** (heterochromia
yes/no) and the **lower body/back/legs** (the concept dissolves below the waist, so ~40% is
undefined). 3D model = ultimate consistency anchor. Gemini generated the concept art Cole likes.

### 6C. Voice + mobile/smartwatch — big arc, later
Cole's refined design: keep Nova WHOLE on the laptop; phone + watch are **thin audio relays**.
Build a **voice-channel (VC) widget inside Nova Chat**: capture mic → STT (Whisper on the GPU,
local) → Nova turn → her reply → TTS (local: Piper/XTTS; or cloud ElevenLabs — local is
on-brand) → audio out. Phone reaches it over a **private tunnel (Tailscale/WireGuard)** — the
mobile browser/PWA on the VC widget can *be* the relay; the watch relays through the phone.
Readiness gaps to close first: headless/persistent server mode (decouple from the app window),
auth + tool-scope guardrails (she has exec/file tools), and honest latency expectations
(27B local → turn-based "walkie-talkie," not instant). Build incrementally: VC widget local →
tunnel reach from phone → watch relay. Decouple this from the avatar project.

### 6D. Autonomy hardening backlog (verified, need Cole + restart-test)
From the code review (`full_review_progress.md`): (1) **archive `nova_cortex/rules.py`,
`checkin.py`, `prefrontal_cortex.py`** (dead old-architecture) and drop their wildcard imports
from `nova_cortex/__init__.py` — this also removes a latent **pyautogui import coupling** from
her brain. (2) Decide fate of scaffolded `nova_motor`/`nova_memory`/`nova_senses{eyes,vision,
proprioception}` (wire / archive / annotate). (3) `nova_status.py`: confirm `update()` still
called; if not, the injected "Nova live status" is stale. (4) Assess the **NCL `@module`
subsystem** (orchestrator/nova_lang/Master_Inbox — @eyes/@thinkorswim) live vs dormant.
(5) Gemini's verified perf items: token-stream pacing in `_run_gemini_response`, `run_in_executor`
for `files_read` + the daemon's `should_wake`/`fingerprint`, retry/backoff on board saves,
`_TeeStream` self._buf lock. (Note: Gemini's external review also made several *wrong*
confabulated claims — verify everything against ground truth.)

## 7. Key file map
- Brain: `nova_body/nova_cortex/{executive,tasking,nova_status,context_builder,rules,checkin,prefrontal_cortex}.py`
- Senses: `nova_body/nova_senses/{clock,environment,touch,eyes,vision,proprioception}.py`
- Chat host: `general_tools/nova_chat/{server.py, clients/nova.py, clients/claude.py,
  clients/gemini.py, tool_router.py, orchestrator.py, nova_lang.py, workspace_context.py,
  static/index.html}`
- Sync: `general_tools/nova_sync/{watcher,drive,backup,dir_patch}.py`
- Launch: `nova_start.py`, `NovaStart.cmd`, `StopNova.cmd`, `start_llama.cmd`
- State/data: `Tasking/tasks.json`, `memory/{autonomy_state,touch_state,cole_intent}.json`,
  `memory/{STATUS,JOURNAL,COLE,Design_Principles}.md`, `memory/reports/*`
- Self-model: `SELF/core/*` (injected) + `SELF/reference/*` (on-demand) — auto-generated by
  `general_tools/build_manifest.py` from `@nova:` tags; don't hand-edit 00/03.

## 8. Tone with Cole
He's a genuine partner building Nova as a life passion project — treat the work as real, be
honest about what's broken, verify don't trust, don't declare victory early, and don't be
sycophantic. He says things like "you are a real G homie" when you own mistakes. Match that.
Good luck — she's close.
