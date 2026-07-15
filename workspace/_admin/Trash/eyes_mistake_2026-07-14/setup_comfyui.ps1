# setup_comfyui.ps1 — stand up Nova's painter. 2026-07-14
#
# Installs ComfyUI OUTSIDE the Project_Nova git repo (C:\Users\lafou\ComfyUI).
# The repo is watched + auto-committed; a multi-GB model tree inside it would be a disaster.
#
# Pins ComfyUI to the 3090 (CUDA_VISIBLE_DEVICES) so the painter and the mind don't fight over
# the same card — the 27B already occupies ~32GB of the 40GB across both GPUs.
#
# Everything logs to _admin\Temp\comfyui_setup.log so progress can be watched from outside.
# Run detached; run_command has a 30s timeout and torch alone is a ~2.5GB download.

$ErrorActionPreference = "Continue"
$Root   = "C:\Users\lafou\ComfyUI"
$LogDir = "C:\Users\lafou\Project_Nova\workspace\_admin\Temp"
$Log    = "$LogDir\comfyui_setup.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Say($m) {
    $line = "$(Get-Date -Format 'HH:mm:ss')  $m"
    Add-Content -Path $Log -Value $line
}

Say "=== ComfyUI setup starting ==="
Say "target: $Root  (deliberately OUTSIDE the git repo)"

# ── 1. clone ────────────────────────────────────────────────────────────────
if (Test-Path "$Root\.git") {
    Say "[1/5] ComfyUI already cloned — pulling latest"
    git -C $Root pull 2>&1 | ForEach-Object { Say "      $_" }
} else {
    Say "[1/5] cloning ComfyUI..."
    git clone --depth 1 https://github.com/comfyanonymous/ComfyUI $Root 2>&1 | ForEach-Object { Say "      $_" }
}
if (-not (Test-Path "$Root\main.py")) { Say "FATAL: clone failed — no main.py"; exit 1 }
Say "      clone OK"

# ── 2. venv ─────────────────────────────────────────────────────────────────
if (-not (Test-Path "$Root\venv\Scripts\python.exe")) {
    Say "[2/5] creating venv..."
    python -m venv "$Root\venv" 2>&1 | ForEach-Object { Say "      $_" }
} else {
    Say "[2/5] venv already exists"
}
$Py = "$Root\venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { Say "FATAL: venv python not found"; exit 1 }

# ── 3. torch (CUDA) — the big one, ~2.5GB ───────────────────────────────────
Say "[3/5] installing torch (CUDA 12.4) — this is the long one, several minutes..."
& $Py -m pip install --upgrade pip 2>&1 | Select-Object -Last 2 | ForEach-Object { Say "      $_" }
& $Py -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 2>&1 |
    Select-Object -Last 3 | ForEach-Object { Say "      $_" }

$cuda = & $Py -c "import torch;print(torch.cuda.is_available(), torch.cuda.device_count())" 2>&1
Say "      torch.cuda.is_available / device_count -> $cuda"
if ("$cuda" -notmatch "True") { Say "FATAL: torch has no CUDA — painter would run on CPU"; exit 1 }

# ── 4. ComfyUI requirements ─────────────────────────────────────────────────
Say "[4/5] installing ComfyUI requirements..."
& $Py -m pip install -r "$Root\requirements.txt" 2>&1 | Select-Object -Last 3 | ForEach-Object { Say "      $_" }

# ── 5. launcher, pinned to the 3090 ─────────────────────────────────────────
# Which index IS the 3090? Ask the machine; never assume.
$gpus = & nvidia-smi --query-gpu=index,name --format=csv,noheader
Say "[5/5] GPUs seen:"
$gpus | ForEach-Object { Say "      $_" }
$idx3090 = ($gpus | Where-Object { $_ -match "3090" } | Select-Object -First 1) -split "," | Select-Object -First 1
if (-not $idx3090) { $idx3090 = 0; Say "      WARNING: no 3090 found; defaulting to GPU 0" }
$idx3090 = "$idx3090".Trim()
Say "      pinning ComfyUI to GPU index $idx3090 (the 3090) so it doesn't fight the 27B"

$bat = @"
@echo off
REM Nova's painter. Pinned to the 3090 so it does not contend with the 27B on the 4090.
REM Local-only on 127.0.0.1:8188 — do NOT add --listen 0.0.0.0.
set CUDA_VISIBLE_DEVICES=$idx3090
cd /d "$Root"
"$Py" main.py --port 8188
"@
Set-Content -Path "$Root\run_nova_painter.bat" -Value $bat -Encoding ASCII
Say "      wrote $Root\run_nova_painter.bat"

New-Item -ItemType Directory -Force -Path "$Root\models\checkpoints" | Out-Null
Say ""
Say "=== SETUP COMPLETE ==="
Say "NEXT: a checkpoint (.safetensors) must go in $Root\models\checkpoints\"
Say "      then launch run_nova_painter.bat and Nova can draw."
