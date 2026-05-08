@echo off
TITLE Nova Auto-Patcher
COLOR 0A

echo ==================================================
echo              NOVA FILE AUTO-PATCHER
echo ==================================================
echo.
echo Scanning workspace root for staged .py files...
echo.

:: Run the --pup command through python automatically
python general_tools\nova_sync\watcher.py --pup

echo.
echo ==================================================
echo Patching complete.
echo ==================================================
pause
