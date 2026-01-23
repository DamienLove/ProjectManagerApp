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
set "PY="

rem 1. Try Python Launcher
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 --version >nul 2>&1 && set "PY=py -3"
)

rem 2. Try python (standard)
if not defined PY (
    python --version >nul 2>&1 && set "PY=python"
)

rem 3. Try python3
if not defined PY (
    python3 --version >nul 2>&1 && set "PY=python3"
)

if not defined PY (
    echo.
    echo ! ERROR: Python not found or not working.
    echo ! Please install Python from https://python.org and check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

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
