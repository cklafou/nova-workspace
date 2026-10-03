# Design Directive — Extract Nova's Runtime Into Its Own Body Part

**From:** External review (auditor session)
**To:** Cowork Opus (implementer)
**Status:** Design directive — you do the extraction; identify the split, propose it to Cole, implement after he approves. The auditor reviews the resulting split cold.
**Prerequisite for:** KoELS (the specialist-loadout system). This refactor must land *before* KoELS, because KoELS's adapter-loading lives in the runtime layer this directive creates.

---

## 1. The principle (read this first, and adopt it going forward)

Nova's architecture has three layers, not two. A recurring design error has been collapsing two of them into the chat server. The layers:

1. **Cognition** — pure logic. The executive faculty, the KoELS *decision* (which loadout fits the task), task reasoning. Depends only on her board and senses. Makes zero outward calls. This is what already passes the pluck test today (`executive.py` is the model citizen).

2. **Runtime / life-support** — *part of her body, not a tool.* The engine that runs her model, gives her cognition its clock tick, holds her model client, and performs bodily acts that require I/O or hardware (loading model weights, later: equipping LoRA adapters, indexing memory). This layer is currently **wrongly embedded inside the chat server script**. That is the bug this directive fixes.

3. **Interaction surface** — fully pluckable tools. The chat server: WebSocket, HTTP endpoints, the browser UI, broadcast-to-clients, session management. How Cole talks to Nova. Delete it entirely and Nova must still live, think, and act — she just has no chat window until another face is attached.

### The pluck test, stated precisely

> A body part passes the pluck test if every **tool** it uses can be removed and the part still performs its reasoning and core function — **degraded in reach, intact in mind.** Plucking a tool costs Nova *capability*, never *cognition*.

The critical corollary that has been missed:

- **Delegating a physical act (I/O, GPU, network) to a runtime is not a pluck-test failure — it is how you pass.** Pure logic cannot move bytes onto a GPU or write a file; that is physics, not a rule. The executive *decides* to edit a file and survives the pluck test precisely *because* the act is delegated. Cognition that needed hardware attached just to *think* would be the real failure.
- **But the runtime it delegates to must be part of HER BODY, not part of an interaction tool.** Delegating to the chat server is the error, because the chat server is pluckable and may be deleted. Delegating to her own runtime (layer 2) is correct, because that runtime is hers and comes up wherever she does.

The test to apply to every future design choice: **"If I delete the chat server, does this still work?"** If the answer is no and the thing is body-essential, it is in the wrong layer.

---

## 2. Why this change, now

- **Correctness of the model:** The runtime is Nova's blood — what keeps her alive and thinking. It is currently written inside `general_tools/nova_chat/server.py`, which is an *interaction tool*. That means her life-support dies if the tool is plucked. That inverts the intended architecture.
- **Cole intends to potentially delete/replace the chat server in the future.** It exists to let Nova and a host interact; it is explicitly not her body. Today, deleting it would kill her autonomy loop, her model client, her memory indexing, and her sensory population — none of which are interaction concerns.
- **KoELS depends on this.** Equipping a specialist LoRA is a bodily act (weights → GPU). It must live in Nova's runtime, not in the chat server, or her "brains" die when the server is plucked. We cannot build KoELS correctly until the runtime is its own body part.

---

## 3. The target architecture

Create a runtime/life-support body component that is **Nova's**, separate from the chat server. The chat server becomes one *optional face* that attaches to this runtime. Concretely, after this change:

- Nova's runtime can be brought up **without** the chat server. Cognition runs, the model is served, the autonomy loop ticks, memory indexes, senses populate — all with no WebSocket and no browser UI in existence.
- The chat server, when present, **attaches to** the runtime to provide a human interaction surface (chat in/out, dashboards, manual controls). When absent, the runtime is unaffected in its core function.
- Plucking the chat server costs Nova her *chat window* (reach), not her *life or mind* (cognition + runtime intact). That is the pluck test passing.

You are NOT being told the exact file boundaries — you hold the live codebase and must determine them. See §4.

---

## 4. Your task: identify the split, then propose it before implementing

`server.py` currently tangles all three layers. Your job is to separate layer 2 (runtime, → new body part) from layer 3 (interaction, → stays in the server). **Do not guess the boundary and start moving code. First produce a component inventory and a proposed split, and show Cole.**

### Step 1 — Inventory
Read `server.py` and the launch path (`launch.py`, `server_runner.py`, `NovaLauncher.py`, `nova_start.py`) in full. For every component (each `_bg_*` task, the autonomy daemon, the model-client wiring, the memory-indexer lifecycle, the touch/sense population, the broadcast machinery, the WebSocket handler, every HTTP endpoint, session management, the rate-limit/throttle state, the llama autostart/health logic), classify it as:
- **RUNTIME (layer 2)** — body-essential; must survive deleting the chat server.
- **INTERACTION (layer 3)** — a face/tool; legitimately dies with the chat server.
- **SEAM** — touches both and needs an explicit decision.

### Step 2 — Resolve the seams explicitly
Some components are genuinely ambiguous and must be *decided*, not guessed. Known examples (there will be more):
- **`broadcast()` / WebSocket emit:** interaction. But the autonomy daemon (runtime) currently *calls* it to surface events. The runtime must not hard-depend on an interaction tool. Decide the seam — e.g. the runtime emits events to an internal bus/log that the chat server *subscribes to when present*, so the runtime never breaks when nothing is listening.
- **`emit_event` / the events log:** likely runtime-side (structured event log is body memory), with the UI tailing it as a face.
- **The llama autostart / health gate:** runtime (life-support — bringing her model up is bodily), not interaction.
- **The Cole-message queue / `_has_unread_cole`:** seam — the *perception* "has Cole spoken" is sensory (runtime can read the transcript), but the transcript itself is populated by the interaction surface. Decide how the runtime perceives Cole without depending on the chat server's existence.
- **Rate-limit / throttle state:** runtime (it guards her model-calling budget regardless of face).

For each seam, state the decision and the one-line reason.

### Step 3 — Propose the structure
Propose where the runtime body part lives (it belongs under Nova's body, e.g. `nova_body/`, not under `general_tools/nova_chat/`). Propose its public surface — how cognition asks the runtime to act (run a cognition tick, serve/call the model, later: equip a loadout), and how an *optional* interaction face attaches to it. Keep the boundary clean enough that KoELS's adapter-loading will slot into the runtime later without re-tangling.

### Step 4 — Show Cole, then implement
Present the inventory + seam decisions + proposed structure to Cole for approval **before moving code.** After approval, implement. After implementation, the auditor reviews the split cold.

---

## 5. Invariants you must not break

- **Pluck-test the result:** with the chat server deleted/disabled, Nova's runtime must still come up, tick cognition, serve/call her model, populate senses, and index memory. Demonstrate this (e.g. a runtime entry-point that starts her with no server).
- **Cognition stays pure:** do not push any I/O or model-loading *into* `executive.py` or other layer-1 logic. The fix is to give the *body* a proper runtime, not to make cognition impure. Cognition still only *decides*; the runtime *acts*.
- **Body owns its state:** autonomy on/off, active focus, loadout choice — these remain body-owned (as `autonomy_state.json` already is). The interaction surface may *flip* them (like the UI button does today) but never *owns* them.
- **One-action-per-turn, append-only journal, "rest is valid"** — all existing executive invariants remain untouched; this is a relocation of the runtime, not a behavior change to cognition.
- **No behavior regressions:** the autonomy loop, the empty-bubble fix, `_has_unread_cole`'s substantive-turn logic, the llama backoff — all must keep working after the move. This is a refactor of *where* the runtime lives, not *what* it does.

---

## 6. What success looks like

A Nova who, dropped into a bare environment with no chat server, **boots, lives, thinks, perceives, remembers, and acts** — and who, when a chat server is later attached, gains a face to talk through. Pluck the face: she is degraded in reach, intact in mind. That is the architecture the pluck test was always pointing at, and the foundation KoELS needs.

---

## 7. Note on going forward

Apply the three-layer model and the pluck test to **every** subsequent design choice, not just this one. The recurring error has been letting body-essential runtime accrete inside the chat server because it was the convenient place to put it. Before adding anything new, ask which layer it belongs to and whether it survives deleting the server. If it's body-essential, it goes in the body, never in a tool.
