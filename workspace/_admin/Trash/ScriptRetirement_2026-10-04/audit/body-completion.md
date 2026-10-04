<!-- @nova: Read-only completion audit of remaining body helpers, paused for manual layout controls. -->
# Body helper audit supplement (in progress)

Paused 2026-10-04 for user-requested manual layout saving. No services, desktop, body source, personal records, or authored shelf changed.

Source findings so far:
- `nova_cortex/rules.py`: legacy one-action/checkin/BOOTSTRAP policy, requires removed nova_motor modules. Only current references found are its package docstring and an example in audit_scripts.py. Candidate retirement, pending final replacement/manual route check.
- `nova_cortex/checkin.py`: legacy CLI still reads the typing inbox actively produced by nova_chat/server.py. Modern environment.cole_typing and executive/runtime consume the same inbox. Do not remove producer. Helper decision remains uncertain until current interrupt path checked.
- `nova_senses/presence.py`: old relative nova_chat/logs/chat_history.json and role-based last-message heuristic. Current runtime uses nova_senses.touch via face_state plus environment typing. Candidate retirement, pending transcript path/schema proof.
- `nova_senses/stretch.py`: callback StretchWatcher class has no source caller found. Runtime instead dynamically loads Nova_Created/Cole_journal/stretch_watcher.py and calls check(runtime=self, dry_run=False). Authored shelf left untouched. Legacy helper retirement remains conditional on provenance/manual-use check.
- `nova_memory/state.py`: NovaState window/trading helpers lack source callers found, but contain Nova-authored historical rationale. validate_ui_stability counts removed nova_ui directory files. Keep/uncertain rather than archive solely for no imports.
- `nova_memory/goals.py`: manual STATUS proposal writer to logs/proposed; not equivalent to live task board merely because both track goals. Keep/uncertain until manual protocol relevance established without reading Nova records.
- `nova_memory/journal.py`: append/read_last legacy API; CLI writes a test entry to real personal journal (not executed). Current tool_router journal tools likely supersede; comparison incomplete.
- `nova_memory/log_reader.py`: keep. nova_logs/logger.py still writes dated sessions/<type>.jsonl including actions/errors, exactly the reader storage pattern; standalone diagnostics remain useful even with retired mentor-specific reporting.

Source-only evidence: rules.py, checkin.py, presence.py, stretch.py, state.py, goals.py and memory package docstring inspected; journal.py and log_reader.py inspected in full; nova_logs/logger.py through its writer/indexer; cortex package docstring; environment.py; runtime.py lines 310-355. No imports executed (rules and logger have side effects).

Remaining: journal router path comparison; presence producer proof; current execution interruption and manual docs; add precise line references/final classifications.
