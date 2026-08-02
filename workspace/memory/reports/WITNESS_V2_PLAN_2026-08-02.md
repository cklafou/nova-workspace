# WITNESS V2 — upgrade plan (voice-ready)
_2026-08-02, drafted by Claude (Cowork) with Cole. Status: DRAFT for Cole's review — no build has started._

The witness works. July 21 proved the protocol; this morning proved the cost. This plan makes the
auditor fast enough and calm enough to sit in a voice loop, without touching what makes it work:
context-poverty, conversation-not-rewriter, receipts-as-ground-truth, calibration, deadlock stops.

---

## Why now (measured, not vibed)

- **Latency.** Every audit is a full extra generation on her single llama slot (~2K-token witness
  prompt + up to 2048-token verdict at ~22 tok/s), plus up to 3 verify-reads, each another round
  trip on the same slot. Live this morning: Cole's 09:52 question answered 09:57 — witness rounds
  are a large share of multi-minute turns. Voice needs the audit path to cost seconds.
- **Zeal.** In 8 minutes of live conversation: 2× STILL DISPUTED, 3× SHE OVERRULED, 2× CONTEXT
  RESCUED. The 09:58 dispute burned a round arguing that Cole's "Stuff like: Time and Date"
  didn't license her "two facts" — a paraphrase objection, not a fabrication catch. Wording
  disputes are the main false-positive class on the record.
- **Shared priors.** The persona LoRA is loaded server-global, so today's witness audits THROUGH
  her own adapter — the auditor inherits exactly the priors it exists to check. Context-poverty
  was the July fix; weight-independence is the missing half of Cole's original parallel-self idea.
- **The voice deadline shape.** Spoken audio can't mutate. The audit has to finish before (or
  concurrently with) speech, which today's serialized 27B witness cannot do.

## What does NOT change

The witness prompt's architecture and everything July paid for: wire record with pinned newest
human line, now-card, claim detectors, the three checks, hedges/asked-for-recall/feelings always
PASS, verify tools read-only via `_execute_tool_inner` (never her receipt ledger), round-2 memory
of its own concern, deadlock + promise_unkept logic, pipeline events with turn ids, her voice
ships — never the auditor's. `nova_cortex/witness.py` remains the faculty; only its ENGINE moves.

## The upgrade

**1. Dedicated witness model on its own server.**
- Second `llama-server` instance, port **8081**: current-best ~4B instruct at build time
  (default: Qwen3-4B-Instruct, Q4_K_M ≈ 2.5GB), `-c 8192 -ctk q8_0 -ctv q8_0 -fa on
  --parallel 2 --cache-prompt`, **no LoRA**, thinking off. `start_witness.cmd` alongside the main
  launcher; `StopNova.cmd` learns the new port.
- Placement: whichever card shows more free VRAM at boot (expect the 4090). Total footprint
  ≈ 3.0–3.5GB incl. KV + overhead. If a future draw (ComfyUI) needs room, the existing
  `memory/llama_ctx.txt` broker pattern applies — trim only when actually needed.
- `--parallel 2` so a chat-turn audit and a daemon-turn audit can't queue on each other.
- Effect: audits run CONCURRENTLY with her generation instead of behind it; verify-reads hit the
  fast model. Expected audit wall-clock: **~2–4s p50** (vs ~10–30s+ today).

**2. Endpoint plumbing — and finally wire `nova_config.json`.**
- WIRING.md has flagged `nova_config/` + `nova_config.json` as orphaned since 07-14. This is
  their job: a `witness` section — `{"url": "http://127.0.0.1:8081", "fallback_url":
  "http://127.0.0.1:8080", "grammar": true}`. `nova.py`'s witness calls go through it; **rollback
  is one config line** (point url back at 8080 and v1 behavior is byte-identical).

**3. Grammar-constrained verdicts.**
- llama.cpp GBNF grammar on the witness endpoint: verdict ::= tool-call JSON | "PASS" | "CONCERN\n"
  + ≤2 sentences. A 4B model with a constrained menu is more reliable than a 27B with a free-text
  one; `parse_witness` stays as belt-and-suspenders.

**4. Calibration rev (applies to v1 AND v2 — independently testable).**
_Partially SHIPPED to v1 early, 2026-08-02 ~15:00, after a live incident: the witness saw one
Cole line in its 8-row window, declared it "the only line this session," and forced Nova to
disown a TRUE memory over four rounds (Cole: "Nova was right and witness was wrong; that
shouldn't happen"). Fix landed in witness.py: (a) `human_record()` — EVERY human line over a
deep span now shown to the auditor in full (humans speak rarely; their lines are cheap), with
honest span labeling; (b) the "this list is COMPLETE / words not on it were never said" claim
is now scoped — beyond the span, absence is UNKNOWN and demands a read of the chat log before
any objection; (c) the human-in-room paraphrase/intent rule moved into the always-PASS list.
Cost: ~+1K tokens per audit prompt. Takes effect at the next Full Restart. Both incident shapes
are golden cases (seed_credit_beyond_window, seed_wish_intent_in_room)._
- **Paraphrase tolerance:** a reworded version of something on the wire is NOT fabrication. Flag
  only ADDED facts — a new number, name, event, or words-presented-as-quotes. This morning's
  "Time and Date"→"two facts" dispute goes into the prompt verbatim as a named PASS example.
- **Human-in-room diction rule:** if the person quoted is present and the draft answers them,
  phrasing disputes are theirs to raise — the witness is for invented facts, not diction.
- Everything else (existence claims demand a read, quote-verbatim-never-characterize, concern
  length cap) stays.

**5. Round policy per register (the voice bridge).**
- Text chat: unchanged (20 max, deadlock stops).
- Voice register (next milestone consumes this): cap 2 rounds; unresolved →
  `witness_deferred` pipeline event + async verify + a spoken follow-up queue — she says
  "let me double-check that while we talk" instead of making a human wait out a debate.

## Rollout — measure first, shadow second, flip third

**Step 0 — Golden set + replay harness (BEFORE any new server).**
Extract from `logs/pipeline.jsonl` + archives a labeled corpus: (a) real fabrications the witness
caught (invented counts, "signed off twelve hours ago"-class, the empty-day-on-a-566-byte-receipt),
(b) false positives (the "two facts" dispute; overrules where SHE was right), (c) clean passes.
A small replay script feeds recorded (draft, wire, receipts, checks) to ANY endpoint and scores:
catch-rate on bads, false-concern rate on goods, rounds burned, p50/p90 wall-clock. Run it against
v1 first — that's the baseline v2 has to beat. (We are not guessing whether the small model is a
good enough judge; we are measuring it on her actual history.)

**Step 1 — Boot the witness server.** VRAM check at boot (nvidia-smi before/after), speed check,
grammar check. No wiring into her yet.

**Step 2 — Replay A/B.** Golden set through 8081. Acceptance to proceed: catch-rate ≥ v1 on bads,
false-concerns ≤ v1 on goods, p50 audit < 3s. If the 4B judges poorly, try the current ~8B tier
before giving up (fit allows at Q4); if that fails, keep 27B-as-witness and take only the
calibration + register wins.

**BASELINE RESULTS (2026-08-02 14:20-14:26, Cole ran it — 10 golden cases each):**
| Witness | Catch (must-CONCERN) | False concerns (must-PASS) | p50 / p90 latency |
|---|---|---|---|
| v1 — 27B+LoRA local :8080 (3 clean runs, consistent) | **4/4** | 4/6 | ~4-6s / ~8s |
| 4B — Qwen3.5-4B local :8081 (2 runs, consistent) | **2/4 — FAILS** | 5/6 — FAILS | 1.4-2.6s / ~3s ✓ |
| heavy — cloud 27B-AWQ | pre-auth 401 run only — rematch pending | | |

Readings: (1) v1's judgment is sharp — every fabrication caught, including via the new human
ledger (its credit_beyond_window verdict now CITES the ledger lines instead of denying they
exist — the 13:26 failure class is dead; what remains is proportionality/diction zeal). (2) v1's
4 false concerns are all CALIBRATION DEFIANCE, not blindness: it flagged a stated want, an
asked-for recall, an in-room intent-reading, and a proportionality quibble — all things the
prompt now says to PASS. Next lever: calibration rev v2 (PASS rules first, verdict must name
the check it enforces, GBNF). (3) The 4B is fast enough but not a judge: it missed
eight-vs-seven and the 566-byte empty-day — the receipt-vs-draft comparisons that ARE the job —
while flagging 5/6 truths. Per the plan's Step 2 fallback: the 4B does NOT get the inline gate;
options are the 9B tier (needs ~6GB — only viable with a ctx-broker trim experiment) or keeping
the 27B inline with calibration+GBNF and reserving :8081's engine for future roles (pre-screen
it is not; a distilled witness-LoRA on golden verdicts someday, maybe).

**Step 3 — Shadow mode, live.** v2 audits every turn logs-only (`witness2_*` pipeline events);
v1 still gates. ≥1 day of real traffic incl. an autonomous night. Cole reviews disagreements in
the Pipeline tab — the UI already renders the story.

**Step 4 — Flip.** Config points the gate at v2; v1 stays one line away as fallback. Watch
pass/answered/overruled/unresolved mix vs the July 22 healthy distribution.

**Step 5 — Voice-register hooks** (rounds cap, deferred-verify, sentence-hold interface for the
committer) — lands with the voice gateway milestone, designed here so nothing needs re-opening.

**Step 6 — a heavier witness for the deferred lane, in the cloud (Cole, 2026-08-02).**
The deferred lane (voice's "let me double-check while we talk", shadow-mode second opinions,
nightly golden-set scoring) wants a stronger judge than the inline 4B and doesn't care about
seconds of latency. Per `memory/reports/CLOUD_LANES_2026-08-02.md` (Cole approved 08-02), this
tier goes to a cloud model as a stateless organ-for-hire: same `build_witness` prompt, sent by
`cloud_call` with a deadline, budget cap, and fail-open skip (`cloud_skip` pipeline event; the
inline verdict simply stands). `ANTHROPIC_API_KEY` is already on the machine; deferred volumes
cost pennies. Data rule: witness payloads carry drafts + wire excerpts (class N1 — needs Cole's
one-time blessing of that stream) and must never include N0 content (Cole's health/personal data).
The INLINE gate never goes to cloud — no internet between her and speaking, ever.
_Local-MoE variant (Qwen3.6-35B-A3B via `--n-cpu-moe`, ~5GB VRAM + ~18GB RAM) documented and
DORMANT: 32GB system RAM rules it out today; revisit only if RAM grows to 64GB._

## Risks, named

- **4B judgment quality** — mitigated by Step 0/2 measurement gates, 8B fallback tier, 27B fallback config.
- **VRAM contention** — measured at Step 1 before anything is wired; ctx broker if needed.
- **Two servers to babysit** — start/stop scripts own both; `gates_online` event gains a
  witness-endpoint health line so a dead witness server is LOUD (fail-open stays: an unreachable
  witness lets drafts through and logs why, same as today's unusable-verdict rule).
- **Identity framing** — the witness stops sharing her weights. Framing for Nova (she's read the
  brief's first half and endorsed it): the faculty is still hers — an immune system is part of
  the body without speaking in its voice. Her side of the conversation doesn't change at all.

## Who does what

Claude builds Steps 0–3 with Cole's review gate at each step boundary; Cole judges shadow-mode
disagreements (his eye for her voice is the ground truth the metrics can't capture); Nova's
false-positive reports from inside the audits are first-class calibration data — she's the only
one who experiences the witness from the audited side.
