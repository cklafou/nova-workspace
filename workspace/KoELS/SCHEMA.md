# KoELS — Manifest Contract (v1)
_Last updated: 2026-07-15 23:14:48_
_Knowledge of Experts Loadout System. One `manifest.json` per expert under `KoELS/<name>/`.
An expert is a drop-in folder: add `KoELS/legal/` with a manifest + adapter + DB and Nova can
equip it — no code change. This contract is the interface her loadout-decision faculty reads._

## Folder layout (one self-contained folder per expert)
```
KoELS/
  SCHEMA.md                  # this contract
  <name>/
    manifest.json            # the contract below — what this expert IS
    adapter/<name>.gguf      # durable LoRA weights (trained on cloud → convert to GGUF)
    knowledge.lancedb/       # volatile facts (written by the updater; NEVER baked into weights)
    visual/                  # optional: the loadout's outfit/appearance ref
```

## The design law every expert obeys
**Weights = durable expertise** (how to reason in the domain — doctrine, theory, judgment, voice).
**Retrieval = anything with a date on it** (patch notes, stats, prices, current meta) — lives in
`knowledge.lancedb`, never trained into the adapter. Training facts into weights is forbidden:
it forces a retrain every patch and produces confident hallucination.

## manifest.json fields
| Field | Req | Meaning |
|---|---|---|
| `name` | ✓ | short id, matches the folder (e.g. `gaming`) |
| `domain` | ✓ | what this expert is for (human-readable) |
| `trigger` | ✓ | how cognition recognizes a task needs this loadout: `{keywords:[], intents:[]}`. Routing matches against this; the *decision* stays in cognition. |
| `adapter` | ✓ | path/ref to the LoRA GGUF (the durable brain) |
| `knowledge_db` | ✓ | path/ref to this expert's LanceDB namespace (volatile facts) |
| `oracle` | – | external ground-truth tool this expert consults instead of reasoning from weights: `{name, applies_to:[], how}`. e.g. chess → Stockfish. If present, the expert *consults and explains* the oracle for that sub-domain. |
| `fusion_mode` | ✓ | how expertise attaches. `adapter` (LoRA on Nova-core) is the only mode built first; the field exists so `oracle_tool`/`external_model` slot in later with no schema change. |
| `visual` | – | the loadout's outfit/appearance ref, so the active expert is legible at a glance (a visual LoRA switched together with the knowledge LoRA). |

## Two invariants (guard like the pluck test)
1. **Nova-core is always loaded underneath.** A specialist is equipped *on top of* her core
   identity/personality/memory — minimum two-deep (core + specialist). She never stops being herself.
2. **Identity + memory are always hers; the specialist supplies expertise, never the voice.** A
   loadout that strips her voice/memory has destroyed the only reason to route through Nova.

## Equip cost (two speeds — set by the verified llama.cpp finding)
- **Instant** — equip / unequip / blend *within the already-loaded set* (`POST /lora-adapters`
  scale, or per-request `lora`). No reload.
- **Heavy (self-restart, ~30–60s dark)** — rotate *which* specialists are loaded (adapters can
  only be added at boot `--lora`). Deliberate, Nova-aware, never mid-reply.

Her decision faculty (cognition) labels a wanted loadout `instant` (in the loaded set) vs
`restart` (on disk, not loaded) so she swaps eagerly when free and only self-restarts on a clear,
worth-it domain change. Stacking (core + multiple specialists) is supported at the runtime layer;
the first implementation fills one specialist slot but the interface doesn't assume exactly one.
