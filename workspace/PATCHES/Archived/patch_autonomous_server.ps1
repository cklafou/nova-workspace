# patch_autonomous_server.ps1
# Adds autonomous_toggle handling to nova_chat/server.py.
# Run from workspace root.

$ErrorActionPreference = "Stop"
$target = "general_tools\nova_chat\server.py"

if (-not (Test-Path $target)) {
    Write-Host "ERROR: $target not found. Run from workspace root." -ForegroundColor Red
    exit 1
}

$content = Get-Content $target -Raw -Encoding UTF8

# ── Guard: already patched? ───────────────────────────────────────────────────
if ($content -match "autonomous_toggle") {
    Write-Host "Already patched (autonomous_toggle found). Nothing to do." -ForegroundColor Green
    exit 0
}

# ── 1. Add global state variable after `is_processing` declaration ───────────
$old1 = 'is_processing: bool = False'
$new1 = 'is_processing: bool = False
autonomous_mode: bool = False      # toggled by the Qt UI autonomous button'

if (-not $content.Contains($old1)) {
    Write-Host "ERROR: could not find is_processing declaration." -ForegroundColor Red
    exit 1
}
$content = $content.Replace($old1, $new1)
Write-Host "  OK: autonomous_mode global added" -ForegroundColor Green

# ── 2. Add autonomous_toggle handler in the websocket dispatch block ──────────
# Insert before the existing "if data.get("type") == "stop":" block
$old2 = '            if data.get("type") == "stop":'
$new2 = '            if data.get("type") == "autonomous_toggle":
                global autonomous_mode
                autonomous_mode = bool(data.get("enabled", False))
                label = "ON ⚡" if autonomous_mode else "OFF"
                content_msg = f"⚡ Autonomous mode: {label}"
                sys_msg = session_mgr.active.add("System", content_msg)
                await broadcast({
                    "type": "user_message",
                    "author": "System",
                    "content": content_msg,
                    "id": sys_msg["id"],
                    "timestamp": sys_msg["timestamp"],
                })
                continue

            if data.get("type") == "stop":'

if (-not $content.Contains($old2)) {
    Write-Host "ERROR: could not find stop handler anchor." -ForegroundColor Red
    exit 1
}
$content = $content.Replace($old2, $new2)
Write-Host "  OK: autonomous_toggle WS handler added" -ForegroundColor Green

# ── 3. Inject autonomous mode hint into Nova's context block ──────────────────
# Find where Nova's ws_context is built and prepend the mode line
$old3 = '            ws_context = workspace.build_nova_context_block()'
$new3 = '            ws_context = workspace.build_nova_context_block()
                if autonomous_mode:
                    ws_context = "[AUTONOMOUS MODE: ON — Nova may chain tool calls and multi-step actions without pausing for confirmation.]\n\n" + ws_context
                else:
                    ws_context = "[AUTONOMOUS MODE: OFF — Nova should complete one action, report the result, and wait for Cole before proceeding.]\n\n" + ws_context'

if (-not $content.Contains($old3)) {
    Write-Host "WARN: could not find build_nova_context_block anchor — mode hint not injected into Nova context." -ForegroundColor Yellow
    Write-Host "      The chat system message will still work; Nova will see the toggle in her transcript." -ForegroundColor Yellow
} else {
    $content = $content.Replace($old3, $new3)
    Write-Host "  OK: autonomous mode prepended to Nova context block" -ForegroundColor Green
}

# ── Write ─────────────────────────────────────────────────────────────────────
$backup = "$target.bak"
Copy-Item $target $backup -Force
Write-Host "  Backup: $backup" -ForegroundColor Cyan
Set-Content -Path $target -Value $content -Encoding UTF8
Write-Host ""
Write-Host "Done. Restart nova_chat server to apply." -ForegroundColor Green
