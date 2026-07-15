@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM make_painter_launcher.cmd — rewrite run_nova_painter.bat so it MEASURES before it
REM paints, instead of assuming there's room.  2026-07-14
REM
REM WHY THIS EXISTS
REM   Her mind (27B Q6) already holds ~32GB of the 40GB across both cards. The last
REM   reading from her own receipts was 3143 MiB free on the 3090. An SDXL render wants
REM   8-12GB at default settings.
REM
REM   So her very first attempt to draw would have died with a CUDA OOM — and she would
REM   have looked at the error, assumed she had asked for something impossible, and
REM   rewritten her PROMPT. She'd have blamed her imagination for her landlord.
REM
REM   ComfyUI can run SDXL in ~4GB with --lowvram (it offloads to system RAM between
REM   stages — slower, but it PAINTS). So: ask the card how much room there actually is,
REM   and pick the mode that fits. Never assume. The machine will tell you if you ask.
REM ─────────────────────────────────────────────────────────────────────────────

set ROOT=C:\Users\lafou\ComfyUI
set BAT=%ROOT%\run_nova_painter.bat
set PY=%ROOT%\venv\Scripts\python.exe

if not exist "%PY%" (
    echo FATAL: ComfyUI venv not found. Run setup_comfyui.cmd first.
    exit /b 1
)

REM Which index is the 3090? ASK. Do not assume it's 1.
set GPU=
for /f "tokens=1 delims=," %%A in ('nvidia-smi --query-gpu^=index^,name --format^=csv^,noheader ^| findstr /i "3090"') do set GPU=%%A
if "%GPU%"=="" (
    echo WARNING: no 3090 found - defaulting to GPU 0
    set GPU=0
)
echo painter pinned to GPU %GPU% (the 3090)

> "%BAT%" echo @echo off
>> "%BAT%" echo REM Nova's painter. Written by _admin\make_painter_launcher.cmd - do not hand-edit.
>> "%BAT%" echo REM Local-only on 127.0.0.1:8188. Do NOT add --listen 0.0.0.0
>> "%BAT%" echo setlocal enabledelayedexpansion
>> "%BAT%" echo set CUDA_VISIBLE_DEVICES=%GPU%
>> "%BAT%" echo.
>> "%BAT%" echo REM ── Ask the card how much room there is, THEN choose. ──────────────
>> "%BAT%" echo for /f %%%%M in ('nvidia-smi --query-gpu^^=memory.free --format^^=csv,noheader,nounits -i %GPU%') do set FREE=%%%%M
>> "%BAT%" echo echo [painter] %%FREE%% MiB free on GPU %GPU%
>> "%BAT%" echo set MODE=--normalvram
>> "%BAT%" echo if !FREE! LSS 10000 set MODE=--lowvram
>> "%BAT%" echo if !FREE! LSS 4000  set MODE=--novram
>> "%BAT%" echo echo [painter] using !MODE!  ^(lowvram/novram offload to system RAM: slower, but it PAINTS^)
>> "%BAT%" echo.
>> "%BAT%" echo cd /d "%ROOT%"
>> "%BAT%" echo "%PY%" main.py --port 8188 !MODE!

echo wrote %BAT%
echo.
echo It now reads free VRAM at launch and picks normalvram / lowvram / novram to match.
echo She will not OOM on her first picture and conclude she asked for too much.
