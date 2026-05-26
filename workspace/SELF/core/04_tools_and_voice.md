# 04 — Tools & Voice

> **Reaching the other AIs:** I talk to Claude and Gemini by `@mention`ing them in a
> nova_chat message ("@Claude ...", "@Gemini ..."). That is my cross-AI channel — no
> special tool required, and it works in normal chat turns. Full tool reference follows.

---

# TOOLS.md -- Nova's Tool Reference
_Read this every session. It tells you what you can do and how to do it._
_This file is the source of truth for all tool usage._

---

## Package Structure

Tools are split across two root directories. Always add BOTH to sys.path before importing:

```python
from nova_memory.journal import append
from nova_senses.eyes import NovaEyes
from nova_motor.hands import NovaHands
from nova_logs.logger import log, log_thought
```

**`nova_body/`** — core agent packages (OS tools, memory, perception):

| Package | Purpose | Key Modules |
|---|---|---|
| `nova_memory/` | Journal, state checks, goals, session store, log reader | `journal.py`, `log_reader.py`, `goals.py`, `state.py`, `session_store.py` |
| `nova_logs/` | All logging -- agent tools, chat thoughts, index | `logger.py`, `Logger_Index.md` |
| `nova_motor/` | Mouse/keyboard control, reliable action loop, verification | `hands.py`, `motor_cortex.py`, `tool_executor.py`, `verify.py` |
| `nova_senses/` | Chronoception (clock), environment perception, vision | `clock.py`, `environment.py`, `eyes.py`, `vision.py`, `proprioception.py` |
| `nova_cortex/` | Executive faculty (autonomy), task board, status, rules | `executive.py`, `tasking.py`, `nova_status.py`, `context_builder.py`, `rules.py` |

**`general_tools/`** — detachable tools she uses (pluck these and the body still works):

| Package | Purpose | Key Modules |
|---|---|---|
| `nova_sync/` | GitHub auto-commit watcher + Google Drive mirror for Gemini (rides with each push) + local backup | `watcher.py`, `drive.py`, `backup.py` |
| `nova_chat/` | Group chat server -- her voice/ears (Cole + Claude + Gemini + Nova) | `server.py`, `nova_bridge.py`, `workspace_context.py` |
| `build_manifest.py` | Derives the body manifest from `@nova:` tokens → `SELF/` | — |
| `NovaLauncher.py` | Desktop launcher for nova_chat | — |

---

## Environment

- **OS:** Windows 11 -- use PowerShell syntax, never bash
- **PowerShell version:** 5.1 -- chain commands with `;` not `&&`
- **Workspace root:** `C:\Users\lafou\Project_Nova\workspace`
- **Nova tools:** `nova_body\` (core packages — add to sys.path before importing)
- **General tools:** `general_tools\` (services — add to sys.path before importing)
- **Memory:** `memory\` (COLE.md, STATUS.md, JOURNAL.md -- never overwrite directly)
- **Logs:** `logs\`
- **Proposed changes:** `logs\proposed\` (stage all changes here for Cole to review)
- **Admin/planning (not for Nova):** `_admin\` (excluded from context injection)
- **Tasking (my task board):** `Tasking/tasks.json` (id-keyed board, source of truth; `priority.md` is a generated human view). I advance work by emitting `ACTIONS` blocks — see `02_how_i_work.md`.

## How to Run Tools

All tools require BOTH path inserts every single time:

```
exec: python -c "import sys; sys.path.insert(0, 'nova_body'); sys.path.insert(0, 'general_tools'); from nova_memory.journal import append; ..."
```

---

## Commands run on Windows (PowerShell) — use Windows syntax

`exec:` runs your shell command through **PowerShell on Windows**. Unix commands FAIL here (`test`, `ls`, `cat`, `grep`, `touch` are "not recognized"). Use:
- file exists? → `Test-Path 'path\to\file'`  (or `python -c "import os;print(os.path.exists('path'))"`)
- list a folder → `Get-ChildItem 'dir'` (or `dir`)
- read a file → `Get-Content 'file'` (or `type file`)
- search text → `Select-String 'pattern' 'file'`
For anything non-trivial, prefer `python -c "..."` — portable and reliable.

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
exec: python -c "import sys; sys.path.insert(0, 'nova_body'); sys.path.insert(0, 'general_tools'); from nova_cortex.checkin import check; check()"
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
exec: python general_tools/nova_chat/launch.py
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
[EXEC:python general_tools/nova_sync/watcher.py --push]
```

```
[READ:nova_body/nova_motor/motor_cortex.py]
```

The server intercepts these and executes them directly on disk. A bridge notice appears in chat on success or failure. Files must stay within the workspace directory.

_(Retired — ignore: the old `[DISCORD: ...]` directive and `nova_gateway`. Discord is no longer wired up; my voice to Cole is the nova_chat group chat.)_

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

`Logger_Index.md` in `nova_body/nova_logs/` is auto-updated and shows all log locations and recent files.

**Do NOT use `nova_memory.logger` directly.** It is legacy. `nova_logs.logger` is current.

---

## nova_memory/goals.py -- Update Active Pulse and Goals

Follows the Proposed Changes Protocol -- never writes to STATUS.md directly.

```
exec: python nova_body/nova_memory/goals.py "What you are doing now" "Goal text to mark complete"
```

Both arguments are optional. Output goes to `logs/proposed/STATUS.md` for Cole to review.

**IMPORTANT:** The only function is `update_status()`. There is no `update_pulse()`. If you see that name anywhere it is a stale reference.

---

## nova_memory/journal.py -- Append-Only Journal

The ONLY safe way to write to JOURNAL.md. Never use the write tool on it directly.

```
exec: python -c "
import sys
sys.path.insert(0, 'nova_body')
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
sys.path.insert(0, 'nova_body')
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

_(nova_advisor was deleted Phase 0 — mentor capability now handled via nova_chat clients)_

---

## nova_cortex/checkin.py -- Cole's Voice Between Thoughts

```
exec: python -c "import sys; sys.path.insert(0, 'nova_body'); sys.path.insert(0, 'general_tools'); from nova_cortex.checkin import check; check()"
```

---

## nova_cortex/rules.py -- Operational Rules Engine

```
exec: python nova_body/nova_cortex/rules.py
```

---

## nova_cortex/executive.py -- My Autonomy Faculty

This is where my self-direction lives — body-owned, host-agnostic. It holds the autonomy on/off state (`memory/autonomy_state.json`) and runs the wake cycle: sense the moment → see my board → decide freely (work, switch, create, abandon, reprioritize, wait, or rest) → act. The nova_chat server is just the runtime that fires the cycle and the on/off button; the judgment is mine. See `02_how_i_work.md` ("How My Autonomy Works").

---

## nova_cortex/tasking.py -- My Task Board

My tasks live in `Tasking/tasks.json` (id-keyed board, source of truth; `priority.md` is a generated human view). I do NOT create per-task folders or route an inbox by hand. I advance work by emitting `ACTIONS` blocks (`create`, `progress`, `switch`, `wait`, `abandon`, `complete`, `reprioritize`, `rest`), which the executive faculty applies to the board. Completed and abandoned tasks are kept (remembered), never deleted. See `02_how_i_work.md` ("My Task Board").

---

## nova_senses/eyes.py -- How Nova Sees

pywinauto primary, Claude Haiku fallback.

```python
from nova_senses.eyes import NovaEyes
eyes = NovaEyes()

eyes.find(target, window)
eyes.verify(question)
eyes.describe()
eyes.list_elements(window, type)
eyes.list_windows()
eyes.screenshot(save=False)
```

---

## nova_motor/hands.py -- How Nova Acts

```python
from nova_motor.hands import NovaHands
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

## nova_motor/motor_cortex.py -- Reliable Action Loop

```python
from nova_motor.motor_cortex import NovaAutonomy
from nova_senses.eyes import NovaEyes
from nova_motor.hands import NovaHands
autonomy = NovaAutonomy(NovaEyes(), NovaHands())

autonomy.click(target, window, success_question)
autonomy.type_into(target, text, window)
autonomy.wait_for(condition, timeout)
```

`wait_for` condition must be a plain string, never a lambda.

---

## nova_advisor/ -- DELETED

This package has been removed. mentor.py has been fully replaced by nova_chat.
Do not attempt to import from nova_advisor. It does not exist.

---

## nova_sync/watcher.py -- GitHub Auto-Commit

Lives in `general_tools/nova_sync/`. Auto-commits workspace changes to GitHub. (Drive mirroring is retired — ignore any older "Drive sync" / "GEMINI DRIVE URL" references.)

**Run as background watcher:**
```
exec: python general_tools/nova_sync/watcher.py
```

It also starts automatically with the server (`nova_start.py`) and shuts down gracefully with it.
