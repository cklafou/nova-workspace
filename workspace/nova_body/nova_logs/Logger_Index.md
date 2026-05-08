# Logger_Index.md -- Nova Logging Registry
_Auto-updated by nova_nova_nova_nova_nova_tools/nova_logs/logger.py_
_Last updated: 2026-05-09 08:08:17_

## Log Types and Locations

| Log Type | File | Location | Updated By |
|----------|------|----------|------------|
| Agent Actions | `actions.jsonl` | `logs/sessions/YYYY-MM-DD/` | `nova_senses/eyes.py`, `nova_motor/hands.py` |
| Agent Errors | `errors.jsonl` | `logs/sessions/YYYY-MM-DD/` | All agent tools on exception |
| Vision Events | `vision.jsonl` | `logs/sessions/YYYY-MM-DD/` | `nova_senses/vision.py` |
| Mentor Calls | `mentor.jsonl` | `logs/sessions/YYYY-MM-DD/` | (nova_advisor deleted Phase 0 — kept for log compatibility) |
| Nova Chat Thoughts | `nova_thoughts.jsonl` | `logs/sessions/YYYY-MM-DD/` | `nova_chat/clients/nova.py` |
| Chat Transcripts | `YYYY-MM-DD_HH-MM-SS_chat.jsonl` | `logs/chat_sessions/` | `nova_chat/session_manager.py` |
| Session Index | `sessions_index.json` | `logs/chat_sessions/` | `nova_chat/session_manager.py` |
| Persistent Errors | `errors.jsonl` | `logs/` | `nova_logs/logger.py` fallback |

## Recent Session Logs

**2026-05-09:** `nova_thoughts.jsonl`
**2026-05-08:** `nova_thoughts.jsonl`
**2026-05-07:** `nova_thoughts.jsonl`
**2026-03-28:** `actions.jsonl`

## Recent Chat Sessions

- `logs/chat_sessions/2026-05-08_17-44-22_chat.jsonl`
