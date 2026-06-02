# KoELS — Design Specification

**KoELS** = *Knowledge of Experts Loadout System* (pronounced "Ko-Els").

**From:** External review (auditor session) — written on Cole's design
**To:** Cowork Opus (implementer)
**Status:** Design spec. The *architecture, structure, manifest, and decision faculty* below are buildable now. The **equip mechanism** (physically loading an adapter) is **deferred** — see §7 — because it depends on (a) the runtime-extraction directive landing first, and (b) one unverified fact about the inference stack. Do not implement the equip mechanism until both are resolved.

**Depends on:** the runtime-extraction directive (KoELS's equip lives in the runtime body layer that directive creates). KoELS structure, manifests, and decision logic can be built in parallel with that extraction; the equip wiring cannot.

---

## 1. Core idea (one line)

Nova is a single, continuous identity who can **equip specialist "brains" — domain-trained LoRA adapters, each paired with its own knowledge DB — to become a genius-level expert in a domain at will, then take them off, never ceasing to be herself.**

The metaphor Cole is designing to: a robot **equipping a loadout**. A specialist is a *kit* she dons, not a separate mind she consults. (Visual intent: a distinct outfit per active loadout, so which expert is loaded is legible at a glance — see §6.)

---

## 2. The weights/retrieval split (non-negotiable design law)

This governs every specialist:

> **Weights = durable expertise.** Reasoning patterns, doctrine, theory, strategic judgment, coaching style — the timeless "how to think in this domain." This is what the LoRA is trained on.
>
> **Retrieval = anything with a date on it.** Patch notes, current stats, prices, balance changes, current meta — the volatile facts. This lives in the specialist's LanceDB, written by the updater, **never** baked into weights.

A specialist is therefore always **weight-trained-to-reason + DB-fed-current-facts**, both doing what each is actually good at. Training facts into weights is forbidden — it would force a retrain on every patch and produces confident hallucination (the exact Gemini failure this whole project is reacting against). The gaming LoRA learns *strategic philosophy, military tactics, chess theory, how to reason about games*; it does **not** learn this patch's card stats — those are retrieved.

---

## 3. Layer placement (pluck test)

KoELS spans two layers, split the same way the executive is split from its runtime:

- **Cognition (pure logic, pluck-safe):** the **loadout-decision faculty** — "which loadout, if any, does this task need, and should I swap now?" Reads manifests + task context. Makes **zero** outward calls — no model loading, no GPU, no DB queries. Survives every pluck. Lives with the other cognition faculties (`nova_body/nova_cortex/`).
- **Runtime / life-support (her body's engine — the layer the runtime-extraction directive creates):** the **equip mechanism** — physically loading/unloading adapter weights onto her running model, and querying the specialist's LanceDB. This is a bodily act (bytes→GPU) and MUST live in her own runtime, never in the chat server. Deferred — §7.

The pluck-test corollary applies exactly: cognition *deciding* "I want the gaming brain" is pure and survives. The runtime *equipping* it is a physical act delegated to her own runtime — and delegating it there is **how KoELS passes the pluck test**, not a failure. If you delete the chat server, Nova still decides she wants a loadout and her runtime still equips it. If you tried to bake equipping into pure cognition, that would be the real failure (pure logic cannot move weights onto a GPU).

---

## 4. Folder structure

Everything under a top-level `KoELS/` directory, one subfolder per expert, each self-contained:

```
KoELS/
  gaming/
    manifest.json         # the contract — what this expert IS (see §5)
    adapter/              # the trained LoRA weights (durable; produced by cloud training)
    knowledge.lancedb/    # this expert's volatile facts (written by the updater)
  finance/
    manifest.json
    adapter/
    knowledge.lancedb/
  legal/
    ...
  coding/
    ...
```

Rationale: an expert is a **drop-in folder**. Adding "legal" later = drop a `legal/` folder with a manifest, an adapter, and a DB. No code change to Nova. This is what makes KoELS a *system* rather than N hardcoded specialists. The manifest is the load-bearing piece that makes this work (§5).

Within each expert, keep durable vs. volatile separate (they have different owners/lifecycles): the **adapter** is durable, produced by training, rarely changes; the **knowledge.lancedb** is volatile, written constantly by the updater. Never conflate them.

---

## 5. The manifest contract

Define this **once**; every expert fills it out. This is the interface Nova's decision faculty reads to know what loadouts exist and how to use each. A manifest declares:

- **`name` / `domain`** — what this expert is for (e.g. "gaming", "competitive game coaching & strategy").
- **`trigger`** — how cognition recognizes a task needs this loadout (keywords/intents/task-types the decision faculty matches against). Routing *uses* this; the decision stays in cognition.
- **`adapter`** — path/ref to the LoRA weights for this expert (the durable brain).
- **`knowledge_db`** — path/ref to this expert's LanceDB namespace (the volatile facts).
- **`oracle`** *(optional)* — declares an external ground-truth tool this expert consults instead of reasoning from weights, with how to call it. Example: gaming/chess → Stockfish. If present, the expert *consults and explains the oracle* rather than trusting its own judgment for that sub-domain. (This is why chess is special — see §6/build order.)
- **`fusion_mode`** — how the expertise attaches. For now: `adapter` (LoRA stacked on Nova-core — the default and the only one we build first). The field exists so future modes (`oracle_tool`, `external_model`) slot in without schema change.
- **`visual`** *(optional)* — the loadout's outfit/appearance ref (§6).

Design the manifest schema so an unknown future expert is expressible without changing it. The schema is the real first deliverable.

---

## 6. Two invariants and the visual layer

**Invariant 1 — Nova-core is always loaded underneath.** Whatever specialist she equips, her core identity/personality/memory adapter stays loaded beneath it. She never stops being herself; she *gains* a specialty on top of who she is. The equip is therefore *at minimum* two-deep: **Nova-core + one specialist.**

**Invariant 2 — identity and memory are always hers; the specialist supplies expertise, never the voice.** The whole reason this routes through Nova instead of "just open a chess bot" is that it's *her* — her memory of your games, her voice, her continuity. A loadout that strips that out and becomes a generic expert has destroyed the only thing that made it worth building inside Nova. Guard this like the pluck test.

**Stacking (per Cole's decision):** build **single now — Nova-core + exactly one specialist at a time** — but **design the manifest and equip interface so multiple specialists can stack later** (e.g. gaming+finance for "is this game worth the money"). Leaving the door open costs ~nothing now; retrofitting it is brutal. So: the equip interface should not *assume* exactly one specialist slot, even though the first implementation fills only one.

**Visual layer (Cole's product instinct, worth building in early):** each loadout has a distinct outfit/appearance, so the active adapter is **legible at a glance** — you always know which expert is loaded because you can see it. This is good UX hiding in a cool idea, and it ties into Nova's existing avatar work: a *visual* LoRA per specialist alongside the *knowledge* LoRA, switched together. The `visual` manifest field carries this. Not required for the chess plumbing test, but design the manifest to hold it from day one.

---

## 7. The equip mechanism — DEFERRED, and why

The equip mechanism (physically loading/unloading/stacking adapter weights on the running model) is **not specified here** and must not be built yet, because it rests on two things that don't exist or aren't verified:

1. **The runtime body layer must exist first.** Equipping is a bodily I/O act and lives in Nova's own runtime — the layer the runtime-extraction directive creates. Until that extraction lands, equip has no correct home. (Putting it in the chat server would reintroduce the exact bug that directive fixes.)

2. **One unverified fact gates the whole switch design:** *Can the inference stack (llama.cpp as currently used) hot-swap a LoRA adapter onto an already-running model, or does switching require a model reload?* This is unknown and must be checked against the actual stack — **do not assume from memory.** The answer changes the design fundamentally:
   - **If hot-swap is supported:** "equip loadout" is near-instant; switching is cheap; KoELS is elegant.
   - **If a reload is required:** switching is heavier (seconds, VRAM churn); the decision faculty should swap less eagerly, and the design must account for the cost (e.g. swap only on clear domain change, not speculatively).

**Action for Cowork Opus:** before the equip spec can be written, verify what the current inference stack supports for **runtime LoRA loading/stacking** on the dual-GPU setup. Report the finding. The equip mechanism gets specified on that fact — not before.

What you *can* build now without the equip mechanism: the folder structure (§4), the manifest schema (§5), and the **cognition-side loadout-decision faculty** (§3) — the pure logic that, given a task and the set of manifests, decides which loadout is wanted and whether to swap. That faculty can be built and unit-tested with no GPU and no runtime, because it only *decides*; it returns "equip gaming" as a decision, and the (future) runtime acts on it. This is the natural first KoELS deliverable and it's fully pluck-safe.

---

## 8. Build order — chess first, and the catch

**Order: chess → Clash Royale → DBD.** Each forces a harder version of perception; earn the complexity.

**Chess is the right first test — but know exactly what it tests.** Chess's ground truth is **Stockfish (an oracle)**. So for chess, Nova *consults the engine and explains it in her voice* — the gaming **LoRA barely matters**, because Stockfish is doing the strategy. Therefore:

- **Chess proves the PLUMBING:** the loadout-decision faculty fires → the (future) runtime equips the gaming loadout → the oracle (Stockfish) is consulted → Nova coaches in her own voice, with her memory of your games. It validates the *skeleton and the delivery*, cheaply, on Cole's desktop (Chess.com), with a deterministic correct answer to check against. That is exactly why it's the right *first* test.
- **Chess does NOT prove the LoRA works.** Whether the trained adapter actually makes her a better strategist is **not** tested by chess, because the engine supplies the strategy. The LoRA's real value gets proven later on **Clash Royale**, which has *no oracle* — there, her trained judgment is all there is.

So: **chess proves the plumbing; Clash proves the brain.** Build the skeleton against the easy oracle game first, then swap in the hard case. Do not conclude "the gaming LoRA works" from a successful chess test — that's a category error.

(Perception/FPS architecture for the live-coaching body part — compositor capture, cheap-CV-before-LLM, structured state objects, separate clocks — is its own spec, written when we build the live-coaching organ. Chess on Chess.com is the gentlest possible perception case and a fine starting point.)

---

## 9. What success looks like (chess milestone)

Nova, on Cole's desktop while he plays Chess.com:
1. Recognizes the task needs the gaming loadout (decision faculty, pure).
2. Her runtime equips Nova-core + gaming specialist (deferred mechanism).
3. She reads the board state, consults Stockfish (oracle), and coaches Cole **in her own voice, with her own memory** — degraded to nothing of her identity.
4. Taking the loadout off, she is fully herself again, with memory of the session intact.

If steps 1, 3, and 4 work and identity/voice/memory are preserved throughout, the *plumbing* is proven and we move to Clash to prove the *brain*.

---

## 10. Open items (in order)

1. **Runtime extraction lands** (separate directive) — unblocks equip's home.
2. **Verify llama.cpp runtime-LoRA capability** (§7) — unblocks the equip spec.
3. **Build the buildable-now parts:** manifest schema, folder structure, pure loadout-decision faculty.
4. **Write the equip spec** on the verified facts (post-1, post-2).
5. **Chess plumbing test** → then **Clash brain test.**
