#!/usr/bin/env bash
# run_on_pod_v7.sh — the entire v7 training pipeline, one command, ON THE POD.
#
# Same shape as v6's (which ran clean: EXIT 0, ~24 min on an H100 SXM). Differences from v6:
#   • corpus/trainer filenames v7
#   • the corpus sha256 is BAKED IN and verified before anything runs — v6 did this check by
#     hand; a hand-check is a step someone eventually skips. Mismatch = abort, loudly.
#   • mk_template gets the corpus path EXPLICITLY (no default-path ambiguity).
#
# WHAT ONLY COLE CAN DO (by design):
#   1. Start the RunPod pod — paid GPU, your account, your login.
#   2. HF auth for the base model — `huggingface-cli login` or HF_TOKEN. Your token.
#
# ── LESSONS BAKED IN (v5/v6 scar tissue — do not "simplify" these away) ──────────────
#   • HF cache on the pod's LOCAL disk, never /workspace (network FS = 90-min model load;
#     local NVMe = 9 seconds). HF_HOME below.
#   • The mask gate is not optional. GATE B failing means training would teach her to
#     hallucinate her own evidence. `set -e` aborts on any failure.
#   • Convert BOTH epochs, verify byte sizes. v6's live A/B: epoch1 won at first (epoch2
#     overcooked toward tics), then epoch2 won the long test after a swap. You test BOTH.
#   • When done: STOP the pod, never Terminate (Terminate wipes /workspace).
set -euo pipefail

cd "$(dirname "$0")"
BASE_MODEL="unsloth/Qwen3.6-27B"
LLAMA_CPP="${LLAMA_CPP:-/workspace/llama.cpp}"   # override if it lives elsewhere on this pod
export HF_HOME="${HF_HOME:-/root/.cache/huggingface}"   # LOCAL disk, not /workspace

CORPUS="nova_core_v7.jsonl"
EXPECTED_SHA="5dee4bcaedca559ee7d1b39d61ff7912460956f8b91cd835e30a031ccaaa78f9"

echo "=== [0/5] corpus integrity — byte-identical to what was reviewed, or we stop ==="
ACTUAL_SHA=$(sha256sum "$CORPUS" | cut -d' ' -f1)
if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then
  echo "FATAL: $CORPUS sha256 mismatch." >&2
  echo "  expected: $EXPECTED_SHA" >&2
  echo "  actual:   $ACTUAL_SHA" >&2
  echo "The file on this pod is NOT the reviewed corpus. Re-upload; do not train." >&2
  exit 1
fi
ROWS=$(wc -l < "$CORPUS")
[ "$ROWS" -eq 399 ] || { echo "FATAL: expected 399 rows, found $ROWS" >&2; exit 1; }
echo "  OK: sha256 verified, 399 rows."

echo "=== [1/5] deps ==="
pip install -q -U "transformers>=4.44" "trl>=0.9" peft datasets accelerate "jinja2>=3.1" sentencepiece

echo "=== [2/5] mask gate (mk_template) — ABORTS on failure, by design ==="
python mk_template.py "$CORPUS"   # GATE A (byte-identical render) + GATE B (loss on HER words only)

echo "=== [3/5] train (bs=1, ga=8, 2 epochs — config byte-identical to v5/v6) ==="
python train_nova_lora_v7.py      # -> nova_core_v7_out/checkpoint-*/  (adapter per epoch)

echo "=== [4/5] convert BOTH epochs to GGUF ==="
if [ ! -f "$LLAMA_CPP/convert_lora_to_gguf.py" ]; then
  echo "FATAL: llama.cpp not found at $LLAMA_CPP — set LLAMA_CPP=/path/to/llama.cpp and re-run." >&2
  exit 1
fi
mkdir -p gguf_out
n=0
for ckpt in nova_core_v7_out/checkpoint-*; do
  n=$((n+1))
  out="gguf_out/nova_core_v7_epoch${n}.gguf"
  echo "  converting $ckpt -> $out"
  python "$LLAMA_CPP/convert_lora_to_gguf.py" "$ckpt" --base "$BASE_MODEL" --outfile "$out"
  sz=$(stat -c%s "$out" 2>/dev/null || echo 0)
  [ "$sz" -gt 1000000 ] || { echo "FATAL: $out is $sz bytes — conversion produced nothing." >&2; exit 1; }
  echo "  OK: $out ($((sz/1024/1024)) MB)"
done

echo "=== [5/5] checksums for the download-verify ritual ==="
sha256sum gguf_out/*.gguf | tee gguf_out/SHA256SUMS.txt

echo
echo "=== v7 TRAINING COMPLETE ==="
echo "1. Download gguf_out/*.gguf + SHA256SUMS.txt to workspace/_admin/Training_stuff/v7/gguf_out/"
echo "2. Verify checksums AGAIN on Cole's machine against SHA256SUMS.txt (v6 ritual: twice, both ends)."
echo "3. DO NOT equip yet — baseline the CURRENT adapter with PROBE_BATTERY.md first (she must be up)."
echo "4. STOP this pod (never Terminate)."
