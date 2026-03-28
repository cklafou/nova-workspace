"""
Determines who responds to each message and in what order.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ARCHITECTURE: SMART LISTENER MODEL  (v2 — 2026-03-28)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FOR DEVS (Cole + Claude) AND FOR NOVA (so you know how the room works):

MENTION SYSTEM
──────────────
  Direct mentions: @Claude, @Gemini, @Nova
  Role aliases:
    @mentor → Claude + Gemini  (both respond, in order)
    @all    → Claude + Gemini + Nova

  No @mentions at all → only Nova responds (she's the default).

  NCL MODULE CALLS (@eyes, @thinkorswim, etc.) are distinct from the above.
  They are parsed by nova_lang.py and routed through the NCL execution path,
  not through the orchestrator response queue.  Use is_ncl_message() to
  detect them before calling parse_directed().

RESPONSE ORDER (always sequential, never parallel)
──────────────────────────────────────────────────
  When multiple AIs are triggered, they respond in this fixed order:

      Claude → Gemini → Nova

  Each AI sees all previous responses in the transcript before it replies.
  Nova is always LAST so she has the full picture before saying anything.

  When @mentor is used, the full flow is:
    1. Claude responds to the original message
    2. Gemini responds (sees Cole's message + Claude's response)
    3. Nova responds (sees everything above)

NOVA'S SMART @MENTION BEHAVIOR
───────────────────────────────
  After Nova's response is saved to the transcript, server.py checks
  whether Nova's text contains any @mentions.  If it does, those AIs
  are triggered in a follow-up round (they see Nova's full message as
  additional context before replying).

  This is the mechanism by which Nova smartly escalates to Claude/Gemini
  based on her own judgment — she writes her response to Cole first, reads
  it, and if she genuinely needs mentor input she includes "@Claude ..." or
  "@Gemini ..." or "@mentor ..." naturally in her text.  The system then
  routes that automatically.

  IMPORTANT for Nova: Be deliberate with @mentions.  Only escalate when
  you have a specific question or task that genuinely benefits from Claude
  or Gemini's expertise.  Unnecessary @mentions cost API money.

  Follow-up rounds are ONE level deep — if Claude responds to Nova's
  @mention, that response does NOT trigger another Nova → @mention cycle.

DEFAULT BEHAVIOR
────────────────
  No @mentions → only Nova responds.
  @Nova (explicit) → only Nova responds.
  @Claude → Claude, then Nova (Nova always appended at end to react).
  @mentor → Claude, Gemini, then Nova.
  @all    → Claude, Gemini, Nova.

RATE-LIMIT FAILSAFE  (TEMPORARY — see server.py _NOVA_RATE_LIMIT)
──────────────────────────────────────────────────────────────────
  Still in effect: >4 Nova inject_message calls/60s → auto-throttle.
  Follow-up @mention rounds do NOT count toward this limit (they are
  Cole-initiated response cycles, not Nova-initiated inject calls).
  Remove once autonomy loop is proven stable. — Cole & Claude, 2026-03-28

MODULE REGISTRY  (Phase 4A.3+)
──────────────────────────────
  MODULE_REGISTRY maps @name → metadata for NCL modules Nova can call.
  Loaded from workspace/modules.json if present; falls back to defaults.
  Use get_module(name) to look up a registered module.
  Use list_modules() to enumerate all registered modules.
"""
import json
import re
from pathlib import Path
from typing import Optional

# ── Orchestrator participants ────────────────────────────────────────────────

PARTICIPANTS = ["Claude", "Gemini", "Nova"]

# Role aliases — map role name to list of participant names
ROLES: dict[str, list[str]] = {
    "mentor": ["Claude", "Gemini"],
    "all":    ["Claude", "Gemini", "Nova"],
}

# Canonical sequential order — listeners always before Nova
RESPONSE_ORDER = ["Claude", "Gemini", "Nova"]

# ── NCL Module Registry ───────────────────────────────────────────────────────
#
# Default registry — can be overridden by workspace/modules.json.
# Each entry maps the @name (lowercase) → module metadata dict.
# Fields:
#   description   Human-readable purpose
#   local_model   Primary local execution method (Ollama, pywinauto, etc.)
#   api_fallback  Cloud fallback when local tiers fail (or None)
#   status        "active" | "partial" | "planned" — reflects implementation state
#
_MODULE_REGISTRY_DEFAULTS: dict[str, dict] = {
    "eyes": {
        "description": "Visual perception, screenshot analysis, UI element detection",
        "local_model":  "pywinauto (Tier 1) → moondream2 Ollama (Tier 2) → LLaVA 13B (Tier 3)",
        "api_fallback": "Claude Haiku (Tier 4)",
        "status":       "active",    # All tiers implemented (Phase 4A.7). Ollama pull required for T2-3.
        "ollama_models": ["moondream", "llava:13b"],
        "setup_note":   "ollama pull moondream && ollama pull llava:13b",
    },
    "mentor": {
        "description": "High-reasoning review, strategic advice — routes to Claude + Gemini",
        "local_model":  "Claude + Gemini (they ARE the local solution)",
        "api_fallback": None,
        "status":       "active",
    },
    "thinkorswim": {
        "description": "Trading platform analysis, position management, order execution",
        "local_model":  "Fine-tuned Nova variant (future)",
        "api_fallback": "Claude / Gemini",
        "status":       "planned",
    },
    "browser": {
        "description": "Web research, page reading, form interaction, link following",
        "local_model":  "Headless Chromium + HTML parsing",
        "api_fallback": "Claude in Chrome",
        "status":       "planned",
    },
    "memory": {
        "description": "Semantic search over Nova's session history and journal",
        "local_model":  "nomic-embed-text (Ollama)",
        "api_fallback": None,
        "status":       "planned",
    },
    "coder": {
        "description": "Code generation, debugging, review, refactoring",
        "local_model":  "DeepSeek-Coder / Qwen-Coder (Ollama)",
        "api_fallback": "Claude",
        "status":       "planned",
    },
    "voice": {
        "description": "Audio transcription, speech-to-text processing",
        "local_model":  "whisper.cpp local",
        "api_fallback": None,
        "status":       "planned",
    },
}

# Runtime registry — populated by _load_module_registry() below
MODULE_REGISTRY: dict[str, dict] = {}

# Path to external config override (relative to workspace root)
_MODULES_JSON_NAME = "modules.json"


def _load_module_registry() -> dict[str, dict]:
    """
    Load the module registry.

    Priority:
    1. workspace/modules.json (if present) — merges on top of defaults
    2. _MODULE_REGISTRY_DEFAULTS (hardcoded fallback)

    modules.json format:
    {
        "modules": {
            "eyes": { "status": "active", ... },
            "my_custom_module": { "description": "...", ... }
        }
    }
    """
    registry = dict(_MODULE_REGISTRY_DEFAULTS)
    try:
        # Locate workspace root (3 levels up from this file: nova_chat/ → tools/ → workspace/)
        ws_root = Path(__file__).resolve().parent.parent.parent
        modules_path = ws_root / _MODULES_JSON_NAME
        if modules_path.exists():
            with open(modules_path, encoding="utf-8") as f:
                data = json.load(f)
            overrides = data.get("modules", {})
            for name, meta in overrides.items():
                name_lc = name.lower()
                if name_lc in registry:
                    registry[name_lc].update(meta)
                else:
                    registry[name_lc] = meta
    except Exception:
        pass  # Silently fall back to defaults if config is missing or malformed
    return registry


# Populate at import time
MODULE_REGISTRY = _load_module_registry()


def reload_module_registry() -> dict[str, dict]:
    """
    Re-read modules.json and reload the registry at runtime.
    Useful if modules.json was updated while the server is running.
    """
    global MODULE_REGISTRY
    MODULE_REGISTRY = _load_module_registry()
    return MODULE_REGISTRY


def get_module(name: str) -> Optional[dict]:
    """
    Look up a module by @name (case-insensitive).
    Returns the metadata dict, or None if the module is not registered.
    """
    return MODULE_REGISTRY.get(name.lower())


def list_modules(status_filter: str = "") -> list[tuple[str, dict]]:
    """
    Return all registered modules as (name, metadata) tuples.
    If status_filter is given (e.g. "active", "partial"), only return
    modules with that status value.
    """
    items = list(MODULE_REGISTRY.items())
    if status_filter:
        items = [(n, m) for n, m in items if m.get("status") == status_filter]
    return items


def is_ncl_message(content: str) -> bool:
    """
    Quick check: does this message contain NCL module calls?

    A message is considered NCL if it contains BOTH:
    1. At least one non-orchestrator @mention (not @Claude/@Gemini/@Nova/@all), AND
    2. At least one structural NCL token: [[ ]], (( )), << >>, ;; or ::

    The structural token requirement prevents bare "@mentor, what do you think?"
    from being misrouted as NCL — that should go through the normal orchestrator.
    A proper NCL call always includes [[instructions]], ((criteria)), or similar.

    Imports nova_lang lazily to avoid circular import at module load.
    """
    # Quick structural token check (fast path before importing nova_lang)
    _NCL_STRUCTURAL = ("[[", "((", "<<", ";;", " :: ")
    if not any(tok in content for tok in _NCL_STRUCTURAL):
        return False
    try:
        from nova_chat.nova_lang import extract_module_names
        return len(extract_module_names(content)) > 0
    except ImportError:
        return False


def parse_directed(content: str) -> list[str]:
    """
    Parse @mentions from message content, resolving role aliases.

    Direct:  @Claude, @Gemini, @Nova
    Roles:   @mentor → Claude + Gemini
             @all    → Claude + Gemini + Nova

    Returns a deduplicated list in canonical RESPONSE_ORDER order.
    Empty list = no explicit mentions (Nova responds by default).
    """
    mentioned: set[str] = set()

    # Individual participant names
    for name in PARTICIPANTS:
        if re.search(rf"@{name}\b", content, re.IGNORECASE):
            mentioned.add(name)

    # Role aliases
    for role, members in ROLES.items():
        if re.search(rf"@{role}\b", content, re.IGNORECASE):
            for m in members:
                mentioned.add(m)

    # Return in canonical order (not insertion order)
    return [p for p in RESPONSE_ORDER if p in mentioned]


def build_response_queue(directed_at: list[str], available: dict) -> list[str]:
    """
    Build the ordered list of AIs that should respond to a message.

    Rules:
      • No @mentions → only Nova (default responder), if online.
      • @mentions with Claude/Gemini → those listeners first (in order),
        then Nova appended at end so she sees their responses.
      • @Nova only → just Nova.
      • Offline AIs are skipped.

    Returns ordered list, e.g. ["Claude", "Gemini", "Nova"].
    """
    if not directed_at:
        # Default: only Nova
        return ["Nova"] if available.get("Nova") else []

    queue: list[str] = []
    for name in RESPONSE_ORDER:
        if name in directed_at and available.get(name):
            queue.append(name)

    # If any listener (Claude/Gemini) is in the queue, Nova always goes last
    # so she can read their responses.  Add her if not already included.
    has_listeners = any(n in directed_at for n in ("Claude", "Gemini"))
    if has_listeners and "Nova" not in queue and available.get("Nova"):
        queue.append("Nova")

    return queue


def should_respond(ai_name: str, directed_at: list[str]) -> bool:
    """
    Legacy compatibility shim for any callers that haven't been updated.
    Prefer build_response_queue() for primary dispatch logic.
    """
    mock_available = {n: True for n in PARTICIPANTS}
    return ai_name in build_response_queue(directed_at, mock_available)
