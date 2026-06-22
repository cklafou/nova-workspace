# Nova-Core v2 retrain — RunPod runbook (gotchas pre-solved)
_Last updated: 2026-06-22 09:49:11_

Same flow that produced v1, with the v2 dataset (r=64). Cole drives the terminal + spend; paste
outputs back and I'll guide each step.

## 0. Pod
- **A100 SXM 80GB**, template **PyTorch 2.8**, ~150GB volume on `/workspace`.
- Remember: `/workspace` is persistent; container disk (`/root`, `/`) is EPHEMERAL (wiped on
  stop/restart). Put the big HF cache on the ephemeral overlay for space, keep outputs on `/workspace`.

## 1. Upload these two files to the pod (`/workspace/`)
- `nova_core_v2.jsonl`
- `build/train_nova_lora.py`
(JupyterLab upload, or `hf`/scp — whatever's easiest.)

## 2. Environment (paste in a terminal)
```
cd /workspace
export HF_HOME=/root/hf            # big ephemeral overlay → avoids the 50GB volume-quota error we hit
export HF_HUB_ENABLE_HF_TRANSFER=1
export HF_TOKEN=<your token>       # keep it in your terminal; do NOT paste it to me
pip install -U transformers peft trl accelerate datasets sentencepiece hf_transfer
```

## 3. Train
```
cd /workspace && python train_nova_lora.py
```
- ~108 examples × 4 epochs ≈ 50-ish steps; fast on an A100. Watch the loss.
- `save_strategy="epoch"` → checkpoints land in `nova_core_v2_out/checkpoint-*` (one per epoch).
- v1 overfit by epoch 3 and we used epoch-2. With fewer examples + higher rank here, watch for the
  loss diving too fast — the keeper is the last epoch BEFORE it flattens/overfits (likely 2 or 3).

## 4. Convert the chosen checkpoint to GGUF
```
cd /workspace
pip install -U "transformers>=5.12"            # newer transformers needed for the Qwen3.6 convert
git clone https://github.com/ggml-org/llama.cpp 2>/dev/null; true
hf download unsloth/Qwen3.6-27B config.json --local-dir base   # arch metadata only (explicit filename)
python llama.cpp/convert_lora_to_gguf.py nova_core_v2_out/checkpoint-<N> --base base --outfile nova_core_v2.gguf --outtype f16
```

## 5. Download `nova_core_v2.gguf` to the PC, then TERMINATE the pod.

## 6. Equip (local)
- Drop `nova_core_v2.gguf` into `models\qwen3.6\`.
- Point the launcher at it: in `nova_start.py` / `start_llama_qwen36.cmd`, the Nova-core `--lora` line
  currently names `nova_core_v2_e2.gguf` — change to `nova_core_v2.gguf` (I'll do this edit).
- Restart, then A/B vs v1, and sweep the weight box (1.0 → 1.4) to find v2's sweet spot.
