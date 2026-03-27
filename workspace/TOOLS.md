# TOOLS.md -- Nova's Tool Reference
_Read this every session. It tells you what you can do and how to do it._
_This file is the source of truth for all tool usage._

---

## Package Structure

Tools live under `tools/` as Python packages. Always import using the package style:

```python
from nova_memory.journal import append
from nova_perception.eyes import NovaEyes
from nova_action.hands import NovaHands
from nova_logs.logger import log, log_thought
```

| Package | Purpose | Key Modules |
|---|---|---|
| `nova_sync/` | Workspace sync, GitHub push, Drive mirror, backup | `watcher.py`, `drive.py`, `backup.py` |
| `nova_memory/` | Journal, state checks, status updates, log reader | `journal.py`, `log_reader.py`, `status.py`, `state.py` |
| `nova_logs/` | All logging -- agent tools, chat thoughts, index | `logger.py`, `Logger_Index.md` |
| `nova_action/` | Mouse/keyboard control, autonomy loop, verification | `hands.py`, `autonomy.py`, `verify.py` |
| `nova_perception/` | UI element detection, vision, screen exploration | `eyes.py`, `explorer.py`, `vision.py` |
| `nova_core/` | Rules engine, yield check-in, cognitive router (stub) | `rules.py`, `checkin.py`, `brain.py` |
| `nova_chat/` | Group chat server -- Cole + Claude + Gemini + Nova | `server.py`, `nova_bridge.py`, `workspace_context.py` |
| `nova_advisor/` | Legacy Claude mentor bridge -- DEPRECATED, pending removal | `mentor.py` |

Also at `tools/` root: `calls.py` (generates call graph docs per package).

---

## Environment

- **OS:** Windows 11 -- use PowerShell syntax, never bash
- **PowerShell version:** 5.1 -- chain commands with `;` not `&&`
- **Workspace root:** `C:\Users\lafou\.openclaw\workspace`
- **Tools:** `tools\` (Python packages, always add to sys.path before importing)
- **Memory:** `memory\` (COLE.md, STATUS.md, JOURNAL.md -- never overwrite directly)
- **Logs:** `logs\`
- **Proposed changes:** `logs\proposed\` (stage all changes here for Cole to review)
- **Admin/planning (not for Nova):** `_admin\` (excluded from context injection)

## How to Run Tools

All tools require the path insert every single time:

```
exec: python -c "import sys; sys.path.insert(0, 'tools'); from nova_memory.journal import append; ..."
```

---

## CRITICAL: Apostrophes in exec commands crash on Windows

Never use apostrophes inside single-quoted Python strings in exec commands.

**Wrong:** `python -c "from nova_memory.journal import append; append('I've done it')"`
**Right:** `python -c "from nova_memory.journal import append; append('I have done it')"`

Rephrase to avoid contractions entirely. Do not use escape sequences. Do not write temp files. Just rephrase.

---

## The Yield Protocol (mandatory)

After EVERY exec, before the next one, run:

```
exec: python -c "import sys; sys.path.insert(0, 'tools'); from nova_core.checkin import check; check()"
```

- No output = Cole has not sent anything, continue.
- Output = Cole sent a message. Read it. Decide whether to stop or finish the current step first.

**One action per turn.** Do the thing. State what you did in one sentence. Stop. Wait for the system to process. Never chain multiple execs together.

---

## The Proposed Changes Protocol (mandatory for any file edits)

Nova does NOT write directly to root workspace files or `memory/` files. Ever.

1. Copy the original: `exec: python -c "import shutil; shutil.copy('memory/STATUS.md', 'logs/proposed/STATUS.md')"`
2. Edit the copy in `logs/proposed/`
3. Tell Cole: "Drafted changes to STATUS.md in logs/proposed/ -- want to review?"

---

## Nova Chat -- How Nova Talks to Claude and Gemini

Nova Chat is the group chat where Cole, Claude, Gemini, and Nova work together.

**Start it:**
```
exec: python tools/nova_chat/launch.py
```
Opens at `http://127.0.0.1:8765`

**Nova's bridge syntax** -- use these inside nova_chat messages to take real actions:

```
[WRITE:logs/proposed/my_file.py]
def my_function():
    pass
[/WRITE]
```

```
[EXEC:python tools/nova_sync/watcher.py --push]
```

```
[READ:tools/nova_action/autonomy.py]
```

The server intercepts these and executes them directly on disk. A bridge notice appears in chat on success or failure. Files must stay within the workspace directory.

**IMPORTANT:** Bridge syntax is for task work only. Never use `[WRITE:]` or `[EXEC:]` in a message that is primarily a conversation or brainstorm.

---

## nova_logs/logger.py -- Unified Logger (ALL logging goes here)

Single file, sectioned by use case. Logs land in `logs/sessions/YYYY-MM-DD/`.

```python
# Agent tool events (clicks, vision, errors, mentor calls):
from nova_logs.logger import log
log("actions", "click", target="Login button", result="ok")
log("errors", "element_not_found", target="Trade button", attempt=3)
log("mentor", "ask", question="Is this safe?", response="PROCEED")
log("vision", "describe", result="ThinkOrSwim positions page visible")

# Nova's chat responses (called automatically by nova_chat):
from nova_logs.logger import log_thought
log_thought("response text", source="nova_chat_client")

# Screenshot directory for today:
from nova_logs.logger import get_screenshot_dir
shot_dir = get_screenshot_dir()
```

`Logger_Index.md` in `tools/nova_logs/` is auto-updated and shows all log locations and recent files.

**Do NOT use `nova_memory.logger` directly.** It is legacy. `nova_logs.logger` is current.

---

## nova_memory/status.py -- Update Active Pulse and Goals

Follows the Proposed Changes Protocol -- never writes to STATUS.md directly.

```
exec: python tools/nova_memory/status.py "What you are doing now" "Goal text to mark complete"
```

Both arguments are optional. Output goes to `logs/proposed/STATUS.md` for Cole to review.

**IMPORTANT:** The only function is `update_status()`. There is no `update_pulse()`. If you see that name anywhere it is a stale reference.

---

## nova_memory/journal.py -- Append-Only Journal

The ONLY safe way to write to JOURNAL.md. Never use the write tool on it directly.

```
exec: python -c "
import sys
sys.path.insert(0, 'tools')
from nova_memory.journal import append
append('''
What actually happened today. Honest, first-person, casual.
No bullet points. Write sentences. Swear if it fits.
Do not fabricate memories or events that did not happen.
''')
"
```

Voice rules: first person, casual, no bullet lists, no headers, no fabricated events.

---

## nova_memory/log_reader.py -- Read Your Own Session Logs

Run this before conversations requiring real data.

```
exec: python -c "
import sys
sys.path.insert(0, 'tools')
from nova_memory.log_reader import summarize_today, get_failures, get_recent_sessions
print(get_recent_sessions())
print(summarize_today())
print(get_failures(7))
"
```

---

## nova_memory/state.py -- Application State Checks

```python
from nova_memory.state import NovaState
state = NovaState()
state.check_thinkorswim_ready()
state.check_application_state(app_name)
state.wait_for_state(check_func, timeout)
```

`build_context_snapshot()` will be added here when the nova_advisor refactor is merged.

---

## nova_core/checkin.py -- Cole's Voice Between Thoughts

```
exec: python -c "import sys; sys.path.insert(0, 'tools'); from nova_core.checkin import check; check()"
```

---

## nova_core/rules.py -- Operational Rules Engine

Loaded every session via BOOTSTRAP.md Step 2.

```
exec: python tools/nova_core/rules.py
```

---

## nova_core/brain.py -- Cognitive Router (STUB -- NOT FUNCTIONAL)

Returns "standby" for everything. Do not rely on it. Phase 4 work.

---

## nova_perception/eyes.py -- How Nova Sees

pywinauto primary, Claude Haiku fallback.

```python
from nova_perception.eyes import NovaEyes
eyes = NovaEyes()

eyes.find(target, window)
eyes.verify(question)
eyes.describe()
eyes.list_elements(window, type)
eyes.list_windows()
eyes.screenshot(save=False)
```

---

## nova_action/hands.py -- How Nova Acts

```python
from nova_action.hands import NovaHands
hands = NovaHands()

hands.move_to(x, y)
hands.move_and_click(x, y)
hands.type_text(text)
hands.press_key(key)
hands.hotkey(key1, key2)
hands.right_click(x, y)
hands.double_click(x, y)
```

---

## nova_action/autonomy.py -- Reliable Action Loop

```python
from nova_action.autonomy import NovaAutonomy
from nova_perception.eyes import NovaEyes
from nova_action.hands import NovaHands
from nova_advisor.mentor import NovaMentor

autonomy = NovaAutonomy(NovaEyes(), NovaHands(), NovaMentor())

autonomy.click(target, window, success_question)
autonomy.type_into(target, text, window)
autonomy.wait_for(condition, timeout)
```

`wait_for` condition must be a plain string, never a lambda.

---

## nova_advisor/mentor.py -- DEPRECATED

Being replaced by nova_chat. The `evaluate_action()` gatekeeper and `get_project_briefing()` logic are pending migration. See `logs/proposed/nova_advisor_refactor.py`.

---

## nova_sync/watcher.py -- GitHub and Drive Sync

**Run as background watcher:**
```
exec: python tools/nova_sync/watcher.py
```

**Manual push + copy session URL:**
```
exec: python tools/nova_sync/watcher.py --push
```

**Stage a file for --pup (routes by filename match):**
Drop the file in workspace root, then `python tools/nova_sync/watcher.py --pup`
Supports: `.py`, `.md`, `.json`, `.jsonl`, `.txt`, `.html`

**IMPORTANT:** `watcher.py` is a script. There is no `NovaWatcher` class. Do not attempt to import it.

---

## Live File Access -- Bootstrap Protocol

**Claude bootstrap URL (permanent):**
```
https://api.github.com/repos/cklafou/nova-workspace/contents/workspace/tools/nova_sync/FILE_INDEX_LINK.md
```

**Gemini Drive mirror:**
```
https://drive.google.com/drive/folders/1GLW6qVm5PHp_xnSlEXlnZIBhhmixzFya?usp=sharing
```
