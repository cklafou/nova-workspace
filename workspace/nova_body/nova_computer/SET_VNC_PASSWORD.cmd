@echo off
REM @nova: Sets the password of Nova's desktop viewer (the Computer widget) from nova_computer\desktop_secret.json and proves it works.
title Nova Computer - desktop viewer password
cd /d "%~dp0.."
py -3 -u -m nova_computer.set_vnc_password
echo.
echo Every step is also saved in nova_computer\provision\set_vnc_password.log
pause
