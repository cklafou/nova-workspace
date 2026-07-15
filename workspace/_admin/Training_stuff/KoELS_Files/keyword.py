# Last updated: 2026-07-15 23:14:48
"""Keyword decision strategy — the first (and simplest) DecisionStrategy.

PLUCK-SAFE: pure. Tokenizes the task and scores each manifest by which of its
trigger terms appear, weighted. Deterministic, fast, no I/O.

This is intentionally the *baseline*. Because the faculty depends only on the
DecisionStrategy protocol, a smarter strategy (e.g. model-judged: "this reads like a
chess question -> gaming") can replace this later without changing the faculty. The
exact scoring heuristic here is tunable and not load-bearing for the architecture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from ..manifest import Manifest


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


@dataclass
class KeywordStrategy:
    """Score = summed weight of matched triggers, linearly mapped to 0..1.

    Parameters
    ----------
    full_match_weight : float
        Matched-weight at which confidence saturates to 1.0. With the default of 2.0,
        one ordinary trigger (weight 1.0) -> 0.5; a weight-2.0 primary term, or two
        ordinary hits -> 1.0. Tune per how eager you want auto-equip to be.

    Matching rules (predictable on purpose):
      * single-word trigger  -> exact token match (so "game" does NOT match "gamer";
        list plural/variant forms explicitly in the manifest if you want them)
      * multi-word trigger    -> substring match on the lowercased task
    """

    full_match_weight: float = 2.0

    def rank(self, task: str, manifests: Sequence[Manifest]) -> list[tuple[Manifest, float]]:
        text = task.lower()
        tokens = _tokenize(text)

        scored: list[tuple[Manifest, float]] = []
        for m in manifests:
            matched_weight = 0.0
            for trig in m.triggers:
                t = trig.lower().strip()
                if not t:
                    continue
                hit = (t in text) if (" " in t) else (t in tokens)
                if hit:
                    matched_weight += m.weight_for(trig)

            if matched_weight <= 0.0:
                confidence = 0.0
            else:
                confidence = min(1.0, matched_weight / max(self.full_match_weight, 1e-9))
            scored.append((m, confidence))

        # Best first. Tie-break on the manifest's declared priority, then name for
        # deterministic ordering.
        scored.sort(key=lambda pair: (pair[1], pair[0].priority, pair[0].name), reverse=True)
        return scored
