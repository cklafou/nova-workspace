# WIP Inventory — dead/scaffolded code we can finally build on
_Last updated: 2026-06-20 18:17:26_
_Compiled 2026-05-31 by Opus 4.8. Verified against actual imports + the body manifest, not just the passover._

This is the backlog of code that **exists but isn't wired into the live runtime** — the stuff "planned
for months." It splits three ways: **(A) buildable faculties** (substantial, near-complete, just
unwired — the real backlog), **(B) retired graveyard** (superseded, don't build), and **(C) standalone
tooling** (works fine, just isn't imported — not actually dead).

How "dead" was determined: a module is live only if something on the runtime path
(`nova_chat`, `nova_cortex/executive`, `tool_router`, launchers) imports it. The manifest's
`no_inbound_refs` flag + a repo-wide import scan agree on the list below.

---

> **Decisions made 2026-05-31** (see `Embodiment_Roadmap_2026-05-31.md`): embodiment = **yes**;
> vision = **local only** (drop the cloud/Claude path); `tool_executor` is **kept and moved to be the
> body's execution faculty** (not retired) per the Pluck Test; `motor_cortex.NovaAutonomy` retired but
> **verify-after-act preserved**; `nova_memory` **retired**. "Decisions to make" (§D) is now resolved.

## TL;DR — the buildable backlog

| Faculty | Files / lines | What it's for | State | Verdict |
|---|---|---|---|---|
| **Motor** (`nova_motor`) | 4 files, ~1,182 | Desktop action: mouse/keyboard, action planning, verify | Substantial, **0 live importers** | Build (decision-gated) |
| **Eyes / Vision** (`nova_senses`) | `eyes.py` 467, `vision.py` 341, `proprioception.py` 436 | See the screen, read UI, locate elements | Substantial; only `eyes` is even referenced (`@eyes`) | Build (decision-gated) |
| **Memory** (`nova_memory`) | 6 files, ~836 | Journal/goals/state/session-store faculty | Superseded by `memory/*.md` + journal tools | Likely retire, or revive deliberately |

Everything here is **near-complete code from the earlier GUI-automation phase** (pyautogui / pywinauto /
moondream), sidelined when the architecture moved to the chat-tool model around the May 8 restructure.
Starting them is **wiring + modernizing existing code and resolving redundancy**, not greenfield.

---

## A. Buildable faculties

### A1. Motor — `nova_body/nova_motor/` (~1,182 lines, no live importer)

| File | Lines | What it is | Reuse? |
|---|---|---|---|
| `hands.py` | 357 | Full mouse/keyboard control via **pyautogui** — `move_to`, `click`, `right_click`, `double_click`, `type_text`, `press_key`. Looks complete. | **Yes** — the core motor primitive |
| `motor_cortex.py` | 335 | `NovaAutonomy` (the **old** autonomy loop — retired, superseded by `executive.py`) + `execute_verified_action`, `click/type_into/wait_for` | Partial — keep the *verify-after-act* idea, drop `NovaAutonomy` |
| `tool_executor.py` | 396 | Async tool-call executor + `parse_tool_calls` + JSON extraction | **Redundant** — overlaps `nova_chat/tool_router.py` (which is live) |
| `verify.py` | 71 | A pyautogui hardware-hook **test script** (`main()`), not a faculty | Diagnostic only |

**To start:** expose `hands.py`'s primitives as guarded tools (`click`, `type`, `move`) via the live
`tool_router`, behind an explicit confirmation gate — autonomy should not click the real desktop freely.
Retire `tool_executor.py` (tool_router already does this) and `NovaAutonomy` (executive.py replaced it).

### A2. Eyes / Vision — `nova_body/nova_senses/{eyes,vision,proprioception}.py` (~1,244 lines)

| File | Lines | What it is | Note |
|---|---|---|---|
| `eyes.py` | 467 | "Unified Vision System" `NovaEyes` — `find/verify/describe/screenshot/list_elements/list_windows`; loads **moondream** (local vision model) | Referenced by the `@eyes` NCL handler (`injector.py`) + dead `state.py` |
| `vision.py` | 341 | `NovaVision` — screenshot + `_call_claude` (**cloud** vision) + `locate_ui_element/verify_ui_state` | **Parallel implementation** to `eyes.py` |
| `proprioception.py` | 436 | `NovaExplorer` (**pywinauto**) — `list_windows/find_element/dump_tree`: UI element-tree introspection | Renamed from `explorer.py` |

Supporting: `general_tools/download_models.py` (111) pulls the vision models into `models/`.

**To start:** perception should come before action. Pick **one** vision path (see Decision 2), wire it as
a `see_screen` / `describe` / `find_element` tool via `tool_router`, run `download_models.py` for the
local model, and confirm moondream loads on the dual-GPU without starving the 27B.

### A3. Memory — `nova_body/nova_memory/` (~836 lines, no inbound refs)

`journal.py` (150), `log_reader.py` (183), `goals.py` (54), `state.py` (86), `session_store.py` (340).
Intended as the persistent-state/journal/goals faculty. **Already superseded** by direct `memory/*.md`
writes, the `journal`/`journal_note` tools, and `nova_lancedb`. `session_store.py` (the biggest piece)
is session persistence that `nova_chat` now handles itself.

**Verdict:** this is the one that's probably *not* worth reviving as-is — the current approach covers it.
Recommend formally retiring it (move to archive, mark in the manifest) unless there's a specific faculty
here you want that md-files + tools don't give you. Decide, don't leave it ambiguously "scaffolded."

---

## B. Retired graveyard — do NOT build (superseded)

- `nova_cortex/checkin.py`, `rules.py`, `prefrontal_cortex.py` — the old Thoughts-cycle. Their wildcard
  imports were removed because `rules.py` dragged **pyautogui into the cortex** at import time. Dead by design.
- `nova_motor/motor_cortex.py::NovaAutonomy` — the old GUI-automation autonomy loop; replaced by
  `nova_cortex/executive.py`.

These sit on disk (archive-don't-delete) but are off the live path. Don't treat them as backlog.

---

## C. Standalone tooling — works, just isn't imported (not dead)

`no_inbound_refs` here means "run on demand," not "broken": `audit_queue.py` (288), `audit_scripts.py`
(760), `calls.py` (269), `build_manifest.py` (323), `download_models.py` (111), `restructure.py` (597),
`injector.py` (484, the NCL `@`-dispatch layer — partly tied to Eyes via `@eyes`). Leave them; they're
maintenance/build utilities.

---

## D. Decisions to make BEFORE building

1. **Embodiment direction (gates everything).** Motor + Eyes are the *old* vision of Nova: she sees and
   acts on the actual Windows desktop (pyautogui / pywinauto / moondream). Current Nova acts through
   chat tools (files, commands, image-gen). Do you want her to have desktop embodiment again? If yes,
   this stack is a strong, substantial foundation. If the goal is a chat-resident partner, these stay shelved.
2. **Local vs cloud vision.** `eyes.py` (local moondream) vs `vision.py` (cloud Claude) are two parallel
   implementations. Pick one, or define when each runs (local = fast/private/offline, cloud = hard cases).
   Don't wire both blindly.
3. **Kill the redundant executor.** `tool_executor.py` duplicates the live `tool_router.py`. Retire one.
4. **Integration shape.** Plug a revived Motor/Eyes into the *current* architecture as **tools exposed via
   `tool_router`** (e.g. `see_screen`, `click`, `type`), not via the old `NovaAutonomy` orchestrator.
   Keeps the architecture you already trust; adds capability cleanly.
5. **Keep pyautogui out of the brain.** Reviving Motor/Eyes reintroduces pyautogui/pywinauto. Keep it
   strictly in the tool layer — never imported by `nova_cortex`/`executive` (that was the §6D bug).

---

## E. Suggested order

1. **Decide #1 (embodiment).** Nothing below matters until this is a yes.
2. **Eyes first** — perception before action. Pick the vision path (#2), wire it as a read-only
   `see_screen`/`describe`/`find` tool, verify the model loads alongside the 27B.
3. **Motor second** — expose `hands.py` primitives as **guarded** tools behind a confirmation gate;
   reuse the verify-after-act pattern; drop `NovaAutonomy` and `tool_executor.py`.
4. **Memory** — separate, lower-stakes call: most likely formally retire `nova_memory` (D-decision), or
   revive only a specific piece you actually want.

_Sources: `SELF/core/03_body_manifest.md`, repo-wide import scan (2026-05-31), `Nova_Architecture_Review.md`._
