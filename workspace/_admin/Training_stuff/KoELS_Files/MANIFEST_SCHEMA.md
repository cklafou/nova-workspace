# KoELS Manifest — The Expert Contract
_Last updated: 2026-07-15 17:41:52_

_Defines what one expert loadout IS. Filling this out is how you add an expert — drop a folder with a `manifest.json`, never edit Nova's code. This is the load-bearing piece that makes KoELS a **system** instead of hardcoded specialists._

## Folder layout (per expert)

```
KoELS/
  gaming/
    manifest.json          # this contract
    adapter/gaming.gguf     # the trained LoRA (DURABLE expertise/reasoning)
    knowledge.lancedb/      # VOLATILE facts (updater-maintained, patch-tagged)
    visual/gaming_outfit... # optional: the loadout's "outfit" (visual LoRA)
  finance/
    manifest.json
    adapter/finance.gguf
    knowledge.lancedb/
```

**Core law:** the *adapter* holds durable how-to-reason expertise; the *knowledge_db* holds anything with a date on it. Never bake volatile facts into the adapter — that's the confident-hallucination failure the whole split exists to prevent.

## Fields

| Field | Required | Meaning |
|---|---|---|
| `name` | yes | Unique id, lowercased (e.g. `"gaming"`). How the faculty/runtime refer to the loadout. |
| `domain` | yes | Human-readable description of what this expert is for. |
| `triggers` | yes | List of terms the keyword router matches against. Single words match whole tokens (`"game"` ≠ "gamer"); multi-word entries (`"clash royale"`) match as substrings. List plural/variant forms explicitly. |
| `adapter` | yes¹ | Path/ref to the LoRA GGUF (the durable brain). Required for `fusion_mode: adapter`. |
| `knowledge_db` | no | LanceDB namespace path for this expert's volatile facts. `null`/omit for pure-reasoning experts. |
| `fusion_mode` | no | `adapter` (default — LoRA on Nova-core), `oracle_tool` (expertise from an external tool), or `external_model` (separate model). |
| `oracle` | no² | `{ kind, invoke, notes }` — an external ground-truth tool. Required if `fusion_mode: oracle_tool`. An adapter-mode expert may *also* declare an oracle for a sub-domain (e.g. gaming uses Stockfish for chess only). |
| `visual` | no | Path/ref to the loadout's appearance (visual LoRA) — switched together with the knowledge adapter so the active expert is legible at a glance. |
| `trigger_weights` | no | Map of `term -> weight` (default 1.0). Give primary terms higher weight so a single strong hit can clear the confidence bar. |
| `priority` | no | Tiebreaker (default 1.0) when two experts score equally. |
| `notes` | no | Freeform. |

¹ Required when `fusion_mode` is `adapter`. ² Required when `fusion_mode` is `oracle_tool`.

## Fusion modes

- **`adapter`** (default, the KoELS norm) — a LoRA stacked on Nova-core. She stays herself, gains the specialty on top.
- **`oracle_tool`** — expertise comes from an external ground-truth tool the runtime calls; Nova consults and *explains* it rather than reasoning from weights. Use when the domain has a deterministic source better than any LLM (chess → Stockfish).
- **`external_model`** — a separate full model consulted and relayed. Rare; for domains needing reasoning beyond the base.

## How the decision faculty uses this

The pure-logic faculty (`koels/decision.py`) takes a task + the loaded manifests and returns a `LoadoutDecision` (EQUIP / STAY / UNEQUIP a specialist on top of always-present Nova-core). It does **not** load anything — the runtime acts on the decision. Routing is autonomous via a swappable `DecisionStrategy` (keyword today, model-judged later) and Cole can override manually; a manual override always wins.

## Adding a new expert (e.g. legal)

1. `mkdir KoELS/legal/`
2. Train the legal LoRA → convert to GGUF → `KoELS/legal/adapter/legal.gguf`
3. (If it has volatile facts) point `knowledge_db` at `KoELS/legal/knowledge.lancedb` and let the updater fill it
4. Write `KoELS/legal/manifest.json` filling the contract above
5. Done — the faculty picks it up from the manifest set; **one llama restart** to add it to the preloaded adapter roster (per the verified llama.cpp finding), then switching to it is free.
