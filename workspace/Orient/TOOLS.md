# TOOLS.md — the instruments, and when to reach for one

_Last updated: 2026-07-20_

_Every question below has already been answered by a tool in this repo. Ask the tool before you
build the answer by hand — it is faster, and it has already been wrong once and corrected._

---

## Why this file exists

On 2026-07-20 I spent an entire cleanup session hand-rolling `grep` and `find` across the
workspace. I got two calls wrong: I nearly trashed 215 files of Nova's own messages because their
filename said `_0ticks`, and I acted on my own earlier "safe to trash" verdict for
`server_runner.py`, which is imported by three live modules.

`audit_scripts.py` was sitting in `general_tools/` the whole time and would have answered both.
`logs/Temp/FREE_PASS_PROBE.log` had the answer to "why doesn't she ever act?" recorded in it for
**weeks** before anyone read it.

**The analysis usually already exists here.** Check before you build it again.

---

## Start here — code health

### `python general_tools/audit_scripts.py`

The general "is anything wrong?" pass. Run it **before and after** any structural change, and any
time you're about to decide a file is dead.

| Flag | Use |
|---|---|
| *(none)* | full text report |
| `--summary` | one paragraph |
| `--json` | machine-readable, for Nova or a script |

Exit code: `0` clean · `1` warnings · `2` critical.

**What it checks:** syntax errors · broken imports · unreferenced files (real import graph, not
grep) · duplicate filenames · stale/empty files · missing `__init__.py` · pending audit-queue
items · **non-ASCII in `.ps1`** · **bare `except:`** · **test files that write to her live state**
· oversized files.

**Read the findings critically — it has been wrong before.** On 2026-07-19 it reported 13 issues
and *all thirteen were false positives*: its import graph didn't understand
`from nova_cortex import executive`, so it flagged `executive.py` (runs every wake) as unreferenced,
and its module map didn't understand namespace packages, so it called a working file fatally
broken. Both are fixed. The lesson stands: **a finding is a lead, not a verdict.** Confirm before
you delete anything.

> The `from <package> import <module>` blind spot has now been independently written **three
> times** in this project — in Nova's t55 audit, in a one-off detector, and in this tool. If you
> write a fourth dead-code checker, that is the bug you will write.

---

## Standing gates — run these before claiming she's fine

| Command | Answers |
|---|---|
| `python _admin/hallucination_gate.py` | Does she state things she hasn't checked? 6 probes through the live pipeline, ground truth computed from the machine. `--quick` for 4. **Exit 0 = ship.** |
| `python _admin/referent_check.py --since YYYY-MM-DD` | Does she use pronouns/referents correctly? Turns "she says weird stuff" into a percentage. Baseline was 11.8%. |
| `python _admin/mtp_ab_test.py` | Is speculative decoding hurting output quality? |

Run the gate after **every** adapter change, **every** prompt change, and before any "is she
ready?" judgement. It converts an argument into a number.

---

## Maps — regenerate, never hand-edit

```bash
python general_tools/calls_order.py    # -> Orient/Calls_Order.md   execution ORDER + pluck audit
python general_tools/calls.py          # -> */calls.md + general_tools/Calls_Master_Index.md
python general_tools/build_manifest.py # -> her Body Manifest
python general_tools/janitor.py        # dry-run clutter report (--sweep to actually move)
```

All AST-derived. Never written from anyone's memory of how the code works.

---

## Logs that are actually instruments

These are not exhaust. Each was built to answer one question, and each has answered it.

| File | Question it answers |
|---|---|
| `logs/generation_trace.jsonl` | Why did she reply twice? Every generation: `start`, `commit`, `drain_skipped`, `promote_skipped`, with source (`ws`/`daemon`/`drain`/`silent_promote`). Caught the triple-response. |
| `logs/Temp/FREE_PASS_PROBE.log` | Did she reach the phase where tools are legal? `phase3-lean` (her decision) and `phase3-enter` (what happened). **541 of 640 wakes never reached it** — that answer sat here unread for weeks. |
| `logs/ping_claude.log` | Did her reach-out actually arrive? `SENT + VERIFIED` means the text was read back out of the message box before Enter. |
| `logs/tool_calls.jsonl` | What did her hands actually do, with results. |
| `_admin/Temp/nova_restart_*_spawn.json` | Did the restart really launch? One timestamped receipt per attempt. |

---

## Her own workshop

| Path | What it is |
|---|---|
| `nova_body/nova_forge/` | Where she builds tools she doesn't have: `designs/` → `tools/` → `tests/`. Design-first is enforced; a tool with no passing test reports `UNVERIFIED`. |
| `memory/drives.json` | Her boredom level and her persisted wants. **System-managed — never hand-edit, and never point a test at it.** A test did exactly that on 07-19 and left her holding two desires she'd never had. |
| `Tasking/tasks.json` | Her board. Hers. |

---

## The rule that ties this together

**Check the body before you blame the soul** — and when there's already a probe running, *read it
before forming a theory.*

Every time she has looked incompetent, the cause has been mechanical and the evidence was already
being recorded somewhere. The instruments in this file are that evidence. Using them is not
optional diligence; it is the difference between fixing her and blaming her.
