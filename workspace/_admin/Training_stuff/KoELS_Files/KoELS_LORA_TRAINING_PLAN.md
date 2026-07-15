# KoELS Specialist LoRAs — Training Plan
_Last updated: 2026-07-15 17:41:29_

How the gaming + finance specialist adapters get built. The good news: **the pipeline is identical
to Nova-core's** — nothing new to build, just new datasets. Once Nova-core finishes training on
RunPod, these slot into the exact same flow.

---

## What's done vs what's pending

**Done (ready):**
- `koels_gaming_lora_dataset_spec.md` — the gaming training target (durable strategy, no dated facts).
- `koels_finance_lora_dataset_spec.md` — the finance training target (durable method, no dated numbers).
- The manifests already exist (`gaming.json`, `finance.json`) and the decision faculty is built/tested
  (`decision.py`, `keyword.py`, `manifest.py`, `test_koels.py`) — so the *runtime contract* the
  adapters plug into is settled.

**Pending (gated on your sign-off):**
- Generating the two datasets (~280 examples each) — held until you approve the specs, exactly like
  Nova-core went spec → approve → batches → train. I don't want to mass-produce 560 examples in the
  wrong voice.
- Training each adapter (RunPod, same as Nova-core).

---

## The pipeline (same as Nova-core — reuse everything)

For each specialist, once its dataset markdown batches exist:

1. **Convert** → `python convert_dataset.py` (point it at the specialist's batches) → `*.jsonl`.
2. **Train** → `train_nova_lora.py` with two edits: `DATA_PATH` → the specialist jsonl, and
   `OUTPUT_DIR` → e.g. `gaming_lora_out`. Same base (Qwen 3.6 27B), same QLoRA/bf16, same A100 on
   RunPod. ~280 examples trains in minutes.
3. **Convert adapter → GGUF** → `convert_lora_to_gguf.py` → drop at the manifest's `adapter` path
   (`KoELS/gaming/adapter/gaming.gguf`, `KoELS/finance/adapter/finance.gguf`).
4. **Equip** via the KoELS runtime (`koels_equip.py`) — add to the boot `--lora` roster; one llama
   restart adds it, then switching is free (per the verified llama.cpp finding).

No new training infrastructure. The Nova-core run is the dress rehearsal for these.

---

## Hard line: what does NOT go in these LoRAs

Per the KoELS core law, the adapters are **reasoning only**. The volatile facts — current card
stats, this patch's meta, live prices, today's earnings — are **NOT trained**; they go into each
expert's `knowledge.lancedb`, written by the **updater** (a separate, later piece), patch/date
tagged. Training a single dated fact into the adapter reintroduces the exact confident-hallucination
problem the whole split exists to kill. The datasets must stay ruthlessly method-only.

---

## Build order (from KoELS design §8)

- **Nova-core first** (in progress) — her identity adapter is the always-loaded base everything
  stacks on. Nothing else matters until she's herself in the weights.
- **Then specialists.** Of the two, **gaming** is the first integration target because chess is the
  cheapest plumbing test — but note the catch: **chess proves the *plumbing* (it uses Stockfish as
  the oracle), Clash Royale proves the *brain*.** So a successful chess coaching session validates
  the equip/decision/voice skeleton, NOT that the gaming LoRA's judgment is good. The adapter's real
  value gets tested on Clash (no oracle). Worth remembering so we don't over-conclude from chess.

---

## Decisions I need from you before generating the datasets

1. **The voice fork (biggest one):** I've specced these as **method-focused / light-personality** so
   the specialist doesn't fight Nova-core's voice when stacked (Invariant 2: "the specialist supplies
   expertise, never the voice"). Confirm that's right, or say you want some Nova flavor baked in.
2. **Counts / band weighting** — ~280 each; adjust if you want gaming weighted more toward one game,
   or finance heavier on the discipline bands.
3. **Order** — generate gaming first (since it's the first integration target), or both together?

Approve the two specs and I'll produce the batches the same way we did Nova-core, then they train on
the same RunPod setup.
