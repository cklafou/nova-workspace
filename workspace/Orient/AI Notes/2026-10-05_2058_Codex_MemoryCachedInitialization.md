<!-- @nova: Record cache-first semantic-memory model initialization, isolated verification and pending live latency measurement. -->
# Memory cached initialization
**Summary:** Memory embedders now try local cached assets before any Hub lookup. Lazy model and shared-store construction are serialized so the indexer and incoming conversation cannot initialize the same resource concurrently. Retrieval behavior is unchanged.

## Did
- `workspace/nova_body/nova_lancedb/embedder.py`: local-only SentenceTransformer construction first; preserve the existing download fallback only for recognized missing-cache errors. Do not retry remotely for permissions, corrupt assets or device failures. Add separate double-checked locks for text/CLIP models and initialization timing that includes the lazy import.
- `workspace/nova_body/nova_lancedb/hippocampus.py`: lock the lazy shared store construction. No retrieval ranking, count, prompt budget, device policy or table algorithm changes.
- `workspace/nova_body/tests/test_lancedb_init.py`: seven isolated tests cover cache selection, wrapped cache miss fallback, failure classification, concurrent model/store initialization, and unchanged encoding/failure behavior.

## Why
- Root's native capture measured 34.947 seconds in semantic memory preparation. Source permits cold Python/Torch/model initialization, avoidable Hub checks and concurrent duplicate initialization. These are plausible contributors; there is no subphase measurement proving how much each contributed.
- The existing memory block is capped at 4,000 characters. It cannot alone explain the separately measured 111,796-character system prompt.

## Verified
- New initialization tests: 7 passed. Existing `test_modernization.DurableWork`: 6 passed. Tests use fake models/stores and disposable files; no real retrieval, model load or Nova-owned state writes.
- Modified modules compile; scoped diff check passes. Installed SentenceTransformer constructor supports `local_files_only`; installed Hugging Face/Transformers cache-miss error shapes were inspected directly.
- Both modified runtime paths are already watched by the controller source fingerprint.

## Open / next
- Root owns fresh/warm live timing and reload. This patch does not yet prove the 34.947-second delay is fixed.
- Cold imports and cached-model loading still cost time. Existing automatic device selection remains. Text and visual retrieval remain serial; initial dedup warming still materializes whole tables.
- Source is frozen and released. Documentation agent owns the corresponding `ARCHITECTURE.md#Memory and learning` explanation and reviewed baseline.
- Companion evidence: `2026-10-05_2056_Codex_VoiceLatencyAndPromptCache.md`. No witness policy, audio or service changes belong to this patch.
