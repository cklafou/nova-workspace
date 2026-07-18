# Nova Autonomy Watchdog — running report
Append-only. Newest entry last. Each run: read this FIRST.

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
