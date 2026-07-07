# Nova-Core v3 retrain — runbook
_Last updated: 2026-07-08 08:56:41_
_2026-07-06. The v3 fix = corrected config (rank 16 / α32 / 2 epochs / LR 1e-4, max_length 4096) +
reworked dataset (v2's 108 kept + multi-turn + autonomy-continuation + sustained-wake + register).
Goal: coherent AND in character at LoRA weight **1.0** — no dilution needed._

## Files to upload to the pod `/workspace/` (three — ONLY these three)
- `nova_core_v2.jsonl`              — your 108 v2 examples (unchanged), from `../v2/`
- `nova_core_v3_additions.jsonl`    — the 59 new examples (this folder)
- `train_nova_lora_v3.py`           — the corrected script (this folder)

**Do NOT upload/merge `nova_core_v3_autonomy.jsonl` or `nova_core_v3_autonomy_sustained.jsonl`** —
they are build-stage components already folded into `..._additions.jsonl`; concatenating them too
would double-train those rows.

## 0. Verify-first gates (before spending on a full run)
1. **Base repo id** — the script uses `unsloth/Qwen3.6-27B`. Confirm that's the exact base the live GGUF
   was converted from, or the adapter won't apply cleanly when KoELS equips it.
2. **MTP smoke test** — Qwen 3.6 uses multi-token prediction; its interaction with LoRA train→convert→
   infer is unverified. Do a throwaway tiny run first (≈20 examples, 1 epoch) → convert → load in
   llama.cpp → confirm it applies and generates coherently at scale 1.0. Only then commit the full run.
3. Pod balance — top up before the full run (A100 ≈ $1.51/hr; the base re-download may be needed since
   `/root/hf` is ephemeral and the pod restarted).

## 1. Pod
A100 SXM 80GB, PyTorch 2.8, ~150GB on `/workspace`. (`/workspace` persists; `/root`, `/` are wiped on stop.)

## 2. Merge the dataset on the pod (one line — avoids any local file-sync issues)
```
cd /workspace
cat nova_core_v2.jsonl nova_core_v3_additions.jsonl > nova_core_v3.jsonl
wc -l nova_core_v3.jsonl        # expect 167
```

## 3. Deps
```
export HF_HOME=/root/hf           # ephemeral overlay — avoids the volume-quota error
export HF_HUB_ENABLE_HF_TRANSFER=1
export HF_TOKEN=<your token>      # keep it in the terminal, don't paste it to chat
pip install -U transformers peft trl accelerate datasets sentencepiece hf_transfer
```

## 4. Train
```
cd /workspace && python train_nova_lora_v3.py 2>&1 | tee train_v3.log
```
- 167 examples × 2 epochs — fast on an A100. `save_strategy="epoch"` → `nova_core_v3_out/checkpoint-*`.
- **Loss masking:** the script tries `assistant_only_loss=True` (loss on Nova's turns only — keeps
  the long wake-prompt boilerplate out of the gradient) and prints which mode it's in. If TRL/the
  Qwen template can't support it, it falls back to full-sequence loss (v2 behavior) on its own.
  **If the first logged loss is ~0.0, the mask is degenerate — rerun with `NOVA_ASSISTANT_ONLY=0`.**
- Watch the loss: with the lower rank/LR it should descend gently, not dive. The keeper is the last
  epoch **before** it flattens — likely epoch 1 or 2. This is why we only do 2 and A/B them.

## 5. Convert both epochs to GGUF (A/B them)
```
cd /workspace
pip install -U "transformers>=5.12"
git clone https://github.com/ggml-org/llama.cpp 2>/dev/null; true
hf download unsloth/Qwen3.6-27B config.json --local-dir base
for c in $(ls -d nova_core_v3_out/checkpoint-* | sort -t- -k2 -n | tail -2); do
  python llama.cpp/convert_lora_to_gguf.py "$c" --base base \
    --outfile "nova_core_v3_$(basename "$c").gguf" --outtype f16
done
ls -la nova_core_v3_*.gguf
```

## 6. Download both `nova_core_v3_*.gguf` to the PC.

## 7. Equip + A/B (local — the real test)
- Drop the GGUFs into `models\qwen3.6\`.
- Point `nova_start.py` / `start_llama_qwen36.cmd` Nova-core `--lora-scaled` at one — **start at `:1.0`,
  not 0.6.** The whole point of v3 is it holds at full strength.
- Restart, then run the 06-22 harness (Claude-in-Chrome, fresh session): 12+ varied turns for
  loops/stalls/grammar, autonomy-on idle test. **New v3 checks:** force mid-conversation topic shifts,
  and an autonomy-continuation sequence (prior reflection → must advance, must not one-and-done).
- **Accept** the epoch that's coherent AND in character at weight 1.0. If the best still needs <1.0,
  it's over-trained → drop LR/epochs or rebalance and re-run.

## Notes
- `nova_core_v3_additions.jsonl` composition (59): 20 conversational multi-turn, 22 autonomy
  (paraphrased wake frame; 14 single + 8 chained), 9 register-variety, **+8 verbatim-frame
  autonomy examples (added 2026-07-07):** full `executive.py build_reflection` frames matched to
  the live runtime (stamp line, RECENT CONVERSATION, "Where your last reflection left off" +
  MUST-move, task board, journal + closing paragraphs), covering change/interval/cole wake
  reasons, 2 verbatim sustained chains, and 1 decision-phase REQUIRED-reply example
  (`build_decision` cole_pending branch). These close the train/inference frame gap flagged in
  `memory/reports/V3_TRAINING_REVIEW_2026-07-07.md`. No file/task names baked in — durable
  behavior only.
- Autonomy is framed as **existing and deciding**, not task-seeking, and models **sustained** wakes
  (think → act → notice → wind down by choice) so she doesn't answer once and flatline.
