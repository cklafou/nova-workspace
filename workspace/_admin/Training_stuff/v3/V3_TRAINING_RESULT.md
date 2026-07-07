# Nova Core v3 — Training Result
_Last updated: 2026-07-08 08:56:41_

**Run:** automated check 2026-07-08 (pod time 2026-07-07 ~15:11 UTC)
**Final status:** ✅ DONE — pipeline.log: `[2026-07-07T15:10:01Z] PIPELINE DONE` (`convert done: ggufs=2`)

## Outputs

| File | Size | Location |
|---|---|---|
| nova_core_v3_checkpoint-21.gguf | 159,419,232 B (~152 MB) | pod `/workspace/v3/` + downloaded |
| nova_core_v3_checkpoint-42.gguf | 159,419,232 B (~152 MB) | pod `/workspace/v3/` + downloaded |

Two epoch checkpoints produced (checkpoint-21 = epoch 1, checkpoint-42 = epoch 2), each converted to GGUF.

**Downloads:** triggered to this machine's Downloads folder via Jupyter. Note: the task's `/files/v3/...` URL 404'd — correct path was `/files/workspace/v3/<file>`. Both triggered successfully; couldn't verify completion from the session (no Downloads folder access), so check `Downloads\nova_core_v3_checkpoint-*.gguf`. Backup copies persist at `/workspace/v3/` on the pod's 200 GB network volume.

## Pod

**STOPPED** (Stop, not Terminate) at ~15:12 UTC. Console confirms: Compute + Container storage "Not running", **Total $0.00/hr**. Billing halted. Volume `visual_peach_leopon_volume` (200 GB, mounted `/workspace`) preserved — pod can be restarted later if re-download is needed. This scheduled task has been disabled.

## Next step (equip)

1. Move the chosen GGUF into `models\qwen3.6\`
2. Point `nova_start.py --lora-scaled` at it starting at **:1.0** (not 0.6)
3. Restart
4. A/B both epochs (checkpoint-21 vs checkpoint-42) at weight 1.0

---
## Opus verification (live-watched the whole run)
- I watched training end-to-end: **42/42 steps, loss healthy at ~2.1** (NOT the degenerate ~0.0 case), `assistant_only_loss` mask engaged the entire run — no full-sequence fallback needed. Both epoch checkpoints saved and converted to GGUF cleanly. The adapter trained correctly.
- Confirmed in the console: pod **STOPPED, $0.00/hr** — billing halted, volume preserved.
- **Download caveat — please check when you wake.** The only path from the pod to your PC is the RunPod JupyterLab `/files/` proxy, and it was flaky tonight: `/files/v3/…` returned 404, and `/files/workspace/v3/…` hit a JupyterLab "workspace" routing collision. So I can NOT confirm the two GGUFs actually landed in your **Downloads** folder.
  - **Check:** `Downloads\nova_core_v3_checkpoint-21.gguf` and `…-42.gguf` (~152 MB each).
  - **If present →** equip (steps above).
  - **If missing →** they're safe on the pod's 200 GB volume at `/workspace/v3/`. Restart the pod once, download via the JupyterLab file browser (right-click → Download builds the correct URL), then Stop it again — a couple cents. Or ping me next time we're both online and I'll fetch them.
