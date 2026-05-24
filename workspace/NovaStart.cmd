@echo off
REM @nova: Launcher — runs nova_start.py to bring up the whole Nova stack (double-click entry point).
title Project Nova - Launcher
cd /d "%~dp0"

REM Prefer the py launcher, fall back to python on PATH.
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
