@echo off
REM @nova: KoELS-enabled launcher (Step: equip skeleton, LIVE-GATED). Identical to start_llama.cmd
REM except it appends the runtime-written boot --lora set so a specialist loadout is preloaded.
REM
REM HOW TO FLIP KoELS ON (after a real GGUF adapter exists + the quick -fa/per-adapter-VRAM check
REM passes on this build): point her runtime at this launcher instead of start_llama.cmd, e.g. in
REM NovaRuntime.__init__  ->  LlamaControl(self.workspace, launcher="start_llama_koels.cmd").
REM Revert = point it back at start_llama.cmd. Until then this file is inert (nothing runs it).
REM
REM The boot --lora set is written by nova_runtime/koels_equip.py on a self-restart-with-loadout
REM (memory\koels_lora_args.txt). Absent/empty file = no specialist = Nova-core only.
title llama.cpp Qwen 3.5 27B — Dual GPU (4090 + 3090 eGPU) [KoELS]
cd /d "%~dp0"

echo [llama.cpp] Starting Qwen 3.5 27B Dense Q8 with dual-GPU split... [KoELS launcher]
echo.
echo GPU layout assumed: GPU 0 = RTX 4090 Laptop (16GB), GPU 1 = RTX 3090 eGPU (24GB)
echo Run 'nvidia-smi -L' to verify. If reversed, swap -ts to 28,12 below.
echo.
echo Tensor split: 12,28 (4090 holds 30%% of layers, 3090 holds 70%%).
echo Model : models\qwen-27b-q8.gguf
echo Vision: models\qwen-27b-mmproj.gguf
echo Port  : 8080
echo Context: 32768 tokens
echo.

if not exist "prompt_cache" mkdir "prompt_cache"

REM ── KoELS: read the runtime-written boot --lora set (empty when Nova-core only) ──
set "KOELS_LORA="
if exist "memory\koels_lora_args.txt" set /p KOELS_LORA=<"memory\koels_lora_args.txt"
if defined KOELS_LORA echo [KoELS] preloading adapters: %KOELS_LORA%

.\llama\llama-server.exe ^
    -m models\qwen-27b-q8.gguf ^
    --mmproj models\qwen-27b-mmproj.gguf ^
    -ngl 999 ^
    -ts 12,28 ^
    -c 32768 ^
    -fa on ^
    --cache-prompt ^
    --slot-save-path prompt_cache ^
    -b 2048 ^
    -ub 1024 ^
    --port 8080 ^
    --host 127.0.0.1 ^
    %KOELS_LORA%

pause
