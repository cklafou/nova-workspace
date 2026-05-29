#!/usr/bin/env python3
# Last updated: 2026-05-29 15:52:09
# @nova: One-time downloader for Nova's vision models into workspace/models/ (for nova_senses).
"""
download_models.py — Pre-download Nova's vision models to workspace/models/

Run this ONCE after setting up a fresh machine so nova_senses/eyes.py
can load moondream2 without internet access during normal operation.

The Qwen 3.5 27B Q8 GGUF (qwen-27b-q8.gguf) and vision projector (qwen-27b-mmproj.gguf)
are NOT handled here — they must be placed manually at workspace/models/.

Usage:
    python tools/download_models.py

Requirements:
    pip install huggingface_hub transformers
"""

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
MODELS_DIR = WORKSPACE / "models"
MODELS_DIR.mkdir(exist_ok=True)


# ── moondream2 ─────────────────────────────────────────────────────────────────
MOONDREAM_MODEL_ID = "vikhyatk/moondream2"
MOONDREAM_REVISION = "2024-08-26"
MOONDREAM_DEST     = MODELS_DIR / "moondream2"


def download_moondream():
    print(f"\n[download] moondream2  →  {MOONDREAM_DEST}")
    print("[download] Size: ~2GB — this may take a few minutes on the first run.")

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("[download] ERROR: huggingface_hub not installed.")
        print("           Run:  pip install huggingface_hub")
        sys.exit(1)

    MOONDREAM_DEST.mkdir(parents=True, exist_ok=True)

    snapshot_download(
        repo_id=MOONDREAM_MODEL_ID,
        revision=MOONDREAM_REVISION,
        local_dir=str(MOONDREAM_DEST),
        ignore_patterns=["*.msgpack", "flax_model*", "tf_model*", "*.ot"],
    )

    print(f"[download] moondream2 saved to:  {MOONDREAM_DEST}")
    files = list(MOONDREAM_DEST.glob("**/*"))
    total_mb = sum(f.stat().st_size for f in files if f.is_file()) / 1_048_576
    print(f"[download] {len(files)} files, {total_mb:.0f} MB on disk")


# ── Verify existing models ─────────────────────────────────────────────────────

def check_existing():
    print("\n=== Model Status ===")

    # qwen-27b-q8.gguf (Qwen 3.5 27B Dense Q8)
    gguf = MODELS_DIR / "qwen-27b-q8.gguf"
    mmproj = MODELS_DIR / "qwen-27b-mmproj.gguf"
    if gguf.exists():
        size_gb = gguf.stat().st_size / 1_073_741_824
        print(f"  ✓  qwen-27b-q8.gguf        ({size_gb:.1f} GB)")
    else:
        print(f"  ✗  qwen-27b-q8.gguf        MISSING — place manually in models/")
    if mmproj.exists():
        size_gb = mmproj.stat().st_size / 1_073_741_824
        print(f"  ✓  qwen-27b-mmproj.gguf    ({size_gb:.1f} GB)")
    else:
        print(f"  ✗  qwen-27b-mmproj.gguf    MISSING — place manually in models/")

    # moondream2
    if MOONDREAM_DEST.is_dir() and any(MOONDREAM_DEST.iterdir()):
        files = list(MOONDREAM_DEST.glob("**/*"))
        total_mb = sum(f.stat().st_size for f in files if f.is_file()) / 1_048_576
        print(f"  ✓  models/moondream2/      ({total_mb:.0f} MB, {len(files)} files)")
    else:
        print(f"  ✗  models/moondream2/      MISSING — run this script to download")

    print()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Download Nova vision models")
    parser.add_argument("--check", action="store_true", help="Only check status, don't download")
    args = parser.parse_args()

    check_existing()

    if args.check:
        sys.exit(0)

    # Download anything that's missing
    if not (MOONDREAM_DEST.is_dir() and any(MOONDREAM_DEST.iterdir())):
        download_moondream()
    else:
        print("[download] moondream2 already present — skipping. Use --force to re-download.")

    print("\n[download] All done. Nova's vision models are ready.")
    check_existing()
