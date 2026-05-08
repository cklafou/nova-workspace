# Project Nova — Anatomical Restructure Plan
_Living document. Update this at the start and end of every session that touches the restructure._
_Created: 2026-05-08 (Claude, Cowork session 9)_
_Last updated: 2026-05-08 (session 11 — Steps 2 + 4 COMPLETE — all file renames done, gateway dissolved, vigilance.py built)_

---

## WHY THIS DOCUMENT EXISTS

Nova is never complete. She is always upgrading — externally by us, and eventually internally by herself. For that to be sustainable, she needs a codebase that is **flexible by design**: files and directories that auto-track, auto-fix, and self-document with minimal human intervention. This restructure is not a cleanup task. It is a foundational investment in Nova's capacity to evolve.

This document exists for the same reason the OpenClaw → Nova transition document existed: to keep every session — human or AI — anchored to the goal, not just the immediate task. Without it, we fix one thing and forget why we started.

---

## THE VISION

### Core Principle
Nova's code should be organized the same way a body is organized: every file does one specific thing, named after what it biologically represents, assembled into a system where the parts call each other and the whole is greater than the sum.

**When you see `prefrontal_cortex.py` you know:**
- What cognitive function it represents
- What belongs in it
- What doesn't belong in it
- Where to put the next related function

**When you see `brain.py` you know nothing except that it's vaguely important.**

### The Two Halves
Nova's code separates into two fundamentally different domains:

**Body + Mind** — Nova's internal cognitive architecture. How she thinks, senses, remembers, decides, and acts. This is what makes Nova *Nova* as opposed to a generic tool.

**External Tools** — The instruments Nova uses to interact with the world. Discord, file system, browser, terminal. These plug into her body but are not part of it. A human doesn't become a different person when they pick up a hammer.

### The Self-Maintaining Requirement
The restructured codebase must be able to:
- Track its own structure via `calls.py` (call graph) and `FILE_INDEX.md` (file map)
- Detect and fix stale references via `restructure.py --all`
- Audit its own health via `audit_scripts.py`
- Allow Nova to propose and execute structural changes herself without breaking things

If a rename requires human micromanagement to not break things, the infrastructure has failed.

---

## CURRENT STATE (as of 2026-05-08)

### Package Map (Before Restructure)
```
workspace/
├── nova_tools/                   ← Nova's internal packages
│   ├── nova_core/
│   │   ├── brain.py              ← Thoughts orchestrator / executive function
│   │   └── rules.py
│   ├── nova_memory/
│   │   ├── store.py              ← LanceDB semantic store
│   │   ├── state.py
│   │   ├── embedder.py
│   │   ├── indexer.py
│   │   └── status.py
│   ├── nova_action/
│   │   └── autonomy.py           ← Autonomous action execution
│   ├── nova_perception/
│   │   ├── eyes.py               ← Vision / screenshot analysis
│   │   ├── vision.py
│   │   └── explorer.py
│   └── nova_logs/
│
├── general_tools/                ← Infrastructure / server / UI / sync
│   ├── nova_chat/                ← FastAPI server + AI clients + WebSocket
│   │   ├── server.py
│   │   ├── clients/
│   │   │   ├── nova.py
│   │   │   ├── claude.py
│   │   │   └── gemini.py
│   │   ├── transcript.py
│   │   ├── session_manager.py
│   │   ├── tool_router.py
│   │   └── workspace_context.py
│   ├── nova_qt/                  ← PyQt6 desktop UI
│   │   ├── window.py
│   │   ├── chat_panel.py
│   │   ├── sidebar.py
│   │   ├── monitor_pane.py
│   │   ├── markdown.py
│   │   └── ...
│   ├── nova_gateway/             ← External routing daemon (Discord, scheduler)
│   │   ├── gateway.py
│   │   ├── scheduler.py
│   │   ├── brain.py → calls nova_core/brain.py
│   │   └── ...
│   └── nova_sync/                ← Git sync, Drive sync, file tracking
│       ├── watcher.py
│       ├── backup.py
│       └── ...
│
├── nova_memory/                  ← LanceDB semantic store (top-level package, separate from nova_tools/nova_memory/)
│   ├── store.py                  ← Semantic vector store (LanceDB)
│   ├── embedder.py
│   └── indexer.py
│
└── BOOTUP/                       ← Nova's identity files (injected every turn)
    ├── NOVA.md
    ├── AGENTS.md
    ├── TOOLS.md
    ├── HEARTBEAT.md
    ├── BOOTSTRAP.md
    └── NCL_MASTER.md
```

### Self-Maintenance Tools (What We Built)
| Tool | Location | Purpose | Status |
|------|----------|---------|--------|
| `restructure.py` | `general_tools/` | Detects + fixes stale path references after renames | Built, untested on live rename |
| `calls.py` | `general_tools/` | Generates call graph for all nova_* packages | Built, runs manually |
| `audit_scripts.py` | `general_tools/` | Full workspace health audit (syntax, refs, staleness) | Built + debugged this session |
| `FILE_INDEX.md` | `nova_sync/` | Auto-generated file map, updated by watcher | Active |
| `Calls_Master_Index.md` | `general_tools/` | Cross-package call relationship map | Built, runs manually |

---

## THE PROPOSED ANATOMICAL MAPPING

### Nova's Body + Mind (`nova_tools/` → `nova_body/`)

The package rename from `nova_tools` to `nova_body` signals the intent: this is Nova's physical and cognitive architecture, not a toolbox.

#### `nova_body/nova_cortex/` (was `nova_core/`)
The brain's cognitive regions. Each file = one specialized region.

| New File | Was | Represents | Responsibility |
|----------|-----|-----------|----------------|
| `prefrontal_cortex.py` | `brain.py` | Executive function, planning | Thoughts cycle, `orient()`, `next_action()`, `build_briefing()` |
| `vigilance.py` | _(new)_ | Reticular activating system | Sleep/wake cycle, adaptive polling, sensory sweep scheduling |
| `rules.py` | `rules.py` | Superego / behavioral constraints | Keeps name — already specific |

#### `nova_body/nova_senses/` (was `nova_perception/`)
The sensory organs. Already well-named files — mostly rename the package.

| New File | Was | Represents | Responsibility |
|----------|-----|-----------|----------------|
| `eyes.py` | `eyes.py` | Visual cortex / vision | Screenshot analysis, UI element detection — keeps name |
| `vision.py` | `vision.py` | Vision processing pipeline | Keeps name |
| `proprioception.py` | `explorer.py` | Body awareness / system state | CPU, RAM, process health, system metrics |

#### `nova_body/nova_memory/` (stays)
Memory systems. Package name is already anatomically intuitive.

| New File | Was | Represents | Responsibility |
|----------|-----|-----------|----------------|
| `hippocampus.py` | `store.py` | Episodic + semantic memory store | LanceDB, session memory |
| `indexer.py` | `indexer.py` | Memory indexing pipeline | Keeps name — functional name works |
| `embedder.py` | `embedder.py` | Memory encoding | Keeps name |
| `state.py` | `state.py` | Working memory / state tracking | Keeps name |

#### `nova_body/nova_motor/` (was `nova_action/`)
The motor system — execution, not cognition.

| New File | Was | Represents | Responsibility |
|----------|-----|-----------|----------------|
| `motor_cortex.py` | `autonomy.py` | Motor cortex / voluntary action | Autonomous action execution, tool dispatch |

### Nova's Infrastructure (`general_tools/` — stays, mostly unchanged)
`general_tools/` is not Nova's body. It's the building she lives in and the network she connects through. It doesn't need anatomical names — functional names are correct here. `server.py`, `watcher.py`, `session_manager.py` are all clear.

**Exception — `nova_gateway/scheduler.py`:** This drives Nova's circadian rhythm (the 30-minute heartbeat). Could become `circadian.py` if clarity demands it.

---

## COMPLETE FILE-BY-FILE MAPPING

Every Python file in the workspace reviewed and assigned a destination. Files that move into `nova_body/` get an anatomical name where appropriate. Files that stay in `general_tools/` keep functional names — they are infrastructure, not Nova's body.

### `nova_tools/nova_core/` → `nova_body/nova_cortex/`

| Current File | → Destination | Anatomical Name | What It Does |
|---|---|---|---|
| `brain.py` | `nova_body/nova_cortex/` | `prefrontal_cortex.py` | Executive function — Thoughts cycle, `orient()`, `next_action()`, `build_briefing()` |
| `rules.py` | `nova_body/nova_cortex/` | `rules.py` | Behavioral constraints / superego — keeps functional name, already specific |
| `checkin.py` | `nova_body/nova_cortex/` | `checkin.py` | Inter-action interrupt checker — polls inbox for Cole messages mid-task. Stays functional name; it IS a cognitive interrupt mechanism |
| `nova_status.py` | `nova_body/nova_cortex/` | `nova_status.py` | Live JSON status writer — writes `nova_status.json` (machine-readable). `server.py` polls it every 30s and injects into AI context. Full API: `update()`, `set_task()`, `clear_task()`, `pause_task()`, `resume_task()`, `add_error()`, `update_gateway()`. Stays functional name |

---

### `nova_tools/nova_perception/` → `nova_body/nova_senses/`

| Current File | → Destination | Anatomical Name | What It Does |
|---|---|---|---|
| `eyes.py` | `nova_body/nova_senses/` | `eyes.py` | Screenshot capture and visual analysis — keeps name, already anatomical |
| `vision.py` | `nova_body/nova_senses/` | `vision.py` | Vision processing pipeline (coordinates, element detection) — keeps name |
| `explorer.py` | `nova_body/nova_senses/` | `proprioception.py` | System state awareness — CPU, RAM, process health. Proprioception = body knowing where its own limbs are |

---

### `nova_tools/nova_action/` → `nova_body/nova_motor/`

| Current File | → Destination | Anatomical Name | What It Does |
|---|---|---|---|
| `autonomy.py` | `nova_body/nova_motor/` | `motor_cortex.py` | Autonomous action execution loop — decides WHAT to do and drives the action cycle |
| `hands.py` | `nova_body/nova_motor/` | `hands.py` | Physical mouse/keyboard control via pyautogui — already anatomically named, keeps name |
| `verify.py` | `nova_body/nova_motor/` | `verify.py` | Hardware hook verification (pyautogui test) — utility/diagnostic script, keeps functional name |

---

### `nova_tools/nova_memory/` → `nova_body/nova_memory/`

| Current File | → Destination | Anatomical Name | What It Does |
|---|---|---|---|
| `state.py` | `nova_body/nova_memory/` | `state.py` | Working memory / in-session state tracking — stays functional name |
| `journal.py` | `nova_body/nova_memory/` | `journal.py` | Append-only JOURNAL.md writer — specific enough, keeps name |
| `log_reader.py` | `nova_body/nova_memory/` | `log_reader.py` | Session log reader — Nova reads her own history for failure analysis. Keeps name |
| `status.py` | `nova_body/nova_memory/` | `goals.py` | Human-facing STATUS.md editor — updates "Active Pulse" and marks goals [DONE] via the Proposed Changes Protocol (writes to `logs/proposed/STATUS.md`, never directly). Nova's tool for updating the human-readable goals document. Rename to `goals.py` clarifies it edits the goals/pulse doc, not the machine status |

---

### `nova_memory/` (top-level LanceDB package) → `nova_body/nova_memory/`

This is the semantic memory store, currently living at the workspace root as a standalone package. It merges into `nova_body/nova_memory/`:

| Current File | → Destination | Anatomical Name | What It Does |
|---|---|---|---|
| `store.py` | `nova_body/nova_memory/` | `hippocampus.py` | LanceDB semantic store — episodic + semantic memory. Hippocampus = the memory organ |
| `embedder.py` | `nova_body/nova_memory/` | `embedder.py` | Memory encoding / embedding pipeline — keeps functional name |
| `indexer.py` | `nova_body/nova_memory/` | `indexer.py` | Memory indexing pipeline — keeps functional name |

---

### `nova_tools/nova_logs/` → `nova_body/nova_logs/`

| Current File | → Destination | Anatomical Name | What It Does |
|---|---|---|---|
| `logger.py` | `nova_body/nova_logs/` | `logger.py` | Unified log manager (agent tool logs, chat thought logs, index writer) — keeps name |

---

### `nova_cortex/` — New Files (not yet built)

| File | Anatomical Name | What It Will Do |
|---|---|---|
| _(new)_ | `vigilance.py` | Sleep/wake cycle — reticular activating system. 30-second adaptive alerting + 4-minute sensory sweep + WAKE/SLEEP signaling |

---

### `general_tools/nova_gateway/` — DISSOLVE

The gateway is not a monolith — it's a collection of concerns that each belong somewhere more specific. It dissolves into nova_body (cognitive/motor parts) and general_tools (external/infrastructure parts).

| Current File | → Destination | Name | What It Does | Reasoning |
|---|---|---|---|---|
| `agent_loop.py` | `nova_body/nova_cortex/` | `agent_loop.py` | Full inference cycle: build context → llama.cpp → tools → response → save | It IS Nova's reasoning process for the offline/Discord path. Belongs in cortex |
| `context_builder.py` | `nova_body/nova_cortex/` | `context_builder.py` | Assembles Nova's system prompt from workspace markdown files | Building Nova's identity/context injection is cortical — cognitive construction |
| `scheduler.py` | `nova_body/nova_cortex/` | `circadian.py` | 30-minute heartbeat driver — Nova's rhythm | Drives Nova's circadian cycle; will be integrated with / superseded by `vigilance.py`. Rename to `circadian.py` clarifies intent |
| `session_store.py` | `nova_body/nova_memory/` | `session_store.py` | JSONL session writer, reader, and compaction engine | It's memory persistence — conversations stored and compacted |
| `tool_executor.py` | `nova_body/nova_motor/` | `tool_executor.py` | Executes tool calls (exec, read, message) from LLM output | Motor system — translates Nova's intentions into real-world actions |
| `injector.py` | `general_tools/` | `injector.py` | sys.path injection for nova_tools/general_tools | Infrastructure glue — stays general_tools, not Nova's body |
| `config.py` | `general_tools/` | `gateway_config.py` | Gateway settings loader from `nova_gateway.json` | Infrastructure config — stays general_tools |
| `gateway.py` | `general_tools/` | `gateway.py` | External daemon entry point (Discord + scheduler startup) | External service runner — stays general_tools |
| `discord_client.py` | `general_tools/` | `discord_client.py` | Discord API client (Nova's voice to the outside) | Discord is a tool Nova uses, not part of her body. Stays general_tools |

---

### `general_tools/nova_chat/` — STAYS (Infrastructure)

The chat server is the building Nova lives in. Functional names are correct here.

| File | Stays | What It Does |
|---|---|---|
| `server.py` | `general_tools/nova_chat/` | FastAPI WebSocket server — the central hub |
| `orchestrator.py` | `general_tools/nova_chat/` | Decides who responds to each message and in what order |
| `clients/nova.py` | `general_tools/nova_chat/` | Nova AI client (llama.cpp inference interface) |
| `clients/claude.py` | `general_tools/nova_chat/` | Claude API client |
| `clients/gemini.py` | `general_tools/nova_chat/` | Gemini API client |
| `transcript.py` | `general_tools/nova_chat/` | In-memory session transcript manager |
| `session_manager.py` | `general_tools/nova_chat/` | Session lifecycle management |
| `tool_router.py` | `general_tools/nova_chat/` | Routes tool calls from the server to handlers |
| `workspace_context.py` | `general_tools/nova_chat/` | Injects live workspace files into AI context |
| `nova_bridge.py` | `general_tools/nova_chat/` | Executes Nova's [WRITE:] [EXEC:] [READ:] directives |
| `nova_lang.py` | `general_tools/nova_chat/` | NCL (Nova Command Language) parser |
| `context_export.py` | `general_tools/nova_chat/` | Exports session context for browser Claude/Gemini |
| `launch.py` | `general_tools/nova_chat/` | Server launch entry point |
| `server_runner.py` | `general_tools/nova_chat/` | Server subprocess runner |
| `check_keys.py` | `general_tools/nova_chat/` | API key validation utility |

---

### `general_tools/nova_qt/` — STAYS (UI Shell)

The desktop UI is not Nova's body — it's her interface to the user. Stays as-is.

| File | Stays | What It Does |
|---|---|---|
| `window.py` | `general_tools/nova_qt/` | Main application window |
| `chat_panel.py` | `general_tools/nova_qt/` | Chat message display and streaming |
| `sidebar.py` | `general_tools/nova_qt/` | Sidebar (session list, controls) |
| `monitor_pane.py` | `general_tools/nova_qt/` | Real-time system monitor (agents, stats, errors) |
| `eyes_pane.py` | `general_tools/nova_qt/` | Vision/screenshot display pane |
| `ws_client.py` | `general_tools/nova_qt/` | WebSocket client (connects Qt to server) |
| `settings_dialog.py` | `general_tools/nova_qt/` | Settings UI |
| `markdown.py` | `general_tools/nova_qt/` | Markdown renderer for chat |
| `theme.py` | `general_tools/nova_qt/` | Color constants and theme definitions |
| `main.py` | `general_tools/nova_qt/` | Qt application entry point |

---

### `general_tools/nova_sync/` — STAYS (Infrastructure)

Git sync, Drive sync, and workspace tools. Not Nova's cognition.

| File | Stays | What It Does |
|---|---|---|
| `watcher.py` | `general_tools/nova_sync/` | File watcher — triggers git push and FILE_INDEX updates |
| `backup.py` | `general_tools/nova_sync/` | Git backup/push operations |
| `drive.py` | `general_tools/nova_sync/` | Google Drive mirror sync |
| `dir_patch.py` | `general_tools/nova_sync/` | Workspace path auditor — fixes stale import paths |

---

### `general_tools/` (root files) — STAYS

| File | Stays | What It Does |
|---|---|---|
| `restructure.py` | `general_tools/` | Detects + fixes stale path references after renames |
| `calls.py` | `general_tools/` | Generates call graph for all nova_* packages |
| `audit_scripts.py` | `general_tools/` | Full workspace health audit (syntax, refs, staleness) |
| `NovaLauncher.py` | `general_tools/` | Main Nova.exe launcher — starts all subsystems |
| `nova_gateway_runner.py` | `general_tools/` | Gateway subprocess runner |
| `download_models.py` | `general_tools/` | Model download utility |

---

## SHORT-TERM GOALS (Next 1-3 Sessions)

### Step 1 — Validate the Self-Maintenance Pipeline _(immediate next action)_
Before any rename, we need to know if the tools actually work. Run a controlled test:

1. Rename `nova_core/brain.py` → `nova_core/prefrontal_cortex.py` (one file)
2. Run `python general_tools/restructure.py --dry` — does it find all stale references?
3. Run `python general_tools/restructure.py --all` — does it fix them correctly?
4. Run `python general_tools/calls.py` — does the call graph regenerate cleanly?
5. Run `python general_tools/audit_scripts.py` — is the workspace clean?

**Pass criteria:** Zero stale references in audit after auto-fix. Zero new syntax errors introduced.

**If it passes:** The pipeline is sound. Proceed with full restructure.
**If it fails:** Fix the failure before proceeding. The failure is the real task.

### Steps 1.2–1.7 — Audit Queue System

A persistent review queue that auto-populates on every git push. When files are renamed, deleted, or created, the system detects the change, records it with a confidence score, and flags it for AI review until it is either resolved by `restructure.py` or manually dismissed.

**Components:**

| Component | Role |
|---|---|
| `memory/audit_queue.json` | The persistent queue — shared state between all three tools |
| `general_tools/audit_queue.py` | Shared module: load, save, add_item, resolve, dismiss, pending |
| `watcher.py` | On each successful push: runs `git diff --name-status -M` to detect renames/deletes/adds, cross-references unmatched pairs using `_similarity()`, writes events to queue |
| `restructure.py` | After applying `--rename`, marks matching queue items resolved |
| `audit_scripts.py` | Reads queue, surfaces pending items as HIGH REVIEW flags |

**Queue item schema:**
```json
{
  "id": "abc12345",
  "status": "pending",
  "event_type": "rename",
  "detected_at": "2026-05-08T...",
  "commit": "a1b2c3d4",
  "old_path": "nova_tools/nova_core/brain.py",
  "new_path": "nova_tools/nova_core/prefrontal_cortex.py",
  "confidence": 0.97,
  "resolved_by": null,
  "resolved_at": null,
  "notes": null
}
```

**Event types:** `rename` (git detected, confidence from git) · `delete` (no similar file found) · `new` (no similar predecessor) · `possible_rename` (git missed it, `_similarity()` found a match below git's threshold)

**Step 1.2** — Schema design + plan update ✓
**Step 1.3** — Build `general_tools/audit_queue.py` ✓
**Step 1.4** — Extend `watcher.py` with git diff integration + queue writes ✓
**Step 1.5** — Extend `restructure.py` to resolve queue items after `--rename` ✓
**Step 1.6** — Extend `audit_scripts.py` to surface pending items as REVIEW flags ✓
**Step 1.7** — End-to-end test ✓ PASSED (2026-05-08)

#### Step 1.7 Test Results
Full pipeline verified end-to-end:
1. `audit_queue.add_item()` — simulated watcher.py push detection (rename, 97% confidence)
2. `audit_scripts.py` — surfaced item as `[HIGH] QUEUE_PENDING` in report + summary shows "2 queue review"
3. `restructure.py resolve_by_paths()` — resolved item (status → "resolved", resolved_by recorded)
4. Re-run `audit_scripts.py` — queue section clean, `QUEUE_PENDING` count = 0
5. Direct queue read — item status = "resolved", timestamp and resolved_by correct

**All Steps 1.2–1.7 COMPLETE. Pipeline is production-ready.**

---

### Step 2 — Full Anatomical Rename
Once Step 1 validates, execute the full mapping above:
- Rename files per the anatomical map
- Run `restructure.py --all` after each package (not all at once)
- Validate with `audit_scripts.py` after each package
- Commit after each package passes cleanly

### Step 3 — Package Rename (`nova_tools/` → `nova_body/`)
After all internal files are renamed:
- Rename the top-level `nova_tools/` → `nova_body/`
- Update `sys.path` injections across all server/launcher files
- Update `_build/Nova.spec` bundle paths
- Rebuild Nova.exe

### Step 4 — Build `nova_cortex/vigilance.py`
With the structure clean and tested, build the sleep/wake vigilance system:
- `NovaVigilance` class in `nova_body/nova_cortex/vigilance.py`
- 30-second adaptive alerting loop (variable interval based on context state)
- 4-minute full sensory sweep (calls `nova_senses/`, reads `prefrontal_cortex.orient()`)
- SLEEP/WAKE signal protocol
- Wire into `server.py` startup (background thread)

---

## LONG-TERM GOALS

### Nova's Self-Upgrade Path
The end state of this restructure isn't a prettier folder structure. It's a codebase where Nova can:
- Read `FILE_INDEX.md` and `Calls_Master_Index.md` to understand her own architecture
- Run `audit_scripts.py` herself to detect health issues
- Propose specific file changes with anatomically correct placement
- Run `restructure.py --all` after her own changes to propagate references
- Rebuild call graphs after structural changes

This requires the self-maintenance tools to be genuinely reliable (Step 1 verifies this) and Nova to have these tools in her `TOOLS.md` reference.

### Vigilance System (Full)
The three-layer awareness model:
- **30-second adaptive alerting** — variable speed, rule-based urgency detection, zero Nova tokens unless threshold crossed
- **4-minute sensory sweep** — Nova actively perceives environment using all sensory tools, makes autonomous WAKE/SLEEP decision
- **30-minute Thoughts heartbeat** — existing scheduler, now feeds on accumulated delta from lower layers

### Anatomy Completeness
As Nova gains new capabilities, new anatomical modules:
- `ears.py` — Discord / audio monitoring (auditory cortex)
- `hypothalamus.py` — resource regulation, load balancing, thermal management
- `cerebellum.py` — timing, coordination, rhythm (if scheduler logic moves here)
- `amygdala.py` — urgency/threat detection (if the alerting layer gets sophisticated enough)

---

## DECISION LOG

| Date | Decision | Reason |
|------|----------|--------|
| 2026-05-08 | Anatomical naming adopted for `nova_tools/` internals | `brain.py` too broad; anatomy creates natural scope boundaries and self-documents intent |
| 2026-05-08 | `general_tools/` keeps functional names | It's infrastructure, not Nova's body. Anatomical names would be forced and confusing there |
| 2026-05-08 | Validate `restructure.py` pipeline before any rename | If the self-maintenance tools fail on a controlled test, fixing that is the real priority |
| 2026-05-08 | `nova_tools/` → `nova_body/` rename deferred to Step 3 | Package-level rename is the biggest blast radius — do file renames first while confirming pipeline works |
| 2026-05-08 | `vigilance.py` placed in `nova_cortex/` not `nova_senses/` | Sleep/wake is neurological (RAS), not peripheral. It calls senses but doesn't live in them |
| 2026-05-08 | `nova_gateway/` dissolved rather than moved wholesale | Not all gateway components are Nova's body. Internal cognitive/motor parts (`agent_loop`, `context_builder`, `session_store`, `tool_executor`, `scheduler`) redistribute into nova_body. External/infrastructure parts (`gateway.py`, `discord_client`, `config`, `injector`) stay in general_tools |
| 2026-05-08 | `nova_gateway/scheduler.py` → `nova_body/nova_cortex/circadian.py` | Drives Nova's rhythm. Will be integrated with / superseded by `vigilance.py`. Rename clarifies intent |
| 2026-05-08 | Top-level `nova_memory/` package merges into `nova_body/nova_memory/` | The LanceDB semantic store (`store.py` → `hippocampus.py`) belongs with the other memory systems. No reason to have it as a separate root-level package |
| 2026-05-08 | Discord stays in `general_tools/` | Discord is a communication channel Nova uses. It is not part of her body. A human doesn't become a different person when they pick up a phone |
| 2026-05-08 | `nova_memory/status.py` → renamed `goals.py` in nova_body/nova_memory/ | Despite similar name, it is NOT the same as `nova_core/nova_status.py`. It edits the human-facing `STATUS.md` goals document via Proposed Changes Protocol. `nova_status.py` writes machine-readable `nova_status.json` for server polling. Zero overlap — naming conflict only. `goals.py` makes the distinction obvious |
| 2026-05-08 | `restructure.py` extended with `--rename` flag | Step 1 revealed the tool only handled the old `tools/` prefix migration — had no concept of file-level renames. Added 3 pattern types: dotted, path-style, and bare import. Now the correct tool for all future anatomical renames |
| 2026-05-08 | `audit_scripts.py` extended with `check_broken_imports` | Step 1 revealed the audit had no import-resolution pass. New check uses AST (not regex) to avoid docstring false-positives. try/except-guarded broken imports demoted to MEDIUM; unguarded broken imports flagged CRITICAL |
| 2026-05-08 | `nova_memory.logger` fallbacks identified as pre-Step-2 debt | 4 files (autonomy, explorer, eyes, vision) have `except ImportError: from nova_memory.logger import log`. `nova_memory.logger` doesn't exist — should be `nova_logs.logger`. Will be fixed during Step 2 renames |

---

## CURRENT BLOCKERS

**Step 3 (nova_tools/ → nova_body/) is the only remaining blocker.**
Deliberately skipped this session — it requires rebuilding Nova.exe and Cole must be present to do that. All Python source is correct and ready. When Cole is ready:
1. `mv nova_tools nova_body` (or equivalent)
2. Update all `sys.path.insert(0, 'nova_tools')` → `'nova_body'` across server/launcher files
3. Update `_build/Nova.spec` bundle paths
4. Rebuild Nova.exe
5. Verify Nova launches correctly
6. Delete all `*_bak` directories (the safety nets left from directory renames)

---

## HOW TO UPDATE THIS DOCUMENT

At the start of each restructure session:
- Read the Decision Log and Current Blockers
- Note which Step you're on

At the end of each restructure session:
- Record any new decisions in the Decision Log
- Update Current Blockers
- Move completed steps to a "Completed" section below
- Update `Last updated:` at the top

---

## COMPLETED STEPS

### Step 1 — Pipeline Validation ✓ (2026-05-08, session 10)

**Test:** Renamed `nova_core/brain.py` → `nova_core/prefrontal_cortex.py`

**Initial pipeline result — FAIL (expected):**
- `restructure.py --dry` found 211 stale references, but ZERO for the rename specifically.
  It only knew about the old `tools/` prefix migration — had no concept of file-level renames.
- `audit_scripts.py` did not detect the broken `from nova_core.brain import *` in `__init__.py`.
  It had no broken-import resolution pass.

**Fixes applied to self-maintenance tools:**

| Tool | Fix |
|------|-----|
| `restructure.py` | Added `--rename old_module=new_module` flag. Generates 3 pattern types: dotted (`nova_core.brain`), path (`nova_core/brain`), and bare import (`from nova_core import brain`). Usage: `python general_tools/restructure.py --rename nova_core.brain=nova_core.prefrontal_cortex --all` |
| `audit_scripts.py` | Added `build_module_map()` + `check_broken_imports()`. Uses AST parsing (not regex) so docstring examples never trigger false positives. Demotes try/except-guarded broken imports to MEDIUM (intentional fallback dead-code) vs. CRITICAL (unguarded, file would crash on load). |

**Re-test result — PASS:**
- `restructure.py --rename nova_core.brain=nova_core.prefrontal_cortex --dry` found all 5 stale references (TOOLS.md, __init__.py, rules.py, prefrontal_cortex.py docstring, cache files)
- `restructure.py --rename nova_core.brain=nova_core.prefrontal_cortex --all` fixed all 17 affected files in one pass, including calls.py auto-regeneration
- `audit_scripts.py` now shows: zero CRITICAL, 1 HIGH (pre-existing unreferenced file), 4 MEDIUM BROKEN_IMPORT (all pre-existing `nova_memory.logger` try/except fallbacks — pre-Step-2 debt)
- `calls.py` regenerated cleanly — call graph shows `prefrontal_cortex.py`, no `brain.py`

**Pre-existing debt surfaced (to fix in Step 2):**
- 4 MEDIUM BROKEN_IMPORT: `nova_memory.logger` try/except fallbacks in autonomy.py, explorer.py, eyes.py, vision.py — should point to `nova_logs.logger` instead
- `brain.py.bak` still in `nova_core/` (safety net) — remove after Step 2 confirms stable

**Pipeline verdict:** ✓ SOUND. The self-maintenance tools now work correctly for file-level renames. Proceed to Step 2.
