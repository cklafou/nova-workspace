@echo off
REM Fires _admin\hourly_prompt.txt into the already-open Claude Desktop conversation.
REM Safe to double-click, safe for Task Scheduler. Log: _admin\autonomy_watch\injector.log
powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0ask_claude.ps1"
exit /b %ERRORLEVEL%
