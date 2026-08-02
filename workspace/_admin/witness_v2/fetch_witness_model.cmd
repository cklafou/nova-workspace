@echo off
REM @nova-adjacent infra: Witness v2, Step 1 — download the witness model (~2.5GB, one time).
REM Qwen3.5-4B: same family as her Qwen 3.6 base (and the proven 3.5 rollback line), so the
REM chat template / --jinja behavior is known-good on this stack. Official unsloth GGUF.
REM Resumable: safe to re-run if the connection drops (curl -C -).
title Witness v2 - fetch Qwen3.5-4B GGUF
cd /d "%~dp0..\.."

if not exist "models\witness" mkdir "models\witness"

set "REPO=https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main"
set "OUT=models\witness\Qwen3.5-4B-UD-Q4_K_XL.gguf"

echo [witness-fetch] Trying UD-Q4_K_XL (unsloth dynamic 4-bit — best quality/GB)...
curl.exe -L -C - --fail -o "%OUT%" "%REPO%/Qwen3.5-4B-UD-Q4_K_XL.gguf"
if %errorlevel%==0 goto :done

echo [witness-fetch] UD-Q4_K_XL not found under that name - falling back to Q4_K_M...
set "OUT=models\witness\Qwen3.5-4B-Q4_K_M.gguf"
curl.exe -L -C - --fail -o "%OUT%" "%REPO%/Qwen3.5-4B-Q4_K_M.gguf"
if %errorlevel%==0 goto :done

echo.
echo [witness-fetch] Both candidate filenames failed. List the repo's actual files at:
echo    https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/tree/main
echo and edit the OUT/URL lines above to match. (Any ~4B instruct Q4-class GGUF works;
echo the MTP variant unsloth/Qwen3.5-4B-MTP-GGUF is a fine speed upgrade too.)
exit /b 1

:done
echo.
echo [witness-fetch] Done: %OUT%
for %%A in ("%OUT%") do echo [witness-fetch] Size: %%~zA bytes (expect roughly 2.3-2.9 GB)
echo [witness-fetch] Next: _admin\witness_v2\start_witness.cmd
pause
