@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"
echo [1/3] Unblocking files...
powershell -Command "Get-ChildItem -Path . -Recurse -File | Where-Object { $_.Name -ne 'nul' } | Unblock-File -ErrorAction SilentlyContinue"
echo [2/3] Checking dependencies...
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
