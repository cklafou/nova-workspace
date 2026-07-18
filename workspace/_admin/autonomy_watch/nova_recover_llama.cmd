@echo off
REM Nova Autonomy Watchdog - surgical recovery, 2026-07-19
REM Unwedge nova_chat (:8765): its event loop is blocked in a terminal_run sp.run()
REM whose stdout pipe is held open by a bare llama-server (grandchild of an orphaned
REM `cmd /c start_llama_qwen36.cmd` from terminal_run). Killing that server closes the
REM pipe -> communicate() returns -> loop unblocks. The orphaned launcher cmd is killed
REM FIRST so it cannot resume and respawn a bare server that re-inherits the pipe
REM (mirrors LlamaControl._kill_port ordering). No data touched; no state files edited.
setlocal
set "OUT=%~dp0nova_recover_result.txt"
echo recovery started %DATE% %TIME%> "%OUT%"
powershell -NoProfile -Command "$c = Get-CimInstance Win32_Process | ? { $_.CommandLine -like '*start_llama_qwen36.cmd*' }; if ($c) { $c | % { 'kill launcher-cmd PID ' + $_.ProcessId; Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue } } else { 'no orphaned launcher cmd' }">> "%OUT%" 2>&1
powershell -NoProfile -Command "$l = Get-Process llama-server -EA SilentlyContinue; if ($l) { $l | % { 'kill llama-server PID ' + $_.Id }; Stop-Process -Name llama-server -Force -EA SilentlyContinue } else { 'no llama-server' }">> "%OUT%" 2>&1
echo recovery done %DATE% %TIME%>> "%OUT%"
endlocal
