# Last updated: 2026-07-08 08:43:32
# @nova: Loadout-decision faculty — KoELS cognition (layer 1, pure, pluck-safe). Given a task and
#        the set of expert manifests, it DECIDES which specialist loadout (if any) the task wants,
#        and whether equipping it is INSTANT (already loaded) or HEAVY (needs a self-restart to
#        load). It makes ZERO outward calls — no GPU, no model load, no DB, no llama. Her runtime
#        ACTS on the decision; this only decides. That split is how KoELS passes the pluck test
#        (spec §3): delete the chat server and she still decides "I want the gaming brain"; her
#        runtime still equips it. Nova-core is always loaded underneath — a specialist is gained
#        on top of who she is, never instead of it.
"""
nova_cortex/loadout.py — the buildable-now, fully pluck-safe first KoELS deliverable.

Pure functions over manifests + task text + the runtime's loaded-set status:
  load_manifests(koels_dir)              -> {name: manifest}     (scan KoELS/*/manifest.json)
  decide_loadout(task_text, manifests, loaded) -> decision dict   (which loadout, how costly)
  loadout_status(manifests, loaded_ids)  -> {loaded, available_not_loaded, all}

The runtime supplies `loaded` (the live /lora-adapters set); this never queries it itself.
"""

import json
from pathlib import Path


def load_manifests(koels_dir) -> dict:
    """Scan KoELS/*/manifest.json → {name: manifest}. Pure file read. Tolerant: a missing dir
    returns {}, a malformed manifest is skipped (one bad expert never breaks the others)."""
    out: dict = {}
    base = Path(koels_dir)
    if not base.exists():
        return out
    for mpath in sorted(base.glob("*/manifest.json")):
        try:
            m = json.loads(mpath.read_text(encoding="utf-8"))
        except Exception:
            continue
        name = m.get("name") or mpath.parent.name
        m["_dir"] = str(mpath.parent)
        out[name] = m
    return out


def _trigger_terms(manifest: dict) -> list:
    """The lowercased keyword + intent terms this expert routes on."""
    t = manifest.get("trigger") or {}
    terms = [str(k).lower() for k in (t.get("keywords") or [])]
    terms += [str(i).lower() for i in (t.get("intents") or [])]
    return [term for term in terms if term]


def decide_loadout(task_text: str, manifests: dict, loaded=None) -> dict:
    """Pure decision: which loadout does this task want, and how costly is it to equip?

    Returns:
      {
        "loadout": <name> | None,       # the specialist wanted, or None = stay Nova-core only
        "matched": [terms...],          # which trigger terms hit (for transparency)
        "equip":   "none" | "instant" | "restart",
        "reason":  <human-readable why>
      }

    `loaded` = names of specialists currently loaded (from the runtime status surface). Used ONLY
    to label instant (in the loaded set → free /lora-adapters swap) vs restart (on disk, needs a
    boot-time --lora reload). No side effects; safe to call anywhere, anytime.
    """
    loaded_set = set(loaded or [])
    text = (task_text or "").lower()

    # Score each expert by how many of its trigger terms appear in the task. Highest wins;
    # ties break toward the first by sorted name (deterministic). No match → Nova-core only.
    best_name, best_hits = None, []
    for name in sorted(manifests):
        hits = [term for term in _trigger_terms(manifests[name]) if term in text]
        if len(hits) > len(best_hits):
            best_name, best_hits = name, hits

    if not best_name:
        return {"loadout": None, "matched": [], "equip": "none",
                "reason": "no specialist trigger matched — stay Nova-core only"}

    equip = "instant" if best_name in loaded_set else "restart"
    reason = (f"task matches '{best_name}' on {best_hits} — "
              + ("already loaded, instant equip"
                 if equip == "instant"
                 else "not loaded, needs a self-restart to add it to the boot set"))
    return {"loadout": best_name, "matched": best_hits, "equip": equip, "reason": reason}


def loadout_status(manifests: dict, loaded_ids=None) -> dict:
    """Diff what's AVAILABLE on disk (manifests) against what's LOADED now (runtime-supplied).
    Pure perception her decision faculty reads — `loaded` are instant-equip, `available_not_loaded`
    would each cost a self-restart. `loaded_ids` = specialist names currently loaded."""
    loaded_set = set(loaded_ids or [])
    available = list(manifests.keys())
    return {
        "loaded": sorted(n for n in available if n in loaded_set),
        "available_not_loaded": sorted(n for n in available if n not in loaded_set),
        "all": sorted(available),
    }
