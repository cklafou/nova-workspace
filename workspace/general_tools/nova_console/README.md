# Nova Console — one window instead of cmd-window confetti
_Last updated: 2026-07-15 23:14:48_

_2026-07-13. Replaces the 4–5 popup consoles NovaStart used to spawn with a single dark, tabbed,
Nova-themed window that tucks into the system tray once Nova Chat is up._

## What it replaces

| Old popup window | Where it came from | Now |
|---|---|---|
| "Project Nova - Launcher" | `NovaStart.cmd` ran `py -3` (console python) | Gone — `NovaStart.cmd` uses **pythonw** |
| llama-server console | `nova_start.py` `CREATE_NEW_CONSOLE` | Gone — and it was **empty anyway**, its output already went to `logs/llama/` |
| NovaLauncher console | `nova_start.py` `CREATE_NEW_CONSOLE` | Piped → **Nova** tab |
| Watcher console | `nova_start.py` `CREATE_NEW_CONSOLE` | Piped → **Watcher** tab |
| A *new* console on every LoRA equip | `llama_control.py` `os.startfile(...)` = "double-click it" | Spawned `CREATE_NO_WINDOW` → **llama-server** tab |

## Pieces

- **`hub.py`** — captures every child's output into ring buffers and serves them on
  `http://127.0.0.1:8799`. Two capture modes:
  - `attach_pipe()` for processes we own (Nova, Watcher).
  - `tail_file()` for **llama-server** — because `LlamaControl` restarts it *out of band* (LoRA
    equip / Full Restart), so a pipe we opened would go dead. Tailing `logs/llama/` survives that.
- **`console_app.py`** — the desktop window (tkinter, dark Nova palette, a tab per stream) + tray
  icon. Runs as its own `pythonw` process, so a GUI hiccup cannot take the stack down.
- **Nova Chat "Console" widget** — `index.html`. Reads the **same** hub API, so the app and the
  widget can never show different data. Its `⬈ Window` button POSTs `/api/show` to summon the
  desktop window out of the tray.

## Behaviour

- Nova Chat **not** up → plain application window, visible, so you can watch the boot.
- Nova Chat comes up → **auto-minimises to the tray**. Restore from the tray icon, or from the
  Console widget in Nova Chat (View ▸ Widgets ▸ Console).
- **Closing the console window never kills Nova.** It hides to tray. The stack lifecycle still
  belongs to `nova_start.py`; the console is only a viewer.

## Requires

```
pip install pystray pillow
```

Both are optional-by-design: if they're missing the console still runs, it just can't do the tray
(the window minimises to the taskbar instead and tells you so in the footer). **A missing package
can never block Nova's boot.**

## Plain English toggle

Every line is translated **once, at write time**, by `plainspeak.py` — a rule table, not a model.
A log tail emits hundreds of lines a minute; sending them to an LLM would be slow, expensive, and
would sometimes **invent** a plausible-sounding wrong translation. A lookup table can't hallucinate.

- No rule for a line? It falls through to the **raw text, dimmed**. We never fabricate a friendly
  translation just to have something readable to show.
- Errors stay visibly errors (`✗`), warnings stay warnings (`⚠`). Plain-speak must never make a
  failure *sound* fine.
- Toggle lives in both the app header and the widget. Defaults to **on**.

```
[INFO] llama-server is HEALTHY on :8080        -> ✓ Nova's brain is loaded and responding.
load_tensors: offloaded 65/65 layers to GPU    -> Loaded 65 of 65 model layers onto the graphics cards.
"POST /api/equip HTTP/1.1" 500                 -> ✗ A POST request to /api/equip failed (error 500).
nothing to commit, working tree clean          -> No changes to save.
```

## THE REGRESSION THIS CAUSED (and the fix)

Removing the consoles created a worse problem. **A console-less process that spawns a console app
(git, powershell, nvidia-smi) makes Windows allocate a BRAND NEW console for it.** So:

- the **watcher** flashed a cmd window on every git call (auto-commit = constant blinking),
- Nova's **`run_command`** tool would have flashed a PowerShell window on *every shell command she
  ran*,
- `nova_start`'s nvidia-smi / Python probes flashed at boot,
- `llama_control`'s `_kill_port` PowerShell flashed on every LoRA equip.

Fixed by forcing `CREATE_NO_WINDOW` on **every** child: `watcher.py` (module-level `subprocess.run`
patch — catches any git call added later), `tool_router.py`, `nova_start.py`, `llama_control.py`.

## StopNova.cmd — rewritten

The old one only killed whatever LISTENED on 8080/8765. The orchestrator, the console app, and the
**watcher** listen on nothing — so StopNova appeared to do nothing and the watcher kept firing git
commands forever. Now it's two phases:

1. **Ask nicely** — `POST :8799/api/shutdown`. `nova_start.py` runs its normal teardown, which
   sends **CTRL_BREAK** to the watcher so it finishes its git push instead of leaving a stale
   `.git\index.lock`. A `taskkill` *cannot* do that.
2. **Force** — sweep ports 8080/8765/8799, `llama-server.exe`, and any python/pythonw whose
   **command line** matches Nova's scripts (so an unrelated Python of yours is never touched).

## THE ACTUAL CAUSE OF THE FLASHING (found 2026-07-13, after two wrong fixes)

It was never really a *window* problem. It was an **infinite git loop**, and every lap shelled out
to git.

`watcher.py` tried to avoid feeding itself:

```python
if src_path.endswith(".pyc") or "FILE_INDEX.md" in src_path:   # <- the bug
    return
```

`"FILE_INDEX.md"` is **not a substring of** `"FILE_INDEX_LINK.md"`. So the LINK file — which the
watcher itself regenerates — was never excluded. It regenerated it, saw it change, stamped a fresh
`_Last updated_` into it (it's `.md`, so the content *always* differs), committed, pushed, and
regenerated again. Forever.

**Evidence:** `FILE_INDEX_LINK.md` appeared in **60 of the last 60 commits**; **204 commits in one
hour**.

Fixed with a `GENERATED_ARTIFACTS` prefix list (`FILE_INDEX`, `GEMINI_INDEX`, `Logger_Index`,
`manifest.json`, `sessions_index`) — *anything the watcher generates must be excluded from what the
watcher watches, matched by prefix, never by exact filename.*

A second, slower loop was fixed too: `update_timestamp_in_file()` **writes** the file it just saw
change, which fires another event, and a second later the new timestamp differs — so it writes
again. Now rate-limited to one stamp per file per 30s.

> **Note:** the repo has ~200 junk `auto-commit` commits from the loop. Squashing them is your call
> — I don't rewrite history without being asked.

## Stray-console janitor (the safety net)

`stray_janitor.py` runs inside the console app. It enumerates `ConsoleWindowClass` windows, walks
the owning process's parent chain, and **hides** any whose ancestry reaches a known Nova PID —
catching even `git push`'s grandchildren. Each sighting is reported to a single deduped **Strays**
tab (first sighting, then only at x10/x100/x1000, so a loop can't flood it).

**It cannot capture their text.** Once a process owns a console, its stdout goes to that console's
buffer; there is no supported way to reach in afterwards and redirect it. Their output is already
in `logs/` anyway. It stops the flashing and tells you *what* flashed — that's the honest limit.

**It never touches a window that isn't Nova's** — your own terminals are checked by process
ancestry and left alone.

If the Strays tab is busy, the janitor is papering over a real bug upstream. It's a net, not a fix.

## Gotcha this fixed along the way

`nova_start.py` and `NovaLauncher.py` both called `input("Press Enter to exit...")` on failure.
With no console and no stdin, that would **hang forever, invisibly**. Both are gone:
`nova_start.halt()` now parks the error in the Launcher tab and holds the window open instead.

## Rollback

`NovaStart.cmd` → swap `start "" %PYW%` back to `py -3 nova_start.py`, and flip the three
`_NO_WINDOW` flags in `nova_start.py` back to `subprocess.CREATE_NEW_CONSOLE`.
