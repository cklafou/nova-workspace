<!-- @nova: Record the bounded control-POST acknowledgement repair and independent natural recorded-response review. -->
# HTTP acknowledgment and natural content review
**Summary:** The separate pre-existing control-POST reset race is fixed and verified offline. The new natural recorded run demonstrates ongoing body work and a useful follow-up adjustment, but is not fully accepted semantically or as natural-latency audible voice.

## HTTP diagnosis and change
- `workspace/Temp/hub-http-body-race/result.json` records the exact Windows10053 traceback in a disposable ephemeral-port hub. Sending POST headers, waiting50ms, then the declared body allowed the old handler to accept a fake action before the body and close its HTTP/1.0 connection. Reading the body before dispatch returned202 normally. Teardown only happened after the observation; no running hub or Nova process was controlled.
- Changed only `workspace/general_tools/nova_console/hub.py` and new `workspace/general_tools/nova_chat/tests/test_hub_http_body.py`.
- Mode start/stop and full shutdown/restart now consume a bounded complete JSON object before admission: maximum4096bytes and2seconds. Invalid framing/JSON/incomplete bodies reject400; oversized declaration413; body timeout408. Existing mode origin/host/content-type gates remain. Bodyless legacy StopNova.cmd requests remain supported. No action is admitted from an incomplete body.
- Six focused real-HTTP tests cover delayed bodies for all four routes, existing access guards, invalid/non-object/NaN JSON, invalid framing/oversize, incomplete input/timeout and legacy bodyless shutdown. These plus19 launcher-mode and3 lifecycle-ack tests all passed: **28 total**. Compile and scoped diff checks passed.
- Source frozen and handed to root; root owns production reload and live acknowledgement verification. No provider calls or service restarts by this agent.

## Natural recorded content
- Raw run: `workspace/Temp/voice-acceptance-20261006/fresh-natural-ready/result.json`; run `f4b2544d802147ea801608093181f921`.
- Independent assessment: `independent-content-review.json` in that folder. Existing receipts and the other agent's acceptance review were not altered.
- Two committed parts retain one run and revisions0→1. The follow-up changes the duration to five minutes and keeps work on the desk; the later answer substantially reflects that change. It makes no unobserved audio/hearing or actual-tool-success claim.
- Full content acceptance fails: later advice invents the presence of an on-desk bin and makes a trash exception without supplied evidence or permission. This does not cleanly satisfy the no-other-storage/keep-everything request. This is an instance-specific finding, not a recommendation to ban bins or special-case that word.
- First part42.5s after request acknowledgment; terminal61.812s; follow-up waited27.438s to apply. This does not establish real-time natural voice. Nine synthesized WAVs were file-only; microphone and speaker were not opened.
- Fresh transcript isolation preserves normal shared memory/identity/context. The earlier revision-zero segment was delivered before the accepted revision-one input was applied, as the selected frozen-segment contract permits; do not mislabel it as already responding to the amendment.

## Frozen source hashes
At 2026-10-06T03:48:27.834109+09:00:
- `workspace/general_tools/nova_console/hub.py`: `bb12f8d507fbb4a719405ec0dfeb4689c97edb86b375b6253260444929d3de78`
- `workspace/general_tools/nova_chat/tests/test_hub_http_body.py`: `7c313dc779a0381ab3e1c6f3c0e54ccd27db3510046f2cc4bbce974b7f888b91`
