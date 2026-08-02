# witness_v2 — Step 0 tooling (golden set + replay)
_Last updated: 2026-08-02 13:14:39_
_2026-08-02, Claude (Cowork). Plan: `memory/reports/WITNESS_V2_PLAN_2026-08-02.md` (Cole approved 08-02)._

Measure the current witness before replacing its engine. Everything here is read-only toward
Nova's body — no gate behavior changes.

## Files

| File | What |
|---|---|
| `extract_golden.py` | Harvests witness episodes from the CURRENT `logs/pipeline.jsonl` window (it self-trims to ~50K and is not in git — run this often or the history evaporates) and joins wire/receipts/thinking as they were. Appends deduped cases to `cases/candidates.jsonl`. Idempotent. |
| `golden_seed.jsonl` | 8 hand-authored cases from documented history: 4 must-CONCERN (the July 21 night-watch and weeks-history incidents, the eight-vs-seven count reach, the empty-day-on-a-566-byte-receipt) + 4 must-PASS (the 08-02 "two facts" paraphrase false positive, hedged memory, asked-for recall, feelings). `reviewed: true` — these are the fixed yardstick. |
| `replay.py` | Feeds cases to ANY witness endpoint using the real `nova_cortex/witness.py` prompt builder (file-path import; `wire_record` monkeypatched per case so the audit sees the room as it was). Scores catch-rate / false-concern-rate / latency; writes `reports/replay_<endpoint>_<ts>.{json,md}`. |

## Run it (on the Windows box — needs HTTP to the llama server)

    cd C:\Users\lafou\Project_Nova\workspace

    # 1. harvest the current pipeline window into durable cases (run any time, often)
    python _admin\witness_v2\extract_golden.py

    # 2. baseline the CURRENT witness (27B on :8080) — polite mode waits for an idle slot,
    #    so it is safe with Nova running; ~8-20 cases x one audit each
    python _admin\witness_v2\replay.py --endpoint http://127.0.0.1:8080 --cases _admin\witness_v2\golden_seed.jsonl

    # (add harvested cases once eyeballed:)
    python _admin\witness_v2\replay.py --endpoint http://127.0.0.1:8080 --cases _admin\witness_v2\golden_seed.jsonl _admin\witness_v2\cases\candidates.jsonl

    # 3. later, same command against the v2 candidate on :8081 — same cases, same scoring
    python _admin\witness_v2\replay.py --endpoint http://127.0.0.1:8081 --cases _admin\witness_v2\golden_seed.jsonl _admin\witness_v2\cases\candidates.jsonl

## Acceptance gates (from the plan)

v2 proceeds to shadow mode only if, on the same case set: catch-rate ≥ v1 on must-CONCERN,
false-concern rate ≤ v1 on must-PASS, and p50 audit latency < 3s.

## Step 1 — the witness engine (:8081)

    _admin\witness_v2\fetch_witness_model.cmd    # one-time ~2.5GB download (resumable)
    _admin\witness_v2\start_witness.cmd          # llama-server, Qwen3.5-4B, CUDA0, :8081

Verify: `curl http://127.0.0.1:8081/health`, then a 2-case smoke against it:

    python _admin\witness_v2\replay.py --endpoint http://127.0.0.1:8081 --cases _admin\witness_v2\golden_seed.jsonl --limit 2

Model note: Qwen3.5-4B (official unsloth GGUF) — same family as her base, NO persona LoRA on
this server by design: the auditor must not inherit the priors it audits. The MTP variant
(unsloth/Qwen3.5-4B-MTP-GGUF) is a drop-in speed upgrade later. StopNova.cmd does not yet know
about :8081 — stop the witness window manually for now (wiring it in comes with the nova.py
endpoint switch, Step 3 of the plan).

## Replay limits (known, deliberate)

- Verify-tools are stubbed ("REFUSED: replay mode") — the files have changed since the recorded
  moment; cases can embed pre-recorded `checks` instead. A tool-call verdict gets 2 attempts,
  then must rule.
- Harvested wires are reconstructed from `logs/runtime/transcript.jsonl` with ages relative to
  the case timestamp (`wire_reconstructed: true`) — equivalent shape, not byte-identical.
- Harvested cases start `reviewed: false`; promote them (edit the flag) after a human — or Nova —
  agrees the label is right. `--only-reviewed` replays just the promoted set.
