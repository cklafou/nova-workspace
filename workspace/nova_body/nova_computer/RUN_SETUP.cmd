@echo off
title Nova Computer - first boot
cd /d "%~dp0.."
echo Building the Nova computer... output logs to nova_computer\provision\first_boot.log
py -3 -u -m nova_computer.first_boot > nova_computer\provision\first_boot.log 2>&1
if errorlevel 1 python -u -m nova_computer.first_boot > nova_computer\provision\first_boot.log 2>&1
echo Done. This window closes in 15 seconds.
timeout /t 15 >nul
