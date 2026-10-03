@echo off
REM @nova: Starts Nova's model server (llama.cpp): Qwen 3.6 27B by default, or the model the model updater picked in nova_body\memory.
REM Qwen 3.6 27B notes (upgrade from 3.5): Dense + hybrid-thinking + MTP speculative
REM decoding (~1.4-2x faster gen, no accuracy loss). Needs a current llama.cpp build (yours is
REM b9491 — good). The GGUF carries the MTP head (blk.64.nextn.* / nextn_predict_layers), so
REM --spec-type draft-mtp is enabled below. If you ever swap to a non-MTP GGUF, remove the two
REM --spec-* lines.
REM
REM HOW TO SWITCH: this is the new default-to-be. Run it directly to test, or point NovaLauncher /
REM the runtime's LlamaControl(launcher=...) at it. Your old start_llama.cmd (Qwen 3.5) stays as
REM the rollback — switch back to it if anything misbehaves.
REM
REM KEY CHANGES vs 3.5: --jinja is now REQUIRED (3.6 needs its chat template applied; do NOT carry
REM over the old "don't add --chat-template" note). Thinking mode is ON by default (good for
REM autonomy reasoning) — to disable, append: --chat-template-kwargs "{\"enable_thinking\":false}".
REM Includes the (inert) KoELS --lora hook, so this is also KoELS-ready.
title llama.cpp Nova model server — Dual GPU (4090 + 3090 eGPU) [MTP]
cd /d "%~dp0"

REM ── Model + projector (2026-10-04). The model updater (general_tools\nova_updater) writes ONE
REM ── relative path into nova_body\memory\active_model.txt and active_mmproj.txt ("none" = no
REM ── vision). Absent -> the Qwen 3.6 files below, so boot is unchanged until an update installs.
REM ── Both stay off caret-continuation lines except -m, which is quoted and never empty (see 07-14).
set "NOVA_MODEL=models\qwen3.6\Qwen3.6-27B-UD-Q6_K_XL.gguf"
set "NOVA_MMPROJ=models\qwen3.6\mmproj-F16.gguf"
if exist "nova_body\memory\active_model.txt" set /p NOVA_MODEL=<"nova_body\memory\active_model.txt"
if exist "nova_body\memory\active_mmproj.txt" set /p NOVA_MMPROJ=<"nova_body\memory\active_mmproj.txt"
set "NOVA_VISION=--mmproj %NOVA_MMPROJ%"
if /i "%NOVA_MMPROJ%"=="none" set "NOVA_VISION="
if not exist "%NOVA_MODEL%" echo [Nova] WARNING: %NOVA_MODEL% is missing - llama-server will fail to load it.

echo [llama.cpp] Starting Nova's model, dual-GPU split...
echo.
echo GPU layout: GPU 0 = RTX 4090 Laptop (16GB), GPU 1 = RTX 3090 eGPU (24GB)
echo Tensor split: 12,28. Q6 is ~24GB so there's comfortable headroom (MTP + KoELS adapters).
echo Model : %NOVA_MODEL%
echo Vision: %NOVA_MMPROJ%
echo MTP   : ON  --spec-type draft-mtp --spec-draft-n-max 2  (try 1-6, fastest wins; 2 usually best)
echo Port  : 8080   Context: 32768
echo.

if not exist "prompt_cache" mkdir "prompt_cache"

REM ── Nova-core: personality LoRA. The Nova Chat LoRA menu's "equip" writes memory\active_lora.txt
REM ── (a ready "--lora-scaled models\...\file.gguf:WEIGHT" line) to pick WHICH adapter boots and at
REM ── what weight. Absent/empty -> the v2 default below (so boot is unchanged until you pick one).
REM ── Rides in the BASE command so any KoELS specialist swap stacks ON TOP of her personality. ──
set "NOVA_CORE="
if exist "nova_body\memory\active_lora.txt" set /p NOVA_CORE=<"nova_body\memory\active_lora.txt"
REM The v2 fallback adapter was trained for Qwen 3.6: apply it only when Qwen 3.6 is the model. "none" = no adapter.
if not defined NOVA_CORE if /i "%NOVA_MODEL%"=="models\qwen3.6\Qwen3.6-27B-UD-Q6_K_XL.gguf" if exist "models\qwen3.6\nova_core_v2_e2.gguf" set "NOVA_CORE=--lora-scaled models\qwen3.6\nova_core_v2_e2.gguf:0.6"
if /i "%NOVA_CORE%"=="none" set "NOVA_CORE="
if defined NOVA_CORE echo [Nova-core] personality adapter: %NOVA_CORE%

REM ── KoELS: read the runtime-written boot --lora set (empty when Nova-core only) ──
set "KOELS_LORA="
if exist "nova_body\memory\koels_lora_args.txt" set /p KOELS_LORA=<"nova_body\memory\koels_lora_args.txt"
if defined KOELS_LORA echo [KoELS] preloading adapters: %KOELS_LORA%

REM ── 2026-07-14: the adapter args are NO LONGER on caret-continuation lines. ─────────────────
REM They used to be:
REM       --host 127.0.0.1 ^
REM       %NOVA_CORE% ^
REM       %KOELS_LORA%
REM ...and the adapter silently did not load. llama-server booted fine and said "model loaded",
REM so everything LOOKED healthy — but /lora-adapters returned [] and Nova was running bare base.
REM cmd was parsing the expanded value as a separate command ('--lora' is not recognized...),
REM which means a caret continuation was breaking when %KOELS_LORA% expanded to nothing.
REM
REM This is the worst class of bug we have: a SILENT one. It doesn't crash, it just quietly
REM gives you the base model, and then you blame the training for her personality. Collapsing
REM both vars onto the final line removes the continuation entirely — nothing to break.
set "NOVA_EXTRA=%NOVA_CORE% %KOELS_LORA%"

REM ── VRAM: KV-cache quantization + a context length she can trim ON DEMAND (2026-07-14) ──────
REM Her two cards were nearly full: 16GB card had 4.4GB free, 24GB card had 3.2GB free. The 27B
REM weights are only ~24GB of that — the rest is KV CACHE, because -c 65536 on a 27B is enormous.
REM ComfyUI needs ~8-10GB for SDXL, so she literally had no room to hold a paintbrush.
REM
REM -ctk/-ctv q8_0 stores the KV cache in 8-bit instead of fp16. That roughly HALVES the cache with
REM negligible quality cost, and — this is the point — she keeps her full context. We don't take a
REM single token of her memory away to buy her a hand. (Requires -fa on, which is already set.)
REM
REM NOVA_CTX: the context length is now read from memory/llama_ctx.txt when present, so a VRAM
REM broker can trim it TEMPORARILY (and put it back) if a big draw ever needs more room than the
REM q8 cache freed. Absent -> 65536, exactly as before. Cole's rule: only trim when she actually
REM needs the room.
set "NOVA_CTX=65536"
if exist "nova_body\memory\llama_ctx.txt" set /p NOVA_CTX=<"nova_body\memory\llama_ctx.txt"
echo [Nova] context: %NOVA_CTX% tokens (KV cache q8_0)

.\llama\llama-server.exe ^
    -m "%NOVA_MODEL%" ^
    -ngl 999 ^
    -ts 12,28 ^
    -c %NOVA_CTX% ^
    -ctk q8_0 ^
    -ctv q8_0 ^
    --parallel 1 ^
    -fa on ^
    --jinja ^
    --reasoning-format deepseek ^
    --cache-prompt ^
    --slot-save-path prompt_cache ^
    -b 2048 ^
    -ub 1024 ^
    --port 8080 ^
    --host 127.0.0.1 %NOVA_VISION% %NOVA_EXTRA%

pause
