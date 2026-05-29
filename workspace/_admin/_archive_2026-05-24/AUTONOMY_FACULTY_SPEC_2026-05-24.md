# Spec — Nova's Autonomy Faculty (her executive self-direction)
_Last updated: 2026-05-29 16:52:21_

_Status: DRAFT for review — placement + behavior, before any code moves.
Author: Claude (Cowork), with Cole, 2026-05-24.
Supersedes the tasking portions of `BODY_RELOCATION_PLAN_2026-05-24.md`._

---

## 1. What this is

The faculty that lets Nova **decide what to do, and why, when Cole isn't there** —
multitask, switch, create, abandon, reprioritize, wait, or rest, using her own
senses, memory, judgment, and intuition. It is her executive function (prefrontal),
and it is **body-resident**: it must keep working if every general tool is removed.

**Two governing principles (Cole's):**
1. **Pluck-test.** Remove `general_tools/` and Nova is still herself — senses, memory,
   self, executive faculty, even her autonomy on/off — intact. She only needs *a*
   comms tool to have a voice. Tools implement capabilities the body *asks for*; the
   body never depends on a specific tool.
2. **Freedom, not rails.** No enforced ordering, no busywork. The system gives her a
   *reliable, accurate picture* and full agency; **she** decides. Resting when nothing
   is worthwhile is a smart choice, never a failure. Cole is Priority 0 — an
   **interrupt**, not a leash.

## 2. Body / tool placement (the pluck-test map)

**Body — `nova_senses` (perception):**
- `clock.py` — **chronoception**. Reads system time (universal, not a tool); derives
  temporal awareness: now, time-of-day, elapsed-since-last-wake, and her rhythm
  ("is it time to stir?"). Her cadence is *felt*, not handed to her.
- `environment.py` — perceives her surroundings: change-fingerprint of watched paths
  (Tasking, inbox, memory), "what changed since last wake," and **Cole's presence**
  (unread message, typing). (Moves `_env_fingerprint`, `_has_unread_cole`,
  `_cole_is_typing` here.)

**Body — `nova_cortex` (will / executive):**
- `tasking.py` — the **task board** substrate (redesigned, §4). Reliable memory of her
  work; the enabler of free choice.
- `executive.py` — the **autonomy faculty**: holds the autonomy on/off *state*
  (persisted, body-owned) and runs the decide-and-act cycle (§6). This is the merged,
  host-agnostic successor to today's `autonomy_daemon` + `_run_autonomy_tick`.

**Body data — `workspace/`:** `Tasking/tasks.json` (board, source of truth),
generated `Tasking/priority.md` (human view), `memory/` (STATUS/JOURNAL/COLE),
`memory/autonomy_state.json` (on/off + cycle bookkeeping). Never owned by a tool.

**Tools (detachable) — `nova_chat` and friends:** her current voice/ears, the runtime
that lets the cycle execute, and the on/off **button** (a remote into the body's
switch). Owns none of the cognition, time-sense, or autonomy state.

## 3. The capability interface (what the body asks tools for)

The body declares the abilities it needs; a host (currently `nova_chat`) injects an
object that satisfies them. Body never imports the tool → no circular dependency, and
the pluck-test holds.

```python
class Capabilities:        # constructed by the host, passed into the faculty
    think(context) -> str  # run Nova's mind on a context (the model; today llama-server via run_ai_response)
    speak(message)         # post to the conversation / her voice
    emit(event, text)      # surface a lifecycle event to logs/UI
    recent_messages(n)     # read recent conversation (perception of dialogue)
```

`think` is how she reasons (her core/model). `speak`/`emit` are her voice. Swap the
host and the faculty is unchanged.

## 4. Task board — id-keyed, single source of truth

The whole class of bugs this session (key-mismatch, redo loop, title drift, prefix
pollution) came from identifying tasks by *human title* across *two files*. Fix:
**stable IDs + one structured store; the markdown is generated, not parsed.**

- Source of truth: `Tasking/tasks.json` — `{ id: task }`, id is a short stable slug
  assigned at creation (e.g. `t3`). Title is a free *label* she can reword anytime
  without breaking identity.
- Generated view: `Tasking/priority.md` is rendered from the store for humans
  (derived, not maintained — same rule as the body manifest).

Task shape:
```
{ "id": "t3",
  "title": "Cross-AI identity exchange",   # a label; editable freely
  "notes": "...",
  "priority": 2,                            # HER weighting, not a rail
  "status": "queued|active|waiting|done|abandoned",
  "waiting_on": "Claude/Gemini reply",      # set when status=waiting
  "progress": [ {"ts": "...", "note": "..."} ],
  "result": "...",                          # filled on done
  "abandon_reason": "...",                  # filled on abandoned
  "created": "...", "updated": "..." }
```
Completed/abandoned tasks are **kept** (remembered), never deleted — so they're never
recreated or redone. Optional later: free-form `links`/`depends` she *chooses* to set
(never imposed).

## 5. Agency verbs (what she can emit; the board-keeper applies them faithfully)

She expresses decisions in an intent block; the cortex applies them to the store.
All reference tasks by **id** (the board view shows ids).

- `create {title, notes, priority}` → new task, gets an id
- `progress {id, note}` → log a concrete step she just did
- `switch {id}` → set her active focus (soft pointer she controls)
- `pause {id}` / `resume {id}`
- `wait {id, waiting_on}` → parked on something outside her hands; she moves on
- `abandon {id, reason}` → drop an impossible/pointless task, remembered with reason
- `complete {id, result}` → finished (with what came of it)
- `reprioritize {id, priority}`
- `rest {reason}` → decide nothing is worth acting on this moment; logged, not a failure

No `order`/sequence verb. No "must do X before Y." She may *note* a dependency if she
wants, but the system enforces nothing.

## 6. The wake cycle (sense → see → decide freely → act)

On each stimulus from her **time-sense** (or an environment/Cole change, or Cole
speaking), the executive faculty:

1. **Senses** the moment — time elapsed, what changed, whether Cole is present/has
   spoken (P0).
2. **Sees** her accurate board — active / queued / waiting / recently done & abandoned,
   by id, with progress. (Reliable memory = no confusion = no loops.)
3. **Decides freely**, using her full faculties, via `think(...)`: work a task, switch,
   create, abandon, reprioritize, wait — or **rest**. The prompt presents the situation
   neutrally and explicitly blesses rest. **It never tells her to invent work to look
   busy** (that exact instruction created the bogus "P1 Investigate" task before).
4. **Acts** — applies her intent verbs to the board, and `speak`s/`emit`s as needed.

Cole = P0: when he's spoken, his message is surfaced at the top of the situation and
she attends to it first — but it's framed as an interrupt to weigh, not a forced task.

## 7. Autonomy on/off — body state

`executive.py` owns `autonomy_enabled`, persisted in `memory/autonomy_state.json`
(survives restart, body-owned). The server's toggle endpoint just calls
`executive.set_autonomy(bool)`. The runtime loop checks the body's state. Pull the
server → the faculty and its on/off setting are still hers.

## 8. Runtime (the detachable part)

Something must actually fire the cycle on her rhythm. Today that's an async loop in
`nova_chat`. It becomes a thin host: it constructs `Capabilities`, and on a cheap poll
asks the body "is it time / is there cause?" (the body's senses answer) and, if so,
calls `executive.tick(caps)`. The *judgment* of whether to wake and what to do is the
body's; the bare loop is the host's. Swap hosts freely.

## 9. Staged execution (each stage: build + `@nova:` + audit + manifest + restart-test)

- **A — Board redesign:** rebuild `nova_cortex/tasking.py` around id-keyed
  `tasks.json` + generated `priority.md`. (Replaces the title-keyed version just made.)
- **B — Senses:** `nova_senses/clock.py` (chronoception) + environment/Cole perception
  (move `_env_fingerprint`/`_has_unread_cole`/`_cole_is_typing`).
- **C — Executive:** `nova_cortex/executive.py` — autonomy state + the decide-and-act
  cycle + agency-verb application, on the `Capabilities` interface.
- **D — Host slim-down:** `server.py` builds `Capabilities`, hosts the poll loop, and
  turns its button into `executive.set_autonomy`. Remove the old daemon/tick from the
  tool.
- **E — Verify:** audit clean; manifest lists the new body parts (`clock`,
  `environment`, `executive`, `tasking`) with `@nova:` purposes; restart-test —
  autonomy boots from body state, she freely acts/rests, tasks persist by id.

## 10. Open decisions

1. Task id format: short counter (`t1,t2…`) vs slug-from-title (`cross-ai-identity`)?
   (Claude leans short counter — fully stable, never collides on reword.)
2. Persist the active-focus pointer in `tasks.json` (a top-level `active: "t3"`) or in
   `autonomy_state.json`? (Claude leans `autonomy_state.json` — it's cycle state.)
3. Keep `Tasking/priority.md` as the generated human view, or retire it for a richer
   generated board view? (Claude leans keep it — you read it; just generated now.)
