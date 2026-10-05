<!-- @nova: Record truthful voice turn-phase and confirmed mute UI feedback with isolated regression evidence. -->
# Voice turn and mute status
**Summary:** The Voice widget now makes microphone/output mute explicit and distinguishes the backend's pause, recognition and waiting states. This is a source/fixture update, not a new live conversation pass.

## Did
- `workspace/general_tools/nova_chat/static/voice.js`: show `finishing_turn` as “Finishing your turn” between hearing and recognition; show `settings.end_of_turn_silence_ms` only when the backend supplies a valid positive numeric value. No fake countdown or inferred completion.
- Add prominent independent microphone/speaker state badges, muted warnings and state-plus-action button labels. Use acknowledged status only; a pending mute request is not confirmation. Failed status reads show unknown mute status.
- A muted speaker cannot display Speaking/Preparing output from an old playback event. Current hearing/finishing/recognition states take priority over previous reply playback records before a new utterance receives its request ID.
- `voice.css`: style status/mute feedback accessibly and retain scrolling for small widget sizes. `index.html` cache-busts voice assets to voice-widget-3. Saved layouts and lifecycle routes are unchanged.

## Verified
- `node --test workspace/general_tools/nova_chat/tests/test_voice_ui.cjs`: 21/21 pass, including five new tests for phase/pause truth, both mute channels, acknowledgement/failure/concurrent-client status and stale playback precedence.
- `node --check workspace/general_tools/nova_chat/static/voice.js` and scoped `git diff --check` pass.
- Fakes only: no Nova request, microphone, playback, service start/restart or desktop interaction occurred.

## Handoff
- Root owns worker/controller forwarding of `finishing_turn` and `settings.end_of_turn_silence_ms`, final documentation and reload. Bridge owns STT endpointing/continuation changes. Those backend changes need their own integration evidence.
- Source released. Root must not describe these UI checks as fixing reply latency, voice quality or all pause splitting. Cole's final real conversation test remains separate.
