# Nova-Core v3 — overnight training run status
_Launched 2026-07-07 ~14:54 UTC by the Cowork Opus session while Cole slept._

## What's running
- **Pod:** `dshspj5dwaop0l` (visual_peach_leopon-migration), A100-80GB, ~$1.51/hr. Balance was ~$27.46.
- **Dataset:** `/workspace/v3/nova_core_v3.jsonl` = **167 rows** (108 v2 + 59 additions), merge JSON-validated.
- **Config:** rank 16 / alpha 32 / 2 epochs / LR 1e-4 / max_length 4096 (Fable's script, `assistant_only_loss` with auto-fallback to full-sequence if the mask is degenerate).
- **Pipeline:** `/workspace/v3/pipeline.sh` (PID 2987, nohup). Does: train (attempt 1 = assistant_only; auto-retry full-sequence if first loss ~0.0 or no checkpoints) → convert the last 2 epoch checkpoints to GGUF. Runs independently of the Cowork session.
- **Base model:** `unsloth/Qwen3.6-27B` — public (HTTP 200), downloading now **unauthenticated** (slower; no token was needed).

## How to check state (pod JupyterLab terminal)
```
cat /workspace/v3/PIPELINE_STATUS.txt      # RUNNING | DONE ggufs=N | FAILED ...
tail -20 /workspace/v3/pipeline.log
ls -la /workspace/v3/nova_core_v3_*.gguf   # the output adapters (appear when DONE)
```

## Automatic finish + shutdown
A scheduled task **`nova-v3-finish-and-stop-pod`** runs every 15 min. When the pipeline is DONE it downloads the GGUF(s) to this PC and **Stops the pod** (halting billing); if it FAILED or stalled it Stops the pod anyway and reports. It writes results to `V3_TRAINING_RESULT.md`.

> **Pre-approve it:** open the Scheduled panel and click **Run now** once so it can use Chrome + files without pausing on a permission prompt while you sleep.

## ⚠️ Honest risks / manual fallback
- **The pod can't stop itself** (`runpodctl` is Unauthorized on this pod), so shutdown depends on the scheduled watcher running — which needs the Cowork app open. If the app is closed, the watcher runs on next launch.
- **If you wake and the pod still shows billing** at console.runpod.io/pods → open pod `dshspj5dwaop0l` → **Stop** (not Terminate). The trained GGUF is safe on the pod volume at `/workspace/v3/nova_core_v3_*.gguf` even after Stop (restart briefly to download if needed).
- Optional: to speed the base download / avoid rate limits, put your HF token as the only line in `/workspace/hf_token.txt` — the pipeline sources it automatically (I never see it). The current run already started unauthenticated, so this would only help a restart.

## Next step for you (after GGUFs are down)
Equip + A/B: move the chosen `nova_core_v3_checkpoint-*.gguf` into `models\qwen3.6\`, point `nova_start.py`'s `--lora-scaled` at it **starting at `:1.0`** (the whole point of v3 — no 0.6 dilution), restart, and A/B both epochs at weight 1.0 with the 06-22 harness (12-turn convo + idle autonomy + topic-shift + autonomy-continuation checks).
