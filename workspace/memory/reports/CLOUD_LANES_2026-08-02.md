# CLOUD LANES — skippable cloud offload for Nova
_2026-08-02. Cole's idea; shaped with Claude (Cowork). Cole approved the direction same day._

Cole's framing: use cloud resources for anything that doesn't need immediate local compute, with
a safety skip when the cloud can't be reached — so local VRAM/RAM stay free for what's actually
urgent. Sort capabilities into `Local_Only` / `CloudLocalHybrid` / `Cloud_Only`, with a resource
check deciding placement for hybrids.

## First principles (the guardrails everything below hangs on)

1. **The body stays local and singular.** No cloud copy of her architecture, memory, board, or
   identity — a second body is the shadow-package incident at architecture scale (see
   2026-08-02, and the two-crawlers cleanup before it; one source of truth, Design Principle 12).
   The cloud hosts **stateless organs-for-hire**: pure functions, request in → result out, no
   memory, no identity. Pluck the cloud and Nova is whole — slower and dimmer, never less her.
2. **Fail-open, always, loudly.** Cloud unreachable, over deadline, or over budget → skip, log a
   `cloud_skip` pipeline event with the reason, continue local (or without). Same law as the
   witness's unusable-verdict rule: an enhancement must never become a silent drop.
3. **Opt-in per capability.** Default is `Local_Only`. Most of her scripts are tiny IO-bound
   Python where network overhead exceeds the compute — offloading those buys nothing. A tool
   earns a cloud lane only where it measurably pays: GPU-hungry, RAM-hungry, or batch.
4. **No cloud dependence in any lane where a human is waiting.** Interactive paths may *prefer*
   cloud under contention (see voice, below) only with a local fallback resident and able to take
   over instantly; the gate path (inline witness) is forbidden cloud outright.

## Placement = latency lane × data class × statefulness

**Lanes**
| Lane | Examples | Cloud policy |
|---|---|---|
| Gate/inline (human waiting on the reply itself) | inline witness, claim classifier, sentence-commit | **Never cloud** |
| Interactive-adjacent (human hears/sees output as it renders) | TTS synthesis, STT | Hybrid allowed with resident local fallback + per-chunk deadline |
| Deferred (seconds-to-minutes is fine) | witness-heavy second opinions, deferred voice verifications, image gen | Hybrid, cloud-preferred under local contention |
| Batch/overnight | replay scoring, corpus builds, embedding backfills, nightly reviews | Hybrid, cloud-preferred |
| Off-box entirely | v7+ LoRA training runs, frontier-model verdicts | `Cloud_Only` |

**Data classes** (Cole adjudicates the lists; these are the proposed defaults)
- **N0 — never egress:** `Nova_Created/Cole_journal/` data (posture, sleep), `memory/COLE.md`,
  anything about Cole's body or private life. No cloud call may carry N0 content, period.
- **N1 — egress with standing consent:** RULED BY COLE 2026-08-02 — "anything that git can get is
  already allowed into a cloud. The witness is basically the same." Governing standard: content
  classes that already flow through git/Drive sync are cloud-eligible, and witness payloads
  (draft + wire excerpts + receipts) are explicitly blessed for the witness lane. (Precision note
  for the record: `logs/` is gitignored, so the wire itself isn't literally in git — the blessing
  covers conversation-class content by Cole's intent, not by the gitignore boundary.)
- **N2 — free:** public data, generated art prompts, model configs.

**State:** anything that writes her memory/board/journal is `Local_Only` by definition. Cloud
functions return results; her local body decides what becomes memory.

## Wiring — three small pieces, mapped to her existing anatomy

1. **Sense:** `proprioception` grows resource awareness — local VRAM/RAM/CPU headroom plus cloud
   endpoint reachability, read from a status file the transport tool maintains (senses read
   traces through a body-owned contract; remove the tool and the sense reports "nothing there").
2. **Decision:** a pure placement policy in the executive: `(lane, data_class, resources,
   budget) → local | cloud | skip`. Deterministic, loggable, testable — and shadow-mode first:
   for its first days the broker only LOGS what it would have decided, before anything obeys it.
3. **Transport:** `general_tools/cloud_call.py` — auth, timeouts, retries, the budget ledger
   (`memory/cloud_ledger.json`: per-lane counters + monthly cap), and `cloud_call`/`cloud_skip`
   pipeline events (lane, bytes, latency, est. cost) so the Pipeline tab tells the whole story.

## Controls

- **Kill switch:** one flag (`nova_config.json → cloud.enabled`) turns every lane off; the
  system must be indistinguishable from pre-cloud Nova when it's off.
- **Pluck-day:** one deliberate offline day a month proves the skippability is real, not
  theoretical. If anything degrades beyond "slower and dimmer," that thing got load-bearing and
  gets demoted.
- **Budget:** monthly cap + per-lane quotas in config; ledger visible to Nova (it's her body's
  spend; she should be able to read it) and to Cole.

## Voice goes hybrid (Cole, 2026-08-02)

TTS is `CloudLocalHybrid` with hard rules:
- Local engine (Chatterbox-Turbo class, ~1.5-2GB) is always resident and always primary.
- Cloud synthesis is *preferred* only when BOTH: local VRAM is genuinely contested (huge KV
  growth, painting session — proprioception says so) AND the cloud endpoint answers within the
  per-sentence deadline (~700ms to first audio chunk).
- **Same voice both sides, non-negotiable:** identical engine family + identical reference
  embedding locally and in the cloud, or no switching happens. Her voice is her identity; a
  timbre shift under load would be the uncanny version of the thinking-leak.
- Placement is per-utterance, never mid-sentence; a cloud failure mid-conversation means the
  local engine finishes the next sentence and a `cloud_skip` is logged. Nobody hears the seam.
- STT same pattern later if ever needed (Moonshine is small enough that it may never be).

## Rollout order (each lane lands alone, fail-open from day one)

1. **Cloud witness-heavy** for the deferred lane — smallest possible first lane, key already on
   the machine (`ANTHROPIC_API_KEY`), pennies at deferred volumes. This is Witness plan Step 6.
2. **Resource sense + placement policy in shadow mode** — decisions logged, nothing obeys yet.
3. **Batch lane** — nightly replay scoring / corpus work through the same transport.
4. **TTS hybrid** — only after voice v1 is proven local-first.
5. **v7+ training as `Cloud_Only`** — rented GPU per run, the single biggest thing the local
   box cannot do.

## Providers + costs (researched 2026-08-02; the ledger revisits this with real usage)

Two different kinds of "cloud" — don't conflate them:
1. **Managed inference APIs (no provider account for compute, nothing uploaded, no server).**
   The vendor permanently hosts THEIR model; each HTTPS call carries its own payload (the witness
   prompt) and nothing of Nova persists there. Only prerequisite: the API key already in her env.
   This is why the heavy-witness lane is buildable TODAY — `cloud_call.py` is an HTTP client, not
   an environment. Cost (Anthropic, current): Haiku 4.5 $1/M in, $5/M out; cache reads 0.1×;
   Batch API 50% off, stackable. A ~2.5K-token verdict ≈ $0.003 standard, ~$0.001-0.002 with
   caching/batch → even 200 deferred audits/day lands around **$6-20/month**.
2. **Rented GPU compute — account EXISTS (Cole, 2026-08-02: LoRA training already runs on RunPod
   pods).** Division of labor, per RunPod's own guidance and ours: **pods for training** (long
   continuous jobs; serverless's ~2-3x per-second premium buys scale-to-zero that a never-idle
   job can't use; automate lifecycle via runpodctl/API so a forgotten pod can't idle-bill),
   **serverless for bursty inference lanes** (TTS, image gen, self-hosted heavy witness) —
   per-second billing, scale-to-zero, no egress fees, ~$0.34/hr-class 4090. **Vast.ai** stays the
   cheaper checkpointed-training alternate (~$0.31/hr interruptible). Korea latency: RunPod's
   AP-JP-1 (Fukushima, H200s headline) claims 8-50ms for JP/KR users vs 150-200ms US/EU — verify
   on the console whether serverless + cheap GPU classes are offered there before counting on it
   for the TTS deadline. **Anti-pick** unchanged: no always-on rented box until the ledger says so.

**Weights ruling (Cole, 2026-08-02):** `models/` is gitignored for SIZE, not privacy — and LoRA
training already runs on RunPod pods, so weights/corpus egress is established practice, blessed.
(The earlier "weights caveat" here is void.)

## Non-goals

No cloud copy of the body. No always-on rented GPU until the ledger shows usage that justifies
one. No cloud in the gate path, ever — the thing that decides whether her words are true stays
within arm's reach of the words.
