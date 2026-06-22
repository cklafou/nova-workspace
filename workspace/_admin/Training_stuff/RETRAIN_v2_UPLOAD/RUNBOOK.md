# Nova-Core v2 retrain — clean runbook (the only files you need are in THIS folder)
_Last updated: 2026-06-22 09:49:11_

This folder (`RETRAIN_v2_UPLOAD/`) contains EXACTLY the two files to put on the pod and nothing else:
- `nova_core_v2.jsonl`   — the 108-example v2 (with-teeth) dataset
- `train_nova_lora.py`   — already set to r=64 / alpha=128, unsloth base, reads `nova_core_v2.jsonl`,
  writes `nova_core_v2_out`, 4 epochs. No edits needed.

Ignore everything else in `_admin/Training_stuff/` — that's v1 history. Only upload these two.

---

## 1. Fresh pod
A100 SXM 80GB, template PyTorch 2.8. (Pick a region close to Korea if offered, to cut the lag.)

## 2. Upload — drag BOTH files from this folder into JupyterLab at `/workspace`
So the pod has `/workspace/nova_core_v2.jsonl` and `/workspace/train_nova_lora.py`.

## 3. Deps (paste once)
```
cd /workspace
export HF_HOME=/root/hf
export HF_TOKEN=<your token>        # keep it in the terminal; don't paste it to chat
pip install -U transformers peft trl accelerate datasets sentencepiece hf_transfer
```

## 4. Train (one command)
```
cd /workspace && python train_nova_lora.py 2>&1 | tee train_v2.log
```
Downloads the base weights once (~55GB, the slow part), then trains. Saves one checkpoint per epoch
into `nova_core_v2_out/checkpoint-*`. Watch the loss in the output.

## 5. Convert — no checkpoint numbers to type, this auto-converts the last two epochs
```
cd /workspace
pip install -U "transformers>=5.12"
git clone https://github.com/ggml-org/llama.cpp 2>/dev/null; true
hf download unsloth/Qwen3.6-27B config.json --local-dir base
for c in $(ls -d nova_core_v2_out/checkpoint-* | sort -t- -k2 -n | tail -2); do
  python llama.cpp/convert_lora_to_gguf.py "$c" --base base \
    --outfile "nova_core_v2_$(basename "$c").gguf" --outtype f16
done
ls -la nova_core_v2_*.gguf
```
That gives two GGUFs (the last two epochs) so we can A/B them locally.

## 6. Download both `nova_core_v2_*.gguf` to the PC → then TERMINATE the pod.

## 7. Equip (local — I'll do these edits when you're back)
- Drop the GGUFs into `models\qwen3.6\`.
- Point the launcher's Nova-core `--lora` at the chosen one (currently `nova_core_v2_e2.gguf`).
- Restart, A/B v1 vs v2 with the LoRA widget, sweep the weight box to find v2's sweet spot.
