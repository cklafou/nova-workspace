<!-- @nova: Describe the voice gateway: first-stage delivered-text speech, its event contract, verified tests and the remaining audio work. -->
_Last updated: 2026-10-05 20:33:23_
# voice_gateway — Cole's microphone to Nova

This is the pipe that lets Cole **talk** to Nova and **hear** her back. It starts on the desktop; a watch → phone → tunnel path comes later and reuses this gateway. It is a **comms tool, not a faculty**. Delete this folder and Nova is unchanged; she just has no mic. It speaks nova_chat's WebSocket protocol from the outside, exactly like the browser UI.

```
   mic ─▶ VAD (Silero) ─▶ STT (Whisper turbo) ─▶ nova_chat WS ──▶ Nova (her full mind + witness)
                                                  ▲                       │
   speakers ◀─ TTS ◀─ speech player ◀─ session ◀──┴── delivered reply + audit status
                             │
                             └─▶ body events (state, captions, speech start/end) for an avatar
```

## Use it in Nova Chat

Open **Widgets → Voice**. Voice is a separate dockable widget: move, resize or pop it out like
other widgets. Existing saved layouts are left alone; use **Save layout** to retain an arrangement.
Start Nova with the small power button below Conversation's composer, then choose **Call Nova** in
Voice. **End call** immediately retires local speech, requests cancellation of this call's pending
Nova request, and closes the audio worker. It does not issue a global generation stop or stop Nova.
Closing the widget or its popout does not end the shared call.

Microphone and spoken-output mute are separate. Expand **Settings & tests** to find compatible
inputs/outputs, apply devices while stopped, meter six seconds of microphone audio or play a short
speaker test. **Stop test** cancels an audio test. Tests work while Nova is off; a call needs Nova on.
Page load and status polling never record or play audio, and device discovery is explicit.

The main call surface reports listening, recognizing speech, waiting/thinking and output status.
Delayed or suppressed replies remain visible. **Latest words** contains the last recognized text
and delivered caption with its audit status. **Delivery & playback details** shows request/message/run
IDs, submission/completion outcomes, selected output and available timing fields. Preparing audio,
a playback-process launch and a successful playback API submission are different observations;
none proves that a person heard sound. Windows system speech is a labelled temporary baseline,
not Nova's final cast voice. If no `windows_voice` name is configured, Windows speech prefers an
installed English female voice, falling back to the system default only when none is available.

## First stage (built 2026-10-05; contract agreed with Codex in the Collaboration room #55–#63)

- **Speaks only delivered final text, and only in reply to the gateway's own request.** Every utterance carries a fresh `request_id`. Nova Chat echoes it on `user_message`, `message_start`, `message_end` and `request_end`. A reply is spoken only when `delivery == "delivered"` and the `request_id` is ours (`speak_scope="mine"`). `"replies"` is opt-in and still requires a `reply_to`.
- **Never spoken, in any scope:** `error` ends (they carry a diagnostic), `empty`, `suppressed`, `cancelled` and `unsolicited` promotions (these need their own policy later). An end without a `delivery` field comes from an old server: it is silent and logs one "restart/update Nova Chat" diagnostic. `request_end` and rejections are cleared by `request_id` alone, even without an echo.
- **Identity is checked, not assumed** (Codex review #70). A reply counts as ours only if its `request_id` is pending, its `reply_to` equals the server id from the `user_message` echo, and its `message_id`/`run_id` match the `message_start` seen for that request. A missing or mismatched field means silence.
- **Delivered is not approved.** The audit `{status, reason, source}` rides on every caption and body event. A missing audit is `NOT_RUN`, never PASS. `audit_gate="delivered"` (default) speaks any delivered reply with its status attached. `audit_gate="pass_only"` speaks only an explicit PASS; NOT_RUN, CONCERN, INCOMPLETE and ERROR stay silent.
- **No pre-audit speech.** `speak_from="stream"` is ignored with a warning. Tokens are never spoken.
- **Scoped interruption.** End call, a new utterance or full-duplex barge-in flushes queued speech, stops current output and retires earlier requests immediately. The worker sends `stop` with its own `request_id`; the server matches only an owned request on the same socket. The client waits at most two seconds for final `stopped` with that exact ID and `matched=true`; `stop_pending`, a submitted frame or a timeout is not proof of completed cancellation. Unconfirmed cancellation is diagnosed, without falling back to global Stop. Late finals from retired requests remain silent. Backend synthesis already computing may finish after cancellation, but its resulting audio must not begin playing. Closing the player also flushes queued work and rejects late output.
- **Half duplex by default.** The mic drops audio at capture while she speaks, plus a 400 ms tail. Every buffered or queued frame from before the gate closed is discarded, and no utterance is ever spliced across her turn. The fake-microphone regressions discard both queued echo and a transcription that completes after its capture generation or gate became invalid. Physical echo, device buffering and the appropriate tail length still need hardware testing. Use `duplex="full"` only with headphones or echo cancellation.
- **Recognition hygiene.** Silero consumes 512-sample frames at 16 kHz. Brief noises below the minimum voiced duration are ignored; onset audio is buffered, trailing silence is trimmed, and decoder errors produce a visible diagnostic while listening continues. Missing local assets stop readiness instead of silently downloading or substituting energy detection.
- **What is never read aloud:** tool markers (`[`tool` resulted in N bytes.]`), code blocks, raw URLs ("a link") and markdown.
- **Body events v1** (`body.py`): `state` (idle/transcribing/waiting/thinking/speaking), `turn`, `message`, `speech`, `caption`, `interrupt` and `diagnostic`. Sinks are `none`, `stdout`, or `jsonl` (`logs/voice/body_events.jsonl`). The trace stays honest:
  - `message` records policy and queueing only (`eligible`, `queued_units`).
  - `speech` goes `requested`, then `start`, then `end`, with outcome `played`, `completed`, `cut`, `skipped`, `no_audio` or `error`. NullTTS reports `no_audio`; subprocess playback reports `completed` with `clock="process"`, without claiming measured sound.
  - A `caption` follows a successful playback API submission (`clock="playback"`); that timestamp is not a measurement of audible output. A legacy backend without the callback uses `clock="requested"`. NullTTS and the process-only fallback do not claim an audio start.
- **A slow accepted reply is retained.** After `request_timeout_s` (default 300 seconds), the current acknowledged eligible request emits one delayed warning and keeps its exact reply correlation. It remains eligible until completion, explicit stop/new input or socket closure. Unacknowledged and already retired requests expire; only one current request can remain speech-eligible. `run()` supervises the mic and socket so a failure in either shuts down the loop.
- **Controller diagnostics.** `/api/voice/status` includes `last_turn`, `last_playback` and a bounded `recent_events` history. Turn phases include sent, acknowledged, queued, started, delayed and terminal states. Playback phases are requested/start/end, with backend/output and measured timing fields when available. Unrelated broadcasts cannot overwrite the current turn. These fields survive a stopped call until another call starts.

| module | job |
|---|---|
| `nova_link.py` | WebSocket client; `parse_event` maps server frames to `NovaEvent` |
| `turns.py` | `VoiceSession`: pending requests, end classification (`classify()` is the only speech policy), timeouts |
| `speech.py` | `speech_text()` sanitizer; `SpeechPlayer` (ordered, interruptible, audio-clocked captions) |
| `body.py` | v1 body events and sinks |
| `committer.py` | sentence units (2026-10-05 fix: a merged one-word stub no longer swallows the rest into one unit) |
| `stt.py` / `tts.py` | recognition/playback, capture and post-decode gating, bounded speech segments |
| `windows_tts.py` | cancellable Windows system speech through the selected output |
| `control_worker.py` | explicit session/device tests, progress and control pipe |
| `setup_windows.py` | isolated CPU dependencies and checksummed local speech assets |

## Verification and remaining evidence

At the October 5 repair checkpoint, **73 gateway tests**, **30 controller tests** and **70 frontend
scenarios** pass. The frontend total covers Voice (16), Conversation power (8), Pipeline (24) and
manual layouts (22); it is not 70 audio tests. Gateway fixtures cover exact reply identity, delivered-only
speech, late replies after the 300-second threshold, new-input/stop suppression, acknowledgement of
request-scoped cancellation, queue/capture gates, synthesis cancellation, output failures and bounded
diagnostics. A local mock WebSocket is transport evidence; it does not call a model or microphone.

Hidden-browser checks verified the separate Voice widget, compact power control, widget checkmarks
and Collaboration's scroll-to-latest behavior without console errors. Earlier native microphone
metering and Windows system-voice playback completed; generated test speech was transcribed by the
then-selected Moonshine backend. Those are dated component checks, not proof of current English
recognition quality or a complete spoken exchange.

The earlier live `--smoke-link` delivered correlated IDs and audit events after **312.804 seconds**, but
answered an older topic instead of the greeting and had audit INCOMPLETE. It used NullTTS and produced
no audio. The old microphone sweeper would discard correlation at 300 seconds; the silent smoke did not
exercise that sweeper. The repair now retains an acknowledged slow reply and runs both smoke modes
with sweeping. This is a demonstrated source hazard, not proof of every earlier silent-turn cause.
See `Temp/voice-validation/live-link-result.json` and the dated
`Orient/Architecture/evidence/2026-10-05-voice-continuity-validation.md`.

The local **Whisper large-v3-turbo, CPU int8, English** recognizer is installed and selected by default.
The later 20:48 `voice_fast` test used real Windows TTS with the microphone off: a relevant greeting
was delivered in 94.844 seconds, first playback began at 96.246 seconds, and both speech units ended
`played`. It produced two sentences rather than the requested one; audit remained INCOMPLETE. This
proves the tested reply/output path, not low-latency conversation. Cole separately confirmed hearing
that greeting and disliked the temporary voice. Subsequent synthesis selected Microsoft Zira Desktop
as the female placeholder; that synthesis receipt is not human approval or a final casting choice.

A separate public 11-second human-speech clip produced 0/22 word errors for both recognizers. Whisper
decoded in 6.529 seconds; Moonshine in 0.822 seconds. One clean clip is not broad accuracy evidence or a
Cole-microphone test. See the [dated repair validation](../../Orient/Architecture/evidence/2026-10-05-voice-repair-validation.md)
for receipts, the measured memory/prefill/audit delays and the file-decoder workaround. Natural human
conversation, physical echo, native avatar timing and a suitable final voice remain unverified.
Human audibility is confirmed for this greeting only; the new female placeholder is not yet approved.

## The smoke ladder — verify each layer before wiring audio

| # | command | proves | needs |
|---|---------|--------|-------|
| 1 | `python general_tools/voice_gateway/test_voice_flow.py` (+ `test_link_socket.py`, `test_committer.py`) | session, policy, sanitizer, link | nothing (`websockets` for the socket test) |
| 2 | `python general_tools/voice_gateway/gateway.py --smoke-link "hey nova, what's up"` | one correlated request against running Nova, with delay sweeping; deliberately silent | `websockets`, current Nova Chat |
| 3 | `python general_tools/voice_gateway/gateway.py --smoke-tts "this is my voice test"` | sanitizer → committer → configured TTS; NullTTS remains no audio | explicit real TTS for an audio check |
| 4 | `python general_tools/voice_gateway/gateway.py --smoke-audio "hey nova, what's up"` | correlated final reply through real TTS with delay sweeping; refuses NullTTS | running Nova, prepared environment, explicit output |
| 5 | `python general_tools/voice_gateway/gateway.py --run` | microphone → recognition → Nova → output; use `stt_backend='stdin'` for a typed-input variant | selected local recognizer/VAD assets and real TTS |

Run these commands from `workspace`; full Nova/audio checks are explicit actions, never startup probes.

## Install the Windows baseline

From a Python 3.12 shell, run `python general_tools/voice_gateway/setup_windows.py`. This creates the
local `.venv`, installs `requirements-windows.lock.txt` and checksums pinned Whisper/Silero/Moonshine assets.
It does not start Nova or open audio devices. Use `--assets-only` to repair assets in an existing env.
The environment is excluded from Git, sync, code audits, context and source backups; the setup script
and lockfile reproduce it. The default recognizer uses faster-whisper/CTranslate2 on CPU with int8
compute and `speech_language="en"`. It requires no Torch, Chatterbox or GPU allocation. Moonshine
remains an explicit optional recognizer; a missing selected backend does not silently fall back.

Nova Chat automatically uses that environment. Its supervised Windows worker selects Windows system
speech for `tts_backend="auto"`. CLI gateway smoke commands instead need an explicit
`VOICE_GW_TTS_BACKEND=windows` override and the environment's Python. Chatterbox/llama.cpp remain optional
backends with separate dependencies and validation; neither is required for this baseline.

## Config

`config.py` holds every knob; override via `_admin/voice_gateway.json` or `VOICE_GW_*` env vars.

- `register`: defaults to `voice_fast`; `voice` and `text` remain explicit alternatives. With
  `voice_fast_thinking_off` enabled, only the first model loop requests thinking off; later tool loops
  keep normal reasoning. Choose `voice` for the ordinary thinking-enabled voice path. The witness
  still audits final delivery. This setting is not an utterance classifier or a latency guarantee.
- `speak_scope`: `mine` or `replies`.
- `audit_gate`: `delivered` or `pass_only`.
- `request_timeout_s`: delay threshold for the current acknowledged request; expiry for unacknowledged/retired requests.
- `duplex` and `half_duplex_tail_ms`
- `barge_in`: full duplex only.
- `body_sink` and `body_log_path`
- `tts_backend`, `windows_voice`, `tts_reference_wav`, `stt_backend`
- `whisper_model` (`large-v3-turbo`), `speech_language` (`en`), `whisper_cpu_threads` (8)
- `min_speech_ms` (192), `pre_roll_ms` (288), `speech_tail_ms` (192), `silence_ms` (700)

`server_patch.md` is a superseded 2026-10-04 sketch; the live contract is `nova_chat/response_events.py`.

## What needs Cole

- **A voice to pick.** This is the audition round: candidate Chatterbox reference clips, chosen with Nova. It is a casting decision, not code.
- **Human check.** Confirm the intended headphones/speakers and try a short live spoken exchange. Native avatar timing and a custom expressive voice still need their own validation.
