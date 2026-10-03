REM @nova: Open Nova Chat for collaboration without starting Nova's model or autonomous body.
@echo off
cd /d "%~dp0"
setlocal
set "NOVA_CHAT_ONLY=1"
set "NOVA_CHAT_PYW="
for /f "delims=" %%P in ('where pythonw 2^>nul') do if not defined NOVA_CHAT_PYW set "NOVA_CHAT_PYW=%%P"
if defined NOVA_CHAT_PYW (
    start "" "%NOVA_CHAT_PYW%" nova_start.py --chat-only
    exit /b 0
)
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 nova_start.py --chat-only
) else (
    python nova_start.py --chat-only
)
