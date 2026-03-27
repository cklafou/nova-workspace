# GEMINI_INDEX.md -- Nova Workspace Session Manifest
_Last updated: 2026-03-27 19:56:54_

## INITIALIZATION PROTOCOL
Run these three steps at the start of every session in order:

```
Step 1: @Google Drive: Search for the folder 'Nova_Workspace'
Step 2: @Google Drive: Search for 'workspace/tools/nova_sync/GEMINI_INDEX.md'
Step 3: Refer to the Search Key column below for all subsequent file lookups.
```

**Rule: Never guess a path. Only search using the exact string in the Search Key column.**

## START HERE EVERY SESSION

| File | Search Key | Description |
|------|-----------|-------------|
| STATUS.md | `workspace/memory/STATUS.md` | Current project state -- READ FIRST |
| JOURNAL.md | `workspace/memory/JOURNAL.md` | Nova's session log -- READ SECOND |
| COLE.md | `workspace/memory/COLE.md` | Who Cole is and Nova's notes |
| TOOLS.md | `workspace/TOOLS.md` | Tool reference and exec patterns |
| BOOTSTRAP.md | `workspace/BOOTSTRAP.md` | Session startup sequence |

## Root Files

| Filename | Search Key | Description |
|----------|-----------|-------------|
| AGENTS.md | `workspace/AGENTS.md` | Nova's operating rules and agent behavior definitions |
| BOOTSTRAP.md | `workspace/BOOTSTRAP.md` | Boot sequence Nova follows on every OpenClaw start |
| HEARTBEAT.md | `workspace/HEARTBEAT.md` | Current heartbeat state |
| IDENTITY.md | `workspace/IDENTITY.md` | Nova's self-definition document |
| nova_gateway - Copy.json | `workspace/nova_gateway - Copy.json` | JSON file |
| nova_gateway.json | `workspace/nova_gateway.json` | JSON file |
| nova_gateway_runner.py | `workspace/nova_gateway_runner.py` | PY file |
| README.md | `workspace/README.md` | Project overview |
| SOUL.md | `workspace/SOUL.md` | Nova's identity, values, and growth framework |
| TOOLS.md | `workspace/TOOLS.md` | How to use all tools, method reference, exec patterns |
| USER.md | `workspace/USER.md` | Who Cole is -- personality, background, preferences |

## memory/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| .drive_sync_cache.json | `workspace/memory/.drive_sync_cache.json` | JSON file |
| archive_2026-02.md | `workspace/memory/archive/archive_2026-02.md` | MD file |
| COLE.md | `workspace/memory/COLE.md` | Cole's notes and Nova's observations about Cole |
| JOURNAL.md | `workspace/memory/JOURNAL.md` | Nova's running session log -- READ SECOND |
| STATUS.md | `workspace/memory/STATUS.md` | Current project state and mission -- READ FIRST |

## tools/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| build_nova.py | `workspace/tools/build_nova.py` | PY file |
| calls.py | `workspace/tools/calls.py` | PY file |
| Calls_Master_Index.md | `workspace/tools/Calls_Master_Index.md` | MD file |
| __init__.py | `workspace/tools/nova_action/__init__.py` | PY file |
| autonomy.py | `workspace/tools/nova_action/autonomy.py` | FIND->COMMIT->VERIFY action loop with interrupt polling |
| calls.md | `workspace/tools/nova_action/calls.md` | MD file |
| hands.py | `workspace/tools/nova_action/hands.py` | Mouse/keyboard control via pyautogui + pynput |
| verify.py | `workspace/tools/nova_action/verify.py` | Action verification helpers |
| __init__.py | `workspace/tools/nova_advisor/__init__.py` | PY file |
| calls.md | `workspace/tools/nova_advisor/calls.md` | MD file |
| mentor.py | `workspace/tools/nova_advisor/mentor.py` | Claude Sonnet + Haiku advisor -- GROWTH MODE, gatekeeper |
| calls.md | `workspace/tools/nova_chat/calls.md` | MD file |
| check_keys.py | `workspace/tools/nova_chat/check_keys.py` | PY file |
| claude.py | `workspace/tools/nova_chat/clients/claude.py` | PY file |
| gemini.py | `workspace/tools/nova_chat/clients/gemini.py` | PY file |
| nova.py | `workspace/tools/nova_chat/clients/nova.py` | PY file |
| context_export.py | `workspace/tools/nova_chat/context_export.py` | PY file |
| launch.py | `workspace/tools/nova_chat/launch.py` | PY file |
| nova_bridge.py | `workspace/tools/nova_chat/nova_bridge.py` | PY file |
| orchestrator.py | `workspace/tools/nova_chat/orchestrator.py` | PY file |
| server.py | `workspace/tools/nova_chat/server.py` | PY file |
| server_runner.py | `workspace/tools/nova_chat/server_runner.py` | PY file |
| session_manager.py | `workspace/tools/nova_chat/session_manager.py` | PY file |
| transcript.py | `workspace/tools/nova_chat/transcript.py` | PY file |
| workspace_context.py | `workspace/tools/nova_chat/workspace_context.py` | PY file |
| __init__.py | `workspace/tools/nova_core/__init__.py` | PY file |
| brain.py | `workspace/tools/nova_core/brain.py` | Companion-first cognitive router |
| calls.md | `workspace/tools/nova_core/calls.md` | MD file |
| checkin.py | `workspace/tools/nova_core/checkin.py` | Inter-turn message listener and session init |
| nova_status.py | `workspace/tools/nova_core/nova_status.py` | PY file |
| rules.py | `workspace/tools/nova_core/rules.py` | Immutable operating directives and yield protocol |
| __init__.py | `workspace/tools/nova_gateway/__init__.py` | PY file |
| agent_loop.py | `workspace/tools/nova_gateway/agent_loop.py` | PY file |
| config.py | `workspace/tools/nova_gateway/config.py` | PY file |
| context_builder.py | `workspace/tools/nova_gateway/context_builder.py` | PY file |
| discord_client.py | `workspace/tools/nova_gateway/discord_client.py` | PY file |
| gateway.py | `workspace/tools/nova_gateway/gateway.py` | PY file |
| scheduler.py | `workspace/tools/nova_gateway/scheduler.py` | PY file |
| session_store.py | `workspace/tools/nova_gateway/session_store.py` | PY file |
| tool_executor.py | `workspace/tools/nova_gateway/tool_executor.py` | PY file |
| __init__.py | `workspace/tools/nova_logs/__init__.py` | PY file |
| calls.md | `workspace/tools/nova_logs/calls.md` | MD file |
| logger.py | `workspace/tools/nova_logs/logger.py` | Dated log folder manager |
| Logger_Index.md | `workspace/tools/nova_logs/Logger_Index.md` | MD file |
| __init__.py | `workspace/tools/nova_memory/__init__.py` | PY file |
| calls.md | `workspace/tools/nova_memory/calls.md` | MD file |
| journal.py | `workspace/tools/nova_memory/journal.py` | Append-only JOURNAL.md writer with sanitize() |
| log_reader.py | `workspace/tools/nova_memory/log_reader.py` | Reads session logs -- summarize_today(), get_failures() |
| state.py | `workspace/tools/nova_memory/state.py` | Pre-condition state checking before any action |
| status.py | `workspace/tools/nova_memory/status.py` | STATUS.md proposed-changes updater |
| __init__.py | `workspace/tools/nova_perception/__init__.py` | PY file |
| calls.md | `workspace/tools/nova_perception/calls.md` | MD file |
| explorer.py | `workspace/tools/nova_perception/explorer.py` | pywinauto accessibility API wrapper -- exact UI coordinates |
| eyes.py | `workspace/tools/nova_perception/eyes.py` | Unified vision -- pywinauto first, Claude Haiku fallback |
| vision.py | `workspace/tools/nova_perception/vision.py` | Claude Haiku screen verification and description |
| .drive_sync_cache.json | `workspace/tools/nova_sync/.drive_sync_cache.json` | JSON file |
| __init__.py | `workspace/tools/nova_sync/__init__.py` | PY file |
| backup.py | `workspace/tools/nova_sync/backup.py` | Session snapshots on boot, weekly full backups on Sundays |
| calls.md | `workspace/tools/nova_sync/calls.md` | MD file |
| dir_patch.py | `workspace/tools/nova_sync/dir_patch.py` | Import path auditor -- scans .py and .md for stale references |
| drive.py | `workspace/tools/nova_sync/drive.py` | Google Drive diff-based sync (this system) |
| FILE_INDEX.md | `workspace/tools/nova_sync/FILE_INDEX.md` | Full workspace file listing with GitHub URLs (for Claude) |
| FILE_INDEX_LINK.md | `workspace/tools/nova_sync/FILE_INDEX_LINK.md` | Claude's bootstrap URL pointer |
| watcher.py | `workspace/tools/nova_sync/watcher.py` | GitHub sync + Drive sync + backup. Modes: --push, --pup, --full |
| NovaLauncher.py | `workspace/tools/NovaLauncher.py` | PY file |

## logs/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| 2026-03-21_16-46-47_chat.jsonl | `workspace/logs/chat_sessions/2026-03-21_16-46-47_chat.jsonl` | JSONL file |
| 2026-03-21_19-26-26_chat.jsonl | `workspace/logs/chat_sessions/2026-03-21_19-26-26_chat.jsonl` | JSONL file |
| 2026-03-21_19-26-26_context_claude.md | `workspace/logs/chat_sessions/exports/2026-03-21_19-26-26_context_claude.md` | MD file |
| 2026-03-21_19-26-26_context_gemini.md | `workspace/logs/chat_sessions/exports/2026-03-21_19-26-26_context_gemini.md` | MD file |
| sessions_index.json | `workspace/logs/chat_sessions/sessions_index.json` | JSON file |
| nova_advisor_refactor.py | `workspace/logs/proposed/nova_advisor_refactor.py` | PY file |
| mentor.jsonl | `workspace/logs/sessions/2026-03-19/mentor.jsonl` | JSONL file |
| mentor.jsonl | `workspace/logs/sessions/2026-03-20/mentor.jsonl` | JSONL file |
| stress_test.jsonl | `workspace/logs/sessions/2026-03-20/stress_test.jsonl` | JSONL file |
| system.jsonl | `workspace/logs/sessions/2026-03-22/system.jsonl` | JSONL file |
| actions.jsonl | `workspace/logs/sessions/2026-03-25/actions.jsonl` | JSONL file |
| actions.jsonl | `workspace/logs/sessions/2026-03-26/actions.jsonl` | JSONL file |
| nova_thoughts.jsonl | `workspace/logs/sessions/2026-03-26/nova_thoughts.jsonl` | JSONL file |

## _admin/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| COWORK_SESSION_LOG.md | `workspace/_admin/COWORK_SESSION_LOG.md` | MD file |
| migrate_to_project_nova.py | `workspace/_admin/migrate_to_project_nova.py` | PY file |
| NOVA_PROJECT_PLAN.md | `workspace/_admin/NOVA_PROJECT_PLAN.md` | MD file |
| passover_2026-03-10.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-10.md` | MD file |
| passover_2026-03-15.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-15.md` | MD file |
| passover_2026-03-19.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-19.md` | MD file |
| passover_2026-03-20.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-20.md` | MD file |
| passover_2026-03-20_gemini.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-20_gemini.md` | MD file |
| passover_2026-03-21_claude.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-21_claude.md` | MD file |
| passover_2026-03-21_gemini.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-21_gemini.md` | MD file |
| passover_2026-03-21_gemini_session2.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-21_gemini_session2.md` | MD file |
| passover_2026-03-26_claude.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-26_claude.md` | MD file |
| session_notes_2026-03-22.md | `workspace/_admin/passover/3 MAR 2026/session_notes_2026-03-22.md` | MD file |
| PHASE2_ARCHITECTURE.md | `workspace/_admin/PHASE2_ARCHITECTURE.md` | MD file |

## sessions/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| 27319801-a1e2-4172-9754-550105bfac1f.jsonl | `workspace/sessions/2026-03-27/27319801-a1e2-4172-9754-550105bfac1f.jsonl` | JSONL file |

---
_This manifest is auto-generated on every Drive sync by nova_sync/drive.py._
_Do not edit manually -- changes will be overwritten._