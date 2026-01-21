@echo off
setlocal

rem This repo is nested; prefer launching the source UI from the parent project.
set "ROOT=%~dp0"
set "PARENT=%ROOT%.."

if exist "%PARENT%\\Launch-OmniSync.bat" (
  echo Launching source UI from %PARENT%
  call "%PARENT%\\Launch-OmniSync.bat"
  exit /b %errorlevel%
)

rem Fallback to the packaged exe if the parent launcher is missing.
set "EXE=%ROOT%dist\\OmniProjectSync.exe"
if not exist "%EXE%" (
  echo OmniProjectSync.exe not found at: %EXE%
  exit /b 1
)

pushd "%ROOT%dist"
start "" "%EXE%"
popdthe

endlocal
