# patch_workspace_context.ps1
# Adds BOOTUP/UPGRADE_PROTOCOL.md to workspace_context.py's inject list
# so Nova gets her dev collaborator context in every nova_chat session.
# Run from workspace root: .\PATCHES\patch_workspace_context.ps1 [-DryRun]

param([switch]$DryRun)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent

function Log($msg)  { Write-Host $msg -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "  OK: $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  WARN: $msg" -ForegroundColor Yellow }

Log "=== workspace_context.py -- Inject UPGRADE_PROTOCOL.md ==="
Log "Working dir: $root"
if ($DryRun) { Log "[DRY RUN - no changes written]" }

$path = Join-Path $root "general_tools\nova_chat\workspace_context.py"

if (-not (Test-Path $path)) {
    Warn "workspace_context.py not found at: $path"
    exit 1
}

$content = Get-Content $path -Raw -Encoding UTF8

if ($content -match [regex]::Escape('BOOTUP/UPGRADE_PROTOCOL.md')) {
    Ok "UPGRADE_PROTOCOL.md already present in inject list -- no changes needed"
    exit 0
}

# Anchor: the line after NCL_MASTER.md in the inject list
$old = @'
        "BOOTUP/NCL_MASTER.md",
'@

$new = @'
        "BOOTUP/NCL_MASTER.md",
        "BOOTUP/UPGRADE_PROTOCOL.md",
'@

if (-not $content.Contains($old.Trim())) {
    Warn "Anchor 'BOOTUP/NCL_MASTER.md' not found in inject list -- check workspace_context.py manually"
    exit 1
}

if (-not $DryRun) {
    $content = $content.Replace($old, $new)
    Set-Content -Path $path -Value $content -Encoding UTF8
}

Ok "BOOTUP/UPGRADE_PROTOCOL.md added to workspace_context.py inject list"
Log ""
Log "Done. Restart nova_chat to apply."
