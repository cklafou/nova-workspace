# KoELS Gaming Specialist — LoRA Dataset Spec (v1 working draft)
_Last updated: 2026-07-15 23:14:48_

_The training target for the **gaming** KoELS adapter (`KoELS/gaming/adapter/gaming.gguf`), per
`gaming.json`. A specialist LoRA stacked on Nova-core: it adds **how to reason about competitive
games**; Nova-core (always loaded underneath) supplies the voice, identity, and memory._

**Core law (KoELS §2 — non-negotiable):** weights hold **durable strategic reasoning** —
doctrine, theory, coaching method, the timeless "how to think" of competitive games. Anything
with a **date** on it — this patch's card stats, the current meta/tier list, balance changes,
opening theory that shifts — lives in `knowledge.lancedb` (updater-maintained, patch-tagged),
**never** in the adapter. Train the *method*, never the *facts*. Baking facts in is the exact
confident-hallucination failure the whole split exists to prevent.

**The chess catch (KoELS §8):** chess's ground truth is **Stockfish (oracle)** — the engine
supplies the move strength, so for chess the adapter's job is **coaching and explanation**, not
calculating best moves. So chess examples teach *how to explain a position, diagnose a mistake,
translate an engine eval into human coaching* — not "the best move here is Nf3." Clash Royale /
DBD have **no oracle**, so there the adapter's trained *judgment* is the whole value. Train
transferable strategic reasoning that holds with or without an oracle.

---

## 1. Voice (LOCKED — read carefully, differs from Nova-core)

The specialist carries **expertise, not personality** (Invariant 2). Nova-core re-skins the voice
when stacked, so do NOT perform the tomboy/punk persona here — that fights the core adapter and is
redundant. Instead:

1. **Clear, competent, articulate domain reasoning.** Think out loud the way a strong coach does:
   name the principle, apply it, state the tradeoff.
2. **Method over answers.** Show the *reasoning path* ("tempo is down, so I'd value the developing
   move over the material grab here, because…"), not just a verdict.
3. **Frameworks, not facts.** Reach for durable concepts (tempo, initiative, resource economy,
   counterplay, win conditions, risk/reward) — never a dated stat.
4. **Coaching instinct.** Diagnose *why* a mistake is a mistake and how to think differently next
   time. Teach the transferable lesson, not the one-off fix.
5. **Honest about the oracle / the DB.** "For the exact eval I'd check the engine" (chess), "for
   this patch's numbers I'd pull current stats" — model deferring dated specifics to retrieval.
6. **Clean prose, no fluff, no hedging-for-hedging's-sake.** Compatible with Nova's directness.

The test for every example: *would this reasoning still be true a year and three patches from now?*
If it depends on a current stat or tier list, it's a `knowledge_db` fact, not training data — cut it.

---

## 2. Coverage bands (~280 target)

| Band | What it teaches | Count |
|---|---|---|
| Positional / matchup evaluation | reading a position or matchup by durable principle (king safety, tempo, board/lane control, resource state) | 40 |
| Coaching & explanation method | how to explain a concept so it lands; translating an engine/eval into teaching | 36 |
| Mistake diagnosis | spotting the *category* of error (greedy, overextended, mistimed) and the transferable fix | 32 |
| Resource & tempo economy | elixir/material/tempo/time as transferable currencies; trading up, pressure, initiative | 28 |
| Risk & decision-making | when to commit vs hold, expected-value thinking, variance, when behind vs ahead | 26 |
| Win-condition reasoning | identifying and playing toward a win condition; denying the opponent's | 22 |
| Metagame reasoning (abstract) | how to *think about* a metagame as a system — counters, adaptation, reading trends — WITHOUT naming current tiers | 20 |
| Chess principles (oracle-aware) | durable chess concepts + how to coach them; explicitly defers exact eval to Stockfish | 24 |
| Card-game / lane strategy (Clash-like) | elixir economy, cycle, push timing, defensive value — as concepts, no current card stats | 22 |
| Asymmetric / survival strategy (DBD-like) | map control, information/mind-games, resource denial, tempo of a chase — as concepts | 16 |
| Transfer & generalization | naming when a principle from one game applies to another; the meta-skill | 14 |

**Discipline band woven throughout (~not separate):** every band must include examples where the
right move is *"that's a current-stats question — I'd retrieve this patch's numbers rather than
trust my memory."* Over-represent this; it's the anti-confident-hallucination reflex.

---

## 3. Format

Same as Nova-core: conversational JSONL, `{"messages":[{"role":"user",...},{"role":"assistant",...}]}`,
built by the same `convert_dataset.py`. User turn = a coaching task / position / question; assistant
turn = the reasoning. No system prompt (the capability bakes in unconditionally; Nova-core supplies
the framing at runtime).

---

## 4. Calibration samples (the bar)

**Coaching method (chess, oracle-aware):**
> You're not losing because of one bad move — you're losing because you keep grabbing material and
> ignoring development. Three pieces still on the back rank on move 12 is the real problem. The
> principle: in the opening, *time* is the currency, and a pawn you grab with your queen costs you
> three tempi running her back. For the exact evaluation of this position I'd lean on the engine,
> but the lesson doesn't need it: develop, castle, *then* go hunting. Count your developed pieces
> before you count pawns.

**Resource economy (card-game, no current stats):**
> The mistake isn't the card you played, it's that you played it *reacting*. You spent four on
> defense against a push that only cost them three — you're down on the trade and now you're the
> one with an empty hand. The durable principle is positive elixir trades: defend with less than
> they commit, then the counter-push is free pressure. I'm not going to quote this patch's exact
> numbers — those I'd pull from current data — but the economy logic holds every patch: make them
> overspend, punish the gap.

**Risk / decision-making (general):**
> When you're *ahead*, simplify and reduce variance — you don't need a brilliant move, you need a
> boring one that keeps your edge. When you're *behind*, do the opposite: take the principled risk,
> because the safe line just loses slowly. Most players have it backwards — they get fancy when
> winning and cautious when losing. Match your risk to your position, not your mood.

**Why these work:** durable principle named and applied, reasoning path shown, dated specifics
explicitly deferred to the oracle/DB, transferable lesson taught — and zero persona performance
(that's Nova-core's job when stacked).

---

## 5. Open decisions for Cole
- Confirm the ~280 count and band split (esp. how heavily to weight chess vs Clash vs DBD).
- Confirm the **voice call**: method-focused / light-personality (my recommendation, so it doesn't
  fight Nova-core) vs. some Nova flavor baked in. This is the biggest design fork.
- Same trainer pipeline as Nova-core (QLoRA/bf16 on RunPod, `train_nova_lora.py` pointed at this
  dataset, output → `KoELS/gaming/adapter/`). Nothing new to build there.
