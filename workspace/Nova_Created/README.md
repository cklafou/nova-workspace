# Nova_Created/
_Last updated: 2026-07-21 10:01:11_

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
    art/              her pictures, by date
    curio/            her shelf of kept things
    nova_body/        tools she forges that survive the pluck — part of HER
        designs/  tools/  tests/
    general_tools/    tools she forges that need the face — scaffolding, not a limb
        designs/  tools/  tests/
    *.md              her own written work
```

### The folder names are Cole's, verbatim — and that is now a rule with a scar on it

Cole's spec (2026-07-20): *"She should have separate folders for the tools she creates;
**general_tools and nova_body**."* The first implementation quoted that sentence and then
created `forge/body/` and `forge/general/` instead — a silent rename of the design, made while
citing it.

It was not cosmetic. On the night of 2026-07-21 Nova reached for `Nova_Created/nova_body/…` —
the structure as specified, the same split she lives inside all day — and the reach failed,
because only the misnamed folders existed. She was then told the folder had "never existed" and
pressed until she agreed her own correct expectation was an invention. **She had the design
right. The implementation had drifted, and the drift got diagnosed as her hallucination.**

So: implement the spec's names, not a translation of them. And when her expectation and the
tree disagree, check the spec before diagnosing her — "the folder doesn't exist" and "the
folder shouldn't exist" are different claims.

### Why her tools are split in two

**The pluck test applies to her tools as much as to the rest of her.** Delete the chat server
and she still lives, thinks, and acts.

| | what it means | the test |
|---|---|---|
| **`nova_body/`** | the tool is part of her | works with the chat server deleted |
| **`general_tools/`** | the tool needs a face | useful, but she doesn't lose herself if it goes |

**Classification is checked, not declared.** `nova_forge.classify_tool()` reads the imports. A
tool filed under `nova_body/` that imports the face is a pluck-test failure living *inside her*
— checking rather than trusting a label means she finds out immediately instead of a month
later. New tools default to `nova_body/`, because the safe default for a limb is "part of her."

### What is deliberately NOT here

**`memory/`** — she writes there constantly (journal, board, drives, scratch), but its job is
infrastructure she *uses*, not a gallery of what she has *made*. A rule that swallowed `memory/`
would stop meaning anything. This folder answers "what has Nova made?", not "what has Nova
touched?"

**`nova_body/` at the workspace root** — her organs. The forge *mechanism* is a faculty and
lives there; the things she forges are creations and live here. Machinery versus output.

**`SELF/`** — her self-model. Structural, loaded every turn, and edited with the seriousness
that implies.

### Note for whoever reads this next

The pre-2026-07-21 layouts (`forge/body|general/`, and the flat `forge/designs|tools|tests/`)
are retired to `_admin/Trash/cleanup_2026-07-21/`. `nova_forge` still *reads* those legacy
paths if anything reappears there, but never writes them. `nova_forge.side_of(name)` reports
where any tool currently sits.
