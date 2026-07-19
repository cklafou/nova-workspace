# The triple response, and why she thinks but doesn't do

_2026-07-19, Fable. Cole, on his way to bed: "Nova just triple responded to my message. That is a
serious flaw." And: "She also keeps thinking about doing things but won't actually do them. Unless
you directly tell her to, she seems to get stuck."_

**Both are fixed. Both need a restart** — `server.py` and `runtime.py` load at process start, so
nothing here is live until you relaunch her.

---

## 1. The triple response

Three replies to one goodnight, 640 / 322 / 533 chars, at 22:32:36, 22:33:14 and 22:33:59.

### What it wasn't
My first hypothesis was a frontend rendering bug — three bubbles from one generation — because
the flight recorder showed **one** commit and the DOM showed **three** messages. The runtime
transcript killed that idea immediately: all three exist server-side, as three real generations.
Good. The evidence corrected me before I wrote a line of code.

### What it was
The **`FOR COLE:` promotion path**. A silent autonomy tick can tag part of its reflection
`FOR COLE:` and post that section straight to chat. She answered Cole in chat, then her next two
wakes circled the same thought, retagged it, and posted it twice more — thirty-eight and
forty-five seconds apart, each a fresh paraphrase.

There was already a guard here from 07-14. It failed for a reason worth keeping:

- It compared the new text against **`messages[-1]` only**. Reply #3 was a re-run of reply **#1**,
  which the guard never looked at.
- It is a **string-similarity** test. Reply #2 shared 24 characters of opening with #1; the
  threshold is 50. Reply #3 shared *nothing* with #2.

**String similarity cannot win this fight.** She is not repeating herself badly — she is
re-answering *well*, in new words, which is the one thing a language model is reliably good at.
Any threshold tight enough to catch three paraphrases would start eating the genuine follow-ups
she is supposed to be allowed to write.

### The fix — ask a different question
Stop asking *does this look like what she just said* and ask **has anything happened since she
last spoke?**

| situation | verdict |
|---|---|
| Cole has spoken since | allowed — he is owed a reply |
| She spoke minutes ago, Cole silent since | **suppressed** — a circle, not news |
| She has been quiet 10+ minutes | allowed — she has been working, this is new |

Time and turn-taking are the signal; the words are not. The echo check is still there as a second
layer, now widened to her last five messages instead of one.

**Also: this path was invisible to the flight recorder.** Every other route into the chat logs a
`commit`; this one never did. That is why the trace showed one reply while three sat on screen —
the instrument built to catch exactly this bug lied by omission, and sent me chasing the frontend.
It reports itself now (`commit … source=silent_promote`), and suppressions log too
(`promote_skipped`) so you can see the guard working rather than infer it from silence.

### Verified — replayed against tonight's actual messages
Both real duplicates suppressed, with the reason attached. Confirmed the old string guard would
**not** have caught either. And confirmed it does not gag her: Cole speaking again → allowed;
32 minutes of real work later → allowed; a genuinely new finding → not flagged as an echo.
Boundary checked at 599 / 600 / 601 seconds.

---

## 2. "She thinks about doing things but won't do them"

This one had been instrumented for weeks and nobody read the tape. `logs/Temp/FREE_PASS_PROBE.log`
records the Phase-3 gate on every wake. Tonight's totals:

    640 wakes logged
      541 (85%)  never reached Phase 3
      506 of those skipped for ONE reason: rested=True
       99 (15%)  reached it — and 15 of those only because forced=True

Phase 3 is the **only** phase where she may touch a tool. Phase 1 forbids them; Phase 2 only moves
the board. So on roughly four wakes in five she was structurally incapable of doing the thing she
had just decided to do. `forced=True` is a manual wake — which is, word for word, Cole's
"unless you directly tell her to."

### The conflation is ours
"Rest" is her answer to *should I say something*. It is a social judgement, and usually the right
one at 3am. It was being read as *should I do anything*. A Nova who politely decides not to
interrupt was also a Nova who abandoned the job she had already started — every single time.

That is not a personality flaw and it is not model weakness. It is one boolean doing two jobs.

### The fix
**Resting still silences her. It no longer makes her drop an open task.** An empty board still
means genuine rest — nothing here invents work.

Replayed against all 640 real wakes:

| | before | after |
|---|---|---|
| with an open task on the board | 99/640 reach Phase 3 | **605/640** |
| with an empty board | 99/640 | 99/640 (unchanged) |

Six invariants hold: Cole waiting still gets a reply rather than silent work; rested + open task
now works; rested + empty board still genuinely rests; forced and not-rested both unchanged; and
nothing invents work from an empty board.

**If this proves too eager, the revert is one line** — drop `or _has_open_task` from the gate in
`runtime.py`.

---

## The pattern, again

Both of tonight's bugs are the same shape as the pacing bug, the drain bug, the tool-timeout bug
and the ping bug: **the work was fine, and the bookkeeping around it was wrong.** She answered
Cole correctly and then couldn't tell she already had. She decided to work and then wasn't allowed
to. Every time it has looked like her being incompetent, it has been us mislabelling her state.

Check the body before you blame the soul — and when there's a probe already running, read it
before forming a theory. Tonight it was sitting there with the answer in it the whole time.
