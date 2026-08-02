# Tunable Variables — a coding convention

_Established 2026-08-03 (Cole). Applies to all of Nova's scripts going forward._

## The rule

**Any constant that Cole (or Nova) might reasonably want to change without editing code and
restarting belongs in the tunables registry, not as a literal in the script.**

If you catch yourself writing a magic number that governs behavior — how many witness rounds,
how deep a tool chain may go, a threshold, a timeout, an on/off for a whole feature — stop and
ask: *would we ever want to turn this knob live to see what happens?* If yes, register it. The
cost is three lines; the payoff is tuning her by feel instead of by redeploy.

## How it works

- **Registry + storage:** `nova_body/nova_cortex/tunables.py`. Each knob declares a default,
  type (`int`/`float`/`bool`), bounds (`min`/`max`), a human `label`, a `desc`, and a `category`.
  Values persist to `_admin/tunables.json`.
- **Reading a knob (hot):** `tunables.get("key")` re-reads the store each call, so a change takes
  effect on the **next turn** — no restart. In `nova.py` use the fail-safe wrapper:
  `_tune("key", fallback)` — if the registry can't load, it returns the literal you'd have
  hardcoded, so a tuning system can never break the thing it tunes.
- **Adjusting on the fly:** the **Variables** panel (Nova Chat → Widgets → Variables…, served at
  `/variables`), backed by `GET/POST /api/variables`. It renders itself from the registry —
  add a knob and it appears, no UI work.

## Adding a knob — the whole recipe

1. Register it in `tunables.py`'s `REGISTRY` (default, type, bounds, label, desc, category).
2. Replace the literal in your script with `tunables.get("your_key")` — or, inside `nova.py`,
   `_tune("your_key", <the old literal>)`.
3. That's it. The panel picks it up automatically.

```python
# in tunables.py REGISTRY:
"reach_watcher_enabled": {"default": True, "type": "bool", "category": "Cognition",
    "label": "Reach-watcher", "desc": "Run the solo-draft reach lint before shipping."},

# at the use site:
if tunables.get("reach_watcher_enabled"):
    ...
```

## Fail-safe rules (non-negotiable)

- **Never let a knob crash a turn.** `get()` returns the registered default on any error
  (missing file, corrupt JSON, bad value, unknown key). `_tune()` returns your fallback.
- **Bound every number.** `set()` clamps to `min`/`max`, so the panel can't push a value that
  breaks her (0 witness rounds, a 10,000-deep tool loop).
- **Defaults ARE the current behavior.** When you migrate a literal, its default must equal the
  literal, so registering a knob changes nothing until someone actually turns it.

## Currently registered

Witness rounds (text / voice), deadlock threshold, cloud heavy-witness on/off, max tool-chain
depth, voice-fast reasoning skip. Migrate more as you touch them — the goal is that Nova's
behavior is increasingly shaped by knobs Cole can feel out live, not by literals buried in code.
