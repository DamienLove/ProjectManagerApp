@echo off
setlocal EnableDelayedExpansion

rem Repo root (this script lives there).
set "ROOT=%~dp0"
cd /d "%ROOT%"

rem Optional: Firebase service account for cloud sync.
if exist "%ROOT%secrets\firebase-service-account.json" (
  set "GOOGLE_APPLICATION_CREDENTIALS=%ROOT%secrets\firebase-service-account.json"
)

rem Prefer exe unless USE_PYTHON=1.
set "PY="
set "FORCE_PY="
if /I "%USE_PYTHON%"=="1" set "FORCE_PY=1"

rem Auto-pick a free port if REMOTE_PORT is not already defined.
if not defined REMOTE_PORT (
  for %%P in (8765 8767 8768 8769 8770 8771) do (
    netstat -ano | findstr /r /c:":%%P " >nul
    if !errorlevel! neq 0 (
      set "REMOTE_PORT=%%P"
      goto :port_done
    )
  )
  :port_done
  if defined REMOTE_PORT echo Using REMOTE_PORT=!REMOTE_PORT!
)

set "EXE="
if exist "%ROOT%omni_remote_android\\dist\\OmniProjectSync.exe" (
  set "EXE=%ROOT%omni_remote_android\\dist\\OmniProjectSync.exe"
) else if exist "%ROOT%dist\\OmniProjectSync.exe" (
  set "EXE=%ROOT%dist\\OmniProjectSync.exe"
)

if defined EXE if not defined FORCE_PY goto :run_exe

rem Prefer py -3 if available, fallback to python.
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)

rem Validate Python (avoid Microsoft Store alias).
if defined PY (
  !PY! --version 2>&1 | findstr /i "was not found" >nul
  if !errorlevel! == 0 set "PY="
)

if defined PY (
  rem Install deps if needed (quiet).
  !PY! -m pip install -r requirements.txt --quiet

  rem Capture logs for debugging.
  set "LOG=%ROOT%launch_log.txt"
  !PY! src\main.py > "%LOG%" 2>&1

  if !errorlevel! neq 0 (
    echo.
    echo ! ERROR: Omni Project Sync failed to start.
    echo ! Log: %LOG%
    pause
  )
  endlocal
  exit /b !errorlevel!
)

rem Fallback to packaged exe when Python isn't available.
if not defined EXE (
  echo.
  echo ! ERROR: Python not found and OmniProjectSync.exe missing.
  echo ! Checked: %ROOT%omni_remote_android\\dist and %ROOT%dist
  pause
  endlocal
  exit /b 1
)

:run_exe
for %%F in ("%EXE%") do set "EXE_DIR=%%~dpF"

rem Ensure secrets.env is alongside the exe for packaged mode.
if exist "%ROOT%secrets.env" (
  copy /Y "%ROOT%secrets.env" "%EXE_DIR%secrets.env" >nul
)

pushd "%EXE_DIR%"
start "" "%EXE%"
popd

endlocal
