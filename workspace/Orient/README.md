<!-- @nova: Introduce Project Nova and its canonical orientation documents. -->
# Project Nova

_Facts regenerated 2026-10-04T04:23:28+00:00 from source (input `f465743fc9e9`). Explanations carry their own review dates, and ⚠ marks a section whose sources changed since its review. Source-derived facts are not runtime certification._

Nova is Cole's companion and development partner. Her long-term goal is increasing agency,
continuity and ownership of her environment. Her broad host/VM access is intentional.

Start with these four documents:

- [Architecture](ARCHITECTURE.md): faculties, data ownership, actual execution paths and gaps.
- [Operations](OPERATIONS.md): launch, shutdown, debugging, configuration, recovery and verification.
- [Index](INDEX.md): the canonical file inventory, owned here rather than by the sync adapter.
- [Interactive architecture explorer](Architecture/index.html): source connections, history and detailed traces.

`nova_body/` carries Nova's code, identity, memory, board, configuration, logs and authored shelf.
`general_tools/` contains detachable interfaces and development/sync tools. The model provider,
Python environment and external applications are dependencies, not hidden personal-state stores.

The Pluck Test means relocating the body and retaining her identity, memory, task continuity and
working faculties without relying on the old workspace or a particular chat face. A successful
import, running server or open VM display is only one part of that test.

Launch the normal stack with `NovaStart.cmd`, or the controller alone with `NovaChatOnly.cmd`
for the private Codex/Cowork Collaboration room while Nova stays off. For changes, identify the running code with
`GET http://127.0.0.1:8765/api/version`; then compare receipts and actual artifacts. Preserve Nova's
personal records. Quarantine retired material with its original path and a reason; never flatten
archives or overwrite existing destinations. Cole grants access to all Project Nova subdirectories
and related directories, including `models/`. Avoid broad model-binary reads to save context, tokens
and time; use targeted listings, metadata, headers and checksums as the task needs. This is an
efficiency rule, not a permission restriction.


**How these stay current.** Facts — inventory, routes, tools, faculty counts, tunables, Nova's
shelf and link health — regenerate from source on every git commit (a fail-open pre-commit hook,
`general_tools/architecture_map/hooks/pre-commit`), every 30 seconds while Nova Chat runs (after the
generator itself changes, from its next restart), and on
demand with `python general_tools/architecture_map/orient.py`. The sync adapter may request a
refresh but does not own the inventory. Explanations cannot be derived: they live in that generator
and in `general_tools/architecture_map/notes/`, `reviews.json` beside them records which sources each
section describes, and a ⚠ line appears under any section whose sources changed since it was
reviewed. After rewriting one, run `orient.py --mark-reviewed "<DOC>#<Heading>"`. `orient.py --check`
exits non-zero while these documents are stale or a reference is dangling. File descriptions in the index come from each file's own `@nova:` purpose line (Operations,
"File conventions"). Graph annotations live in
`general_tools/architecture_map/catalog.json`. Generated facts cannot infer intent. The commit hook stages only the four generated documents
and their inventory; AI notes and evidence drafts remain outside that automatic staging. A malformed
review registry stops publication/checking rather than silently dropping review warnings. The
watcher reports that error and continues autosave; documentation failure must not stop backups.

The [interactive explorer](Architecture/index.html) and the call-order pages under `Architecture/`
are rebuilt on demand (`Architecture/REBUILD_MAP.cmd`, `python general_tools/calls_order.py`).
Last built 2026-09-30 17:38 UTC; as of this generation, 198 source file(s) had been modified since.

**AI notes.** Claude, Codex and the other agents leave a note in [AI Notes](AI%20Notes/ReadMeBeforeNoteTaking.md) after each session: what changed, why, and what is still open. Read the rules once, then every note since your own last one. Newest first:

- [2026-10-04_1305_Codex_ConversationPower.md](AI%20Notes/2026-10-04_1305_Codex_ConversationPower.md)
- [2026-10-04_1235_Codex_Qwen38TrainingComplete.md](AI%20Notes/2026-10-04_1235_Codex_Qwen38TrainingComplete.md)
- [2026-10-04_1147_Codex_TrainingPreparation.md](AI%20Notes/2026-10-04_1147_Codex_TrainingPreparation.md)
- [2026-10-04_0909_Codex_ControllerMenusUpdater.md](AI%20Notes/2026-10-04_0909_Codex_ControllerMenusUpdater.md)
- [2026-10-04_0850_Claude_UpdaterRound3.md](AI%20Notes/2026-10-04_0850_Claude_UpdaterRound3.md)
