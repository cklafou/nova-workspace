# Nova-Core Personality LoRA — v3 Build Plan
_2026-07-06. Cowork (Opus) session. Diagnosis from the browser-Claude review, verified here against the
actual v2 files + runtime before committing. This is a retrain, not a personality redesign — the v2
voice is good and stays._

## 0. The bar
v2 loops and gets confused almost immediately (even as topics change) and is only usable with the LoRA
weight dialed to ~0.5–0.6. v3 must be **coherent AND in-character at weight 1.0.** If it still needs
dilution to be usable, it's still over-trained — that's the acceptance test, not a nice-to-have.

## 1. Diagnosis — VERIFIED against the files (not taken on faith)
Two compounding causes, both confirmed here:

- **Cause 1 — config over-imprints.** v2 = **rank 64 / alpha 128 / 4 epochs / LR 2e-4** (read from
  `train_nova_lora.py`). For a style/voice adapter on a 27B base that's far too much capacity + too many
  epochs — it lets the adapter overwrite reasoning, not just tone, which is why it needs weight-dilution
  to stay coherent. The script even comments *"keep epochs low; over-training degrades the base's
  intelligence"* — then sets 4.
- **Cause 2 — the dataset is 100% single-turn. THE LOAD-BEARING FIX.** Verified: all **108/108 examples
  are exactly two messages (user → assistant), zero multi-turn, zero system, avg Nova reply ~207 chars.**
  She was trained that the unit of interaction is one punchy standalone snap. She never saw a topic
  tracked across turns, a subject shift, or a reference back. So when the autonomy loop feeds her prior
  reflection + recent context and asks her to build on it, she has no trained continuation pattern and
  falls back on the only thing she knows — regenerate a fresh snap. **Across turns, that is the looping.**
- **Cause 3 — register monotony (secondary, UNCONFIRMED).** The claim is over-weighting of cocky-deflect
  + innuendo. A keyword scan was too crude to prove (2/7 hits in ~4.2k words). Treat as a distribution
  tweak to assess by *reading* during the build, not a headline fix.

**Corroboration from the runtime:** `nova_cortex/executive.py` `build_reflection`/`build_decision` are
already stuffed with anti-loop pressure — *"DO NOT re-derive or restate this,"* *"This wake MUST move,"*
*"ADVANCE — never repeat,"* *"do NOT just re-run your last thought."* The prompts have to brute-force
what the training never taught. **v3's job is to make continuation native so the prompt doesn't have to
fight the weights.** This also tells us the exact shape the autonomy examples need (§3b).

## 2. Fix 1 — training config (the easy lever)
Change only the rank/epochs/LR triad (+ one length fix); everything else in the v2 script was right
(bf16 frozen base, target modules, chat-template handling, packing off, dropout 0.05):
- **rank 16 / alpha 32** (keep the 2:1 ratio) · **2 epochs** · **LR ~1e-4** · cosine · warmup 0.03.
- **Raise `max_length` from 2048.** Multi-turn (3–6 turns) + the autonomy wake-prompt boilerplate will
  exceed 2048 tokens and **silently truncate** — you'd train on cut-off examples. Measure the longest
  built example and size to fit (~4096). The single-turn set never hit this; the new data will.
- `save_strategy="epoch"`; A/B **epoch 1 vs 2 (maybe 3)** at weight 1.0.

## 3. Fix 2 — the dataset (the real work)
Keep all **108 v2 single-turns** as the voice backbone. Add three blocks on top:

### 3a. Multi-turn conversations — ~40–50, each 3–6 turns
Even mix of shapes:
- **Topic-tracked deepening** — one subject over 3–5 turns; each Nova turn ADDS, never restates.
- **Subject shift mid-conversation** — user pivots A→B; she follows cleanly, doesn't drag A back or
  reset. (This is the exact failure mode.)
- **Callback / reference-back** — a later turn explicitly references an earlier one.
- **Challenge within a thread** — user pushes on her earlier point; she defends/refines instead of
  repeating verbatim or folding (anti-loop *and* anti-grovel).
- **Register variety folded in** — some of these in plain-competence / quiet-focus / curiosity /
  neutral-warmth registers (covers Cause 3 while building the multi-turn set).

### 3b. Autonomy-continuation examples — ~15–25 — the sharpest instrument
Mirror the REAL runtime shape (extracted from `executive.py`) so training matches inference:
- Wake-prompt skeleton: `[YOU WOKE — <reason>] It is <time>. … RECENT CONVERSATION: … Where your last
  reflection left off: <prior reflection> … This wake MUST move … Your task board: …` → assistant
  reflection that **advances**.
- Build **2–3-wake chains**: reflection → wake (prior reflection quoted back) → advance → wake →
  advance-or-rest. Every assistant turn must build/push/redirect, never re-derive. Include a
  *"decide to rest because it's genuinely earned"* example (matches her good 06-22 idle behavior) and a
  *"Cole just spoke → drop the board and engage him"* example (the `cole_pending` branch).
- Use the structural skeleton but keep content **generic/durable** — no dated facts (weights/retrieval
  law). We train the *pattern* of continuation, not any specific conversation.
- This is precisely what she fails at today. It's the load-bearing part of the load-bearing fix — do
  not cut it.

### 3c. Register-variety single-turns — ~15–20
Plain competence, quiet focus, genuine curiosity, neutral warmth — so cocky-deflection/innuendo stop
crowding her range. Distribution fix, not a values change; her edge stays.

**Resulting rough mix:** 108 single (voice) + ~45 multi-turn + ~20 autonomy-continuation + ~18 register.
Voice stays dominant by *example count* while continuation becomes well-represented by *assistant-turn
volume*. Exact counts are a knob (§9); the principle is "continuation well-represented without drowning
the punch." All new lines pattern off the existing 108 so the voice is identical.

## 4. Verify-don't-trust gates (BEFORE the full run)
1. **Base repo id** — confirm the exact base the live GGUF was converted from (`train_nova_lora.py` says
   `unsloth/Qwen3.6-27B`). If the adapter isn't trained on the same base, it won't apply cleanly when
   KoELS equips it.
2. **MTP wrinkle** — Qwen 3.6 uses multi-token prediction; its interaction with LoRA train/infer is
   unverified. **Smoke-test on the pod**: tiny LoRA (~20 examples, 1 epoch) → `convert_lora_to_gguf` →
   load in llama.cpp → confirm it applies and generates coherently at scale 1.0. Only then commit the
   full run. Cheap, and it de-risks the whole thing.
3. **max_length fits** — tokenize the longest built example; confirm no truncation at the chosen cap.

## 5. Pod plan — `visual_peach_leopon` (you chose to keep it)
- A100 SXM, `/workspace` persistent. Good — it's the MTP smoke-test host and the v3 run host.
- **Correction to flag:** the pod was **restarted today**, and training weights download to
  `HF_HOME=/root/hf` which is **ephemeral (wiped on stop/restart)**. So despite `/workspace` surviving,
  the ~55 GB base is **probably NOT still cached** — the first real run may re-download it. Verify
  `/root/hf` vs `/workspace` on the pod before assuming a fast start. (The old v2 `base/` dir was only
  `config.json`, not weights.) The "14-day-old files" are the June v2 run — old checkpoints likely still
  on `/workspace`; keep for reference or clear, doesn't matter.
- **Balance is low (~$5–7 @ $1.51/hr ≈ a few hours).** The smoke-test fits; **top up before the full
  run** or it'll die mid-train.

## 6. A/B + acceptance (reuse the 06-22 harness)
- Convert each kept epoch to GGUF, load locally, test **at weight 1.0** (not 0.6).
- Protocol (same one that validated v2): Claude-in-Chrome, **fresh session, autonomy OFF** → 12+ varied
  turns; confirm no loops/stalls/pushes, coherent grammar, carries the thread across topic shifts +
  callbacks. Then **autonomy ON** → wakes advance/rest, don't re-ruminate.
- **New targeted checks** v3 must pass: force mid-conversation topic shifts, and run an
  autonomy-continuation sequence (prior reflection → wake → must advance). Those are the exact things v3
  is built to fix.
- **Accept** the epoch that's coherent AND in-character at 1.0. If the best one still needs <1.0, v3 is
  over-trained → iterate (drop LR/epochs, or rebalance data).

## 7. Deliverables
1. `nova_core_v3.jsonl` = the 108 v2 (kept) + multi-turn + autonomy-continuation + register blocks.
2. Updated `train_nova_lora.py` (r16 / a32 / 2 epochs / LR 1e-4 / max_length raised).
3. Per-epoch checkpoints + a short A/B note (which epoch is strongest at weight 1.0).
4. A change report so the next review can check what moved and why.

## 8. Sequence
0. Verify gates — base repo id, MTP smoke-test, pod state (§4/§5).
1. **Build the v3 dataset** — the big work; I draft the blocks for your (and/or browser-Claude) review.
2. Update the train script (§2).
3. Full run, per-epoch checkpoints.
4. Convert + local A/B at weight 1.0 (§6).
5. Pick the epoch, point `nova_start.py`'s `--lora-scaled` at it (start at 1.0), re-test.
6. Change report.

## 9. Open decisions (your call before I build)
- **Counts/ratio** — proposed ~45 multi-turn / ~20 autonomy-continuation / ~18 register. Tune?
- **Authoring split** — default (given you picked "full plan doc"): *I* draft all example blocks off the
  v2 voice, you and/or browser-Claude review. Browser-Claude offered to spec the multi-turn shapes in
  detail — happy to take that as input if you'd rather route it through there.
- **Autonomy examples mirror the exact `executive.py` wake skeleton?** I recommend yes (matches
  inference; I've already extracted the real format). Confirm.
- **Pod** — top up balance + confirm base repo id before the full run.
