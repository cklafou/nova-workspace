# Last updated: 2026-06-22 20:57:58
# @nova: Nova's settings — body-owned config loader (inference, sessions, tool-exec limits). Reads workspace/nova_config.json; falls back to defaults. Import as: from nova_config import cfg.
"""
nova_body/nova_config — Nova's Settings Loader
===============================================
Body-resident configuration. Holds the settings Nova's faculties need to run:
inference limits, session storage, and tool-execution safety bounds.

This lives in the body (not general_tools) on purpose: the pluck-test says the
body must keep working if every tool is removed, so the config the body depends
on cannot live in a tool. The detachable chat/voice tooling no longer owns it.

Settings DATA lives in workspace/nova_config.json (parallel to memory/ and
Tasking/). If that file is missing, DEFAULT_CONFIG is used and a template is
written. Import the singleton anywhere with:  from nova_config import cfg

(Supersedes the retired general_tools/gateway_config.py — the dead Discord /
gateway / cron sections were dropped; only live settings remain.)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ── Locate workspace root ────────────────────────────────────────────────────
# This file: workspace/nova_body/nova_config/__init__.py  → workspace is 3 up.
# Inside a PyInstaller bundle __file__ resolves oddly, so prefer NOVA_WORKSPACE.
WORKSPACE = (
    Path(os.environ["NOVA_WORKSPACE"])
    if "NOVA_WORKSPACE" in os.environ
    else Path(__file__).resolve().parent.parent.parent
)
CONFIG_PATH = WORKSPACE / "nova_config.json"

# ── Defaults (used if nova_config.json is missing or incomplete) ─────────────
DEFAULT_CONFIG: dict[str, Any] = {
    # Inference settings (llama.cpp standalone server on :8080)
    "inference": {
        "context_window": 32768,
        "max_tokens":     16384,
        "timeout_s":      120,
    },
    # Session storage
    "sessions": {
        "dir":                "logs/gateway_sessions",  # existing session history lives here
        "compact_at_frac":    0.85,
        "compact_keep_pairs": 10,
    },
    # Tool-execution safety bounds
    "tools": {
        "exec_timeout_s": 60,      # max seconds a shell command may run
        "exec_cwd":       None,    # None = workspace root
        "read_max_bytes": 524288,  # 512 KB max file read
    },
}


class NovaConfig:
    """Thin wrapper around the merged config dict.

    Access sections as attributes (cfg.inference, cfg.sessions, cfg.tools) or
    individual keys via dot-path (cfg.get("inference.max_tokens"))."""

    def __init__(self, data: dict[str, Any]):
        self._data = data

    @property
    def inference(self) -> dict: return self._data["inference"]
    @property
    def sessions(self) -> dict:  return self._data["sessions"]
    @property
    def tools(self) -> dict:     return self._data["tools"]

    def get(self, dot_path: str, default=None):
        node = self._data
        for p in dot_path.split("."):
            if not isinstance(node, dict) or p not in node:
                return default
            node = node[p]
        return node

    @property
    def workspace(self) -> Path:
        return WORKSPACE

    @property
    def sessions_dir(self) -> Path:
        return WORKSPACE / self.sessions["dir"]

    def __repr__(self) -> str:
        return f"<NovaConfig workspace={WORKSPACE}>"


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load(config_path: Path = CONFIG_PATH) -> NovaConfig:
    """Load nova_config.json merged over defaults; write a template if absent."""
    if not config_path.exists():
        try:
            config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
            log.warning("nova_config.json not found — wrote default template to %s", config_path)
        except Exception as e:
            log.error("could not write nova_config.json template: %s", e)
        return NovaConfig(DEFAULT_CONFIG)
    try:
        with open(config_path, encoding="utf-8") as f:
            user_cfg = json.load(f)
    except json.JSONDecodeError as e:
        log.error("nova_config.json is invalid JSON: %s — using defaults", e)
        return NovaConfig(DEFAULT_CONFIG)
    return NovaConfig(_deep_merge(DEFAULT_CONFIG, user_cfg))


# ── Module-level singleton ────────────────────────────────────────────────────
# Usage: from nova_config import cfg
cfg: NovaConfig = load()


if __name__ == "__main__":
    print(f"Workspace:  {cfg.workspace}")
    print(f"Inference:  ctx={cfg.inference['context_window']} max_tokens={cfg.inference['max_tokens']}")
    print(f"Sessions:   {cfg.sessions_dir}")
    print(f"Tool exec:  timeout={cfg.tools['exec_timeout_s']}s read_max={cfg.tools['read_max_bytes']}B")
