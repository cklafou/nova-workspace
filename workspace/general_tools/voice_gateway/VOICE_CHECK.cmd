@echo off
REM @nova: One-click, read-only voice readiness check (GPU memory, voice packages, audio devices, local services); writes voice_check.log.
title Nova Voice - readiness check
cd /d "%~dp0..\.."
py -3 general_tools\voice_gateway\check_voice_ready.py
echo.
pause
