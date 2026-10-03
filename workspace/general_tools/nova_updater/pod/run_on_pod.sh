#!/usr/bin/env bash
# @nova: The whole LoRA training pipeline ON the pod, one command: verify inputs, prove the mask, train, convert every epoch to GGUF, checksum.
#
# Generalised from _admin/Training_stuff/v7/run_on_pod_v7.sh (ran clean on an H100 SXM in ~25 min).
# Everything job-specific comes from job.json, written by the updater. Lessons kept on purpose:
#   * HF cache on the pod's LOCAL disk, never /workspace (network FS = 90-minute model load).
#   * The mask gate is not optional; `set -e` aborts on any failure.
#   * Convert EVERY epoch and verify sizes; A/B both locally (v6: epoch1 won first, epoch2 won long).
#   * When done the updater STOPS the pod. Never Terminate (it wipes /workspace).
set -euo pipefail
cd "$(dirname "$0")"
export HF_HOME="${HF_HOME:-/root/.cache/huggingface}"
LLAMA_CPP="${LLAMA_CPP:-/workspace/llama.cpp}"
BASE_MODEL=$(python3 -c 'import json;print(json.load(open("job.json"))["base_model_id"])')
OUT_NAME=$(python3 -c 'import json;print(json.load(open("job.json"))["output_name"])')
echo "=== [0/5] inputs are byte-identical to what was reviewed ==="
sha256sum -c inputs.sha256
python3 - <<'EOF'
import json
job = json.load(open("job.json"))
for d in job["data"]:
    rows = sum(1 for line in open(d["name"], encoding="utf-8") if line.strip())
    assert rows == int(d["rows"]), f"{d['name']}: {rows} rows, reviewed {d['rows']}"
print("  OK: checksums and row counts match job.json")
EOF
echo "=== [1/5] deps ==="
pip install -q -U "transformers>=4.57" "trl>=0.20" peft datasets accelerate "jinja2>=3.1" sentencepiece
echo "=== [2/5] mask gate: build + prove the generation-marked template (aborts on failure) ==="
python3 template_gen.py "$BASE_MODEL" chat_template.gen.jinja --trust-remote-code
echo "=== [3/5] train ==="
python3 train_lora.py job.json
echo "=== [4/5] convert every epoch to GGUF ==="
if [ ! -f "$LLAMA_CPP/convert_lora_to_gguf.py" ]; then
  echo "  llama.cpp not found at $LLAMA_CPP - fetching the converter (git clone --depth 1)"
  git clone --depth 1 https://github.com/ggml-org/llama.cpp "$LLAMA_CPP"
  pip install -q -e "$LLAMA_CPP/gguf-py"
fi
mkdir -p gguf_out
n=0
for ckpt in $(ls -d lora_out/checkpoint-* | sort -t- -k2 -n); do
  n=$((n+1))
  out="gguf_out/${OUT_NAME}_epoch${n}.gguf"
  echo "  converting $ckpt -> $out"
  python3 "$LLAMA_CPP/convert_lora_to_gguf.py" "$ckpt" --base "$BASE_MODEL" --outfile "$out"
  sz=$(stat -c%s "$out" 2>/dev/null || echo 0)
  [ "$sz" -gt 1000000 ] || { echo "FATAL: $out is $sz bytes - conversion produced nothing." >&2; exit 1; }
  echo "  OK: $out ($((sz/1024/1024)) MB)"
done
[ "$n" -gt 0 ] || { echo "FATAL: no checkpoints were saved" >&2; exit 1; }
echo "=== [5/5] checksums for the download-verify step ==="
(cd gguf_out && sha256sum *.gguf | tee SHA256SUMS.txt)
echo "=== TRAINING COMPLETE ==="
