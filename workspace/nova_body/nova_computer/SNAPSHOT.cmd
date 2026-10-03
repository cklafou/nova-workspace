@echo off
title Nova Computer - baseline snapshot
cd /d "%~dp0.."
echo Exporting a full image of her computer. This is the undo button - run it before
echo letting her work unattended. Takes several minutes and a few GB.
echo.
py -3 -u -c "from nova_computer.computer import NovaComputer; import datetime; d=datetime.datetime.now().strftime(chr(37)+chr(89)+chr(37)+chr(109)+chr(37)+chr(100)); p=r\"C:\Users\lafou\Project_Nova\NovaDrop\nova_computer_\"+d+\".tar\"; print(\"writing\", p); print(NovaComputer().snapshot(p))"
echo.
pause
