@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"
echo [1/3] Unblocking files...
powershell -Command "Get-ChildItem -Path . -Recurse -File | Where-Object { $_.Name -ne 'nul' } | Unblock-File -ErrorAction SilentlyContinue"
echo [2/3] Checking dependencies...
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
%PY% -m pip install -r requirements.txt --quiet
echo [3/3] Launching Omni Project Sync...
echo Using: %ROOT%src\\main.py
set "LOG=%ROOT%launch_log.txt"
%PY% -u src\main.py > "%LOG%" 2>&1
if %errorlevel% neq 0 (
echo.
echo ! ERROR: Application failed to start.
echo ! Log: %LOG%
pause
)
endlocal
