# Last updated: 2026-07-15 23:14:48
"""Runnable tests / demo for the KoELS decision core.

Pure: loads the example manifest JSONs from disk HERE (the test plays the role of
the runtime/loader), then exercises the faculty with no model/GPU/DB. Proves the
decision logic before any of it goes near the runtime.

Run from the package parent dir:
    python -m koels.test_koels
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from koels import (
    Manifest,
    KoELSDecisionFaculty,
    KeywordStrategy,
    ManualOverride,
    Action,
)

HERE = Path(__file__).resolve().parent
MANIFEST_DIR = HERE / "manifests"


def load_manifests() -> list[Manifest]:
    """Edge I/O lives here (test/runtime), NOT in the pure core."""
    manifests = []
    for p in sorted(MANIFEST_DIR.glob("*.json")):
        with open(p, "r", encoding="utf-8") as fh:
            manifests.append(Manifest.from_dict(json.load(fh)))
    return manifests


def main() -> int:
    manifests = load_manifests()
    faculty = KoELSDecisionFaculty(strategy=KeywordStrategy(), min_confidence=0.5)

    names = ", ".join(m.name for m in manifests)
    print(f"Loaded manifests: {names}\n")

    failures = 0

    def check(label: str, decision, *, action: Action, loadout, source: str | None = None):
        nonlocal failures
        ok = decision.action == action and decision.loadout == loadout
        if source is not None:
            ok = ok and decision.source == source
        flag = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"[{flag}] {label}")
        print(f"        -> {decision}")
        if decision.ranked:
            print(f"        ranked: {decision.ranked}")
        print()

    # 1) Clear domain match -> equip gaming.
    d = faculty.decide(task="help me with my chess opening, I keep losing", manifests=manifests)
    check("chess question -> equip gaming", d, action=Action.EQUIP, loadout="gaming", source="auto")

    # 2) Different clear domain -> equip finance.
    d = faculty.decide(task="should I rebalance my portfolio given these earnings?", manifests=manifests)
    check("portfolio question -> equip finance", d, action=Action.EQUIP, loadout="finance", source="auto")

    # 3) No domain match -> stay on Nova-core only.
    d = faculty.decide(task="can you help me write a birthday message for my friend", manifests=manifests)
    check("unrelated task -> stay nova-core only", d, action=Action.STAY, loadout=None, source="auto")

    # 4) Best match already loaded -> no needless swap.
    d = faculty.decide(task="another clash royale matchup question", manifests=manifests, currently_loaded="gaming")
    check("already in gaming -> stay (no thrash)", d, action=Action.STAY, loadout="gaming", source="auto")

    # 5) Loaded specialist + unrelated task -> KEEP loadout (default no-thrash).
    d = faculty.decide(task="what's a good name for this variable", manifests=manifests, currently_loaded="gaming")
    check("gaming loaded + general task -> stay gaming (no-thrash default)", d, action=Action.STAY, loadout="gaming", source="auto")

    # 5b) Same, but with unequip_when_no_match=True -> drop to core.
    eager = KoELSDecisionFaculty(strategy=KeywordStrategy(), min_confidence=0.5, unequip_when_no_match=True)
    d = eager.decide(task="what's a good name for this variable", manifests=manifests, currently_loaded="gaming")
    check("gaming loaded + general task (eager) -> unequip to core", d, action=Action.UNEQUIP, loadout=None, source="auto")

    # 6) Manual override wins over autonomous read.
    d = faculty.decide(task="help me with my chess opening", manifests=manifests, manual_override=ManualOverride.equip("finance"))
    check("manual override finance beats chess task", d, action=Action.EQUIP, loadout="finance", source="manual")

    # 7) Manual override to Nova-core only.
    d = faculty.decide(task="anything", manifests=manifests, currently_loaded="gaming", manual_override=ManualOverride.to_core())
    check("manual to_core while gaming -> unequip", d, action=Action.UNEQUIP, loadout=None, source="manual")

    # 8) Manual override naming an unknown loadout -> stay + flagged not-ok.
    d = faculty.decide(task="anything", manifests=manifests, currently_loaded=None, manual_override=ManualOverride.equip("legal"))
    check("manual override unknown 'legal' -> stay + flagged", d, action=Action.STAY, loadout=None, source="manual")
    assert d.ok is False, "unknown manual loadout should set ok=False"
    print("        (ok flag correctly False for unknown loadout)\n")

    print("=" * 60)
    if failures:
        print(f"RESULT: {failures} FAILURE(S)")
        return 1
    print("RESULT: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
