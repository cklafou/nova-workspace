@echo off
setlocal
title Nova - repair git so pushes work again (one-time)
REM @nova: One-time git repair - folds unpushed autosaves without the VM tar, Drive temp files, avatar files and the work-queue DB, then pushes.
cd /d "%~dp0..\.."
echo ================================================================
echo  Repairing git so the watcher can push again.
echo.
echo  Unpushed history holds things GitHub will not take:
echo    * NovaDrop\nova_computer_20260905.tar - a 1 GB VM export,
echo      auto-committed 2026-09-07
echo    * ~75,000 Google Drive temp files from .tmp.driveupload,
echo      auto-committed 2026-10-01
echo    * avatar files under nova_body\SELF\Avatar - about 1.1 GB of rigs,
echo      art and checkpoints; excluded from git 2026-10-03
echo    * nova_body\memory\runtime_work.sqlite3 - Nova's live work queue
echo.
echo  This folds the unpushed autosaves into ONE commit without them and
echo  pushes it. Files on disk are never touched. The original commits stay
echo  on your computer on branch backup/before-fix-git.
echo ================================================================
echo.
echo Quit Nova first (tray icon, Quit Nova) and pause Codex. Then press a key.
pause >nul
echo.
if exist ".git\index.lock" goto :locked
git rev-parse --verify -q origin/master >nul
if errorlevel 1 goto :noorigin

for /f %%i in ('git rev-parse HEAD') do set "SAFE=%%i"
git branch backup/before-fix-git %SAFE% 2>nul
if errorlevel 1 echo Branch backup/before-fix-git already exists - keeping the original.
echo Original history: branch backup/before-fix-git
echo.

echo --- 1/5  keep Google Drive's temp folders out of git ---
findstr /b /c:".tmp.driveupload/" .gitignore >nul 2>&1
if errorlevel 1 (
  >>.gitignore echo.
  >>.gitignore echo # Google Drive for Desktop stages its uploads and downloads here. Never source.
  >>.gitignore echo .tmp.driveupload/
  >>.gitignore echo .tmp.drivedownload/
)
echo done.

echo --- 2/5  untrack Drive temp files, NovaDrop, avatar files and the work queue - files stay on disk ---
git rm -r --cached --quiet --ignore-unmatch -- .tmp.driveupload .tmp.drivedownload NovaDrop workspace/nova_body/SELF/Avatar workspace/nova_body/memory/runtime_work.sqlite3
if errorlevel 1 goto :fail
echo done.

echo --- 3/5  fold the unpushed autosaves into one commit ---
git reset --soft origin/master
if errorlevel 1 goto :fail
git add -A
if errorlevel 1 echo WARNING: some files could not be added. The watcher will add them later.
git commit -q -m "Fold unpushed autosaves into one commit" -m "Drops NovaDrop/nova_computer_20260905.tar (1 GB VM export), ~75k Google Drive temp files (.tmp.driveupload) the watcher swept in, the avatar files under nova_body/SELF/Avatar (excluded from git 2026-10-03) and the live work-queue database. GitHub rejects files over 100 MB. The original commits are kept locally on branch backup/before-fix-git."
if errorlevel 1 goto :fail
git log --oneline -1

echo --- 4/5  anything over 100 MB still committed? ---
powershell -NoProfile -Command "$big = git ls-tree -r -l HEAD | Where-Object { $f = $_ -split '\s+'; $f[3] -match '^\d+$' -and [int64]$f[3] -gt 100MB }; if ($big) { $big; exit 1 }"
if errorlevel 1 goto :toobig
echo none.

echo --- 5/5  install the git hooks and push ---
copy /y "workspace\general_tools\architecture_map\hooks\pre-commit" ".git\hooks\pre-commit" >nul
copy /y "workspace\general_tools\nova_sync\hooks\pre-push" ".git\hooks\pre-push" >nul
git push origin HEAD
if errorlevel 1 goto :fail
echo.
echo SUCCESS - pushes work again. Start Nova; autosave and push resume.
goto :done

:toobig
echo.
echo STOPPED before pushing. The file^(s^) listed above are over 100 MB.
echo Add each to .gitignore, run  git rm --cached "PATH"  for each, then run this again.
echo Nothing was uploaded.
goto :done

:locked
echo .git\index.lock exists - Nova, Codex or another git command is still running.
echo Quit them and run this again. If nothing is running, delete .git\index.lock first.
goto :done

:noorigin
echo There is no origin/master here, so there is nothing to repair against. Nothing changed.
goto :done

:fail
echo.
echo FAILED - nothing was uploaded and your files on disk were not touched.
echo To put history back exactly as it was:   git reset backup/before-fix-git
echo Send the output above to Claude.

:done
echo.
pause
