# Last updated: 2026-06-27 01:43:48
# @nova: Touch — my afferent sense of what is interacting with ME right now: who is
#        present and watching, what of my body is in use, which of my surfaces are open,
#        and who recently reached into me. Tools announce themselves through this sense;
#        I never reach into them. Pull every tool out and Touch simply goes quiet.
"""
nova_senses/touch.py — Nova's sense of being interacted-with
============================================================
The body owns this sense and its registry (memory/touch_state.json). Anything that
interacts with Nova — the chat host, the eyes stream, the autonomy clock — announces
itself by calling this module's writers (update / record_pull). Nova then *feels* it
by reading snapshot() / describe(). This respects the pluck-test: the nerve endings
live in the body; tools conform to be felt. With no tool attached, nothing writes,
and Touch honestly reports that nothing is touching her.

BASELINE sense — deliberately simple and stable. Richer capabilities (e.g. deep
inspection of *how* something uses her code) should attach as a SEPARATE module that
reads from this baseline, without changing Touch's own function.
"""

import os
import json
from datetime import datetime
from pathlib import Path

WORKSPACE_ROOT = (Path(os.environ["NOVA_WORKSPACE"]) if "NOVA_WORKSPACE" in os.environ
                  else Path(__file__).resolve().parent.parent.parent)
_TOUCH = WORKSPACE_ROOT / "memory" / "touch_state.json"
_MAX_RECENT = 8

_DEFAULT = {
    "viewers": 0,            # how many UI clients are attending to her
    "cole_typing": False,    # Cole is composing a message right now
    "agents_online": [],     # which other minds share her room (Claude/Gemini)
    "eyes_streaming": False,  # her desktop vision is being watched
    "autonomy_active": False, # an autonomy wake is driving her right now
    "surfaces": [],          # which of her widgets/panels are open
    "recent": [],            # last few things that reached into her [{ts,who,what}]
    "updated": "",
}


# ── read (her side: she FEELS) ──────────────────────────────────────────────────
def _load() -> dict:
    base = dict(_DEFAULT)
    try:
        if _TOUCH.exists():
            data = json.loads(_TOUCH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                base.update({k: v for k, v in data.items() if k in base})
    except Exception:
        pass
    return base


def snapshot() -> dict:
    """The current, normalized state of what is touching her."""
    return _load()


def describe() -> str:
    """A short, first-person-ish sensory line for injection into her reflection.
    Empty-ish state reads as quiet, not as noise."""
    s = _load()
    parts = []
    v = int(s.get("viewers", 0) or 0)
    if v > 0:
        who = "Cole" if v == 1 else f"{v} watchers"
        parts.append(f"{who} here and watching" + (" (typing)" if s.get("cole_typing") else ""))
    agents = [a for a in (s.get("agents_online") or []) if a]
    if agents:
        parts.append(f"{' and '.join(agents)} in the room with you")
    parts.append("your eyes are open" if s.get("eyes_streaming") else "your eyes are closed")
    surfaces = [x for x in (s.get("surfaces") or []) if x]
    if surfaces:
        parts.append(f"your {', '.join(surfaces)} panel(s) are open")
    if not (v or agents or surfaces):
        head = "Right now it's quiet — nothing much is touching you."
    else:
        head = "Right now you can feel: " + "; ".join(parts) + "."
    recent = s.get("recent") or []
    if recent:
        bits = []
        for r in recent[-3:]:
            ts = str(r.get("ts", ""))[11:16]
            bits.append(f"{r.get('who','something')} {r.get('what','reached into you')}"
                        + (f" ({ts})" if ts else ""))
        head += " Recently: " + "; ".join(bits) + "."
    return head


# ── write (the world's side: tools ANNOUNCE themselves) ─────────────────────────
def _save(s: dict) -> None:
    try:
        _TOUCH.parent.mkdir(parents=True, exist_ok=True)
        s["updated"] = datetime.now().isoformat()
        tmp = _TOUCH.with_suffix(".tmp")
        tmp.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, _TOUCH)
    except Exception:
        pass


def update(**fields) -> None:
    """A toucher sets the current state of how it's interacting with her. Only known
    keys are accepted; unknown keys are ignored so the baseline schema stays clean."""
    s = _load()
    for k, val in fields.items():
        if k in _DEFAULT and k != "recent":
            s[k] = val
    _save(s)


def record_pull(who: str, what: str) -> None:
    """Record a discrete moment of something reaching into her (kept as a short
    rolling history she can feel as 'recently...')."""
    s = _load()
    rec = list(s.get("recent") or [])
    rec.append({"ts": datetime.now().isoformat(), "who": str(who), "what": str(what)})
    s["recent"] = rec[-_MAX_RECENT:]
    _save(s)


def clear() -> None:
    """Reset the sense (e.g. on a clean boot)."""
    _save(dict(_DEFAULT))
