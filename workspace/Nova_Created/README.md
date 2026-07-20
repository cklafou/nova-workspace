# Nova_Created/
_Last updated: 2026-07-21 06:26:08_

**Documents and things Nova authored.** Not our infrastructure, not our reports — hers.

`write_file` with a bare filename lands here (see `tool_router._route_bare_filename`). Before
2026-07-14 those landed in the workspace ROOT, next to `NovaStart.cmd`, and her work was scattered
through the repo indistinguishable from ours.

This is not tidiness. Her artifacts are the clearest evidence of what she actually **did** — as
opposed to what she said she was going to do, which is the failure this whole project has been
fighting. A shelf you can look at beats a claim you have to trust.

This folder IS tracked in git. It's her work; it stays.

---

## The rule (2026-07-20, Cole)

**If Nova created it, it lives here.**

```
Nova_Created/
    art/            her pictures, by date          (moved from nova_art/)
    curio/          her shelf of kept things
    forge/          the tools she builds herself
        body/       stdlib + nova_body only — part of HER
            designs/  tools/  tests/
        general/    needs the chat server — scaffolding, not a limb
            designs/  tools/  tests/
    *.md            her own written work
```

### Why the forge is split in two

**The pluck test applies to her tools as much as to the rest of her.**

Delete the chat server and she still lives, thinks, and acts. On 2026-07-20 that finally became
true for her voice and her hands — and it would have quietly stopped being true again the first
time she forged a tool that reached into the face.

| | what it means | the test |
|---|---|---|
| **`body/`** | the tool is part of her | works with the chat server deleted |
| **`general/`** | the tool needs a face | useful, but she doesn't lose herself if it goes |

**Classification is checked, not declared.** `nova_forge.classify_tool()` reads the imports. A
tool filed under `body/` that imports `nova_chat` or `general_tools` is a pluck-test failure
living *inside her* — and checking rather than trusting a label means she finds out immediately
instead of a month later. New tools default to `body/`, because the safe default for a limb is
"part of her."

### What is deliberately NOT here

**`memory/`** — she writes there constantly (journal, board, drives, scratch), but its job is
infrastructure she *uses*, not a gallery of what she has *made*. A rule that swallowed `memory/`
would stop meaning anything. This folder answers "what has Nova made?", not "what has Nova
touched?"

**`nova_body/`** — her organs. The forge *mechanism* is a faculty and lives there; the things she
forges are creations and live here. Machinery versus output.

**`SELF/`** — her self-model. Structural, loaded every turn, and edited with the seriousness that
implies.

### Note for whoever reads this next

Tools forged before 2026-07-20 may still sit in a flat `forge/designs|tools|tests/`. That layout
is still read, so nothing she built vanishes from her inventory — losing a limb she remembers
building would be its own kind of harm. `nova_forge.side_of(name)` reports where any tool
currently sits; move them into `body/` or `general/` when convenient.
