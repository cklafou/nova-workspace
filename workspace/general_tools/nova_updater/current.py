# @nova: Works out which model, projector and LoRAs Nova boots with, from her boot files or the launcher, without opening model files.
"""What is Nova running?

The launcher (`start_llama_qwen36.cmd`) boots llama-server with `-m <model> --mmproj <projector>`
and reads optional boot files in `nova_body/memory/`:
    active_model.txt   model path (written by this updater)
    active_mmproj.txt  projector path, or `none`
    active_lora.txt    `--lora-scaled <path>:<scale>` (personality), or `none`
    koels_lora_args.txt  KoELS specialist adapters
Only these small text files are read. Model files themselves are never opened here.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import naming, paths

MODEL_ARG = re.compile(r"(?:^|\s)-m\s+\"?(?P<path>[^\"\s^]+\.gguf)", re.I)
MMPROJ_ARG = re.compile(r"--mmproj\s+\"?(?P<path>[^\"\s^]+\.gguf)", re.I)
SET_DEFAULT = re.compile(r'set\s+"(?P<var>NOVA_MODEL|NOVA_MMPROJ)=(?P<path>[^"]+)"', re.I)
LORA_ARG = re.compile(r'--lora(?:-scaled)?\s+(?:"(?P<quoted>[^"]+)"|(?P<bare>[^\s"]+))', re.I)
LORA_VALUE = re.compile(r"^(?P<path>.+\.gguf)(?::(?P<scale>[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)))?$", re.I)


def _first_line(path: Path, strip_quotes: bool = True) -> str | None:
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        if line.strip():
            return line.strip().strip('"') if strip_quotes else line.strip()
    return ""


def norm(path_text: str) -> str:
    """Launcher-style paths (backslashes, relative to workspace) as POSIX text."""
    return (path_text or "").replace("\\", "/").strip()


def _launcher_defaults() -> dict:
    found = {"model": None, "mmproj": None}
    try:
        text = paths.launcher().read_text(encoding="utf-8", errors="replace")
    except OSError:
        return found
    for match in SET_DEFAULT.finditer(text):
        key = "model" if match.group("var").upper() == "NOVA_MODEL" else "mmproj"
        found[key] = found[key] or match.group("path")
    if not found["model"]:
        m = MODEL_ARG.search(text)
        found["model"] = m.group("path") if m else None
    if not found["mmproj"]:
        m = MMPROJ_ARG.search(text)
        found["mmproj"] = m.group("path") if m else None
    return found


def active_model() -> dict:
    defaults = _launcher_defaults()
    model = _first_line(paths.boot_file("active_model.txt"))
    mmproj = _first_line(paths.boot_file("active_mmproj.txt"))
    source = "boot file" if model else ("launcher" if defaults["model"] else "unknown")
    model = model or defaults["model"]
    if mmproj is None or mmproj == "":
        mmproj = defaults["mmproj"]
    if mmproj and mmproj.lower() == "none":
        mmproj = None
    info = naming.parse_gguf_filename(norm(model)) if model else {}
    parsed = naming.parse(info.get("stem", "")) if info else None
    folder = Path(norm(model)).parent.name if model else ""
    publisher = "unsloth" if (info.get("quant") or "").upper().startswith("UD-") else None
    return {"source": source, "model_path": norm(model) if model else None,
            "mmproj_path": norm(mmproj) if mmproj else None,
            "name": parsed.to_dict() if parsed else None, "label": parsed.label if parsed else None,
            "quant": info.get("quant"), "folder": folder, "publisher_hint": publisher}


def current_name() -> naming.ModelName | None:
    model = active_model()
    return naming.parse(model["label"]) if model.get("label") else None


def active_loras() -> list:
    """Read both legacy bare tokens and quoted path:scale tokens with spaces."""
    out = []
    for filename, role in (("active_lora.txt", "personality"), ("koels_lora_args.txt", "koels")):
        line = _first_line(paths.boot_file(filename), strip_quotes=False)
        if not line or line.lower() == "none":
            continue
        for argument in LORA_ARG.finditer(line):
            value = argument.group("quoted") or argument.group("bare")
            for token in value.split(","):
                match = LORA_VALUE.fullmatch(token)
                if match:
                    out.append({"role": role, "path": norm(match.group("path")),
                                "scale": float(match.group("scale")) if match.group("scale") else 1.0})
    return out


def snapshot_boot_files() -> dict:
    """Exact text (or None if absent) of every boot file the updater may change, for rollback."""
    out = {}
    for name in ("active_model.txt", "active_mmproj.txt", "active_lora.txt", "koels_lora_args.txt"):
        path = paths.boot_file(name)
        try:
            with open(path, encoding="utf-8", newline="") as handle:  # keep CRLF exactly
                out[name] = handle.read()
        except FileNotFoundError:
            out[name] = None
    return out
