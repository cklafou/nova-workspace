"""
nova_gateway/config.py
======================
Load and validate gateway settings from nova_gateway.json.

The config file lives at: workspace/nova_gateway.json
(same folder as AGENTS.md, SOUL.md, etc.)

If nova_gateway.json doesn't exist yet, DEFAULT_CONFIG is used and a
template is written so Cole can fill in his Discord token.

Plain-English guide to each setting is in COWORK_SESSION_LOG.md.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ── Locate workspace root ────────────────────────────────────────────────────
# This file lives at: workspace/tools/nova_gateway/config.py
# Normally workspace root is three levels up, but inside a PyInstaller bundle
# __file__ resolves to _internal/ — use the NOVA_WORKSPACE env var that
# NovaLauncher.py sets to the real on-disk workspace path instead.
WORKSPACE = (
    Path(os.environ["NOVA_WORKSPACE"])
    if "NOVA_WORKSPACE" in os.environ
    else Path(__file__).resolve().parent.parent.parent
)
CONFIG_PATH  = WORKSPACE / "nova_gateway.json"

# ── Defaults (used if nova_gateway.json is missing or incomplete) ────────────
DEFAULT_CONFIG: dict[str, Any] = {
    # Ollama settings
    "ollama": {
        "base_url":       "http://127.0.0.1:11434",
        "model":          "nova",
        "context_window": 32768,   # update to 131072 after eGPU + model rebuild
        "max_tokens":     16384,
        "timeout_s":      120,
    },

    # Gateway HTTP API (for nova_chat to query)
    "gateway": {
        "port":  18790,
        "host":  "127.0.0.1",
        "token": "nova-gateway-local",   # change this to something secret
    },

    # Discord bot settings
    # Get your bot token from https://discord.com/developers/applications
    "discord": {
        "enabled":   False,         # set True when token is filled in
        "token":     "PASTE_BOT_TOKEN_HERE",
        "allowlist": [],            # list of channel IDs (integers) Nova responds to
        "dm_enabled": True,
        "allow_bots": True,         # Nova responds to other bots (used by nova_chat relay)
    },

    # Cron / scheduled jobs
    "cron": {
        "health_check": {
            "enabled":      True,
            "interval_min": 30,     # fire every N minutes
            "message":      "Perform system health check — verify all components are functioning properly.",
        }
    },

    # Context / system prompt
    "context": {
        # Files to inject into Nova's system prompt (relative to workspace root)
        # Order matters — they appear in Nova's context in this order.
        "inject_files": [
            "AGENTS.md",
            "SOUL.md",
            "IDENTITY.md",
            "TOOLS.md",
            "memory/STATUS.md",
            "memory/COLE.md",
        ],
        # Extra files injected only on cron/heartbeat triggers (not regular messages)
        "heartbeat_extra_files": [
            "HEARTBEAT.md",
        ],
    },

    # Session storage
    "sessions": {
        # Where to store session JSONL files (relative to workspace root)
        "dir":              "sessions",
        # Compact when context hits this fraction of context_window
        "compact_at_frac":  0.85,
        # Keep this many recent message-pairs after compaction
        "compact_keep_pairs": 10,
    },

    # Tool execution safety
    "tools": {
        "exec_timeout_s":    60,     # max seconds a shell command can run
        "exec_cwd":          None,   # None = workspace root (recommended)
        "read_max_bytes":    524288, # 512 KB max file read
    },
}


# ── Loader ───────────────────────────────────────────────────────────────────

class GatewayConfig:
    """
    Thin wrapper around the merged config dict.
    Access sections as attributes: cfg.ollama, cfg.discord, etc.
    Access individual keys: cfg.get("ollama.model")
    """

    def __init__(self, data: dict[str, Any]):
        self._data = data

    # ── Section accessors ────────────────────────────────────────────────────
    @property
    def ollama(self) -> dict:    return self._data["ollama"]
    @property
    def gateway(self) -> dict:   return self._data["gateway"]
    @property
    def discord(self) -> dict:   return self._data["discord"]
    @property
    def cron(self) -> dict:      return self._data["cron"]
    @property
    def context(self) -> dict:   return self._data["context"]
    @property
    def sessions(self) -> dict:  return self._data["sessions"]
    @property
    def tools(self) -> dict:     return self._data["tools"]

    # ── Dot-path accessor ────────────────────────────────────────────────────
    def get(self, dot_path: str, default=None):
        """cfg.get("ollama.model") → "nova" """
        parts = dot_path.split(".")
        node = self._data
        for p in parts:
            if not isinstance(node, dict) or p not in node:
                return default
            node = node[p]
        return node

    # ── Derived helpers ──────────────────────────────────────────────────────
    @property
    def workspace(self) -> Path:
        return WORKSPACE

    @property
    def sessions_dir(self) -> Path:
        return WORKSPACE / self.sessions["dir"]

    @property
    def ollama_chat_url(self) -> str:
        return self.ollama["base_url"].rstrip("/") + "/v1/chat/completions"

    @property
    def ollama_tags_url(self) -> str:
        return self.ollama["base_url"].rstrip("/") + "/api/tags"

    def inject_files(self, heartbeat: bool = False) -> list[Path]:
        """Return absolute paths of files to inject into system prompt."""
        files = list(self.context["inject_files"])
        if heartbeat:
            files += self.context.get("heartbeat_extra_files", [])
        paths = []
        for rel in files:
            p = WORKSPACE / rel
            if p.exists():
                paths.append(p)
            else:
                log.warning("context inject file not found: %s", p)
        return paths

    def __repr__(self) -> str:
        return f"<GatewayConfig workspace={WORKSPACE} ollama_model={self.ollama['model']}>"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base (override wins on conflicts)."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load(config_path: Path = CONFIG_PATH) -> GatewayConfig:
    """
    Load nova_gateway.json, merge with defaults, return GatewayConfig.
    If the file doesn't exist, write a template and return defaults.
    """
    if not config_path.exists():
        _write_template(config_path)
        log.warning(
            "nova_gateway.json not found — wrote template to %s. "
            "Fill in your Discord token and set discord.enabled = true.",
            config_path,
        )
        return GatewayConfig(DEFAULT_CONFIG)

    try:
        with open(config_path, encoding="utf-8") as f:
            user_cfg = json.load(f)
    except json.JSONDecodeError as e:
        log.error("nova_gateway.json is invalid JSON: %s — using defaults", e)
        return GatewayConfig(DEFAULT_CONFIG)

    merged = _deep_merge(DEFAULT_CONFIG, user_cfg)
    log.info("Config loaded from %s", config_path)
    return GatewayConfig(merged)


def _write_template(path: Path) -> None:
    """Write a commented template nova_gateway.json for Cole to fill in."""
    template = dict(DEFAULT_CONFIG)
    path.write_text(json.dumps(template, indent=2), encoding="utf-8")


# ── Module-level singleton (import and use anywhere) ─────────────────────────
# Usage: from nova_gateway.config import cfg
cfg: GatewayConfig = load()


if __name__ == "__main__":
    import pprint
    print(f"Workspace: {cfg.workspace}")
    print(f"Ollama:    {cfg.ollama_chat_url}")
    print(f"Discord:   enabled={cfg.discord['enabled']}")
    print(f"Sessions:  {cfg.sessions_dir}")
    print("Inject files:")
    for p in cfg.inject_files():
        exists = "✓" if p.exists() else "✗ MISSING"
        print(f"  {exists}  {p.name}")
