# ask_claude.ps1 — type a prewritten prompt into the EXISTING Claude Desktop conversation.
#
# WHY THIS EXISTS (2026-07-19, Cole):
#   The built-in scheduled-task system hands each run to a FRESH Fable 5 MAX session. Nothing
#   carries over, so every run re-reads a huge self-contained prompt and re-derives the whole
#   stack from scratch — an expensive re-familiarisation, every hour, usually to conclude
#   "fine". Overnight that burned a fortune and fixed nothing.
#
#   This does the opposite: it types into the conversation that is ALREADY OPEN. That session
#   already knows Nova, the stack, and what we did last hour — so the prompt can be two lines
#   instead of two pages, and the context is continuous instead of amnesiac.
#
# HOW: put the text in _admin\hourly_prompt.txt (edit it any time, no need to touch this script).
#   The script copies it to the clipboard and pastes it — pasting, not SendKeys-typing, so
#   punctuation, newlines and unicode survive intact.
#
# SAFETY — the important part:
#   It will NOT send keystrokes unless Claude Desktop is genuinely the foreground window.
#   Blindly firing Ctrl+V + Enter into "whatever happens to be focused" could paste a wall of
#   text into a game, a terminal, or a document. So we activate Claude, then VERIFY the
#   foreground window really belongs to Claude's process, and abort quietly if it doesn't.
#
# SCHEDULE IT (hourly):
#   schtasks /create /tn "NovaAskClaude" /sc hourly /f ^
#     /tr "powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\Users\lafou\Project_Nova\workspace\_admin\ask_claude.ps1"

$ErrorActionPreference = 'Stop'

$promptFile = Join-Path $PSScriptRoot 'hourly_prompt.txt'
$logDir     = Join-Path $PSScriptRoot 'autonomy_watch'
$log        = Join-Path $logDir 'injector.log'

function Log($msg) {
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg" | Add-Content -Path $log -Encoding UTF8
}

if (-not (Test-Path $promptFile)) { Log "ABORT: no prompt file at $promptFile"; exit 1 }
$text = Get-Content $promptFile -Raw
if ([string]::IsNullOrWhiteSpace($text)) { Log "ABORT: prompt file is empty — nothing sent"; exit 1 }

# ── find Claude Desktop ───────────────────────────────────────────────────────
$proc = Get-Process |
        Where-Object { $_.MainWindowHandle -ne 0 -and $_.ProcessName -match 'Claude' } |
        Select-Object -First 1
if (-not $proc) { Log "SKIP: Claude Desktop is not running — nothing typed."; exit 0 }

# ── win32: read the actual foreground window so we can verify focus ───────────
if (-not ('Win32Fg' -as [type])) {
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32Fg {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
}
"@
}

Add-Type -AssemblyName System.Windows.Forms
Set-Clipboard -Value $text

$shell = New-Object -ComObject WScript.Shell
$null  = $shell.AppActivate($proc.Id)
Start-Sleep -Milliseconds 900

# VERIFY focus actually landed on Claude before sending a single keystroke.
$fg = [Win32Fg]::GetForegroundWindow()
$fgPid = 0
[void][Win32Fg]::GetWindowThreadProcessId($fg, [ref]$fgPid)
if ($fgPid -ne $proc.Id) {
    Log "ABORT: could not focus Claude (foreground pid $fgPid, Claude pid $($proc.Id)). Nothing typed — refusing to paste into another window."
    exit 1
}

# ── paste + send ──────────────────────────────────────────────────────────────
[System.Windows.Forms.SendKeys]::SendWait('^v')
Start-Sleep -Milliseconds 400
[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')

$preview = ($text -replace '\s+', ' ')
if ($preview.Length -gt 80) { $preview = $preview.Substring(0, 80) + '…' }
Log "SENT to Claude (pid $($proc.Id)): $preview"
exit 0
