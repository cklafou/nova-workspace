# @nova: Resolves every folder the updater touches, with environment overrides so tests and relocated installs work.
"""One place for the updater's paths. Nothing here creates or reads files."""
from __future__ import annotations

import os
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent


def workspace() -> Path:
    return Path(os.environ.get("NOVA_WORKSPACE") or PACKAGE.parents[1]).resolve()


def models_root() -> Path:
    """Where model, projector and LoRA files live (the launcher's `models\\...` paths)."""
    return Path(os.environ.get("NOVA_MODELS_DIR") or workspace() / "models")


def body_root() -> Path:
    return Path(os.environ.get("NOVA_BODY") or workspace() / "nova_body")


def boot_file(name: str) -> Path:
    """Boot-time selections the launcher reads (active_model.txt, active_lora.txt, ...)."""
    return body_root() / "memory" / name


def launcher() -> Path:
    return Path(os.environ.get("NOVA_LAUNCHER") or workspace() / "start_llama_qwen36.cmd")


def trash_root() -> Path:
    """Replaced files are moved here, never deleted. Cole empties it himself."""
    return Path(os.environ.get("NOVA_TRASH_DIR") or workspace() / "_admin" / "Trash")


def state_dir() -> Path:
    return Path(os.environ.get("NOVA_UPDATER_STATE") or PACKAGE / "state")


def work_dir() -> Path:
    """Scratch for training bundles, pod outputs and logs (git, Orient and the watcher skip Temp)."""
    return Path(os.environ.get("NOVA_UPDATER_WORK") or workspace() / "Temp" / "updater")


def staging_dir() -> Path:
    """Downloads land beside the models so the final move is a rename on the same drive."""
    return models_root() / ".incoming"


def credentials_path() -> Path:
    """Local-only secrets (RunPod key, optional HF token). Never inside the project folder."""
    override = os.environ.get("NOVA_UPDATER_CREDENTIALS")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / ".config"
    return root / "ProjectNova" / "Updater" / "credentials.json"


def display(path: Path) -> str:
    """Workspace-relative POSIX text for the UI; absolute if it lives elsewhere."""
    path = Path(path)
    try:
        return path.resolve().relative_to(workspace()).as_posix()
    except ValueError:
        return str(path)
