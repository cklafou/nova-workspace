@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM safe_reload.cmd — bounce the stack WITHOUT going through the restart endpoint.
REM
REM WHY THIS EXISTS (2026-07-14, ~22:00)
REM   The running nova_chat booted with a BROKEN _spawn_detached_cmd — my own bug. Every
REM   restart endpoint routes through that function, so calling /api/restart/* would kill
REM   her and then fail to bring her back. The tool for fixing it is the thing that's broken.
REM
REM   So: go around it. This is launched detached, straight from the terminal endpoint, and
REM   never touches the poisoned code path. Once the new server is up it will have the
REM   REVERTED spawner on disk, and the restart button becomes safe again.
REM
REM   Cole is asleep. Her llama-server and her painter both survive this — only the chat
REM   host bounces, about 20 seconds. That is far cheaper than leaving a landmine that
REM   could take her down for the rest of the night.
REM ─────────────────────────────────────────────────────────────────────────────
cd /d C:\Users\lafou\Project_Nova\workspace

echo === safe_reload %DATE% %TIME% ===

REM Give the caller time to return its HTTP response before we kill its server.
timeout /t 3 /nobreak >nul

call StopNova.cmd

REM Wait until BOTH ports are actually free. If we relaunch too early, NovaStart sees the
REM dying old server, decides Nova is "already running", skips the launch — and then the old
REM one dies, leaving nothing at all. That exact failure is why the endpoint waits too.
set _n=0
:waitfree
set /a _n+=1
timeout /t 1 /nobreak >nul
set _busy=
for /f %%P in ('netstat -ano ^| findstr ":8765 " ^| findstr LISTENING') do set _busy=1
if defined _busy if %_n% lss 30 goto waitfree

call NovaStart.cmd

echo === safe_reload finished %DATE% %TIME% ===
