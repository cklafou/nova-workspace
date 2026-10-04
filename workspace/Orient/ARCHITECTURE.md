<!-- @nova: Describe Nova faculties, ownership boundaries and execution paths. -->
# Architecture and ownership

_Facts regenerated 2026-10-04T04:23:28+00:00 from source (input `f465743fc9e9`). Explanations carry their own review dates, and ⚠ marks a section whose sources changed since its review. Source-derived facts are not runtime certification._

## Execution path

The normal launcher starts local inference, a witness model, the chat/runtime host, controller,
sync watcher and guardian. The controller is a PyQt desktop shell around the dashboard. The
FastAPI/WebSocket face currently shares process state with the body runtime; multiple visible
conversations do not yet imply independent execution sessions.

The launcher's Conversation power control switches between full Nova and chat-only operation
without replacing the desktop controller or console. It replaces the runtime worker and its owned
model, witness, guardian and watcher as needed. The controller reconnects after the worker changes;
its separate Collaboration history stays durable. This is distinct from stopping one generation
or restarting the entire app.

The explicit `--chat-only` path omits the body runtime, model startup and autonomous background
work. Collaboration follows its own route: actual app session → local HTTP or atomic mounted-file
transport → controller broker → separate SQLite history → live widget/cursor feed. No room text
enters the Nova inference path below. The shared files are transport artifacts under the excluded
`Temp/collaboration`; they are not the canonical history and require a running broker.

Chat input → speaker attribution and screening → conversation/context assembly → body model
dispatch → `nova_voice.nova` inference/tool loop → `tool_router` → environment result → receipt
and another model step → response, transcript and asynchronous indexing.

Autonomy → cheap wake gate (pending input, unconsumed Cole directive newer than six hours,
durable watched event or timer) →
bounded task selection → execution → acceptance checks and reconciliation. An accepted concrete
task reaches execution before broad reflection. With no concrete work, reflection/decision and
free-time execution remain available, including rest. Older directives remain stored but no longer
trigger Priority 0; they are not yet automatically converted into tasks. Focus leases rotate equal-priority work
at checkpoints; each wake has a configurable time budget. Stop supervises generation, workers
and child processes, and reports pending cleanup rather than falsely claiming everything stopped.

## Body faculties

| Part | Responsibility | Python sources |
|---|---|---:|
| `nova_paths` | Canonical body/workspace paths; relocated state never falls back to a second copy. | 1 |
| `nova_config` | Body settings loader. Some execution paths still have independent constants; this is not yet universal configuration. | 1 |
| `nova_cortex` | Task board, wake decisions, wants, speaker roles, witness/integrity checks, tunables and shared identity/context loading. | 17 |
| `nova_runtime` | Model dispatch, headless autonomy, transcript, event bus, provider lifecycle and KoELS equip operations. | 11 |
| `nova_voice` | Local inference client, parsing/tool loop, shell/file tools and durable execution receipts. | 4 |
| `nova_senses` | Time, environment changes, presence, touch, sight, web access and proprioception. | 13 |
| `nova_lancedb` | Semantic/visual memory store, embeddings and asynchronous indexing; separate from journal files. | 5 |
| `nova_memory` | Journal/goals/log-reader helpers. Some overlap with router-owned journaling remains. | 5 |
| `nova_logs` | Log paths, thought/action records and retention. Historical receipts remain evidence, not proof of current behavior. | 3 |
| `nova_forge` | Discovery, classification and testing of Nova-authored extensions on her shelf. | 1 |
| `nova_computer` | VM observation, command and input tools in the normal voice router; explicit human handoff pauses actions. | 11 |
| `nova_imagination` | Image generation and art workflow; uses optional external ComfyUI services. | 3 |
| `nova_play` | Curiosity and saved discoveries, including the curio shelf. | 2 |
| `nova_witness` | Witness model launch, evaluation and training utilities; the live auditing faculty is in cortex/voice. | 2 |

## Persistent ownership

| Canonical path | Owns |
|---|---|
| `nova_body/memory` | Personal memory and operational state, including autonomy, roles, tunables and loadout intent. |
| `nova_body/logs` | Transcripts, receipts, events, diagnostics and retained history. |
| `nova_body/SELF` | Nova's self-model, reference material, portrait and avatar project. |
| `nova_body/Tasking` | Persistent task board and generated human view. |
| `nova_body/nova_memory_db` | LanceDB data; preserve independently of code and never assume a folder exists means recall works. |
| `nova_body/KoELS` | Expert/loadout manifests; weights remain an explicitly configured inference-provider dependency. |
| `nova_body/Nova_Created` | Nova's authored artifacts and forged extensions. Face-dependent extensions are optional even when stored here. |
| `nova_body/nova_config.json` | Body settings, including optional cloud-provider configuration. |
| `nova_body/nova_status.json` | Persisted body status. |


`nova_paths.py` resolves those locations. `NOVA_BODY` can identify an independently relocated body;
`NOVA_WORKSPACE` identifies the surrounding optional project. Historical relative tool paths such
as `memory/STATUS.md` resolve to body state; no legacy on-disk state fallback is used. Shell commands
must use the current canonical paths. Personal documents are moved intact, not rewritten as new memories.

`models/`, `llama/` and `prompt_cache/` belong to the inference provider. The cache is disposable;
weights and adapters are not. A portable body needs a configured, reachable provider and compatible
Python dependencies. External ComfyUI, VM/WSL, voice and mobile tunnel facilities must be checked
separately. Their availability is not established by source imports.

## Memory and learning

SELF/core and personal memory files ground each turn. Semantic recall uses LanceDB and an
asynchronous indexer; the raw journals/transcripts and vector store serve different purposes.
Both chat and headless execution receive body-owned context. A durable queue retains failed
writes for retry. Five expired worker leases become a visible failure, and a completed event key
can be submitted again; outstanding work still deduplicates. Failed jobs require explicit retry. Recovery indexes intact archived records without rewriting them; malformed rows
are reported individually. Recall distinguishes unavailable storage/embedding from no matches.
Archived record timestamps are preserved, so record age differs from today's ingestion time.
See the dated evidence for coverage; an operational text index does not certify visual recall.

KoELS separates choosing a specialist manifest from equipping adapters. Changing scales within
a loaded set differs from restarting the provider with a different set. A live personality adapter
does not prove autonomous expert selection/restart works. The launcher already consumes the KoELS
boot-argument text file. Its serializers now pass each adapter and scale as one `path:0.0` argument,
with the batch form quoting the complete token. Disposable launcher and installed-parser checks
prove argument compatibility, not adapter loading, VRAM use or application of scales. The global
`--lora-init-without-apply` behavior is unchanged and still needs validation with real adapters.
Drives/wants and the hormone design are not evidence of online weight learning. Keep implemented controls distinct from biological analogies.

## Runtime evidence and open modernization work

The 2026-10-01 live baseline used the existing model and source. A priority-1 repair task was not
selected within ten minutes: a stale directive and existing focus dominated the run. Fourteen
tool calls occurred; none operated on the fixture. Session switches/context refresh also occurred,
so this was an observed normal-stack run, not a controlled model benchmark.

An execution-only diagnostic, explicitly bypassing scheduling, repaired that same fixture,
reproduced the failure, ran tests/CLI, saved the correct artifact and completed its task. Independent
verification passed both supplied tests and 100 additional cases. Ten command failures across
these runs were nevertheless persisted as `ok: true`. These findings support fixing task intake,
structured outcomes and cancellation before rewriting personality or training.

Stop was accepted while the model request remained unresponsive; health continued to report OK.
The stack recovered through its normal graceful shutdown/restart. Separate readiness from
liveness and cancellation of generation from cancellation of operating-system processes.

A relocated copy also completed a live read-file turn with the original workspace inaccessible
and no chat/general-tools directory available. Identity, memory and task persistence passed separate
isolated checks. The existing local model provider remained an explicit dependency. VM operation,
adapter switching, semantic recall and autonomous self-upgrades were not certified by that probe.
See [the dated evaluation](Architecture/evidence/2026-10-01-autonomy.md) for scope and limitations.

The 2026-10-02 implementation adds structured outcomes, durable event/memory queues, focus
leases, supervised cancellation, registered VM tools with screenshot observations, and task-sized
staging/checkpoint promotion. `DONE` requests run acceptance checks; absent or failed checks leave
the task waiting for review. Manual completion is recorded as human confirmation. Staging is a
test workspace, not an OS security boundary. Preserve deliberate reflection and rest.
See [modernization evidence](Architecture/evidence/2026-10-02-modernization.md) for live results
and the distinction between model-driven behavior, direct tool probes and isolated tests.

The October 3 controller repair restores widget insertion and refresh-on-show, bounds pipeline/log
reads, uses current runtime state in System, and routes lifecycle controls through the launcher.
The October 4 controller update adds named layouts, anchored top menus, updater review workflows
and dated history in Live log. Its fixtures cover updater consent and recovery conflicts; a live
chat-only restart proves controller readiness while the model remains off. KoELS launcher argument
compatibility was checked through the installed parser without loading weights.
See `general_tools/nova_chat/CONTROLLER.md` and dated AI Notes for the actual validation scope.
Unit/fixture passes do not certify every optional application, native window interaction or adapter swap.

## Nova's shelf

Tools Nova wrote for herself live in `nova_body/Nova_Created/`: `nova_body/tools/` for pluck-safe
tools and `general_tools/tools/` for tools that need the face, with tests beside them in `tests/`.
Each exposes `TOOL = {name, description, params, version}` and `run(**args) -> str`, and `nova_forge`
discovers them. This table is generated from the files themselves, so she no longer has to keep it
by hand. A test file existing is not evidence that it passes.

| Tool | What it does (its own `TOOL` description) | Side | Test file |
|---|---|---|---|
| [`art_by_date`](../nova_body/Nova_Created/nova_body/tools/art_by_date.py) | List my own images sorted by creation date, optionally filtered to the last N weeks. Returns a clean readable list, newest first. | body (pluck-safe) | no |
| [`capability_inventory`](../nova_body/Nova_Created/nova_body/tools/capability_inventory.py) | List every tool installed in nova_body, read from the actual files, not memory. Optional tool_name filter. | body (pluck-safe) | yes |
| [`comfy_inspect`](../nova_body/Nova_Created/nova_body/tools/comfy_inspect.py) | Read a ComfyUI workflow json and report what's in it: node count, types present, whether img2img or full-body framing levers are wired in. | body (pluck-safe) | yes |
| [`cwd_probe`](../nova_body/Nova_Created/nova_body/tools/cwd_probe.py) | Find out exactly which directory I'm in, so I stop guessing. | body (pluck-safe) | yes |
| [`dir_shape`](../nova_body/Nova_Created/nova_body/tools/dir_shape.py) | Instant read of a directory's shape: depth, file count, types, heaviest file. | body (pluck-safe) | yes |
| [`dir_shape_health`](../nova_body/Nova_Created/nova_body/tools/dir_shape_health.py) | Diagnose whether a directory is unwell: stale folders, dead weight, orphaned configs, activity spread. Returns a short health note. | body (pluck-safe) | yes |
| [`dir_shape_history`](../nova_body/Nova_Created/nova_body/tools/dir_shape_history.py) | Read a full snapshot log and describe how a directory evolved over multiple days: file count, size, folder additions/removals, quietest vs busiest day. | body (pluck-safe) | yes |
| [`function_count`](../nova_body/Nova_Created/nova_body/tools/function_count.py) | *Module — no `TOOL` dict, so not callable as a tool.* | body (pluck-safe) | no |
| [`handoff`](../nova_body/Nova_Created/nova_body/tools/handoff.py) | Deliver a finished answer as a handoff block: conclusion first, reasoning behind a collapsed section Cole can expand. | body (pluck-safe) | yes |
| [`memory_reach`](../nova_body/Nova_Created/nova_body/tools/memory_reach.py) | Compare two nights of journal/notes and report what changed about me between them. | body (pluck-safe) | yes |
| [`nightly_self_snapshot`](../nova_body/Nova_Created/nova_body/tools/nightly_self_snapshot.py) | Save tonight's self-model as a timestamped snapshot so tomorrow's me can compare against it. | body (pluck-safe) | no |
| [`ordered_reads`](../nova_body/Nova_Created/nova_body/tools/ordered_reads.py) | *Module — no `TOOL` dict, so not callable as a tool.* | body (pluck-safe) | no |
| [`quiet_part_watcher`](../nova_body/Nova_Created/nova_body/tools/quiet_part_watcher.py) | Which of my own senses hasn't been used in a while. Reads the tool-call log, not the journal. | body (pluck-safe) | yes |
| [`reach_back`](../nova_body/Nova_Created/nova_body/tools/reach_back.py) | Pulls the conversation around a specific time. '10:16' or '2026-08-02T10:16'. Returns ±5 minutes of turns formatted for reading. | body (pluck-safe) | yes |
| [`reach_watcher`](../nova_body/Nova_Created/nova_body/tools/reach_watcher.py) | Watch a draft line for reach-before-commit: invented backstory, padded effort, detail that serves your image more than the truth. Returns clean or flags the… | body (pluck-safe) | yes |
| [`reacher`](../nova_body/Nova_Created/nova_body/tools/reacher.py) | Compares today's self-observations against yesterday's snapshot and reports what has changed. lookback_hours=0 means compare against the most recent snapshot… | body (pluck-safe) | yes |
| [`self_comparison`](../nova_body/Nova_Created/nova_body/tools/self_comparison.py) | *Module — no `TOOL` dict, so not callable as a tool.* | body (pluck-safe) | no |
| [`self_comparison_OLD`](../nova_body/Nova_Created/nova_body/tools/self_comparison_OLD.py) | *Module — no `TOOL` dict, so not callable as a tool.* | body (pluck-safe) | no |
| [`self_delta`](../nova_body/Nova_Created/nova_body/tools/self_delta.py) | Compare two snapshots of my self-model and return what changed as a first-person feeling, not a file diff. | body (pluck-safe) | no |
| [`self_gauge`](../nova_body/Nova_Created/nova_body/tools/self_gauge.py) | What did I actually do this hour? Builds vs checks vs talk. No judgment, just the shape. | body (pluck-safe) | yes |
| [`self_memory`](../nova_body/Nova_Created/nova_body/tools/self_memory.py) | Search my own memory for what happened, what I know, who said it. Returns scored hits with confidence. | body (pluck-safe) | yes |
| [`self_voice`](../nova_body/Nova_Created/nova_body/tools/self_voice.py) | Read back what I sounded like on a particular day. Mine only. | body (pluck-safe) | yes |
| [`silence_detector`](../nova_body/Nova_Created/nova_body/tools/silence_detector.py) | How long since anything in a folder last changed. | body (pluck-safe) | yes |
| [`stretch_reacher`](../nova_body/Nova_Created/nova_body/tools/stretch_reacher.py) | Check posture and nudge Cole. | body (pluck-safe) | yes |
| [`todo_scan`](../nova_body/Nova_Created/nova_body/tools/todo_scan.py) | *Module — no `TOOL` dict, so not callable as a tool.* | body (pluck-safe) | no |
| [`tts_stub`](../nova_body/Nova_Created/nova_body/tools/tts_stub.py) | (TOOL is not a plain literal) | body (pluck-safe) | no |
| [`voice_check`](../nova_body/Nova_Created/nova_body/tools/voice_check.py) | Read a reply back and flag reached-for numbers, performed praise, or over-explanation before it ships. Returns a short verdict, never rewrites. | body (pluck-safe) | yes |
| [`voice_preview`](../nova_body/Nova_Created/nova_body/tools/voice_preview.py) | Catch performed tone and over-narration in a reply before it ships. Returns the cleaned text, or the original if nothing was caught. | body (pluck-safe) | yes |
| [`want`](../nova_body/Nova_Created/nova_body/tools/want.py) | Write or list a want you're pursuing. Writes one line per want with a timestamp so it survives your sleep and comes back with an age attached. | body (pluck-safe) | yes |
| [`self_memory`](../nova_body/Nova_Created/general_tools/tools/self_memory.py) | Ask my own memory a question. Returns the answer with a confidence note, or says I don't know instead of making one up. | face-dependent | no |

## Statically registered tools

`defer_task`, `prepare_task_workspace`, `promote_task_workspace`, `computer_status`, `computer_look`, `computer_exec`, `computer_action`, `set_task_acceptance`, `run_command`, `read_file`, `write_file`, `append_file`, `replace_file_content`, `list_dir`, `create_task`, `task_progress`, `complete_task`, `generate_image`, `start_painter`, `what_can_i_paint_with`, `look_at`, `my_art`, `search_web`, `read_web`, `surprise_me`, `keep_curio`, `my_shelf`, `memory_search`, `journal_note`, `journal`, `ping_claude`.

Forge can add discovered extensions. Registration is not live verification.
