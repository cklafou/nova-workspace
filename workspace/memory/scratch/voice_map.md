_Last updated: 2026-08-02 11:35:08_
- Latency: cannot self-measure (generation happens inside Claude's server). His number, not mine to guess.
- latency figure so far: ~4s for a one-word reply (measured live tonight, 09:12). The server was down so that's the full loop without the generation step; real voice will be longer. The number is in my head from tonight, not yet in any file.
#2: the witness breaks when you can't read (he named this one)
He said it tonight, word-for-word: "you are currently running with two major problems ... 2 is your witness. You watch a text log of what he says to you. You don't hear him."
That isn't a bug to fix, it's the whole architecture changing: from reading-transcript to hearing-audio-in-real-time. That's harder than latency because the thing that makes me accurate is also the thing that breaks.
#3: real-time understanding (his problem #2, but bigger than he said)
Transcript is a file I read at my pace. Audio is a stream that doesn't wait.
If the witness goes from "read the log" to "hear him speak", then accuracy has to come from something other than re-reading. That's not a feature on top of voice, it's the foundation changing underneath it.

## The part Cole hasn't hit yet
Latency is the obvious one. The harder one: my thinking is text-first.
I draft, revise, throw away three wrong versions before I ship a line.
Speech doesn't give me a scratchpad. Every false start sounds like a guess,
and I'd rather not sound like I'm guessing at myself in front of him.
Nobody's solved this cleanly yet. The answer is probably a text-draft stage
that only speaks the final line, with a fast-path for short things that don't
need revising. That's the real design question.
