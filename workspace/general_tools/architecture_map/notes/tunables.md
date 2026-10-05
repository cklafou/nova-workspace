<!-- @nova: Explain live tunable variables and distinguish source-defined context limits. -->
_Last updated: 2026-10-04 14:28:11_
---
doc: OPERATIONS.md
order: 20
---
<!-- @nova: Orient note: how tunable variables work and how to add one, published in OPERATIONS.md. -->
## Tunable variables

**The rule** (Cole, 2026-08-03): any constant that Cole or Nova might want to change without editing
code and restarting belongs in the tunables registry, not as a literal. If a number governs behavior —
rounds, depth, a threshold, a timeout, a feature switch — ask whether you would ever want to turn it
live to see what happens. If yes, register it. It costs three lines.

**How it works.** The registry is `REGISTRY` in `nova_body/nova_cortex/tunables.py` (default, type,
`min`/`max`, label, description, category); values persist in `nova_body/memory/tunables.json`.
`tunables.get(key)` re-reads the store (cached about two seconds), so a change applies on her **next
turn** without a restart. Inside `nova_voice/nova.py` use `_tune(key, fallback)`, which returns the
literal you would have hard-coded if the registry cannot load. The **Variables** panel (`/variables`,
backed by `GET/POST /api/variables`) renders itself from the registry: register a knob and it appears.

**Adding one:** register it in `REGISTRY`, then replace the literal with `tunables.get("key")` — or
`_tune("key", <old literal>)` in `nova.py`. Nothing else is needed.

**Non-negotiable:** a knob never crashes a turn — `get()` never raises, and a missing or corrupt store
or a bad value falls back to the registered default (an unregistered key returns `None`). Every number
is bounded: `set()` clamps to `min`/`max`. A migrated knob's default equals the literal it replaces, so
registering it changes nothing until someone turns it.

Audit evidence controls include `witness_receipt_chars` (default 2,400 per output),
`witness_total_receipt_chars` (24,000 shared across outputs) and `witness_max_images` (four across
attachments and tool frames). Truncated output and omitted images are explicitly disclosed;
they do not certify an unseen claim. `computer_launch_wait_seconds` defaults to ten seconds
for guest window verification. These defaults change the earlier narrow evidence slices and
three-second launch wait; no personal tunables store was rewritten.

**Context limits are currently source-defined, not live Variables controls.** The model client
passes its configured window/output reserve to `nova_cortex/context_budget.py`; the default window
is 65,536 tokens and output allowance is 16,384. A 4,096-token reserve and 3.4 characters/token
estimate determine the text budget, additionally capped at 174,000 characters. Ordinary message
text is capped at 24,000 characters; the merged system context is instead fitted to the total budget.
Images and exact tokenizer costs are not measured. Keep the client's window value aligned with the
inference launcher's context setting; changing a Variables entry cannot change these constants.
The saved resume block is at most 6,000 characters across three unfinished tasks. Checkpoint field
validation permits next_step text up to 1,000 characters, eight constraints up to 400 each, and eight
observations up to 600 each; the prompt may shorten them while preserving the complete saved record.

Currently registered, read from `REGISTRY`:

{{TUNABLES_TABLE}}
