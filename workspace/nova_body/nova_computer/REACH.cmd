@echo off
title Nova Computer - open her reach onto this PC
cd /d "%~dp0.."
echo Giving her computer read-write reach into this PC (whole drive + Windows programs).
echo She keeps her own screen; this does not touch your mouse, keyboard or focus.
echo This reboots her computer and takes 1-2 minutes.
echo.
type nul > "nova_computer\provision\reach.log"
py -3 -u -m nova_computer.reach 2>&1 | powershell -NoProfile -Command "$input | ForEach-Object { Write-Host $_; Add-Content -LiteralPath 'nova_computer\provision\reach.log' -Value $_ -Encoding UTF8 }"
echo.
pause
