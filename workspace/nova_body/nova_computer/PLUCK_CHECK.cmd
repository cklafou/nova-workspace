@echo off
title Nova Computer - PLUCK CHECK
cd /d "%~dp0.."
echo Proving her computer is hers alone (body only, no tools)...
echo.
type nul > "nova_computer\provision\pluck_check.log"
py -3 -u -m nova_computer.pluck_check --live 2>&1 | powershell -NoProfile -Command "$input | ForEach-Object { Write-Host $_; Add-Content -LiteralPath 'nova_computer\provision\pluck_check.log' -Value $_ -Encoding UTF8 }"
if errorlevel 1 python -u -m nova_computer.pluck_check --live
echo.
pause
