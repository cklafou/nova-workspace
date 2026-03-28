# GEMINI_INDEX.md -- Nova Workspace Session Manifest
_Last updated: 2026-03-28 21:30:30_

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
| NCL_MASTER.md | `workspace/NCL_MASTER.md` | MD file |
| nova_gateway - Copy.json | `workspace/nova_gateway - Copy.json` | JSON file |
| nova_gateway.json | `workspace/nova_gateway.json` | JSON file |
| nova_gateway_runner.py | `workspace/nova_gateway_runner.py` | PY file |
| nova_status.json | `workspace/nova_status.json` | JSON file |
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
| session_start.json | `workspace/memory/session_start.json` | Current session start timestamp |
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
| calls.md | `workspace/tools/nova_chat/calls.md` | MD file |
| check_keys.py | `workspace/tools/nova_chat/check_keys.py` | PY file |
| claude.py | `workspace/tools/nova_chat/clients/claude.py` | PY file |
| gemini.py | `workspace/tools/nova_chat/clients/gemini.py` | PY file |
| nova.py | `workspace/tools/nova_chat/clients/nova.py` | PY file |
| context_export.py | `workspace/tools/nova_chat/context_export.py` | PY file |
| launch.py | `workspace/tools/nova_chat/launch.py` | PY file |
| nova_bridge.py | `workspace/tools/nova_chat/nova_bridge.py` | PY file |
| nova_lang.py | `workspace/tools/nova_chat/nova_lang.py` | PY file |
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
| injector.py | `workspace/tools/nova_gateway/injector.py` | PY file |
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
| actions.jsonl | `workspace/logs/sessions/2026-03-28/actions.jsonl` | JSONL file |

## Thoughts/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| master.md | `workspace/Thoughts/Finished/completed_success/TEST_BRAIN_PROBE/master.md` | MD file |
| priority.md | `workspace/Thoughts/priority.md` | MD file |
| master.md | `workspace/Thoughts/TEST_ADVANCE/master.md` | MD file |
| master.md | `workspace/Thoughts/TEST_BLOCKED/master.md` | MD file |
| master.md | `workspace/Thoughts/TEST_BRIEF/master.md` | MD file |
| master.md | `workspace/Thoughts/TEST_STATUS/master.md` | MD file |
| master.md | `workspace/Thoughts/TEST_STATUS2/master.md` | MD file |
| master.md | `workspace/Thoughts/TEST_STATUS3/master.md` | MD file |
| master.md | `workspace/Thoughts/TEST_STATUS4/master.md` | MD file |
| THOUGHT_TEMPLATE.md | `workspace/Thoughts/THOUGHT_TEMPLATE.md` | MD file |

## _admin/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| COWORK_SESSION_LOG.md | `workspace/_admin/COWORK_SESSION_LOG.md` | MD file |
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
| passover_2026-03-28_claude.md | `workspace/_admin/passover/3 MAR 2026/passover_2026-03-28_claude.md` | MD file |
| session_notes_2026-03-22.md | `workspace/_admin/passover/3 MAR 2026/session_notes_2026-03-22.md` | MD file |
| PHASE2_ARCHITECTURE.md | `workspace/_admin/PHASE2_ARCHITECTURE.md` | MD file |
| PHASE4A_THOUGHTS_SYSTEM.md | `workspace/_admin/PHASE4A_THOUGHTS_SYSTEM.md` | MD file |

## gateway_sessions/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| 02d07c6a-74d6-4770-b3d6-9781b9f96fdf.jsonl | `workspace/gateway_sessions/2026-03-27/02d07c6a-74d6-4770-b3d6-9781b9f96fdf.jsonl` | JSONL file |
| 079fa80b-1373-4420-8a41-8821ff32fbd1.jsonl | `workspace/gateway_sessions/2026-03-27/079fa80b-1373-4420-8a41-8821ff32fbd1.jsonl` | JSONL file |
| 0b8fb077-a8a9-47f1-8f3c-5143369965e2.jsonl | `workspace/gateway_sessions/2026-03-27/0b8fb077-a8a9-47f1-8f3c-5143369965e2.jsonl` | JSONL file |
| 0fa1628f-9924-480e-9a9a-c26432d1d046.jsonl | `workspace/gateway_sessions/2026-03-27/0fa1628f-9924-480e-9a9a-c26432d1d046.jsonl` | JSONL file |
| 1b9f2cc3-e830-4d70-8f89-2c6266e86900.jsonl | `workspace/gateway_sessions/2026-03-27/1b9f2cc3-e830-4d70-8f89-2c6266e86900.jsonl` | JSONL file |
| 27319801-a1e2-4172-9754-550105bfac1f.jsonl | `workspace/gateway_sessions/2026-03-27/27319801-a1e2-4172-9754-550105bfac1f.jsonl` | JSONL file |
| 35e1ff1a-9d5d-4f96-bc07-d84d4b373a2e.jsonl | `workspace/gateway_sessions/2026-03-27/35e1ff1a-9d5d-4f96-bc07-d84d4b373a2e.jsonl` | JSONL file |
| 3b551c2b-d723-4ad6-af8f-1510e6163c39.jsonl | `workspace/gateway_sessions/2026-03-27/3b551c2b-d723-4ad6-af8f-1510e6163c39.jsonl` | JSONL file |
| 3d80261a-09c1-445b-99ed-6217d4182a29.jsonl | `workspace/gateway_sessions/2026-03-27/3d80261a-09c1-445b-99ed-6217d4182a29.jsonl` | JSONL file |
| 3f8b8065-aa69-4b58-bbe6-0f32bcee904d.jsonl | `workspace/gateway_sessions/2026-03-27/3f8b8065-aa69-4b58-bbe6-0f32bcee904d.jsonl` | JSONL file |
| 511acb81-be1c-46e5-b944-f43f5ed10326.jsonl | `workspace/gateway_sessions/2026-03-27/511acb81-be1c-46e5-b944-f43f5ed10326.jsonl` | JSONL file |
| 51a47e67-d810-4437-bae8-331c37ac4b6e.jsonl | `workspace/gateway_sessions/2026-03-27/51a47e67-d810-4437-bae8-331c37ac4b6e.jsonl` | JSONL file |
| 760c1499-ef6d-4359-a2a1-dbb93b3ce791.jsonl | `workspace/gateway_sessions/2026-03-27/760c1499-ef6d-4359-a2a1-dbb93b3ce791.jsonl` | JSONL file |
| 766459d9-6b1f-465c-8c5f-30162c1b1180.jsonl | `workspace/gateway_sessions/2026-03-27/766459d9-6b1f-465c-8c5f-30162c1b1180.jsonl` | JSONL file |
| 77cfc249-4ac4-49e7-ae33-07c560e20238.jsonl | `workspace/gateway_sessions/2026-03-27/77cfc249-4ac4-49e7-ae33-07c560e20238.jsonl` | JSONL file |
| 7d5763ab-3fa0-4d41-a801-5294466b715b.jsonl | `workspace/gateway_sessions/2026-03-27/7d5763ab-3fa0-4d41-a801-5294466b715b.jsonl` | JSONL file |
| 8ac53147-290f-4289-8691-c6dffc1f7332.jsonl | `workspace/gateway_sessions/2026-03-27/8ac53147-290f-4289-8691-c6dffc1f7332.jsonl` | JSONL file |
| 8de5ced2-2f3e-4a40-b5df-4e7f6baba9d1.jsonl | `workspace/gateway_sessions/2026-03-27/8de5ced2-2f3e-4a40-b5df-4e7f6baba9d1.jsonl` | JSONL file |
| 8e0728e5-114a-4395-8748-18ecbf3dae60.jsonl | `workspace/gateway_sessions/2026-03-27/8e0728e5-114a-4395-8748-18ecbf3dae60.jsonl` | JSONL file |
| 964c18f7-f4f8-480e-8e88-2ae20db4c3c7.jsonl | `workspace/gateway_sessions/2026-03-27/964c18f7-f4f8-480e-8e88-2ae20db4c3c7.jsonl` | JSONL file |
| 969797f0-6bb5-40a6-b65a-a99149ed845b.jsonl | `workspace/gateway_sessions/2026-03-27/969797f0-6bb5-40a6-b65a-a99149ed845b.jsonl` | JSONL file |
| 973a412f-2ca8-47fd-ae5a-de989aca1597.jsonl | `workspace/gateway_sessions/2026-03-27/973a412f-2ca8-47fd-ae5a-de989aca1597.jsonl` | JSONL file |
| a2011c76-33cd-4d06-ad7c-1fdb9ca31ce1.jsonl | `workspace/gateway_sessions/2026-03-27/a2011c76-33cd-4d06-ad7c-1fdb9ca31ce1.jsonl` | JSONL file |
| a31b9f75-c7b6-4a63-90e9-dae332d4d8e0.jsonl | `workspace/gateway_sessions/2026-03-27/a31b9f75-c7b6-4a63-90e9-dae332d4d8e0.jsonl` | JSONL file |
| a40697cd-9b45-4de1-a76f-51a40ea93350.jsonl | `workspace/gateway_sessions/2026-03-27/a40697cd-9b45-4de1-a76f-51a40ea93350.jsonl` | JSONL file |
| aa54f72f-3a5d-4fa8-ad72-1513524c9998.jsonl | `workspace/gateway_sessions/2026-03-27/aa54f72f-3a5d-4fa8-ad72-1513524c9998.jsonl` | JSONL file |
| b16952d7-8bd0-4f91-b344-7e58bbbee0cc.jsonl | `workspace/gateway_sessions/2026-03-27/b16952d7-8bd0-4f91-b344-7e58bbbee0cc.jsonl` | JSONL file |
| c00735ad-898f-4b12-b9ab-68af9507359a.jsonl | `workspace/gateway_sessions/2026-03-27/c00735ad-898f-4b12-b9ab-68af9507359a.jsonl` | JSONL file |
| cc7bb92c-f1ae-4f35-a0fa-c1fc7f11cd33.jsonl | `workspace/gateway_sessions/2026-03-27/cc7bb92c-f1ae-4f35-a0fa-c1fc7f11cd33.jsonl` | JSONL file |
| cf81604a-a60b-403d-afbc-a527835543b0.jsonl | `workspace/gateway_sessions/2026-03-27/cf81604a-a60b-403d-afbc-a527835543b0.jsonl` | JSONL file |
| d6c4c5f3-bf02-4ad7-89e6-374e1150c7e9.jsonl | `workspace/gateway_sessions/2026-03-27/d6c4c5f3-bf02-4ad7-89e6-374e1150c7e9.jsonl` | JSONL file |
| d94aa61b-bb63-4b2f-b23b-92fc59dbc402.jsonl | `workspace/gateway_sessions/2026-03-27/d94aa61b-bb63-4b2f-b23b-92fc59dbc402.jsonl` | JSONL file |
| da53e6b7-349a-4077-a5fe-1aaee42f31f8.jsonl | `workspace/gateway_sessions/2026-03-27/da53e6b7-349a-4077-a5fe-1aaee42f31f8.jsonl` | JSONL file |
| f2e9d1cd-8cc1-42d7-b1c3-3e509a3fbce4.jsonl | `workspace/gateway_sessions/2026-03-27/f2e9d1cd-8cc1-42d7-b1c3-3e509a3fbce4.jsonl` | JSONL file |
| f322f2ea-56b6-49b3-9558-79ac707b71e6.jsonl | `workspace/gateway_sessions/2026-03-27/f322f2ea-56b6-49b3-9558-79ac707b71e6.jsonl` | JSONL file |
| f7db2331-9d95-4166-a91a-9ca37af49e4e.jsonl | `workspace/gateway_sessions/2026-03-27/f7db2331-9d95-4166-a91a-9ca37af49e4e.jsonl` | JSONL file |
| fa901728-8225-427e-9067-690def091ff5.jsonl | `workspace/gateway_sessions/2026-03-27/fa901728-8225-427e-9067-690def091ff5.jsonl` | JSONL file |
| fc9bbb20-f6cd-4ee0-b7e5-61c4ff188ad7.jsonl | `workspace/gateway_sessions/2026-03-27/fc9bbb20-f6cd-4ee0-b7e5-61c4ff188ad7.jsonl` | JSONL file |
| 11f97245-a7a7-432d-884b-0b5b85463e6d.jsonl | `workspace/gateway_sessions/2026-03-28/11f97245-a7a7-432d-884b-0b5b85463e6d.jsonl` | JSONL file |
| 29fa2fc5-a92a-4ed9-b1e8-324e9c85049a.jsonl | `workspace/gateway_sessions/2026-03-28/29fa2fc5-a92a-4ed9-b1e8-324e9c85049a.jsonl` | JSONL file |
| 3e78ac77-c6ef-43aa-abc9-bb76a192752e.jsonl | `workspace/gateway_sessions/2026-03-28/3e78ac77-c6ef-43aa-abc9-bb76a192752e.jsonl` | JSONL file |
| 3f53a9c1-4f27-49da-8780-885cdee728c4.jsonl | `workspace/gateway_sessions/2026-03-28/3f53a9c1-4f27-49da-8780-885cdee728c4.jsonl` | JSONL file |
| 7073c404-bacf-4c1d-8036-e75c3f91685f.jsonl | `workspace/gateway_sessions/2026-03-28/7073c404-bacf-4c1d-8036-e75c3f91685f.jsonl` | JSONL file |
| a10d5c0c-07fe-4eb0-8281-122ade8e45fa.jsonl | `workspace/gateway_sessions/2026-03-28/a10d5c0c-07fe-4eb0-8281-122ade8e45fa.jsonl` | JSONL file |
| ea3a1e77-c19d-44c6-ba13-f82bd66c3e28.jsonl | `workspace/gateway_sessions/2026-03-28/ea3a1e77-c19d-44c6-ba13-f82bd66c3e28.jsonl` | JSONL file |

## sessions/

| Filename | Search Key | Description |
|----------|-----------|-------------|
| 7bb1e244-8dd8-44a2-ad55-6aaeb8f094d3.jsonl | `workspace/sessions/2026-03-28/7bb1e244-8dd8-44a2-ad55-6aaeb8f094d3.jsonl` | JSONL file |

---
_This manifest is auto-generated on every Drive sync by nova_sync/drive.py._
_Do not edit manually -- changes will be overwritten._