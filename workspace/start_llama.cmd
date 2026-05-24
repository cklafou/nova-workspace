@echo off
REM @nova: Starts llama.cpp serving Qwen 3.5 27B Q8 on :8080 with the dual-GPU tensor split (4090+3090).
title llama.cpp Qwen 3.5 27B — Dual GPU (4090 + 3090 eGPU)
cd /d "%~dp0"

echo [llama.cpp] Starting Qwen 3.5 27B Dense Q8 with dual-GPU split...
echo.
echo GPU layout assumed: GPU 0 = RTX 4090 Laptop (16GB), GPU 1 = RTX 3090 eGPU (24GB)
echo Run 'nvidia-smi -L' to verify. If reversed, swap -ts to 24,16 below.
echo.
echo Model : models\qwen-27b-q8.gguf
echo Vision: models\qwen-27b-mmproj.gguf
echo Port  : 8080
echo Context: 32768 tokens
echo.
echo NOTE: Using model's own embedded chat template (qwen35 Jinja).
echo       Do NOT add --chat-template qwen3 -- that overrides the GGUF template
echo       with the wrong one and breaks system prompt application.
echo.

if not exist "prompt_cache" mkdir "prompt_cache"

.\llama\llama-server.exe ^
    -m models\qwen-27b-q8.gguf ^
    --mmproj models\qwen-27b-mmproj.gguf ^
    -ngl 999 ^
    -ts 16,24 ^
    -c 32768 ^
    -fa on ^
    --cache-prompt ^
    --slot-save-path prompt_cache ^
    -b 2048 ^
    -ub 1024 ^
    --port 8080 ^
    --host 127.0.0.1

pause
