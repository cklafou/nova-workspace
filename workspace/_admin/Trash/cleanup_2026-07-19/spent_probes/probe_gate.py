# Last updated: 2026-07-19 19:47:30
# nightwatch probe 2026-07-14 23:0x — does her own wake scaffolding trip her honesty gate?
# Read-only: builds the Phase 1/2 prompts exactly as the daemon does and asks the gate about them.
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "nova_body"))
from nova_cortex import integrity, executive

refl = executive.build_reflection(cole_pending=False, reason="scheduled wake", recent="",
                                  last_reflection="(probe)")
dec = executive.build_decision("(probe reflection about the night)", False, "scheduled wake", "")

for name, p in (("phase1_reflection", refl), ("phase2_decision", dec)):
    print(f"{name}: was_asked_to_act = {integrity.was_asked_to_act(p)}")
    # which rule fires?
    import re
    print("  imperative :", bool(integrity._IMPERATIVE_RE.search(p)))
    print("  question   :", bool(integrity._QUESTION_RE.search(p)))
    ct = integrity._CONCRETE_TARGET_RE.search(p)
    aw = re.search(integrity._ACTION_WORDS, p, re.IGNORECASE)
    print("  target+verb:", bool(ct and aw),
          "| target =", (ct.group(0) if ct else None), "| verb =", (aw.group(0) if aw else None))
print("first line of phase1:", refl.splitlines()[0][:70])
print("first line of phase2:", dec.splitlines()[0][:70])
