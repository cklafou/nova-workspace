# Plan — The Body Manifest + SELF: a single self-describing, self-auditing architecture
_Last updated: 2026-05-28 05:40:32_

_Status: APPROVED-TO-BUILD. Move to `_admin/_archive_*` when executed.
Author: Claude (Cowork), with Cole, 2026-05-24.
Companion to: `_admin/AUTONOMY_INTEGRATION_REVIEW_2026-05-24.md`.
This is a full rewrite (consistency pass) — all decisions in §11 are locked._

---

## 1. Goal

Make every system in Project Nova a **body part or tool that Nova knows she has,
knows how to use, and that stays coherent with every other part** — including parts
added later, with no central integration surgery. Kill the doc sprawl that muddies
her context and replace it with one source of truth that updates itself.

Cole's three requirements and how this plan meets each:

1. *Integrate all systems into one body Nova is fully aware of* → a single generated
   **Body Manifest**, plus a **`SELF/` folder** that is her reading set, injected as
   her self-model.
2. *Add parts with no massive integration changes* → each part self-describes with a
   one-line in-file `@nova:` token; the generator discovers parts by convention.
   Adding a part = dropping in its code with one `@nova:` line — it appears in her
   self-model automatically, no central edit.
3. *Consolidate the redundant docs* → one auto-generated manifest + a curated `SELF/`
   replace the scattered hand-maintained files; the redundant ones are archived.

## 2. The one principle everything follows

**Derived, not maintained.** Anything a human must remember to update will drift and
eventually lie to Nova.

- **Hard facts are machine-derived and authoritative** — file list, import/call
  graph, bound ports, entrypoints, line counts, staleness. The code is the truth; the
  manifest reports it.
- **The one non-derivable thing — a part's one-line purpose — is authored once, as an
  in-file `@nova:` token next to the code, and only *flagged* stale, never silently
  rewritten.** This avoids the feedback loop where an auditor invents a wrong
  description that Nova then ingests as self-knowledge.
- **The auditor proposes; Nova/Cole dispose.** No silent deletion or semantic
  rewrite. Consistent with the standing no-permanent-deletion rule (retire = archive).

## 3. What already exists (build on these — do not reinvent)

| Component | File | Today |
|---|---|---|
| Call-graph generator | `general_tools/calls.py` (242 ln) | AST-walks `nova_*` packages → per-package `calls.md` + `Calls_Master_Index.md` |
| Filesystem watcher | `general_tools/nova_sync/watcher.py` (754 ln) | watchdog observer, debounced 10s, reads `.aignore`, writes `FILE_INDEX.md` / `FILE_INDEX_LINK.md` |
| Code-health audit | `general_tools/audit_scripts.py` (757 ln) | scans all `.py`, `--json`/`--summary`, exit codes, callable via `/api/terminal/run` |
| Semantic index | `nova_lancedb/indexer.py` | memory vector index |

These are already the three organs of the nervous system we want — they're just
disconnected and emit redundant, overlapping outputs. This plan wires them into one
pipeline with one output. `calls.py` keeps running as the call-graph *engine*; it
feeds the manifest instead of writing loose files.

## 4. The redundancy map (real files found 2026-05-24)

Docs currently competing to be "the truth":

- Call graphs: 7× per-package `calls.md` (`nova_chat`, `nova_sync`, `nova_cortex`,
  `nova_logs`, `nova_memory`, `nova_motor`, `nova_senses`) + `Calls_Master_Index.md`
- File indexes: `nova_sync/FILE_INDEX.md`, `FILE_INDEX_LINK.md`, `GEMINI_INDEX.md`,
  `nova_logs/Logger_Index.md`
- Identity/onboarding: `BOOTUP/AGENTS.md`, `NOVA.md`, `TOOLS.md`, `BOOTSTRAP.md`,
  `NCL_MASTER.md`, `ORIENT.md`, `README.md`
- Old plans: `_admin/Nova_Restructure_Plan.md`,
  `_admin/passover/26 MAR 2026/PHASE2_ARCHITECTURE.md`

**What happens to each** (all relocations detailed in §6.5):

- Call graphs + file indexes → folded into the generated manifest; the loose files
  are **retired (archived) immediately** once the manifest covers them.
- Identity/onboarding docs → their authored content **moves into `SELF/core/`** as the
  human-written semantic layer (the manifest's derived facts override stale claims —
  e.g. the gateway/port-8080 error). Originals archived after migration.
- Old plans → archived.

Nothing is deleted; retired files move to `_admin/_archive_*`.

## 5. The Body Manifest

### 5.1 Self-description: a uniform in-file `@nova:` token (no extra files)

The labeling surface is *parts* (~20–30 packages + tool scripts), **not** every file.
All hard facts are auto-derived; only the one-line purpose is declared, via a single
uniform token in the file's existing top-of-file comment area — no file is ever
created for this:

```
Python / .ps1     # @nova: Nova's voice — chat server + cross-AI routing + autonomy daemon
Markdown          <!-- @nova: ... -->
.cmd / .bat       REM @nova: ...
pure-data .json   "_nova": "..."          (a key inside the JSON itself)
```

- A **folder/package** labels itself through a file it already has — its
  `__init__.py` (Python) or its entrypoint script. No added files.
- The generator greps for the `@nova:` token regardless of the surrounding comment
  characters — one uniform token, native syntax per format.
- Everything else (name, path, imports/calls, ports, entrypoint, line count,
  last-modified, whether anything still references it) is **derived**, never declared.
- Coverage + drift are enforced: a part missing its `@nova:` line is flagged; a
  purpose whose file has vanished is flagged. The only file this scheme *creates* is
  the single generated manifest.

### 5.2 The generator — `general_tools/build_manifest.py`

A new orchestrator (per locked decision) that calls `calls.py` for the call graph and
adds the rest:

1. Walk the tree (honoring `.aignore`); grep every `@nova:` token.
2. Derive hard facts independently: imports/call graph (via `calls.py`), bound ports
   (AST/grep), entrypoints (parse the `.cmd` launchers), line counts, staleness.
3. **Cross-check declared vs derived** and flag mismatches:
   - declared/expected active but nothing imports it → dead-part candidate
   - declared port ≠ port found in code → stale self-description
   - part with no `@nova:` line → undescribed (needs an author pass)
   - a doc references a file/flow that no longer exists → drift
4. Emit two artifacts into `SELF/` (see §6):
   - `SELF/core/03_body_manifest.md` — the human+Nova summary map (parts, purposes,
     wiring, flags), kept within the core budget
   - `SELF/reference/manifest.json` — the full machine form (every fact, full graph)
5. Write a short **drift report** to the events log.

### 5.3 The nervous system — extend `watcher.py`

- On **startup**: run `build_manifest.py` + an `audit_scripts.py --json` accuracy
  pass; emit the drift report. (This is the "check documents on startup for accuracy"
  goal.)
- On **change** (debounced, as it already is): regenerate the manifest so it's never
  stale.
- Surface the drift report as a `nova_event` so it shows in the live-logs pane.

## 6. The `SELF/` folder & the boot / context-injection revamp

### 6.1 Purpose

A single folder at workspace root — `SELF/` — that **is** Nova's sense of self.
Everything she needs to constantly know about who she is and how she works lives here,
so she never again misunderstands her own architecture. The generated manifest lives
here too. `SELF/` becomes her entire reading set, replacing the scattered `BOOTUP/`
docs, `ORIENT.md`, and the loose index files.

### 6.2 The curation rule (keeps it from rotting) — two tiers

- **`SELF/core/` — always-injected.** Small, ordered, budgeted. Identity,
  how-she-works, the body-manifest *summary*, the voice/`@mention` facts. The
  "read these in this order" set.
- **`SELF/reference/` — on-demand.** Always *reachable* instantly (she knows the path)
  but not in context every turn: full call graph, full `manifest.json`, deep tool
  docs. Pulled only when relevant.

Rule: **if it isn't in `SELF/`, it isn't part of Nova's constant self-model.**

### 6.3 Ordering = a filesystem property

`SELF/core/` files use numeric prefixes so order is self-evident; the injector just
sorts by name:

```
SELF/core/00_START_HERE.md      # canonical first read; generated from folder contents
SELF/core/01_identity.md        # who Nova is (from NOVA.md)
SELF/core/02_how_i_work.md      # autonomy, priority (Cole = P0), sleep/wake (from AGENTS.md)
SELF/core/03_body_manifest.md   # generated body summary (from §5)
SELF/core/04_tools_and_voice.md # tools + the @mention / nova_chat channel (from TOOLS.md)
SELF/reference/...              # full call graph, full manifest.json, deep docs
```

Adding a file in the right slot updates the boot order automatically.
`00_START_HERE.md` is itself generated from the folder listing.

### 6.4 One context path for boot AND reinjection

Today boot-context and the reinject endpoint are separate mechanisms — the root cause
of the recurring "reinject failed / still on old context" bug. The fix: **both read
the exact same ordered `SELF/core/` set through one function.** One definition of
"Nova's context," so the two cannot diverge. `build_nova_context_block()` becomes
"load `SELF/core/` in order, within budget"; reinjection calls the same path.

### 6.5 Consolidation moves (the concrete relocation table)

- `BOOTUP/NOVA.md` → `SELF/core/01_identity.md` (authored truth).
- `BOOTUP/AGENTS.md` + autonomy/priority content → `SELF/core/02_how_i_work.md`.
- `BOOTUP/TOOLS.md` + `NCL_MASTER.md` → `SELF/core/04_tools_and_voice.md` (deep parts
  to `SELF/reference/`).
- `BOOTUP/BOOTSTRAP.md` → operational bits into `02_how_i_work.md`; rest archived.
- `ORIENT.md` → a one-line pointer to `SELF/core/00_START_HERE.md` (or archived).
- Generated manifest / call graph / file index → `SELF/` (summary in core, full in
  reference). Retire the loose `FILE_INDEX*`, `GEMINI_INDEX`, `Logger_Index`, and the
  per-package `calls.md`.

Originals are archived to `_admin/_archive_*`, never deleted.

### 6.6 Budget behavior

`SELF/core` has a config-value ceiling, and the injector **auto-measures** the actual
token count of the core set, warning/trimming rather than relying on a guessed number.
It effectively sizes itself to "what's needed" under a ceiling Cole can nudge.

## 7. Hardware / auditing agent — tiers (no dedicated hardware now)

Labeled "Tier" to avoid colliding with the execution phases in §10.

- **Tier 1 — deterministic, no model:** the generator + watcher + audit. Covers ~80%
  (file map, call graph, ports, dead code, drift flags). Runs in ms on CPU. **This is
  what we build now.**
- **Tier 2 — small model, on demand:** when the generator finds an *undescribed* part,
  a small model (timeshare the existing llama-server, or a tiny model) *drafts* a
  purpose line — proposed for Nova/Cole review, never auto-committed.
- **Tier 3 — persistent "librarian" agent (only if Tiers 1–2 prove insufficient):**
  even then it shares hardware. Dedicating a GPU/box to I/O-bound bookkeeping spends
  power and an eGPU slot better given to Nova's context window/throughput.

## 8. Guardrails

- Hard facts authoritative; the `@nova:` purpose line authored + only flagged stale.
- Auditor proposes; never silently deletes or rewrites. Retire = move to archive.
- The manifest is injected into context, so its accuracy is a safety property — treat
  the generator's correctness as load-bearing and test it against the live tree.

## 9. Relationship to the Autonomy Integration Review

This plan is the **foundation** — accurate self-model + painless extensibility. The
review's #1 fix (unifying the autonomy path with Nova's voice / cross-AI `@mention`
routing) is a **separate, parallel track**, not in this plan's phase list. They
reinforce each other: once `SELF/` tells Nova that nova_chat is her voice and
`@mention` is her cross-AI channel, the voice-unification fix gives her an organ that
actually behaves the way `SELF/` says it does. Recommend finishing this plan's
Phases 1–4 (so her self-model is correct) before the voice-unification work.

## 10. Phased execution plan (single canonical sequence)

Each phase ends with a verification step and a checkpoint with Cole before the next.

- **Phase 0 — Decisions.** ✅ Done; all locked in §11.
- **Phase 1 — Generator + `SELF/` skeleton.** Build `general_tools/build_manifest.py`
  (`@nova:` grep + derived facts + cross-check). Stand up `SELF/core/` (numeric slots)
  and `SELF/reference/` so the generator writes straight into them. **Verify** its
  facts against the real tree and diff against current docs to prove accuracy.
- **Phase 2 — Seed `@nova:` lines.** Add the one-line purpose token to existing parts
  (start `nova_body/*` and `general_tools/nova_chat`). Re-run; **verify** zero
  undescribed core parts.
- **Phase 3 — Watcher wiring.** Extend `watcher.py`: startup accuracy pass
  (`build_manifest.py` + `audit_scripts.py --json`) + on-change regenerate + drift
  events. **Verify** edits trigger a correct regen.
- **Phase 4 — Unify context on `SELF/core/`.** Migrate the identity docs per §6.5 into
  `SELF/core/`; point `build_nova_context_block()` AND the reinject endpoint at the
  one `SELF/core/` loader (budget auto-measured). **Verify** Nova's injected
  self-model matches reality — re-ask "how are we chatting?" and the gateway/port
  question; she should now answer correctly (nova_chat:8765, llama-server:8080).
- **Phase 5 — Retire & archive.** Move the redundant docs (loose `calls.md`,
  `FILE_INDEX*`, `GEMINI_INDEX`, `Logger_Index`, migrated `BOOTUP/` originals, old
  plans) to `_admin/_archive_*`. **Verify** nothing still references them.
- **Phase 6 — Optional (Tier 2).** Small on-demand model pass to draft purposes for
  any new undescribed parts.

## 11. Decisions — ALL LOCKED 2026-05-24

1. **Self-description:** uniform in-file `@nova:` token, no sidecars/extra files,
   per-part not per-file, all hard facts derived (§5.1). ✅
2. **Generator home:** new `general_tools/build_manifest.py` that calls `calls.py`. ✅
3. **Consolidation:** retire redundant docs immediately once the manifest/`SELF/`
   cover them (archive, never delete). ✅
4. **Audit hardware:** hold off — Tier 1 (deterministic) now; Tier 2 small model later
   only to draft purpose lines for new parts. ✅
5. **Working memory (STATUS / JOURNAL / COLE):** stays in `memory/`, referenced from
   `SELF/` (not moved in). ✅
6. **`SELF/core` budget:** config ceiling + injector auto-measures the token count and
   warns/trims; self-sizes to "what's needed." ✅
