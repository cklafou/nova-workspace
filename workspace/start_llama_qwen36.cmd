@echo off
REM @nova: Qwen 3.6 27B launcher (upgrade from 3.5). Dense + hybrid-thinking + MTP speculative
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
title llama.cpp Qwen 3.6 27B — Dual GPU (4090 + 3090 eGPU) [MTP]
cd /d "%~dp0"

echo [llama.cpp] Starting Qwen 3.6 27B Dense Q6_K_XL + MTP, dual-GPU split...
echo.
echo GPU layout: GPU 0 = RTX 4090 Laptop (16GB), GPU 1 = RTX 3090 eGPU (24GB)
echo Tensor split: 12,28. Q6 is ~24GB so there's comfortable headroom (MTP + KoELS adapters).
echo Model : models\qwen3.6\Qwen3.6-27B-UD-Q6_K_XL.gguf  (MTP variant - nextn head present)
echo Vision: models\qwen3.6\mmproj-F16.gguf
echo MTP   : ON  --spec-type draft-mtp --spec-draft-n-max 2  (try 1-6, fastest wins; 2 usually best)
echo Port  : 8080   Context: 32768
echo.

if not exist "prompt_cache" mkdir "prompt_cache"

REM ── Nova-core: personality LoRA. The Nova Chat LoRA menu's "equip" writes memory\active_lora.txt
REM ── (a ready "--lora-scaled models\...\file.gguf:WEIGHT" line) to pick WHICH adapter boots and at
REM ── what weight. Absent/empty -> the v2 default below (so boot is unchanged until you pick one).
REM ── Rides in the BASE command so any KoELS specialist swap stacks ON TOP of her personality. ──
set "NOVA_CORE="
if exist "memory\active_lora.txt" set /p NOVA_CORE=<"memory\active_lora.txt"
if not defined NOVA_CORE if exist "models\qwen3.6\nova_core_v2_e2.gguf" set "NOVA_CORE=--lora-scaled models\qwen3.6\nova_core_v2_e2.gguf:0.6"
if defined NOVA_CORE echo [Nova-core] personality adapter: %NOVA_CORE%

REM ── KoELS: read the runtime-written boot --lora set (empty when Nova-core only) ──
set "KOELS_LORA="
if exist "memory\koels_lora_args.txt" set /p KOELS_LORA=<"memory\koels_lora_args.txt"
if defined KOELS_LORA echo [KoELS] preloading adapters: %KOELS_LORA%

.\llama\llama-server.exe ^
    -m models\qwen3.6\Qwen3.6-27B-UD-Q6_K_XL.gguf ^
    --mmproj models\qwen3.6\mmproj-F16.gguf ^
    -ngl 999 ^
    -ts 12,28 ^
    -c 65536 ^
    --parallel 1 ^
    -fa on ^
    --jinja ^
    --reasoning-format deepseek ^
    --spec-type draft-mtp ^
    --spec-draft-n-max 2 ^
    --cache-prompt ^
    --slot-save-path prompt_cache ^
    -b 2048 ^
    -ub 1024 ^
    --port 8080 ^
    --host 127.0.0.1 ^
    %NOVA_CORE% ^
    %KOELS_LORA%

pause
