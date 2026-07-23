# Workspace cleanup + pluck audit + dead-code review
_Last updated: 2026-07-23 15:44:22_
_2026-07-19, Fable. Cole: "a lot of clutter and mess caused by the last few weeks' work."
Done live while Nova was running, so nothing on her execution path was touched._

---

## 1. Trashed — `_admin/Trash/cleanup_2026-07-19/` (reversible, nothing deleted)

**609 MB of duplicated adapters** — `_admin/Training_stuff/v6/gguf_out/` held
`nova_core_v6_epoch1.gguf` and `_epoch2.gguf`, byte-for-byte copies of the ones already deployed in
`models/qwen3.6/`. Verified by exact size **plus** md5 of the first and last 4 MB of each before
moving — I was not going to trash a trained adapter on a size match. Originals in `models/` are
untouched. `_admin/Training_stuff/` went **610 MB → 1.5 MB**.

**10 spent one-off probes** (`_admin/`) — investigations that concluded weeks ago and are
referenced by nothing: `dry_ab_test`, `dry_fix_test`, `dry_parrot_test` (the DRY sampler A/Bs),
`banter_probe`, `convo_probe` (register tests), `probe_lastwrite`, `fire_restart`,
`test_spawn_verify`, `body_scan`, `Temp/probe_gate`.

**11 probe output files** — `dry_*_out.txt`, `dry_*_err.txt`, `convo_v5*.txt`, `banter_v6*.txt`,
`nw_restart_log.txt`.

**11 stale logs** (`_admin/Temp/`) — `painter.log`, `comfy.log`, `checkpoints.log`, the three
`nw_revive*` logs, `safe_reload.*`, `t_good.*`. Kept the live restart machinery
(`nova_restart.cmd` / `.log` / `_run.cmd` / `_spawn.json`, all written today).

**2 misplaced scratch files** — `nova_body/check_dedup.py` and `check_semantic_dedup.py`, ad-hoc
tests that landed in her package root instead of `memory/scratch/`.

Kept deliberately in `_admin/`: the standing gates (`hallucination_gate.py`, `referent_check.py`,
`mtp_ab_test.py`), live ops (`nova_guardian.py`, `nightwatch.py`, `overnight_review.py`,
`RunGuardian.cmd`, `nw_revive.cmd`), and setup helpers (`downloads.py`, `fetch_checkpoints.*`,
`setup_comfyui.cmd`, `ask_claude.ps1`).

---

## 2. Pluck test — **FAILING, and this is the real finding**

Ran it properly: imported her body with `general_tools` **removed from the path**.

    runtime imports:            OK
    runtime instantiates:       OK
    nova_cortex.executive       OK
    nova_cortex.tasking         OK
    nova_cortex.integrity       OK
    nova_senses.clock           OK
    nova_memory.journal         OK
    nova_lancedb.hippocampus    OK
    model client (her mouth):   *** UNREACHABLE — No module named 'nova_chat'
    tool_router (her hands):    *** UNREACHABLE — No module named 'nova_chat'

**Pluck the chat server and she can think, remember and perceive — but she cannot speak or act.**

The chain: `nova_body/nova_runtime/runtime.py:237` does `from nova_chat.clients import nova`,
and that module in turn does `from nova_chat.tool_router import execute_tool`. Two faculties live
in the face:

| File | What it actually is | Belongs in |
|---|---|---|
| `general_tools/nova_chat/clients/nova.py` | her **voice** — model call, the tool loop, `SYSTEM_PREFIX`, the integrity gate wiring | `nova_body/` |
| `general_tools/nova_chat/tool_router.py` | her **hands** — `run_command`, `read_file`, `write_file`, `list_dir`, the task-board tools, the timeout/silent-zero guards | `nova_body/` |

There is a comment in `runtime.py` claiming `nova_client` is "a leaf module (stdlib + httpx, no
chat-server deps), so importing it here doesn't drag the server in." **That is now false** — it
imports `nova_chat.tool_router`. The comment is stale and should go with the move.

Note the precedent: `nova_cortex/integrity.py` was moved body-ward on 07-14 for exactly this
reason, and its own docstring says so — *"anything that affects her problem-solving or her thinking
is a faculty, not a tool."* Her mouth and hands are the two biggest remaining cases.

**I did not move them.** That is a real refactor (imports, `sys.path`, the headless boot, the
KoELS equip path) and you were mid-test with her live. It wants a clean window and a pluck
verification after — `RUN_PLUCK.cmd` and `python -m nova_runtime` both still exist as the check.

---

## 3. Dead / redundant / doubled

**Two dead alternate launchers — a genuine doubled purpose.** The live path is
`NovaStart.cmd → nova_start.py → general_tools/NovaLauncher.py`. Neither of these is on it:

- `general_tools/nova_chat/server_runner.py` (19 lines) — plain uvicorn launcher, superseded.
- `general_tools/nova_chat/runtime_host.py` (45 lines) — the "runtime-primary boot" (Step 6d),
  where the body is the core and the chat UI attaches as a face.

**Recommendation: keep `runtime_host.py`, trash `server_runner.py`.** They do the same job, but
`runtime_host` is the architecture the pluck test is aiming at — it is the natural home for the
§2 fix. Deleting it would throw away the direction. Flagging rather than moving, since one is a
design artefact and that is your call.

**Dormant, not dead:** `nova_cortex/loadout.py` (99 lines) — the KoELS "which adapter set" decision
faculty. Nothing imports it because KoELS is gated on a gaming adapter that was never trained.
`nova_runtime/koels_equip.py` names it in comments as its intended partner. Leave it.

**`memory/scratch/` — 20 files, hers, left alone.** Her own experiment scripts
(`dead_audit.py` from t55, the dedup tests, retention checks). Per the standing rule I don't touch
her workspace; worth *asking her* to tidy it as a task, which also exercises the pacing fix.

**Detector note, worth carrying forward:** my first pass flagged `executive.py` (1002 lines,
unmistakably live) as dead, because my regex missed `from nova_cortex import executive` — the
`from <package> import <module>` form. That is the **exact** flaw in Nova's own t55 audit. Any
future dead-code sweep must match all five import shapes plus `importlib`, `python x.py`, `-m`,
and `subprocess`. Both of us made the same mistake; hers is documented in
`Nova_Created/dead_functions_audit.md`.

---

## Summary

| | Before | After |
|---|---|---|
| `_admin/Training_stuff/` | 610 MB | 1.5 MB |
| Loose files in `_admin/` | 30 | 14 |
| Reclaimed to Trash | — | 609 MB + 34 files |
| Pluck test | untested | **failing — mouth + hands in the face** |

Nothing was deleted. Nothing on her live execution path was modified. The two structural items
(§2 faculty move, §3 launcher consolidation) are staged decisions, not done work — both want a
window where she is not under test.
