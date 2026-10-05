<!-- @nova: Describe the voice gateway: first-stage delivered-text speech, its event contract, verified tests and the remaining audio work. -->
# voice_gateway — Cole's microphone to Nova

This is the pipe that lets Cole **talk** to Nova and **hear** her back. It starts on the desktop; a watch → phone → tunnel path comes later and reuses this gateway. It is a **comms tool, not a faculty**. Delete this folder and Nova is unchanged; she just has no mic. It speaks nova_chat's WebSocket protocol from the outside, exactly like the browser UI.

```
   mic ─▶ VAD (Silero) ─▶ STT (Moonshine) ─▶ nova_chat WS ──▶ Nova (her full mind + witness)
                                                  ▲                       │
   speakers ◀─ TTS ◀─ speech player ◀─ session ◀──┴── delivered reply + audit status
                             │
                             └─▶ body events (state, captions, speech start/end) for an avatar
```

## First stage (built 2026-10-05; contract agreed with Codex in the Collaboration room #55–#63)

- **Speaks only delivered final text, and only in reply to the gateway's own request.** Every utterance carries a fresh `request_id`. Nova Chat echoes it on `user_message`, `message_start`, `message_end` and `request_end`. A reply is spoken only when `delivery == "delivered"` and the `request_id` is ours (`speak_scope="mine"`). `"replies"` is opt-in and still requires a `reply_to`.
- **Never spoken, in any scope:** `error` ends (they carry a diagnostic), `empty`, `suppressed`, `cancelled` and `unsolicited` promotions (these need their own policy later). An end without a `delivery` field comes from an old server: it is silent and logs one "restart/update Nova Chat" diagnostic. `request_end` and rejections are cleared by `request_id` alone, even without an echo.
- **Identity is checked, not assumed** (Codex review #70). A reply counts as ours only if its `request_id` is pending, its `reply_to` equals the server id from the `user_message` echo, and its `message_id`/`run_id` match the `message_start` seen for that request. A missing or mismatched field means silence.
- **Delivered is not approved.** The audit `{status, reason, source}` rides on every caption and body event. A missing audit is `NOT_RUN`, never PASS. `audit_gate="delivered"` (default) speaks any delivered reply with its status attached. `audit_gate="pass_only"` speaks only an explicit PASS; NOT_RUN, CONCERN, INCOMPLETE and ERROR stay silent.
- **No pre-audit speech.** `speak_from="stream"` is ignored with a warning. Tokens are never spoken.
- **Interruption covers generations, not just audio.** A new utterance, a voice barge-in (full duplex) or the server's `stopped`/`stop_pending` flushes queued units and stops the current one. It also retires every earlier request, so their late finals close quietly and are never spoken. A unit cut while it is still being synthesized never starts playing: each backend checks cancellation before playback. Closing the player also stops active playback, flushes the queue and rejects late work. Synthesis already computing may finish after cancellation; its resulting audio remains suppressed.
- **Half duplex by default.** The mic drops audio at capture while she speaks, plus a 400 ms tail. Every buffered or queued frame from before the gate closed is discarded, and no utterance is ever spliced across her turn. The fake-microphone regression confirms that captured echo queued during a slow transcription is discarded (Codex review #72). Physical echo, device buffering and the appropriate tail length still need hardware testing. Use `duplex="full"` only with headphones or echo cancellation.
- **What is never read aloud:** tool markers (`[`tool` resulted in N bytes.]`), code blocks, raw URLs ("a link") and markdown.
- **Body events v1** (`body.py`): `state` (idle/waiting/thinking/speaking), `message`, `speech`, `caption`, `interrupt` and `diagnostic`. Sinks are `none`, `stdout`, or `jsonl` (`logs/voice/body_events.jsonl`). The trace stays honest:
  - `message` records policy and queueing only (`eligible`, `queued_units`).
  - `speech` goes `requested`, then `start`, then `end`, with outcome `played`, `completed`, `cut`, `skipped`, `no_audio` or `error`. NullTTS reports `no_audio`; subprocess playback reports `completed` with `clock="process"`, without claiming measured sound.
  - A `caption` follows a successful playback API submission (`clock="playback"`); that timestamp is not a measurement of audible output. A legacy backend without the callback uses `clock="requested"`. NullTTS and the process-only fallback do not claim an audio start.
- **No request waits forever:** a request with no end after `request_timeout_s` (300 s) is closed with a diagnostic. `run()` supervises the mic and the socket: if either ends, the whole loop shuts down and cleans up.

| module | job |
|---|---|
| `nova_link.py` | WebSocket client; `parse_event` maps server frames to `NovaEvent` |
| `turns.py` | `VoiceSession`: pending requests, end classification (`classify()` is the only speech policy), timeouts |
| `speech.py` | `speech_text()` sanitizer; `SpeechPlayer` (ordered, interruptible, audio-clocked captions) |
| `body.py` | v1 body events and sinks |
| `committer.py` | sentence units (2026-10-05 fix: a merged one-word stub no longer swallows the rest into one unit) |
| `stt.py` / `tts.py` | backends; `gate`/`on_speech_start` hooks; every TTS has `stop()` |

## Verified (offline, 2026-10-05, Nova off)

- `test_voice_flow.py`: 35 tests. They cover identity matching (no ack, wrong reply_to, unknown message, wrong run_id, missing request_id), late finals after a new request or a stop, a unit cut during synthesis never playing, a playback trace that separates eligible/queued/played/error, echo captured during a slow transcription never coming back as Cole (with a fake mic and transcriber), every non-delivered end staying silent, the old-schema diagnostic, scopes, the pass-only gate, the NOT_RUN default, request_end/error/timeout cleanup, the half-duplex gate, no stream speech and the sanitizer. Nova Chat's own `ResponseEvents` builder is used as a contract check. Additional shutdown tests cover active/queued work at close, backend cancellation during synthesis and conversion, stop/play races, null output, surfaced playback failures and process-only completion. A close() during playback reports `cut`, not `played`, and a late end after the player has closed becomes a diagnostic instead of crashing the link.
- `test_link_socket.py`: two tests. One is a real WebSocket round-trip against a fake Nova Chat: the request_id is echoed, unrelated frames are ignored, and only the delivered reply is spoken with its audit status. The other checks that a dropped socket stops the mic and cleans up. Needs `websockets`.
- `test_committer.py`: 9/9.

**Not yet verified:** a microphone, real TTS, Chatterbox/Moonshine/Silero installs, VTube Studio, lip-sync amplitude, latency, and a live rung-2 run against Nova Chat. Readiness on 2026-10-04 with Python 3.12.6: websockets, NumPy, Torch and Transformers present; sounddevice, onnxruntime, torchaudio, Chatterbox, Silero VAD and Moonshine absent. `VOICE_CHECK.cmd` regenerates `voice_check.log`.

## The smoke ladder — verify each layer before wiring audio

| # | command | proves | needs |
|---|---------|--------|-------|
| 1 | `python general_tools/voice_gateway/test_voice_flow.py` (+ `test_link_socket.py`, `test_committer.py`) | session, policy, sanitizer, link | nothing (`websockets` for the socket test) |
| 2 | `python general_tools/voice_gateway/gateway.py --smoke-link "hey nova, what's up"` | one request against a **running Nova**; prints body events | `websockets`, Nova Chat with the 2026-10-05 contract |
| 3 | `python general_tools/voice_gateway/gateway.py --smoke-tts "this is my voice test"` | sanitizer → committer → TTS | a TTS backend (or Null logs) |
| 4 | `python general_tools/voice_gateway/gateway.py --run` (with `stt_backend='stdin'`) | the whole loop: type to her, hear her reply | TTS; mic optional |

## Install (tiered — see `requirements.txt`, `fetch_models.cmd`)

1. **Transport**: `websockets` (rung 2).
2. **Voice out**: Chatterbox (`pip install torch chatterbox-tts`, expressive, recommended) **or** llama.cpp TTS (`tts_backend='llamacpp'` plus a TTS gguf).
3. **Mic in**: `pip install sounddevice numpy onnxruntime useful-moonshine-onnx silero-vad`. Until then, use `stt_backend='stdin'`.

## Config

`config.py` holds every knob; override via `_admin/voice_gateway.json` or `VOICE_GW_*` env vars.

- `register`: `voice`, `voice_fast` or `text`; validated per request by the server.
- `speak_scope`: `mine` or `replies`.
- `audit_gate`: `delivered` or `pass_only`.
- `request_timeout_s`
- `duplex` and `half_duplex_tail_ms`
- `barge_in`: full duplex only.
- `body_sink` and `body_log_path`
- `tts_backend`, `tts_reference_wav`, `stt_backend`

`server_patch.md` is a superseded 2026-10-04 sketch; the live contract is `nova_chat/response_events.py`.

## What needs Cole

- **A voice to pick.** This is the audition round: candidate Chatterbox reference clips, chosen with Nova. It is a casting decision, not code.
- **The audio stack.** Install torch, Chatterbox and Moonshine plus a mic and speakers, then walk the smoke ladder on real hardware. Only when he says it's OK, since GPU work competes with games.
