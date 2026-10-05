# Last updated: 2026-10-06 03:19:20
# @nova: Install the isolated Windows CPU voice dependencies and verified local Whisper/Silero/Moonshine assets.
"""Run with Python 3.12: python setup_windows.py. No microphone, playback or Nova startup.

Assets are pinned from Silero, UsefulSensors Moonshine and the Dropbox Dash
CTranslate2 conversion of Whisper large-v3-turbo. Every model file must match its
pinned SHA256 before publication; partial downloads stay temporary.
"""
from pathlib import Path
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parent
REVISION = "48b4e427b587bcf67797a5be706d6ddc4a298149"
ASSETS = [
    ("silero_vad.onnx", "https://raw.githubusercontent.com/snakers4/silero-vad/v6.2.1/src/silero_vad/data/silero_vad.onnx",
     "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3"),
    ("moonshine-base/encoder_model.onnx", f"https://huggingface.co/UsefulSensors/moonshine/resolve/{REVISION}/onnx/merged/base/float/encoder_model.onnx",
     "153e128e7abd64a74ee47f2c3f585c3171c4d46cbb368b032827934c4e01e779"),
    ("moonshine-base/decoder_model_merged.onnx", f"https://huggingface.co/UsefulSensors/moonshine/resolve/{REVISION}/onnx/merged/base/float/decoder_model_merged.onnx",
     "58778763ca8438963190244d6b26572bdca2cedec56a4b91e828f3f2d69ef3c5"),
]
WHISPER_REVISION = "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf"
WHISPER_FILES = {
    "model.bin": "e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da",
    "config.json": "b0253ea6c0d3bea6b1e19e91a02acfd3b53f4467362efcb5a3e6b16c9b3a9b7e",
    "tokenizer.json": "297b13372ac43916285644fb9687add3cc62ee2a1adb60da3dc25cc94c1871fd",
    "preprocessor_config.json": "7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711",
    "vocabulary.json": "c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1",
}
ASSETS += [("whisper-large-v3-turbo/" + name,
            f"https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo/resolve/{WHISPER_REVISION}/{name}", sha)
           for name, sha in WHISPER_FILES.items()]



def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def install_assets(destination):
    destination = Path(destination)
    for relative, url, expected in ASSETS:
        path = destination / relative
        if path.is_file() and digest(path) == expected:
            print(f"Verified cached {relative}", flush=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "NovaVoiceSetup/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response, pending.open("wb") as out:
                shutil.copyfileobj(response, out, length=1024 * 1024)
            if digest(pending) != expected:
                raise RuntimeError(f"Checksum mismatch for {relative}; existing asset was preserved")
            os.replace(pending, path)
            print(f"Installed and verified {relative}", flush=True)
        finally:
            pending.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets-only", action="store_true")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("This pinned baseline is for Windows Python 3.12.")
    environment = ROOT / ".venv"
    python = environment / "Scripts/python.exe"
    if not args.assets_only:
        if not python.exists():
            subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements-windows.lock.txt")], check=True)
        subprocess.run([str(python), "-m", "pip", "check"], check=True)
    if not python.exists():
        raise SystemExit("Create the gateway .venv before installing its assets.")
    install_assets(environment / "share/nova_voice")
    print("Windows system voice + Whisper turbo CPU ready; Moonshine remains available. No audio device was opened.")


if __name__ == "__main__":
    main()
