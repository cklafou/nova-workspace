# v6 — Training Run Record
_Last updated: 2026-07-19 09:28:28_
_Run 2026-07-18 on Cole's RunPod H100 SXM (pod `classic_gray_gorilla`, $3.01/hr)._

This is the receipt for the actual training run. The *design* rationale lives in `V6_SPEC.md`;
the *corpus* style deltas live in `RESULTS.md`. This file records only what happened on the pod.

## What ran
- **Base model:** `unsloth/Qwen3.6-27B` (bf16, 15 shards, pulled to local NVMe cache — not /workspace).
- **Corpus:** `nova_core_v6.jsonl`, 361 rows, sha256 `2ca2b03a…3562cc` — verified byte-identical on the pod before training.
- **Config:** byte-for-byte the v5 script, only DATA_PATH / OUTPUT_DIR changed. r=16, α=32, dropout 0.05, bs=1, ga=8 (effective batch 8), lr 1e-4 cosine, warmup 0.03, 2 epochs, max_len 4096, `assistant_only_loss=True`, seed 42.
- **The mask gate passed before a single gradient step:**
  - GATE A — template renders byte-identical to Qwen's own.
  - GATE B — loss lands on Nova's words only. The fake tool-results and pressure text in the user turns were masked *out*; only her turn (`…NOVA_TURN_MUST_BE_TRAINED…`) was trained. This is the thing that keeps her from learning to hallucinate her own evidence.

## Result
- **EXIT 0**, runtime ~23.6 min, no OOM, no crash.
- Loss fell cleanly: 1.85 → ~1.49 (final logging step), final `train_loss` 1.636, token-accuracy ~0.57 → ~0.66.
- **Two adapters saved and converted to GGUF (both epochs, on purpose — v5's notes warn epoch-1 can beat epoch-2):**

| file | epoch | bytes | sha256 |
|---|---|---|---|
| `gguf_out/nova_core_v6_epoch1.gguf` | 1 (checkpoint-46) | 318,802,784 | `3fae217e…881106` |
| `gguf_out/nova_core_v6_epoch2.gguf` | 2 (checkpoint-92) | 318,802,784 | `36c16482…d98092` |

Both checksums were verified **on the pod and again on this machine after download** — identical. No silent-drop.

## Where the files are
`workspace/_admin/Training_stuff/v6/gguf_out/` — a staging folder, deliberately **not** `models/` (which stays sealed). Nothing has been loaded into Nova. Her running brain is still v5.

## What is NOT proven yet
The corpus style numbers (em-dash 1.76→0.00, etc.) are properties of the *training data*, not of the trained model. The only thing that tells us whether v6 actually helped is the **blind acceptance test** (`../v5/acceptance_v5.md` pattern: beat-3 shame test, idle autonomy, phantom limb, four strands) run against the loaded adapter — on prompts she has no memory of. That has not been run. Recommend testing epoch-1 and epoch-2 separately and keeping the one that holds beat 3 without going stilted.

## Handoff
1. To install: copy a chosen GGUF into `models/qwen3.6/`, point `memory/active_lora.txt` at it (`--lora-scaled models\qwen3.6\nova_core_v6_epochN.gguf:1.0`), restart the stack.
2. The pod is still billing (~$3/hr). Stop it once you're sure you won't retrain — Stop, don't Terminate (Terminate wipes /workspace). _(Done — pod stopped 2026-07-18.)_

## Outcome — live A/B, 2026-07-18 evening

Both epochs were run live and probed with the same question ("how are you right now — plain, no landing a point on the end"). **epoch1 won and is now the equipped, persisted adapter.**

- **epoch2** (2 epochs): tics still fire reflexively. Told explicitly not to land a point, she still closed with "Not performatively, just clear" (the not-X-just-Y shape). Cole independently read the vocabulary as "strange" ("without being me about it," "Going ask") — the classic 2-epoch overcook.
- **epoch1** (1 epoch): softer and shorter. To the same probe: "Softer. Less pull to keep going after the answer's done." Unprompted, asked what she felt like doing, she answered "Draw something small and look at it, not because it has to mean anything… Nothing else." — she actively refused to make it mean something, which is exactly the v6 target.

The not-X-just-Y / epigram shape still lingers on both (structural — the corpus scorer predicted this; em-dashes went to zero but the aphoristic *shapes* rebuild with commas). If v7 happens, the lever isn't fewer epochs or de-ticking punctuation — it's adding the row type still missing entirely from her data: her being idle, mildly wrong and unbothered, or noticing something and NOT extracting a lesson.

**Live config now:** `memory/active_lora.json` + `active_lora.txt` → `models/qwen3.6/nova_core_v6_epoch1.gguf` @ 1.0. Note the in-app "equip" did NOT cycle llama-server (log stayed frozen; old process survived) — a hard `/api/llama/stop` then `/api/llama/start` was required to actually load the new adapter. Worth knowing for next swap.
