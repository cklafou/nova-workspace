# ask_claude.ps1 — type a prewritten prompt into the EXISTING Claude Desktop conversation.
#
# WHY THIS EXISTS (2026-07-19, Cole):
#   The built-in scheduled-task system hands each run to a FRESH session. Nothing carries over,
#   so every run re-reads a huge self-contained prompt and re-derives the whole stack from
#   scratch — an expensive re-familiarisation, every hour, usually to conclude "fine".
#   Overnight that burned a fortune and fixed nothing.
#
#   This does the opposite: it types into the conversation that is ALREADY OPEN. That session
#   already knows Nova, the stack, and what happened last hour — so the prompt can be a few
#   lines instead of pages, and the context is continuous instead of amnesiac.
#
# HOW: put the text in _admin\hourly_prompt.txt (edit any time; no need to touch this script).
#   It goes via the CLIPBOARD and Ctrl+V, not SendKeys-typing, so punctuation, newlines and
#   unicode survive exactly.
#
# SAFETY — the important part:
#   It will NOT send keystrokes unless Claude Desktop is genuinely the foreground window.
#   Firing Ctrl+V + Enter into "whatever happens to be focused" could dump a wall of text into
#   a game, a terminal, or a document. So: activate Claude, VERIFY the foreground window really
#   belongs to Claude's process, and abort quietly if it doesn't.
#
# NOTE (2026-07-19): the P/Invoke below is built from a string ARRAY, deliberately. The original
#   used an @"..."@ here-string and PowerShell refused to parse the whole file ("string is
#   missing the terminator") because the file has Unix line endings. Here-strings are
#   line-ending sensitive; a joined array is not. Do not "tidy" this back into a here-string.
#
# SCHEDULE IT (hourly):
#   schtasks /create /tn "NovaAskClaude" /sc hourly /f /tr "C:\Users\lafou\Project_Nova\workspace\_admin\AskClaude.cmd"

$ErrorActionPreference = 'Stop'

$promptFile = Join-Path $PSScriptRoot 'hourly_prompt.txt'
$logDir     = Join-Path $PSScriptRoot 'autonomy_watch'
$log        = Join-Path $logDir 'injector.log'

function Log($msg) {
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $log -Value ($stamp + '  ' + $msg) -Encoding UTF8
}

try {
    if (-not (Test-Path $promptFile)) { Log ('ABORT: no prompt file at ' + $promptFile); exit 1 }
    # -Encoding UTF8 is REQUIRED: without it Windows PowerShell reads the file as ANSI and
    # every non-ASCII character (em-dashes, quotes) arrives mangled as "â€"" in the prompt.
    $text = Get-Content $promptFile -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($text)) { Log 'ABORT: prompt file is empty - nothing sent'; exit 1 }

    # ── find Claude Desktop ───────────────────────────────────────────────────
    $proc = Get-Process |
            Where-Object { $_.MainWindowHandle -ne 0 -and $_.ProcessName -match 'Claude' } |
            Select-Object -First 1
    if (-not $proc) { Log 'SKIP: Claude Desktop is not running - nothing typed.'; exit 0 }

    # ── win32 foreground check (array-joined source; see NOTE above) ──────────
    if (-not ('Win32Fg' -as [type])) {
        $src = @(
            'using System;',
            'using System.Runtime.InteropServices;',
            'public class Win32Fg {',
            '  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();',
            '  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);',
            '}'
        ) -join [Environment]::NewLine
        Add-Type -TypeDefinition $src
    }

    Add-Type -AssemblyName System.Windows.Forms
    Set-Clipboard -Value $text

    $shell = New-Object -ComObject WScript.Shell
    $null  = $shell.AppActivate($proc.Id)
    Start-Sleep -Milliseconds 1200

    # VERIFY focus actually landed on Claude before sending a single keystroke.
    $fg = [Win32Fg]::GetForegroundWindow()
    $fgPid = 0
    [void][Win32Fg]::GetWindowThreadProcessId($fg, [ref]$fgPid)
    if ($fgPid -ne $proc.Id) {
        Log ('ABORT: could not focus Claude (foreground pid ' + $fgPid + ', Claude pid ' + $proc.Id + '). Nothing typed - refusing to paste into another window.')
        exit 1
    }

    # ── paste + send ──────────────────────────────────────────────────────────
    [System.Windows.Forms.SendKeys]::SendWait('^v')
    Start-Sleep -Milliseconds 500
    [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')

    $preview = ($text -replace '\s+', ' ')
    if ($preview.Length -gt 80) { $preview = $preview.Substring(0, 80) + '...' }
    Log ('SENT to Claude (pid ' + $proc.Id + '): ' + $preview)
    exit 0
}
catch {
    Log ('ERROR: ' + $_.Exception.Message)
    exit 1
}
