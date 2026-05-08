@echo off
TITLE Nova Qt — Install Dependencies
COLOR 0A
echo.
echo ==================================================
echo   NOVA QT — Installing Python dependencies
echo ==================================================
echo.

echo [1/3] Installing PyQt6...
pip install PyQt6 --quiet
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PyQt6 install failed.
    pause & exit /b 1
)
echo        PyQt6 OK.

echo [2/3] Installing websocket-client...
pip install websocket-client --quiet
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: websocket-client install failed.
    pause & exit /b 1
)
echo        websocket-client OK.

echo [3/3] Installing markdown2...
pip install markdown2 requests --quiet
echo        markdown2 + requests OK.

echo [4/4] Installing Nova memory dependencies (lancedb, sentence-transformers)...
pip install lancedb sentence-transformers --quiet
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: memory deps install failed - Nova memory will be disabled.
) else (
    echo        lancedb + sentence-transformers OK.
)

echo.
echo ==================================================
echo   All dependencies installed.
echo   Run Nova normally: double-click Nova.exe
echo   Or dev mode: python general_tools\NovaLauncher.py
echo ==================================================
echo.
pause
