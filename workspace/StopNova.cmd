@echo off
REM ====================================================================
REM  StopNova.cmd — guaranteed clean shutdown of the whole Nova stack.
REM  Closing the app window does NOT reliably stop the background servers
REM  (Chrome's --app process handoff can detach them), so use this to be
REM  sure everything is actually off before a fresh restart.
REM  Kills whatever is LISTENING on:
REM     8080  = llama-server      8765 = nova_chat      18790 = nova_gateway
REM ====================================================================
title Stop Nova
echo Stopping the Nova stack (ports 8080 / 8765 / 18790)...
echo.

setlocal enabledelayedexpansion
set FOUND=0
for %%P in (8080 8765 18790) do (
    for /f "tokens=5" %%I in ('netstat -ano ^| findstr ":%%P " ^| findstr LISTENING') do (
        echo   - killing PID %%I  (port %%P)
        taskkill /F /PID %%I >nul 2>nul
        set FOUND=1
    )
)

REM Also sweep any orphaned NovaStart.exe (the launcher itself), if present.
taskkill /F /IM NovaStart.exe >nul 2>nul

echo.
if "!FOUND!"=="0" (
    echo Nothing was listening on those ports — Nova was already stopped.
) else (
    echo Nova stack stopped.
)
echo.
echo You can now double-click NovaStart.cmd for a clean restart.
timeout /t 4 >nul
