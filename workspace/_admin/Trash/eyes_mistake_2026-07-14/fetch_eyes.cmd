@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM fetch_eyes.cmd — download Nova's sight (~6GB).  2026-07-14
REM
REM Qwen2.5-VL-7B: a text half (Q4_K_M, ~4.7GB) and the mmproj vision encoder
REM (f16, 1.35GB — do NOT quantize it, it degrades what she can actually see).
REM
REM Lands in models\eyes\ — a NEW folder. models\qwen3.6\ is sealed and untouched.
REM
REM Uses the ComfyUI venv's python purely because it already has huggingface_hub.
REM Nothing about her sight depends on ComfyUI.
REM ─────────────────────────────────────────────────────────────────────────────

set PY=C:\Users\lafou\ComfyUI\venv\Scripts\python.exe
set WS=C:\Users\lafou\Project_Nova\workspace
set LOG=%WS%\_admin\Temp\eyes.log

if not exist "%WS%\_admin\Temp" mkdir "%WS%\_admin\Temp"

if not exist "%PY%" (
    echo FATAL: python not found at %PY% - run setup_comfyui.cmd first > "%LOG%"
    exit /b 1
)

echo === eyes download started %DATE% %TIME% === > "%LOG%"
"%PY%" -u "%WS%\_admin\fetch_eyes.py" >> "%LOG%" 2>&1
echo === exit code %ERRORLEVEL% === >> "%LOG%"
