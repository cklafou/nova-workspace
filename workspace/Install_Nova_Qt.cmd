@echo off
TITLE Nova Qt — Install Dependencies
COLOR 0A
echo.
echo ==================================================
echo   NOVA QT — Installing Python dependencies
echo ==================================================
echo.

echo [1/5] Installing PyQt6...
python -m pip install PyQt6 --quiet
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PyQt6 install failed.
    pause & exit /b 1
)
echo        PyQt6 OK.

echo [2/5] Installing pywebview (Edge WebView2 - modern HTML UI)...
python -m pip install pywebview --quiet
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: pywebview install failed. Nova will use Qt widget fallback.
) else (
    echo        pywebview OK.
)

echo [3/5] Installing PyQt6-WebEngine (optional, alternative renderer)...
python -m pip install PyQt6-WebEngine --quiet
if %ERRORLEVEL% NEQ 0 (
    echo        PyQt6-WebEngine skipped (optional).
) else (
    echo        PyQt6-WebEngine OK.
)

echo [4/5] Installing websocket-client, markdown2, requests...
python -m pip install websocket-client markdown2 requests --quiet
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Core deps install failed.
    pause & exit /b 1
)
echo        Core deps OK.

echo [5/5] Installing Nova memory dependencies (lancedb, sentence-transformers)...
python -m pip install lancedb sentence-transformers --quiet
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
