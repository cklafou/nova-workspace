@echo off
REM Fires _admin\hourly_prompt.txt into the already-open Claude Desktop conversation.
REM Safe to double-click, safe for Task Scheduler.
REM
REM 2026-07-19: REPOINTED. This called _admin\ask_claude.ps1, which is retired and replaced by
REM general_tools\ping_claude.ps1 — same job, but it RETRIES the focus grab (Windows routinely
REM refuses a foreground change while another app is active) and queues to logs\ping_queue.jsonl
REM instead of silently losing the message. Leaving this aimed at the old path would have made a
REM scheduled task fail quietly every hour: exactly the failure class this project keeps getting
REM bitten by.
REM
REM Nova reaches Claude HERSELF with the ping_claude tool, in her own words — that is the live
REM path and the reason the script moved into general_tools. This wrapper is only for the fixed
REM hourly prompt.
REM Log: logs\ping_claude.log    Undelivered: logs\ping_queue.jsonl
powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%~dp0..\general_tools\ping_claude.ps1" -File "%~dp0hourly_prompt.txt"
exit /b %ERRORLEVEL%
