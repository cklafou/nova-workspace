# GEMINI_INDEX.md -- Nova Workspace Session Manifest
_Last updated: 2026-05-28 02:39:05_

## INITIALIZATION PROTOCOL
Run these steps at the start of every session in order:

```
Step 1: @Google Drive: Search for the folder 'Nova_Workspace'
Step 2: @Google Drive: Search for 'workspace/general_tools/nova_sync/GEMINI_INDEX.md'
Step 3: Use the Search Key column below for all subsequent file lookups.
```

**Rule: Never guess a path. Only search using the exact string in the Search Key column.**

## START HERE EVERY SESSION

| File | Search Key | Description |
|------|-----------|-------------|
| STATUS.md | `workspace/memory/STATUS.md` | Current project state -- READ FIRST |
| JOURNAL.md | `workspace/memory/JOURNAL.md` | Nova's session log -- READ SECOND |
| COLE.md | `workspace/memory/COLE.md` | Who Cole is and Nova's notes |
| NOVA.md | `workspace/NOVA.md` | Nova's identity and values |
| 00_START_HERE.md | `workspace/SELF/core/00_START_HERE.md` | Entry into Nova's self-model |

## Root Files

| Filename | Search Key | Description |
|----------|-----------|-------------|
| nova_start.py | `workspace/nova_start.py` | PY file |
| nova_status.json | `workspace/nova_status.json` | JSON file |
| NovaStart.cmd | `workspace/NovaStart.cmd` | CMD file |
| README.md | `workspace/README.md` | Project overview |
| start_llama.cmd | `workspace/start_llama.cmd` | CMD file |
| StopNova.cmd | `workspace/StopNova.cmd` | CMD file |

## memory/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| archive_2026-02.md | `workspace/memory/archive/archive_2026-02.md` | MD file |
| autonomy_state.json | `workspace/memory/autonomy_state.json` | Nova's persisted wake/sleep + focus + reflection state |
| prompt_kit.md | `workspace/memory/avatar/prompt_kit.md` | MD file |
| COLE.md | `workspace/memory/COLE.md` | Who Cole is and Nova's notes about him |
| cole_intent.json | `workspace/memory/cole_intent.json` | Latest standing directive from Cole (chat -> autonomy) |
| Design_Principles.md | `workspace/memory/Design_Principles.md` | Living best-practices Nova learns from (suggestions, not hard rules) |
| interrupt_inbox.json | `workspace/memory/interrupt_inbox.json` | JSON file |
| JOURNAL.md | `workspace/memory/JOURNAL.md` | Nova's running session log -- READ SECOND |
| Nova_Architecture_Review.md | `workspace/memory/Nova_Architecture_Review.md` | MD file |
| Nova_Avatar_Design_Bible.md | `workspace/memory/Nova_Avatar_Design_Bible.md` | MD file |
| avatar_consistency_protocol.md | `workspace/memory/reports/avatar_consistency_protocol.md` | MD file |
| AVATAR_MORNING_RUNBOOK.md | `workspace/memory/reports/AVATAR_MORNING_RUNBOOK.md` | MD file |
| avatar_pipeline_tools.md | `workspace/memory/reports/avatar_pipeline_tools.md` | MD file |
| code_md_review_2026-05-27.md | `workspace/memory/reports/code_md_review_2026-05-27.md` | MD file |
| comfyui_setup_checklist.md | `workspace/memory/reports/comfyui_setup_checklist.md` | MD file |
| full_review_progress.md | `workspace/memory/reports/full_review_progress.md` | MD file |
| identity_brief.md | `workspace/memory/reports/identity_brief.md` | MD file |
| nova_lora_training_plan.md | `workspace/memory/reports/nova_lora_training_plan.md` | MD file |
| PASSOVER_2026-05-27_opus.md | `workspace/memory/reports/PASSOVER_2026-05-27_opus.md` | MD file |
| self_note.md | `workspace/memory/reports/self_note.md` | MD file |
| UI_OVERHAUL_2026-05-27.md | `workspace/memory/reports/UI_OVERHAUL_2026-05-27.md` | MD file |
| who_i_am.md | `workspace/memory/reports/who_i_am.md` | MD file |
| work_summary.md | `workspace/memory/reports/work_summary.md` | MD file |
| work_vs_body.md | `workspace/memory/reports/work_vs_body.md` | MD file |
| STATUS.md | `workspace/memory/STATUS.md` | Current project state and mission -- READ FIRST |
| touch_state.json | `workspace/memory/touch_state.json` | Touch sense snapshot -- what is interacting with Nova right now |
| ui_layout.json | `workspace/memory/ui_layout.json` | JSON file |

## SELF/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| 00_START_HERE.md | `workspace/SELF/core/00_START_HERE.md` | Auto-generated entry point into Nova's self-model |
| 01_identity.md | `workspace/SELF/core/01_identity.md` | Who Nova is -- core identity |
| 02_how_i_work.md | `workspace/SELF/core/02_how_i_work.md` | Operating rules, Priority 0, yield protocol, autonomy flow |
| 03_body_manifest.md | `workspace/SELF/core/03_body_manifest.md` | Nova's body architecture (senses, cortex, motor) |
| 04_tools_and_voice.md | `workspace/SELF/core/04_tools_and_voice.md` | MD file |
| heartbeat.md | `workspace/SELF/reference/heartbeat.md` | MD file |
| manifest.json | `workspace/SELF/reference/manifest.json` | Generated body manifest -- parts, refs, drift flags |
| ncl_master.md | `workspace/SELF/reference/ncl_master.md` | MD file |
| upgrade_protocol.md | `workspace/SELF/reference/upgrade_protocol.md` | MD file |

## nova_body/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| __init__.py | `workspace/nova_body/nova_config/__init__.py` | PY file |
| __init__.py | `workspace/nova_body/nova_cortex/__init__.py` | PY file |
| calls.md | `workspace/nova_body/nova_cortex/calls.md` | MD file |
| checkin.py | `workspace/nova_body/nova_cortex/checkin.py` | PY file |
| context_builder.py | `workspace/nova_body/nova_cortex/context_builder.py` | PY file |
| executive.py | `workspace/nova_body/nova_cortex/executive.py` | Two-phase wake: reflect -> decide -> execute; board actions |
| nova_status.py | `workspace/nova_body/nova_cortex/nova_status.py` | PY file |
| prefrontal_cortex.py | `workspace/nova_body/nova_cortex/prefrontal_cortex.py` | PY file |
| rules.py | `workspace/nova_body/nova_cortex/rules.py` | PY file |
| tasking.py | `workspace/nova_body/nova_cortex/tasking.py` | Id-keyed task board (status + progress log) |
| __init__.py | `workspace/nova_body/nova_imagination/__init__.py` | PY file |
| imagination.py | `workspace/nova_body/nova_imagination/imagination.py` | PY file |
| __init__.py | `workspace/nova_body/nova_logs/__init__.py` | PY file |
| calls.md | `workspace/nova_body/nova_logs/calls.md` | MD file |
| logger.py | `workspace/nova_body/nova_logs/logger.py` | PY file |
| Logger_Index.md | `workspace/nova_body/nova_logs/Logger_Index.md` | MD file |
| __init__.py | `workspace/nova_body/nova_memory/__init__.py` | PY file |
| calls.md | `workspace/nova_body/nova_memory/calls.md` | MD file |
| goals.py | `workspace/nova_body/nova_memory/goals.py` | PY file |
| journal.py | `workspace/nova_body/nova_memory/journal.py` | PY file |
| log_reader.py | `workspace/nova_body/nova_memory/log_reader.py` | PY file |
| session_store.py | `workspace/nova_body/nova_memory/session_store.py` | PY file |
| state.py | `workspace/nova_body/nova_memory/state.py` | PY file |
| __init__.py | `workspace/nova_body/nova_motor/__init__.py` | PY file |
| calls.md | `workspace/nova_body/nova_motor/calls.md` | MD file |
| hands.py | `workspace/nova_body/nova_motor/hands.py` | PY file |
| motor_cortex.py | `workspace/nova_body/nova_motor/motor_cortex.py` | PY file |
| tool_executor.py | `workspace/nova_body/nova_motor/tool_executor.py` | PY file |
| verify.py | `workspace/nova_body/nova_motor/verify.py` | PY file |
| __init__.py | `workspace/nova_body/nova_senses/__init__.py` | PY file |
| calls.md | `workspace/nova_body/nova_senses/calls.md` | MD file |
| clock.py | `workspace/nova_body/nova_senses/clock.py` | Time-sense: stamps, since-human, scheduling helpers |
| environment.py | `workspace/nova_body/nova_senses/environment.py` | Senses Cole's directive/typing + workspace change fingerprint |
| eyes.py | `workspace/nova_body/nova_senses/eyes.py` | PY file |
| proprioception.py | `workspace/nova_body/nova_senses/proprioception.py` | PY file |
| touch.py | `workspace/nova_body/nova_senses/touch.py` | Touch sense -- what is interacting with Nova (viewers, agents) |
| vision.py | `workspace/nova_body/nova_senses/vision.py` | PY file |

## general_tools/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| audit_queue.py | `workspace/general_tools/audit_queue.py` | PY file |
| audit_scripts.py | `workspace/general_tools/audit_scripts.py` | PY file |
| build_manifest.py | `workspace/general_tools/build_manifest.py` | Regenerates SELF/ body manifest from the live tree |
| calls.py | `workspace/general_tools/calls.py` | PY file |
| Calls_Master_Index.md | `workspace/general_tools/Calls_Master_Index.md` | MD file |
| download_models.py | `workspace/general_tools/download_models.py` | PY file |
| injector.py | `workspace/general_tools/injector.py` | PY file |
| calls.md | `workspace/general_tools/nova_chat/calls.md` | MD file |
| check_keys.py | `workspace/general_tools/nova_chat/check_keys.py` | PY file |
| claude.py | `workspace/general_tools/nova_chat/clients/claude.py` | PY file |
| gemini.py | `workspace/general_tools/nova_chat/clients/gemini.py` | PY file |
| nova.py | `workspace/general_tools/nova_chat/clients/nova.py` | PY file |
| context_export.py | `workspace/general_tools/nova_chat/context_export.py` | PY file |
| launch.py | `workspace/general_tools/nova_chat/launch.py` | PY file |
| nova_bridge.py | `workspace/general_tools/nova_chat/nova_bridge.py` | PY file |
| nova_lang.py | `workspace/general_tools/nova_chat/nova_lang.py` | PY file |
| orchestrator.py | `workspace/general_tools/nova_chat/orchestrator.py` | PY file |
| server.py | `workspace/general_tools/nova_chat/server.py` | Nova Chat FastAPI/WebSocket server + autonomy daemon |
| server_runner.py | `workspace/general_tools/nova_chat/server_runner.py` | PY file |
| session_manager.py | `workspace/general_tools/nova_chat/session_manager.py` | PY file |
| index.html | `workspace/general_tools/nova_chat/static/index.html` | HTML file |
| nova_dock_prototype.html | `workspace/general_tools/nova_chat/static/nova_dock_prototype.html` | HTML file |
| tool_router.py | `workspace/general_tools/nova_chat/tool_router.py` | Safe tool dispatch for Nova (read/write/list/run + task board) |
| transcript.py | `workspace/general_tools/nova_chat/transcript.py` | Chat transcript -> model messages builder |
| workspace_context.py | `workspace/general_tools/nova_chat/workspace_context.py` | Builds Nova's on-demand context block |
| __init__.py | `workspace/general_tools/nova_sync/__init__.py` | PY file |
| backup.py | `workspace/general_tools/nova_sync/backup.py` | Session snapshots on boot, weekly full backups |
| calls.md | `workspace/general_tools/nova_sync/calls.md` | MD file |
| dir_patch.py | `workspace/general_tools/nova_sync/dir_patch.py` | Import-path auditor -- scans .py/.md for stale references |
| drive.py | `workspace/general_tools/nova_sync/drive.py` | Google Drive diff-based mirror for Gemini (this system) |
| FILE_INDEX.md | `workspace/general_tools/nova_sync/FILE_INDEX.md` | MD file |
| FILE_INDEX_LINK.md | `workspace/general_tools/nova_sync/FILE_INDEX_LINK.md` | MD file |
| watcher.py | `workspace/general_tools/nova_sync/watcher.py` | GitHub push + Drive sync + backup. Modes: --push, --pup, --full |
| NovaLauncher.py | `workspace/general_tools/NovaLauncher.py` | PY file |
| restructure.py | `workspace/general_tools/restructure.py` | PY file |

## Tasking/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| tasks.json | `workspace/Tasking/tasks.json` | JSON file |

## PATCHES/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| README.md | `workspace/PATCHES/README.md` | Project overview |

## _admin/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| AUTONOMY_FACULTY_SPEC_2026-05-24.md | `workspace/_admin/_archive_2026-05-24/AUTONOMY_FACULTY_SPEC_2026-05-24.md` | MD file |
| AUTONOMY_INTEGRATION_REVIEW_2026-05-24.md | `workspace/_admin/_archive_2026-05-24/AUTONOMY_INTEGRATION_REVIEW_2026-05-24.md` | MD file |
| BODY_MANIFEST_PLAN_2026-05-24.md | `workspace/_admin/_archive_2026-05-24/BODY_MANIFEST_PLAN_2026-05-24.md` | MD file |
| BODY_RELOCATION_PLAN_2026-05-24.md | `workspace/_admin/_archive_2026-05-24/BODY_RELOCATION_PLAN_2026-05-24.md` | MD file |
| AGENTS.md | `workspace/_admin/_archive_2026-05-24/BOOTUP/AGENTS.md` | Operating rules and agent behavior definitions |
| BOOTSTRAP.md | `workspace/_admin/_archive_2026-05-24/BOOTUP/BOOTSTRAP.md` | MD file |
| HEARTBEAT.md | `workspace/_admin/_archive_2026-05-24/BOOTUP/HEARTBEAT.md` | MD file |
| NCL_MASTER.md | `workspace/_admin/_archive_2026-05-24/BOOTUP/NCL_MASTER.md` | MD file |
| NOVA.md | `workspace/_admin/_archive_2026-05-24/BOOTUP/NOVA.md` | Nova's identity, soul, personality, and values |
| TOOLS.md | `workspace/_admin/_archive_2026-05-24/BOOTUP/TOOLS.md` | Tool reference and exec patterns |
| UPGRADE_PROTOCOL.md | `workspace/_admin/_archive_2026-05-24/BOOTUP/UPGRADE_PROTOCOL.md` | MD file |
| drive.py | `workspace/_admin/_archive_2026-05-24/drive.py` | Google Drive diff-based mirror for Gemini (this system) |
| gateway_config.py | `workspace/_admin/_archive_2026-05-24/gateway_config.py` | PY file |
| nova_gateway - tokenless.json | `workspace/_admin/_archive_2026-05-24/nova_gateway - tokenless.json` | JSON file |
| nova_gateway.json | `workspace/_admin/_archive_2026-05-24/nova_gateway.json` | JSON file |
| ORIENT.md | `workspace/_admin/_archive_2026-05-24/ORIENT.md` | MD file |
| orient.py | `workspace/_admin/_archive_2026-05-24/orient.py` | PY file |
| nova_identity_draft.md | `workspace/_admin/_archive_2026-05-24/pre_test_wipe_2026-05-26/nova_identity_draft.md` | MD file |
| tasks.json | `workspace/_admin/_archive_2026-05-24/pre_test_wipe_2026-05-26/tasks.json` | JSON file |
| priority.md | `workspace/_admin/_archive_2026-05-24/priority.md` | MD file |
| retire_dead_server_fns.py | `workspace/_admin/_archive_2026-05-24/retire_dead_server_fns.py` | PY file |
| HANDOFF.md | `workspace/_admin/passover/23 MAY 2026/HANDOFF.md` | MD file |
| PHASE2_ARCHITECTURE.md | `workspace/_admin/passover/26 MAR 2026/PHASE2_ARCHITECTURE.md` | MD file |
| COWORK_SESSION_LOG.md | `workspace/_admin/passover/27 MAR 2026/COWORK_SESSION_LOG.md` | MD file |
| NOVA_PROJECT_PLAN.md | `workspace/_admin/passover/28 MAR 2026/NOVA_PROJECT_PLAN.md` | MD file |
| PHASE4A_THOUGHTS_SYSTEM.md | `workspace/_admin/passover/28 MAR 2026/PHASE4A_THOUGHTS_SYSTEM.md` | MD file |
| llama_help.txt | `workspace/_admin/passover/29 MAR 2026/llama_help.txt` | TXT file |
| passover_2026-03-10.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-10.md` | MD file |
| passover_2026-03-15.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-15.md` | MD file |
| passover_2026-03-19.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-19.md` | MD file |
| passover_2026-03-20.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-20.md` | MD file |
| passover_2026-03-20_gemini.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-20_gemini.md` | MD file |
| passover_2026-03-21_claude.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-21_claude.md` | MD file |
| passover_2026-03-21_gemini.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-21_gemini.md` | MD file |
| passover_2026-03-21_gemini_session2.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-21_gemini_session2.md` | MD file |
| passover_2026-03-26_claude.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-26_claude.md` | MD file |
| passover_2026-03-28_claude.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-28_claude.md` | MD file |
| session_notes_2026-03-22.md | `workspace/_admin/passover/3 MAR 2026/session_notes_2026-03-22.md` | MD file |
| HANDOFF.md | `workspace/_admin/passover/6 MAY 2026/HANDOFF.md` | MD file |
| README.md | `workspace/_admin/README.md` | Project overview |

## nova_art/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| README.md | `workspace/nova_art/README.md` | Project overview |

## nova_lancedb/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| __init__.py | `workspace/nova_lancedb/__init__.py` | PY file |
| embedder.py | `workspace/nova_lancedb/embedder.py` | PY file |
| hippocampus.py | `workspace/nova_lancedb/hippocampus.py` | PY file |
| indexer.py | `workspace/nova_lancedb/indexer.py` | PY file |

---
_This manifest is auto-generated on every Drive sync by nova_sync/drive.py._
_Do not edit manually -- changes will be overwritten._