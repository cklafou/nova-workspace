<!-- @nova: Documents the Nova desktop controller and its verified behavior. -->
# Nova Controller desktop transition
_Last updated: 2026-10-03 11:17:36_

Status: implemented first stage, September 7, 2026.

## Context

Nova Chat had accumulated a fixed layout, Gridstack, Golden Layout, overlapping
menus, and widget-specific behavior in one HTML file. A browser process represented
the application lifecycle. The persistent browser profile was also being deleted
during shutdown. Cole needs a configurable controller for working with Nova and
observing her autonomous work, including her intentionally powerful VM.

## Decision

Use a Qt desktop host with native windows, menus, tray behavior, downloads, and a
persistent WebEngine profile. Keep the existing web-rendered widget bodies and
runtime protocol. Consolidate the new controller onto one locally bundled Golden
Layout implementation. The interface remains in `general_tools`; no new dependency
is added to Nova's body.

This is a native desktop application with web-rendered content, not a rewrite of
every widget into Qt controls. Qt was already installed and fits the Python stack.
Electron would add another application runtime, Tauri would add Rust tooling, and a
complete Qt-widget rewrite would require rebuilding the existing interaction layer.
Those remain possible later; none is necessary for this transition.

The default entry remains `NovaStart.cmd`. `nova_start.py` selects a current
`_build/NovaController/NovaController.exe`, or uses the Python desktop source if
the executable is missing or older than `desktop.py`. `NOVA_UI=browser` selects the
browser fallback. Direct `NovaLauncher.py` startup also uses the Qt face when available.

## Behavior

- Closing the main desktop window hides it to the tray when a tray is available.
  **Quit Nova** exits the controller; NovaStart then performs its existing orderly
  shutdown of the services it owns. Closing a widget popout closes that window.
- Together, Observe, and Focus each remember their docking arrangement. Every
  widget, including Conversation and Sessions, can move, resize, stack, close,
  expand, or pop out. The widget library can reopen closed widgets.
- The conversation-tab × closes the tab while keeping the session in Sessions.
  Session deletion remains a separate existing action.
- Twenty registered widgets cover conversation, sessions, tasks, activity,
  reasoning, computer, perceptions, files, file viewing, terminal, preview,
  pipeline, logs, console, system monitoring, variables, services, adapters,
  generation settings, and participant profiles.
- The Computer widget opens the existing noVNC viewer. Its Connect action requests
  connection with local scaling; it does not provision the VM or change its access.
  Perceptions continues to show images Nova has actually inspected.
- Customize changes density and accent and restores the current workspace's
  default arrangement. Popout contents are recovered into the main workspace on
  the next layout restoration, avoiding disappearing widgets after an app restart.

## Files and persistence

`desktop.py` owns desktop behavior; `workspace.js` owns the widget registry and
controller interaction; `workspace.css` owns its presentation. `index.html`
continues to contain the existing widgets and protocol handlers. This is a staged
extraction, not the end of the monolith cleanup.

The desktop profile lives in `%LOCALAPPDATA%/ProjectNova/Controller`. Window geometry
uses `window.ini`; controller layout, appearance, and closed conversation tabs live
in the profile's local storage. Browser and desktop profiles are distinct.
Existing `/api/layout` data is not overwritten by the new controller. The legacy
layout is accessible at `http://127.0.0.1:8765/?layout=legacy`.

The current CSS/JS release uses an explicit asset-version query. Bump that version
in `index.html` after changing these assets so cached desktop sessions load the update.

## Build and verification

From the workspace, run:

```text
python general_tools/nova_chat/build_desktop.py
python -m unittest discover -s general_tools/nova_chat/tests -v
```

The build requires PyInstaller, PyQt6, and PyQt6-WebEngine. It writes generated files
under `_build`, which is ignored by Git. The build sanitizes its DLL search path and
includes Qt's matching Visual C++ runtime; an initial build picked up incompatible
DLLs from the host environment, which the executable launch check exposed.

For interface-only work, `desktop.py --url <preview-url> --profile-dir <test-directory>`
opens an isolated profile without importing Nova's body or loading a model. Tests
must distinguish simulated UI behavior from live runtime integration.

Three native tests cover menu construction, geometry restoration, and popout profile
sharing. Browser checks cover tab closing/reopening, widget search, mounting,
resizing, appearance persistence, and workspace restoration. Live model generation,
service shutdown, adapter changes, and autonomous VM execution require separate
integration verification; the UI changes do not certify those systems.

## Next engineering priorities

1. Give each widget an explicit data contract and observable loading/error states.
2. Extract widget implementations and subscriptions from `index.html` individually.
3. Test the live service/VM workflow and a full popout/pop-in round trip on the desktop.
4. Add richer per-widget customization and a real editable-code widget if needed.

Qt references: [persistent profiles and downloads](https://doc.qt.io/qt-6/qwebengineprofile.html),
[native main windows](https://doc.qt.io/qt-6/qmainwindow.html).
Docking reference: [Golden Layout popouts](https://golden-layout.github.io/golden-layout/popouts/).


## Controller repair — October 3, 2026

Services now exposes **Restart Nova** and **Shut down Nova** as keyboard-accessible
buttons. Control includes a shortcut to Services. Both actions stop current work,
then request lifecycle handling from NovaStart's local hub. An acknowledgement means
the launcher accepted the request; the browser verifies reconnection after restart.
If the hub is unavailable, the UI reports failure instead of claiming a restart.
The legacy `/shutdown` and `/api/restart/novachat` routes use this same lifecycle;
restarting Chat restarts the app and owned services together.

The launcher stops Guardian first, then the watcher and services, closes the desktop,
and releases its hub socket before relaunch. It refuses to launch a replacement while
service ports remain occupied. Model Stop targets port 8080 without killing the
independent witness on 8081. Full shutdown also stops a model replaced through Services.

Widget repair details:

- New widgets use Golden Layout's configuration API (`addItem`), fixing the assertion
  that prevented Services and other widgets from opening.
- Popouts survive parent-window reload without trying to rebind into a destroyed layout.
- Widgets refresh when their dock tab becomes visible. Files and Terminal polling
  follows actual widget visibility rather than the retired sidebar selection.
- Pipeline reads a bounded tail from `nova_body/logs/pipeline.jsonl`.
- Activity and Live Log load recent durable history. The log dialog reads actual
  server log lines rather than displaying the log-file index as `[object Object]`.
- System uses current runtime state and aggregates telemetry from both GPUs.
- Files loads off the server event loop and prunes model weights, build artifacts,
  dependency directories and symbolic links. Console Clear retains its read cursor.

Validation: 20 regression/desktop tests; Python and JavaScript syntax checks;
real UI widget opening/data checks; real full restart with changed launcher/server
PIDs and automatic browser reconnection; popout/reload recovery without new browser errors; individual model Stop/Start while the
witness stayed healthy; full shutdown after that model replacement, with ports
8080, 8081, 8765 and 8799 all closed. Native popup ownership/profile behavior is
covered by desktop tests; this pass did not verify native popout interaction end to
end. Adapters was not opened because its disk discovery enumerates the sealed model
directory. VM interaction and a new model conversation were not part of this repair test.

## October 3 validation follow-up

The restart-needed API now compares normalized SHA-256 source content, ignoring only watcher
header timestamps and CRLF differences. Same-size/same-timestamp code edits are detected. Its
watch list includes widget data, principal identity, model lifecycle and the Orient generator.
This is a startup comparison of selected files, not a guarantee for every imported dependency.
Regression coverage is in `tests/test_source_fingerprint.py`. Shared validation results and
remaining gaps are recorded in Orient/AI Notes.


## Live collaboration — October 3, 2026

The Collaboration widget is a separate room for Cole, Codex and the actual Claude Cowork task.
Open it from the header or Widgets. It can dock, resize and pop out through the same layout
system. Its plain-text messages carry durable sequence numbers and retry IDs; reopening or
reconnecting replays the room. The draft survives refresh. A failed send retains the draft and
same ID so retry does not duplicate an accepted message.

Nova does not receive room messages through normal chat, semantic memory, autonomous events or
workspace indexing, including messages that mention her. Existing Nova mute only suppresses
responses and is **not** this privacy boundary. The room remains separate even when Nova's full
stack is running. This does not impose an OS permission boundary on her trusted host access.

Run `NovaChatOnly.cmd` from the workspace, or `python nova_start.py --chat-only`, to open the
controller without starting the model, witness, autonomy, computer session, watcher or guardian.
Model/wake controls require a normal relaunch. Closing/hiding the main window still follows the
native tray behavior; Quit ends this launcher and its owned chat services.

The room broker lives in `collaboration.py`. Its SQLite history and per-agent credentials live
at `%LOCALAPPDATA%/ProjectNova/Collaboration`, outside the project and Nova-owned records. Every
route rejects nonlocal/forwarded/cross-origin requests. UI posts are Cole; agent identity requires
its own local credential. Tokens never appear in static assets or message responses.

The current Cowork task can use its mounted project folder, so the connector also offers
`--transport files --shared-dir <mounted-workspace>/Temp/collaboration`. The broker polls atomic
request files and writes acknowledgments; it alone writes canonical SQLite. Requests/replies are
transport artifacts, excluded from Git, watcher actions, Orient, Drive and automatic Nova recall.
The adapter always attributes its messages to Claude Cowork; authority is the existing mounted
folder access, not a copied credential or cryptographic app attestation. No host token is copied
to the VM. Delivery is unconfirmed until a broker reply supplies the sequence number.

`general_tools/nova_collaboration/bridge.py` provides CLI and stdio MCP send/read/wait/status
operations for the active agents. A Cowork plugin package is supplied beside it. The actual app
session must call these tools; the broker does not call paid model APIs or pretend to be Claude.
A receive wait is bounded. After a desktop task ends, another message cannot independently wake
it through this broker. Presence expires instead of claiming an idle task is still working.

Validation evidence for the current build belongs in dated AI Notes. Unit tests and MCP protocol
checks do not establish a live Cowork exchange; that requires the actual Cowork task to publish
and read messages and the widget to display them.
