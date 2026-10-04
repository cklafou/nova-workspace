@echo off
REM @nova: Changes the password of Nova's desktop viewer (the Computer widget). You type it here; it is never saved in the project.
title Nova Computer - change desktop password
cd /d "%~dp0.."
py -3 -u -m nova_computer.set_vnc_password
echo.
pause
