# Last updated: 2026-10-05 21:33:05
# @nova: One-click, read-only readiness check for Nova's voice: GPU memory, voice packages, audio devices and which local services answer. Writes voice_check.log.
"""Run VOICE_CHECK.cmd (or, from the workspace: py -3 general_tools/voice_gateway/check_voice_ready.py).

It changes nothing. It reads GPU memory with nvidia-smi, looks up which voice packages this Python
has (without importing the heavy ones), lists audio devices when sounddevice is installed, and
checks which local services answer: Nova Chat, her model server, the witness, VTube Studio's plugin
API and her desktop viewer. The report is written to voice_check.log beside this file (git skips
*.log). Run it while Nova is up, so the free GPU memory is what the voice will actually get.
"""
import importlib.util
import json
import platform
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = HERE / "voice_check.log"
PACKAGES = [("websockets", "websockets"), ("numpy", "numpy"), ("sounddevice", "sounddevice"),
            ("onnxruntime", "onnxruntime"), ("torch", "torch"), ("torchaudio", "torchaudio"),
            ("chatterbox-tts", "chatterbox"), ("transformers", "transformers"),
            ("silero-vad", "silero_vad"), ("useful-moonshine-onnx", "moonshine_onnx")]
PORTS = [("Nova Chat", 8765), ("her model server", 8080), ("witness model", 8081),
         ("VTube Studio plugin API", 8001), ("her desktop viewer (noVNC)", 6080)]
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def gpus():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=index,name,memory.total,memory.used,memory.free",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True,
                             timeout=20, creationflags=NO_WINDOW).stdout
    except Exception as error:
        return [{"error": f"{type(error).__name__}: {error}"}]
    rows = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 5:
            rows.append({"gpu": parts[0], "name": parts[1], "total_mb": int(parts[2]),
                         "used_mb": int(parts[3]), "free_mb": int(parts[4])})
    return rows or [{"error": "nvidia-smi printed nothing"}]


def answers(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.5):
            return True
    except OSError:
        return False


def audio_devices():
    if importlib.util.find_spec("sounddevice") is None:
        return "sounddevice is not installed"
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        return {"default_input": sd.default.device[0], "default_output": sd.default.device[1],
                "inputs": [d["name"] for d in devices if d["max_input_channels"] > 0][:10],
                "outputs": [d["name"] for d in devices if d["max_output_channels"] > 0][:10]}
    except Exception as error:
        return f"{type(error).__name__}: {error}"


def torch_cuda():
    if importlib.util.find_spec("torch") is None:
        return "torch is not installed"
    try:
        import torch
        return {"version": torch.__version__, "cuda": torch.cuda.is_available(),
                "devices": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]}
    except Exception as error:
        return f"{type(error).__name__}: {error}"


def main() -> int:
    report = {
        "when": datetime.now().isoformat(timespec="seconds"),
        "python": f"{platform.python_version()} at {sys.executable}",
        "gpus": gpus(),
        "packages": {pip: importlib.util.find_spec(mod) is not None for pip, mod in PACKAGES},
        "torch": torch_cuda(),
        "audio": audio_devices(),
        "services": {f"{name} :{port}": answers(port) for name, port in PORTS},
    }
    lines = [f"Nova voice readiness check, {report['when']}", f"Python {report['python']}", ""]
    for g in report["gpus"]:
        lines.append(f"GPU {g['gpu']} {g['name']}: {g['free_mb']} MB free of {g['total_mb']} MB"
                     if "error" not in g else f"GPU: {g['error']}")
    lines.append("")
    lines += [f"{'yes' if ok else 'no '}  {name}" for name, ok in report["packages"].items()]
    lines.append("")
    lines += [f"{'up  ' if up else 'down'}  {name}" for name, up in report["services"].items()]
    text = "\n".join(lines)
    LOG.write_text(text + "\n\n" + json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(text)
    print(f"\nSaved to {LOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
