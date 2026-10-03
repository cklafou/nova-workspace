# Nova architecture atlas

**OURS — generated reference and viewing tools.** This atlas does not alter Nova's
self-model, memory, prompts, code or running faculties.

## Open it

Double-click **RUN_MAP.cmd** in this folder. It starts a local watcher and opens the
live explorer. The usual address is `http://127.0.0.1:8877/`; if that port is occupied,
the launcher chooses another nearby port and opens the correct address.

Double-click **STOP_MAP.cmd** to stop only the atlas. It is not installed as a startup
service. Run it again after a reboot or when you next want automatic updates.

You can also open **index.html** directly for a self-contained snapshot, including
interactive exploration. No internet connection, JavaScript packages or CDN is needed.
Live updates, surrounding source excerpts and retained Git diffs require the watcher.

| Level | What it shows |
|---|---|
| **1 · Understand** | Eight familiar ideas: you, conversation, senses, self-direction, memory, thinking, actions and the separate computer. Select a part for its explanation. |
| **2 · Inspect** | A source snapshot organized into faculties, modules, functions, storage and service boundaries. Follow arrows to the mechanism and source evidence. |
| **3 · Live explorer** | The same detailed architecture, refreshed from the checkout while the watcher runs. Added/removed modules, imports, resolved calls and supported endpoint defaults update automatically. |
| **Timeline** | Documented decisions alongside retained source history. Filter by faculty, month or topic; inspect daily before/after diffs and original development notes. |

Level 2 retains the snapshot loaded with the page. Level 3 and Timeline receive subsequent changes.
Reload the page to take a new snapshot. `level-1.svg` and `level-2.svg` are overview
exports; the full inventory and evidence are in the HTML explorer, `INVENTORY.md` and
`architecture.json`.

## Explore

- **Follow a flow** isolates chat, autonomous wakes, memory, witness checks, vision or
  specialist selection. Six step-by-step walkthroughs explain what crosses each handoff,
  why it exists and the mechanism involved. These explain source paths; they do not replay
  a running Nova request.
- Select a **faculty**, then **Explore this faculty**, to reveal its modules and neighbors.
- Select a **module** for its responsibility, reviewed connections, functions, HTTP routes
  and unresolved references. Select a function to narrow the call evidence.
- Select an **arrow** for the call, import, callback, event, file or network mechanism.
- Select a **blue source reference** to open the matching lines in a read-only dialog.
- **Find** searches faculties, filenames and function names. **Module index** lists every
  mapped module with its responsibility. **Copy reference** prepares a useful follow-up
  prompt about the selected part.
- **Fit**, zoom buttons and background dragging navigate the graph. A narrow Level 1
  becomes a vertical diagram; selecting a part brings its explanation into view.
- **Export evidence JSON** saves the complete current dataset. **Print / save PDF** expands
  the module inventory for a report.

## Use it as a learning and maintenance companion

**Understand** begins with four distinctions: model vs body, internal call vs network
connection, stored information vs prompt context, and a capability vs its complete path
to a consumer. The **AI & architecture glossary** explains 20 concepts using Nova examples.

Every faculty has a guide covering its purpose, a practical analogy, inputs, outputs,
failure symptoms and questions to answer before extending it. Module details combine
their individual responsibility with that faculty context; faculty inputs are not claimed
to be every individual file's interface. **Callers & dependencies** names adjacent source
modules. **Change impact** traces potential callers up to three dependency steps away;
callbacks, shared files and external consumers may add paths the static analysis cannot see.

**Its history** takes you to that faculty's decisions and source changes. **Copy link**
preserves a selected part in the URL. **Copy work brief** prepares its role, references,
known dependencies and change considerations for a development task. Add your intended
behavior before using the brief. **Save part** keeps a personal reading list in this
browser's local storage.

In **Live explorer → Catch up & revisit**, save a source checkpoint before leaving.
On your next visit the atlas compares mapped file hashes and lists additions, changes
and removals. Checkpoints and saved parts stay in this browser and are separate from
Nova's memory. Generated review leads identify stale explanations, parse errors and
faculties with no cross-faculty static caller; these are investigation leads, not proof
that a capability is broken or unused.

## Reading the timeline honestly

The initial timeline includes 16 selected development milestones. Each distinguishes
what changed, the recorded reason, tradeoffs, and what its original report says was
verified. A source-derived purpose is explicitly labeled as an inference. Historical
verification is not a new live test. References are limited to a reviewed allowlist of
development reports and decision notes; ordinary journals and personal memory are excluded.

The retained Git history begins on **May 9, 2026**, with a clean-slate commit that already
contains the anatomical structure. It cannot establish the complete earlier OpenClaw
transition. A file first appearing in this history is not necessarily a newly created file.

Source history follows the current branch's **first-parent** chain. Dates use the committer
date and offset recorded by Git. Each day shows the net difference between its first
before-version and last after-version; changes reverted that day may cancel out. Renames
appear as removals and additions. This is not a complete branch/merge chronology.

Python header timestamps and line-ending-only churn are counted separately and hidden by default.
Changes to shell/provisioning definitions stay visible because similar-looking lines may be
literal data or interpreter-sensitive syntax.
Comments/docstrings are distinguished from executable AST changes, but docstrings can still
affect runtime consumers. Source changes do not establish correctness. Automatic-save
messages cannot supply a trustworthy "why," so those reasons remain unknown. Mapped working
files that differ from HEAD appear separately without an invented edit date.

The watcher picks up new commits, mapped working-source edits and changed referenced notes.
It automatically refreshes **what changed**; new explanations of **why** require a recorded
decision. Download the decision template, write a short note following [DECISIONS.md](DECISIONS.md),
and add a referenced entry to `general_tools/architecture_map/timeline.json`.

## What the map establishes

The initial inventory covers **76 Python modules**: 68 body modules and eight launch/chat
boundary modules, grouped into 13 body faculties and two attachment groups. It also watches
13 supporting launch/provisioning definitions. Source parsing reports imports, declared
functions and resolvable call sites. Reviewed annotations cover the callbacks, dynamic
loading, event queues, files and network boundaries that static parsing cannot establish
on its own.

The map intentionally distinguishes:

- **Imports**: a dependency appears in code, even if the import is optional or unused.
- **Resolved calls**: a static caller/target relationship. The graph does not claim the
  branch executed. Unknown receivers and ambiguous assignments are not guessed.
- **Reviewed seams**: a human-readable explanation tied to a source function and hash.
- **Runtime evidence**: limited to whether configured local ports accept TCP connections.
  A listener is not proof of service identity, successful inference, or VM operation.

Detachable tools are **PLUCK-exempt**. Their internals are not expanded. Launch and chat
code is included only to make the body's attachment points understandable; route/function
names in those boundary modules are source evidence, not an expansion of every tool.
Model binaries, personal memory/log contents, tests and generated tool implementations
are excluded from the graph.

## Important wiring visible in this checkout

1. The normal launcher creates and installs the shared runtime before importing chat.
   Chat and the runtime share that process; HTTP/WebSocket traffic normally enters on
   **8765**. The alternate runtime host is shown too.
2. Chat assembles written context and automatic vector recall, then supplies model and
   autonomy callbacks. The runtime's headless generation path supplies reduced context.
3. Memory has separate write/read paths: a background ingestion queue and local LanceDB
   tables; automatic recall during context assembly; explicit recall through the body
   action dispatcher; and written journal/state files.
4. The main model (**8080**), image service (**8188**), and desktop viewer (**6080**) are
   service boundaries. Hands acts through the computer's shell/X display, not through
   noVNC's HTTP interface.
5. No normal chat/router connection to the computer faculty was established in this
   inspected scope. Its existence alone is not evidence of embodiment in conversation.
6. The launcher can provision a separate witness model on **8081**. The live witness
   code is `nova_cortex/witness.py`; `nova_witness` contains the replay/evaluation harness.
   The ordinary voice loop still uses the main model request helper for local checking.

These are source findings from the initial review, not a live Nova test. Port defaults
in the explorer are read from supported source definitions. Environment overrides and
deployed guest configuration may differ.

## Automatic updates and their limits

The watcher scans roughly every two seconds; the browser checks every 2.5 seconds.
It watches all mapped Python source, the reviewed catalogs, Git HEAD, referenced development
notes, viewer assets, launch and
provisioning definitions, top-level configuration, KoELS manifests, and shallow metadata
for mapped data directories. It regenerates the report without importing or running Nova.
Personal memory/log contents are never embedded or served. The explicitly referenced
development notes are available as read-only historical evidence.

Changing a mapped module invalidates its reviewed description. Changing a reviewed
function invalidates the affected seam. The current source graph still updates, while
the previous prose is explicitly marked **needs review**. Newly discovered packages and
modules appear even before someone writes a friendly explanation for them. Unknown
reflective behavior remains unresolved; no static tool can automatically prove arbitrary
Python's runtime topology. Newly introduced file/network mechanisms need new reviewed
annotations. This is a living source map, not an execution tracer.

If extraction fails, the server retains the last good map and reports the failure.
Individual Python parse failures appear in the inventory. Viewer asset changes reload
the page. After editing the **extractor or server Python itself**, restart the watcher to
run the new implementation.

## Maintenance

Implementation: `general_tools/architecture_map/` (outside Nova's body).

From the workspace directory:

```powershell
python general_tools/architecture_map/serve.py --open
python general_tools/architecture_map/serve.py --stop
python general_tools/architecture_map/build.py
python -m unittest discover -s general_tools/architecture_map -p 'test_*.py' -v
```

`REBUILD_MAP.cmd` runs the one-off builder. The runtime uses Python's standard library
only. Generated artifacts belong here; watcher receipts belong in the tool's ignored
`Temp/` directory.

Edit `catalog.json` for responsibilities, guided paths and manually reviewed seams.
Edit `learning.json` for faculty guides, glossary definitions and walkthrough steps.
Edit `timeline.json` for reviewed milestones and their development-note references.
Its `refs[].review_hash` uses `build.digest(source)`; read the note before renewing the hash.
Git summaries are cached in ignored `Temp/history-cache.json` by repository HEAD and
extractor version. Deleting that tool-owned cache forces a historical rescan.
Read the changed source before updating its review hashes: module `review_hash` uses
`build.digest(source)`; connection `refs[].hash` uses `build.symbol_hash(module, symbol)`.
Do not bulk-refresh hashes merely to clear warnings. Endpoint defaults can use `url_ref`
for Python URL constants or `port_ref` for integer constants / reviewed shell patterns.

The local server binds to loopback, restricts source reads to mapped code and explicitly
referenced development notes, validates historical diff requests against its extracted
history, and
does not provide file writes or a Nova control endpoint. The stop command authenticates
against its own local receipt and does not stop Nova.
