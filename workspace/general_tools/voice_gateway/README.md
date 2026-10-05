<!-- @nova: Describe the voice gateway: first-stage delivered-text speech, its event contract, verified tests and the remaining audio work. -->
_Last updated: 2026-10-06 03:16:39_
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
Nova inputs, and closes the audio worker. It does not issue a global generation stop or stop Nova.
Closing the widget or its popout does not end the shared call.

Microphone and spoken-output mute are separate. Expand **Settings & tests** to find compatible
inputs/outputs, apply devices while stopped, meter six seconds of microphone audio or play a short
speaker test. **Stop test** cancels an audio test. Tests work while Nova is off; a call needs Nova on.
Page load and status polling never record or play audio, and device discovery is explicit.

The main call surface distinguishes listening, **Hearing you**, **Finishing your turn**,
**Recognizing speech**, waiting/thinking and output status. It displays the actual configured pause
allowance when supplied by the backend. Independent microphone/speaker indicators and explicit muted
warnings reflect acknowledged status; unknown status is labelled unknown, and a muted speaker cannot
appear as Speaking. A submitted mute command alone is not confirmation.
Delayed or suppressed replies remain visible. **Latest words** contains the last recognized text
and delivered caption with its audit status. **Delivery & playback details** shows request/message/run
IDs, submission/completion outcomes, selected output and available timing fields. Preparing audio,
a playback-process launch and a successful playback API submission are different observations;
none proves that a person heard sound. Windows system speech is a labelled temporary baseline,
not Nova's final cast voice. If no `windows_voice` name is configured, Windows speech prefers an
installed English female voice, falling back to the system default only when none is available.

## Delivery contract (foundation and committed-segment continuation, October 5)

- **Speaks delivered audited segments or compatible final replies to the gateway's own requests.** Every utterance carries a fresh `request_id`. Nova Chat echoes it on `user_message` and tracks it through response start/context/end or `request_end`. A reply is spoken only when `delivery == "delivered"` and its bound input identities contain our acknowledged voice request (`speak_scope="mine"`). `"replies"` is opt-in and still requires a `reply_to`.
- **Never spoken, in any scope:** `error` ends (they carry a diagnostic), `empty`, `suppressed`, `cancelled` and `unsolicited` promotions (these need their own policy later). An end without a `delivery` field comes from an old server: it is silent and logs one "restart/update Nova Chat" diagnostic. `request_end` and rejections are cleared by `request_id` alone, even without an echo.
- **Identity is checked, not assumed.** A reply counts as ours only if its pending `request_id` and acknowledged `reply_to` form an exact pair, and its message/run match a prior `message_start` or validated `message_context`. Combined replies carry ordered, aligned `request_ids`/`reply_to_ids` plus `input_revision`. Foreign typed inputs may have null client IDs; they can never claim a local voice request. Applied context updates preserve the existing run and append identities. A gateway joining a running typed turn can first bind from a context update containing its already-acknowledged voice input. Final frames cannot self-bind or expand that context. Committed segments use an exact previously validated revision snapshot; they never self-bind. Their explicit audit turn/revision must match. A 1-based `segment_index` advances once, duplicates are ignored, and gaps are diagnosed. Pending bindings stay open until terminal closure. A compatible unsegmented final still selects the newest eligible local input.
- **Delivered is not approved.** The audit `{status, reason, source}` rides on every caption and body event. A missing audit is `NOT_RUN`, never PASS. `audit_gate="delivered"` (default) speaks any delivered reply with its status attached. `audit_gate="pass_only"` speaks only an explicit PASS; NOT_RUN, CONCERN, INCOMPLETE and ERROR stay silent.
- **No token speech.** `speak_from="stream"` is ignored with a warning. `message_segment` carries committed content plus explicit audit metadata under one stable message/run/turn identity. Each segment can queue before work ends. The final remainder is another segment; terminal `message_end.segment_count` prevents the aggregate being spoken again. The delivered audit policy still permits explicitly unapproved content by default; it does not manufacture PASS.
- **Follow-up input continues work.** A new utterance retains already committed queued speech and never issues Stop for Nova's active work. Full-duplex barge-in cuts only the current audio unit and pauses pending committed units while hearing/recognizing; completed recognition or return to listening resumes them. Explicit End/Stop/output mute still flushes the queue. Each completed utterance sends another ordered input. Body-owned `ConversationTurns`/`ActiveTurn` append follow-ups at natural model/tool boundaries, preserve the original request and completed observations, and bind each delivered segment to the input revision it actually used. Later input cannot silently retract delivered text; the following segment must reconcile any correction. Input arriving after final admission belongs to the next turn. This does not inject text into an already-running local HTTP model request.
- **Explicit scoped interruption.** End call or worker shutdown retires local output and requests Stop for all remaining owned pending inputs, including audio-ineligible earlier ones. The server matches only an owned request on the same socket. Each request waits at most two seconds for final `stopped` with that exact ID and `matched=true`; `stop_pending`, a submitted frame or a timeout is not proof of completed cancellation. Unconfirmed cancellation is diagnosed without global Stop. Late replies remain silent. Already-computing synthesis may finish, but its audio must not start after cancellation. Closing the player flushes queued work and rejects late output.
- **Half duplex by default.** A human turn already hearing, finishing its pause or transcribing holds queued future speech until recognition completes or resets, including recognition failure. That held queue does not close its capture gate. Once output actually starts, the mic drops newly captured audio while she speaks, plus a 400 ms tail. Every buffered or queued frame from before the gate closed is discarded, and no utterance is ever spliced across her turn. The fake-microphone regressions discard both queued echo and a transcription that completes after its capture generation or gate became invalid. Physical echo, device buffering and the appropriate tail length still need hardware testing. Use `duplex="full"` only with headphones or echo cancellation.
- **Recognition hygiene.** Silero consumes 512-sample frames at 16 kHz. Brief noises below the minimum voiced duration are ignored; onset audio is buffered, trailing silence is trimmed, and decoder errors produce a visible diagnostic while listening continues. Missing local assets stop readiness instead of silently downloading or substituting energy detection. The default trailing-pause allowance is 2,000 ms, with explicit overrides preserved. Audio continuing during decoding is collected into the bounded turn; a superseded partial result is withheld and combined audio is decoded after quiet. The 60-second boundary remains. This reduces premature fragments in fixtures; it does not promise recognition quality or a two-second reply.
- **What is never read aloud:** tool markers (`[`tool` resulted in N bytes.]`), code blocks, raw URLs ("a link") and markdown.
- **Body events v1** (`body.py`): `state` (idle/hearing/finishing_turn/transcribing/waiting/thinking/speaking), `turn`, `message`, `speech`, `caption`, `interrupt` and `diagnostic`. Sinks are `none`, `stdout`, or `jsonl` (`logs/voice/body_events.jsonl`). The trace stays honest:
  - `message` records policy and queueing only (`eligible`, `queued_units`); `phase="segment"` includes `segment_index`, while terminal `phase="end"` includes `segment_count`. Unique audio unit indices continue across segments.
  - `speech` goes `requested`, then `start`, then `end`, with outcome `played`, `completed`, `cut`, `skipped`, `no_audio` or `error`. NullTTS reports `no_audio`; subprocess playback reports `completed` with `clock="process"`, without claiming measured sound.
  - A `caption` follows a successful playback API submission (`clock="playback"`); that timestamp is not a measurement of audible output. A legacy backend without the callback uses `clock="requested"`. NullTTS and the process-only fallback do not claim an audio start.
- **A slow accepted reply is retained.** After `request_timeout_s` (default 300 seconds), the current acknowledged eligible request emits one delayed warning. Any acknowledged input bound to an open response retains exact correlation until terminal closure, including an earlier revision retired for legacy final speech. This lets a late, already-committed segment match its original evidence. Explicit cancellation/socket closure still invalidates it. Unacknowledged or unbound retired requests expire. `run()` supervises the mic and socket so a failure in either shuts down the loop.
- **Controller diagnostics.** `/api/voice/status` includes `last_turn`, `last_playback` and a bounded `recent_events` history. Turn phases include sent, acknowledged, queued, started, delivered segment, delayed and terminal states. Playback phases are requested/start/end, with backend/output and measured timing fields when available. Unrelated broadcasts cannot overwrite the current turn. These fields survive a stopped call until another call starts.

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

Committed-segment continuation has fake-provider/event/player coverage: segments queue before final,
exact validated earlier revisions remain usable, malformed identities/audits cannot self-bind, duplicate
and missing segments do not replay the aggregate, and interrupted queued audio survives until resumed.
Close/Stop invalidate held units so late playback cannot begin. Production-renderer fixtures show one
growing reply with an in-progress audit label and a terminal label, without a second aggregate bubble.
The current gateway suite ran **107 tests: 106 passed, one existing skip**. Twenty-nine related frontend
checks pass, including three segment/history cases; two temporary transcript tests preserve audited
part metadata. These changes have no new live microphone, model-latency or audibility proof.

Body work ownership now serializes chat and autonomous work. Human input is attended at natural
completed model/tool steps, with phase fallbacks, then the original task resumes with completed
receipts and delivered interaction context. Nested human turns do not recursively enter autonomous
attention. Headless human attention uses the same body conversation formatter and segmented delivery
with captured input-sequence coverage; autonomous reflect/decide/execute prompts remain separate.
Follow-ups do not reset total work/audit budgets. This is fixture-tested between-call continuation,
not cancellation of in-flight inference, a unified permanent thought stream or a real-time guarantee.

The subsequent pause/continuation slice has isolated evidence: the gateway suite ran **96 tests**
with **95 passed and one existing skip**, including 14 new continuation/correlation cases and nine
endpointing cases. Controller tests passed 31/31 and the separate Voice UI suite passed 21/21. Fake
capture/playback verifies ordered follow-ups, mixed typed/voice aliases, audio-only barge-in and
explicit End call cleanup. These are not fresh microphone, model-latency, full relocated-body or
natural-conversation results; the core continuation integration is separately reviewed/tested.

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
The 21:02 repeat after the cache changes delivered at 94.812 seconds and began playback at 96.190
seconds, with two `played` units. Audit remained INCOMPLETE and flagged an unsupported connection
claim. It showed no meaningful speedup; different history and cold reload prevent a controlled cache
comparison. Human confirmation applies only to the first greeting. A third warm test was not run
because Cole was using the app, and the temporary provider capture was closed.

A separate public 11-second human-speech clip produced 0/22 word errors for both recognizers. Whisper
decoded in 6.529 seconds; Moonshine in 0.822 seconds. One clean clip is not broad accuracy evidence or a
Cole-microphone test. See the [dated repair validation](../../Orient/Architecture/evidence/2026-10-05-voice-repair-validation.md)
for receipts, the measured memory/prefill/audit delays and the file-decoder workaround. Natural human
conversation, physical echo, native avatar timing and a suitable final voice remain unverified.
Human audibility is confirmed for the first greeting only; the new female placeholder is not yet approved.
A separate final operator check observed actual Whisper microphone transcription and confirmed End
call cancelled its pending request; that transcription was not accuracy-scored. Subsequent user/client
activity changed call state, so the check is not a claim that the call remains stopped or muted.

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
