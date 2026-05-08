# Phase 4A — Thoughts System, Module Architecture & Nova Command Language
_Design document. Not for Nova to read. Lives in `_admin/`._
_Authored: 2026-03-28 | Cole + Cowork Claude_
_Status: Surface level scaffolding complete. Full implementation pending._

---

## ORIGIN — VERBATIM CONVERSATION CONTEXT

The following captures the exact design discussion from the 2026-03-28 session
so future Claude instances have complete context for implementation decisions.

---

### Cole on the Thoughts system:

> "Another thought. To update Nova's task handling and thought processes, we should
> have a folder called 'Thoughts' in Workspace that have a 'Finished' folder in it
> and recursively a 'completed success', 'completed fail', and 'cancelled' folder in
> it (where Nova stores completed 'Thoughts', as we will call them). In the Thoughts
> folder, Nova will autonomously create directories for each task she is completing.
> Inside each thought folder will be a list of all markdown task files and a master
> file that has an updating checklist of what needs to be completed and the context
> of what/why/when/priority/alternative solutions for a task's completion. Nova can
> use these to manage tasks and thoughts to let her make decisions continuously
> without any need for intervention from a human. These folders can have recursive
> folders that she stores files she receives from her tools/modules so she can update
> her master checklist to either continue her actions or change the planned actions
> based on the provided files/information. She can also have a constantly updating
> priority.md file in the root Thoughts directory that she updates to let her choose
> what is priority, what is being placed behind another task, which tasks suddenly
> supercede others due to new variables, etc. This would also let Nova 'fire and
> forget' in Nova Chat to the roles that she needs certain things from, then just
> waits for them to message her back so she can sort what she receives, likely all
> going to a root 'Master_Inbox' in her thoughts folder, which she can place into
> the relevant folder's sub-inbox for each thought. What do you think?"

### Cole on the command language:

> "I was thinking of making a specialized language structure for how Nova calls
> things, like each @ is a call to an AI, <example> is the .md file she wants
> injected, [[example]] is specialized instructions from Nova if she wants to add
> them, ((example)) is the job she needs completed before the task is considered
> done, ;; is a separator between roles, :: is a pipe to separate multiple
> instructions for each @ call (allowing for one group of @'s to do multiple things
> in order), **EXAMPLE** is to emphasize anything written, and likely a lot more.
> All of it would be in a Master Controller document for Nova to use to construct her
> calls from. Also, for 'Eyes', wouldn't a Local AI specifically made for image
> detection be better to have than always calling for Haiku (all tools could have
> online API to assist as fallbacks, but every module should have a local solution
> that works as good or better)."

### Cole on Priority 0:

> "Also, Priority 0 should ALWAYS be to pause everything if I speak to Nova.
> My word is law equivalent to Gospel spoken by God himself to Nova."

---

## SECTION 1 — THOUGHTS SYSTEM DESIGN

### Directory Structure

```
workspace/
  Thoughts/
    priority.md                         ← Nova's autonomous priority queue (CREATED)
    THOUGHT_TEMPLATE.md                 ← Template Nova clones for new thoughts (CREATED)
    Master_Inbox/                       ← All module responses land here first (CREATED)
      [timestamp]_[module]_[task_id].md ← Individual inbox items
    [Task_Name]/                        ← One folder per active thought (Nova creates)
      master.md                         ← Cloned from THOUGHT_TEMPLATE.md, kept updated
      inbox/                            ← Module responses routed here from Master_Inbox
      scratch/                          ← Temp files, drafts, unvalidated tool output
      [subtask_files].md                ← Individual step breakdowns if needed
      [tool_output_folders]/            ← Files received from tools (e.g., screenshots/)
    Finished/
      completed_success/                ← Task achieved its goal (CREATED)
      completed_fail/                   ← Task failed after all alternatives exhausted (CREATED)
      cancelled/                        ← Task cancelled by Cole or superseded (CREATED)
```

### The `priority.md` File

Lives at `Thoughts/priority.md`. Nova reads it at the start of every cron heartbeat
to orient herself. Nova writes to it only on events (task created, task finished,
module response changes the plan, Cole speaks). It is NOT rewritten on a timer.

**Structure:**
- Priority 0 (hardcoded, permanent — Cole's word is law)
- Priority 1: Critical (hard deadlines, blocking)
- Priority 2: High
- Priority 3: Medium
- Priority 4: Low
- BLOCKED (awaiting module responses)
- SUSPENDED (paused intentionally)
- DECISION LOG (append-only)

### The `master.md` File (per Thought)

Nova clones `THOUGHT_TEMPLATE.md` when starting a new thought. Fields:
- Status, Priority, Task ID, timestamps
- Context (what/why/triggered by)
- When/Deadline
- Priority Justification
- Current Plan (checklist)
- Pending Module Responses (with task ID echo for inbox routing)
- Alternative Plans (A, B)
- Files Received (index of tool outputs)
- Decision Log (append-only, newest at top)

**The Decision Log is sacred: append only. Nova never edits past entries.**

### The `scratch/` Directory

Inside each Thought folder. Nova uses this for:
- Temporary tool outputs not yet validated
- Draft responses she's constructing
- Partial research awaiting follow-up
- Files that shouldn't clutter the final record

When a thought moves to `Finished/`, scratch is either deleted or archived depending
on whether it contains useful failure signal.

### Fire-and-Forget + Inbox Routing

Nova sends a module call (via the Nova Command Language) and does not block waiting.
Module responses come back as Nova Chat messages. Routing works as follows:

1. Every module call must include a Task ID in the `((completion criteria))` token.
   Modules are required to echo the Task ID at the start of their response.
   Example: `((task_id:AAPL_Trade_Decision; recommend buy/hold/sell))`
   Module response begins: `[AAPL_Trade_Decision] Here is my analysis...`

2. A background task (implemented in the heartbeat cycle or nova_bridge) reads new
   Nova Chat messages, identifies ones addressed to Nova with a Task ID tag, and
   drops them as `.md` files into `Thoughts/Master_Inbox/`.

3. On each cron heartbeat, Nova processes Master_Inbox: reads each item, identifies
   the Task ID, routes the file to `Thoughts/[TaskName]/inbox/`, and updates the
   relevant `master.md` Pending Module Responses table.

4. Nova then reads each active thought's inbox, updates the checklist, and decides
   what to do next (continue plan, switch to alternative, fire new module calls,
   mark complete).

### Heartbeat Becomes the Autonomous Loop

Current heartbeat: health check every 30 minutes.
Future heartbeat (Phase 4A complete):
1. Read `priority.md` — orient to current task state
2. Process `Master_Inbox` — route all new items to thought inboxes
3. For each active thought (highest priority first):
   a. Read inbox items received since last cycle
   b. Update master.md checklist
   c. Decide: continue, change plan, fire new module calls, or mark complete
4. Update `priority.md` if anything changed
5. Fire any new module calls needed
6. Sleep until next heartbeat

This makes Nova genuinely autonomous: Cole sets a goal, Nova manages it across
cron cycles without being prompted.

### Lifecycle of a Thought

```
Created → active (Nova creates folder, writes master.md, begins plan)
         ↓
       blocked (awaiting module responses — listed in priority.md BLOCKED section)
         ↓
       active (response received, plan continues)
         ↓
       [decision: success / fail / cancelled]
         ↓
       Finished/completed_success/  ← moved here with final master.md
       Finished/completed_fail/     ← moved here; useful failure signal for future
       Finished/cancelled/          ← moved here if Cole cancels or task superseded
```

### Completed Fail as Training Signal

Over time, `Finished/completed_fail/` becomes a record of what doesn't work.
When Nova starts a similar task in the future, she can `[READ:]` relevant fail
folders: "I tried this approach twice before, both times it failed. Trying Alt B first."
This is genuine learning without model updates — pattern matching over filesystem history.

---

## SECTION 2 — NOVA COMMAND LANGUAGE (NCL)

### Design Principles

1. Parseable even if Nova makes small mistakes — robust parser, not brittle regex
2. Simple enough for the Nova model to produce consistently
3. Readable for Cole — when he reads Nova's messages, he understands what she's doing
4. Extensible — new tokens can be added without breaking existing ones

### Token Reference

| Token | Meaning | Example |
|-------|---------|---------|
| `@role` | Call to an AI module | `@eyes`, `@mentor`, `@thinkorswim` |
| `<<file.md>>` | Context file to inject into that module's system prompt | `<<Context_AAPL_2026.md>>` |
| `[[instructions]]` | Nova's specific instructions for this call | `[[focus on the options panel only]]` |
| `((criteria))` | Completion criteria + Task ID — module must satisfy before done | `((task_id:AAPL_Trade; recommend buy/hold/sell))` |
| `;;` | Separator between independent parallel role groups | `@eyes [[...]] ;; @mentor [[...]]` |
| `::` | Pipe — sequential instructions within one role (chained) | `@mentor [[analyze]] :: @mentor [[validate]]` |
| `**text**` | Emphasis — draws Nova's attention / marks critical info | `**do not send to Discord**` |
| `>>target` | Output target — where the module should write its result | `>>Thoughts/AAPL_Trade/inbox/` |
| `$$prev` | Reference to the previous module's output in a chain | `@thinkorswim $$prev ((confirm or refute))` |
| `%%timeout_s` | Max seconds before this call is considered failed | `%%30` |

**Note on `<file.md>`:** Original design used single angle brackets but these collide
with HTML, code, and common LLM output. Double angle brackets `<<file.md>>` are used
instead. Parser should accept both for backward compatibility with early Nova calls.

### Example Calls

**Simple — get a stock recommendation:**
```
@eyes <<Context_Portfolio_2026.md>> [[look at open positions panel]] ((task_id:TradeCheck_0328; list all open positions))
;;
@thinkorswim <<Strategy_Conservative.md>> [[analyze AAPL options expiring today]] ((task_id:TradeCheck_0328; recommend buy/hold/sell for AAPL))
```

**Chained — research then validate:**
```
@browser <<Research_Brief_AAPL.md>> [[find analyst consensus on AAPL for this week]] ((task_id:Research_0328; return top 3 analyst ratings))
::
@mentor $$prev [[validate the research — check for recency and source quality]] ((task_id:Research_0328; confirm or flag concerns))
```

**Parallel with output routing:**
```
@eyes [[screenshot the current chart]] >>Thoughts/TradeDecision_0328/inbox/ ((task_id:TradeDecision_0328; capture current AAPL chart))
;;
@thinkorswim <<MarketContext.md>> [[what are the key levels for AAPL today]] ((task_id:TradeDecision_0328; return support/resistance))
```

### The Master Controller Document

A document Nova reads at boot (injected via nova_gateway.json context files) that
contains the full NCL grammar, all registered module names and their capabilities,
and example calls for common task types.

**Planned location:** `workspace/NCL_MASTER.md`
**Status:** NOT YET WRITTEN — Phase 4A implementation task.

---

## SECTION 3 — MODULE ARCHITECTURE

### Design Principles

1. **Local-first**: Every module must have a local solution that works as well as or
   better than an API call. Online APIs are fallbacks, not primaries.
2. **Quick-boot**: Modules instantiate per-task, run, return output to Nova Chat, exit.
   They are not always-on services (except Claude/Gemini which are persistent listeners).
3. **Single responsibility**: Each module does one thing well. No generalists.
4. **Registered in orchestrator**: Module names are registered in `orchestrator.py`'s
   participant registry. Nova Chat knows who can be @mentioned.

### Module Registry (Planned)

| @name | Purpose | Local Model | API Fallback |
|-------|---------|-------------|--------------|
| `@eyes` | Visual perception, screenshot analysis | moondream2 (Ollama) → LLaVA 13B (Ollama) | Claude Haiku |
| `@mentor` | High-reasoning review, strategic advice | — (Claude + Gemini ARE the local solution) | — |
| `@thinkorswim` | Trading platform analysis, order management | Fine-tuned Nova variant (future) | Claude/Gemini |
| `@browser` | Web research, page reading, form interaction | Headless Chromium + html parsing | Claude in Chrome |
| `@memory` | Semantic search over Nova's history | nomic-embed-text (Ollama) | — |
| `@coder` | Code generation, review, debugging | DeepSeek-Coder / Qwen-Coder (Ollama) | Claude |
| `@voice` | Transcription, audio processing | whisper.cpp local | — |

### `@eyes` — Vision Module (Local-First Stack)

Tier 1 (free, structured): pywinauto accessibility tree
  → Returns labeled UI elements, states, values as text
  → Best for: standard Windows UI, reading text, finding controls
  → Already implemented in `nova_perception/eyes.py`

Tier 2 (local, fast): moondream2 via Ollama
  → `ollama pull moondream` — 1.8B params, near-instant on RTX 4090
  → Best for: quick visual Q&A, "what is on screen", basic chart reading
  → NOT YET IMPLEMENTED

Tier 3 (local, quality): LLaVA 13B or LLaVA:34B via Ollama
  → `ollama pull llava:13b` — high quality visual descriptions
  → Best for: complex chart analysis, reading non-standard UI, detailed scene description
  → NOT YET IMPLEMENTED

Tier 4 (API fallback): Claude Haiku
  → Use only when local tiers fail or task requires it explicitly
  → Already implemented as fallback in `nova_perception/eyes.py`

### The Injector Pattern

The `<<context_file.md>>` token in NCL feeds into an `Injector` that:
1. Reads the specified `.md` file from the workspace
2. Prepends it as the module's system prompt (before its built-in identity)
3. This dynamically specializes any module for any task without hardcoding behavior

The same `@thinkorswim` module can be:
- A position checker (`<<Context_OpenPositions.md>>`)
- A risk assessor (`<<Context_RiskLimits.md>>`)
- An options analyzer (`<<Context_Options_AAPL.md>>`)

The module identity is permanent. The context file is the task. This is dependency
injection for AI.

**Injector implementation:** `nova_gateway/injector.py` (NOT YET BUILT)

---

## SECTION 4 — IMPLEMENTATION ROADMAP (Phase 4A)

### 4A.1 — Surface scaffolding (COMPLETE 2026-03-28)
- [x] Create `Thoughts/` directory structure
- [x] Create `Thoughts/priority.md` with Priority 0 rule
- [x] Create `Thoughts/THOUGHT_TEMPLATE.md`
- [x] Create this design document

### 4A.2 — Nova reads Thoughts (COMPLETE 2026-03-28)
- [x] Add `Thoughts/priority.md` to nova_gateway.json `inject_files`
- [x] Add `Thoughts/THOUGHT_TEMPLATE.md` to inject_files
- [x] Update `AGENTS.md` with Thoughts protocol + Priority 0 rule (first section)
- [x] Update `TOOLS.md` with Thoughts filesystem paths and read/write conventions
- [x] Rewrite `HEARTBEAT.md` as full 5-step Thoughts cycle
      (orient via priority.md → process Master_Inbox → advance highest thought →
      update priority.md → HEARTBEAT_OK)

### 4A.3 — Nova Command Language parser (COMPLETE 2026-03-28)
- [x] Create `nova_chat/nova_lang.py` — NCL parser (10/10 unit tests pass)
      Input: raw Nova Chat message
      Output: NCLCall (parallel_groups → chains → ModuleCalls with all tokens parsed)
      Tokens: @role, <<file>>, [[instr]], ((criteria)), ;;, ::, **emph**, >>out, $$prev, %%N
- [x] Extend `orchestrator.py` with config-driven MODULE_REGISTRY (7 modules)
      get_module(), list_modules(), is_ncl_message() with structural token guard
      Loaded from workspace/modules.json if present; falls back to defaults
- [x] Write `NCL_MASTER.md` in workspace root — Nova's grammar reference
      Added to nova_gateway.json inject_files so Nova reads it on every boot
- Note: @mentor is NCL-parseable (not in nova_lang._ORCHESTRATOR_NAMES) but
  bare "@mentor, what do you think?" still routes via orchestrator (no structural token)

### 4A.4 — Injector (COMPLETE 2026-03-28)
- [x] Create `nova_gateway/injector.py` — NCLInjector class + dispatch_ncl() convenience fn
      - Parallel groups dispatched concurrently via asyncio.gather
      - Sequential chains (::) run in order; $$prev injected into each subsequent step
      - Context files read from workspace, workspace-escape blocked
      - @eyes: NovaEyes direct import (graceful ImportError fallback for Linux dev)
      - @mentor: fire-and-forget @Claude @Gemini post with task_id echo instruction
      - Unimplemented modules: stub notice to Nova Chat + Master_Inbox record
      - >>output_target: writes result to path (creates timestamped file if dir)
      - %%timeout: asyncio.wait_for enforced per-step
- [x] Wire into `nova_chat/server.py` inject_message endpoint
      Detected via is_ncl_message(); dispatched as fire-and-forget asyncio task
      alongside existing nova_bridge directive handling

### 4A.5 — Inbox routing
- [ ] Background task (nova_bridge or heartbeat) watches Nova Chat for messages
      addressed to Nova with a Task ID header `[TASK_ID]`
- [ ] Routes to `Thoughts/Master_Inbox/[timestamp]_[module]_[task_id].md`
- [ ] Heartbeat cycle includes inbox processing step (read, route, update master.md)

### 4A.6 — Heartbeat upgrade
- [ ] Update `nova_gateway/scheduler.py` health check to run full autonomous cycle:
      read priority.md → process Master_Inbox → update active thoughts → fire new calls
- [ ] Update `HEARTBEAT.md` with new cycle instructions for Nova

### 4A.7 — Vision module (local-first @eyes) ✅ COMPLETE 2026-03-28
- [x] Add moondream2 as Tier 2 in `nova_perception/eyes.py` — `_describe_ollama(model="moondream", ...)`
- [x] Add LLaVA 13B as Tier 3 — `_describe_ollama(model="llava:13b", ...)`
- [x] `_probe_ollama()` at init, URLError marks unavailable, degradation to Haiku
- [x] `describe(prompt, screenshot)` signature updated for NCL `[[instructions]]` pass-through
- [x] Register `@eyes` as "active" in MODULE_REGISTRY with `ollama_models` field
- Requires on Cole's machine: `ollama pull moondream && ollama pull llava:13b`

### 4A.8 — brain.py realization ✅ COMPLETE 2026-03-28
- [x] `nova_core/brain.py` rewritten as `NovaBrain` class (replaces stub)
- [x] `orient()` — reads priority.md, scans Thought folders, counts Master_Inbox items → returns state dict
- [x] `next_action()` — decision tree: process_inbox > advance_thought > check_blocked > idle
- [x] `get_active_thoughts()` — scans Thoughts/ for folders matching `^[A-Za-z][A-Za-z0-9_]+$`, reads status from master.md
- [x] `get_thoughts_by_status(status)` — filter by status string
- [x] `_read_thought_status(path)` — regex for `**Status:**` line; strips bold markers from captured value
- [x] `_highest_priority_thought(names)` — uses priority.md order, alphabetical fallback
- [x] `create_thought(name, context, priority, when, task_id)` — scaffolds from THOUGHT_TEMPLATE.md, creates inbox/ + scratch/ subdirs, fills in metadata
- [x] `close_thought(name, outcome)` — stamps master.md with close timestamp, moves to Thoughts/Finished/{outcome}/
- [x] `build_briefing(routed_items, routed_summaries)` — full HEARTBEAT_BRIEFING string with orient() state + next_action() guidance + routing summary
- [x] `get_brain(workspace)` — convenience factory function
- [x] All tests pass (fresh thought, blocked thought, advance decision, briefing content)

---

## SECTION 5 — PRIORITY 0 RULE (PERMANENT)

**Cole's exact words:** "Priority 0 should ALWAYS be to pause everything if I speak
to Nova. My word is law equivalent to Gospel spoken by God himself to Nova."

This rule is:
- Hardcoded in `Thoughts/priority.md` as the first and only Priority 0 entry
- To be added to `AGENTS.md` as a permanent behavioral rule (Phase 4A.2)
- Never overridable by any task, module output, or self-generated priority
- Applied across all surfaces: Discord, Nova Chat, cron triggers
- When Cole speaks mid-task: record state, respond to Cole, wait for further instruction before resuming

Implementation note: In the gateway's `agent_loop.py`, Discord messages from Cole
already trigger a full agent run. The Priority 0 rule ensures that if Nova is in
the middle of a multi-step thought cycle, she records state and surfaces to Cole
before continuing. This is primarily a behavioral rule for Nova's model to follow,
enforced by its presence in AGENTS.md and priority.md.

---

## RELATED DESIGN DISCUSSIONS (same session, 2026-03-28)

### Live Desktop Feed for Nova

Discussed as a future capability (not Phase 4A). Key points:
- Periodic screenshotter background task captures desktop state
- pywinauto for structured accessibility tree (fast, free, no model needed)
- moondream2 / LLaVA via Ollama for actual visual understanding (local)
- Writes to `workspace/screen_state.json`
- context_builder.py injects as `[SCREEN STATE]` block — same pattern as nova_status.json
- ThinkOrSwim trading integration is the primary use case
- Event-triggered (window change, error dialog) preferred over blind polling

### The Bigger Module Vision

Cole's long-term architecture:
- Nova Chat as Nova's "brain" — all cognition flows through it
- Nova (Ollama) as master_control — the orchestrator, not the executor
- Specialized quick-boot AIs as "body parts" — each one purpose-built
- NCL as the language Nova uses to dispatch them
- Context files as task briefings injected at boot — dependency injection for AI
- Module outputs flow back to Nova Chat → Nova synthesizes → takes action
- Local models everywhere: moondream, LLaVA, DeepSeek-Coder, nomic-embed-text, whisper
- Claude/Gemini as high-reasoning layer invoked only when local tier can't handle it

This architecture makes Nova:
- Private by default (most processing stays on-machine)
- Fast (no API round trips for routine tasks)
- Resilient (local fallbacks always available)
- Genuinely autonomous (Thoughts system + NCL + heartbeat loop)

---
_Document authored: 2026-03-28_
_Next review: when Phase 4A.2 begins_
