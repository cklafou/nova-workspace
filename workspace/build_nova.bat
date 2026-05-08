@echo off
title Build Nova.exe
cd /d "%~dp0"

echo.
echo ================================================
echo   Building Nova.exe (stub launcher)
echo ================================================
echo.
echo Builds a tiny stub exe that finds your system Python
echo and runs NovaLauncher.py from the workspace at launch.
echo Code changes take effect immediately - no rebuild needed.
echo.
echo Output: Nova.exe  (this folder)
echo Errors go to:  _build\work\  during build
echo.

where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo ERROR: pyinstaller not found. Run:
    echo   pip install pyinstaller
    pause
    exit /b 1
)

:: Remove old artifacts so we know the build actually succeeded
if exist Nova.exe del Nova.exe
:: Remove leftover directory-mode build folder if present
if exist Nova\ rd /s /q Nova

pyinstaller _build\Nova.spec --distpath . --workpath _build\work --noconfirm --clean

if exist Nova.exe (
    echo.
    echo ================================================
    echo   Nova.exe built successfully!
    echo   Double-click Nova.exe to launch.
    echo ================================================
) else (
    echo.
    echo ================================================
    echo   BUILD FAILED - Nova.exe was not created.
    echo   Check output above for errors.
    echo ================================================
)
echo.
pause
