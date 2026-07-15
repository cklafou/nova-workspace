@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM fetch_checkpoints.cmd — download Nova's three paints (~21GB).  2026-07-14
REM
REM Uses the ComfyUI venv's python, which already has huggingface_hub installed
REM (it came in with ComfyUI's own requirements — no new deps needed).
REM
REM Logs to _admin\Temp\checkpoints.log. Watch it with:
REM     Get-Content ...\_admin\Temp\checkpoints.log -Wait -Tail 20
REM
REM The window will look idle for long stretches. That is a 7GB file moving, not a
REM hang. hf_hub_download prints a progress bar to stderr; it's captured below.
REM ─────────────────────────────────────────────────────────────────────────────

set PY=C:\Users\lafou\ComfyUI\venv\Scripts\python.exe
set WS=C:\Users\lafou\Project_Nova\workspace
set LOG=%WS%\_admin\Temp\checkpoints.log

if not exist "%WS%\_admin\Temp" mkdir "%WS%\_admin\Temp"

if not exist "%PY%" (
    echo FATAL: ComfyUI venv python not found at %PY% > "%LOG%"
    echo        Run setup_comfyui.cmd first. >> "%LOG%"
    exit /b 1
)

echo === checkpoint download started %DATE% %TIME% === > "%LOG%"
"%PY%" -u "%WS%\_admin\fetch_checkpoints.py" >> "%LOG%" 2>&1
echo === exit code %ERRORLEVEL% === >> "%LOG%"
