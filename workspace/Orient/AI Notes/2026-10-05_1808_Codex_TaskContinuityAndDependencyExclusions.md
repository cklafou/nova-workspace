<!-- @nova: Record canonical task continuity, bounded context fitting and virtualenv exclusion changes with isolated validation. -->
# Task continuity and dependency exclusions

**Summary:** Existing task records now preserve resumable checkpoints, and ordinary context fitting no longer clips the merged system prompt at 24,000 characters. Local Python environments are excluded from source handling; accidentally tracked dependency files were removed from Git's index without deleting the installed environment.

## Did

- Extended `workspace/nova_body/nova_cortex/tasking.py`: optional next_step, constraints and observations remain on each canonical task; partial updates retain omitted fields, and decision-created tasks keep acceptance checks. No second task store or personal-record migration.
- Extended the existing task_progress routing/prompt contract. `workspace_context.py` reads a bounded unfinished-task resume view before large identity sections; `executive.py` uses the same saved task facts for execution.
- Added pure `nova_cortex/context_budget.py` and applied it to initial fitting plus every ordinary fetch, with the actual output allowance. Current request, newest turn and marked checkpoint have priority over older context. Internal witness, system, reach-watcher and arbitration turns do not replace an unlabelled headless objective. Exact-candidate audit bypass remains unchanged.
- Added the helper to `general_tools/nova_chat/server.py` source fingerprint list.
- Added `.venv` and `venv` exclusions to root/workspace Git and AI ignore files; watcher events/audits/direct timestamp/PUP writes; Drive scans/indexes; weekly backups; Drive reading copies; path audits; and automatic workspace context, including explicit filename injection. The existing Orient exclusions already cover these names.
- Corrected the workspace `.aignore` comment: the watcher loads the repository-root file once at startup; backup/Drive have their own built-in filters. A reference ignore file is not universal live configuration.
- After verifying the exact resolved dependency path and Git-index prefix, removed exactly 1,646 paths beneath `workspace/general_tools/voice_gateway/.venv` using index-only removal. Zero remained tracked. All 1,646 existing disk files retained their size/mtime metadata; the environment configuration and interpreter remained present. No commits or Git-history rewrite were performed by this agent.
- Updated the existing Orient explanations and source watch lists for execution, evidence, configuration, recovery, remote reading and source-defined context limits. Voice-specific operational prose remains assigned to the parent Codex task.

## Verified

- 19 isolated continuity/context tests: fresh-module recovery, partial-update retention after twenty-note pruning, acceptance forwarding, malformed/legacy records, completion filtering, real router forwarding, fresh context assembly, bounded execution context and output reserves. A fixture uses the real system prefix and an oversized checkpoint tail; another executes the real witness builders and seven internal repair/challenge forms to preserve the original headless request.
- 30 existing modernization, 31 witness-delivery and seven ModelClient tests passed: 87 relevant checks including the 19 continuity tests.
- All 34 sync tests passed from the workspace working directory, including ten new dependency fixtures. They prove exclusion before file contents/checksums enter the relevant pipelines, preserve adjacent source, inspect a disposable backup zip, and use a disposable Git repository. Fixtures include model metadata at the prepared `share/nova_voice/moonshine-base` path inside each environment.
- Two existing fingerprint tests pass; the actual source list contains the context helper exactly once.
- No model, audio, VM, desktop or service-control calls from this agent. No Nova-owned records were edited. The parent coordinates runtime reload and live validation.

## Limits / next

- Checkpoint notes remain Nova-authored; persistence is not independent completion evidence or proof that she will consistently save useful checkpoints. Ordinary context includes at most three unfinished tasks and 6,000 characters. Full records remain stored; shortened fields require targeted retrieval rather than a whole-board read whose result may itself be clipped.
- Fitting uses 3.4 characters/token with a 4,096-token reserve and source-defined limits. It does not measure exact tokenizer/image usage, and very small configured budgets can shorten critical text. Keep the model client's context setting aligned with the launcher.
- Source-prefix recognition is tested against current internal messages. New unlabelled internal message forms need equivalent coverage.
- Git exclusions do not remove older history. Source-level filters require normal process reload; the parent owns final restart confirmation and any voice-specific documentation.
- This note follows `2026-10-05_1607_Codex_VoiceFoundationAndHarnessComparison.md`; it does not certify native voice behavior or a witness model benchmark.
