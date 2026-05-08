# patch_eyes_server.ps1
# Adds Nova Eyes live screenshot streaming to server.py:
#   - _eyes_running global flag
#   - POST /api/eyes/start and /api/eyes/stop endpoints
#   - _bg_eyes_stream() background task (5fps JPEG over WebSocket)
# Run from workspace root: .\PATCHES\patch_eyes_server.ps1 [-DryRun]

param([switch]$DryRun)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent

function Log($msg)  { Write-Host $msg -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "  OK: $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  WARN: $msg" -ForegroundColor Yellow }

Log "=== Nova Eyes -- Server Patch ==="
Log "Working dir: $root"
if ($DryRun) { Log "[DRY RUN - no changes written]" }

$srvPath = Join-Path $root "general_tools\nova_chat\server.py"
if (-not (Test-Path $srvPath)) {
    Warn "server.py not found at: $srvPath"
    exit 1
}

$srv = Get-Content $srvPath -Raw -Encoding UTF8

# ── PATCH 1: Add _eyes_running global ──────────────────────────────────────────
if ($srv -match [regex]::Escape('_eyes_running')) {
    Ok "PATCH 1: _eyes_running global already present"
} else {
    $old1 = @'
is_processing: bool = False
_stop_requested = asyncio.Event()  # set by STOP; cleared at start of every new response
'@
    $new1 = @'
is_processing: bool = False
_stop_requested = asyncio.Event()  # set by STOP; cleared at start of every new response

# Eyes streaming flag — toggled by /api/eyes/start and /api/eyes/stop
_eyes_running: bool = False
'@
    if (-not $srv.Contains($old1.Trim())) {
        Warn "PATCH 1: is_processing anchor not found -- check server.py manually"
    } else {
        if (-not $DryRun) { $srv = $srv.Replace($old1, $new1) }
        Ok "PATCH 1: _eyes_running global added"
    }
}

# ── PATCH 2: Add /api/eyes/start and /api/eyes/stop endpoints ─────────────────
if ($srv -match [regex]::Escape('/api/eyes/start')) {
    Ok "PATCH 2: /api/eyes/start endpoint already present"
} else {
    # Anchor: the llama start endpoint (always present)
    $old2 = @'
@app.post("/api/llama/start")
'@
    $new2 = @'
@app.post("/api/eyes/start")
async def eyes_start():
    """Begin streaming Nova's desktop to connected WebSocket clients at ~5fps."""
    global _eyes_running
    _eyes_running = True
    return {"status": "started"}

@app.post("/api/eyes/stop")
async def eyes_stop():
    """Stop the desktop screenshot stream."""
    global _eyes_running
    _eyes_running = False
    return {"status": "stopped"}

@app.get("/api/eyes/status")
async def eyes_status():
    return {"running": _eyes_running}

@app.post("/api/llama/start")
'@
    if (-not $srv.Contains($old2.Trim())) {
        Warn "PATCH 2: /api/llama/start anchor not found -- check server.py manually"
    } else {
        if (-not $DryRun) { $srv = $srv.Replace($old2, $new2) }
        Ok "PATCH 2: /api/eyes/start + /api/eyes/stop + /api/eyes/status endpoints added"
    }
}

# ── PATCH 3: Add _bg_eyes_stream() background task ────────────────────────────
if ($srv -match [regex]::Escape('_bg_eyes_stream')) {
    Ok "PATCH 3: _bg_eyes_stream already present"
} else {
    # Anchor: the existing nova_status background poll
    $old3 = @'
async def _bg_nova_status_poll():
'@
    $eyesTask = @'
async def _bg_eyes_stream():
    """
    Capture Nova's desktop at ~5fps and broadcast JPEG frames to all
    WebSocket clients as {"type": "eyes_frame", "data": <base64>, "mouse": [xf, yf]}.
    Only runs while _eyes_running is True; sleeps otherwise.
    """
    import base64, io
    try:
        import pyautogui
        from PIL import Image
        _EYES_AVAILABLE = True
    except ImportError:
        _EYES_AVAILABLE = False

    while True:
        if not _eyes_running:
            await asyncio.sleep(0.5)
            continue

        if not _EYES_AVAILABLE:
            await broadcast({"type": "eyes_frame", "error": "pyautogui not installed"})
            await asyncio.sleep(5)
            continue

        try:
            # Capture and downscale (1280 wide max -- keeps bandwidth sane)
            screenshot = pyautogui.screenshot()
            sw, sh = screenshot.size
            scale = min(1280 / sw, 720 / sh, 1.0)
            if scale < 1.0:
                nw = int(sw * scale)
                nh = int(sh * scale)
                screenshot = screenshot.resize((nw, nh), Image.LANCZOS)
            else:
                nw, nh = sw, sh

            buf = io.BytesIO()
            screenshot.save(buf, format="JPEG", quality=55, optimize=True)
            data_b64 = base64.b64encode(buf.getvalue()).decode()

            # Mouse position as fractions of ORIGINAL screen size
            mx, my = pyautogui.position()
            mouse_frac = [round(mx / sw, 4), round(my / sh, 4)]

            await broadcast({
                "type":      "eyes_frame",
                "data":      data_b64,
                "mouse":     mouse_frac,
                "timestamp": __import__("time").time(),
            })
        except Exception as _e:
            pass   # never crash the loop

        await asyncio.sleep(0.2)   # 5fps

async def _bg_nova_status_poll():
'@
    if (-not $srv.Contains($old3.Trim())) {
        Warn "PATCH 3: _bg_nova_status_poll anchor not found -- check server.py manually"
    } else {
        if (-not $DryRun) { $srv = $srv.Replace($old3, $eyesTask) }
        Ok "PATCH 3: _bg_eyes_stream() background task added"
    }
}

# ── PATCH 4: Auto-start _bg_eyes_stream() alongside other background tasks ────
if ($srv -match [regex]::Escape('_bg_eyes_stream')) {
    # Check if it's also wired into the startup
    if ($srv -match [regex]::Escape('asyncio.create_task(_bg_eyes_stream())')) {
        Ok "PATCH 4: _bg_eyes_stream startup already wired"
    } else {
        $old4 = @'
    asyncio.create_task(_bg_nova_status_poll())
'@
        $new4 = @'
    asyncio.create_task(_bg_nova_status_poll())
    asyncio.create_task(_bg_eyes_stream())
'@
        if (-not $srv.Contains($old4.Trim())) {
            Warn "PATCH 4: asyncio.create_task(_bg_nova_status_poll()) startup anchor not found -- wire _bg_eyes_stream() manually"
        } else {
            if (-not $DryRun) { $srv = $srv.Replace($old4, $new4) }
            Ok "PATCH 4: _bg_eyes_stream() wired into startup"
        }
    }
}

if (-not $DryRun) {
    Set-Content -Path $srvPath -Value $srv -Encoding UTF8
    Log ""
    Log "Done. Restart nova_chat to apply."
    Log "Then click the Eyes tab in Nova Qt and press Start."
} else {
    Log ""
    Log "Dry run complete -- no files written."
}
