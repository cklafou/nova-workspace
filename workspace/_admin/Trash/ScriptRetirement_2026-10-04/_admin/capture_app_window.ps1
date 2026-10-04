# capture_app_window.ps1 - one-shot: record the Nova app window's CURRENT rect into
# _admin/app_window.json, so the very next boot opens exactly where Cole left it.
# (After that boot the page's own ?app=1 saver keeps the file fresh forever; this script
#  exists only to seed the first restart with his current size. DPI note: on a scaled
#  display this may over-measure once - the in-page saver corrects it within seconds.)
$ErrorActionPreference = 'Stop'
$ws = Split-Path -Parent $PSScriptRoot
$ids = (Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" |
        Where-Object { $_.CommandLine -match 'nova_app_profile' }).ProcessId
if (-not $ids) { Write-Output 'NO APP WINDOW: no chrome.exe using nova_app_profile'; exit 1 }
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public struct NRect { public int L, T, R, B; }
public class NWin {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out NRect r);
}
"@
$p = Get-Process -Id $ids -ErrorAction SilentlyContinue |
     Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $p) { Write-Output 'NO APP WINDOW: profile chrome found but no visible window'; exit 1 }
$r = New-Object NRect
[NWin]::GetWindowRect($p.MainWindowHandle, [ref]$r) | Out-Null
$g = @{ x = $r.L; y = $r.T; w = ($r.R - $r.L); h = ($r.B - $r.T) }
if ($g.w -lt 400 -or $g.h -lt 300) { Write-Output 'IMPLAUSIBLE RECT - not saved'; exit 1 }
$out = Join-Path $ws '_admin\app_window.json'
$g | ConvertTo-Json -Compress | Set-Content -Path $out -Encoding ASCII
Write-Output ("SAVED " + (Get-Content $out))
