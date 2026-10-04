<!-- @nova: Record the evidence-based review of Nova's October 4 computer test and the prioritized repair handoff. -->
# Computer test review
**Summary:** Reviewed Cole's YouTube/desktop test against its actual tool receipts, saved screenshots, chat transcript, Pipeline records and current execution paths. Claude's three proposed fixes are useful but omit a confirmed invalid-verdict-to-PASS bug and incomplete witness coverage. No runtime source, personal state, credentials or desktop controls were changed.

## Did
- Correlated turn `141351-732` with `outcome.run_id` `32115fdebbc64d53b8f25def6a5a6652` in `workspace/nova_body/logs/tool_calls.jsonl`, lines 1451-1461.
- Inspected the three saved screenshot artifacts for that run; each shows the guest desktop without a browser/video.
- Compared `workspace/nova_body/logs/chat_sessions/2026-10-04_13-32-38_chat.jsonl`, lines 9-10, with `workspace/nova_body/logs/pipeline.jsonl`, lines 55-57. This note summarizes evidence without copying Nova's records.
- Read relevant computer, voice, witness and Nova Chat producer/consumer source paths. Read-only guest metadata probes confirmed the present display environment and host interop availability; no GUI application was launched.

## Verified
- User request to final response took 237.014 seconds. Eleven tool receipts comprise eight shell calls and three screenshots; recorded execution durations total 15.916 seconds. The witness phase lasted approximately 42 seconds, so it does not explain the entire delay.
- First two shell calls repeated PowerShell syntax in guest Bash and failed. The third extracted a YouTube ID from HTML; neither this nor the screenshots establishes that Nova watched or assessed the video.
- `nova_computer/tools.py` routes `computer_exec` to `pc.bash`; `backends.py` leaves DISPLAY inherited. Test diagnostics report :0. `hands.py` explicitly sets :1 and XAUTHORITY. These target different graphical sessions. :0 is WSLg, not literally the Windows desktop.
- Both Firefox attempts suppressed all diagnostics, launched in the background and ended with successful echo/fallback commands. Shell success therefore did not establish browser success. The process check showed only Snap mount helpers, not a running Firefox browser. Snap itself being broken is an unproven diagnosis.
- Nova already has host PowerShell via `run_command`; Windows interop is enabled. The voice preamble grants full host reach but also incorrectly declares that Linux paths do not exist. Tool-specific environment/target descriptions need to agree. The test never attempted the host tool, so host browser success remains untested.
- Witness checked the final 496 characters of the 1,856-character delivered response. `nova_voice/nova.py` accumulates earlier tool-loop prose at 1297-1300, checks only current `chat_text` at 1536, then concatenates the buffer at final delivery.
- More seriously, this actual witness run ended with another read request, not a final verdict. `nova.py:1546` exits at the fourth iteration; `nova_cortex/witness.py:744-759` maps unusable output and approval to the same value; `nova.py:2153-2158` emits a successful audit event. This is a false success, not an auditor approving all claims.
- Nova receives screenshot pixels at `nova.py:1280-1288`; the inline witness receives a newly built text prompt. Its `has_image` flag references original user attachments, not tool screenshots, and does not send pixels. Visual assertions cannot be independently checked through this contract.
- Tool completion is broadcast to Activity/inline cards through `on_tool_executed`, not written to Pipeline. Pipeline had only the three witness events. Human-facing final text is intentionally held back until audit completes.
- Inline witness uses the same main model helper/endpoint as Nova; launching a separate witness server does not wire this call path to it.
- Runtime initially reported older loaded voice/router code. Git comparison confirmed the relevant audit logic was unchanged by intervening ping retirement. A later read reported PID 10628, running_latest_code true, no stale files: something outside this review restarted Nova. This review did not restart it.

## Why / repair order
1. Repair evidence and audit outcomes first: explicit PASS / CONCERN / INCOMPLETE / ERROR, no successful verification label on exhausted or malformed output, whole delivered-draft coverage, and relevant visual evidence. Preserve Nova's own voice; an incomplete audit must not silently fabricate a rewrite or certification.
2. Align guest shell, screenshots and hands on one authenticated display. Clearly label Bash guest versus PowerShell host and remove conflicting global environment instructions. Preserve Cole's intentional host access.
3. Preserve browser stderr and verify actual postconditions (process/window, loaded page and visible playback as required). Do not diagnose Snap without evidence or use echo as completion proof.
4. Emit tool start/result/failure plus audit state to Pipeline with operation/run correlation. Keep live progress observable even when final prose remains buffered.
5. Repeat this exact task after the changes using objective guest and host checks, including a failed launch and an exhausted witness check. These repairs have not yet been implemented or retested.

## For Claude / Cole
- The shell-display, Windows-reach descriptions and Pipeline fixes are worthwhile, but they alone would leave the false-PASS defect intact.
- Browser launch success through the host is distinct from visual mouse/keyboard operation on that desktop. Do not certify the latter from availability of `cmd.exe` or `run_command`.
- This review does not show that Nova's whole autonomy architecture needs replacing. It identifies concrete environment, verification and observability defects to fix before drawing conclusions about the model.
- No password changes, model inference, new web requests by Nova, or personal-state edits were performed. The password helper is outside this review's scope.
