# Message-doubling bug — evidence, guard shipped, trigger instrumented
_2026-07-02, Fable. Picks up §3 of PASSOVER_2026-07-02. Status: **user-visible bug killed by a
commit-point guard; root-cause trigger not yet caught — flight recorder now in place to catch it.**_

---

## What the data says (hard evidence, 06-22 session logs)

Five duplicate pairs found across `logs/chat_sessions/2026-06-22_*`: every pair is **byte-identical,
same author (Nova), 6.6–10.5s apart, two different message ids, nothing in between**. One case
(07:55) had a *third*, different reply 40s later. Decisive facts:

1. **Two separate `session.add()` calls** (different ids) — not a persistence double-write.
2. **The runtime mirror has the reply twice too** → both commits ran the full `on_done` normal path
   (only that path mirrors; the `/nova-message` endpoint doesn't). So: `run_ai_response`'s on_done
   executed twice per dup.
3. **The daemon didn't do it.** Wake events land 1–3s *after* commit #2 in 3 cases (change-
   fingerprint wake — a consequence, not a cause), and dup #5 (12:10 session, autonomy genuinely
   off) has **no wake events at all**.
4. Byte-identical at temp 0.7 ⇒ the two generations had effectively identical prompts (built
   before either committed) — i.e., two near-simultaneous generation passes for one Cole message.
5. Opus's prime suspect (the empty-response retry in `clients/nova.py`) is **acquitted** for this
   specific bug: the retry runs with thinking OFF inside the same turn and commits once. It had a
   theoretical doubling mode, now hardened anyway (below).

Eliminated as the second generator: daemon (3), `/nova-message` (2), double WS frame / frontend
resend (would duplicate Cole's entry — it doesn't), `_bg_transcript_flush`/`_bg_runtime_events`
(disk/UI only), queue+drain double-delivery (interleavings checked — single delivery each way).
**The concrete trigger is still unidentified** — some race spawns a second generation pass. Don't
re-litigate the eliminations above; catch it with the trace (next).

## What shipped (3 layers, all in place 2026-07-02)

1. **Commit-point dedupe guard** — `server.py`, `on_done` normal path: an AI reply that is
   byte-identical to the *immediately preceding* message by the same AI within **120s** is
   suppressed (bubble closed with empty `message_end`, generation_end still fires, nothing
   committed/mirrored/indexed). A legit "say it again" always has Cole's message in between, so
   consecutive-identical = bug. This kills the symptom **regardless of which path fires twice.**
2. **Flight recorder** — `logs/generation_trace.jsonl`: every generation logs `start` /
   `commit` / `dup_suppressed` with `ai`, `msg_id`, and **`source`** (`ws` = WS message queue,
   `drain` = queued-message drain, `daemon`, `followup`, `inject`). Console prints turned out to be
   unpersisted (why 06-22 left no evidence). **Next dup → grep dup_suppressed → its `source` +
   the paired `start` lines name the double-firing path. Then fix the root cause and this file
   has done its job.**
3. **Retry hardening** — `clients/nova.py stream_response`: streamed chat tokens are now kept in
   a buffer; if the fetch returns empty but tokens *were* streamed, the reply is recovered from
   the buffer instead of re-generating (the retry can now only fire when nothing reached the UI).
   The original empty-reply fix (retry with thinking OFF) is preserved for true empty turns.

## Verification

Logic unit-tested in /tmp replicas: dedupe 6/6 (suppress consecutive-identical <120s; commit when
Cole intervenes / content differs / >120s / other author / empty session), retry guard 4/4 (normal,
recover-not-retry, true-empty retries, whitespace-only retries). Canonical files Read-verified.
**Torn mount note:** bash `py_compile` on `server.py` fails because the mount serves the fresh file
truncated at ~line 2831 with null padding — Read shows the intact 2889-line file. Known gotcha,
not a syntax error. **Live check = Cole's next restart**, then a 12-turn conversation: expect zero
consecutive duplicates; any `[dedupe] SUPPRESSED` console line or `dup_suppressed` trace row = the
bug fired and was caught — bring the trace file to the next session.

## Spotted, not touched

`clients/nova.py generate_raw()` still carries `frequency_penalty 0.4 / presence_penalty 0.3` while
its comment claims "same anti-loop stack as the streaming path" (which was fixed to 0/0 — the
garble fix). Inconsistent; low priority (generate_raw has no current callers per its docstring).
