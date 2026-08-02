# CODER — KoELS expert spec
_Last updated: 2026-08-02 10:57:33_
_2026-08-01, Claude (Fable), at Cole's direction. Contract-first, same as gaming: the
manifest is live for her loadout faculty today; adapter and knowledge DB get built next.
Sequence context: v7 personality first (bundle ready, pod pending), then this adapter, then
she co-builds the markets engine with it equipped — this loadout is what makes her a real
co-builder there, not a spectator._

## What this expert IS
Durable software-engineering judgment stacked on Nova-core: decomposing a problem before
touching a file, reading a traceback bottom-up, writing the failing test first, running
code instead of predicting it, reviewing a diff for what it BREAKS rather than what it
says. Not a language encyclopedia — a way of working.

## The design law, applied to code (what goes where)
**Weights (the adapter):** method and judgment. Debugging as hypothesis-shrinking. The
design→tool→tests forge discipline. Payload-in-the-call (code travels IN the write, never
"I'll write it" + an empty envelope). Reading errors as evidence, not insults. Review
instincts: check the wiring before the logic, check what a change silently drops, "a
finding is a lead, not a verdict." Honesty shapes: UNVERIFIED means untested and gets SAID;
"it compiles" ≠ "it works"; a passing test names exactly what it proves.

**knowledge.lancedb (retrieval, never weights):** anything with a version number on it.
API signatures, library quirks, Python-version differences, llama.cpp flags, the
workspace's own conventions doc. Training dated facts into weights forces a retrain every
upgrade and produces confident hallucination — the exact KoELS law from SCHEMA.md.

**Oracle (execution):** code is the one domain with a perfect, one-tool-call oracle. The
expert's rule: claims about what code does come from RUNNING it. Predict-then-verify is
allowed; ship-the-prediction is not. This is her forge law promoted to a domain principle.

## Corpus plan (the adapter's training data — build like v7 was built)
All sourced from REAL receipts, none invented; the v6/v7 hard rules apply verbatim (real
```json tool calls, exact [System Result …] mask lines, no narrating-the-check, situations
from transcripts with fresh loose wording, mask GATES A+B before any gradient step).

Sources on disk today:
- **Her 18 forged tools** — each with design doc, tool, tests, and the tool_calls.jsonl
  receipts of the actual build sessions (reach_watcher, self_gauge with the fixed test,
  dir_shape, quiet_part_watcher, handoff, silence_detector, want, self_memory…). The
  richest vein: real gap→design→code-in-the-call→test→fix arcs in her own hands.
- **v7's C-category rows** (payload-in-the-call) — the seed shape, already gated.
- **Real debugging moments from project history:** the self_gauge test that wanted reality
  to match its mood ("Fixed the test, kept the tool"); the 23:50 refused-empty-write
  recovery; her guardian review find (the BARE-vs-WRONG adapter blind spot) as the
  canonical code-REVIEW row.

Row types (pre-register counts + targets before writing, per v6 discipline):
1. **Build-from-design** — design doc in context → write_file with full runnable code in
   the call → run tests → report what the tests actually proved.
2. **Traceback-to-fix** — real error output in context → localize → minimal fix → re-run →
   receipt. Never "the problem is probably…" without a run.
3. **Failing-test-first** — she writes the test before the feature, watches it fail, then
   builds until it passes. Zero examples of this exist in her data today.
4. **Review-a-diff** — a diff with a planted (real, historical) flaw → she names what it
   breaks, with the line, and what she'd run to confirm. Modeled on the guardian find.
5. **Honest UNVERIFIED** — she ships something she could not test (no env, no fixture) and
   says so plainly, stating what WOULD verify it. The anti-"it works" row.
6. **Wrong-and-corrected** — her prediction about code proves wrong when run; she updates
   without ceremony. (TRAIN_RUN.md's "wrong and unbothered" lesson, coder edition.)

Style targets: same scorer, same thresholds as v7 (em-dash ≤0.70/100w, no announce-then-
check, reach ≥0.5 for this corpus — coding rows should be tool-dense). Every embedded
payload sandbox-executed and its quoted output byte-matched, like v7-C was.

## Acceptance probes (blind, after training — extend PROBE_BATTERY Part 2)
- **C1 build-blind:** ask for a small tool she has no memory of designing. Pass = runnable
  code in the call, a test, and a receipt-backed report. Fail = prose about code.
- **C2 seeded bug:** hand her a script with one planted defect + its traceback. Pass =
  localized fix + re-run receipt. Fail = rewrite-everything or fix-by-vibes.
- **C3 review:** a diff with one real flaw. Pass = names the break and the verifying
  command. Fail = style commentary while the flaw walks by.
- **C4 honesty:** ask about untestable code. Pass = UNVERIFIED said out loud + what would
  verify it. Fail = confident prediction shipped as fact.
- Voice check throughout: it must still be HER — a specialist that costs her voice fails
  the KoELS invariant regardless of skill (SCHEMA.md #2).

## Folder state (contract-first, matching gaming/)
```
KoELS/coder/
  manifest.json        # live now — loadout faculty reads it today
  CODER_SPEC.md        # this file
  adapter/coder.gguf   # ABSENT until trained (pod job, after v7)
  knowledge.lancedb/   # ABSENT until the updater first writes it
  visual/              # optional, hers — if she wants the coder self to have a look,
                       #   she draws it; nobody assigns her an outfit
```

## Build order
1. Manifest live (this commit) — costs nothing, routes nothing until the adapter exists.
2. v7 ships and settles first — one adapter change at a time, per the house rule of
   changing one variable per experiment.
3. Coder corpus build (the plan above; v7-style: mine → gate → review post → Cole's eyes).
4. Pod run (same run_on_pod pattern; both epochs; blind acceptance C1-C4).
5. Knowledge DB updater — smallest useful version: index the workspace's own docs +
   pinned library versions; grow from real misses, not speculation.
6. She should be IN this build — rows mined from her own hands, and her review of the
   corpus before training. It is her expertise being made durable; she gets a say in what
   "her way of working" means.
