# apply_bootup_reorganization.ps1
# Run from workspace root.
# Completes the BOOTUP/ reorganization:
#   1. Patches workspace_context.py to load identity files from BOOTUP/
#   2. Removes the now-redundant root copies of the 6 bootup .md files

param([switch]$DryRun)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Log($msg) { Write-Host $msg -ForegroundColor Cyan }
function Ok($msg)  { Write-Host "  OK: $msg" -ForegroundColor Green }
function Warn($msg){ Write-Host "  WARN: $msg" -ForegroundColor Yellow }

Log "=== BOOTUP Reorganization - Final Steps ==="
Log "Working dir: $root"
if ($DryRun) { Log "[DRY RUN - no changes will be written]" }

# ── Step 1: Patch workspace_context.py ──────────────────────────────────────
$ctxPath = Join-Path $root "general_tools\nova_chat\workspace_context.py"
if (-not (Test-Path $ctxPath)) {
    Warn "workspace_context.py not found at: $ctxPath"
} else {
    $content = Get-Content $ctxPath -Raw -Encoding UTF8
    $old = '        _IDENTITY_FILES = ["AGENTS.md", "NOVA.md", "TOOLS.md"]
        for _fname in _IDENTITY_FILES:
            _fpath = WORKSPACE_DIR / _fname'
    $new = '        # Identity files now live in BOOTUP/ subfolder
        _IDENTITY_FILES = ["AGENTS.md", "NOVA.md", "TOOLS.md"]
        for _fname in _IDENTITY_FILES:
            _fpath = WORKSPACE_DIR / "BOOTUP" / _fname'
    if ($content -match [regex]::Escape('_fpath = WORKSPACE_DIR / "BOOTUP"')) {
        Ok "workspace_context.py already patched (BOOTUP path present)"
    } elseif ($content.Contains($old)) {
        if (-not $DryRun) {
            $content = $content.Replace($old, $new)
            Set-Content -Path $ctxPath -Value $content -Encoding UTF8
        }
        Ok "workspace_context.py patched -> BOOTUP/ path"
    } else {
        Warn "workspace_context.py: anchor not found - manual patch may be needed"
        Warn "  Look for _IDENTITY_FILES and change _fpath to use WORKSPACE_DIR / 'BOOTUP' / _fname"
    }
}

# ── Step 2: Remove root copies of bootup files ───────────────────────────────
$bootupFiles = @("NOVA.md", "AGENTS.md", "TOOLS.md", "NCL_MASTER.md", "BOOTSTRAP.md", "HEARTBEAT.md")
Log ""
Log "Removing root copies (now live in BOOTUP/)..."
foreach ($f in $bootupFiles) {
    $p = Join-Path $root $f
    $bootupCopy = Join-Path $root "BOOTUP\$f"
    if (-not (Test-Path $p)) {
        Ok "$f already gone from root"
        continue
    }
    if (-not (Test-Path $bootupCopy)) {
        Warn "${f}: BOOTUP copy missing! NOT deleting root copy."
        continue
    }
    if (-not $DryRun) {
        Remove-Item $p -Force
    }
    Ok "Removed root: $f"
}

Log ""
Log "Done. Run 'python general_tools\NovaLauncher.py' to verify Nova boots correctly."
