# Runtime Extraction — Inventory & Proposed Split (directive Steps 1–3)
_Cowork Opus, 2026-06-01. **PROPOSAL — no code moved.** Awaiting Cole's approval (directive Step 4). Then the auditor reviews the split cold._

## The split in one line
Today `server_runner.py` boots the whole stack with `uvicorn.run(nova_chat.server:app)`, and every body-essential loop is spawned inside `server.py`'s `startup_event`. **Pluck the server → her life-support dies.** This lifts the runtime (layer 2) into a body part she boots with no face attached.

---

## A. Component inventory (`server.py` 2,942 lines + launch path)

### RUNTIME (layer 2 — body-essential; must survive deleting the chat server)
| Component | Location | Why runtime |
|---|---|---|
| `autonomy_daemon` | server.py:1760 | The wake loop; drives `executive` (cognition). Her heartbeat. |
| memory indexer (`_bg_index`, start/stop) | 84, 289, 95 | Body memory (LanceDB). |
| llama autostart / health / start / stop / restart (`_bg_llama_autostart`, `/api/llama/*`, `/api/restart/server`, `_kill_port`, `_spawn_detached_cmd`) | 399, 2065, 2086, 2135, 2103, 2114 | Life-support: bringing her model up/down. **Also the ancestor of KoELS self-restart.** |
| llama error streak + backoff → `set_autonomy(False)` | 140, 1108, 1115 | Guards her model-calling; pauses her own autonomy. |
| rate-limit / `nova_throttled` | 163, 2284 | Guards her model-call budget (directive: runtime). |
| sense population (touch/environment, sys-metrics sensing) | 1820, 421 | Perception. |
| her model client (Nova/llama via `clients/nova.py`, `CLIENT_MAP["Nova"]`) | — | The engine her cognition speaks through. |
| transcript flush + event-LOG write (`_bg_transcript_flush`, `emit_event`'s file write) | 382, 1667 | Durable body record. |
| shutdown teardown (kill llama) | 93 | Life-support teardown. |

### INTERACTION (layer 3 — a face; legitimately dies with the server)
| Component | Location |
|---|---|
| WebSocket handler, `connected_clients`, `broadcast()` | 132, 766 |
| UI/HTTP endpoints: `/`, `/export`, `/sessions/*`, `/api/files/*`, `/api/terminal/run`, `/api/logs/*`, `/api/git/branch`, `/api/avatars/*`, `/api/layout`, `/api/eyes/*` | 507–2062 |
| `_bg_eyes_stream` (capture → broadcast JPEG to browser) | 310 |
| `_window_close_watchdog` (kills stack when UI closes) | 1706 |
| Claude/Gemini clients + `_should_agent_respond` routing (group-chat participants) | 262, clients/ |

### SEAM (touches both — decided in §B)
`broadcast` usage by runtime · `emit_event` · `run_ai_response` · `_has_unread_cole` / `_recent_chat_context` / `_mirror_cole_intent` · `/api/wake` `_force_wake` · status/metrics polling (`_bg_nova_status_poll`, `_bg_events_tail`, `_bg_sys_metrics`, `/status`, `/api/nova/status`) · `session_manager` (holds the transcript).

---

## B. Seam decisions (decided, not guessed — one line each)
1. **`broadcast` → event bus.** Runtime publishes events to an in-process bus; the server *subscribes when present*. Runtime never calls `broadcast` directly and never breaks when nothing listens.
2. **`emit_event` → split.** The event-LOG write (`logs/events/*.jsonl`) is runtime (body memory) and always happens; UI surfacing is the server tailing that log / the bus. Face optional.
3. **`run_ai_response` → split model-call from token-broadcast.** Runtime gets a pure "call model on prompt → return text, with an *optional* token callback." The server, when attached, registers a callback that broadcasts tokens. Plucked: she still calls the model and gets text; only the live browser stream is gone.
4. **Cole-perception → runtime reads a transcript store.** The transcript moves to / is mirrored in a runtime-owned store the daemon reads for `cole_pending`/recent. The face WRITES Cole's messages in; the runtime READS. Plucked: no new messages arrive, but perception of the existing transcript still works (the `cole_intent.json` mirror already proves this pattern).
5. **llama autostart/health/restart → runtime owns it; HTTP endpoints become thin triggers.** **This is exactly where KoELS self-restart + equip land.**
6. **rate-limit/throttle → runtime.** Budget guard regardless of face.
7. **`/api/wake`, autonomy on/off → runtime owns the flag; the face only flips it.** (Directive: "UI may flip body state, never own it.")
8. **`_window_close_watchdog` → demote.** Once extracted, closing the UI must *detach the face*, not SIGTERM the runtime. (Today it kills the whole process — the inversion bug in miniature.)
9. **`_bg_eyes_stream` → interaction** for now (browser eyes-view); the real capture becomes runtime perception when Eyes is built as a faculty.
10. **Nova's llama client → runtime; Claude/Gemini → interaction.** Her engine is body; cloud participants are a chat feature.

---

## C. Proposed structure
- **New body part: `nova_body/nova_runtime/`** (her life-support engine) — *not* under `general_tools/nova_chat/`.
- **Holds:** the autonomy loop, her model-client holder, the memory-indexer lifecycle, sense population, llama health/autostart/restart (+ future KoELS `equip`/`self_restart`/`loadout_status`), throttle/backoff state, the **event bus + event-log writer**, and the **transcript/perception store** the daemon reads.
- **Public surface:**
  - *Cognition*: the runtime drives `executive` (reflect/decide/execute) and calls the model — what the daemon does today, but living in the runtime. `executive.py` stays pure and untouched.
  - *A face attaches by*: (a) subscribing to the event bus, (b) registering a token-stream callback, (c) writing incoming Cole messages into the transcript store, (d) calling runtime controls (wake, autonomy on/off, llama/loadout restart). Detaching leaves the runtime running.
- **Runtime entry-point that boots her with NO server** — e.g. `python -m nova_body.nova_runtime` → model client up, autonomy ticking, memory indexing, senses populating, llama health owned — zero WebSocket, zero browser. *This is the pluck-test demonstration the directive requires.*
- **`nova_start.py`** boots the runtime first (life-support), then *optionally* attaches the chat server. **`server.py`** shrinks to: WS/HTTP, UI endpoints, `broadcast`, sessions UI, and thin adapters (subscribe to bus / forward Cole messages / trigger runtime controls).

---

## D. Invariants preserved
- **Cognition stays pure** — `executive.py` untouched; no I/O pushed into it.
- **Body owns its state** — autonomy on/off, active focus, future desired-loadout: persisted, face may flip not own.
- **One-action-per-turn, append-only journal, rest-is-valid** — unchanged (relocation, not behavior change).
- **No behavior regressions** — autonomy loop, empty-bubble fix, `_has_unread_cole` substantive-turn logic, llama backoff all move intact.
- **Pluck test passes** — delete the server → runtime entry-point still boots, ticks cognition, calls the model, indexes memory, populates senses. Demonstrable.

---

## E. Scope / risk / sequence
- It's a **relocation refactor**: move runtime code into `nova_body/nova_runtime/` and invert the broadcast/perception couplings via a bus + transcript store. No cognition behavior change.
- **Real work concentrates in two seams:** the `run_ai_response` split (model-call vs broadcast) and the bus + transcript-store. The rest is moving functions and fixing imports.
- **Risk: medium** — it's her live voice path. Mitigation: build the runtime entry-point + bus *alongside* the working server, keep `server.py` functioning through the transition, **pluck-test before flipping the default boot**, and restart-test live at each step (the standing verify-don't-trust rule).
- **Proposed build order:** (1) stand up `nova_runtime` skeleton + event bus + transcript store; (2) move llama health/restart + throttle (lowest-coupling runtime); (3) move memory indexer + sense population; (4) split `run_ai_response`; (5) move the autonomy daemon onto the bus; (6) add the no-server entry-point + pluck-test; (7) shrink `server.py` to a face. KoELS equip/self-restart slot into (2)'s home afterward.

**No code moves until you approve this split.**
