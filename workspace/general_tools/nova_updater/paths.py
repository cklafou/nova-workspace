# Last updated: 2026-10-05 18:23:37
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



def training_root() -> Path:
    """Persistent datasets and recipes, separate from finished adapters beside their model."""
    return models_root() / "Training Files"


def training_model_name(base_model_id: str) -> str:
    """A readable, launcher-safe base name, e.g. Qwen 3.8 27B Dense."""
    from . import naming
    import re
    model = naming.parse(base_model_id)
    if model is None:
        raise ValueError("A recognized base model is required for the training folder.")
    parts = [model.family, model.version_text, f"{model.size_b:g}B"]
    parts.append(f"MoE A{model.active_b:g}B" if model.moe else "Dense")
    parts.extend(re.sub(r"[^A-Za-z0-9._ -]", "", token.replace("_", " ")).title()
                 for token in model.variant)
    if model.revision:
        parts.append(model.revision)
    return " ".join(part for part in parts if part)


def training_model_dir(base_model_id: str) -> Path:
    return training_root() / training_model_name(base_model_id)


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
    """Local-only secrets (RunPod key, optional HF token). Never inside the project folder.

    They sit beside the collaboration room's data in the user profile, not in AppData: Windows gives
    each MSIX-packaged launcher its own private AppData, which split the room in two (2026-10-04), so
    a key saved from one launcher would be missing in another."""
    override = os.environ.get("NOVA_UPDATER_CREDENTIALS")
    if override:
        return Path(override)
    return Path.home() / "ProjectNovaData" / "Updater" / "credentials.json"


# The launcher reads boot files with `set /p` (console code page) and echoes or expands them outside
# quotes in places, so only plain ASCII without cmd's special characters reaches llama-server
# intact. Adapter serializers quote the complete path:scale token, so spaces are supported.
CMD_SPECIAL = frozenset('"%!^&|<>()')


def launcher_problem(path: str, spaces: bool = True) -> str | None:
    """Why the launcher could not pass this path to llama-server intact, or None if it can."""
    bad = sorted({ch for ch in str(path) if ch in CMD_SPECIAL or not (ch.isascii() and ch.isprintable())
                  or (ch == " " and not spaces)})
    if not bad:
        return None
    shown = ", ".join("a space" if ch == " " else repr(ch) for ch in bad)
    return f"{path} contains {shown}, which the launcher cannot pass to llama-server intact"


def display(path: Path) -> str:
    """Workspace-relative POSIX text for the UI; absolute if it lives elsewhere."""
    path = Path(path)
    try:
        return path.resolve().relative_to(workspace()).as_posix()
    except ValueError:
        return str(path)
