# Last updated: 2026-10-04 14:34:47
# @nova: Lists installed models, projectors and LoRAs with what each was built for, read from GGUF headers when the user opens the update dialog.
"""Installed files, for the replace/train choices in the dialog.

Runs only when asked (opening the dialog or `python -m nova_updater inventory`), never at
startup. Reads GGUF headers, not weights. LoRAs are bound to the base they were trained for:
from the header when the converter recorded it, otherwise from the folder they sit in
(today's adapters live in `models/qwen3.6/`).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from . import current, gguf, naming, paths

SKIP_DIRS = {".incoming", "__pycache__", ".git", "Training Files"}


def _family_of(text: str) -> str | None:
    """'Qwen3.6-27B' / 'qwen3.6' / 'Qwen/Qwen3.6-27B' -> 'qwen3.6'."""
    if not text:
        return None
    tail = str(text).rstrip("/").split("/")[-1]
    normalized = re.sub(r"^([A-Za-z]+)\s+(\d+(?:\.\d+)*)(?=\s)", r"\1\2", tail)
    parsed = naming.parse(re.sub(r"\s+", "-", normalized))
    if parsed:
        return parsed.slug
    lowered = tail.lower()
    return lowered if any(ch.isdigit() for ch in lowered) else None



def describe_adapter(path: Path, metadata: dict | None = None) -> dict:
    """Read one selected adapter's header and binding; never scan a model directory."""
    path = Path(path)
    if not path.is_absolute():
        path = paths.workspace() / path
    meta = gguf.read_metadata(path) if metadata is None else metadata
    if gguf.classify(meta) != "lora":
        raise gguf.GGUFError(f"{paths.display(path)} is not a LoRA adapter")
    base = gguf.base_model(meta)
    bound = _family_of(base.get("name") or base.get("repo_url") or "") if base else None
    return {"path": paths.display(path), "kind": "lora", "base": base,
            "bound_to": bound or _family_of(path.parent.name), "bound_by": "header" if bound else "folder",
            "alpha": meta.get("adapter.lora.alpha")}


def _group_splits(files):
    groups = {}
    for path in files:
        info = naming.parse_gguf_filename(path.name)
        key = (path.parent, info["stem"] + ("-" + info["quant"] if info["quant"] else "")) if info["parts"] else (path.parent, path.name)
        groups.setdefault(key, []).append(path)
    return [sorted(paths_) for paths_ in groups.values()]


def scan(root: Path | None = None, max_depth: int = 4) -> dict:
    root = Path(root or paths.models_root())
    result = {"root": paths.display(root), "models": [], "projectors": [], "loras": [], "other": [],
              "errors": []}
    if not root.is_dir():
        result["errors"].append(f"{paths.display(root)} does not exist")
        return result
    active = current.active_model()
    active_paths = {p for p in (active.get("model_path"), active.get("mmproj_path")) if p}
    lora_paths = {l["path"]: l for l in current.active_loras()}
    ggufs = []
    for directory, dirs, names in os.walk(root):
        depth = len(Path(directory).relative_to(root).parts)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".") and depth < max_depth]
        for name in names:
            full = Path(directory) / name
            if name.lower().endswith(".gguf"):
                ggufs.append(full)
            elif name.lower().endswith((".safetensors", ".bin")) and depth <= 2:
                result["other"].append({"path": paths.display(full), "size": full.stat().st_size})
    for group in _group_splits(ggufs):
        first = group[0]
        try:
            meta = gguf.read_metadata(first)
        except (OSError, gguf.GGUFError) as error:
            result["errors"].append(f"{paths.display(first)}: {error}")
            continue
        kind = gguf.classify(meta)
        rel = paths.display(first)
        size = sum(p.stat().st_size for p in group)
        entry = {"path": rel, "parts": [paths.display(p) for p in group], "size": size, "kind": kind,
                 "architecture": meta.get("general.architecture"), "name": meta.get("general.name"),
                 "folder": first.parent.name, "quant": naming.parse_gguf_filename(first.name)["quant"],
                 "active": rel in active_paths or rel in lora_paths}
        if kind == "lora":
            entry.update(describe_adapter(first, meta))
            entry["role"] = (lora_paths.get(rel) or {}).get("role")
            result["loras"].append(entry)
        elif kind == "projector":
            entry["bound_to"] = _family_of(first.parent.name)
            result["projectors"].append(entry)
        else:
            entry["family"] = _family_of(meta.get("general.basename") or meta.get("general.name") or "") \
                or _family_of(naming.parse_gguf_filename(first.name)["stem"])
            entry["size_label"] = meta.get("general.size_label")
            result["models"].append(entry)
    for bucket in ("models", "projectors", "loras"):
        result[bucket].sort(key=lambda e: e["path"])
    return result


def invalidated_by(target_slug: str, inv: dict) -> list:
    """LoRAs and projectors that will not fit a model of family `target_slug`."""
    out = []
    for entry in inv.get("loras", []) + inv.get("projectors", []):
        bound = entry.get("bound_to")
        if bound and bound != target_slug:
            out.append({"path": entry["path"], "kind": entry["kind"], "bound_to": bound,
                        "active": entry.get("active", False)})
    return out
