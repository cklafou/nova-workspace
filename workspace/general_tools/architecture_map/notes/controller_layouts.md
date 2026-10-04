<!-- @nova: Explain the desktop controller menus, widgets and saved layouts published in Operations. -->
---
doc: OPERATIONS.md
order: 40
---
## Controller menus and layouts

Nova Chat has one workspace. The top application bar contains expandable menus; opening Services,
Advanced or Appearance leaves the dock arrangement alone. Widgets opens the widget choices, including
Collaboration and Model updates. The optional Services and Generation widgets mirror the original menu
controls and forward their actions; the menu controls keep their unique IDs and existing handlers.
The dock contains legacy panel layers, so Live log and Console cannot cover menus or intercept
their clicks. Dialogs and updater notifications remain above docked content.
Services calls the chat server Controller. The status bar explicitly shows Nova off / Chat only
when Nova is not running, separately from controller connectivity.

Conversation has its own **Start Nova / Stop Nova** control below the session tabs, including when
all conversation tabs are closed. It reports starting/stopping and disables competing actions until
the launcher resolves the transition. Stopping keeps the controller window and Collaboration usable;
starting uses the configured model. The page reconnects after the runtime worker changes and preserves
unsent text, selection, attached images and mentioned files. A draft-storage failure is shown instead
of silently discarding the draft. Older launchers show a restart instruction rather than a working
button. This control differs from stopping the current reply, muting Nova or closing a conversation.

Widget layouts save **manually**. Drag tabs to reorder, stack or split, resize dividers, or pop widgets
into separate windows; these edits stay temporary until **Save layout** captures the live arrangement,
split sizes and popouts. The status distinguishes **Unsaved changes**, **Saving…**, **Saved** and
**Save failed**. Save success requires a successful local-storage write; failure keeps the arrangement
open without changing its last saved copy. Native window size persists separately.

Choose a name in the Layout selector, then **Load layout** to apply it. Selecting alone does nothing;
Load discards the departing layout's unsaved edits and does not automatically save its arrangement or
selected layout. **Revert** restores the currently loaded layout's last saved baseline, regardless of
which name is pending in the selector. **Undo** and **Redo** traverse up to 100 layout snapshots in the
current session, with a drag/resize treated as one edit; Revert is itself undoable. Loading another
layout or reloading the page resets that edit history. Reload/close discards unsaved widget edits;
no dock-change, switch or unload handler automatically saves them.

The management control explicitly creates, renames, duplicates or deletes named layouts, keeping at
least one. Those button actions persist their intended change. **Duplicate current** saves the draft
as a new named layout without overwriting the original. Appearance's **Use starter arrangement
(unsaved)** is an undoable draft change and needs Save layout to persist. Widget menu/library checkmarks
include hidden dock tabs and live popouts. Choosing an open widget focuses it; choosing a closed widget
opens it.

Storage is `nova.controller.layouts.v2` in that profile's local storage. The previous mode selection and
saved Together/Observe/Focus layouts migrate into editable named layouts; the old keys remain intact.
Deletion retains a recovery copy, bounded to twenty records; older reset/recovery records remain available.
An unrestorable saved layout is left unchanged. Saved popouts return to the main dock on restore.
Loading another arrangement closes the old popouts before loading, without saving the departing draft.
A native Nova Chat window and a separate browser have independent layout profiles.

The October 4 screenshot is available as a separate **Screenshot reference** named layout. A one-time
`screenshotReference: "2026-10-04"` migration adds it without selecting it or replacing Default Workspace.
Select it and choose Load layout to use it. Existing layouts and prior recovery copies remain intact;
there is no second automatic active-layout reset.

The native profile now lives at `~/ProjectNovaData/Controller` (`%USERPROFILE%/ProjectNovaData/Controller`
on Windows), outside AppData virtualization. On the first actual desktop launch, if that destination does
not yet exist, the app stages a copy of the caller's old `%LOCALAPPDATA%/ProjectNova/Controller/window.ini`
and `storage/`, then publishes the complete profile. The legacy profile stays intact; disposable cache
is not copied. Migration failure displays an error and exits rather than silently opening a blank
profile. An existing new profile is authoritative; explicit `--profile-dir` previews stay isolated.

Native movement, resizing and window-state changes save after a 350 ms debounce; tray-close and
application quit flush immediately. Minimized windows retain their last normal geometry, maximized
state is restored, and Qt clamps a saved window to available screens. A settings-write failure appears
in the native status bar. Closing the main window hides it when a tray is available; **Nova → Quit Nova**
or the tray's **Quit Nova** exits the app. **Ctrl+R** reloads renderer changes only; desktop Python changes
and profile migration require a full quit and relaunch.

Verification for this persistence repair: 15 isolated desktop tests passed, including resize/move
restoration between two fresh offscreen Qt processes and migration success/failure fixtures. Twenty-one
Node scenarios cover manual saving/loading, Revert, Undo/Redo, screenshot reference and widget checks.
Live browser checks verified draft discard on reload, Undo/Redo, Revert, explicit Save surviving reload,
select-then-Load behavior, screenshot reconstruction and open-widget checks, with no browser errors.
The user's running native app was not restarted or its real profile migrated during this repair;
native reopening remains a separate verification.

Live log includes recorded history as well as new events. Earlier dates are displayed beside the time;
event labels distinguish scheduled reminders from model responses. A `stretch_nudge` comes from the
existing shelf watcher called at autonomy startup: its canned wording does not demonstrate fresh model
inference. Its posture record freshness is a separate runtime issue; the controller does not alter it.
