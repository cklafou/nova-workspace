@echo off
title Nova Computer - her hands
cd /d "%~dp0.."
echo Proving she can SEE her own screen and ACT on it (no part of this touches your mouse).
echo.
type nul > "nova_computer\provision\hands.log"
py -3 -u -m nova_computer.hands --selftest 2>&1 | powershell -NoProfile -Command "$input | ForEach-Object { Write-Host $_; Add-Content -LiteralPath 'nova_computer\provision\hands.log' -Value $_ -Encoding UTF8 }"
echo.
pause
