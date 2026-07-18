@echo off
REM nova_guardian — one pulse check + self-heal. Safe to double-click, safe for Task Scheduler.
REM No pause: this must exit cleanly when run on a schedule. Output goes to
REM _admin\autonomy_watch\guardian.log
cd /d "%~dp0\.."
python "_admin\nova_guardian.py"
exit /b %ERRORLEVEL%
