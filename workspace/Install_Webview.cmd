@echo off
TITLE Install Nova Webview
COLOR 0A
cd /d "%~dp0"

echo.
echo ==================================================
echo   Installing pywebview for Nova modern UI
echo   (Uses Windows Edge WebView2 - no extra download)
echo ==================================================
echo.

python -m pip install pywebview --upgrade
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Install failed. Make sure Python is in your PATH.
    pause
    exit /b 1
)

echo.
echo ==================================================
echo   Done! Run Nova.bat to launch with the new UI.
echo ==================================================
echo.
pause
