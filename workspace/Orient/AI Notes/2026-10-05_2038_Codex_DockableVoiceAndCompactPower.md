<!-- @nova: Record the separate Voice widget, compact Conversation power control and isolated frontend validation. -->
# Dockable Voice and compact power
**Summary:** Voice is now its own dockable widget, as Cole requested. Conversation retains a small power button under the composer beside Users and Options; saved layouts retain manual-only semantics.

## Did
- `workspace/general_tools/nova_chat/static/voice.js` and `voice.css`: explicit `mountNovaVoice(host)`, independent call interface with Call Nova / End call, mic and output mute, actual listening/hearing/recognizing/waiting/thinking/playback/error states. Settings & tests and Latest words are secondary collapsed sections. Delayed replies, suppressed speech and correlated request/message/run/output diagnostics use the backend's new fields.
- `static/workspace.js`: register Voice through the same dock/menu/library/popout paths as other widgets; do not insert it into existing saved layouts. `static/index.html`: load the module before the workspace registry, add composer controls hook and bump changed assets.
- `static/conversation-power.js` and `control.css`: compact accessible 36px power icon with Start/Stop Nova label, live status tooltip and existing real lifecycle/reconnect/draft handling. `workspace.css`: keep power reachable after closing the active conversation.
- `static/index.html`: witness read-attempt labels/counts no longer claim a refused tool successfully checked evidence. Event key remains compatible.
- Parent owns `collaboration.js/css` scroll-to-latest and chat-only composer visibility, plus backend/Orient integration.

## Why
The user corrected the earlier embedded Conversation voice design. A call needs its own movable/popout surface; opening or closing that surface must not implicitly start or stop shared audio. Playback request/preparation and process launch are distinguished from playback API submission, without fake audio-level animations or a claim that sound was actually heard.

## Verified
- `node workspace/general_tools/nova_chat/tests/test_voice_ui.cjs`:16 fake DOM/API tests pass, including explicit actions, muted/test guards, status races, delayed/suppressed replies, playback failure and stale-turn handling, and UI remount without audio actions.
- `node workspace/general_tools/nova_chat/tests/test_conversation_power.cjs`:8 lifecycle/draft/control scenarios pass.
- `node workspace/general_tools/nova_chat/tests/test_pipeline_ui.cjs`:24 scenarios pass, including three refused witness reads with zero returned output.
- `node workspace/general_tools/nova_chat/tests/test_layout_save.cjs`:22 scenarios pass, including real Voice registry/mount ordering, focusing an existing Voice popout, and explicit-save-only behavior. Existing layout/history/recovery cases remain passing.
- Changed standalone JavaScript parses. No Nova/model/audio/service controls, native window actions, personal-state writes or saved-layout mutation performed by this slice.

## Open / next
- Parent owns hidden-browser visual integration and actual audio/runtime validation. Unit/fixture checks do not prove a natural spoken conversation or measured audibility.
- Source released. Parent should document Voice as a separate widget, compact Conversation power, manual layouts, secondary device/testing controls and new honest read-attempt presentation in the appropriate Orient source sections.
- Read companion notes `2026-10-05_2036_Codex_VoiceReplyPlaybackRepair.md` and `2026-10-05_2037_Codex_ProviderDiagnosticsAndReadAttempts.md` for the backend and diagnostics changes. No further witness prompt-policy tuning was introduced.
