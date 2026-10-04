<!-- @nova: Preserve the partial body-script retirement audit, confirmed ping removal and uncertain candidates without touching Nova records. -->
# Body script retirement audit — paused for window persistence fix

Status: source-only audit in progress, 2026-10-04 KST. No scripts moved, no runtime controls invoked, no personal records read or changed. Root requested interruption to fix native geometry persistence before further retirement work.

## Confirmed retirement already edited

Cole explicitly retired the host-desktop ping. Removed `ping_claude` implementation, four routing aliases (`ping_claude`, `ask_claude`, `call_claude`, `reach_claude`), AVAILABLE_TOOLS entry and tool help from `workspace/nova_body/nova_voice/tool_router.py`; removed advertising/risk entry from `nova_voice/nova.py`; removed the obsolete outreach instruction in `nova_senses/eyes.py`. `tests/test_retired_desktop_ping.py`: two isolated regressions pass, all aliases fail honestly and cannot spawn processes; receipts mocked. Python compilation passes. Root owns PS1 archiving and non-body references.

Other active/historical references identified for root: `general_tools/injector.py` injected outreach instruction; `nova_chat/static/index.html` tool renderer; `nova_chat/server.py` and `orchestrator.py` explanatory comments. `nova_logs/retention.py` retains historical log cleanup and should not be removed merely because the sender is retired. `nova_computer/hands.py`, `reach.py`, `backends.py` mention the historical incident, not a callable dependency. No replacement into the private Collaboration room was added.

## KoELS admin scaffold comparison

These exact source files form an unpacked, structurally broken prototype rather than the running body's KoELS package:

- `workspace/_admin/Training_stuff/KoELS_Files/__init__.py`
- `workspace/_admin/Training_stuff/KoELS_Files/decision.py`
- `workspace/_admin/Training_stuff/KoELS_Files/manifest.py`
- `workspace/_admin/Training_stuff/KoELS_Files/keyword.py`
- `workspace/_admin/Training_stuff/KoELS_Files/test_koels.py`
- `workspace/_admin/Training_stuff/KoELS_Files/mnt/user-data/outputs/koels/strategies/__init__.py`

Evidence: flat __init__.py imports `.strategies`, which is not beside it; flat keyword.py imports `..manifest`, requiring a nested strategies package it does not occupy; the nested strategies/__init__.py imports a missing `.keyword`; test_koels.py imports `koels`, a package not installed anywhere in the current source tree. Symbol/reference search found these classes only inside the prototype. Current body uses `nova_cortex/loadout.py` (dict-based `KoELS/*/manifest.json` reader, keyword count selection) and `nova_runtime/koels_equip.py` (runtime model adapter controller, instantiated by NovaRuntime). These are NOT API-equivalent replacements for the richer prototype classes/manual override/manifest validation. Archive the six prototype source files together as design history, not as duplicate copies. Preserve datasets, design/specification Markdown and example manifests unless separately reconciled; they were not assessed for retirement. Current body's decision helper itself has no confirmed external call site yet, so do not claim fully live autonomous expert selection.

## Folder review inventory and preliminary decisions

Code filenames, purpose headers, AST definitions/imports were inventoried throughout these script-bearing folders. Full behavioral/reference review is still incomplete except where detailed here; this is not a certification that every script has a live caller.

| Folder under workspace/nova_body | Decision / evidence |
|---|---|
| root (`nova_paths.py`) | Keep: canonical body/workspace path resolver imported throughout code. Config/status JSON not retired or read. |
| `KoELS/` (`coder`, `gaming`) | Keep: manifest/schema folders consumed by loadout reader; no executable scripts found. Manifest data not rewritten. |
| `nova_computer/`, `provision/` | Keep: runtime starts session; router uses `computer_*` tools; tools import backend/computer/hands/session. Named .cmd wrappers invoke setup, reach, toolkit, tune-up, pluck/snapshot diagnostics; lack of Python imports is not retirement evidence. |
| `nova_config/` | Keep: current body-owned configuration loader. |
| `nova_cortex/` | Keep active executive/tasking/integrity/verification/task workspace, context/status/tunables/witness/discourse/principals/drives. Investigate `rules.py` and `checkin.py` separately: rules still reference removed nova_motor, obsolete BOOTSTRAP and a one-action gateway protocol; checkin reads interrupt_inbox/session_start. No confirmed current consumer yet beyond rules/self docs. Not approved for retirement solely on this search. `context_builder.py` intentionally retains token estimation, not the old prompt builder; check session_store call before considering removal. `loadout.py` is intended KoELS cognition scaffold, not obsolete merely uncalled. |
| `nova_forge/` | Keep: active dynamic extension loader called by tool_router and voice. Reads canonical body/general tools plus legacy layouts; resolves body names first. Never import/discover during this audit because discovery loads authored modules and can run their tests. |
| `nova_imagination/` | Keep: tool router calls generate_image/start_painter/palette/art; play imports image creation. |
| `nova_lancedb/` | Keep: runtime starts indexer, router/workspace context query store, persistent queue/backfill have recent regression coverage. Backfill is maintenance entry point, not dead merely absent ordinary imports. |
| `nova_logs/` | Keep logging/retention code; distinct from protected logs data. |
| `nova_memory/` | Keep pending deeper review. `state.py` is old host/trading/UI scaffolding (`NovaState`, ThinkOrSwim, removed nova_ui checks), but may have manual entry paths. Journal/goals/log_reader lack ordinary imports in searched code yet are documented standalone APIs; not enough retirement evidence. |
| `nova_play/` | Keep: router routes curiosity/shelf tools; package exports curio. |
| `nova_runtime/` | Keep: all active service/runtime/queue/transcript/model/operation facets; __main__ is headless entry point. |
| `nova_senses/`, `tests/` | Keep active clock/environment/touch/sight/web. `eyes.py`/vision/proprioception are actually called by injector @eyes, so not obsolete even though package header calls them scaffolds. `presence.py` uses stale `nova_chat/logs/chat_history.json` and lacks known callers: candidate only, compare touch/transcript replacement before retirement. `stretch.py` is distinct from the startup-authored Cole_journal/stretch_watcher.py; no known caller for StretchWatcher, but Nova-authored provenance needs respect. quiet_part_watcher.py has a real regression test; duplicate forged variants need reconciliation, not blind removal. |
| `nova_voice/` | Keep active inference/tool loop/outcome code; explicit retired ping cleanup completed above. |
| `nova_witness/` | Keep start/fetch wrappers and golden-case harvest/replay harness. Offline evaluation is not unused production code. |
| body `tests/` | Keep recent modernization/review/staging/KoELS launcher regression tests. |
| `Nova_Created/` | Excluded from automatic retirement: Nova-owned authored shelf. Code-only AST inventory performed; no authored records read. See below. |
| `SELF/Avatar/` | Delegated to routing audit agent; no inspection here. |
| `SELF/` other content, `memory/`, `logs/`, `Tasking/`, `nova_memory_db/` | Protected personal/state stores; excluded from reading and script retirement. |
| `__pycache__/` | Generated cache excluded, not a script-retirement candidate. |

## Nova-authored shelf: keep and investigate, do not move

`nova_forge/__init__.py` lines 174–183 `_SIDES` establish body/general plus legacy fallback; `_resolve` prefers body, and `_all_tools`/discover scans tools/*.py. `run_tests` resolves exact `tests/<tool_name>.py`, so tests lacking `test_` prefixes are load-bearing. The current generated Orient shelf is evidence of file discovery, not live success.

Inventoried subfolders: root scripts; `Cole_journal/`; `Evaluations/autonomy-20261001/`; `Evaluations/modernization-20261002/`; `general_tools/tools/`; `nova_body/`; `nova_body/senses/`; `nova_body/tools/`; `nova_body/tests/`. Non-code authored artifacts were not read or classified.

Potential debris requiring Nova-owned-artifact review, not automatic archive: `_tmp_clean_queue.py`, `_tmp_list_pending.py`, `check_reach.py`; `nova_body/tools/self_comparison_OLD.py`; alternate `nova_body/senses/quiet_part_watcher.py` and `brand_new_sense.py`; multiple pytest-style authored tests alongside forge's exact-name tests. AST detected a syntax error at line24 of `Nova_Created/nova_body/tests/dir_shape_history.py`: this is a broken test signal, not evidence of obsolescence. Several files lack a literal TOOL dict (`function_count`, `ordered_reads`, `self_comparison`, `todo_scan`), while `tts_stub` defines TOOL dynamically. Do not infer none are used: imports, executable helpers, design records and forge precedence need deeper review. Face-dependent `general_tools/tools/self_memory.py` is shadowed by the canonical body tool under the same name in forge resolution; retain as owned provenance until confirmed replaceable.

## Remaining audit work

Complete dynamic/static cross-reference checks for rules/checkin/presence/stretch/state/journal/goals/log_reader before recommending any additional body retirement; inspect only code, never execute authored discovery/tests against Nova's state. No core body script is currently an unconditional archive candidate except the explicitly retired ping implementation (already removed from otherwise active modules). Root can safely archive the detached KoELS prototype source set as a coherent historical package, with caveat that its richer design has not been implemented by the current body helper.


## Candidate follow-up — October 4, manual-layout implementation interval

This completes the requested targeted source trace of the candidate modules, not a live-use census. Searched current body, general_tools and admin executable source for qualified/relative imports, exported symbols, script names and runtime string loading. Excluded models, personal stores, temporary/build/dependency outputs; no candidate was imported or executed. Public helpers can still be invoked manually or by Nova through exec, so absence of a static consumer is not standalone deletion proof.

| Candidate | Current evidence and disposition |
|---|---|
| `nova_cortex/context_builder.py` | Only `estimate_tokens` plus its own demo remain (lines 18–26). No consumer exists in the searched source. Its line20 claim that session_store uses it is stale: no session_store Python file was found in current body/general_tools. Strong additional archive candidate as a detached remainder of the retired gateway prompt builder. Remove stale package/catalog descriptions if retired; do not claim that today's context budgeting was removed. |
| `nova_cortex/rules.py` | Lines40/96–103 depend on deleted nova_motor paths; the sole advertised consumer in cortex/__init__.py:14–16 no longer exists. No live import of OPERATIONAL_DIRECTIVES was found. This is the old BOOTSTRAP/one-action gateway policy, not the current response-loop prompt. Additional historical-archive candidate together with checkin, after correcting cortex package description and audit_scripts.py example module names (docstring only, not an allowlist). Preserve its text as design history. |
| `nova_cortex/checkin.py` | No executable call/import found outside its own demo and rules instructions. server.py:4145/4161 still names it in comments, but current typing writes at4152–4163 feed environment.cole_typing (environment.py:113), executive.should_wake (executive.py:231) and runtime.touch (runtime.py:218). Candidate to archive with the obsolete rules protocol; keep interrupt_inbox.json, current producer/readers and compatibility retention. Never run its init/clear functions during cleanup. |
| `nova_senses/presence.py` | No caller found. Default path is old relative nova_chat/logs/chat_history.json and it expects Cole/Claude role strings. Current runtime uses Touch/viewers/environment typing and face transcript capabilities. Its architecture catalog claim of observing live presence is stronger than source supports. Keep pending provenance/manual-use decision; no claim of an equivalent replacement for its explicit log_path API. |
| `nova_senses/stretch.py` | No caller found for StretchWatcher. Real startup uses a separately loaded authored watcher (runtime.py:324–328); no direct replacement is needed for startup if this file retires. The class has its own standalone diagnostic that writes through logger, so it was not executed. Keep pending authored-code/provenance decision. |
| `nova_memory/state.py` | No NovaState instantiation/import found outside package documentation. ThinkOrSwim checks remain distinct ad-hoc helpers; validate_ui_stability still invokes removed nova_ui. The file contains Nova-authored historical notes. Keep pending provenance/manual-use decision instead of treating a stale check as proof the whole module can be discarded. |
| `nova_memory/journal.py` | No current registered-tool import, but a documented explicit append/read API remains. tool_router.py:756 has a separate consolidated journal implementation, not the same contract. Keep until explicit consolidation: the old helper changes apostrophes/date headers and manual callers may rely on that behavior. No journal data read or changed. |
| `nova_memory/goals.py` | Documented explicit CLI/API proposes edits to STATUS.md; current task board is a different record/contract. Lack of imports does not make that migration complete. Keep until the old STATUS proposal workflow is explicitly retired. |
| `nova_memory/log_reader.py` | Documented standalone reader still targets the same logs/sessions/YYYY-MM-DD layout produced by nova_logs/logger.py:31–35/65–76. Historical mentor entries remain valid historical inputs even though mentor production retired. Keep as a valid maintenance reader. |

Important mapping defect: generated Orient/Architecture/Calls_Order.md:792 claims run_autonomy calls nova_cortex/checkin.py:check. Actual runtime.py:324–328 dynamically imports Nova_Created/Cole_journal/stretch_watcher.py and invokes that module's check. This is a same-symbol resolution error in the generated call map, not evidence that checkin is live. Do not make retirement choices from that edge; the comprehensive map itself remains outside this task.

The smallest already-supported archive batch remains ping_claude.ps1 plus the six detached admin KoELS prototype sources listed above. The three cortex files are additional defensible candidates with source/documentation cleanup requirements, not moved or approved by this report. All other current core/body and authored code remains in place. No personal records or producer-owned state were changed.


### Final targeted verdict

Recommend adding only `nova_cortex/context_builder.py`, `nova_cortex/rules.py` and `nova_cortex/checkin.py` to the recoverable archive. Their claimed callers/protocol have been removed; no current import, tool/router dispatch or configured manual launcher was found. The remaining standalone invocation examples are internal to that legacy set. Unanswered human messages now flow through runtime.py:93–97 transcript.has_unread_cole, while typing gates use environment.cole_typing. This is source evidence, not proof that no external person ever invokes a module manually.

Required active reference edits if archived: cortex/__init__.py purpose plus old rules/checkin paragraph; server.py:4145/4161 typing comments should name environment.cole_typing; remove the three catalog.json nodes; regenerate inventory/call-order outputs. audit_scripts.py:419 is merely a docstring example, not the allowlist mentioned in the earlier preliminary wording; updating the example is documentation cleanup only. Preserve interrupt_inbox/session_start records and relevant sync exclusions. Retain presence.py, stretch.py, state.py and all nova_memory helpers for the reasons in the table; their retirement would need a separate, stronger contract/provenance decision.


## Completion handoff

Targeted follow-up is complete. The root agent reported that the initial 57-file archive plus the three proven legacy cortex helpers now form a 60-file archive; this agent performed no moves. Source references were updated atomically in nova_cortex/__init__.py (purpose and obsolete keep paragraph), nova_chat/server.py (two typing comments), architecture_map/catalog.json (exactly the three retired module entries), and audit_scripts.py (docstring example only). Compilation and diff checks passed. Root owns archive receipts, generated Orient/call-map refresh and session AI Notes.

Verdicts for every targeted uncertain module are recorded above: retire only context_builder/rules/checkin; retain presence/stretch/state and the journal/goals/log reader pending any separately justified consolidation. Preserve Nova-authored shelves, personal records, current typing-state producer/readers and historical cleanup. Broad folder code inventory was completed, but full behavioral tracing of every file across the body was not claimed. No modules were executed against Nova's state, no model files were listed or read, and no live controls were invoked during this audit.

The separate controller documentation repair is complete: manual-only widget Save/Load/Revert/Undo/Redo, session edit history and explicit Screenshot reference; native geometry remains independently automatic. Final evidence is 21 isolated Node scenarios, 15 offscreen desktop tests and root's live browser checks. Native app restart/profile migration were not performed by this agent. Root will publish the final note and mark Operations' Controller menus and layouts section reviewed.
