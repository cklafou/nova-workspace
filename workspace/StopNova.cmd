@echo off
REM @nova: Shutdown — stops the whole Nova stack cleanly.
REM ====================================================================
REM  StopNova.cmd
REM
REM  2026-07-13 REWRITE. The old version only killed whatever was LISTENING on 8080/8765.
REM  That is no longer enough: since the Nova Console landed, the orchestrator (nova_start.py),
REM  the console app, and the WATCHER all run as invisible pythonw processes that listen on
REM  nothing — so StopNova appeared to "do nothing" and the watcher kept firing git commands
REM  forever.
REM
REM  Two phases:
REM    1. ASK NICELY  — POST :8799/api/shutdown. nova_start.py then runs its normal teardown,
REM       which sends CTRL_BREAK to the watcher so it finishes its git push instead of leaving
REM       a stale .git\index.lock behind. A taskkill CANNOT do that.
REM    2. FORCE       — sweep ports 8080/8765/8799, llama-server.exe, and any python/pythonw
REM       still running Nova's scripts.
REM ====================================================================
title Stop Nova
echo Stopping the Nova stack...
echo.

REM ── Phase 1: graceful (lets the watcher release git cleanly) ────────────────
echo   [1/2] asking Nova to shut down cleanly...
powershell -NoProfile -NonInteractive -Command ^
  "try { Invoke-WebRequest -Uri 'http://127.0.0.1:8799/api/shutdown' -Method POST -TimeoutSec 3 -UseBasicParsing | Out-Null; Write-Host '        console hub acknowledged.' } catch { Write-Host '        (hub not running - going straight to force)' }" 2>nul

REM give the teardown a moment: watcher CTRL_BREAK -> git push -> nova -> llama
timeout /t 6 /nobreak >nul

REM ── Phase 2: force sweep ────────────────────────────────────────────────────
echo   [2/2] sweeping anything left...
setlocal enabledelayedexpansion
set FOUND=0
for %%P in (8080 8765 8799) do (
    for /f "tokens=5" %%I in ('netstat -ano ^| findstr ":%%P " ^| findstr LISTENING') do (
        echo         killing PID %%I  (port %%P)
        taskkill /F /PID %%I >nul 2>nul
        set FOUND=1
    )
)

REM llama-server by name: aborted restarts orphan instances that never reach LISTENING.
taskkill /F /IM llama-server.exe >nul 2>nul && set FOUND=1

REM The invisible pythonw crew: orchestrator, console viewer, watcher, launcher.
REM Matched on COMMAND LINE so we never touch an unrelated Python you have open.
powershell -NoProfile -NonInteractive -Command ^
  "$n=0; Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -match 'nova_start\.py|console_app\.py|NovaLauncher\.py|nova_sync[\\/]+watcher\.py|nova_guardian\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $n++ }; if ($n -gt 0) { Write-Host \"        stopped $n Nova python process(es).\" }" 2>nul

taskkill /F /IM NovaStart.exe >nul 2>nul

echo.
echo Nova stack stopped.
echo You can now double-click NovaStart.cmd for a clean restart.
timeout /t 3 >nul
