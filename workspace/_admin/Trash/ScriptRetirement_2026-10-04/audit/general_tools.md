<!-- @nova: Preserve the general_tools script retirement audit, evidence, keep decisions and separately authorized ping-reference edits. -->
# general_tools retirement audit — 2026-10-04

Scope: source/static/documentation review; no service, desktop, model, account, or personal-state operations. Root owns archival moves. Vendor, node_modules, __pycache__, temp, generated runtime caches and updater state excluded. Read Orient README/ARCHITECTURE/OPERATIONS and AI Notes through 2026-10-04_1333_Codex_DisposableTrainingPods.md. Audit paused for the user's urgent explicit layout-save request.

## Archive-ready backups

These are named revision backups, not executable source or optional manual tools. Each has a maintained canonical sibling and differs from it. Exact-name search found only generated `Orient/INDEX.md` and `Orient/Architecture/inventory.json`, no live source consumers. Preserve original path in Trash and regenerate inventory; no loader edits required.

| Archive candidate (relative to workspace) | Current replacement | Size bytes | SHA-256 |
|---|---|---:|---|
| general_tools/cloud_call.py.turnabout_bak | general_tools/cloud_call.py | 11085 | 82e326ec9ec813eb9bdf6b222041d59992f7fbec24fb52c1102fab08af4f1929 |
| general_tools/nova_sync/watcher.py.holdback_bak | general_tools/nova_sync/watcher.py | 45219 | faf87c57a42e73e418b4b78b1781c01505bf6cab83f54718bf97cbfdeb1e5635 |
| general_tools/nova_sync/watcher.py.sizeguard_bak | general_tools/nova_sync/watcher.py | 46979 | 5a73198c2ddbcba13559da268a63ed9b6b552ad402f1f2485b5c0a8fdda70d0c |
| general_tools/nova_chat/static/index.html.polish_bak | general_tools/nova_chat/static/index.html | 353625 | 17aba543665d003e16a89e5a676c894cfedfe719feb01b756764866d051af7b5 |

## User-selected retirement requiring coordinated code cleanup

`general_tools/ping_claude.ps1` is a 496-line foreground/clipboard/UI automation helper. It is not merely unreferenced: before the retirement edits, `nova_body/nova_voice/tool_router.py:1115` constructed its exact path and dispatched it, aliases at1329 accepted it, and `nova.py:280,477,1183` plus router help at813,1010 advertised it. `nova_computer/backends.py:144` already called it retired, contradicting actual wiring. Root and body agent are handling removal of that tool and prompt references before archiving the script.

No replacement claims: the current Collaboration room deliberately excludes Nova; it is not a drop-in replacement for Nova contacting Claude. The remaining supported fallback is to ask Cole in conversation.

Separately authorized non-body edits completed atomically:
- `general_tools/injector.py`: retired mentor reply now tells Nova to use available tools or ask Cole; no external contact promised.
- `general_tools/nova_chat/orchestrator.py`: removed ping advice from description/comment.
- `general_tools/nova_chat/server.py`: removed current-use ping comment and corrected stale three-agent streaming docstring.
- `general_tools/nova_chat/static/index.html`: removed special ping success renderer; generic historical tool rendering remains.
- Purpose line first in changed Python files. AST syntax checks passed for all three Python files; all seven inline JS scripts passed `vm.Script` syntax parsing. No remaining ping_claude/via Ping string in these four files.

Historical references remain intentional audit evidence in `audit_scripts.py:820,857` (old PowerShell encoding failure), old `.bak` copies, dated logs/records and generated architecture graphs. The root should distinguish historical explanation from active advertising. The exact generated tool listing in ARCHITECTURE and graphs must be rebuilt after the body removal. Do not hand-edit Nova's logs/memory.

## Conditional legacy launchers — keep until owner chooses retirement

- `general_tools/nova_chat/launch.py`: older browser-only launcher, overwrites server_runner.py and opens a visible shell (`_write_runner` at71 and `_spawn_server` at101). No source caller found outside its self/documentation references. Current canonical launch is NovaStart.cmd / NovaChatOnly.cmd -> nova_start.py -> NovaLauncher.py + native desktop. This is likely superseded, but a manual debug/legacy executable entry point remains plausible, so absence of imports alone does not justify moving it.
- `general_tools/nova_chat/server_runner.py`: companion standalone server entry; directly used by legacy launch.py. Retire only together with launch.py, after deciding whether this manual entry point is still supported.
- Active documentation references both in `architecture_map/notes/security.md:16` and generated `Orient/OPERATIONS.md:206`; generated INDEX, inventory, calls.md and GEMINI_INDEX also mention them. If retired, update the authored security section, regenerate derived indexes, and remove any retained build/shortcut consumers found by root's root/admin audit.
- `general_tools/nova_chat/runtime_host.py`: earlier standalone runtime-primary entry, now duplicated by NovaLauncher behavior. KEEP/uncertain as a documented manual diagnostic, with explicit architecture-map boundary/history references (`architecture_map/build.py:29`, atlas_history.py:24), and headless runtime doc references. Do not archive merely because normal startup uses NovaLauncher.

## Reviewed folder decisions

| Folder (under general_tools) | Decision and evidence |
|---|---|
| root helper scripts | Keep audit_queue/audit_scripts/restructure: watcher produces queue items and its supported rename workflow resolves them. Keep build_manifest: watcher.py:829 and server.py:1092 invoke it. Keep calls/calls_order: documented rebuild tools, restructure.py:517 can run calls.py; Orient README directly names calls_order. Keep cloud_call: nova.py dynamically loads it at1746/1918/2084. Keep injector: server.py:3819 NCL execution imports it. Keep NovaLauncher: nova_start.py:58/468/491 owns it. Keep janitor as an explicit manual quarantine tool, not an orphan-by-import rule. Backup and ping decisions above. |
| architecture_map | Keep generator, build/history/serve, viewer assets, catalog/review/timeline/learning data. Current Orient hooks and source citations use these. Five test files cover parsing, source changes, history, registry, route generation. |
| architecture_map/hooks | Keep pre-commit: regenerates canonical Orient and stages only generator-owned docs. |
| architecture_map/notes | Keep eight authored explanatory sections: generator consumes them; not redundant generated output. |
| nova_chat | Keep current controller/server/session/runtime/NCL/bridge/data modules. workspace_context.py is a compatibility import still imported by server.py:34. build_desktop.py is current packaging, documented in CONTROLLER. Conditional legacy entry points above. |
| nova_chat/clients | No source files; only empty/cache residue. No archival source candidate. |
| nova_chat/static | Keep current CSS/JS/index assets; current index references controller, workspace, collaboration, updater and conversation-power assets. Only index.html.polish_bak is archival. Vendor excluded. |
| nova_chat/tests | Keep all 13 current files: lifecycle, native ownership, chat-only/privacy, collaboration/transport, updater integration, source fingerprint and UI fixtures protect implemented behavior. |
| nova_collaboration | Keep bridge.py, README and MCP config: actual Cowork session transport, separate room with current tests. No substitute paid-model connector. |
| nova_collaboration/.claude-plugin | Keep plugin manifest (version1.0.0); current connector metadata. |
| nova_collaboration/commands | Keep join.md: current joining/identity/privacy instructions. |
| nova_console | Keep console_app/hub/plainspeak/lifecycle; current launcher owns them. stray_janitor is imported by console_app.py:87, so not obsolete despite its name. |
| nova_sync | Keep watcher/backup/drive/drive_copy and dir_patch. watcher.py:977 still imports dir_patch for --full; watcher.py:699 invokes backup. drive.py regenerates GEMINI_INDEX as a remote mirror index, not the canonical Nova inventory. The two watcher backups are archival. |
| nova_sync/hooks | Keep pre-push size guard; still supports FIX_GIT install and protects GitHub push. |
| nova_sync/tests | Keep all three current exclusion/privacy/timestamp regression tests. |
| nova_updater | Keep current CLI/API/catalog/install/train/store/network/funding modules and README. Current server/UI call these. State excluded from audit. |
| nova_updater/pod | Keep training/template/shell scripts; used to freeze new training packages and validated by current tests. Not one-off because a recent run finished. |
| nova_updater/tests | Keep 14 current Python files including support, cleanup, funding, training/provenance, launch/install/API and opt-in pod validation. |
| nova_updater/tests/fixtures | Keep both Qwen3.6/Qwen3.8 chat templates: cross-version compatibility regression inputs, not obsolete model copies. |
| voice_gateway | Keep optional manual gateway/STT/TTS/link/committer/config/fetch_models and its test. README documents smoke ladder and incomplete audio bringup; absence of automatic startup is intentional. server_patch.md is still pending guidance: current server.py stream_response call does not thread register, and README/nova_link/config reference it. Do not archive as an already-applied patch. |

## Limits and handoff

This is retirement classification, not a full code-correctness or live-use certification. No services or existing tests with potential live providers were run. Current body/customer state and models were not inspected. Root owns moves, archive manifest, authored Orient edits/review marks and the consolidated AI note. Before each move, re-read current source because other agents are editing shared files. Nothing in this audit report authorizes changes beyond the user's/root's existing scope.
