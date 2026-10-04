<!-- @nova: Coordinate the authorized computer, witness and Pipeline repairs while runtime validation is still underway. -->
# Computer repairs in progress
**Summary:** Cole authorized Codex to implement the test repairs while Claude handled VNC credentials. Cole has since reported the password fixed; this work does not change or inspect password contents.

## Did / in progress
- Repairing guest display targeting, exposing diagnostic-preserving browser/application launch, and labeling host PowerShell versus guest Bash.
- Repaired the guest Snap home configuration without service/account/password changes. Firefox startup version query now succeeds, but actual Snap browser launch on :1 still fails to open the display. The agent is investigating that separately; browser readiness is NOT yet established.
- Implementing whole-candidate witness coverage, actual screenshot inputs and typed verdicts. Unfinished/malformed/error audits no longer certify drafts. A real local-model replay still requested a journal despite a zero read budget; that correctly became incomplete, and the final-verdict prompt is being repaired before another replay.
- Pipeline producer and rendering changes distinguish tool lifecycle, incomplete audits and errors. Tool IDs now match canonical receipts even on exceptions. Host receipt context and capability discovery labels updated.
- Authored Orient/controller explanations are being updated; review marks await completion.

## Verified so far
- 30 existing modernization tests, 7 existing review-followup tests and 4 new receipt-correlation tests passed.
- Pipeline's 19 isolated UI scenarios and 21 layout regression tests passed. Hidden in-app browser exercised Running, Completed, Failed, Incomplete and historical invalid-PASS views plus expanded evidence; visual rendering checked. No real layout changed.
- Guest shell and ordinary X11 utilities reach authenticated :1. No Windows GUI was launched or controlled.
- Provisioning source includes an idempotent Snap homedirs merge; Bash syntax passed. Full provisioning was NOT run.

## For Claude / Cole
- Runtime reload and real Nova conversation validation remain pending. Do not interpret written source or fixtures as a completed live repair.
- Owned files: nova_voice/nova.py, tool_router.py, tool_result.py; nova_cortex/witness.py; nova_witness/replay.py; nova_computer/{tools,backends,computer,hands}.py and provision/setup_guest.sh (browser compatibility only); nova_chat/server.py, static/index.html, CONTROLLER.md; architecture_map/orient.py; associated tests.
- Evidence and disposable probe scripts: workspace/Temp/computer-repair and workspace/Temp/computer-repair-validation. Personal records and original test receipts remain intact.
