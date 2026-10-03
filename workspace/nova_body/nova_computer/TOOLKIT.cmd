@echo off
title Nova Computer - her own toolkit
cd /d "%~dp0.."
echo Making her computer self-sufficient: checking network/sudo/apt, then installing a
echo workstation base INTO HER VM (not onto this PC), plus thinkorswim for Linux.
echo This downloads packages and takes several minutes.
echo.
type nul > "nova_computer\provision\toolkit.log"
py -3 -u -m nova_computer.toolkit --tos 2>&1 | powershell -NoProfile -Command "$input | ForEach-Object { Write-Host $_; Add-Content -LiteralPath 'nova_computer\provision\toolkit.log' -Value $_ -Encoding UTF8 }"
echo.
pause
