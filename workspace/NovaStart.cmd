@echo off
REM @nova: Launcher — runs nova_start.py to bring up the whole Nova stack (double-click entry point).
REM
REM 2026-07-13: launches via pythonw so this window does NOT stick around. Every child process is
REM now spawned with CREATE_NO_WINDOW and piped into the Nova Console (one dark window with a tab
REM per stream, tray icon once Nova Chat is up). No more cmd-window confetti.
REM Rollback: swap `start "" %PYW%` back to `py -3 nova_start.py` to get the old consoles back.
cd /d "%~dp0"

REM Find a windowless Python (pythonw). Fall back to console python if it isn't there.
set "PYW="
for /f "delims=" %%P in ('where pythonw 2^>nul') do if not defined PYW set "PYW=%%P"

if defined PYW (
    start "" "%PYW%" nova_start.py
    exit /b 0
)

REM --- fallback: no pythonw found, run visibly so the user can see what's wrong ---
echo [NovaStart] pythonw not found on PATH - running in this window instead.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 nova_start.py
) else (
    python nova_start.py
)

if errorlevel 1 (
    echo.
    echo Nova launcher exited with an error. See logs\launcher\ for details.
    pause
)
