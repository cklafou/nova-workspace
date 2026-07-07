# Upgrade — Qwen 3.5 27B → Qwen 3.6 27B (Q6_K_XL + MTP)
_Last updated: 2026-07-08 08:44:42_
_2026-06-10. Box-side steps (Cole, on the Windows machine). The config edits (launcher, nova_client
sampling, docs) are already done by Cowork. Goal: 3.6 27B Dense, Q6_K_XL, MTP speculative decoding._

**Decisions locked:** quant = **Q6_K_XL** (~24GB, near-lossless, leaves VRAM for MTP + KoELS adapters);
**MTP = yes** (~1.4-2x faster gen, +~1GB); thinking mode **on** (default — best for autonomy reasoning).

---

## 0. Pre-checks (2 min)
- **CUDA:** `nvcc --version`. ⚠ **Do NOT use CUDA 13.2** (Unsloth: gibberish output). Use **< 13.2 or 13.3**.
  If you're on 13.2, update/downgrade the toolkit before rebuilding.
- **Disk:** Q6 GGUF (~24GB) + mmproj (~1-2GB) → have ~30GB free.
- **VRAM sanity:** Q6 (~24GB weights) + mmproj + 32K KV + MTP head should sit comfortably in your 40GB
  (you were at ~33GB on 3.5 Q8). If you ever OOM: drop context, or add `--cache-type-k bf16 --cache-type-v bf16`.

## 1. Back up the working setup (so rollback is trivial)
```
copy start_llama.cmd start_llama.cmd.bak
xcopy /E /I llama llama_qwen35_backup
```
(Your 3.5 model files in `models\` stay where they are — don't delete them until 3.6 is verified.)

## 2. Update llama.cpp to an MTP-capable build
MTP merged into llama.cpp in May 2026; your binary is ~2025-05 and will NOT run 3.6. Two ways:

**Option A — prebuilt CUDA release (recommended, easiest on Windows):**
1. Go to https://github.com/ggml-org/llama.cpp/releases and grab the latest **`llama-*-bin-win-cuda-x64.zip`**
   (any release from mid-2026 onward includes MTP + the `--spec-type draft-mtp` flag).
2. Extract it and replace the contents of your `llama\` folder with the new binaries
   (`llama-server.exe` + the CUDA DLLs). Keep the backup from step 1.
2b. **CRITICAL — the CUDA runtime DLLs (separate download).** The release ships `ggml-cuda.dll`
   but NOT the CUDA runtime it depends on. From the SAME release page, also download the
   `cudart-llama-bin-win-cuda-13.x-x64.zip` companion and extract its `cudart64_*.dll`,
   `cublas64_13.dll`, `cublasLt64_13.dll` into `llama\` (next to `ggml-cuda.dll`). Without these,
   `ggml-cuda.dll` fails to load and llama-server **silently runs on CPU** (loads + serves fine,
   but `nvidia-smi` shows the GPUs idle — the exact trap we hit). `ggml-cuda.dll` here wants
   CUDA **13** (`cublas64_13.dll`), matching the 13.3 driver.
3. Verify: `.\llama\llama-server.exe --version`  and  `.\llama\llama-server.exe --help | findstr spec-type`
   (the `--spec-type` flag must be present → MTP support is in). On the next boot, confirm the
   log prints `ggml_cuda_init: found 2 CUDA devices` and `nvidia-smi` shows VRAM in use.

**Option B — build from source (if you prefer):**
```
git clone https://github.com/ggml-org/llama.cpp
cmake llama.cpp -B llama.cpp\build -DBUILD_SHARED_LIBS=OFF -DGGML_CUDA=ON
cmake --build llama.cpp\build --config Release -j --clean-first --target llama-server llama-gguf-split llama-mtmd-cli
```
Then copy `llama.cpp\build\bin\llama-*.exe` (+ DLLs) into your `llama\` folder.

## 3. Download the model (Q6_K_XL MTP GGUF + mmproj)
```
pip install -U huggingface_hub
hf download unsloth/Qwen3.6-27B-MTP-GGUF --local-dir models\qwen3.6 --include "*UD-Q6_K_XL*" --include "*mmproj-F16*"
```
Then **check the actual filename** it wrote into `models\qwen3.6\` and make sure
`start_llama_qwen36.cmd` points at it. The launcher currently expects:
`models\qwen3.6\Qwen3.6-27B-MTP-UD-Q6_K_XL.gguf` and `models\qwen3.6\mmproj-F16.gguf`.
If the download named the GGUF differently (or split it into `-00001-of-000xx` parts), update the
`-m` line in the launcher to match (for split files, point `-m` at the first part).

## 4. Smoke-test the model ALONE (before bringing Nova up)
Run the new launcher directly:
```
start_llama_qwen36.cmd
```
- Watch for a clean load (no OOM, no "unknown argument").
- In another terminal: `curl http://127.0.0.1:8080/health` → expect `{"status":"ok"}`.
- Quick gen test: `curl http://127.0.0.1:8080/v1/chat/completions -H "Content-Type: application/json" -d "{\"messages\":[{\"role\":\"user\",\"content\":\"say hi in 5 words\"}]}"`
- **If output is gibberish:** check CUDA (step 0), and/or add `--cache-type-k bf16 --cache-type-v bf16`
  to the launcher. If it complains about `--jinja` or `--spec-type`, your llama.cpp build is too old (redo step 2).

## 5. Point Nova at the new launcher
Once the smoke test is clean, make the runtime use the 3.6 launcher. Cleanest one-liner — in
`nova_body/nova_runtime/runtime.py`, `NovaRuntime.__init__`, change:
`self.llama = LlamaControl(self.workspace)` →
`self.llama = LlamaControl(self.workspace, launcher="start_llama_qwen36.cmd")`
(LlamaControl's `launcher` param already exists.) Then start Nova normally (NovaLauncher).
Rollback = change it back to the default (`start_llama.cmd`).

## 6. Verify Nova end-to-end (the usual)
- Clean boot: no errors dated today in `logs\nova_launcher.log`.
- A real generation streams in the UI; `logs\events\events-<today>.jsonl` shows wake/reflect/autonomy.
- Tell Cowork "3.6 is up" and it can re-run the filesystem + Chrome-UI verification pass.

## 7. Rollback (if needed)
- Point `self.llama` back at `start_llama.cmd` (or restore `start_llama.cmd.bak`).
- Restore the old binary: delete `llama\`, rename `llama_qwen35_backup\` → `llama\`.
- The 3.5 model files were never removed, so this fully restores the prior working state.

---

### What Cowork already changed (no action needed)
- `start_llama_qwen36.cmd` — the new launcher (3.6 + `--jinja` + MTP flags + inert KoELS `--lora` hook).
- `nova_client.py` — sampling tuned for 3.6 (`top_k 20`, `min_p 0.0`; `repeat_penalty 1.15` kept as
  loop insurance — lower toward 1.0 if quality dips).
- Docs (STATUS / body manifest): NOT changed yet — they correctly still say 3.5 until 3.6 is live.
  Tell Cowork once you've verified it and it'll flip the "current model" line to 3.6 (so her status
  files never lie about her actual state).

### Open watch-items
- `-fa on` + MTP + (later) KoELS `--lora` together on your exact build — flagged for the smoke test.
- `repeat_penalty`: 3.6 prefers 1.0; we kept 1.15 as anti-loop insurance. Tune if needed.
- Context stays 32K (3.6 supports 256K via YaRN — raise later only if VRAM allows).
