<!-- @nova: Claude's start on Nova's live voice and 2D body: the plan, the proposed body-event interface for the console, and a read-only readiness check. -->
# Voice and body: plan started
**Summary:** Cole asked for Nova's voice to come together, with a live plan connecting it to the console and the 2D
VTuber model Codex is building. The base is the existing `general_tools/voice_gateway` (built 2026-08-02, never run
with audio). The plan is a Claude Doc, "Nova Voice & Body - Live Plan", owned by Cole. Its key content is below for
anyone who can't open it.

## Plan in short
- **Loop:** mic, Silero VAD, Moonshine Streaming (Small or Medium; upgrade from `moonshine/base`), nova_chat WebSocket
  with `register=voice`, sentence-committer, Chatterbox-Turbo (MIT, clones from a ~10 s clip), speakers.
- **Latency:** the main problem is hold-back streaming (`nova.py` `_HOLD`, since 08-03). Chat gets nothing until the
  witness clears, so the gateway can only speak the finished reply. Planned fix (step 4): speak casual sentences as
  they are written and hold claim-bearing sentences for the witness.
- **Body interface (proposed, Codex to confirm):** a loopback-only WebSocket owned by the console. The gateway sends
  four events:
  - `state` {listening|thinking|speaking|idle}
  - `mouth` {open 0..1}, about 30 Hz, from the playing audio's loudness
  - `expression` {name, intensity, hold_ms}
  - `caption` {text}

  Body mode drives VTube Studio with `InjectParameterDataRequest` (values resent at least once a second) and
  `ExpressionActivationRequest`/`HotkeyTriggerRequest` on ws://localhost:8001. The VTS plugin API has no audio lip-sync.
- **Owners:**
  - Codex: step 3 (thread `register` from the WS message into `stream_response`, per `voice_gateway/server_patch.md`),
    step 10 (console body mode) and step 11 (the rigged Live2D model).
  - Claude: steps 1-2 and 4-9.
  - Cole with Nova: step 6, the voice audition.
- **Licensing:** every voice model picked is MIT or Apache-2.0. XTTS-v2, Fish Audio S2 and VibeVoice are ruled out.
  Live2D is fine for Cole's own use. A sold product above 10M yen a year needs Live2D's SDK release license, so the
  product path is our own Cubism renderer.

## Did
- Added `general_tools/voice_gateway/check_voice_ready.py` (3d88aea4) and `VOICE_CHECK.cmd` (6367409b). Both are
  read-only. They write `voice_check.log` with:
  - free GPU memory per card
  - installed voice packages
  - torch CUDA
  - audio devices
  - whether ports 8765, 8080, 8081, 8001 and 6080 answer

  Run it while Nova is up; anyone on Windows may run it. The log is a placeholder until then.
- Gateway committer tests: 9/9 pass. Room #44 has the interface proposal.

## Open / next
- Step 1 needs the readiness check run on Windows. Step 2 (text link smoke) needs `pip install websockets` and a
  running Nova. It sends a real message into her chat, so run it with Cole watching.
