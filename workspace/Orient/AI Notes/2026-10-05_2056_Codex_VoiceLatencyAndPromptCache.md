<!-- @nova: Record measured native voice latency and cache-preserving prompt ordering without changing witness policy. -->
# Voice latency and prompt cache
**Summary:** The controlled voice_fast greeting reached the provider with the correct current utterance. Most of its wait was memory retrieval and prompt processing, not token generation. Root reported delivery after 94.844 seconds and first native Windows playback after 96.246 seconds; this is working transport/audio, not satisfactory conversational latency.

## Measured
- Capture `workspace/Temp/provider-diagnostics/voice-native-20261005-2048/`: context update 380ms; semantic memory 34,947ms; workspace assembly 7ms.
- Main provider request: 31,383 prompt tokens, cache_n=0, 25.992s prompt evaluation, 1.466s decoding, 28.677s elapsed; zero thinking characters. The outgoing current request remained intact, and the draft addressed the greeting.
- Four witness calls: 30.030s total. Calls two and three reused only 35 tokens; the read budget changed near the front, before roughly 20k characters of stable evidence. Combined provider prompt evaluation was 46.031s and decoding 8.502s across all five calls.
- Read-only actual provider `/props` and `/slots`: build b9733-f449e0553, one 65,536-token slot, idle after the run. One slot alone does not prove permanent eviction: the exact-build [official server documentation](https://raw.githubusercontent.com/ggml-org/llama.cpp/f449e0553/tools/server/README.md) documents RAM prompt caching and idle-slot caching defaults. Actual warm-turn savings remain unmeasured.

## Did
- `workspace/general_tools/nova_chat/transcript.py`: keep stable instructions first and put the exact existing clock/gap text immediately after them, at the same system priority.
- `workspace/nova_body/nova_cortex/witness.py`: relocate only the identical READ BUDGET line behind stable evidence, before growing read-check receipts. The final no-more-reads protocol remains distinct and unchanged.
- `workspace/nova_body/nova_voice/nova.py`: remove unsupported near-one-second audio and automatic utterance-classifier claims from voice register comments. This changes no runtime behavior.
- `workspace/general_tools/nova_chat/tests/test_prompt_cache.py`: five tests including pre-change prompt hashes for ten text/image/read-budget variants, preserving every non-budget byte; exact clock/current-request retention, prefix stability, counter/evidence retention and strict parser behavior.

## Verified
- Five new prompt-cache tests plus all 58 existing witness tests passed; source AST and scoped diff checks passed. No new inference or service/audio control was performed by this slice.
- Witness parser, approval policy, read limits, supplied evidence, sampling and tools are unchanged. Root authorized only cache-oriented relocation, not a policy rewrite or deployment of the rejected witness candidate.

## Open / handoff
- Root owns reload and repeat native voice capture; compare cache_n and prompt_ms rather than promising an unmeasured speedup. Memory latency investigation is assigned separately to the bridge agent.
- Documentation agent owns matching Orient explanations/review baselines. Source is frozen and released for testing. The raw opt-in provider capture remains local Temp; do not quote personal prompt contents into notes or reports.
