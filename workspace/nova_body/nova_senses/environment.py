# Last updated: 2026-07-08 08:43:33
# @nova: Environmental perception — I sense my surroundings: which of my watched places
#        changed since I last looked, Cole's standing directive (his word = Priority 0),
#        and whether he's typing. The filesystem is universal, so I read it directly.
"""
nova_senses/environment.py — Nova's perception of her workspace + Cole's presence
=================================================================================
Pure file/logic — no chat/server dependency. The live chat transcript lives in a
tool, so "did Cole just speak in chat" is supplied to the executive via Capabilities;
here we perceive what is on disk: watched-path changes, the mirrored directive, typing.
"""

import os
import json
from datetime import datetime
from pathlib import Path

WORKSPACE_ROOT = (Path(os.environ["NOVA_WORKSPACE"]) if "NOVA_WORKSPACE" in os.environ
                  else Path(__file__).resolve().parent.parent.parent)
_COLE_INTENT = WORKSPACE_ROOT / "memory" / "cole_intent.json"
_INTERRUPT = WORKSPACE_ROOT / "memory" / "interrupt_inbox.json"


def fingerprint(watch_paths) -> tuple:
    """A cheap, comparable snapshot of watched files/dirs. Changes when any is touched."""
    parts = []
    for rel in (watch_paths or []):
        p = WORKSPACE_ROOT / rel
        try:
            if p.is_dir():
                entries = sorted(q.name for q in p.iterdir())
                parts.append((rel, len(entries), int(p.stat().st_mtime)))
            elif p.exists():
                st = p.stat()
                parts.append((rel, st.st_size, int(st.st_mtime)))
            else:
                parts.append((rel, -1, 0))
        except Exception:
            parts.append((rel, -2, 0))
    return tuple(parts)


def changed(prev_fp, watch_paths) -> bool:
    return fingerprint(watch_paths) != prev_fp


def cole_directive() -> str:
    """Cole's current standing instruction (Priority 0), or '' if none/consumed."""
    try:
        if _COLE_INTENT.exists():
            ci = json.loads(_COLE_INTENT.read_text(encoding="utf-8"))
            if ci.get("text") and not ci.get("consumed"):
                return ci["text"]
    except Exception:
        pass
    return ""


def record_cole_directive(text: str) -> None:
    """Persist Cole's latest instruction so it survives a cold wake. Called by the host
    when Cole speaks (the trigger comes from comms; the record lives on disk)."""
    try:
        _COLE_INTENT.parent.mkdir(parents=True, exist_ok=True)
        payload = {"text": text, "ts": datetime.now().isoformat(), "consumed": False}
        tmp = _COLE_INTENT.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, _COLE_INTENT)
    except Exception as e:
        print(f"[environment] cole_intent write failed: {e}")


def consume_cole_directive() -> None:
    """Mark the standing directive as attended-to so it stops re-surfacing."""
    try:
        if _COLE_INTENT.exists():
            ci = json.loads(_COLE_INTENT.read_text(encoding="utf-8"))
            ci["consumed"] = True
            _COLE_INTENT.write_text(json.dumps(ci, indent=2), encoding="utf-8")
    except Exception:
        pass


def cole_typing() -> bool:
    """True if Cole is typing or typed within the last 30s (don't act over him)."""
    try:
        if _INTERRUPT.exists():
            ib = json.loads(_INTERRUPT.read_text(encoding="utf-8"))
            lt = ib.get("last_typed_at", 0)
            import time as _t
            return bool(ib.get("is_typing")) or (lt and (_t.time() - lt) < 30)
    except Exception:
        pass
    return False
