@echo off
title Project Nova
cd /d "%~dp0"
python general_tools\NovaLauncher.py
if errorlevel 1 (
    echo.
    echo Nova exited with an error.
    pause
)
