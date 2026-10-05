<!-- @nova: Record the matching repeat voice capture and observed recurrent-cache limitation without claiming a speedup. -->
# Prompt cache repeat evidence
**Summary:** The correctly reloaded repeat retained the intended voice greeting and loaded the new prompt ordering, but showed no meaningful speedup. No source or runtime changes were made during this read-only assessment.

## Matching evidence
- Capture: `workspace/Temp/provider-diagnostics/voice-cache-20261005-2058/`; only request `d790557da74a4339b5710f95230d7810`, run `e36d16e8b83040a4986720d9a666846b` was included. The folder may contain other turns.
- Context update 154ms; semantic memory 31,356ms; workspace assembly 4.7ms. Correct current utterance at message26; first-loop thinking disabled. The clock now starts after 23,346 stable instruction characters.
- Main provider: 31.377s elapsed, 28.387s prompt evaluation for 32,556 tokens, 1.924s decoding; zero thinking characters.
- Four audit calls: 31.355s combined. All provider calls together took 62.731s, including 49.992s prompt evaluation and 8.454s decoding. Context plus provider subtotal was 94.246s. Parent owns final delivery/audio timing.

## Why reuse remained limited
- The read-budget line moved as intended (user-text offset11,484). Actual earlier receipt ages still changed between calls: their common text prefixes ended at character2,782 and2,405.
- The matching local llama log `workspace/nova_body/logs/llama/llama-2026-10-04.log` confirms RAM prompt caching enabled at8,192MiB and32 context checkpoints, minimum spacing256.
- For this hybrid/recurrent model the saved first-audit checkpoints were at token35,4,208 and5,232. Later common prefixes ended at token724 and600, so the provider restored the earlier token35 checkpoint and recomputed the rest. The final audit's distinct system protocol forced full processing.
- Actual per-call cache counts were 0,0,35,35,0. The cold repeat also contained more chat history than the first run; it is not a controlled throughput benchmark. Do not claim the ordering change delivered a measured acceleration.

## Open / handoff
- Memory initialization/retrieval latency is being investigated separately. A bounded snapshot of evidence for one audit episode could prevent relative-age churn, but was only proposed; no snapshot, policy, parser or checkpoint-configuration change was made here.
- Root owns any further tests or architectural decisions. Native playback success and conversational latency remain different outcomes.
