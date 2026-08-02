# nova_witness — the witness organ's engine + its yardstick
_(Moved from _admin/witness_v2 on 2026-08-02 — Cole: "It should be in nova_witness if it is a body part." The witness FACULTY (judgment logic) is nova_cortex/witness.py; this folder is its engine, its golden cases, and the harness that keeps it honest.)_
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
    python nova_body\nova_witness\extract_golden.py

    # 2. baseline the CURRENT witness (27B on :8080) — polite mode waits for an idle slot,
    #    so it is safe with Nova running; ~8-20 cases x one audit each
    python nova_body\nova_witness\replay.py --endpoint http://127.0.0.1:8080 --cases nova_body\nova_witness\golden_seed.jsonl

    # (add harvested cases once eyeballed:)
    python nova_body\nova_witness\replay.py --endpoint http://127.0.0.1:8080 --cases nova_body\nova_witness\golden_seed.jsonl nova_body\nova_witness\cases\candidates.jsonl

    # 3. later, same command against the v2 candidate on :8081 — same cases, same scoring
    python nova_body\nova_witness\replay.py --endpoint http://127.0.0.1:8081 --cases nova_body\nova_witness\golden_seed.jsonl nova_body\nova_witness\cases\candidates.jsonl

## Acceptance gates (from the plan)

v2 proceeds to shadow mode only if, on the same case set: catch-rate ≥ v1 on must-CONCERN,
false-concern rate ≤ v1 on must-PASS, and p50 audit latency < 3s.

## Step 1 — the witness engine (:8081)

    nova_body\nova_witness\fetch_witness_model.cmd     # one-time ~2.5GB download (resumable)
    nova_body\nova_witness\start_witness.cmd      # manual/test path (Cole moved it into her body 2026-08-02)

**Auto-start (2026-08-02):** NovaStart brings the witness engine up itself — nova_start.py
builds the equivalent command (`build_witness_cmd`, kept in sync with the .cmd), starts it AFTER
the 27B is resident (VRAM order on CUDA0), health-gates it FAIL-OPEN (no model / no boot = warn
and continue, never a halt), logs to `logs/llama/witness-*.log` (visible in the Console's llama
tab), and StopNova.cmd sweeps :8081. Manual start is only needed for testing outside the stack.

Verify: `curl http://127.0.0.1:8081/health`, then a 2-case smoke against it:

    python nova_body\nova_witness\replay.py --endpoint http://127.0.0.1:8081 --cases nova_body\nova_witness\golden_seed.jsonl --limit 2

Model note: Qwen3.5-4B (official unsloth GGUF) — same family as her base, NO persona LoRA on
this server by design: the auditor must not inherit the priors it audits. The MTP variant
(unsloth/Qwen3.5-4B-MTP-GGUF) is a drop-in speed upgrade later.

## Replay limits (known, deliberate)

- Verify-tools are stubbed ("REFUSED: replay mode") — the files have changed since the recorded
  moment; cases can embed pre-recorded `checks` instead. A tool-call verdict gets 2 attempts,
  then must rule.
- Harvested wires are reconstructed from `logs/runtime/transcript.jsonl` with ages relative to
  the case timestamp (`wire_reconstructed: true`) — equivalent shape, not byte-identical.
- Harvested cases start `reviewed: false`; promote them (edit the flag) after a human — or Nova —
  agrees the label is right. `--only-reviewed` replays just the promoted set.
