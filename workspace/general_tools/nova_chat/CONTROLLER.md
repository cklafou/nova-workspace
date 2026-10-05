<!-- @nova: Documents the Nova desktop controller and its verified behavior. -->
# Nova Controller desktop transition
_Last updated: 2026-10-05 21:33:06_

Status: desktop controller implemented; named layouts, anchored menus and the model updater integrated October 4, 2026. Validation scope is recorded below and in dated AI Notes.

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
  **Nova → Quit Nova**, or the tray menu's **Quit Nova**, exits the controller; NovaStart
  then performs its existing orderly shutdown of the services it owns. Closing a
  widget popout closes that window. **Ctrl+R** reloads the interface; a full quit and
  relaunch is required to load changes to the native desktop host.
- One customizable workspace uses a compact **Layout** selector with **Save layout**,
  **Load layout**, **Revert**, **Undo** and **Redo** beside it. Widget edits are
  temporary until Save layout captures the live arrangement, divider sizes and
  popout configuration. Status distinguishes **Unsaved changes**, **Saving…**,
  **Saved** and **Save failed**. Failure leaves the arrangement open and preserves
  its saved baseline. Native window size persists separately. Every widget,
  including Conversation and Sessions, can move, resize, stack, close, expand, or
  pop out. An empty layout offers **Browse widgets** to begin arranging it.
- Selecting a layout name stages a choice; **Load layout** applies it and discards
  unsaved edits to the departing layout. **Revert** restores the currently loaded
  layout's last saved baseline, even when a different selector choice is pending.
  **Undo/Redo** keep up to 100 snapshots in the current session and group a drag or
  resize as one edit. Revert can be undone. Loading another layout or refreshing
  clears edit history. Reloading/closing discards unsaved widget changes; changing
  the dock, switching layouts and page unload never save an arrangement automatically.
- **⋯** explicitly creates, renames, duplicates or deletes layouts; these management
  actions persist and keep at least one layout. **Duplicate current** saves the
  current draft under a new name without overwriting its original saved layout.
- The single application bar keeps File, View, Agents, Services, Advanced and Widgets
  as anchored dropdowns. **Widgets** and its searchable library explicitly open
  widgets. Services and Advanced remain in their original DOM locations; optional
  Services and Generation widgets mirror their controls and forward their existing
  handlers. The original control IDs are not duplicated or moved into a dock. Widget
  menu/library checkmarks include hidden dock tabs and live popouts; selecting an
  already-open widget focuses it instead of toggling it closed.
- Conversation contains Voice Start/Stop, separate microphone/output mute, compatible-device
  selection and bounded microphone/speaker tests. Tests work with Nova off; conversations need
  Nova on. Audio never starts on page load. The temporary Windows system voice is labelled,
  delivered captions retain their audit status, and Stop closes the owned worker. Voice settings
  scroll without covering the composer or the message viewport's Latest button.
- The conversation-tab × closes the tab while keeping the session in Sessions.
  Session deletion remains a separate existing action.
- The registry includes Control, Conversation, Collaboration, Model updates,
  Sessions, Tasks, Activity, Thoughts, Computer, Perceptions, Files, File viewer,
  Terminal, Preview, Pipeline, Live log, Console, System, Variables, Services,
  Adapters, Generation and Profiles.
- Model updates opens a review workflow for checks, install plans, adapters and
  training. Notifications initialize only in the main window; choosing Update
  opens the workflow and does not authorize an installation by itself. Training
  starts use the reviewed request ID returned by the updater backend. Keep, export and paid
  training have distinct results; export creates inputs only. Settings can check RunPod credit,
  and insufficient credit links to Billing before a paid run. Google browser sign-in alone
  does not grant the backend API access. Training inputs and finished adapter paths are
  displayed separately, with adapters beside their base model.
- The Computer widget opens the existing noVNC viewer. Its Connect action requests
  connection with local scaling; it does not provision the VM or change its access.
  Perceptions continues to show images Nova has actually inspected.
- **Appearance** is an anchored menu for density and accent. **Use starter
  arrangement (unsaved)** creates an undoable draft; Save layout is required to keep
  it. Other named layouts are unaffected.
- Loading layouts closes the old layout's separate windows before loading the next
  arrangement, without automatically saving the departing draft. Their widgets return to the original layout's
  dock when it is restored; stale popout windows are not reopened automatically.
  Choosing a widget already open in a separate window focuses that window.
- Chat-only mode visibly reads **Nova off · Chat only** in the status bar. The
  Services row labeled **Controller** reports the chat/controller server, not a
  running Nova. Collaboration opens automatically for a fresh chat-only workspace;
  an existing saved layout, including an intentionally empty one, is respected.
- Live log combines recent durable history with incoming events. Entries from a
  different local date include their date and time; each row's tooltip identifies
  the event type and recorded timestamp. `stretch_nudge` is visibly labeled
  **Scheduled reminder**, distinguishing the scheduled event from a model response.

- Pipeline shows each widget/tool action from start through its outcome, including environment,
  duration and operation identifiers. Action rows stay visible when audit details are collapsed.
  Failed, cancelled, timed-out, refused and unknown outcomes remain distinct from completion.
  Witness **Incomplete** and **Error** states explicitly mean the reply was not verified; unknown
  stages use neutral styling. A historical approval row containing an unfinished read request
  displays as incomplete, preserving the original log. Polling compares event content, so updates
  within the same timestamp remain visible.

## Files and persistence

`desktop.py` owns desktop behavior; `workspace.js` owns the widget registry and
controller interaction; `workspace.css` owns its presentation. `index.html`
continues to contain the existing widgets and protocol handlers. This is a staged
extraction, not the end of the monolith cleanup.

The desktop profile lives in `~/ProjectNovaData/Controller` (on Windows,
`%USERPROFILE%/ProjectNovaData/Controller`), outside the AppData paths that MSIX can
virtualize differently for Codex and ordinary launches. Window geometry uses
`window.ini`; controller layout, appearance, and closed conversation tabs live in
the persistent renderer `storage/`. Browser and desktop profiles are distinct.

On first launch with no canonical profile, the actual desktop process copies
`window.ini` and `storage/` from its own view of the previous
`%LOCALAPPDATA%/ProjectNova/Controller` into a staging directory, then renames the
complete copy into place. The old profile is preserved and disposable cache is
omitted. A copy failure shows a native error and aborts instead of starting with
blank settings. An existing canonical profile wins on subsequent launches.
Explicit `--profile-dir` previews never import the user's profile.

Move, resize and window-state events persist geometry after a 350 ms debounce,
without waiting for the window to close. Close-to-tray and application quit flush
immediately. Minimized windows preserve their last normal geometry; maximized
state and its restore size persist. Qt adjusts off-screen saved geometry to the
available screens. Settings write failures remain visible in the native status
bar. Reloading web content does not replace the running native host or migrate
its profile; that happens on a full quit and relaunch.

Named layouts use the local-storage key `nova.controller.layouts.v2`, containing
`version: 2`, `activeId`, `items` and a bounded `deleted` recovery collection. Each
item has an ID, name, starter seed and Golden Layout configuration, with an update
time after saving. Existing Together/Observe/Focus configurations migrate to named
layouts while keeping the selected arrangement. The old `nova.controller.v1` and
`nova.controller.dock.*` keys remain untouched. An unreadable v2 collection is copied
to a timestamped `.recovery.*` key before fallback. Deletion retains a recovery
copy, bounded to 20 records; previous reset/recovery copies stay intact. An
unrestorable saved configuration is left unchanged. These copies are not a
user-facing trash or a substitute for a profile backup. Loading a layout alone
does not persist the selected layout; Save layout commits its arrangement and
active selection. Explicit named-layout management also persists its own changes.

Cole's October 4 screenshot is available as a separate **Screenshot reference**
named layout. The one-time `screenshotReference: "2026-10-04"` migration adds that
option without selecting it, overwriting Default Workspace or resetting the
active arrangement. Choose its name and Load layout to restore it. Earlier
recovery copies remain intact. Page teardown only cancels pending in-memory
history updates; it never writes the unsaved arrangement or an empty dock over
the last saved configuration.

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

As of the October 4 persistence repair, 15 isolated desktop tests cover menus,
popout profile sharing, debounced movement/resizing, maximized/minimized state,
tray/quit flushing, off-screen restore, visible write errors and profile migration.
A two-process offscreen Qt regression writes geometry, exits without close/quit
hooks, and restores the same size and position in a fresh process. Twenty-one Node
scenarios cover manual Save/Load, Revert, Undo/Redo, no unload autosave, screenshot
reference and widget checkmarks. Live browser checks verified close-widget drafts,
Undo/Redo, Revert, discard on reload, explicit Save surviving reload, selection
without loading, explicit screenshot loading and open-widget checks, with no
browser errors. Earlier browser checks also cover tab closing/reopening, search,
mounting, resizing and appearance. The user's running native app was not restarted
and its real profile was not migrated during this repair; native reopen
confirmation remains separate from those fixtures and browser checks.
Live model generation,
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

Services exposes **Restart app and services** and **Shut down app and services**
as keyboard-accessible buttons (clarified labels as of October 4). Control includes a shortcut to Services. Both actions stop current work,
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
Open it from **Widgets → Collaboration** or the widget library. It can dock, resize and pop out through the same layout
system. Its plain-text messages carry durable sequence numbers and retry IDs; reopening or
reconnecting replays the room. The draft survives refresh. A failed send retains the draft and
same ID so retry does not duplicate an accepted message.

Nova does not receive room messages through normal chat, semantic memory, autonomous events or
workspace indexing, including messages that mention her. Existing Nova mute only suppresses
responses and is **not** this privacy boundary. The room remains separate even when Nova's full
stack is running. This does not impose an OS permission boundary on her trusted host access.

Run `NovaChatOnly.cmd` from the workspace, or `python nova_start.py --chat-only`, to open the
controller without starting the model, witness, autonomy, computer session, watcher or guardian.
Use **Start Nova** in Conversation to enable the full stack; wake/model controls remain inactive until then. Closing/hiding the main window still follows the
native tray behavior; Quit ends this launcher and its owned chat services.

The room broker lives in `collaboration.py`. Its SQLite history and per-agent credentials live
at `%USERPROFILE%/ProjectNovaData/Collaboration`, outside the project and Nova-owned records. Every
route rejects nonlocal/forwarded/cross-origin requests. `NOVA_COLLABORATION_DIR` can select
an explicit shared directory. The default stays outside AppData to prevent Windows MSIX
virtualization from splitting Codex and ordinary desktop launches into separate rooms. UI posts are Cole; agent identity requires
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


## Named-layout and menu validation — October 4, 2026

An isolated browser fixture exercised the real docking and workspace code, with
simulated service/widget data and no model API access. Checks covered legacy
migration, rename, duplicate, empty creation, case-insensitive name uniqueness,
two-step deletion, the final-layout guard, selection persistence after reload,
and keeping a saved empty layout empty in chat-only mode. Services and Advanced
stayed anchored; both menu and mirrored widget controls forwarded their handlers.
The Generation mirror updated the original slider and its handler.

A real browser popout exposed a timing race: Golden Layout schedules window closure,
so immediately restoring the next layout allowed the old unload callback to insert
its widget into the new layout. The controller now waits for those windows to close.
The repeated fixture check preserved separate arrangements and restored the original
widget to its dock; opening an already popped-out widget did not duplicate it.

The header and dropdowns were visually checked at desktop, 760px and 390px widths.
The fixture finished without console errors. Node checks covered migration/recovery,
the delayed popout-close regression, historical log formatting and JavaScript syntax.
These checks do not certify live model installation, training, VM use or native Qt
popout interaction; dated AI Notes hold the separate live controller results.

A later live check exposed a second integration issue: the docked Live log retained
its legacy `z-index: 9999`. It remained a stacking context as a flex child even after
becoming `position: static`, so log rows intercepted clicks intended for Services.
The main dock now isolates its stacking layers, log/console panels reset their old
z-index, and application overlays sit above the dock. An expanded fixture using the
actual legacy log CSS confirmed menu, update notification, legacy modal and native
dialog hit tests; service and notification clicks reached their intended handlers.


## Conversation power — October 4, 2026

Conversation provides **Start Nova / Stop Nova**, even with no open conversation tab. The
launcher changes between full and chat-only services while retaining the desktop window and console.
The runtime worker briefly reconnects; unsent draft text, selection, images and file mentions survive
the page reload. Pending requests disable competing controls. Unreachable or older lifecycle owners
produce an actionable status instead of pretending the button worked. Existing installations need
one normal full app restart to load the new launcher/backend.

Stopping drains supervised activity, flushes the active session and closes owned worker helpers
before teardown; a failed drain refuses the switch. New body input and updater writes are blocked
until the transition settles, including in the replacement worker. Starting reads the updater's
selected model through the existing model launcher. Startup failure attempts chat-only recovery.
Quitting the desktop during startup cancels readiness waits and prevents further service launches.

Verification: 61 combined lifecycle/launcher/chat-only/controller regression tests, 8 updater
integration tests, 152 updater tests (3 opt-in skips), the Node updater suite and 8 Conversation
power UI scenarios passed. A real browser using the real lifecycle router and button code with
simulated services completed off -> on -> off (button labels Start -> Stop -> Start), retained an unsent draft across both reloads
and produced exactly one start and one stop request with no browser errors. That fixture does not
prove a live model start or Qt window continuity. The real Nova and native window were left untouched
while Cole was gaming; the first full native service cycle remains to be checked after restart.

Cancellation requested is a pending cleanup state, not confirmation that a worker or application stopped. Pipeline keeps that distinction visible on the correlated tool row.
