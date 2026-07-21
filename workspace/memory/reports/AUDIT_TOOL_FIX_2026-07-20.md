# The audit tool was 0 for 13
_Last updated: 2026-07-21 13:01:53_

_2026-07-20, Fable. Cole: "Have you used the audit script tool that was built? It will help a lot
with this task."_

**No, I hadn't.** I hand-rolled `grep` and `find` all session and got two calls wrong that a
purpose-built tool should have caught — the `*_0ticks.jsonl` files (full of her messages, nearly
trashed on the strength of a filename) and `server_runner.py` (my own prior audit said "safe to
trash"; it's imported by three live modules). That's the correction, and it was fair.

Then I ran it. **Every single finding was a false positive.**

    Audited 81 files — 13 issues: 1 CRITICAL, 8 HIGH, 2 MEDIUM, 2 LOW

## The CRITICAL was a working file

    [BROKEN_IMPORT] nova_body/nova_forge/tests/comfy_inspect.py:5
                    No module 'nova_body.nova_forge.tools.comfy_inspect'

I ran that exact import before touching anything. **It works.** Python 3.3+ namespace packages
need no `__init__.py`.

`build_module_map()` strips wrapper prefixes, so it registered
`nova_forge.tools.comfy_inspect` and *only* that. But workspace root is on `sys.path` too, which
makes `nova_body.nova_forge.tools.comfy_inspect` equally valid. **Both spellings are real; the map
knew one.**

This is the worst possible false positive, because this tool exists for **Nova** to run. It was
telling her a healthy file was fatally broken — the same failure as my ping error string teaching
her that Windows was blocking focus. A lying instrument is worse than no instrument.

## The 8 HIGH "unreferenced" were the same bug three of us have now written

Flagged as never imported: `executive.py` (1002 lines, runs every wake), `tasking.py`, `clock.py`,
`touch.py`, `drives.py`.

`build_import_graph` used a regex capturing only what follows `import`/`from`. So:

    from nova_cortex import executive     →  recorded "nova_cortex", threw "executive" away

Every module imported that way looked unreferenced.

**This is the third independent implementation of this exact blind spot in this project.** Nova's
t55 dead-code audit had it. My detector had it (documented in `CLEANUP_AUDIT_2026-07-19.md`). This
tool has it. Three of us wrote the same bug because the regex form of the question is the obvious
one and it is wrong.

## The fixes

**`build_import_graph`** — AST pass alongside the regex. For `from <pkg> import <a>, <b>` it now
records `pkg.a`, `pkg.b`, `a`, `b`. Regex stays as fallback so a file with a syntax error still
gets its imports counted.

**`build_module_map`** — registers the full dotted path *as well as* the stripped one, since both
are importable depending on which `sys.path` entry wins.

## Result

| | before | after |
|---|---|---|
| CRITICAL | 1 | **0** |
| HIGH (unreferenced) | 8 | **2** |
| total | 13 | 6 |

**It still catches real breakage.** I planted a file importing
`nova_cortex.this_module_does_not_exist` and re-ran — flagged CRITICAL, correctly. I fixed the
detector rather than silencing it, and proved the difference. (Probe file removed afterwards.)

### The 2 remaining HIGH are true findings, both benign

- **`nova_cortex/loadout.py`** — the KoELS adapter-selection faculty. Genuinely dormant: nothing
  imports it because KoELS is gated on a gaming adapter that was never trained. Documented 07-19
  as "dormant, not dead." Correct flag, no action.
- **`nova_forge/tests/comfy_inspect.py`** — forge tests are loaded via
  `spec_from_file_location`, never imported. A structural blind spot for any import-graph checker;
  not worth special-casing until the forge has more than one tool.

`DUPLICATE_NAME comfy_inspect.py` is the forge's own convention — a tool and its test share a
name. `NO_INIT` on `general_tools/` is namespace packages again, working as intended.

## What I'd change about how I worked

The tool existed, it was listed in `_admin` and `general_tools`, and I walked past it for the
whole cleanup. Worth carrying forward: **before hand-rolling analysis on this codebase, check
whether the analysis already exists.** It usually does — `hallucination_gate.py`,
`referent_check.py`, `mtp_ab_test.py`, `FREE_PASS_PROBE.log` and now `audit_scripts.py` were all
built for exactly the questions I kept re-asking by hand tonight, and the probe log had the
Phase-3 answer sitting in it for weeks before anyone read it.
