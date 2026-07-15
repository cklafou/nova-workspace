# Last updated: 2026-07-15 17:13:29
"""KoELS manifest model — the per-expert contract.

PLUCK-SAFE: pure logic. No file I/O, no model, no GPU, no network.
`Manifest.from_dict` takes an already-parsed dict (the runtime/loader reads the
JSON off disk; this module never touches the filesystem). This keeps the whole
decision core testable and runnable with nothing attached.

A manifest declares what one expert loadout IS, so adding a new expert means
dropping a folder with a manifest.json — never editing Nova's code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


ALLOWED_FUSION_MODES = ("adapter", "oracle_tool", "external_model")
# adapter        -> a LoRA stacked on Nova-core (the default; the KoELS norm)
# oracle_tool    -> expertise comes from an external ground-truth tool (e.g. an
#                   engine/API); Nova consults & explains it rather than reasoning
#                   from weights. (Chess -> Stockfish is the canonical case.)
# external_model -> a separate full model consulted and relayed (rare).


class ManifestError(ValueError):
    """Raised when a manifest dict is malformed. Carries a clear message."""


@dataclass(frozen=True)
class Oracle:
    """An external ground-truth tool an expert can consult.

    `invoke` is a descriptive reference (a command, an endpoint) that the RUNTIME
    interprets and calls. This model never executes anything — it just carries the
    declaration. Keeping it inert is what preserves the pluck-test boundary.
    """

    kind: str           # e.g. "stockfish", "http_api"
    invoke: str         # how the runtime reaches it (command / endpoint), descriptive
    notes: str = ""     # when/why to use it

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Oracle":
        kind = str(d.get("kind", "")).strip()
        invoke = str(d.get("invoke", "")).strip()
        if not kind:
            raise ManifestError("oracle.kind is required and must be non-empty")
        if not invoke:
            raise ManifestError("oracle.invoke is required and must be non-empty")
        return cls(kind=kind, invoke=invoke, notes=str(d.get("notes", "")).strip())


@dataclass(frozen=True)
class Manifest:
    """Declares one expert loadout. Frozen + hashable so it's safe to pass around.

    Durable vs volatile (the KoELS core law) lives here by reference, not value:
      - `adapter`        -> the trained LoRA weights (DURABLE expertise / reasoning)
      - `knowledge_db`   -> the LanceDB namespace (VOLATILE facts; updater writes it)
    The manifest only points at them; loading/querying is the runtime's job.
    """

    name: str                                   # unique id, e.g. "gaming" (lowercased)
    domain: str                                 # human-readable description
    triggers: tuple[str, ...]                   # terms used by keyword routing
    adapter: str                                # path/ref to the LoRA GGUF (durable brain)
    knowledge_db: str | None = None             # LanceDB namespace (None = pure reasoning)
    fusion_mode: str = "adapter"                # how the expertise attaches
    oracle: Oracle | None = None                # optional ground-truth tool
    visual: str | None = None                   # optional appearance ref (the loadout's "outfit")
    trigger_weights: Mapping[str, float] = field(default_factory=dict)  # per-term weight (default 1.0)
    priority: float = 1.0                       # tiebreaker when scores are equal
    notes: str = ""                             # freeform

    # ---- validation / construction -------------------------------------------------

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Manifest":
        """Build & validate from a parsed dict. Raises ManifestError on problems."""
        name = str(d.get("name", "")).strip().lower()
        if not name:
            raise ManifestError("manifest 'name' is required and must be non-empty")

        domain = str(d.get("domain", "")).strip()
        if not domain:
            raise ManifestError(f"[{name}] 'domain' is required and must be non-empty")

        raw_triggers = d.get("triggers", [])
        if not isinstance(raw_triggers, (list, tuple)) or not raw_triggers:
            raise ManifestError(f"[{name}] 'triggers' must be a non-empty list")
        triggers = tuple(str(t).strip() for t in raw_triggers if str(t).strip())
        if not triggers:
            raise ManifestError(f"[{name}] 'triggers' contained no usable terms")

        fusion_mode = str(d.get("fusion_mode", "adapter")).strip()
        if fusion_mode not in ALLOWED_FUSION_MODES:
            raise ManifestError(
                f"[{name}] fusion_mode '{fusion_mode}' invalid; "
                f"must be one of {ALLOWED_FUSION_MODES}"
            )

        adapter = str(d.get("adapter", "")).strip()
        oracle_raw = d.get("oracle")
        oracle = Oracle.from_dict(oracle_raw) if isinstance(oracle_raw, Mapping) else None

        # An adapter-mode expert needs an adapter. An oracle_tool-mode expert needs
        # an oracle. external_model is validated loosely here (runtime owns specifics).
        if fusion_mode == "adapter" and not adapter:
            raise ManifestError(f"[{name}] fusion_mode 'adapter' requires an 'adapter' ref")
        if fusion_mode == "oracle_tool" and oracle is None:
            raise ManifestError(f"[{name}] fusion_mode 'oracle_tool' requires an 'oracle' block")

        # trigger_weights: optional map of term -> float
        weights_raw = d.get("trigger_weights", {}) or {}
        if not isinstance(weights_raw, Mapping):
            raise ManifestError(f"[{name}] 'trigger_weights' must be an object/map")
        trigger_weights = {}
        for k, v in weights_raw.items():
            try:
                trigger_weights[str(k).strip()] = float(v)
            except (TypeError, ValueError):
                raise ManifestError(f"[{name}] trigger_weights['{k}'] must be a number")

        knowledge_db = d.get("knowledge_db")
        knowledge_db = str(knowledge_db).strip() if knowledge_db else None
        visual = d.get("visual")
        visual = str(visual).strip() if visual else None

        try:
            priority = float(d.get("priority", 1.0))
        except (TypeError, ValueError):
            raise ManifestError(f"[{name}] 'priority' must be a number")

        return cls(
            name=name,
            domain=domain,
            triggers=triggers,
            adapter=adapter,
            knowledge_db=knowledge_db,
            fusion_mode=fusion_mode,
            oracle=oracle,
            visual=visual,
            trigger_weights=trigger_weights,
            priority=priority,
            notes=str(d.get("notes", "")).strip(),
        )

    def weight_for(self, trigger: str) -> float:
        """Weight of a trigger term (defaults to 1.0 if unspecified)."""
        return float(self.trigger_weights.get(trigger, 1.0))
