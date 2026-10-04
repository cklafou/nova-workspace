#!/usr/bin/env bash
# @nova: The whole LoRA training pipeline ON the pod, one command: verify inputs, prove the mask, train, convert every epoch to GGUF, checksum.
#
# Hyperparameters come from v7; Qwen3.8 runtime, VRAM and duration require their own GPU proof.
# Everything job-specific comes from job.json, written by the updater. Lessons kept on purpose:
#   * HF cache on the pod's LOCAL disk, never /workspace (network FS = 90-minute model load).
#   * The mask gate is not optional; `set -e` aborts on any failure.
#   * Convert EVERY epoch and verify sizes; A/B both locally (v6: epoch1 won first, epoch2 won long).
#   * When done the updater STOPS the pod. Never Terminate (it wipes /workspace).
set -euo pipefail
cd "$(dirname "$0")"
export HF_HOME="${HF_HOME:-/root/.cache/huggingface}"
# Separate pinned converter checkout; never reuse or change another job's llama.cpp checkout.
LLAMA_REV="11fe02151f79c41d0d4af7da708755d73b9c0da6"
LLAMA_CPP="/workspace/nova-llama-converter-${LLAMA_REV}"
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
# BEGIN TRAINING VENV
# Reuse the image's CUDA Torch while installing only into this job's isolated environment.
# Inherit the existing pip module: --without-pip avoids Ubuntu's optional ensurepip package.
# Dependency trees have many small files: keep them off /workspace's network filesystem.
# Include the package path and recipe bytes so separate jobs never share a mutable venv.
TRAIN_VENV=$(python3 - <<'EOF'
from pathlib import Path
import hashlib
import os
cache = Path(os.environ.get("NOVA_TRAINING_CACHE_DIR", "/root/.cache/nova-training")).expanduser().resolve()
key = hashlib.sha256(str(Path.cwd().resolve()).encode() + b"\0" + Path("job.json").read_bytes()).hexdigest()[:24]
print(cache / key)
EOF
)
python3 -m venv --system-site-packages --without-pip "$TRAIN_VENV"
source "$TRAIN_VENV/bin/activate"
export PIP_REQUIRE_VIRTUALENV=true
export PIP_USER=false
python3 - <<'EOF'
import sys
assert sys.prefix != sys.base_prefix, "Training package installation must run in a virtual environment"
EOF
python3 -m pip --version
# END TRAINING VENV
# Do not let pip replace the CUDA Torch supplied by the reviewed pod image.
python3 - <<'EOF'
import torch
from packaging.version import Version
assert Version(torch.__version__.split("+")[0]) >= Version("2.6"), "Use a CUDA PyTorch >=2.6 pod image"
assert torch.cuda.is_available() and torch.cuda.is_bf16_supported(), "A bf16 CUDA GPU is required"
open("torch-constraint.txt", "w").write("torch==" + torch.__version__.split("+")[0] + "\n")
EOF
python3 -m pip install -q -c torch-constraint.txt "transformers==5.18.0" "trl==1.14.1" "peft==0.21.2" \
  "datasets==5.0.1" "accelerate==1.15.0" "tokenizers==0.23.1" "huggingface-hub==1.31.0" \
  "safetensors==0.8.0" "jinja2==3.1.6" "sentencepiece==0.2.2"
# Converter fetched before training: dependency/network failure must not waste a completed run.
if [ ! -f "$LLAMA_CPP/convert_lora_to_gguf.py" ]; then
  git init "$LLAMA_CPP"
  git -C "$LLAMA_CPP" remote add origin https://github.com/ggml-org/llama.cpp
  git -C "$LLAMA_CPP" fetch --depth 1 origin "$LLAMA_REV"
  git -C "$LLAMA_CPP" checkout --detach FETCH_HEAD
fi
[ "$(git -C "$LLAMA_CPP" rev-parse HEAD)" = "$LLAMA_REV" ] || { echo "FATAL: converter revision mismatch" >&2; exit 1; }
python3 -m pip install -q -c torch-constraint.txt -e "$LLAMA_CPP/gguf-py"
python3 "$LLAMA_CPP/convert_lora_to_gguf.py" --help >/dev/null
python3 - <<'EOF' > environment.txt
import sys
print("# @nova: Record the actual training interpreter, environment path and installed packages.")
print("# Python:", sys.version.replace("\n", " "))
print("# Executable:", sys.executable)
print("# Environment:", sys.prefix)
EOF
python3 -m pip freeze >> environment.txt
echo "=== [2/5] mask gate: build + prove the generation-marked template (aborts on failure) ==="
python3 template_gen.py "$BASE_MODEL" chat_template.gen.jinja
echo "=== [3/5] train ==="
python3 train_lora.py job.json
echo "=== [4/5] convert every epoch to GGUF ==="
mkdir -p gguf_out
n=0
for ckpt in $(ls -d lora_out/checkpoint-* | sort -t- -k2 -n); do
  n=$((n+1))
  out="gguf_out/${OUT_NAME}_epoch${n}.gguf"
  echo "  converting $ckpt -> $out"
  python3 "$LLAMA_CPP/convert_lora_to_gguf.py" "$ckpt" --base base_config --outfile "$out"
  sz=$(stat -c%s "$out" 2>/dev/null || echo 0)
  [ "$sz" -gt 1000000 ] || { echo "FATAL: $out is $sz bytes - conversion produced nothing." >&2; exit 1; }
  echo "  OK: $out ($((sz/1024/1024)) MB)"
done
[ "$n" -gt 0 ] || { echo "FATAL: no checkpoints were saved" >&2; exit 1; }
# Bounded reproducibility receipt, separate from the GGUF-only download manifest.
python3 - <<'EOF'
from pathlib import Path
import hashlib
import shutil
out = Path("gguf_out/training_details")
out.mkdir(parents=True, exist_ok=True)
for name in ("environment.txt", "base_source.json", "tokenization_report.json",
             "chat_template.gen.jinja", "base_config/config.json"):
    destination = out / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(name, destination)
(out / "README.md").write_text(
    "<!-- @nova: Record the exact model revision, tokenizer mask audit and environment of this training run. -->\n"
    "# Training run details\n\n"
    "The sibling reproduction package contains the checksummed dataset, job settings and pod scripts.\n"
    "base_source.json pins the Hugging Face model revision used for template, tokenizer and weights.\n"
    "base_config/config.json is the same configuration given to the pinned GGUF converter.\n"
    "environment.txt records installed packages; tokenization_report.json records row/mask counts.\n"
    "chat_template.gen.jinja is the rendered-equivalent assistant-only training template.\n"
    "Converter revision: 11fe02151f79c41d0d4af7da708755d73b9c0da6.\n"
    "Finished GGUF adapters are installed beside the base model, outside this input package.\n",
    encoding="utf-8")
files = sorted(path for path in out.rglob("*") if path.is_file() and path.name != "SHA256SUMS.txt")
(out / "SHA256SUMS.txt").write_text("".join(
    f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(out).as_posix()}\n" for path in files), encoding="utf-8")
EOF
echo "=== [5/5] checksums for the download-verify step ==="
(cd gguf_out && sha256sum *.gguf | tee SHA256SUMS.txt)
echo "=== TRAINING COMPLETE ==="
