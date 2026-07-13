# Last updated: 2026-07-13 19:12:53
"""KoELS decision faculty — the pure-logic part of Nova's cognition that decides
WHICH loadout (if any) a task wants, and whether to swap.

PLUCK-SAFE: zero outward calls. No model, no GPU, no DB, no file I/O. It takes a
task + the available manifests and RETURNS a decision; the runtime is what acts on
that decision (loads/unloads adapters). Deciding is cognition; equipping is a bodily
act delegated to the runtime — and that delegation is how this passes the pluck test,
not a violation of it.

Design:
  * The faculty is SCAFFOLDING. The actual "which fits" judgment lives behind a
    swappable `DecisionStrategy`. Today: KeywordStrategy. Later: a model-judged
    strategy can drop in WITHOUT touching this faculty.
  * Routing is autonomous (strategy picks) but Cole can override manually, and a
    manual override always wins.

Invariant honored: Nova-core is ALWAYS loaded underneath. A decision is only ever
about the *specialist on top*. So:
    EQUIP  -> Nova-core + <loadout>
    STAY   -> keep whatever's current (loadout=None means Nova-core only)
    UNEQUIP-> drop back to Nova-core only
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, Sequence, runtime_checkable

from .manifest import Manifest


class Action(str, Enum):
    EQUIP = "equip"        # load a specialist on top of Nova-core
    STAY = "stay"          # keep current state (no change)
    UNEQUIP = "unequip"    # drop back to Nova-core only


@dataclass(frozen=True)
class LoadoutDecision:
    """What the faculty decided. Inert data — the runtime reads this and acts."""

    action: Action
    loadout: str | None          # target specialist name; None = Nova-core only
    reason: str                  # human-readable why (for logs / transparency)
    source: str                  # "auto" | "manual"
    confidence: float            # 0..1 (1.0 for manual)
    ranked: tuple[tuple[str, float], ...] = ()   # (loadout, score) best-first, for transparency
    ok: bool = True              # False flags a problem (e.g. unknown manual loadout)

    def __str__(self) -> str:  # pragma: no cover - convenience
        tgt = self.loadout or "nova-core only"
        return f"{self.action.value.upper()} -> {tgt}  [{self.source}, conf={self.confidence:.2f}]  ({self.reason})"


@dataclass(frozen=True)
class ManualOverride:
    """Cole's explicit choice. `equip(name)` to force a loadout; `to_core()` to
    force Nova-core only. A manual override always beats the autonomous strategy."""

    loadout: str | None = None
    unequip: bool = False

    @classmethod
    def equip(cls, name: str) -> "ManualOverride":
        return cls(loadout=str(name).strip().lower())

    @classmethod
    def to_core(cls) -> "ManualOverride":
        return cls(unequip=True)


@runtime_checkable
class DecisionStrategy(Protocol):
    """Swappable judgment. Pure: given a task + manifests, rank them by fit.

    Returns a list of (Manifest, confidence-in-0..1), best first. The faculty turns
    that ranking into an Action. Implementations MUST stay pure (no I/O) to preserve
    the pluck-test guarantee — a model-judged strategy would still return a ranking,
    just computed differently upstream.
    """

    def rank(self, task: str, manifests: Sequence[Manifest]) -> list[tuple[Manifest, float]]:
        ...


@dataclass
class KoELSDecisionFaculty:
    """Decides loadout from task + manifests using a swappable strategy.

    Parameters
    ----------
    strategy : DecisionStrategy
        The judgment engine (keyword today, model-judged later).
    min_confidence : float
        Below this, no specialist is chosen (autonomous path).
    unequip_when_no_match : bool
        If False (default), an already-loaded specialist is KEPT when a new task
        doesn't clearly match anything — avoids thrashing off a loadout for a stray
        general question. If True, no-match drops back to Nova-core.
    """

    strategy: DecisionStrategy
    min_confidence: float = 0.5
    unequip_when_no_match: bool = False

    def decide(
        self,
        *,
        task: str,
        manifests: Sequence[Manifest],
        currently_loaded: str | None = None,
        manual_override: ManualOverride | None = None,
    ) -> LoadoutDecision:
        current = (currently_loaded or "").strip().lower() or None
        by_name = {m.name: m for m in manifests}

        # 1) Manual override always wins.
        if manual_override is not None:
            return self._decide_manual(manual_override, by_name, current)

        # 2) Autonomous: rank via the strategy.
        ranked = self.strategy.rank(task, list(manifests))
        ranked_pairs = tuple((m.name, round(float(c), 3)) for m, c in ranked)

        best_name: str | None = None
        best_conf = 0.0
        if ranked:
            best_name, best_conf = ranked[0][0].name, float(ranked[0][1])

        # 2a) Nothing clears the bar -> no clear domain.
        if best_name is None or best_conf < self.min_confidence:
            if current is not None and not self.unequip_when_no_match:
                return LoadoutDecision(
                    Action.STAY, current,
                    "No new domain matched above threshold; keeping current loadout.",
                    "auto", best_conf, ranked_pairs,
                )
            if current is not None and self.unequip_when_no_match:
                return LoadoutDecision(
                    Action.UNEQUIP, None,
                    "No domain matched above threshold; dropping to Nova-core only.",
                    "auto", best_conf, ranked_pairs,
                )
            return LoadoutDecision(
                Action.STAY, None,
                "No domain matched above threshold; staying on Nova-core only.",
                "auto", best_conf, ranked_pairs,
            )

        # 2b) Best match is already loaded -> don't swap needlessly.
        if best_name == current:
            return LoadoutDecision(
                Action.STAY, current,
                f"Best match '{best_name}' is already loaded.",
                "auto", best_conf, ranked_pairs,
            )

        # 2c) A different specialist clearly fits -> equip it.
        return LoadoutDecision(
            Action.EQUIP, best_name,
            f"Task matches '{best_name}' (confidence {best_conf:.2f}).",
            "auto", best_conf, ranked_pairs,
        )

    # ------------------------------------------------------------------ manual

    def _decide_manual(
        self,
        override: ManualOverride,
        by_name: dict[str, Manifest],
        current: str | None,
    ) -> LoadoutDecision:
        # Force Nova-core only.
        if override.unequip:
            if current is None:
                return LoadoutDecision(
                    Action.STAY, None, "Manual: already on Nova-core only.",
                    "manual", 1.0,
                )
            return LoadoutDecision(
                Action.UNEQUIP, None, "Manual: drop to Nova-core only.",
                "manual", 1.0,
            )

        name = (override.loadout or "").strip().lower()
        # Unknown loadout named -> don't act, flag it (faculty never raises; runtime
        # calls this every turn and should get a usable decision, not an exception).
        if name not in by_name:
            return LoadoutDecision(
                Action.STAY, current,
                f"Manual override named unknown loadout '{name}'; staying as-is.",
                "manual", 0.0, ok=False,
            )
        if name == current:
            return LoadoutDecision(
                Action.STAY, current, f"Manual: '{name}' already loaded.",
                "manual", 1.0,
            )
        return LoadoutDecision(
            Action.EQUIP, name, f"Manual override: equip '{name}'.",
            "manual", 1.0,
        )
