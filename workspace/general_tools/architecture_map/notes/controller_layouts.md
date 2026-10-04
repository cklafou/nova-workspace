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

The small Layout selector switches named arrangements. Its adjacent management control creates an empty
layout, duplicates the current one, renames it or deletes it while keeping at least one. Drag widget tabs
to reorder, stack or split; drag dividers to resize; the popout control opens a separate window. Changes
save automatically in the current browser/app profile. A failure to save is shown as Not saved.

Storage is `nova.controller.layouts.v2` in that profile's local storage. The previous mode selection and
saved Together/Observe/Focus layouts migrate into editable named layouts; the old keys remain intact.
The last twenty deleted/reset/unrestorable layouts are retained as recovery records in the collection.
Saved popouts return to the main dock on restore. Switching arrangements closes their old popouts before
loading the next layout. A native Nova Chat window and a separate browser have independent layout profiles.

Live log includes recorded history as well as new events. Earlier dates are displayed beside the time;
event labels distinguish scheduled reminders from model responses. A `stretch_nudge` comes from the
existing shelf watcher called at autonomy startup: its canned wording does not demonstrate fresh model
inference. Its posture record freshness is a separate runtime issue; the controller does not alter it.
