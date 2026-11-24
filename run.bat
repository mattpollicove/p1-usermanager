@echo off
REM PingOne User Manager Test Runner
REM This script activates the virtual environment and runs the application

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
echo %BLUE%║   PingOne User Manager - Test Runner   ║%NC%
echo %BLUE%╚════════════════════════════════════════╝%NC%
echo.

REM Check if venv exists
if not exist "%VENV_PATH%" (
    echo %YELLOW%⚠ Virtual environment not found at %VENV_PATH%%NC%
    echo Creating virtual environment...
    python -m venv "%VENV_PATH%"
    if !errorlevel! equ 0 (
        echo %GREEN%√ Virtual environment created%NC%
    ) else (
        echo %RED%Error: Failed to create virtual environment%NC%
        exit /b 1
    )
)

REM Check if Python exists in venv
if not exist "%PYTHON%" (
    echo %YELLOW%⚠ Python not found in virtual environment%NC%
    echo Attempting to create venv...
    python -m venv "%VENV_PATH%"
    if !errorlevel! neq 0 (
        echo %RED%Error: Failed to create virtual environment%NC%
        exit /b 1
    )
)

echo %GREEN%√ Virtual environment found%NC%
echo   Location: %VENV_PATH%
echo.

REM Activate the venv
echo %BLUE%Activating virtual environment...%NC%
call "%VENV_PATH%\Scripts\activate.bat"
echo %GREEN%√ Virtual environment activated%NC%
echo.

REM Check Python version
for /f "tokens=*" %%I in ('"%PYTHON%" --version 2^>^&1') do set "PYTHON_VERSION=%%I"
echo Python: %PYTHON_VERSION%
echo.

REM Check if required packages are installed
echo %BLUE%Checking dependencies...%NC%

setlocal enabledelayedexpansion
set "MISSING_COUNT=0"

for %%P in (PySide6 httpx sqlalchemy ldap3 keyring) do (
    "%PYTHON%" -c "import %%P" 2>nul
    if !errorlevel! equ 0 (
        echo %GREEN%√ %%P%NC%
    ) else (
        echo %YELLOW%✗ %%P (missing)%NC%
        set "MISSING[!MISSING_COUNT!]=%%P"
        set /a "MISSING_COUNT+=1"
    )
)

if !MISSING_COUNT! gtr 0 (
    echo.
    echo %YELLOW%Installing missing packages...%NC%
    for /l %%I in (0,1,!MISSING_COUNT!-1) do (
        echo   Installing !MISSING[%%I]!...
        "%PYTHON%" -m pip install -q !MISSING[%%I]! 2>nul
        if !errorlevel! neq 0 (
            echo %YELLOW%Warning: Failed to install !MISSING[%%I]!%NC%
        )
    )
    echo %GREEN%√ Dependencies installed%NC%
) else (
    echo %GREEN%√ All dependencies installed%NC%
)

endlocal

echo.
echo %BLUE%╔════════════════════════════════════════╗%NC%
echo %BLUE%║      Starting Application...          ║%NC%
echo %BLUE%╚════════════════════════════════════════╝%NC%
echo.

REM Run the app
cd /d "%SCRIPT_DIR%"
"%PYTHON%" app.py

REM Deactivate venv on exit (optional, but good practice)
call "%VENV_PATH%\Scripts\deactivate.bat" 2>nul

endlocal
