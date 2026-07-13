# Nova Console — one window instead of cmd-window confetti

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

## Gotcha this fixed along the way

`nova_start.py` and `NovaLauncher.py` both called `input("Press Enter to exit...")` on failure.
With no console and no stdin, that would **hang forever, invisibly**. Both are gone:
`nova_start.halt()` now parks the error in the Launcher tab and holds the window open instead.

## Rollback

`NovaStart.cmd` → swap `start "" %PYW%` back to `py -3 nova_start.py`, and flip the three
`_NO_WINDOW` flags in `nova_start.py` back to `subprocess.CREATE_NEW_CONSOLE`.
