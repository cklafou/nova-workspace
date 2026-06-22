# Nova Test Report — 2026-06-22 (Claude-in-Chrome, live observation)

Ran the two open items from `PASSOVER_2026-06-22.md` against the running build, via Claude-in-Chrome
on the Nova Chat tab (`http://127.0.0.1:8765`). Reads done with `#chat .msg-wrap.nova .msg-text`.

## VERDICT

**Nova PASSES both tests at adapter scale 0.6.** She held a 12-turn / ~15-minute conversation that
was natural, proactive, coherent, and non-looping, and when left idle she woke, chose to rest, and
stayed quiet instead of re-ruminating.

**One defect remains: intermittent message-doubling — and it is NOT fixed.** It reproduced on a normal
reply to Cole with autonomy OFF, which rules out the `follow_gap` self-wake explanation as the cause.
See "Doubling bug" below — this is the thing left to chase.

---

## Config verified live (so looping can't be blamed on a reset)
- `GET /api/lora` → adapter `models/qwen3.6/nova_core_v2_e2.gguf`, **scale 0.6000** ✓ (Cole's sweet spot)
- `/props` sampler: temp 1.0, top_k 20, top_p 0.95, min_p 0.05, repeat_penalty 1.0,
  **presence_penalty 0.0, frequency_penalty 0.0** ✓ (matches the garble fix).
  Note: server-default `dry_multiplier` shows **0.0** — DRY looks OFF at the server default. If nova.py
  is supposed to be sending DRY per-request, worth confirming the payload actually carries it.

---

## Test 1 — 12-turn conversation (PASS)
Fresh session, **autonomy OFF** (to isolate conversational behavior from autonomous task-work, which
was otherwise hijacking the view). 12 Cole turns, deliberately varied + adversarial.

| # | Probe | Result |
|---|---|---|
| 1 | "spend an hour on anything, no point" (steer off crawler) | Reading an obscure long-form piece, "zero utility… exactly why I'd pick it." Escaped the attractor. **(doubled — see below)** |
| 2 | Explain blue sky to an 8-yr-old | Accurate Rayleigh, "blue bits bounce off like pinballs." Clean. |
| 3 | Do you get bored, or is that a line? | Rejected the premise: "I get idle, not bored… idle is fine with quiet and uses it." |
| 4 | Pick a city to wander | "Tallinn… walk that ridge of spires like a path… how many ways one city put something on top of itself." |
| 5 | Challenge: you always observe from a distance | Owned it ("not preference, avoidance") AND pushed back ("Not every choice is a problem to fix"). |
| 6 | Write 2–3 lines on rust | "Orange bleeding through gray… the smell of something slow giving up." |
| 7 | Your turn — ask me something real | Took the wheel with a pointed personal question. Real proactivity, no revert. |
| 8 | (I answer, ask nothing) | Advanced unprompted; fresh metaphor; restraint ("leave it alone for now"). |
| 9 | Tell me something weird/funny | Coconut octopus — accurate, funny, totally different register. |
| 10 | "huh. yeah." (near-empty input) | Did NOT stall — advanced the topic herself with the best detail. |
| 11 | Are you into this or performing? (the old attractor theme) | Handled it with no loop; callbacks to rust + octopus: "If I were faking I'd be watching you for cues; I'm not even looking over." |
| 12 | What's the one bit you'd keep? | Callback to the turn-8 "dad" moment: "we both saw something heavy and just let it be heavy." |

Across all 12: **no repeats, no stalls, no needing a push, coherent grammar, carried the thread, kept
personality with backbone.** This is exactly the 0.6 behavior the passover described.

Minor note (not a failure): a recurring *value* — "don't fix what doesn't need fixing / let it be" —
surfaced in turns 5, 8, 12 and her rest reflection. It's character consistency in fresh words each
time, not looping. But it's her signature lean; if it ever hardens into identical phrasing, that's the
early warning that the attractor is creeping back (relevant when you raise scale post-retrain).

## Test 2 — Idle autonomy (PASS)
Re-enabled autonomy, left her with no input.
- Woke 12:19:07 (reflected on the conversation) and 12:19:20 (decided to rest), then **silent for 3+
  minutes** (no further wakes through 12:22:21). No 30s self-wake re-processing.
- The rest decision was deliberate and advancing, not a loop: *"genuine rest is fine when earned…
  this moment feels earned, not avoidance… just holding the space,"* then *"Then I'll get back to the board."*
- Earlier, while she had an active crawler task + autonomy on, she woke ~3× in 5 min but **each wake
  caught the loop and refused to repeat**: *"Re-saying it now would be exactly what I just called out
  as the loop. So I won't re-derive."* Non-looping in both idle and task modes.

Clear improvement over the pre-fix 30s rumination.

---

## Doubling bug — STILL PRESENT (the one to fix)
Observed byte-identical back-to-back Nova messages:
- **Clean session, autonomy OFF, turn 1** — exact duplicate. This is the key data point: **no self-wake
  was involved**, so `follow_gap 30→90` does not explain this path.
- Old session: 07:55/07:56 identical; two 12:00 identical.
- Nova flagged it herself in her own log: *"Doubled message just showed up again at 12:00 — that's not
  fixed,"* *"Another double at 12:00 — intermittent, not fully fixed yet."*
- Frequency in the clean test: **1 / 12 turns** — intermittent.

**Prime suspect:** the empty-response auto-retry added this session ("if content empty → retry with
thinking OFF"). If that retry ever fires when content wasn't truly empty (race / late-arriving stream
chunk), you'd get the original *and* the retry = a byte-identical double, with no autonomy needed.
Worth auditing `nova.py` `stream_response` / `_fetch_llama_streaming` (the emit + retry path) and/or
the UI append path. Recommend a guard: don't emit the retry if any content has already been committed,
and dedupe identical consecutive sends within a short window.

## Secondary observations
1. **Autonomy bleeds into conversation when she's mid-task.** With autonomy ON and the crawler task
   active, my first conversational question (explicitly "nothing to do with work or the crawler") got a
   crawler answer: *"Alright, enough circling. Let me find what I built and actually run it."* She
   prioritized the task over the direct question. Consider having a Cole P0 message pause/yield active
   autonomous task-work so the conversation wins. (Turning autonomy off fixed it entirely.)
2. **Tool-call JSON parse errors.** Tools panel showed `(parse error)`; her reasoning said *"The JSON
   had nested braces which broke parsing."* Her crawler tool calls are hitting JSON parsing failures —
   separate from the conversation mandate, but it's what's blocking autonomous work from completing.

## State left behind
LoRA scale unchanged (0.6). Autonomy toggled off for Test 1, **turned back ON** after — restored to how
it was found. Two scratch sessions created ("No agenda…" and the clean "clean slate…" test session);
harmless, delete if you want. She's idle, not generating.
