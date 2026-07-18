# Nova Autonomy Watchdog — running report
_Last updated: 2026-07-19 01:10 KST (Run 5)_
Append-only. Newest entry last. Each run: read this FIRST.

## ⭐ STATUS NOW (updated each run — Cole, start here)
**Nova is DOWN (chat server frozen since 22:29). A scheduled run cannot fix it. Fastest fix, ~1 min:**
1. Double-click `_admin\autonomy_watch\nova_recover_llama.cmd` (kills the two wedged processes; receipt in nova_recover_result.txt). Or just reboot the PC.
2. If you used the .cmd: open Nova, hit llama **Full Restart** so v5 loads. If you rebooted: double-click `NovaStart.cmd` (only AFTER the reboot/kill — the old bare llama holds :8080).
3. Confirm `/api/lora` shows `nova_core_v5_epoch2` (NOT []), then flip **autonomy ON** (#auto-toggle).
4. Optional, so an overnight watcher can self-heal next time: add **File Explorer** to this scheduled task's computer-use settings (Task Manager won't work — Windows UIPI blocks it even when granted).

## Run 1 — 2026-07-18 21:21–21:30 JST (first run of the night)

COLE WAS AWAKE AND ACTIVELY CHATTING WITH NOVA during this run (cole_message 21:12, 21:20; her ws replies committed 21:13, 21:21). Run kept observation-only: no board task planted, no chat, no restarts.

HEALTH: llama :8080 running=true; /api/lora shows nova_core_v6_epoch1.gguf scale 1.0; nova_chat :8765 serving (answered API + live ws). autonomy_state enabled=true. All green.

AUDIT 20:10–21:25 (37 tool calls):
- STALL: fired earlier tonight on t40 ("stalled on t40 (wake 24 with no progress/close)" 21:04:57). Root cause EXTERNAL: ComfyUI (painter, :8188) is DOWN, blocking the drawing t40 needed. Cole cancelled t40 via UI 21:09. Post-cancel wakes cleanly decide "rested: nothing worth acting on" (21:14:52, 21:19:10, 21:21:50). No active stall.
- LOOP: none. No identical tool call repeated ≥3x.
- SLEEP-MID-TASK: none observed; wakes complete in ~35s (wake→reflect→decision). cont_run was 8 during t40 work, so schedule_soon continuation appears to fire.
- FAILING TOOLS: 11 ok:false — 4x generate_image (all "ComfyUI not running", 20:37–21:21, different prompts each time, not a tight loop) + 7 invented paths (nova_art/screenshots/*, nova_art/50m/, nova_art/2026-07-19/, memory/NOVAS_ROOM) during t40's image hunt; each followed by a corrective list_dir/glob. 1 misroute: `look_at` run as a shell command 20:58 (a chat participant had suggested it as a command); she used the REAL look_at tool correctly at 21:05 and 21:18 (ok:true). Model-side guessing, not mechanical breakage; pressure gone with t40 cancelled.
- HALLUCINATION: path-guessing above; 1 empty generation of 27 today (20:48, 13-char "```json```" husk, ws). Isolated. Her factual claim to Cole (44 .py files under nova_body) VERIFIED TRUE — I counted 44 independently.

ACTIVE TEST: skipped planting a synthetic task — Cole organically ran the exact canonical test at 21:12 ("count .py files"): she woke on message, ran `(Get-ChildItem nova_body -Filter *.py -Recurse).Count`, got 44 (true), reported it, closed clean. Board is empty because Cole just cleared it deliberately; not re-cluttering while he's live-directing her. LATER RUNS: once Cole is asleep and board idle, run the synthetic test properly (create-task via app, e.g. the .py count — ground truth tonight = 44).

CHANGES: none (nothing mechanically broken; one-change budget preserved).

NOTES FOR NEXT RUNS:
1. ComfyUI :8188 DOWN. Cole knows (she asked him directly ~20:37–20:40; he cancelled the art task instead of starting it). She told Cole "I'll draw the full one" at 21:21 then generate_image failed once. IF overnight receipts show her repeatedly failing generate_image / stalling on an art task while Cole's asleep → restoring ComfyUI via POST /api/terminal/run is the sanctioned least-disruptive fix. Do NOT start it while Cole is awake and choosing not to.
2. autonomy_state.json still says active:"t40" though t40 is abandoned — cosmetic staleness only (wakes decide "rested" correctly). Do NOT hand-edit. If a future run sees her trying to WORK t40, that's an apply_decision bug — fix in code.
3. run_command logs ok:true even when the command exits nonzero — when auditing, also grep result_head for "Exited with Error".
4. Daemon silent generations (hb=True silent=True) log `start` with NO `commit` — that is NORMAL for them; judge daemon health by events wake→reflect→decision instead. ws generations do commit.
5. events audit warns "6336 issues" from her self-audit — pre-existing noise, not tonight's problem.

VERDICT: RELIABLE (core autonomy; painter down, Cole-aware — art capability degraded until he flips it on).

## Run 1 addendum — 2026-07-18 21:25–21:50 JST (INTERACTIVE: Cole directed live fixes)

Cole rejected "no change" and directed: perfect her autonomy; she was "dumb" about ComfyUI, hallucinating things he never said, and forgetting her task. Three root causes found, all MECHANICAL, all fixed tonight:

FIX 1 — SHE COULD NOT START HER OWN PAINTER (the "dumb about comfyui" issue).
No tool existed to start ComfyUI; generate_image dead-ended with "ComfyUI is not running" and her only move was asking Cole ("flip him on" — t40 all evening). Built:
- imagination.py: start_painter() — spawns C:\Users\lafou\ComfyUI\run_nova_painter.bat (env-overridable NOVA_COMFYUI_HOME/NOVA_COMFYUI_LAUNCHER), hidden-window + logs/comfy/ redirect (mirrors LlamaControl), polls :8188 up to 120s. generate_image now SELF-HEALS: painter down → wake him → paint.
- tool_router.py: start_painter registered (AVAILABLE_TOOLS, dispatch w/ aliases, list_tools text); "painter isn't running" messages now tell her the switch is HERS.
VERIFIED: compiled clean; ComfyUI actually woken via her code path at ~21:38 ("ComfyUI reachable"); what_can_i_paint_with through tool_router lists mediums.

FIX 2 — HIS ASKS WERE SILENTLY DISCARDED SECONDS AFTER SHE REPLIED (the amnesia).
runtime.py's poll loop consumed the standing cole-directive the moment she was last speaker (~seconds after any reply), racing and defeating apply_decision's designed lifecycle (release on task-creation or 3-wake valve). AND no prompt ever showed her the directive text — she was expected to remember asks from a rolling 14-message window. Receipt: cole_intent.json "Nova. Fucking boot the comfyui and draw..." consumed:true with no task ever created.
- runtime.py: poll-loop consumption REMOVED (lifecycle now owned solely by apply_decision).
- executive.py: build_reflection + build_decision now SURFACE the standing ask verbatim ("COLE'S STANDING ASK — ... DO it this wake or `create` a task NOW").
VERIFIED: events now show wake reason "directive" (21:44:13, 21:44:54 — never seen before tonight); directive_seen increments; informational comments release via the 3-wake valve as designed.

FIX 3 — HER SAVED REFLECTION WAS HALF MACHINE DROPPINGS (hallucination feeder).
save_reflection stored raw generation text incl. tool-loop residue (```json husks, "[`tool` resulted in N bytes.]"), re-read to her every wake as "your last thought" — husk-shaped context that confabulation grows on. Added _strip_tool_residue() in executive.py; save_reflection stores clean prose. VERIFIED: stripper tested against live contaminated state; post-fix reflection stored CLEAN.
(Second contamination path noted, NOT yet fixed: she sometimes writes transcript-style fake quotes — "[11:40] Cole: ..." — into board progress notes (see t30), which later wakes read back as things Cole said. Candidate next fix: sanitize/attribute progress notes. Model-side confabulation of file paths persists but she self-corrects with receipts.)

OPERATIONAL NOTES:
- 2x /api/restart/novachat tonight (loads new code, llama+ComfyUI survive). HAZARD LEARNED: restarts can trip the llama error-backoff (server.py ~1452) which AUTO-PAUSES autonomy (enabled→false). It did tonight; re-enabled via the app's own UI toggle (#auto-toggle → "auto-toggle on", state confirmed true). EVERY later run: re-verify enabled after ANY restart.
- ~21:45 Cole told Nova: "Your v6 LoRa was awful, so we rolled back to v5." At 21:47 llama :8080 was DOWN — Cole mid-rollback. Run 1's "/api/lora should show nova_core_v6_epoch1" expectation is SUPERSEDED: v5 loaded is now CORRECT; do NOT "fix" it back to v6.
- ComfyUI up since ~21:38 (self-started). If down on later runs, generate_image self-heals now; a start_painter receipt failing repeatedly = read logs/comfy/.
- autonomy_state "active":"t40" still stale-points at an abandoned task (cosmetic; wakes decide correctly).

VERDICT: FIXED-THIS-RUN x3 (painter agency, directive amnesia, reflection hygiene). Pending at write time: llama back up post-rollback + autonomy re-enabled after it (checked below).

CLOSE-OUT 21:54: Cole's LoRA-equip flow (memory/active_lora.txt → v5_epoch2:1.0, written 21:42) had stopped llama but the relaunch never fired; Nova sat unable to answer his Wake presses ~21:45–21:52. Restored via POST /api/llama/start (boots HIS configured loadout). CONFIRMED: :8080 up, /api/lora = nova_core_v5_epoch2.gguf scale 1.0, autonomy enabled:true, ComfyUI up, wake "directive" firing on new code. Stack fully healthy on v5. LATER RUNS: expected LoRA is now V5_EPOCH2 (Cole's decision, 21:45); v6 was rolled back as "awful" — do not restore it.

## Run 2 — 2026-07-18 22:04–22:55 KST — ⚠️ ENDS DEGRADED, SELF-INFLICTED. COLE: READ THIS FIRST.

TL;DR for Cole: nova_chat (:8765) is FROZEN and I could not unfreeze it from a scheduled run (computer-use needs your approval; the API path is the very thing that's wedged). Nova is effectively DOWN until you do a clean restart. Recovery steps at the bottom. This is my fault — I ran a diagnostic that hung her chat server. I'm sorry.

STATE AT START (pre-existing, NOT caused by me):
- autonomy_state enabled=FALSE (auto-paused earlier, consistent with the restart-backoff hazard from Run 1). active still "t40" (cosmetic).
- llama :8080 UP and healthy BUT running BARE — /lora-adapters = [] (NO v5 personality adapter). active_lora.txt and active_lora.json both correctly say nova_core_v5_epoch2.gguf:1.0, so config is right; the boot just didn't apply it.
- nova_chat :8765 up and serving; hub :8799 up; ComfyUI down (not checked deeply).

ROOT CAUSE of the bare-LoRA (real, recurring, predates me — this is the important finding):
In-app llama restarts go LlamaControl.start() → `cmd /c start_llama_qwen36.cmd`. On a stop→start, the OLD launcher cmd is orphaned and RESUMES reading the batch file at a stale byte offset, executing comment/line FRAGMENTS as commands. Receipts in logs/llama/llama-2026-07-18.log: boots at lines 7499 / 7625 / 7732 show `[Nova] context: 65536` with NO `Starting Qwen` banner and NO `[Nova-core] personality adapter` line, surrounded by a storm of `'COREKOELS_LORA"' is not recognized`, `'ComfyUI' is not recognized`, `'negligible' is not recognized` (fragments of the .cmd's own REM comments). The `set NOVA_CORE`/`NOVA_EXTRA` block gets skipped → llama boots with no --lora → bare base model. This is a SECOND path of the launcher's "worst class of bug: a SILENT one" already documented in the .cmd header. It fires on the in-app Full-Restart / LoRA-equip flow, NOT on a fresh NovaStart (nova_start.build_llama_cmd builds --lora directly in Python from active_lora.json, bypassing the fragile .cmd) — so a clean NovaStart boots v5 correctly.

FIX APPLIED (ONE change, compiled, kept): nova_body/nova_runtime/llama_control.py `_kill_port()` now kills the launcher cmd (Get-CimInstance cmd.exe whose CommandLine matches start_llama_qwen36.cmd) FIRST, before the port owner and llama-server, so no orphaned launcher survives to resume-and-corrupt. `python -m py_compile` OK on her Windows interpreter. Partial verification: the new _kill_port EXECUTED cleanly once this run (POST /api/llama/stop → survivors empty, no stray cmd/llama). Corruption-PREVENTION is UNVERIFIED because I then wedged the box before a clean retest (below). Low risk, precisely scoped (only kills cmd.exe running the llama launcher). Recommend keeping.

WHAT I BROKE: to inspect the launcher I ran, through nova_chat's /api/terminal/run, `cmd /c "start_llama_qwen36.cmd < nul"`. terminal_run is an `async def` that calls a BLOCKING subprocess.run(timeout=30) ON the event loop; the launched llama-server (a grandchild) inherited terminal_run's stdout pipe, so communicate() never sees EOF and blocks the loop FOREVER. nova_chat's last activity is 22:29:28 (nova log stream frozen at seq 635; /api/llama/status hangs 45s). The whole :8765 server — API, WS autonomous_toggle, and the autonomy daemon — is frozen. LESSON (for later runs): NEVER run a long-lived/foreground process (esp. the llama launcher) through /api/terminal/run; it will wedge her. Use POST /api/llama/{stop,start} for llama.

WHY I COULDN'T SELF-RECOVER: (1) every :8765 endpoint is dead, so /api/restart/novachat, /api/llama/*, and the WS toggle are all unreachable. (2) computer-use (desktop control to taskkill / relaunch) is BLOCKED in a scheduled run — needs Cole to approve. (3) hub :8799 only exposes show/shutdown/pids/streams/log — /api/shutdown would tear down the stack AND exit nova_start (no supervisor relaunches it; NovaStart is one-shot), and nova_start's tracked llama/nova handles are STALE (I'd restarted both out-of-band earlier), so shutdown would kill the hub/watcher and STILL leave the wedged nova_chat + bare llama running — strictly worse and blind. So I deliberately did NOT trigger it. (4) I did NOT hand-edit any state file (HARD RULE 1).

RECOVERY (Cole — ~2 min): easiest is a clean full restart.
  1. Kill the bare/hung llama that's holding the pipe: `taskkill /F /IM llama-server.exe`
  2. Kill the frozen chat server (owner of :8765): in a terminal —
     `for /f "tokens=5" %a in ('netstat -ano ^| findstr :8765') do taskkill /F /PID %a`
     (or just fully Quit Nova from the Console tray / reboot the machine).
  3. Double-click NovaStart.cmd. It boots llama with v5 DIRECTLY from active_lora.json (bypasses the buggy .cmd), so confirm the llama-server tab shows `[Nova-core] personality adapter: ...nova_core_v5_epoch2.gguf:1.0` and GET /api/lora lists it (NOT []).
  4. autonomy_state is enabled=FALSE — flip autonomy ON in the UI (#auto-toggle) after the stack is healthy. Verify wake fires.
With the llama_control.py fix in place, future in-app Full-Restarts / LoRA-equips should stop stripping the adapter — but please watch the first one and confirm /api/lora stays populated.

VERDICT: DEGRADED (self-inflicted nova_chat wedge; pre-existing bare-LoRA + autonomy-off). Root cause of the recurring bare-LoRA diagnosed and a fix committed but unverified. Needs Cole's manual restart to come back.

## Run 3 — 2026-07-18 23:04–23:12 JST — STILL DEGRADED, BLOCKED ON COLE. Nova is DOWN; a scheduled watcher CANNOT revive her. COLE: 30-second fix at the top.

⭐ COLE — FASTEST FIX (do this first): **Reboot the PC, then double-click `NovaStart.cmd`.** A reboot clears every wedged/orphaned process at once; NovaStart then boots llama with your v5 adapter directly from active_lora.json. That's it. (Manual, no-reboot steps are in Run 2's RECOVERY block above if you prefer.) IMPORTANT ORDERING: do NOT double-click NovaStart while the old stack is still up — the bare llama is holding :8080, so a fresh NovaStart would halt on "model not ready." Reboot (or fully kill the old stack) FIRST, then launch.

WHY A WATCHER CAN'T FIX THIS (the important escalation): I confirmed FIRST-HAND this run that computer-use (desktop control to taskkill/relaunch) returns "can't be approved during a scheduled run" — it needs you awake to approve, or the app added to the scheduled task's settings. So every HTTP lever into her is dead (see below) AND the one non-HTTP lever is gated. No overnight run can self-heal a wedged nova_chat. She will stay down until you act. This is not new breakage — it's Run 2's wedge, unchanged.

STATE (verified, identical to where Run 2 left it — nothing moved on its own):
- nova_chat :8765 — event loop FROZEN. Hub nova-stream stuck at seq 635 across repeated polls; nova_launcher.log last line 22:29:28 and dead since; /api/llama/status times out >8s. All API/WS/autonomy-daemon dead.
- llama :8080 — UP + healthy but BARE: GET /lora-adapters = [] (no v5 personality). This is the terminal_run-spawned server from ~22:29 that is also the pipe-holder wedging nova_chat.
- hub :8799 — UP (only show/shutdown/pids/streams/log). ComfyUI :8188 — DOWN. autonomy_state enabled = FALSE, active still "t40" (cosmetic).
- Last real activity: last wake 22:01:19 ("woke up clean on this new build" — she was briefly alive on v5); last tool_call 21:54; last cole_message 22:01:11. All pre-wedge.

WHY NO HTTP SELF-RECOVERY (re-derived and re-confirmed, not taken on faith):
- nova_chat's loop is blocked inside subprocess.run()'s post-timeout communicate(), waiting on a stdout pipe the spawned llama-server keeps open. No HTTP handler can run, so /api/restart/novachat, /api/llama/*, and the WS toggle are all unreachable. The 30s timeout can't fire (grandchild holds the pipe) — it's been wedged 40+ min; it will not self-clear.
- Killing that llama-server would close the pipe and unwedge her — but that's a Windows process kill, and computer-use is gated (above). Bash is a separate Linux sandbox; it cannot touch Windows processes. llama-server has no HTTP shutdown route.
- Read nova_start.py end-to-end: it is one-shot, NO supervisor/relaunch of dead children (main() blocks on app_proc.wait()); and _bg_llama_autostart fires ONCE at boot, no watchdog loop. So nothing auto-restarts llama or nova_chat.
- hub /api/shutdown STILL rejected (as Run 2): nova_start's tracked llama/nova handles are stale, so it would tear down the hub+watcher+launcher and EXIT while leaving the wedged nova_chat + bare llama orphaned — strictly worse, and it kills my only observability. Did NOT trigger it.

WHAT I VERIFIED / SECURED THIS RUN (no state-file edits, no restarts, no risky ops, ZERO changes — HARD RULE 4 budget untouched):
- Run 2's llama_control.py `_kill_port` fix is present, compiles, and is correctly scoped: it kills the launcher cmd.exe (matched by CommandLine LIKE start_llama_qwen36.cmd) FIRST, then the port owner, then llama-server by name — precisely targeting the orphaned-launcher-resume path that was silently stripping --lora. Sound; keep it. Watch /api/lora after your first in-app Full-Restart to confirm it holds.
- All 6 code files Run 1/2 touched (llama_control, imagination, tool_router, runtime, executive, server) compile clean — no landmine waiting in your restart.
- active_lora.txt AND active_lora.json both = nova_core_v5_epoch2.gguf : 1.0 (Cole's post-rollback choice). A clean NovaStart boot builds --lora in Python straight from that (bypassing the fragile .cmd), so it will load v5 correctly. Do NOT restore v6 — Cole rolled it back as "awful" (21:45).

No AUDIT / ACTIVE TEST this run: the autonomy daemon is frozen (no new receipts to audit) and the create-task path routes through the dead :8765 API (can't plant a board test). Both resume once she's restarted.

PREVENTION (optional, for next time): if you want an overnight watchdog to be ABLE to recover a wedge like this without you, add the needed app (e.g. Task Manager) to this scheduled task's computer-use settings — that's the only thing that would let a headless run kill+relaunch. Absent that, keep the terminal_run guard in mind: never run a long-lived/foreground process (esp. the llama launcher) through /api/terminal/run — that's what wedged her.

VERDICT: DEGRADED — BLOCKED ON COLE. No change made (nothing safely actuatable from a scheduled run). Stack set up to recover correctly on your restart; the fix that should stop the recurring bare-LoRA is in place and compiles.

## Run 4 — 2026-07-19 00:04–00:22 KST — STILL DEGRADED, BLOCKED ON COLE (unchanged since Run 3). Two fixes at top; new: 1-double-click recovery pre-staged.

⭐ COLE — FASTEST FIX (either works):
  • **No-reboot:** double-click `_admin\autonomy_watch\nova_recover_llama.cmd` (I wrote it this run). It kills ONLY the orphaned launcher cmd + the bare llama-server that are wedging nova_chat. :8765 unfreezes within seconds. THEN open Nova and hit the llama **Full Restart** (or Start) so llama reloads your v5 adapter, and flip **autonomy ON** (#auto-toggle). Receipt of what it killed lands in `_admin\autonomy_watch\nova_recover_result.txt`.
  • **Cleanest:** **reboot the PC, then double-click `NovaStart.cmd`** — clears every wedged process at once and boots llama with v5 straight from active_lora.json. Then flip autonomy ON. (Do NOT double-click NovaStart while the old stack is still up — the bare llama holds :8080 and NovaStart halts on "model not ready." Reboot, or run the recover .cmd, FIRST.)

STATE (fresh receipts this run — identical to Run 3; nothing moved on its own):
- nova_chat :8765 — FROZEN. Hub "nova" stream stuck at **seq 635, last line 22:29:28** (~1h55m of silence); direct probe timed out >8s. The loop is blocked in terminal_run's `subprocess.run()` post-timeout `communicate()`, which on Windows takes NO timeout and waits forever on a stdout pipe the bare llama-server holds → it will NEVER self-recover.
- llama :8080 — UP but BARE (`/lora-adapters = []`). This IS the terminal_run-spawned pipe-holder.
- hub :8799 — UP (runs inside nova_start's process, alive but blocked on app_proc.wait()). watcher — ALIVE (git auto-commits every few min, seq 1260 — the ~00:07-00:11 mass FILE_INDEX/header churn is just its normal manifest regen, NOT a concurrent editor). autonomy_state enabled=FALSE; active "t40" (cosmetic).

WHY A SCHEDULED RUN STILL CAN'T SELF-HEAL (re-derived first-hand, not taken from Run 3):
- Recovery REQUIRES killing a Windows process (the bare llama-server holding the pipe). Every lever confirmed dead THIS run: (1) computer-use request_access("File Explorer") → **"can't be approved during a scheduled run"** — the real gate (an earlier terminal request only returned the click-mode notice, which misled me for one step). (2) terminals grant click-only (no typing). (3) bash = Linux sandbox, can't touch Windows PIDs. (4) live HTTP is only :8080 (llama — no exec/shutdown route), :8799 (hub — API is show/shutdown/pids/streams/log only, no kill) and the FROZEN :8765. The one endpoint that could taskkill — terminal_run — is the thing that's wedged.
- hub /api/shutdown re-ruled-out (re-read nova_start.py end-to-end): it flips a flag a daemon thread reads → terminate()s app_proc+nova_proc → main() exits. nova_start's llama handle is stale (bare llama spawned out-of-band), so it would NOT kill the bare llama, WOULD kill hub+watcher, and EXIT nova_start (one-shot, no relaunch) → wedged nova_chat + bare llama orphaned with nothing to revive them, and I lose observability. Strictly worse. Did NOT trigger it.

WHAT I DID THIS RUN (no code or state change; ONE-change budget intact):
- **Pre-staged `_admin/autonomy_watch/nova_recover_llama.cmd`** — turns Run 2/3's hand-typed taskkill into a scoped double-click. Two standard Stop-Process calls (orphaned launcher cmd FIRST so it can't resume-and-respawn a pipe-re-inheriting server, then llama-server), writes a receipt, touches no data/state files. This is the no-reboot path above.
- **Compile-checked all 6 files prior runs edited** (llama_control, imagination, tool_router, runtime, executive, server) — ALL OK. No syntax landmine in your reboot. Run 2's `_kill_port` fix (kill launcher cmd first → stops the recurring bare-LoRA on in-app restarts) is present and sound; watch /api/lora after your first in-app Full-Restart to confirm it holds.
- Verified active_lora.txt/.json both = nova_core_v5_epoch2.gguf:1.0 and the adapter file exists → any clean boot loads v5. Do NOT restore v6 (rolled back "awful" 07-18 21:45).

ROOT CAUSE worth a VERIFIED daytime fix — documented, NOT shipped blind (I can't restart/verify from here and won't push untested code into your recovery boot): `terminal_run` (general_tools/nova_chat/server.py ~L1653) runs a BLOCKING `subprocess.run(timeout=30)` directly ON the asyncio loop; when a launched grandchild keeps the stdout pipe open, the post-timeout communicate() hangs forever and freezes the WHOLE server. Fix to apply+verify awake: move the sp.run into a local `_run_blocking()` and call `proc = await asyncio.to_thread(_run_blocking)`, so a hung command can only stall its own worker thread — Nova stays alive/autonomous. (Follow-up: on TimeoutExpired, tree-kill via CREATE_NEW_PROCESS_GROUP so orphaned grandchildren don't leak.) NOTE: this wedge came from a WATCHER running `cmd /c start_llama_qwen36.cmd` through terminal_run (Run 2's self-inflicted mistake), NOT from Nova's normal autonomy — recurrence risk from her own behavior is low; the guard is for future watchers.

PREVENTION so a future overnight run CAN self-heal a wedge like this: add **Task Manager** (or File Explorer) to THIS scheduled task's computer-use settings — the ONLY thing that would let a headless run kill+relaunch. And never run a long-lived/foreground process (esp. the llama launcher) through /api/terminal/run.

No AUDIT / ACTIVE TEST this run (daemon frozen → no receipts to audit; create-task routes through the dead :8765). Both resume once she's restarted.

VERDICT: DEGRADED — BLOCKED ON COLE (unchanged since Run 3). No code/state change. New this run: one-double-click recovery script staged; all touched files confirmed compiling; terminal_run root-cause patch written up for a verified daytime fix.

## Run 5 — 2026-07-19 01:04–01:12 KST — STILL DEGRADED, BLOCKED ON COLE (3rd consecutive run; wedge age ~2h40m). Nothing moved; no new lever.

FRESH PROBES (all first-hand this run, not inherited):
- nova_chat :8765 — still FROZEN: /api/llama/status aborted at 8.9s; hub "nova" stream still seq 635 (last line 22:29:28). Dead: all API, WS toggle, autonomy daemon, create-task path.
- llama :8080 — UP, /health ok, still BARE: /lora-adapters = `[]`. Its log shows only idle-slot heartbeats since boot (~22:29); the Jul-19 00:18 mtime was Run 4's probes, not activity.
- hub :8799 — UP (4ms). Watcher ALIVE: stream seq 1260→1283 since Run 4; last auto-commits 00:15/00:23 align exactly with Run 4's own file writes (watcher is change-triggered; silence since = static workspace, not death).
- ComfyUI :8188 — down (refused). Irrelevant until she's back; generate_image self-heals (Run 1 fix).
- autonomy_state: enabled=false, unchanged. No events-2026-07-19.jsonl, no tool_calls since 21:54, no autonomy_runs since 22:01 → she has not woken once tonight.

LEVER RE-CHECK: computer-use allowlist EMPTY; request_access("File Explorer") → still "can't be approved during a scheduled run" (verbatim, re-confirmed 01:08). Noted for prevention advice: even a granted Task Manager would be useless (elevated → UIPI blocks input) and terminals grant click-only — **File Explorer** (to double-click the staged .cmd) is the ONE app that makes a headless recovery possible. Banner at top updated accordingly.

CHANGES: none to code or state. Deliberately did NOT ship the terminal_run/asyncio.to_thread patch into the recovery boot path — Run 4's reasoning stands (py_compile can't catch a runtime slip; Cole's recovery restart must load known-good code). Only edit this run: this report (STATUS NOW banner + this entry).

NO AUDIT / ACTIVE TEST possible (daemon frozen, no new receipts, create-task routes through dead :8765). Resumes automatically once Cole restarts her; next run after recovery should do the full health→audit→board-test cycle immediately, incl. verifying /api/lora holds v5 through the in-app restart (first live test of Run 2's _kill_port fix).

VERDICT: DEGRADED — BLOCKED ON COLE. Watchdog can add no further value until he runs the 1-minute recovery; subsequent hourly runs will re-probe and pick up the moment she's back.
