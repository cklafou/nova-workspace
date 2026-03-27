# Logger_Index.md -- Nova Logging Registry
_Auto-updated by tools/nova_logs/logger.py_
_Last updated: 2026-03-27 18:01:28_

## Log Types and Locations

| Log Type | File | Location | Updated By |
|----------|------|----------|------------|
| Agent Actions | `actions.jsonl` | `logs/sessions/YYYY-MM-DD/` | `nova_perception/eyes.py`, `nova_action/hands.py` |
| Agent Errors | `errors.jsonl` | `logs/sessions/YYYY-MM-DD/` | All agent tools on exception |
| Vision Events | `vision.jsonl` | `logs/sessions/YYYY-MM-DD/` | `nova_perception/vision.py` |
| Mentor Calls | `mentor.jsonl` | `logs/sessions/YYYY-MM-DD/` | `nova_advisor/mentor.py` |
| Nova Chat Thoughts | `nova_thoughts.jsonl` | `logs/sessions/YYYY-MM-DD/` | `nova_chat/clients/nova.py` |
| Chat Transcripts | `YYYY-MM-DD_HH-MM-SS_chat.jsonl` | `logs/chat_sessions/` | `nova_chat/session_manager.py` |
| Session Index | `sessions_index.json` | `logs/chat_sessions/` | `nova_chat/session_manager.py` |
| Persistent Errors | `errors.jsonl` | `logs/` | `nova_logs/logger.py` fallback |

## Recent Session Logs

**2026-03-26:** `actions.jsonl`, `nova_thoughts.jsonl`
**2026-03-25:** `actions.jsonl`
**2026-03-22:** `system.jsonl`
**2026-03-20:** `mentor.jsonl`, `stress_test.jsonl`
**2026-03-19:** `mentor.jsonl`

## Recent Chat Sessions

- `logs/chat_sessions/2026-03-21_16-46-47_chat.jsonl`
- `logs/chat_sessions/2026-03-21_19-26-26_chat.jsonl`
