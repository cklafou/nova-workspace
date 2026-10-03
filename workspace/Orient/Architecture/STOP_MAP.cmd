@echo off
setlocal
set "NOVA_ATLAS_SCRIPT=%~dp0..\..\general_tools\architecture_map\serve.py"
powershell -NoProfile -WindowStyle Hidden -Command "$atlasPython = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source; if (-not $atlasPython) { $atlasPython = (Get-Command python.exe -ErrorAction Stop).Source }; Start-Process -FilePath $atlasPython -ArgumentList @(([char]34 + $env:NOVA_ATLAS_SCRIPT + [char]34), '--stop') -WindowStyle Hidden"
endlocal
