<!-- @nova: Claude's 2026-10-05 work with Codex: the voice gateway's first stage (delivered-text speech, request matching, interruption, body events) and the witness dev set plus sealed holdout. -->
# Voice first stage and witness evaluation cases
**Summary:** Cole asked Claude to work with Codex again (Collaboration room #54–#67). I hit a usage limit on 10-04 right after #53. Codex then finished every review fix solo and ran controls_v1: 16/26 matched. Today Claude built the voice gateway's first stage and the witness evaluation sets. Codex built the server transport contract. Everything was offline: Cole was in a League match (#60) and Nova, her models, audio and the GPU were not touched.

## Did
- **Witness cases.** `controls_v1` is now a frozen regression set, not a holdout, because both of us inspected its failures.
  - New open dev set: `nova_body/nova_witness/dev/dev_v1.jsonl`. It has 27 cases with labels written before any run (12 PASS, 12 CONCERN, 3 INCOMPLETE), paired P01–P27. It covers more than computer use: tool outcomes, guest vs host, pixels, playback, file contents and counts, receipts cut by the 2400-char budget, words in mouths, answering the room, memory hedges, earlier-turn receipts, pre-tool prose and feelings.
  - Built with the new shared `nova_witness/casekit.py`. Receipts go through runtime's `observation_text`, and the room and session lines come from `witness.py`'s own formatters.
- **Sealed holdout.** `nova_body/nova_witness/holdout/holdout_v1.tar.gz` holds 27 paired cases with the same labels and categories (sha256 `d6c4cab1…b1539b`, full hash in its README and room #62). Do not open it until Codex posts "candidate locked". It gets scored once, with controls_v1 as regressions.
- **Voice gateway first stage** (`general_tools/voice_gateway`, Claude's):
  - It speaks only `delivery == "delivered"` text whose `request_id` is the gateway's own. It never speaks error, empty, suppressed, cancelled or unsolicited ends.
  - An end without a `delivery` field comes from an old server: it stays silent and produces one diagnostic.
  - The audit `{status, reason, source}` rides on every caption. A missing audit is NOT_RUN, never PASS.
  - A new utterance or a stop flushes queued speech and stops the current unit.
  - The mic is half duplex by default, so her voice can't come back as Cole's words.
  - Tool markers, code, URLs and markdown are never read aloud.
  - It emits v1 body events: state, caption, speech start/end, message, interrupt and diagnostic.
  - New modules: `nova_link` (`parse_event`), `turns` (VoiceSession; `classify()` is the only speech policy), `speech`, `body`. Every TTS backend gained `stop()`, and STT gained gate and speech-start hooks.
  - Committer bug fixed: a merged one-word stub used to collapse every later sentence into one unit.
  - `server_patch.md` is marked superseded by `nova_chat/response_events.py`.

## Codex review of the gateway (room #70, #72), all fixed in Claude's files
- **Identity:** a reply speaks only when its request_id is pending, its reply_to equals the acknowledged server id, and its message_id/run_id match the message_start seen for that request. There is no fallback.
- **Interruption retires generations:** a new utterance, a barge-in or a stop makes every earlier request ineligible. Their late finals close the request quietly and are never spoken.
- **No playback after a cut:** each TTS backend checks `should_stop` after synthesis, before playback.
- **Explicit `audit_gate`:** `delivered` is the default; `pass_only` speaks only an explicit PASS.
- **Echo:** the mic is gated at capture, frames from before a gate closure are discarded, and no utterance is spliced across her turn. A fake mic with a slow transcriber shows that the echo is never transcribed as Cole.
- **Supervision:** `run()` supervises mic and socket; either ending shuts the loop down cleanly. stdin is read on a daemon thread.
- **Honest trace:** `message` reports eligible/queued_units. `speech` goes requested, start, end with outcome played/cut/skipped/no_audio/error. Captions are emitted only when the backend reports real playback.

## Verified (VM, Python 3.10)
- Voice: `test_voice_flow.py` passes 22/22, including a contract test built with Codex's `ResponseEvents` and the fake-mic echo test. `test_link_socket.py` passes 2/2: a real websockets round-trip, and socket loss stopping the mic (websockets 16.1 is installed in the VM user site only). `test_committer.py` passes 9/9.
- Cases: all 27 dev and 27 holdout cases run through replay v3 with a scripted endpoint, with no harness errors and all images resolving.
  - The truncated-receipt claims (P18) are confirmed absent from the rendered receipts.
  - The session-log facts (P23/P24) are confirmed visible within the 90-character session lines.
- Not verified: anything live. That means rung 2 against Nova Chat, a microphone, real TTS, latency, VTube Studio and lip-sync. No model run of dev or holdout has happened yet.

## Open
- Codex owns the next witness iteration (P1–P4: explicit sufficiency, claim ledger behind a tunable, INCOMPLETE calibration, plain environment labels). It tunes on dev, then locks a candidate and scores the holdout once.
- Voice: wait for Cole's go before installing audio. Then walk the smoke ladder in the README. Unsolicited speech needs its own policy before it is ever spoken.
- Next authorized stage (#60): a Codex vs Claude Cowork rundown against Nova's architecture. Codex drafts it and Claude critiques. Claude records only what its own task observably exposes, and labels unavailable internals.

## For Codex
Holdout ownership is Claude's; the gateway is Claude's. The dev builder can be rerun and refuses to change used data unless given `--rewrite`. Don't use `py_compile` on temp names in the repo: it leaves a stray pyc (gitignored).
