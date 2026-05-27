# Autonomy Integration Review — 2026-05-24
_Last updated: 2026-05-28 08:41:49_

_Analysis of the 2026-05-24 three-task autonomy test (07:26–08:35). Written before
any code changes, at Cole's request: "write it up and re-review before changing
anything." Evidence is cited by tick number from
`logs/autonomy_runs/2026-05-24_ticks.jsonl` and by line number in
`general_tools/nova_chat/server.py`._

---

## The core finding (one sentence)

**The autonomy loop is a separate orchestrator bolted on top of the chat server,
not an integrated faculty of Nova — so Nova's "will" (the autonomy daemon), her
"voice" (the chat + @mention routing), her "memory" (three separate state stores),
and her "self-model" (NOVA.md / TOOLS.md) operate as disconnected systems that are
unaware of each other and sometimes actively clash.**

Every concrete failure in the test traces back to this. The systems are not yet
"body parts and tools Nova knows she has and knows how to use." They are parallel
machines that happen to share a process.

---

## Part 1 — The anatomy, and where it's disconnected

Think of the stack as Nova's body. Here is what each part is, and the seam where it
fails to connect to the others.

**Voice — the chat reply + cross-AI routing.** The *only* code that makes Claude or
Gemini actually answer is the `@mention` follow-up in `_run_response_queue`
(server.py:1184–1194): after Nova posts a normal chat message, her text is scanned
for `@Claude` / `@Gemini` and those clients are invoked. A second copy of this
routing exists for injected/bridge messages (server.py:2723–2743). Both live on the
*chat* path.

**Will / motor — the autonomy daemon.** `autonomy_daemon()` (server.py:2342) wakes
Nova on a tick and calls `_run_autonomy_tick()` (2149), which calls
`run_ai_response(...)` **directly** (server.py:2252). It never goes through
`_run_response_queue`. **Therefore the autonomy path has no cross-AI @mention
routing at all** — it is the one response path in the entire server that cannot
reach Claude or Gemini, and it is the exact path all of Nova's autonomous *work*
flows through.

**Voice is also muted on the work path.** A silent work tick's output "never touches
the chat transcript" (server.py:1012–1031); it is broadcast only to the
`autonomous_output` monitoring pane and written to the tick log. The single escape
hatch is a `FOR COLE:` prefix that promotes a slice of the reply into chat
(server.py:1034–1044) — but Nova is never told this marker exists, and even when
used it still does **not** run the @mention routing. So when Nova "reaches out to
@Claude" inside a work tick, the words go to a log and a side pane. No message is
ever broadcast; nobody receives an @mention.

**Memory — fragmented across three stores that drift.**
- the chat transcript (`session_mgr.active.messages`),
- `Tasking/task_state.json` (server-owned task status + progress),
- `Tasking/cole_intent.json` (Cole's mirrored "directive").

During a work tick Nova runs on `HeartbeatContext`, which by design contains **no
chat history** (server.py:222–248). So while working she cannot see the
conversation — not Cole's flow, not any reply Claude/Gemini might have sent. This is
why, when Cole pasted her own thinking pane at tick 53, she had "never seen your
responses": the cold context literally excludes them.

**Self-model — NOVA.md / TOOLS.md don't match reality.** At tick 35 Nova told Cole
the stack is "browser → nova_gateway → me on port 8080 via llama.cpp." The gateway
is retired; she runs on nova_chat (8765); 8080 is llama-server. At tick 30 she said
she has no "call_ai" tool and would need one built. She does not know that the chat
she is already in **is** her cross-AI channel, and that `@Claude` / `@Gemini` is how
she speaks to them. Her map of her own body is wrong, so she reaches for organs she
doesn't have and misdescribes the ones she does.

---

## Part 2 — The dual-path clash (two systems both own "respond to Cole")

The WebSocket chat handler responds to **every** Cole message through
`_run_response_queue` (server.py:3207) with **no `autonomous_mode` gate**. At the
same time, the autonomy daemon independently detects `_has_unread_cole()` and fires
a `cole_pending` tick that *also* posts a reply to chat (cole_pending ticks are
not silent — server.py:894). Both paths are mediated only by a shared
`is_processing` flag and the mirrored `cole_intent.json`.

The result is two subsystems racing to answer the same message with **different
capabilities and different memory**:

| | Chat handler path | Autonomy `cole_pending` path |
|---|---|---|
| Context | full transcript | cold `HeartbeatContext`, no history |
| @mention routing | yes (1184) | no |
| Run log | `*_manual_0ticks.jsonl` | daily `*_ticks.jsonl` |

Both kinds of run-log files exist for this test, confirming both fired. Whichever
wins the race determines whether Cole's reply came from "rich Nova" or "amnesiac
Nova." This is the clash: the chat system and the autonomy system each believe they
own the conversation, and they have unequal abilities.

---

## Part 3 — What the test proved, layer by layer

**Layer A — the `_task_key` fix worked (a real win).** The key-normalization fix
applied earlier this session did its job: at tick 11 Nova marked "Creative Writing
Practice" done, and the server correctly matched it, removed it from `priority.md`,
and wrote it to the Decision Log. Task status now persists and completes. The reset
loop's *bookkeeping* half is fixed.

**Layer B — Task 2 (cross-AI) never actually happened.** Every "I reached out to
@Claude / @Gemini" exists only as prose inside `TASK_PROGRESS` notes during silent
work ticks (ticks 59, 62, 67). No message was broadcast; the listener clients were
never invoked. Reachable *in principle* via the chat @mention path — but Nova's work
runs on the one path that lacks it, she doesn't know @mention is the channel, and
the cold context hides any reply even if one came. Task 2 was the test's true
failure, and it is structural, not a matter of effort.

**Layer C — conversation force-fit into the task machine ("the rabbit hole").**
Cole's conversational nudges — "why aren't you responding to me?", "It's meant to be
a conversation" — are mirrored into `cole_intent.json` as a "Priority-0 directive,"
and the next interval tick tells her *"do NOT re-answer Cole, carry out his
directive."* With no real task to carry out, she invents one: the "P1: Investigate
Chat Infrastructure" task was born at tick 37 from "how are we chatting?" She turned
a question into a self-assigned research project instead of answering it.

**Layer D — task identity drift and prefix pollution.** She re-creates the same task
under new names each wake ("Creative Writing Practice" → "…— Nova Identity Draft" →
"…— Solo Draft"), and the exact-string dedup in `_reconcile_queue` lets every
variant through. She also copies the queue *display* format ("P2: **Title**") into
her own task titles, producing "P1:"/"P4:"-prefixed names. `_task_key` normalizes
bold and the em-dash tail but not a leading `P#:`, so one task fragments into two
state entries — visible right now in `task_state.json` as both
`creative writing practice` and `p2: creative writing practice`.

**Layer E — empty / degenerate ticks.** Eight work ticks returned completely empty
replies (ticks 5, 7, 9, 14, 16, 24, 26, 28): no `TASK_PROGRESS`, no `DECISION`,
nothing. Wasted wakes that read as a stall.

**Layer F — cold-context disorientation.** With no clock and no history, she
fabricates continuity: "memory says I did them 10h ago" (the gap was ~40 min);
"Claude's still broken like you said last time" (no such prior).

---

## Part 4 — Fix direction (principles, not yet code)

The guiding principle, in Nova's terms: **every system should be a body part or a
tool that Nova knows she has, knows how to use, and that is coherent with her other
parts.** Concretely, that means:

1. **One voice.** Autonomy ticks that intend to speak or reach another AI must emit
   through the *same* path as a normal chat reply — i.e. route tick output that
   contains `@mention`s (or addresses Cole) through `_run_response_queue`'s
   follow-up logic, so her autonomous will and her voice are the same organ. Today
   they are two.

2. **One source of truth for "is Cole owed a reply."** The chat handler and the
   autonomy daemon must not both own responding to Cole. Pick one. Likely: the chat
   handler owns direct replies; the daemon only does background work and yields to
   Cole rather than re-answering him through a second, weaker path.

3. **Separate conversation from task creation.** A conversational message from Cole
   should be answerable as conversation. Not every utterance is a directive that
   must become a queued task. The "Priority-0 directive" machine should trigger only
   on actual work instructions.

4. **Teach Nova her real anatomy.** Fix NOVA.md / TOOLS.md: remove the gateway/8080
   myth, and state plainly that nova_chat is her body, that Claude and Gemini are
   participants in it, and that `@Claude` / `@Gemini` in a chat message is how she
   talks to them — no special tool required.

5. **Give the work tick memory of the conversation when it needs it.** A pure cold
   context prevents re-answering loops but also blinds her to replies she is waiting
   on (Task 2). The tick needs a controlled, read-only view of recent relevant
   messages.

6. **Harden task identity.** Dedup by normalized key (strip `P#:` prefixes; treat
   title-drift variants as the same task), and instruct her to reuse exact titles.

7. **Eliminate empty ticks.** A tick that produces no `TASK_PROGRESS`/`DECISION`
   should be caught and either retried with a tighter prompt or logged as a no-op,
   not counted as a wake.

---

## Part 5 — Recommended order & status

- **Already applied & confirmed working:** `_task_key` normalization (Layer A).
- **#1 priority — unify voice + cross-AI routing on the autonomy path (Layers A/B,
  fix-direction 1 & 4).** Without this, Task 2 can never complete; it is the
  highest-leverage change and the heart of the "make autonomy a body part" goal.
- **#2 — resolve the dual-path clash and stop forcing conversation into the task
  machine (Layers C, dual-path; fix-directions 2 & 3).**
- **#3 — dedup/prefix hardening and empty-tick handling (Layers D & E;
  fix-directions 6 & 7).**

Nothing in this document has been changed in code. Each item above should be
re-reviewed against the live `server.py` before implementation, because several
touch the same `run_ai_response` / `_run_response_queue` seam and need to be designed
together rather than patched one at a time.

---

## Appendix — verified code references

- `_run_response_queue` @mention follow-up: server.py:1184–1194
- Injected-message @mention trigger: server.py:2723–2743
- Silent-tick routing + `FOR COLE:` escape hatch: server.py:1012–1044
- `_silent_tick = _is_hb_tick and not cole_pending`: server.py:894
- Autonomy tick calls `run_ai_response` directly (no queue): server.py:2252
- `HeartbeatContext` has no chat history: server.py:222–248
- Chat handler responds with no `autonomous_mode` gate: server.py:3176–3207
- `_task_key` (fixed this session): server.py:2051–2073
- Exact-string dedup in `_reconcile_queue`: server.py:1940–1954
