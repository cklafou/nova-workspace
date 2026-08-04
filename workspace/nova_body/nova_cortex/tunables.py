# Last updated: 2026-08-05 08:51:21
# @nova: nova_cortex/tunables.py — LIVE-TUNABLE knobs. Cole (2026-08-03): "make things that
#   should be easily changed into adjustable variables, with a tool that adjusts them on the
#   fly." This is that registry. Any constant Cole might reasonably want to change WITHOUT a
#   code edit + restart belongs here. get() re-reads the store every call, so a change made in
#   the Variables panel takes effect on her NEXT turn — no restart. See Orient/TUNABLE_VARIABLES.md.
"""
nova_cortex/tunables.py — the one place live-adjustable parameters live.

    from nova_cortex import tunables
    rounds = tunables.get("witness_max_rounds")     # hot: reflects the latest panel change

Design rules (why it is shaped this way):
  - FAIL-SAFE. These govern her cognition. A missing/corrupt store, a bad value, a type
    mismatch — none of it may ever raise into her turn. Every path falls back to the registered
    default. A knob that could crash her is worse than a knob that can't be tuned.
  - HOT. get() reads _admin/tunables.json each call (tiny file, cached 2s to avoid hammering
    disk in a tight loop). The panel writes the file; her next turn reads the new value. No
    restart, no import reload.
  - BOUNDED. Every knob declares a type and, for numbers, a min/max. set() clamps/validates —
    the panel cannot push a value that would break her (e.g. 0 witness rounds, or 10000 loops).
  - SELF-DESCRIBING. The registry carries label/desc/category so the panel and the API render
    themselves with no duplicated UI config.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

_WS = (Path(os.environ["NOVA_WORKSPACE"]) if "NOVA_WORKSPACE" in os.environ
       else Path(__file__).resolve().parents[2])
_STORE = _WS / "_admin" / "tunables.json"

# ── THE REGISTRY ─────────────────────────────────────────────────────────────────────────────
# Add a knob here the moment you find yourself wanting to change a constant to see what happens.
# type: "int" | "float" | "bool".  For numbers, min/max bound the panel control and clamp set().
REGISTRY: dict = {
    "witness_max_rounds": {
        "default": 20, "type": "int", "min": 1, "max": 40, "category": "Witness",
        "label": "Witness rounds — text",
        "desc": "Max back-and-forth between Nova and her witness on a TEXT turn before the "
                "dispute is sealed (and, if still disputed, escalated to the cloud judge). "
                "Cole's original ask that started this system."},
    "witness_max_rounds_voice": {
        "default": 2, "type": "int", "min": 1, "max": 8, "category": "Witness",
        "label": "Witness rounds — voice",
        "desc": "Same, for VOICE turns. Kept low so a person on a mic isn't left waiting out a "
                "debate; the cloud heavy-witness still settles the record afterward."},
    "witness_deadlock_repeats": {
        "default": 3, "type": "int", "min": 2, "max": 10, "category": "Witness",
        "label": "Deadlock threshold",
        "desc": "How many times the same objection may return with NO new evidence between "
                "rounds before the loop is declared deadlocked and ends. Lower = quicker to "
                "stop two minds restating themselves."},
    "heavy_witness_enabled": {
        "default": True, "type": "bool", "category": "Witness",
        "label": "Cloud heavy witness",
        "desc": "On a disputed verdict, escalate to the cloud 32B judge for a logged second "
                "opinion (fail-open, logs-only, ~$0.008/dispute). Turning this off keeps every "
                "audit fully local."},
    "hold_back_streaming": {
        "default": True, "type": "bool", "category": "Witness",
        "label": "Hold-back streaming",
        "desc": "Buffer her draft AND the whole turnabout debate — nothing reaches chat "
                "until the witness clears it, then only the resolved answer ships. The "
                "thinking-leak fix: no tool-call JSON or reasoning flashing on screen "
                "mid-turn. OFF = old behavior, the draft streams live as she writes it. "
                "Human turns only — autonomous ticks always stream to the Monitor pane."},
    "binding_cloud_escalation": {
        "default": True, "type": "bool", "category": "Witness",
        "label": "Binding cloud escalation",
        "desc": "On a checkable-FACT dispute the local witness can't settle, pause and ask "
                "the cloud arbiter (ping-verified, ~8s) who's right, and ACT on its ruling "
                "instead of only logging it. If the cloud can't be reached in time, Nova gets "
                "one consensus turn as the final authority (keep or revise, her call). OFF = "
                "the cloud stays a background logs-only opinion and her draft ships as-is."},
    "max_tool_loops": {
        "default": 60, "type": "int", "min": 10, "max": 120, "category": "Cognition",
        "label": "Max tool-chain depth",
        "desc": "How many tool calls Nova may chain in ONE turn before the loop force-delivers "
                "a best-effort answer instead of running forever. Witness rounds and guard "
                "retries draw from this same budget."},
    "voice_fast_thinking_off": {
        "default": True, "type": "bool", "category": "Voice",
        "label": "Voice-fast skips reasoning",
        "desc": "For register 'voice_fast' (casual chit-chat), skip the <think> pass on the "
                "first spoken reply for ~1s first audio. Off = always reason, even on 'hey'."},
}

_CACHE: dict = {"t": 0.0, "data": {}}
_CACHE_TTL_S = 2.0


def _read() -> dict:
    """Read the store, cached briefly. Never raises — returns {} on any problem."""
    now = time.time()
    if now - _CACHE["t"] < _CACHE_TTL_S:
        return _CACHE["data"]
    data = {}
    try:
        if _STORE.exists():
            data = json.loads(_STORE.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict):
                data = {}
    except Exception:
        data = {}
    _CACHE["t"] = now
    _CACHE["data"] = data
    return data


def _coerce(value, meta):
    """Force `value` to the knob's declared type and bounds. Returns the default on any failure
    so a garbage store value can never poison a turn."""
    t = meta.get("type", "int")
    try:
        if t == "bool":
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "yes", "on")
            return bool(value)
        if t == "int":
            v = int(value)
        elif t == "float":
            v = float(value)
        else:
            return value
        lo, hi = meta.get("min"), meta.get("max")
        if lo is not None:
            v = max(lo, v)
        if hi is not None:
            v = min(hi, v)
        return v
    except Exception:
        return meta.get("default")


def get(key: str):
    """The value of a knob — hot (reflects the latest panel change), validated, fail-safe.
    An unregistered key returns None (with a print), never raises."""
    meta = REGISTRY.get(key)
    if meta is None:
        print(f"[tunables] unknown knob '{key}' — returning None (register it in tunables.py)")
        return None
    raw = _read().get(key, meta["default"])
    return _coerce(raw, meta)


def set(key: str, value) -> dict:
    """Set a knob (validated + clamped) and persist atomically. Returns
    {ok, key, value, [why]}. Never raises."""
    meta = REGISTRY.get(key)
    if meta is None:
        return {"ok": False, "why": f"unknown knob '{key}'"}
    coerced = _coerce(value, meta)
    try:
        data = {}
        if _STORE.exists():
            try:
                data = json.loads(_STORE.read_text(encoding="utf-8")) or {}
            except Exception:
                data = {}
        data[key] = coerced
        _STORE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STORE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        os.replace(tmp, _STORE)
        _CACHE["t"] = 0.0        # bust cache so the change is visible immediately
        return {"ok": True, "key": key, "value": coerced}
    except Exception as e:
        return {"ok": False, "why": str(e)[:200], "key": key}


def snapshot() -> list:
    """Every knob with its live value + metadata, for the panel / API to render itself."""
    out = []
    for key, meta in REGISTRY.items():
        item = {"key": key, "value": get(key)}
        item.update({k: meta[k] for k in
                     ("default", "type", "min", "max", "label", "desc", "category") if k in meta})
        out.append(item)
    return out


def reset(key: str) -> dict:
    """Restore a knob to its registered default."""
    meta = REGISTRY.get(key)
    if meta is None:
        return {"ok": False, "why": f"unknown knob '{key}'"}
    return set(key, meta["default"])


if __name__ == "__main__":
    print("Tunables registry:")
    for item in snapshot():
        print(f"  {item['key']:28} = {item['value']!r:>7}  [{item.get('category')}] {item['label']}")
