#!/usr/bin/env python3
"""
Download vision models for Nova's local inference stack.
Moondream2 is a lightweight (~1GB) vision model optimized for fast image understanding.
It handles routine visual tasks while reserving heavier models (Qwen3 27B) for complex reasoning.

Usage:
    python tools/download_models.py [--all]
"""
import os
import sys
import urllib.request
from pathlib import Path

def download_model(url, dest_path):
    """Download a model file with progress indicator."""
    print(f"Downloading {dest_path.name}...")
    try:
        urllib.request.urlretrieve(url, dest_path)
        size_mb = os.path.getsize(dest_path) / (1024 * 1024)
        print(f"✓ Downloaded: {dest_path.name} ({size_mb:.1f} MB)")
        return True
    except Exception as e:
        print(f"✗ Failed to download {dest_path.name}: {e}")
        return False

def main():
    models_dir = Path("models")
    if not models_dir.exists():
        models_dir.mkdir()
        print(f"Created models directory: {models_dir.absolute()}")
    
    # Moondream2 - lightweight vision model (~1GB)
    moondream_url = "https://huggingface.co/vikhyat/moondream2/resolve/main/moondream-2-bf16.gguf"
    moondream_path = models_dir / "moondream-2-bf16.gguf"
    
    print("\n=== Nova Model Downloader ===")
    if not moondream_path.exists():
        success = download_model(moondream_url, moondream_path)
        return 0 if success else 1
    else:
        size_mb = os.path.getsize(moondream_path) / (1024 * 1024)
        print(f"Moondream2 already exists: {moondream_path.name} ({size_mb:.1f} MB)")
        return 0

if __name__ == "__main__":
    sys.exit(main())
