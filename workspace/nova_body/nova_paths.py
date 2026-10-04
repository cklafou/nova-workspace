# Last updated: 2026-10-04 15:01:23
"""Nova's persistent-state ownership, independent of the face or current directory.

NOVA_BODY may name a relocated body directory. NOVA_WORKSPACE identifies the optional
surrounding project (tools, authored artifacts, inference launchers). No reads fall back
to old workspace-level state: missing body data must not silently select another Nova.
"""
from __future__ import annotations

import os
from pathlib import Path

BODY_ROOT = Path(os.environ.get("NOVA_BODY") or (
    str(Path(os.environ["NOVA_WORKSPACE"]) / "nova_body")
    if os.environ.get("NOVA_WORKSPACE") else str(Path(__file__).resolve().parent)
)).resolve()
WORKSPACE_ROOT = Path(os.environ.get("NOVA_WORKSPACE") or BODY_ROOT.parent).resolve()
OWNED_ROOTS = frozenset({"memory", "logs", "SELF", "Tasking", "KoELS", "Nova_Created",
                         "nova_memory_db", "nova_config.json", "nova_status.json"})


def body_path(*parts: str, workspace=None) -> Path:
    """Resolve body state; an explicit alternate workspace supports isolated instances.

    The standard process root always honors NOVA_BODY, even if the relocated directory
    has a different name. An alternate workspace owns its own nova_body subdirectory.
    This function creates nothing and never probes legacy state locations.
    """
    if workspace is None or Path(workspace).resolve() == WORKSPACE_ROOT:
        root = BODY_ROOT
    else:
        root = Path(workspace).resolve() / "nova_body"
    return root.joinpath(*parts)


def workspace_path(path: str | Path, *, workspace=None) -> Path:
    """Resolve a workspace-relative path, translating historic body-state spellings.

    This translation supports old task references without leaving aliases or second
    writable copies on disk. Absolute paths remain explicit; callers own access policy.
    """
    value = Path(path)
    if value.is_absolute():
        return value
    if value.parts and value.parts[0] == "nova_body":
        return body_path(*value.parts[1:], workspace=workspace)
    if value.parts and value.parts[0] in OWNED_ROOTS:
        return body_path(*value.parts, workspace=workspace)
    base = Path(workspace).resolve() if workspace is not None else WORKSPACE_ROOT
    return base / value
