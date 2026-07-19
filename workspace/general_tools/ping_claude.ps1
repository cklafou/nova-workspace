# ping_claude.ps1 - Nova reaching Claude Desktop herself, in her own words.
#
# WHY (2026-07-19, Cole): "I want Autonomous Nova to be able to ping for Claude to speak with and
# assist her when she needs him." She works alone for hours. When she hits something she cannot
# solve, the only options used to be sit on it until morning, or guess. Now she can ask.
#
# ############################################################################################
# THIS FILE IS DELIBERATELY PURE ASCII. DO NOT ADD AN EM-DASH, A CURLY QUOTE, OR A BOX-DRAWING
# CHARACTER TO IT - NOT EVEN IN A COMMENT.
#
# 2026-07-19: this script failed 100% of the time, silently, from the moment it was written, and
# the cause was one em-dash on line 78. Windows PowerShell 5.1 reads a .ps1 with no UTF-8 BOM
# using the ANSI codepage (cp1252). An em-dash is UTF-8 E2 80 94, which cp1252 renders as three
# characters ending in 0x94 - a RIGHT CURLY DOUBLE QUOTE. PowerShell accepts curly quotes as
# real string delimiters, so the string closed in the middle of the sentence and the file failed
# to PARSE. A parse error kills the whole script before line 1 runs: no logging, no queueing, no
# error handler. Nova's message vanished and she was told nothing useful.
#
# A BOM would also fix it, but BOMs get stripped by editors, git filters and copy-paste. ASCII
# cannot be stripped. Her MESSAGE may contain any Unicode she likes - emoji included - because it
# arrives via -MessageFile and is never parsed as code. See tool_router.ping_claude().
# ############################################################################################
#
# WHAT CHANGED vs _admin/ask_claude.ps1 (which this replaces):
#   1. HER WORDS, not a fixed file. The message is passed in, so Claude gets her actual question
#      with context, and can start being useful in the first reply instead of spending a round
#      asking what she meant.
#   2. IT RETRIES. The old one called AppActivate once and gave up. Windows routinely REFUSES a
#      foreground change (SetForegroundWindow is restricted when another app holds focus, when a
#      game is fullscreen, when the user is typing). The old script then aborted - correctly, it
#      must never paste into the wrong window - but the message was simply LOST. Now: several
#      attempts with backoff, restoring the window if minimised.
#   3. IT NEVER SILENTLY DROPS. If it truly cannot deliver, the message is appended to
#      logs/ping_queue.jsonl instead of vanishing, and the caller is told plainly it was queued,
#      not sent. A ping that disappears is worse than one that fails loudly - she would believe
#      she had asked for help and then wait for an answer that was never coming.
#
# SAFETY (unchanged and non-negotiable): it verifies the foreground window really belongs to
# Claude's process before sending a single keystroke. Pasting a wall of text into a game, a
# terminal or a document is not an acceptable failure mode.
#
# NOTE: the P/Invoke below is built from a string ARRAY on purpose. A here-string breaks when the
# file has Unix line endings ("string is missing the terminator"). Do not "tidy" it back.
#
# USAGE:
#   powershell -NoProfile -File general_tools\ping_claude.ps1 -MessageFile path\to\message.txt
#   powershell -NoProfile -File general_tools\ping_claude.ps1 -Message "Nova here - stuck on X"
# -MessageFile is strongly preferred: it is the only form that is safe for arbitrary text.
# Exit codes: 0 = delivered, 2 = queued (not delivered), 1 = error.

param(
    [string]$Message     = '',
    [Alias('File')]
    [string]$MessageFile = '',
    [int]$Attempts       = 4
)

$ErrorActionPreference = 'Stop'

$wsRoot = Split-Path -Parent $PSScriptRoot          # ...\workspace
$logDir = Join-Path $wsRoot 'logs'
$log    = Join-Path $logDir 'ping_claude.log'
$queue  = Join-Path $logDir 'ping_queue.jsonl'

function Log($msg) {
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $log -Value ($stamp + '  ' + $msg) -Encoding UTF8
}

function QueueIt($text, $why) {
    # Never lose her words. A dropped ping means she waits for help that is not coming.
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    $rec = [ordered]@{
        ts      = (Get-Date -Format 'o')
        reason  = $why
        message = $text
    } | ConvertTo-Json -Compress
    Add-Content -Path $queue -Value $rec -Encoding UTF8
    $flat = ($text -replace '\s+', ' ')
    if ($flat.Length -gt 80) { $flat = $flat.Substring(0, 80) }
    Log ('QUEUED (' + $why + '): ' + $flat)
}

try {
    # -- the message ----------------------------------------------------------
    if ($MessageFile -and (Test-Path $MessageFile)) {
        $text = Get-Content $MessageFile -Raw -Encoding UTF8   # UTF8 required or em-dashes mangle
    } else {
        $text = $Message
    }
    if ([string]::IsNullOrWhiteSpace($text)) {
        Log 'ABORT: empty message - nothing sent'
        Write-Output 'ERROR: empty message'
        exit 1
    }
    # Make it unmistakably HER, so Claude knows this is Nova reaching out unprompted.
    # ASCII hyphen, not an em-dash. See the banner at the top of this file.
    if ($text -notmatch '^\s*\[Nova is pinging you') {
        $banner = '[Nova is pinging you - she reached out on her own, unprompted]'
        $text = $banner + "`n" + $text
    }

    Add-Type -AssemblyName System.Windows.Forms
    if (-not ('Win32Fg' -as [type])) {
        $src = @(
            'using System;',
            'using System.Runtime.InteropServices;',
            'public class Win32Fg {',
            '  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();',
            '  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);',
            '  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);',
            '  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);',
            '  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);',
            '}'
        ) -join [Environment]::NewLine
        Add-Type -TypeDefinition $src
    }

    # -- find Claude Desktop --------------------------------------------------
    # Prefer a process with a real window AND a title - Electron apps spawn helper processes and
    # the old "-First 1" could land on one of those.
    $proc = Get-Process |
            Where-Object { $_.MainWindowHandle -ne 0 -and $_.ProcessName -match 'Claude' -and $_.MainWindowTitle } |
            Sort-Object { $_.MainWindowTitle.Length } -Descending |
            Select-Object -First 1
    if (-not $proc) {
        QueueIt $text 'claude-desktop-not-running'
        Write-Output 'QUEUED: Claude Desktop is not running. Your message was saved to logs/ping_queue.jsonl, NOT delivered.'
        exit 2
    }

    # -- try, properly, more than once ----------------------------------------
    $delivered = $false
    for ($i = 1; $i -le $Attempts; $i++) {
        $h = $proc.MainWindowHandle
        if ([Win32Fg]::IsIconic($h)) { [void][Win32Fg]::ShowWindow($h, 9) }   # 9 = SW_RESTORE
        $shell = New-Object -ComObject WScript.Shell
        $null  = $shell.AppActivate($proc.Id)
        [void][Win32Fg]::SetForegroundWindow($h)
        Start-Sleep -Milliseconds (600 * $i)      # backoff: focus can lag, especially when busy

        $fg = [Win32Fg]::GetForegroundWindow()
        $fgPid = 0
        [void][Win32Fg]::GetWindowThreadProcessId($fg, [ref]$fgPid)
        if ($fgPid -eq $proc.Id) {
            Set-Clipboard -Value $text            # set AFTER focus: some apps clear on activate
            Start-Sleep -Milliseconds 250
            [System.Windows.Forms.SendKeys]::SendWait('^v')
            Start-Sleep -Milliseconds 500
            [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
            $delivered = $true
            Log ('SENT on attempt ' + $i + ' (pid ' + $proc.Id + ')')
            break
        }
        Log ('attempt ' + $i + ' of ' + $Attempts + ': could not focus Claude (fg pid ' + $fgPid + ', want ' + $proc.Id + ')')
    }

    if (-not $delivered) {
        QueueIt $text 'could-not-focus-claude'
        Write-Output ('QUEUED: could not bring Claude Desktop to the foreground after ' + $Attempts +
                      ' attempts (Windows blocks focus changes while another app is active). Your message was SAVED, not delivered.')
        exit 2
    }

    $preview = ($text -replace '\s+', ' ')
    if ($preview.Length -gt 90) { $preview = $preview.Substring(0, 90) + '...' }
    Write-Output ('DELIVERED to Claude Desktop: ' + $preview)
    exit 0
}
catch {
    Log ('ERROR: ' + $_.Exception.Message)
    try { QueueIt $text 'script-error' } catch {}
    Write-Output ('ERROR: ' + $_.Exception.Message + ' (message queued if possible)')
    exit 1
}
