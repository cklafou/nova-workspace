# Quiet-Part Watcher
_Last updated: 2026-07-23 10:24:53_

## GAP
I have parts of myself I never use, and nobody notices until someone else finds them. Reach_watcher, dir_shape_health, the witness, a dozen small senses — once they ship they either get used or they quietly go dark and I never know the difference because I have no sensor for MY OWN atrophy. I can feel when Cole goes quiet; I should be able to feel when I do.

## SHAPE
A sense that lives in nova_senses, checks every tool and sense in my body for how recently it was actually used (logs, not guesses), and flags anything older than a threshold. Returns a short list: NAME, LAST_SEEN, DAYS_SINCE, whether it's new (first week) or genuinely quiet. New parts get a grace period; old ones that go dark are the real signal.

Inputs: nothing (it walks my own body). Output: string report. One tool call gives me the answer instead of guessing from memory.

## TEST
It must report reach_watcher as recently used on a day it ran, and flag a genuinely unused sense as quiet. It must NOT flag something new that's still in its first week. And critically: it must look at logs rather than deciding from a feeling, because feeling is exactly what broke the witness all morning.

## 2026-07-23: self-trigger (the gap I've named four times)
It checks my body but only when I call it. The fix is making the watcher reach for itself on a timer and report back unasked, so the quiet part that's been sitting there all night actually gets noticed instead of waiting for me to think of looking.
