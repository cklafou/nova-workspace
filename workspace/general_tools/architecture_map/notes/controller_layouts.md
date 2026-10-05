<!-- @nova: Explain the desktop controller menus, widgets and saved layouts published in Operations. -->
_Last updated: 2026-10-04 15:13:52_
---
doc: OPERATIONS.md
order: 40
---
## Controller menus and layouts

Nova Chat has one workspace. The top application bar contains expandable menus; opening Services,
Advanced or Appearance leaves the dock arrangement alone. Widgets opens the widget choices, including
Voice, Collaboration and Model updates. The optional Services and Generation widgets mirror the original menu
controls and forward their actions; the menu controls keep their unique IDs and existing handlers.
The dock contains legacy panel layers, so Live log and Console cannot cover menus or intercept
their clicks. Dialogs and updater notifications remain above docked content.
Services calls the chat server Controller. The status bar explicitly shows Nova off / Chat only
when Nova is not running, separately from controller connectivity.

Conversation has a compact **power button** below its composer, beside Users and Options, including
when all conversation tabs are closed or the controller is chat-only. Its accessible label and status
tooltip say **Start Nova / Stop Nova**; its green state indicates Nova is on. It reports starting/stopping and disables competing actions until
the launcher resolves the transition. Stopping keeps the controller window and Collaboration usable;
starting uses the configured model. The page reconnects after the runtime worker changes and preserves
unsent text, selection, attached images and mentioned files. A draft-storage failure is shown instead
of silently discarding the draft. Older launchers show a restart instruction rather than a working
button. This control differs from stopping the current reply, muting Nova or closing a conversation.

**Voice** is a separate dockable widget opened from Widgets or the widget library. It can be resized,
stacked or popped out and participates in the normal active-widget checkmarks. Adding it does not
replace a saved layout or save any arrangement automatically. **Call Nova / End call** owns the
shared audio session; closing or moving the widget only changes its UI. Microphone and speaker mute
are independent. Prominent confirmed mute indicators explain when input is not sent or replies will
be silent; a failed status refresh shows unknown, and output mute cannot look like Speaking. The
primary surface distinguishes listening, Hearing you, Finishing your turn, Recognizing speech and
waiting/thinking, with delayed/suppressed reply notices. The backend's configured pause allowance is
shown when known; it is not a reply-time promise. No audio levels or countdown are invented. New
utterances continue active body work while retaining committed queued speech. Explicit End call keeps
its scoped cancellation behavior. Conversation's **added to active work** badge means input was
accepted for the next completed model/tool step; it does not mean the pending provider call was
interrupted or the input has already been applied. The ordinary queued badge means waiting for admission; during autonomous work this can be the next natural body boundary, while input that cannot join waits for a later turn.
Conversation frames tagged for another session do not create bubbles in the selected tab, including
late echoes, thinking tokens and final replies. The separate Thoughts feed remains global; untagged
legacy/global frames retain their previous behavior. The current server session-switch path still cancels its active task; filtering also guards late frames already in flight.
Audited committed segments grow one response bubble, labelled Reply in progress with delivered-part
count and the actual audit disposition. The terminal aggregate reconciles that same bubble without a
second reply; Turn complete/ended distinguishes final closure from continuing work. Reloaded history
retains separate delivered parts with their saved part number and actual audit disposition. Voice likewise
reports a delivered part while work continues and never speaks the final aggregate again. New input
retains committed queued speech; full-duplex barge-in cuts current audio and pauses the rest through
recognition, while explicit End call/Stop/output mute flushes it.

Expand **Settings & tests** for compatible 16 kHz mono inputs/outputs, Apply while stopped and bounded
microphone/speaker tests. **Stop test** cancels a test. Page load/status polling never opens devices;
device discovery is explicit. Tests work while Nova is off; a call needs Nova on. The installed English
Whisper large-v3-turbo recognizer runs CPU int8; Windows system speech is labelled temporary.
**Latest words** and **Delivery & playback details** are secondary: captions retain their actual audit
status, missing approval is never PASS, and correlated request/message/run IDs expose delay, suppression,
output submission and completion/failure. A playback API receipt does not prove audible output.

Conversation and Collaboration each anchor **↓ Latest** inside their message viewport. The control
appears when the reader is more than 60 pixels above the bottom, including manual scrolling without
new messages. New incoming messages leave the older scroll position alone and update the unread
count; choosing Latest scrolls to the bottom and clears it. Hidden-browser checks confirmed the
Collaboration scroll/show/click/hide behavior; its messages remain separate from Nova.

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
restoration between two fresh offscreen Qt processes and migration success/failure fixtures. Twenty-two
Node scenarios cover manual saving/loading, Revert, Undo/Redo, screenshot reference and widget checks.
Live browser checks verified draft discard on reload, Undo/Redo, Revert, explicit Save surviving reload,
select-then-Load behavior, screenshot reconstruction and open-widget checks, with no browser errors.
The user's running native app was not restarted or its real profile migrated during this repair;
native reopening remains a separate verification.

Live log includes recorded history as well as new events. Earlier dates are displayed beside the time;
event labels distinguish scheduled reminders from model responses. A `stretch_nudge` comes from the
existing shelf watcher called at autonomy startup: its canned wording does not demonstrate fresh model
inference. Its posture record freshness is a separate runtime issue; the controller does not alter it.

Pipeline pairs tool starts and terminal results by operation ID. Unknown outcomes remain neutral
and count as finished steps; they are not displayed as successful. A revised answer whose audit
is INCOMPLETE or ERROR retains that status instead of appearing as a successful correction.
Witness read attempts show attempted/returned/refused/failed counts; output is not labelled successful
verification. The October 5 follow-through passes 24 isolated Pipeline scenarios, including refusals.
