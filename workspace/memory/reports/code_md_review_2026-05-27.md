# Code + Markdown Review Sweep — 2026-05-27
_Last updated: 2026-05-28 04:36:49_

_Reviewer: Opus (Claude). Scope: hunt dead references to retired systems and stale
docs across the live workspace (archives under `_admin/_archive_*` and `_admin/passover/*`
were intentionally skipped — they are history). Drive was **restored** today, so this
sweep also flags "Drive retired" claims that are now wrong in the other direction._

---

## 1. Fixes applied this session (safe, factual — already live on disk)

These were unambiguous factual corrections, so I made them directly:

- **`StopNova.cmd`** — removed all references to the retired gateway port `:18790`
  (the `@nova:` annotation, the comment legend, the echo, and the kill loop now list
  only `8080` / `8765`). The gateway was archived in May; nothing listens on 18790.
  This also cleans the two **auto-generated** files that copy that annotation
  (`SELF/reference/manifest.json` line ~254 and `SELF/core/03_body_manifest.md` line ~90)
  — they'll regenerate clean on the watcher's next `build_manifest` pass.
- **`README.md`** — line 60 "Drive sync retired" → now describes `drive.py` as the
  Google Drive mirror that rides with each GitHub push. Line 53 `nova_senses` list now
  includes `touch.py` and `proprioception.py`.
- **`memory/STATUS.md`** — line 68 same Drive correction; line 55 `nova_senses` row now
  lists `touch.py` and names touch as a sense.

---

## 2. Recommended doc updates — NOT applied (need your eye; they shape Nova's self-model)

These describe Nova's **autonomy as single-pass** — which is now wrong. The implemented
flow (executive.py + the daemon) is **two-phase reflect → decide**, plus the **Phase 3
execution pass** added today, and the **Touch** sense feeds the reflection. I left these
for you because they are the docs Nova *reads about herself*, and you've been deliberate
about how her cognition is framed. Proposed wording below; say the word and I'll apply.

**a) `SELF/reference/heartbeat.md` (lines ~29–40), "Each wake, the executive faculty:"**
Currently: 1 Senses → 2 Sees board → 3 Decides → 4 Acts. Should become roughly:

> 1. **Reflects first** — before doing anything, sits with the moment in first person:
>    recent conversation, how it feels (via **Touch** — what's interacting with her:
>    viewers, Cole typing, which agents are online), what it logically calls for. No
>    tools, no board changes in this phase.
> 2. **Decides**, having reflected — engage Cole, work the board, keep thinking, or rest.
>    Board moves are OPTIONAL; resting is valid.
> 3. **Executes** — if she holds an open task and isn't mid-reply to Cole or resting, she
>    does the next concrete step with her real tools and logs honest progress (or completes).

Also: the **agency-verb list still shows `pause`/`resume`**, which the executive's
`ACTIONS` block does **not** implement. The real verbs are
`create / progress / switch / wait / abandon / complete / reprioritize / rest`. Recommend
dropping `pause`/`resume` (or wiring them) so the doc matches the code.

**b) `SELF/core/02_how_i_work.md` (lines ~152–160)** — the autonomy narrative says she's
"shown my board + senses + anything Cole said, and I freely decide … After I act, I stir
again." Recommend adding the reflect-first beat, the Touch sense, and the execute step so
her injected self-model matches reality.

**c) `memory/STATUS.md` (lines ~24–29)** — the "Her autonomy is a body faculty" bullet
reads "sense the moment → see her board → decide freely → act." Recommend: "**reflect** on
the moment (with Touch) → decide freely → **execute** the next concrete step of an open
task." I held off so all three autonomy docs get the same wording in one pass.

---

## 3. Flags for your judgment (no change made — "archive, don't delete")

- **Vestigial body packages.** `nova_body/nova_motor/` (hands.py, motor_cortex.py,
  tool_executor.py, verify.py) and `nova_body/nova_memory/` (session_store.py, goals.py,
  state.py, log_reader.py) are flagged **no-inbound-ref** by the body manifest — nothing
  currently imports them — yet STATUS/README list them as live faculties. Options:
  (a) wire them, (b) move to `_admin/_archive_*`, or (c) annotate them in the docs as
  "designed, not yet wired." They aren't hurting anything; just inaccurate as "live."
- **Vestigial tool scripts.** `general_tools/download_models.py`, `injector.py`,
  `restructure.py` are also no-inbound (likely one-time/manual utilities). Worth a quick
  confirm they're intentionally kept; if so, a one-line "manual utility" note in their
  headers would stop them re-flagging.
- **`README.md` setup deps (line ~141).** Now that Drive is back, the `pip install` line
  should add the Google libs: `google-auth-oauthlib google-auth-httplib2
  google-api-python-client`. (Plus the existing line omits `google-genai`/`uvicorn` is
  there — minor.)

---

## 4. Reviewed and intentionally left alone (clean / benign)

- **Archives** (`_admin/_archive_2026-05-24/*`, `_admin/passover/*`) — full of Discord /
  gateway / BOOTUP / ORIENT / old-`drive.py` references. Correct: they're history.
- **Auto-generated files** — `nova_sync/FILE_INDEX.md`, `nova_sync/GEMINI_INDEX.md`,
  `SELF/reference/manifest.json`, `SELF/core/03_body_manifest.md`, the `calls.md` /
  `Calls_Master_Index.md` graphs. Don't hand-edit; they regenerate (the `:18790` they
  carry clears once StopNova's annotation regenerates).
- **SELF docs' retired markers** — `SELF/core/02_how_i_work.md`,
  `04_tools_and_voice.md`, `reference/ncl_master.md` explicitly say
  "Retired — ignore: Discord / nova_gateway." Good pattern; left as-is.
- **Active-code removal comments** — `nova_cortex/context_builder.py` and
  `nova_chat/nova_bridge.py` mention gateway/Discord only to note they were *removed*.
  Accurate, benign.

---

## 5. Net

Live code is clean of *functional* dead references — the gateway/Discord/ExLlamaV2
removals from earlier sessions held. What remains is **documentation drift**: the Drive
reversal (fixed), the missing Touch sense (fixed in the two main docs), and the autonomy
model still being described as single-pass in the three self-model docs (recommended,
awaiting your wording sign-off). The vestigial `nova_motor`/`nova_memory` packages are the
one structural question worth a decision.

---

## 6. Round 2 — everything applied (per "fix everything to be accurate")

The §2 recommendations and the motor/memory question are now resolved:

- **Autonomy model → reflect → decide → execute (+ Touch)** in all three docs:
  `SELF/reference/heartbeat.md` (now a 5-phase wake), `SELF/core/02_how_i_work.md`
  (narrative), and `STATUS.md`'s autonomy bullet. README's short version matches.
- **heartbeat.md verbs** — dropped the unimplemented `pause`/`resume` to match the
  executive's real `ACTIONS` set.
- **nova_motor / nova_memory** — checked `@nova:` tags + imports. Neither is imported by the
  running stack (archived `orient.py` tagged both **PLANNED**; `motor_cortex.NovaAutonomy` is
  the *old* loop `executive.py` replaced). STATUS + README now mark them **scaffolded, not
  yet wired**, intent preserved, not deleted.
- **Drive reversal, round 2** — fixed `SELF/core/04_tools_and_voice.md` and the
  `nova_sync/__init__.py` `@nova:` tag (feeds the manifest → `03_body_manifest.md` /
  `manifest.json` self-correct on the next watcher pass). Same path for the `:18790` lines.
- **COLE.md** — "How Cole Reaches Nova" now points to the `nova_chat` group chat instead of
  retired Discord/`nova_gateway`.
- **Stale logger docstrings** — `nova_cortex/__init__.py`, `nova_sync/__init__.py`,
  `nova_sync/dir_patch.py` corrected (`nova_logs.logger` is current, not `nova_memory`).
- **Path corruption** — `general_general…_tools` botched replaces fixed in `dir_patch.py`
  and `check_keys.py`.

**Left intentionally:** archives, append-only `JOURNAL.md` history, all auto-generated files
(regenerate from the now-correct sources), and the `clawhub`/legacy detector patterns in
`audit_scripts.py` (they're meant to name retired systems).

Edited Python verified compiling; the larger files only show torn-mount truncation in
`py_compile`, confirmed clean by direct read. Everything needs the next watcher/server run
to propagate (and to regenerate the manifest from the fixed `@nova:` tags).
