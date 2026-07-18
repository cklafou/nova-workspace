#!/usr/bin/env bash
# run_on_pod.sh — the entire v6 training pipeline, one command, ON THE POD.
#
# WHY THIS EXISTS: v5 was run by hand, step by step, over the pod terminal. That's fine when
# someone's driving, but it meant "train v6" secretly depended on a human being awake to type
# each step. This collapses it to one script so the human's only job is: start a pod, get the
# files onto it, run this. Then download two GGUFs. That's the whole handoff.
#
# WHAT ONLY COLE CAN DO (hard blockers for me, by design):
#   1. Start a RunPod pod  — it's a paid GPU on your account behind your login. I don't
#      enter credentials and I don't spin up paid resources. This is the real gate.
#   2. HF auth for the base model — `huggingface-cli login` or HF_TOKEN, your token, not mine.
#
# EVERYTHING ELSE is automated below. Once the pod exists and I can reach its terminal, I can
# run this myself (exactly like v5's "pod is running, go for it").
#
# ── LESSONS FROM v5, baked in so we don't relearn them ───────────────────────────────
#   • Put the HF cache on the pod's LOCAL disk, not /workspace (MooseFS network FS = 90-min
#     model load; local NVMe = 9 seconds). HF_HOME below points at local.
#   • The mask gate is not optional. If mk_template's GATE B fails, STOP — training on a broken
#     mask teaches her to hallucinate her own evidence. `set -e` makes any failure abort.
#   • Convert BOTH epochs. v5's acceptance notes say epoch-1 can beat epoch-2 (2 epochs on a
#     warm-heavy corpus can overfit toward agreeableness). We want both to test.
set -euo pipefail

cd "$(dirname "$0")"
BASE_MODEL="unsloth/Qwen3.6-27B"
LLAMA_CPP="${LLAMA_CPP:-/workspace/llama.cpp}"   # override if it lives elsewhere on the pod
export HF_HOME="${HF_HOME:-/root/.cache/huggingface}"   # LOCAL disk, not /workspace

echo "=== [1/4] deps ==="
pip install -q -U "transformers>=4.44" "trl>=0.9" peft datasets accelerate "jinja2>=3.1" sentencepiece

echo "=== [2/4] mask gate (mk_template) — ABORTS on failure, by design ==="
python mk_template.py            # writes qwen_template_gen.jinja; GATE A + GATE B must pass

echo "=== [3/4] train (bs=1, ga=8, 2 epochs — identical config to v5) ==="
python train_nova_lora_v6.py     # -> nova_core_v6_out/checkpoint-*/  (adapter per epoch)

echo "=== [4/4] convert BOTH epochs to GGUF ==="
if [ ! -f "$LLAMA_CPP/convert_lora_to_gguf.py" ]; then
  echo "FATAL: llama.cpp not found at $LLAMA_CPP — set LLAMA_CPP=/path/to/llama.cpp and re-run." >&2
  exit 1
fi
mkdir -p gguf_out
n=0
for ckpt in nova_core_v6_out/checkpoint-*; do
  n=$((n+1))
  out="gguf_out/nova_core_v6_epoch${n}.gguf"
  echo "  converting $ckpt -> $out"
  python "$LLAMA_CPP/convert_lora_to_gguf.py" "$ckpt" --base "$BASE_MODEL" --outfile "$out"
  # verify bytes actually landed — a convert that writes nothing is the exact silent-drop bug
  sz=$(stat -c%s "$out" 2>/dev/null || echo 0)
  [ "$sz" -gt 1000000 ] || { echo "FATAL: $out is $sz bytes — conversion produced nothing." >&2; exit 1; }
  echo "  OK: $out ($((sz/1024/1024)) MB)"
done

echo
echo "=== v6 TRAINING COMPLETE ==="
echo "Download these to models/qwen3.6/ on Cole's machine, then point active_lora.txt at one:"
ls -la gguf_out/*.gguf
echo
echo "Then locally:  echo '--lora-scaled models\\qwen3.6\\nova_core_v6_epoch2.gguf:1.0' > memory/active_lora.txt"
echo "and restart the stack. Test with _admin/Training_stuff/v6/acceptance_v6 (blind — no coaching)."
