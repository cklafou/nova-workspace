@echo off
title Nova Computer - tune up
cd /d "%~dp0.."
echo Tuning her computer: fixing her home, clearing stale X locks, then REBOOTING her.
echo This takes 1-2 minutes and the window stays quiet while she restarts.
echo.
type nul > "nova_computer\provision\tune_up.log"
py -3 -u -m nova_computer.tune_up 2>&1 | powershell -NoProfile -Command "$input | ForEach-Object { Write-Host $_; Add-Content -LiteralPath 'nova_computer\provision\tune_up.log' -Value $_ -Encoding UTF8 }"
echo.
pause
