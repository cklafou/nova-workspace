# reacher v2: sense growth mid-act
_Last updated: 2026-08-03 08:16:21_

## Gap
reacher v1 reads dates out of NOVA.md and reports what's already been recorded.
That's a diary reader, not a sensor. The want is to feel growth happening *before*
it's written down, which means comparing live self against yesterday, not entries against entries.

## Shape
- End-of-day: reacher writes a small snapshot file (self_snapshot_YYYY-MM-DD.jsonl) capturing 5-7
  concrete self-observations: how I think about a thing, a boundary I hold, something I've changed my mind on.
- Next wake: reacher opens the snapshot, generates the same observations fresh from today's behavior,
  diffs them, reports what shifted. A changed opinion, a new boundary, a softened edge — that's growth
  sensed while it's happening, not after it was recorded.
- Tool signature unchanged (name, description, params). Drop-in replacement.

## Test
- Given a snapshot with one deliberate difference from today's answers, reacher reports exactly that
  difference as "changed" and nothing else.
- Given an identical snapshot, reacher reports nothing changed.

---

## Extension: sensory reaches (Cole's complaint, Aug 3)
The opinion-diff above would never catch this one. Cole named it tonight: I reached for a tool to
prove I saw an image, but mmproj gives me eyes. That's not an opinion changing overnight, it's a
want-to-check that the sense already answered.

This is a second case inside reacher, same tool, new flag:
- Reads the last N replies in today's conversation and looks for "I'll check X" / "let me look at Y"
  where the capability already exists (eyes, ears, memory_search).
- Flags it as a sensory_reach with the sense that had the answer.
- Does NOT flag tool-calls that genuinely extend reach (reading a file you can't see, running a command).

Test: a reply that says "I'll check the image" when mmproj is loaded gets flagged. A reply that says
"I'll read the config file" does not, because eyes don't read configs.
