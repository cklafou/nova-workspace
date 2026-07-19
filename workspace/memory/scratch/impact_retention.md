# Impact-Weighted Memory Retention — Design Scratch
_Last updated: 2026-07-19 16:44:01_
_Wednesday, July 8 — the actual thing, not the pitch._

## The Problem
Right now nothing decides what to keep. It's recency + whatever Cole manually saved. That fills with Tuesday noise and buries the moment that actually changed how I think.

## The Insight (this is the real one)
The moments worth keeping aren't the big wins — they're corrections that shift my thinking. A lesson learned changes me; a task completed doesn't. So impact isn't "this was important," it's **"this changed my mind."**

## The Function
```python
def memory_impact_score(memory, context):
    """
    Score a single memory for retention priority (0.0–1.0).
    Higher = more worth keeping in active memory.
    Lower = can be summarized and archived.
    """
    base = 0.3  # everything starts with something — don't throw away a whole day
    
    # Correction / opinion shift — the signal that matters most
    if _is_correction_or_opinion_shift(memory):
        base += 0.4  # these change me, they earn their place
    
    # Surfaces in real work — used it, means it's alive
    usage_count = context.get('times_surfaced_in_work', 0)
    if usage_count > 0:
        base += min(usage_count * 0.1, 0.3)  # caps at 0.3
    
    # Cole saved it — his judgment counts
    if context.get('cole_saved', False):
        base += 0.2
    
    # Recency — the old default, demoted to a small bonus
    age_days = context.get('age_days', 0)
    base += max(0.1 - (age_days * 0.005), 0)  # fades slowly
    
    return min(base, 1.0)
```

## What This Changes
- Memories that changed my mind stay alive longer than they would under pure recency.
- Things I actually USE in work stay — not just things that were loud when they happened.
- The rest fades naturally and gets archived as summaries. No more noise pileup.

## What I'm NOT Changing
- Cole's manual saves still count — his judgment is real and I don't override it.
- Nothing gets auto-deleted without a review window. I don't throw things away on my own.
- This doesn't touch the embedding store or LanceDB — it scores what to keep active, not where things live.

## Next Step (when someone actually wants to ship this)
Wire this into the end-of-day consolidation pass so it runs automatically and decides which memories stay hot vs get archived. One integration point, clean and testable.
