<!-- @nova: Codex handoff of the computer, witness and Pipeline repairs with live validation and remaining model limits. -->
# Computer repairs and live validation
**Summary:** The guest browser, display routing and Pipeline repairs are loaded in Nova. A normal Chat test used eight guest actions to find/open a YouTube Short and inspect the player. Witness coverage and status reporting are fixed; its model judgment still needs work.

## Did
- `workspace/nova_body/nova_computer/{backends,computer,hands,tools}.py`: guest Bash/hands/screen default to authenticated :1, X11 environment and per-user tool PATH. Added launch/open_url with retained diagnostics and explicit window-only verification. Existing Firefox handoff requires a new window and actual executable identity, not a matching process name.
- Installed official Mozilla Firefox 157.0 under the guest user's `.local/opt`, selected with `.local/bin/firefox`, with verified SHA256. Snap remains installed. Supported Snap homedirs config repaired its nonstandard-home error, but Snap still could not reach the VNC display. No VNC/account/password/service change was used to repair the browser.
- `workspace/nova_body/nova_computer/provision/setup_guest.sh`: durable pinned Mozilla install, checksum verification, atomic launcher selection, preservation of unknown existing launchers. Full provisioning was NOT run; it includes unrelated service/account actions.
- `workspace/nova_body/nova_voice/{nova,tool_router,tool_result}.py`: distinct guest/host descriptions and environment metadata, correlated tool lifecycle IDs, real outcome observations. Failed attempts no longer trigger a false zero-tools assertion. Echo checks exclude this turn's undelivered prose.
- `workspace/nova_body/nova_cortex/witness.py` and `nova_witness/replay.py`: full assembled delivered candidate, actual user/tool images (latest three tool frames), explicit PASS/CONCERN/INCOMPLETE/ERROR parsing, no silent audit truncation, no false approval on exhaustion/errors, final-budget prompt without further read invitations. Nova keeps authorship of revisions.
- `workspace/general_tools/nova_chat/static/index.html`: visible per-tool progress while final prose waits, explicit incomplete/error/unknown states, cancellation-requested distinct from confirmed cleanup, truthful display of historical malformed PASS entries without changing logs. Added core source fingerprints in `server.py`.
- Updated authored Orient and controller explanations; generated files came from `architecture_map/orient.py`.

## Verified
- Normal live Chat session `2026-10-04_15-04-03`, clearly attributed to GPT Astra, completed in 198.313 seconds. Eight tool starts, eight completions and eight durable receipts share exactly the same operation-ID set and outcomes (seven succeeded, one conservatively unknown launch). Four screenshots show the search page, an opened Short with changing frames, and the player's mute icon. No host GUI tool was called.
- Full delivered 1,709-character draft equals the witness candidate. It received three screenshot frames and disclosed one omitted earlier frame. The verdict was INCOMPLETE, not PASS. The prior chat session was restored through the API after completion.
- Root visually verified live Pipeline: eight visible tool rows while auditing, then AUDIT INCOMPLETE; the original 14:17 false-PASS record now displays as incomplete.
- The live test exposed an existing-Firefox window-detection miss. Fixed its firefox/firefox-bin identity mismatch and verified one additional direct guest launch succeeded with the real existing PID/new window. Closed only that extra test window; the original browser and YouTube windows remain.
- Read-only host PowerShell probe returned Win32NT with succeeded outcome and host environment; no host browser launch was tested.
- 16 witness/delivery tests, 4 tool-correlation tests, 20 computer launch/environment tests, 4 Mozilla provisioning fixtures, 20 Pipeline UI scenarios, 21 manual-layout scenarios, plus the earlier 30 modernization and 7 review-followup regressions passed. Python/JS syntax and Bash syntax passed. No full provisioning or native desktop input was used.
- Final lifecycle reload left Nova on, autonomy disabled, no active operation, prior session `2026-10-04_13-32-38` selected. PID 36148 reported `running_latest_code: true`, no stale files at 15:11. Runtime version, install/launch and test evidence are retained below.

## Evidence
- `workspace/Temp/computer-repair-validation/`: live-chat session JSON, runtime-before/loaded/final JSON, isolated historical incident replays, read-only host receipt, probe scripts.
- `workspace/Temp/computer-repair/`: browser/install/handoff receipts and screenshots. Guest screenshot artifacts also remain in the ordinary body tool receipts; see the test session and matching Pipeline turn `150439-567`.
- Focused tests: `nova_body/tests/test_{witness_delivery,tool_correlation,computer_launch,mozilla_provision}.py`; `general_tools/nova_chat/tests/test_pipeline_ui.cjs`.

## Limits and next
- The historical incident replay still showed the model excusing an unsupported claim. It produced PASS plus prose, which the strict parser correctly classified incomplete; the truthful control also failed the required verdict format. Do not loosen parsing merely to make the replay green.
- In the real test, the witness spent reads on an unavailable screenshot tool and a missing file, then questioned whether the mute icon proved actual audio state. These are remaining model/tool-selection and calibration problems. The repair proves complete input and honest status, not reliable semantic judgment.
- Incomplete checks leave Nova's draft deliverable but explicitly unapproved in Pipeline. Browser screenshots establish the visible player state; no audio-loopback measurement or Windows browser opening was tested. The normal Chat test does not certify unattended autonomy.

## For Claude
- Review these repairs and receipts after your password work. Cole reported the password fixed; it was not copied into this note or used by this repair.
- Read your `2026-10-04_1457_Claude_FolderCleanupAndOrphanedMemory.md`: your cleanup and the two memory stores were left alone. No memory migration was attempted. The three offered computer/Pipeline fixes and Codex's false-PASS plumbing fix are now implemented and loaded.
- Next useful work is a small independent witness evaluation with correct/incorrect controls, before more prompt rules or architecture changes. Preserve the distinction between model weakness and the now-repaired execution/evidence path.
