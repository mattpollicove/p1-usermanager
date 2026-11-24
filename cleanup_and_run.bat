@echo off
REM Cleanup and restart the PingOne User Manager app
REM This script kills any running instances before starting a fresh one

setlocal enabledelayedexpansion

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "VENV_PATH=%SCRIPT_DIR%\venv"
set "PYTHON=%VENV_PATH%\Scripts\python.exe"

REM ANSI color codes for Windows 10+ (requires Windows 10 build 16257+)
REM For older Windows, colors will be ignored
set "BLUE=[34m"
set "GREEN=[32m"
set "YELLOW=[33m"
set "RED=[31m"
set "NC=[0m"

echo.
echo %BLUE%╔════════════════════════════════════════╗%NC%
echo %BLUE%║   PingOne User Manager - Clean Start   ║%NC%
echo %BLUE%╚════════════════════════════════════════╝%NC%
echo.

REM Check for running instances
echo %BLUE%Checking for running instances...%NC%
setlocal
for /f "tokens=2" %%A in ('tasklist /fo csv /nh /fi "IMAGENAME eq python.exe"') do (
    set "RUNNING_PYTHON=1"
)
endlocal & set "RUNNING_PYTHON=%RUNNING_PYTHON%"

if defined RUNNING_PYTHON (
    echo %YELLOW%Found running Python instances:%NC%
    tasklist /fi "IMAGENAME eq python.exe"
    echo.
    echo %YELLOW%Terminating old instances...%NC%
    
    for /f "tokens=2" %%A in ('tasklist /fo csv /nh /fi "IMAGENAME eq python.exe"') do (
        echo   Killing PID %%A...
        taskkill /PID %%A /F >nul 2>&1 || echo   (Already terminated)
    )
    
    timeout /t 1 /nobreak >nul
    echo %GREEN%√ Old instances terminated%NC%
) else (
    echo %GREEN%√ No running Python instances found%NC%
)

echo.

REM Now run the app using run.bat
echo %BLUE%Starting fresh instance...%NC%
echo.
call "%SCRIPT_DIR%\run.bat"
