# Last updated: 2026-07-13 19:12:53
"""KoELS — Knowledge of Experts Loadout System (decision core).

Pure-logic, pluck-safe pieces buildable before the runtime/equip layer exists:
  * Manifest / Oracle      -- the per-expert contract (manifest.py)
  * KoELSDecisionFaculty   -- decides which loadout a task wants (decision.py)
  * DecisionStrategy       -- swappable judgment; KeywordStrategy is the first impl

The faculty RETURNS a LoadoutDecision; it never loads weights or touches a GPU.
The runtime acts on the decision. That separation is the pluck test passing.
"""

from .manifest import Manifest, Oracle, ManifestError, ALLOWED_FUSION_MODES
from .decision import (
    Action,
    LoadoutDecision,
    ManualOverride,
    DecisionStrategy,
    KoELSDecisionFaculty,
)
from .strategies import KeywordStrategy

__all__ = [
    "Manifest",
    "Oracle",
    "ManifestError",
    "ALLOWED_FUSION_MODES",
    "Action",
    "LoadoutDecision",
    "ManualOverride",
    "DecisionStrategy",
    "KoELSDecisionFaculty",
    "KeywordStrategy",
]
