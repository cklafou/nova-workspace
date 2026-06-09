@echo off
REM @claude 2026-06-10: Step 6c PLUCK TEST — stops the whole stack, then boots Nova
REM headless (python -m nova_runtime, NO chat server). Output mirrors live here and
REM appends line-by-line to logs\pluck_2026-06-10.log (UTF8, closed per write so
REM Claude's mount can read it). Stop with Ctrl+C or close this window.
title PLUCK TEST - Nova headless (no chat server)
cd /d "%~dp0"

call StopNova.cmd

echo.
echo ==== PLUCK TEST: nova_runtime headless boot (no chat server) ====
echo ==== Live output below; also logging to logs\pluck_2026-06-10.log ====
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -u nova_body\nova_runtime\__main__.py 2>&1 | powershell -NoProfile -Command "$input | ForEach-Object { Write-Host $_; Add-Content -LiteralPath 'logs\pluck_2026-06-10.log' -Value $_ -Encoding UTF8 }"
) else (
    python -u nova_body\nova_runtime\__main__.py 2>&1 | powershell -NoProfile -Command "$input | ForEach-Object { Write-Host $_; Add-Content -LiteralPath 'logs\pluck_2026-06-10.log' -Value $_ -Encoding UTF8 }"
)

echo.
echo Pluck run ended.
pause
