# _archive_2026-06-20 — workspace spring cleaning
_Moved here by Cowork Opus, 2026-06-20. Nothing was deleted — every item is reversible. Each file
sits at the same relative path it came from, so restoring is just moving it back._

## What's in here (198 files, ~2.0 MB) — all verified UNREFERENCED by live code
- **logs/autonomy_runs/** (129) — old per-tick autonomy logs (May–Jun 1). Superseded by `logs/events/`.
- **logs/gateway_sessions/** (45) + **logs/gateway/** (1) — deprecated "gateway" logs (last touched May 9).
- **logs/events/** (8) — old **May** daily event logs (June + today's were kept live).
- **logs/autonomy/** (1), **logs/self_notes/** (1) — old one-offs.
- **logs/ root one-offs** (7) — `llama_before/after/after2/cycle.txt`, `pluck_2026-06-10.log`,
  `pycheck.txt`, `systems_check_t4.md` (one-shot diagnostic outputs).
- **memory/reports/** (4) — `PASSOVER_2026-05-27` & `2026-05-29` (superseded by the 06-04 passover),
  `_continue_test.md`, `executive_continue_fix_PROPOSED_2026-05-31.md` (that fix was applied).
- **_admin/** (2) — duplicate `nova_core_lora_dataset_spec.md` + `nova_lora_dataset_batch1.md`
  (the canonical copies remain in `_admin/Training_stuff/`).

## To restore anything
Move it back to its original path (this tree mirrors the workspace), e.g. in PowerShell:
```
move _archive_2026-06-20\memory\reports\PASSOVER_2026-05-29_opus.md memory\reports\
```
Once you're confident you don't need any of it, delete this whole folder.

## What was deliberately NOT touched (and why)
**Live code was left alone.** Nova's body manifest flags some modules as "no inbound ref"
(`nova_motor`, `audit_queue`, `audit_scripts`, `calls`, `download_models`, `injector`,
`restructure`) — but that's her *body-part graph*, not the import graph. They ARE imported by
running code: `restructure` → goals/motor_cortex/proprioception/hippocampus; `injector` →
server + prefrontal_cortex; `audit_*` → the live `watcher`; `server` → `nova_motor`. Archiving any
of them would break her next boot, so they stayed. Her active memory/state files, current docs,
the model, and the binaries were untouched.

## Candidates left in place for YOU to judge (not auto-archived — they're in her live memory area)
A few `memory/reports/` docs look stale but sit in a directory her cognition reads/writes, so I
left them: `WIP_Inventory_2026-05-31.md`, `runtime_extraction_inventory_2026-06-01.md`,
`full_review_progress.md`, `code_md_review_2026-05-27.md`, `work_summary.md`, `work_vs_body.md`,
`UI_OVERHAUL_2026-05-27.md`. Say the word and I'll archive any you confirm are done with.
