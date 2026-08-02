@echo off
REM @nova-adjacent infra: Witness v2, Step 1 — her witness's own engine, on its own port.
REM A small dedicated model (Qwen3.5-4B, NO persona LoRA — the auditor must not inherit her
REM priors) serving llama.cpp on :8081. Her main server on :8080 is untouched; audits stop
REM queueing behind her own generation. Plan: memory\reports\WITNESS_V2_PLAN_2026-08-02.md
REM
REM VRAM: ~2.6GB weights + ~0.5GB KV/overhead, pinned to CUDA0 (the 4090 — it had the most
REM headroom at last audit). If it doesn't fit, check nvidia-smi and either free CUDA0 or
REM switch --device to CUDA1 below.
REM
REM Thinking is OFF at the server default (the witness rules on evidence, it doesn't muse) —
REM replay.py and nova.py also send enable_thinking:false per-request; belt and suspenders.
title llama.cpp WITNESS - Qwen3.5-4B on :8081 (CUDA0)
cd /d "%~dp0..\.."

set "WMODEL=models\witness\Qwen3.5-4B-UD-Q4_K_XL.gguf"
if not exist "%WMODEL%" set "WMODEL=models\witness\Qwen3.5-4B-Q4_K_M.gguf"
if not exist "%WMODEL%" (
    echo [witness] No model found in models\witness\ - run fetch_witness_model.cmd first.
    pause
    exit /b 1
)

echo [witness] Starting witness engine: %WMODEL%
echo [witness] Port 8081, ctx 16384 over --parallel 2 (8K per slot - the audit prompt is ~2-3K)
echo [witness] Device CUDA0 (4090). Her main server on :8080 is not touched.
echo.

.\llama\llama-server.exe ^
    -m "%WMODEL%" ^
    --device CUDA0 ^
    -ngl 999 ^
    -c 16384 ^
    --parallel 2 ^
    -ctk q8_0 ^
    -ctv q8_0 ^
    -fa on ^
    --jinja ^
    --chat-template-kwargs "{\"enable_thinking\":false}" ^
    --cache-prompt ^
    -b 2048 ^
    -ub 512 ^
    --port 8081 ^
    --host 127.0.0.1

pause
