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
