@echo off
REM nightwatch one-shot revive - 2026-07-15 23:10 KST. Spawned by a self-deleting post-commit hook.
REM Why: chat listener (8765) died ~21:02 inside a living process; painter (8188) down.
set WS=C:\Users\lafou\Project_Nova\workspace
set TLOG=%WS%\_admin\Temp\nw_revive.log
if not exist "%WS%\_admin\Temp" mkdir "%WS%\_admin\Temp"
echo ==== %date% %time% revive start ==== >> "%TLOG%"
netstat -ano | findstr ":8188 " | findstr LISTENING >nul 2>&1
if not errorlevel 1 goto painter_ok
if exist "C:\Users\lafou\ComfyUI\run_nova_painter.bat" (start "" /b cmd /c "C:\Users\lafou\ComfyUI\run_nova_painter.bat > %WS%\_admin\Temp\painter.log 2>&1") else (start "" /b cmd /c "%WS%\_admin\run_nova_painter.bat > %WS%\_admin\Temp\painter.log 2>&1")
echo %time% painter launched >> "%TLOG%"
goto painter_done
:painter_ok
echo %time% painter already up >> "%TLOG%"
:painter_done
echo %time% killing hung NovaLauncher python >> "%TLOG%"
powershell -NoProfile -NonInteractive -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -match 'NovaLauncher\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >> "%TLOG%" 2>&1
timeout /t 4 /nobreak >nul
cd /d "%WS%"
set NOVA_NO_WINDOW=1
set PYTHONUNBUFFERED=1
echo %time% relaunching NovaLauncher via py -3.12 >> "%TLOG%"
start "" /b cmd /c "py -3.12 general_tools\NovaLauncher.py > %WS%\_admin\Temp\nw_revive_nova.log 2>&1"
timeout /t 30 /nobreak >nul
netstat -ano | findstr ":8765 " | findstr LISTENING >nul 2>&1
if not errorlevel 1 goto up
echo %time% not up after 30s - fallback plain python >> "%TLOG%"
start "" /b cmd /c "python general_tools\NovaLauncher.py > %WS%\_admin\Temp\nw_revive_nova2.log 2>&1"
timeout /t 30 /nobreak >nul
:up
netstat -ano | findstr ":8765 " | findstr LISTENING >> "%TLOG%" 2>&1
echo ==== %date% %time% revive end ==== >> "%TLOG%"
