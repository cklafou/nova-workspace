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
# 2026-07-19: this script failed 100% of the time, silently, and the cause was one em-dash.
# Windows PowerShell 5.1 reads a .ps1 with no UTF-8 BOM using the ANSI codepage (cp1252). An
# em-dash is UTF-8 E2 80 94, which cp1252 renders as three characters ending in 0x94 - a RIGHT
# CURLY DOUBLE QUOTE. PowerShell accepts curly quotes as real string delimiters, so the string
# closed mid-sentence and the file failed to PARSE. A parse error kills the whole script before
# line 1 runs: no logging, no queueing, no error handler.
#
# A BOM would also fix it, but BOMs get stripped by editors, git filters and copy-paste. ASCII
# cannot be stripped. Her MESSAGE may contain any Unicode she likes - emoji included - because
# it arrives via -MessageFile and is never parsed as code. See tool_router.ping_claude().
# ############################################################################################
#
# ============================================================================================
# HOW IT FINDS THE WINDOW (rewritten 2026-07-19, second failure)
#
# First real ping after the ASCII fix logged this, four times:
#     attempt 1 of 4: could not focus Claude (fg pid 12496, want 15412)
# Claude Desktop was ALREADY in the foreground - Cole was typing in it. We had simply picked the
# wrong window. The old code took Get-Process, filtered on MainWindowHandle, and sorted by title
# length; Claude Desktop is Electron and spawns several processes that satisfy that filter, so
# "longest title wins" chose a sibling window and then spent four attempts trying to raise it
# over the real one. It was fighting the user for a window he was already looking at.
#
# Now:
#   1. ENUMERATE every visible top-level window and keep the ones owned by a Claude process.
#      MainWindowHandle is not trusted; EnumWindows sees what is actually on screen.
#   2. IF ONE IS ALREADY IN FRONT, SEND. No focus stealing at all. This is the common case
#      whenever Cole is at the machine, and it is the case that used to fail.
#   3. Otherwise force the foreground properly: AttachThreadInput to the current foreground
#      thread plus a synthetic ALT tap, which is what releases the foreground lock. A bare
#      SetForegroundWindow from a background process is refused by Windows by design.
#   4. Try EVERY candidate window, not one guess.
#   5. If it still cannot deliver, FLASH the taskbar button so Cole can SEE she wanted him,
#      and queue the message.
# Every candidate is logged, so the next failure is diagnosable instead of a guess.
# ============================================================================================
#
# SAFETY (unchanged and non-negotiable): it verifies the foreground window really belongs to
# Claude's process before sending a single keystroke. Pasting a wall of text into a game, a
# terminal or a document is not an acceptable failure mode.
#
# NOTE: the P/Invoke below is built from a string ARRAY on purpose. A here-string breaks when
# the file has Unix line endings ("string is missing the terminator"). Do not "tidy" it back.
# The C# must stay C#5-compatible - PS 5.1's Add-Type has no string interpolation, no `out var`.
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
    [int]$Attempts       = 5
)

$ErrorActionPreference = 'Stop'

$wsRoot = Split-Path -Parent $PSScriptRoot          # ...\workspace
$logDir = Join-Path $wsRoot 'logs'
$log    = Join-Path $logDir 'ping_claude.log'
$queue  = Join-Path $logDir 'ping_queue.jsonl'

# UTF-8 with NO BOM. Add-Content -Encoding UTF8 on PS 5.1 writes a BOM at file creation, which
# made the first line of ping_queue.jsonl unparseable as JSON - a queue nothing could read.
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-Line($path, $line) {
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    [System.IO.File]::AppendAllText($path, $line + [Environment]::NewLine, $Utf8NoBom)
}

function Log($msg) {
    Write-Line $log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + '  ' + $msg)
}

function QueueIt($text, $why) {
    # Never lose her words. A dropped ping means she waits for help that is not coming.
    $rec = [ordered]@{
        ts      = (Get-Date -Format 'o')
        reason  = $why
        message = $text
    } | ConvertTo-Json -Compress
    Write-Line $queue $rec
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
            'using System.Text;',
            'using System.Collections.Generic;',
            'using System.Runtime.InteropServices;',
            'public class Win32Fg {',
            '  public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);',
            '  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr lParam);',
            '  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);',
            '  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);',
            '  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder s, int max);',
            '  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();',
            '  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);',
            '  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);',
            '  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);',
            '  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);',
            '  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);',
            '  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);',
            '  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();',
            '  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);',
            '  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }',
            '  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);',
            '  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);',
            '  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr e);',
            '  public static void ClickAt(int x, int y) {',
            '    SetCursorPos(x, y);',
            '    mouse_event(0x02, 0, 0, 0, UIntPtr.Zero);   // LEFTDOWN',
            '    mouse_event(0x04, 0, 0, 0, UIntPtr.Zero);   // LEFTUP',
            '  }',
            '  public static int[] Rect(IntPtr hWnd) {',
            '    RECT r = new RECT();',
            '    GetWindowRect(hWnd, out r);',
            '    return new int[] { r.Left, r.Top, r.Right, r.Bottom };',
            '  }',
            '  [StructLayout(LayoutKind.Sequential)] public struct FLASHWINFO {',
            '    public uint cbSize; public IntPtr hwnd; public uint dwFlags; public uint uCount; public uint dwTimeout; }',
            '  [DllImport("user32.dll")] public static extern bool FlashWindowEx(ref FLASHWINFO pwfi);',
            '',
            '  // Every visible top-level window, as "hwnd|pid|title".',
            '  public static List<string> Windows() {',
            '    List<string> res = new List<string>();',
            '    EnumWindows(delegate(IntPtr h, IntPtr l) {',
            '      if (!IsWindowVisible(h)) return true;',
            '      int len = GetWindowTextLength(h);',
            '      if (len == 0) return true;',
            '      StringBuilder sb = new StringBuilder(len + 2);',
            '      GetWindowText(h, sb, sb.Capacity);',
            '      uint pid = 0; GetWindowThreadProcessId(h, out pid);',
            '      res.Add(h.ToInt64() + "|" + pid + "|" + sb.ToString());',
            '      return true;',
            '    }, IntPtr.Zero);',
            '    return res;',
            '  }',
            '',
            '  // Windows refuses SetForegroundWindow from a background process. Attaching our input',
            '  // queue to the current foreground thread, plus a synthetic ALT tap, is the documented',
            '  // way to be allowed. Without this a background ping can essentially never win focus.',
            '  public static bool Force(IntPtr hWnd) {',
            '    if (hWnd == IntPtr.Zero) return false;',
            '    if (GetForegroundWindow() == hWnd) return true;',
            '    IntPtr fg = GetForegroundWindow();',
            '    uint dummy = 0;',
            '    uint fgThread = GetWindowThreadProcessId(fg, out dummy);',
            '    uint myThread = GetCurrentThreadId();',
            '    keybd_event(0x12, 0, 0, UIntPtr.Zero);',
            '    keybd_event(0x12, 0, 2, UIntPtr.Zero);',
            '    bool attached = false;',
            '    if (fgThread != 0 && fgThread != myThread) attached = AttachThreadInput(myThread, fgThread, true);',
            '    if (IsIconic(hWnd)) ShowWindow(hWnd, 9);',
            '    BringWindowToTop(hWnd);',
            '    SetForegroundWindow(hWnd);',
            '    if (attached) AttachThreadInput(myThread, fgThread, false);',
            '    return GetForegroundWindow() == hWnd;',
            '  }',
            '',
            '  public static void Flash(IntPtr hWnd) {',
            '    FLASHWINFO fi = new FLASHWINFO();',
            '    fi.cbSize = (uint)Marshal.SizeOf(typeof(FLASHWINFO));',
            '    fi.hwnd = hWnd;',
            '    fi.dwFlags = 2 | 12;   // FLASHW_TRAY | FLASHW_TIMERNOFG',
            '    fi.uCount = 6;',
            '    fi.dwTimeout = 0;',
            '    FlashWindowEx(ref fi);',
            '  }',
            '}'
        ) -join [Environment]::NewLine
        Add-Type -TypeDefinition $src
    }

    # -- find every Claude window that is actually on screen -------------------
    $claudePids = @{}
    foreach ($p in (Get-Process | Where-Object { $_.ProcessName -match 'Claude' })) {
        $claudePids[[uint32]$p.Id] = $p.ProcessName
    }
    if ($claudePids.Count -eq 0) {
        QueueIt $text 'claude-desktop-not-running'
        Write-Output 'QUEUED: Claude Desktop is not running. Your message was saved to logs/ping_queue.jsonl, NOT delivered.'
        exit 2
    }

    $cands = @()
    foreach ($w in [Win32Fg]::Windows()) {
        $bits = $w.Split('|', 3)
        $wpid = [uint32]$bits[1]
        if ($claudePids.ContainsKey($wpid)) {
            $cands += [pscustomobject]@{
                Hwnd  = [IntPtr][int64]$bits[0]
                Pid   = $wpid
                Title = $bits[2]
            }
        }
    }
    if ($cands.Count -eq 0) {
        QueueIt $text 'claude-running-but-no-visible-window'
        Write-Output 'QUEUED: Claude Desktop is running but has no visible window (minimised to tray?). Saved to logs/ping_queue.jsonl, NOT delivered.'
        exit 2
    }
    Log ('candidates: ' + (($cands | ForEach-Object { $_.Pid.ToString() + ':' + $_.Title }) -join ' ; '))

    # ========================================================================================
    # PUTTING THE CARET IN THE BOX (2026-07-19, third failure)
    #
    # Cole: "It brought up the window and copied the Message, but it didn't hit the text box
    # nor post." Foreground and clipboard were both fine. The gap was KEYBOARD FOCUS: raising
    # a window does not give any control inside it the caret. Chromium restores focus to
    # whatever was last focused in that renderer, which after a background activation is often
    # nothing at all. Ctrl+V and Enter were being delivered to a window with no focused editor,
    # so both went nowhere.
    #
    # I could not screenshot Claude Desktop to hardcode where the composer sits - and I should
    # not want to, because a pixel offset breaks the first time the window is resized. So this
    # asks the app where its text box is, via UI Automation:
    #   1. Find the lowest keyboard-focusable Edit/Document in the window. Composers live at
    #      the bottom; that ordering is far more stable than any coordinate.
    #   2. SetFocus() on it, then paste.
    #   3. READ THE TEXT BACK before pressing Enter. If the paste did not land we must NOT fire
    #      a stray Enter into an unknown control - we fail loudly and queue instead.
    # Only if UIA finds nothing at all do we fall back to a click, computed from the live window
    # rect rather than a magic number.
    #
    # Chromium builds its accessibility tree lazily, on first query, so the first FindAll can
    # come back empty. Hence the retry.
    # ========================================================================================
    try { Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes } catch {}

    function Find-Composer($hwnd) {
        $AE = [System.Windows.Automation.AutomationElement]
        $CT = [System.Windows.Automation.ControlType]
        for ($t = 1; $t -le 3; $t++) {
            try {
                $root = $AE::FromHandle($hwnd)
                if (-not $root) { Start-Sleep -Milliseconds 300; continue }
                $isEdit = New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::Edit)
                $isDoc  = New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $CT::Document)
                $focusable = New-Object System.Windows.Automation.PropertyCondition($AE::IsKeyboardFocusableProperty, $true)
                $either = New-Object System.Windows.Automation.OrCondition($isEdit, $isDoc)
                $cond   = New-Object System.Windows.Automation.AndCondition($either, $focusable)
                $found  = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)
                if ($found -and $found.Count -gt 0) {
                    $best = $null; $bestBottom = -1
                    foreach ($e in $found) {
                        try {
                            $r = $e.Current.BoundingRectangle
                            if ($r.Bottom -gt $bestBottom) { $bestBottom = $r.Bottom; $best = $e }
                        } catch {}
                    }
                    if ($best) { Log ('UIA: composer found, ' + $found.Count + ' candidate(s), bottom=' + [int]$bestBottom); return $best }
                }
            } catch { Log ('UIA probe ' + $t + ' failed: ' + $_.Exception.Message) }
            Start-Sleep -Milliseconds 400      # let Chromium build its a11y tree
        }
        Log 'UIA: no focusable Edit/Document found'
        return $null
    }

    function Read-Back($el) {
        if (-not $el) { return $null }
        try { return $el.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value } catch {}
        try { return $el.GetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern).DocumentRange.GetText(-1) } catch {}
        return $null
    }

    # A distinctive slice of HER text, used to prove the paste actually landed.
    $probe = ($text -replace '^\[Nova is pinging you[^\]]*\]\s*', '' -replace '\s+', ' ').Trim()
    if ($probe.Length -gt 24) { $probe = $probe.Substring(0, 24) }

    function Send-It($why, $hwnd) {
        $el = Find-Composer $hwnd
        if ($el) {
            try { $el.SetFocus() } catch { Log ('SetFocus threw: ' + $_.Exception.Message) }
            Start-Sleep -Milliseconds 200
        } else {
            # No a11y tree. Click the composer, positioned from the LIVE window rect: bottom
            # centre, one tenth of the height up. Center-x avoids the attach/send buttons.
            $r = [Win32Fg]::Rect($hwnd)
            $cx = [int](($r[0] + $r[2]) / 2)
            $cy = [int]($r[3] - [Math]::Max(50, ($r[3] - $r[1]) * 0.09))
            Log ('UIA unavailable - clicking composed point ' + $cx + ',' + $cy + ' in rect ' + ($r -join ','))
            [Win32Fg]::ClickAt($cx, $cy)
            Start-Sleep -Milliseconds 250
        }

        Set-Clipboard -Value $text                # set AFTER focus: some apps clear on activate
        Start-Sleep -Milliseconds 250
        [System.Windows.Forms.SendKeys]::SendWait('^v')
        Start-Sleep -Milliseconds 600

        # Prove it landed before committing to Enter.
        $seen = Read-Back $el
        if ($seen -ne $null -and $seen -ne '') {
            $flatSeen = ($seen -replace '\s+', ' ')
            if ($flatSeen.Contains($probe)) {
                [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
                Log ('SENT + VERIFIED (' + $why + ')')
                return 'verified'
            }
            Log ('PASTE DID NOT LAND (' + $why + '); composer holds: ' +
                 $flatSeen.Substring(0, [Math]::Min(60, $flatSeen.Length)))
            return 'failed'      # do NOT press Enter into an unknown control
        }

        # No read-back available (no UIA, or the control exposes no text pattern). Enter is
        # benign in a chat composer, so still send - but say plainly that it is unconfirmed.
        [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
        Log ('SENT, UNVERIFIED (' + $why + ') - no read-back available')
        return 'unverified'
    }

    # -- 1. already in front? then do not steal focus from the user ------------
    $fgNow = [Win32Fg]::GetForegroundWindow()
    $fgPid = 0
    [void][Win32Fg]::GetWindowThreadProcessId($fgNow, [ref]$fgPid)
    $delivered = $false
    $status    = 'failed'
    if ($claudePids.ContainsKey([uint32]$fgPid)) {
        $status = Send-It ('already foreground, pid ' + $fgPid) $fgNow
        $delivered = ($status -ne 'failed')
    }

    # -- 2. otherwise take the foreground, trying every candidate --------------
    if (-not $delivered) {
        for ($i = 1; $i -le $Attempts -and -not $delivered; $i++) {
            foreach ($c in $cands) {
                [void][Win32Fg]::Force($c.Hwnd)
                Start-Sleep -Milliseconds (250 * $i)   # backoff: focus can lag when busy
                $fg = [Win32Fg]::GetForegroundWindow()
                $p2 = 0
                [void][Win32Fg]::GetWindowThreadProcessId($fg, [ref]$p2)
                # Accept ANY Claude window winning - it may raise a sibling, and that is fine.
                if ($claudePids.ContainsKey([uint32]$p2)) {
                    # Focus the window that actually WON, which may not be the one we pushed.
                    $status = Send-It ('attempt ' + $i + ', pid ' + $p2) $fg
                    if ($status -ne 'failed') { $delivered = $true; break }
                    Log ('focused pid ' + $p2 + ' but the paste did not land; trying the next window')
                }
            }
            if (-not $delivered) {
                Log ('attempt ' + $i + ' of ' + $Attempts + ': foreground pid ' + $p2 +
                     ', delivered=false; tried ' + $cands.Count + ' window(s)')
            }
        }
    }

    if (-not $delivered) {
        # Cannot paste - but at least make it VISIBLE that she wanted him.
        try { [Win32Fg]::Flash($cands[0].Hwnd) } catch {}
        QueueIt $text 'could-not-reach-composer'
        Write-Output ('QUEUED: reached Claude Desktop but could not get the text into its message box ' +
                      'after ' + $Attempts + ' attempts across ' + $cands.Count + ' window(s). Nothing was ' +
                      'submitted - deliberately, since pressing Enter into an unknown control is worse ' +
                      'than not sending. Its taskbar button has been flashed. Your message was SAVED to ' +
                      'logs/ping_queue.jsonl, NOT delivered. Detail in logs/ping_claude.log.')
        exit 2
    }

    $preview = ($text -replace '\s+', ' ')
    if ($preview.Length -gt 90) { $preview = $preview.Substring(0, 90) + '...' }
    if ($status -eq 'verified') {
        Write-Output ('DELIVERED to Claude Desktop (text confirmed in the message box before sending): ' + $preview)
    } else {
        Write-Output ('DELIVERED to Claude Desktop, UNCONFIRMED (the window exposed no readable text box, ' +
                      'so the paste could not be verified - it was submitted anyway): ' + $preview)
    }
    exit 0
}
catch {
    Log ('ERROR: ' + $_.Exception.Message)
    try { QueueIt $text 'script-error' } catch {}
    Write-Output ('ERROR: ' + $_.Exception.Message + ' (message queued if possible)')
    exit 1
}
