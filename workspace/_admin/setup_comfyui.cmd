@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM setup_comfyui.cmd — stand up Nova's painter.  2026-07-14
REM
REM A .cmd, not a .ps1, deliberately: PowerShell's ExecutionPolicy governs script
REM FILES, and disabling it with -ExecutionPolicy Bypass is turning off a security
REM control Cole never asked to turn off. A batch file needs no such thing.
REM
REM Installs to C:\Users\lafou\ComfyUI — OUTSIDE the Project_Nova git repo, which is
REM watched and auto-committed. A multi-GB model tree inside it would be a disaster.
REM
REM Logs everything to _admin\Temp\comfy.log so progress can be watched from outside
REM (run_command times out at 30s; torch alone is a ~2.5GB download).
REM ─────────────────────────────────────────────────────────────────────────────

set ROOT=C:\Users\lafou\ComfyUI
set WS=C:\Users\lafou\Project_Nova\workspace
set LOG=%WS%\_admin\Temp\comfy.log

if not exist "%WS%\_admin\Temp" mkdir "%WS%\_admin\Temp"
echo === ComfyUI setup started %DATE% %TIME% === > "%LOG%"

echo [1/5] cloning ComfyUI (outside the git repo)... >> "%LOG%"
if exist "%ROOT%\main.py" (
    echo       already cloned >> "%LOG%"
) else (
    git clone --depth 1 https://github.com/comfyanonymous/ComfyUI "%ROOT%" >> "%LOG%" 2>&1
)
if not exist "%ROOT%\main.py" (
    echo FATAL: clone failed - no main.py >> "%LOG%"
    exit /b 1
)
echo       clone OK >> "%LOG%"

echo [2/5] creating venv... >> "%LOG%"
if not exist "%ROOT%\venv\Scripts\python.exe" (
    python -m venv "%ROOT%\venv" >> "%LOG%" 2>&1
)
if not exist "%ROOT%\venv\Scripts\python.exe" (
    echo FATAL: venv python not found >> "%LOG%"
    exit /b 1
)
echo       venv OK >> "%LOG%"
set PY=%ROOT%\venv\Scripts\python.exe

echo [3/5] installing torch CUDA 12.4 (~2.5GB, several minutes)... >> "%LOG%"
"%PY%" -m pip install --upgrade pip >> "%LOG%" 2>&1
"%PY%" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 >> "%LOG%" 2>&1

REM FAIL LOUD. A painter silently running on CPU would take minutes per image and
REM we would spend an hour blaming the model. Assert the thing we actually need.
"%PY%" -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)"
if errorlevel 1 (
    echo FATAL: torch has NO CUDA - painter would run on CPU. Stopping. >> "%LOG%"
    exit /b 1
)
"%PY%" -c "import torch;print('      torch',torch.__version__,'cuda',torch.cuda.is_available(),'gpus',torch.cuda.device_count())" >> "%LOG%" 2>&1

echo [4/5] installing ComfyUI requirements... >> "%LOG%"
"%PY%" -m pip install -r "%ROOT%\requirements.txt" >> "%LOG%" 2>&1
echo       requirements OK >> "%LOG%"

echo [5/5] writing launcher pinned to the 3090... >> "%LOG%"
REM Which index IS the 3090? ASK the machine. Never assume — the checklist says
REM "usually 1, but verify", and assuming is how today went wrong repeatedly.
for /f "tokens=1 delims=," %%A in ('nvidia-smi --query-gpu^=index^,name --format^=csv^,noheader ^| findstr /i "3090"') do set GPU3090=%%A
if "%GPU3090%"=="" (
    echo       WARNING: no 3090 found in nvidia-smi - defaulting to GPU 0 >> "%LOG%"
    set GPU3090=0
)
echo       pinning painter to GPU %GPU3090% (the 3090) so it does not fight the 27B >> "%LOG%"

if not exist "%ROOT%\models\checkpoints" mkdir "%ROOT%\models\checkpoints"

> "%ROOT%\run_nova_painter.bat" echo @echo off
>> "%ROOT%\run_nova_painter.bat" echo REM Nova's painter. Pinned to the 3090; the 27B lives on the 4090.
>> "%ROOT%\run_nova_painter.bat" echo REM Local-only on 127.0.0.1:8188 - do NOT add --listen 0.0.0.0
>> "%ROOT%\run_nova_painter.bat" echo set CUDA_VISIBLE_DEVICES=%GPU3090%
>> "%ROOT%\run_nova_painter.bat" echo cd /d "%ROOT%"
>> "%ROOT%\run_nova_painter.bat" echo "%PY%" main.py --port 8188
echo       wrote %ROOT%\run_nova_painter.bat >> "%LOG%"

echo. >> "%LOG%"
echo === STAGE 1 COMPLETE === >> "%LOG%"
echo NEXT: a .safetensors checkpoint must go in %ROOT%\models\checkpoints\ >> "%LOG%"
echo       then run run_nova_painter.bat and Nova can draw. >> "%LOG%"
