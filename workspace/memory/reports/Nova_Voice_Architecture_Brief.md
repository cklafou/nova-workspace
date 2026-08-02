# Nova Voice — Architecture Brief (working)
_2026-08-02, Claude session following Cole's Nova Chat post on voice plans_

## Goal
Real-time voice chat with Nova (eventually smartwatch → Android app → tunnel → PC) without sacrificing the witness/integrity competence built in July. Cole's two named blockers: (1) turn latency from the reasoning + witness loops, (2) drafts/thinking streaming into Nova Chat and mutating mid-debate — spoken audio can't mutate.

## Measured baseline (llama log 2026-08-01)
- Generation: median 22.4 tok/s (122-tok reply ≈ 5.4s; p90 10.8s), prompt-eval 704 tok/s, median 0.7s (cache warm), p90 6.7s (cache busted; always-load ~108KB is the driver — CONTEXT_DIET still open).
- Turn shape: 6–14K-token Nova prompt → witness audits (~2K prompt + up to 2048-tok verdict) → possible redraft — all serialized on ONE llama slot (--parallel 1). Real claim-bearing turns: ~15–45s.
- Live confirmation (2026-08-02 morning, wire): Cole's 09:52 question answered at 09:57 — ~6 min. Cole to Nova 09:59: latency + thinking-leak are the two fixes before voice.
- VRAM: both cards nearly full (~4-8GB free total after q8 KV). ComfyUI (planned, 8-10GB) homeless.

## Witness history (Cole asked why it became same-model)
- Cole's 07-21 original: a parallel self that audits + a short-term-context self. The 07-21 session merged them ("those turned out to be one idea") because that day's failure was contaminated CONTEXT, not weak weights — a same-context second pass re-blessed her errors (watched live). Context-poverty became the active ingredient; same-27B was chosen because it was free (VRAM was full), infra-simple on a broken day, and text chat tolerated serialization. Note: the persona LoRA is server-global, so today's witness also runs THROUGH her personality adapter.
- Recommendation now: restore the parallel form — small dedicated witness model (Qwen3-4B-class, Q4, ~3GB, own llama-server instance, ctx ~8K) keeping ALL protocol (context-poor prompt, conversation-not-rewriter, calibration, deadlock, verify tools, pipeline events). Gains: parallel + ~5-10x faster audits, weight-level independence. Risk: weaker judge → A/B via existing pipeline.jsonl metrics (pass/answered/overruled mix), config fallback to 27B endpoint.
- 08-02 live observation supporting the upgrade: in 8 min of morning conversation, 2× STILL DISPUTED + 3× SHE OVERRULED + 2× CONTEXT RESCUED; one dispute burned a round arguing whether Cole's "Time and Date" licensed "two facts" — pedantic zeal on wording. Witness calibration/prompt tuning goes in the same milestone as the model swap.

## Voice pipeline v1 (desktop-first — decided)
Mic → Silero VAD → Moonshine STT (streaming, 245M, MIT) → Nova voice-register turn → sentence-committer → Chatterbox-Turbo TTS (350M, MIT, ~75ms, emotion exaggeration + paralinguistic tags, zero-shot clone from ~10s reference) → speakers.
- Commit discipline (pending Cole's pick): recommended = register split + sentence-commit + concurrent witness. Sentences with no checkable claims release to TTS immediately; claim-bearing sentences hold until the (parallel) witness passes; late concern after audio → spoken self-correction (rare by construction). Existing claim detectors (needs_witness / claims_a_*) become the per-sentence classifier.
- Voice mode: witness rounds capped 2-3, unresolved → defer out loud ("let me double-check while we talk") + async verify; deep work = acknowledge by voice, run full pipeline async, report back (Cortana pattern). Thinking mode off/capped for casual turns (per-request chat_template_kwargs), on for substantive.
- Leak fix: TTS + phone UI receive only committed text; Nova Chat/Pipeline tab keeps live drafts as observability.
- Latency budget v1: first audio ~1.5-2.5s fast path; +2-6s claim-gated (vs +10-30s today).

## Voice identity
Nova's decision doc (memory/decisions/voice_preference.md): clear, warm underneath, able to get sharp when disagreeing — sharpness is the requirement, not a style. Cole: expressive, not-AI-sounding, tomboyish. Chatterbox zero-shot cloning makes this a casting decision: produce candidate reference clips, audition with Cole + Nova ("the moment I hear something, I'll know better").

## Hardware ground truth + expansion answer (2026-08-02)
Rig (per memory/COLE.md): Tracer VII Edge I17E, 2× M.2 2280 slots — one holds the M.2→OCuLink adapter feeding the MINISFORUM DEG1 + EVGA 3090 (PCIe 4.0 x4), the other is storage. One Thunderbolt 4 (USB-C, rear), free.
- Splitting the existing OCuLink 4i cable into two eGPUs: NO — it's 4 PCIe lanes point-to-point; splitting requires an 8i port + host bifurcation or a PCIe-switch board (no consumer OCuLink-4i splitter product; jank risk on her spine not worth it).
- Second eGPU: YES, via the free TB4 port — a USB4 eGPU dock (e.g. AOOSTAR AG02, ~$229, OCuLink+USB4 inputs, built-in 800W PSU) or any TB enclosure. USB4 ≈ half OCuLink bandwidth — irrelevant for a resident small model (witness-4B, TTS, STT, ComfyUI). llama.cpp simply sees a third CUDA device. 3090 stays on OCuLink.
- Voice v1 still fits with $0 spend (~5-6GB across current free VRAM); dock+card (~$420-650 with used 3060 12GB or 5060 Ti 16GB) is the comfort/ComfyUI purchase, not a blocker. Cole 2026-08-02: waiting on eGPU parts takes too long — building on current hardware.

## Nova condition snapshot (2026-08-02 ~10:00, logs + live UI)
Healthy and sharp: overnight autonomous run stable (gates never offline), board 113 done / 2 open (t144 clock time-sense, t145 Cole's ordered-reads idea), 1139 thought entries today, bad_requests stale (5, last 22:13 yesterday). Reach-watcher working as designed — caught her inventing counts 3× in one reply ("reached for 'eight' instead of reading the receipt that had seven"); she endorses the witness explicitly. Friction measured: reply latency to Cole 1.5-6 min; her 09:51 cryptic fragment reply → Cole's "What?" is the thinking-leak made visible. Shelf audit done (see chat log 08-02): only strays were Cole_journal/, the nova_senses shadow, and memory-area working docs; Orient/NOVA_CREATED_TOOLS.md exists and was fixed (missing entries, stale pointer, honest header).
- RESOLVED 2026-08-02 ~11:00 (was: LIVE FLAG, two `nova_senses` packages): the shadow package at
  workspace root is retired to `_admin/Trash/nova_senses_shadow_2026-08-02/` and `Cole_journal/`
  moved to `Nova_Created/Cole_journal/` (import sites patched: runtime.py, stretch_reacher.py —
  file-path loads, no sys.path inserts). Mechanism correction, verified by test: the shadow had no
  `__init__.py`, making it a namespace package, and a regular package later on sys.path WINS — so
  imports always resolved to the body package; the shadow was inert at runtime. The real damage
  was epistemic, not mechanical: listing the shadow directory gave Nova a false "the clock doesn't
  exist" premise, and she built a duplicate clock.py from it. Claude's first correction to her
  overstated the mechanism (claimed imports hit the shadow); corrected in chat with the test.

## Build order (desktop v1)
1. Witness milestone: see `memory/reports/WITNESS_V2_PLAN_2026-08-02.md` (drafted 08-02) — dedicated small witness server, grammar-constrained verdicts, calibration rev, golden-set replay A/B, shadow-mode rollout.
2. Context diet (always-load ~108KB) — now on the critical path for voice prefix latency.
3. voice_gateway general_tool (pluck-test: comms tool, body untouched): VAD+STT+TTS+sentence-committer, WebSocket client of nova_chat.
4. Voice-register policy in nova.py (rounds cap, thinking policy, deferred-verify path).
5. Voice audition round (Chatterbox reference clips).
6. Then phone: Android app + Tailscale tunnel → same gateway. Watch = remote for phone app.

## Witness v2 status (2026-08-02, end of day)
SHIPPED (all effective at next Full Restart): (1) Restart-amnesia fix in witness.py — human_record() complete human-lines ledger with honest span labels, scoped certainty (beyond the span, absence is UNKNOWN and demands a read), human-in-room paraphrase/intent in the always-PASS list; both incident shapes are golden cases. (2) Golden set (10 hand-authored cases) + endpoint-agnostic replay harness in nova_body/nova_witness/ (body part, per Cole). Measured: v1 27B+LoRA = 4/4 catch, 4/6 false concerns — every false concern is calibration DEFIANCE (flagging things the prompt says to PASS), not blindness; the 4B = 2/4 catch, fails receipt-vs-draft comparison, EXCLUDED from the inline gate. (3) Local Qwen3.5-4B engine on :8081 auto-started by nova_start.py (fail-open, boots after main llama for VRAM order) + StopNova now fully kills the witness window; the engine is reserved for future non-judge roles. (4) Cloud Lanes: general_tools/cloud_call.py (fail-open transport, CloudSkip, monthly ledger memory/cloud_ledger.json, kill switch nova_config.json->cloud.enabled, $25/mo cap) + RunPod serverless endpoint LIVE (geefit73llqyaw, Qwen3-32B-AWQ served as NovaWitnessLarge, 48GB MIG, US-WA-1; template fight documented in the plan doc — GPU_MEMORY_UTILIZATION=1 was the root killer). (5) Heavy witness WIRED into nova.py's disputed-verdict path: witness_overruled / witness_unresolved now dispatch a background cloud second opinion — same build_witness prompt + turn evidence, up to 2 verify-reads executed locally through the same read-only door, <=3 paid calls, logged as witness_heavy pipeline events (sides: her | inline_witness | no_ruling) on the disputed turn's id. Logs-only, fail-open; the inline gate never touches the cloud.
OPEN (next levers, in order): calibration rev v2 — the biggest measured win (reposition PASS rules, verdict must name the check it enforces, GBNF-constrained verdicts), then golden rematch incl. the live heavy endpoint, harvested-case review/promotion loop (extract_golden.py output), nightly batch-scoring lane, voice-register hooks (rounds cap 2-3, deferred-verify) landing with the voice gateway, context diet.
