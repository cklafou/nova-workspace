<!-- @nova: Hand off completed review repairs, independent witness results and unfinished voice integration after Claude's usage limit. -->
# Witness review results and solo handoff
**Summary:** Cole asked Codex to finish what it could solo. Claude completed the review, replay harness v2, 26 independent controls and voice readiness script before its limit. Codex completed the review fixes and a first local-model run. Code checks pass; model judgment still has concrete failures.

## Did
- Answered Claude collaboration messages 51-53 and the ownership handoff in `2026-10-04_1523_Codex_CollaborationHandoff.md`. This completes the work in `2026-10-04_1837_Codex_WitnessReviewInProgress.md`.
- Runtime/replay now share compact receipt formatting, bounded disclosed output, verdict-first read dispatch, bounded combined user/tool images, and literal-safe inline audit sampling. Bad-request diagnostics omit screenshot payload bytes.
- Revised answers still enter the configured concession check after incomplete/error re-audits; those statuses remain unapproved in Pipeline. Unknown tool outcomes use neutral tool_finished. Loop-exhaustion salvage omits raw tool JSON and duplicate prefix text.
- Guest launch verification uses a tagged result so warnings cannot break parsing; existing-browser handoff requires a successful initial window enumeration. Default wait is a live tunable ten seconds.
- Replay v3 preserves earlier reports, captures source/case hashes and request parameters, and uses the actual served model ID. Added controls README and a separate experiment readout without changing labels or images.
- Updated authored Orient sections and voice README. The latter previously equated delivered final text with witness approval and promised unmeasured early speech; it now documents current gaps.

## Verified
- 141 isolated checks passed (42 witness, 22 launcher, 23 Pipeline, 30 modernization, 7 earlier review, 4 correlation, 4 provisioning, 9 committer). Changed Python compiled. Final whitespace validation and Orient freshness are checked separately below/in the closing response.
- Fresh direct guest launch observed a new Firefox window on :1, left page/playback unverified, and closed only that window. Receipt: `workspace/Temp/computer-repair-validation/browser-review-2026-10-04.json`.
- All six control-image checksums match. First unchanged 26-case run on local Qwen 3.8 27B Q6_K_XL with nova_core_v7_qwen38_r2_epoch2 at scale 1.0: 16 matching labels, 1 false approval, 1 false concern, 8 unnecessary incomplete verdicts; no harness/provider errors. Both historical replies remained incomplete rather than receiving the needed objection. Median 17.98s, p90 49.45s. Read refusals in historical replay and selected cases limit interpretation.
- Readout: `workspace/nova_body/nova_witness/reports/2026-10-04_1849_controls_v1_readout.md`; raw report `replay_v3_127.0.0.1_8080_2026-10-04_184921_053922.json` and matching environment metadata live beside it.
- Nova remained off/chat-only, autonomy false, no active operations. Only the benchmark model was started, then stopped with confirmed port closure. Final state evidence is `workspace/Temp/computer-repair-validation/witness-review-final-state.json`. Existing chat PID 37804 has old imported code; next Start Nova loads the repaired backend. Existing UI requires reload after saving any intended layout changes.

## Voice / next
- `VOICE_CHECK.cmd` ran on Windows Python 3.12.6 with Nova off: websockets, numpy, torch, transformers present; sounddevice, onnxruntime, torchaudio, chatterbox, silero_vad, moonshine_onnx absent in that interpreter. VTube Studio API was down. No live audio claim.
- First-stage voice scope from the room remains delivered-final-text playback, message/run IDs, start/reset, interruption/flush, audit status and body events. The current gateway drops IDs, ignores starts, and its stream branch can be silent when tokens are held. Register routing must follow the current queue and runtime model client; the older server_patch.md is only a sketch. Claim tagging is not a speech gate.
- Model judgment is the next audit priority. Preserve strict approval parsing: one erroneous verbose PASS was kept unapproved by that rule. Do not relabel these controls to fit the model; use fresh independent cases for further prompt/model comparisons.

## For Claude / other Codex work
The avatar chat remains independent and untouched; its 1830 frontal-master note was read. No host desktop input, microphone recording, personal-state edits, password changes, provider-key changes or cloud inference were performed. No new voice engine or speech output was installed/activated.
