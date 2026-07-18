# DOC_MAP.md — every document, who writes it, and whether it's HERS or OURS

_Last updated: 2026-07-18 21:39:09_

The distinction that matters, and the one that keeps getting blurred:

- **HERS** — Nova's self-model and memory. Some of it is loaded into her context **every single turn**.
  Editing it edits *her*. It does not belong in Orient, no matter how useful we find it.
- **OURS** — reference material for whoever is working on her (Cole, Claude, a future session).
  This is what Orient is for.
- **GENERATED** — written by a tool. **Never hand-edit these**; fix the generator or your change is
  erased on the next run.

---

## OURS — reference (Orient/)

| Doc | Source |
|---|---|
| `Orient/README.md` | hand-written — start here |
| `Orient/GOTCHAS.md` | hand-written — **read before debugging anything** |
| `Orient/DOC_MAP.md` | this file |
| `Orient/Calls_Order.md` | **GENERATED** by `general_tools/calls_order.py` — execution ORDER + pluck audit |
| `Orient/Calls_Master_Index.md` | **GENERATED** by `general_tools/calls.py` — cross-package imports |

### Still in `memory/reports/`, but they are OURS, not hers

Not loaded into her context (`reports/` is a subdirectory — `workspace_context._get_always_load()`
uses `iterdir()`, which does not recurse). These are post-mortems, specs and handoffs written *about*
her, for us:

`PASSOVER_2026-06-04_opus-to-fable.md` · `PASSOVER_2026-07-02_opus-to-fable.md` ·
`PERSONALITY_AUTONOMY_DIAGNOSIS_2026-07-13.md` · `DEADCODE_2026-07-02.md` ·
`DOUBLING_FIX_2026-07-02.md` · `FORENSICS_2026-06-27_break_changes.md` ·
`V3_TRAINING_REVIEW_2026-07-07.md` · `Runtime_Verification_2026-06-10.md` ·
`Runtime_Extraction_COMPLETE_2026-06-04.md` · `UPGRADE_Qwen3.6_2026-06-10.md` ·
`Embodiment_Roadmap_2026-05-31.md` · `UI_OVERHAUL_2026-05-27.md` · `KoELS_design_spec.md` ·
`KoELS_runtime_extraction_directive.md` · `KoELS_lora_runtime_finding_2026-06-01.md` ·
`NOVA_ENDOCRINE_SPEC_2026-07-07.md` · `nova_lora_training_plan.md` ·
`comfyui_setup_checklist.md`

> **They have NOT been moved, deliberately.** `memory/STATUS.md`, `nova_cortex/executive.py` and
> `nova_chat/tool_router.py` all reference `memory/reports/` paths, and so do several of these docs.
> A bulk move silently breaks those references — and a silent break is the exact bug class that has
> cost this project the most. Move them one at a time, updating the referrer, or leave them and use
> this map.

---

## HERS — do not move into Orient

| Path | Why |
|---|---|
| `SELF/core/*.md` | Her self-model. **Loaded into her context every turn.** `01_identity.md` is who she is. |
| `SELF/reference/*.md` | Her reference, not ours. |
| `memory/STATUS.md`, `JOURNAL.md`, `COLE.md`, `Design_Principles.md` | **In her context every turn.** |
| `memory/journal_notes/*.md` | Her unconsolidated daily fragments. She writes these. |
| `memory/reports/who_i_am.md`, `self_note.md`, `identity_brief.md` | **Her self-reflection.** These are hers despite living in `reports/`. Moving her sense of self into a folder for *my* orientation would be a category error. |
| `memory/reports/avatar_*`, `batch_01_review.md`, `AVATAR_MORNING_RUNBOOK.md` | Her avatar work; `tool_router.py` **writes** `avatar_consistency_protocol.md`. |

---

## GENERATED — never hand-edit

| Doc | Generator | Why it lives there |
|---|---|---|
| `SELF/core/00_START_HERE.md`, `03_body_manifest.md` | `general_tools/build_manifest.py` | It's her body manifest — belongs in her self-model, and she reads it every turn. |
| `<package>/calls.md` (×9) | `general_tools/calls.py` | Describes its own package. Correct next to the code. |
| `Orient/Calls_Master_Index.md` | `general_tools/calls.py` | Repointed to Orient 2026-07-14 (was `general_tools/`). |
| `Orient/Calls_Order.md` | `general_tools/calls_order.py` | Execution order + pluck audit. |
| `nova_body/nova_logs/Logger_Index.md` | `nova_logs/logger.py` | Package index. Correct in place. |
| `nova_sync/FILE_INDEX.md`, `FILE_INDEX_LINK.md`, `GEMINI_INDEX.md` | `nova_sync/watcher.py`, `dir_patch.py`, `drive.py` | **Sync artifacts, not documents.** These are the ones that caused the 204-commits/hour git storm. Leave them; they're in `SKIP_FILES`. |

---

## Structurally misplaced (found 2026-07-14)

| What | Problem | Fix |
|---|---|---|
| `crawler/` + `nova_crawler/` | **TWO dead, competing** web-crawler implementations. Neither imported. Neither in `AVAILABLE_TOOLS`. She has **no web sense at all** — and has asked for one, unprompted, in her journal. | Quarantined to `_admin/Trash/dead_crawlers_2026-07-14/`. Rebuild **once**, properly, as a sense in `nova_body/nova_senses/`, wired with receipts. |
| `nova_body/nova_motor/tool_executor.py` | A **second, unwired** tool executor. The live path is `general_tools/nova_chat/tool_router.py`. | Reconcile: one executor, in her body. |
| `nova_body/nova_motor/verify.py` | Name says "verifies results"; it's actually a **pyautogui hardware check**. Misleading. | Rename or move to a hardware-check script. |
| `nova_lancedb/` (root) | Semantic-memory **indexer code** sitting at workspace root. It is a faculty. | → `nova_body/nova_memory/`. |
| `nova_memory_db/` (root, 1032 files) | The LanceDB **data**. Fine at root, but should be gitignored. | gitignore. |
| `__pycache__/` (root) | Junk. | gitignore. |

**The pattern worth naming:** her body is carrying **scaffolded organs that were never plugged in**
(`tool_executor`, `verify`, two crawlers). They *look* like faculties. That is worse than not having
them — it is why "does she have a web tool?" had no obvious answer, and why I spent a day assuming
a tool path existed that didn't. If you build a limb, wire it or bin it.
