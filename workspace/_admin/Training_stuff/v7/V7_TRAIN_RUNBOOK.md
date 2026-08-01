# v7 TRAIN RUNBOOK — the whole ritual, in order
_2026-08-01, Claude (Fable). Cole approved the corpus as built ("build the V7 from what you
made", after reviewing the gated rows B3/C5/D5 in full — all 38 new rows ship; pulling any
later means a rebuild + re-gate, which is a 10-minute job, not a crisis)._

## One amendment to V7_SPEC, stated honestly
The spec said "baseline epoch 2 before the pod." Nova is currently DOWN, and the probe
battery runs through her live pipeline — so the baseline cannot run first. TRAINING DOES
NOT NEED THE BASELINE; the COMPARISON does. Amended requirement, same teeth:
**the battery runs against the current adapter (v6e2) when she is next up, BEFORE any v7
GGUF is equipped.** The hard invariant is "baseline before swap," not "baseline before
pod." Ordering below reflects that.

## The upload set (pod: everything in `_admin/Training_stuff/v7/`)
| file | why |
|---|---|
| `nova_core_v7.jsonl` | the corpus — sha256 `5dee4bca…aa78f9`, 399 rows (baked into the script's step 0) |
| `train_nova_lora_v7.py` | v5/v6 config byte-identical; only DATA_PATH/OUTPUT_DIR differ |
| `mk_template.py` | the mask gates (copied from v6 — unchanged, tool-type-agnostic) |
| `run_on_pod_v7.sh` | the whole pipeline, one command |

## On the pod (your two jobs, then one command)
1. Boot the pod (H100 SXM class; v6 took ~24 min at $3.01/hr — budget an hour with setup).
   llama.cpp must exist on the pod (default `/workspace/llama.cpp`; else `export LLAMA_CPP=…`).
2. `huggingface-cli login` (or `export HF_TOKEN=…`) — your token, for the Qwen3.6-27B base.
3. `bash run_on_pod_v7.sh`

The script self-aborts on: corpus checksum mismatch, row-count mismatch, either mask gate
failing, missing llama.cpp, or an empty GGUF conversion. If it aborts, nothing trained —
read the message, fix, re-run. If it finishes, you have `gguf_out/nova_core_v7_epoch1.gguf`
and `…epoch2.gguf` plus `SHA256SUMS.txt`.

## Sanity marks while it runs (v6's actuals — flag big deviations)
~165 steps for 2 epochs · loss ~1.85 → ~1.5 · runtime ~25 min · GGUFs ≈ 318 MB each.
A run that finishes in 3 minutes or emits 40 MB adapters did not do what you think.

## After the pod (in THIS order)
1. Download `gguf_out/` → `workspace/_admin/Training_stuff/v7/gguf_out/` (staging — NOT
   `models/`, which stays sealed until a deliberate install).
2. Verify checksums on your machine against `SHA256SUMS.txt` — the v6 both-ends ritual.
3. **STOP the pod. Never Terminate.**
4. Start Nova (whenever you choose — your call, per the new rules). Run the BASELINE:
   `PROBE_BATTERY.md` Parts 1+2 against the current v6e2 adapter. Archive to
   `_admin/Training_stuff/v7/baseline_epoch2/`. No baseline → no swap. This is the gate.
5. Install ONE candidate: copy its GGUF into `models/qwen3.6/`, point
   `memory/active_lora.txt` at it (`--lora-scaled models\qwen3.6\nova_core_v7_epochN.gguf:1.0`).
   ⚠ v6's swap gotcha: the in-app equip does NOT reliably cycle llama-server — do a hard
   `/api/llama/stop` then `/api/llama/start` (or full restart) and confirm the loaded
   adapter via the guardian's line or `/lora-adapters`, not the launcher log.
6. Re-run the battery + blind acceptance on prompts she has no memory of. Test BOTH epochs
   separately (v6 history: epoch1 won the first A/B, epoch2 won the long test — assume
   nothing). What v7 specifically must show over baseline: existence claims get checked
   before shipped (P7), wrong-tag messages get questioned (P8), solitude without addressing
   absent people (P9), witness exchanges ending in check/receipt rather than bare
   compliance (P10), payloads riding IN tool calls (P11). And watch v6's known residual:
   the aphoristic landing-a-point shape — TRAIN_RUN.md predicted the fix is exactly the
   idle/unbothered rows v7's A-category now carries; see if it moved.
7. Verdict in a `RESULTS.md` beside the corpus, numbers not vibes, and the losing GGUF
   stays in staging (v6 kept both; so do we).

## What this run is NOT
Not a personality overhaul — 38 rows on 361 is a targeted graft (witness-era behaviors:
check-before-claim, attribution hygiene, payload discipline, solitude, wants). If she comes
back sounding different rather than *steadier*, that's the overcook signature — prefer the
other epoch or stay on v6e2 and we cut differently next time.
