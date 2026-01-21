@echo off
setlocal

rem Repo root (this script lives there).
set "ROOT=%~dp0"
cd /d "%ROOT%"

rem Optional: Firebase service account for cloud sync.
if exist "%ROOT%secrets\firebase-service-account.json" (
  set "GOOGLE_APPLICATION_CREDENTIALS=%ROOT%secrets\firebase-service-account.json"
)

rem Prefer py -3 if available, fallback to python.
set "PY=python"
where py >nul 2>nul && set "PY=py -3"

rem Install deps if needed (quiet).
%PY% -m pip install -r requirements.txt --quiet

rem Capture logs for debugging.
set "LOG=%ROOT%launch_log.txt"
%PY% src\main.py > "%LOG%" 2>&1

if %errorlevel% neq 0 (
  echo.
  echo ! ERROR: Omni Project Sync failed to start.
  echo ! Log: %LOG%
  pause
)

endlocal
