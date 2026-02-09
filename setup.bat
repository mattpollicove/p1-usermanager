@echo off
REM PingOne UserManager Setup Script (Windows)
REM This script sets up the development environment

setlocal enabledelayedexpansion

echo ===================================
echo PingOne UserManager Setup
echo ===================================
echo.

REM Check if Python is available
echo Checking Python version...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.9 or higher from https://www.python.org/
    pause
    exit /b 1
)

REM Get Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Found Python %PYTHON_VERSION%

REM Check if version is 3.9 or higher (basic check)
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set MAJOR=%%a
    set MINOR=%%b
)

if %MAJOR% lss 3 (
    echo Error: Python 3.9 or higher is required
    echo Current version: %PYTHON_VERSION%
    pause
    exit /b 1
)

if %MAJOR% equ 3 if %MINOR% lss 9 (
    echo Error: Python 3.9 or higher is required
    echo Current version: %PYTHON_VERSION%
    pause
    exit /b 1
)

echo [OK] Python version check passed
echo.

REM Create virtual environment
echo Creating virtual environment...
if exist venv (
    echo Warning: Virtual environment already exists
    set /p RECREATE="Do you want to recreate it? (y/N): "
    if /i "!RECREATE!"=="y" (
        echo Removing existing virtual environment...
        rmdir /s /q venv
        python -m venv venv
        echo [OK] Virtual environment recreated
    ) else (
        echo Using existing virtual environment
    )
) else (
    python -m venv venv
    echo [OK] Virtual environment created
)
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo Error: Failed to activate virtual environment
    pause
    exit /b 1
)
echo [OK] Virtual environment activated
echo.

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1
echo [OK] pip upgraded
echo.

REM Install dependencies
echo Installing dependencies from requirements.txt...
if not exist requirements.txt (
    echo Error: requirements.txt not found
    pause
    exit /b 1
)

pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed
echo.

echo ===================================
echo [OK] Setup completed successfully!
echo ===================================
echo.
echo To run the application:
echo   1. Activate the virtual environment:
echo      venv\Scripts\activate
echo   2. Run the application:
echo      python app.py
echo.
echo To deactivate the virtual environment when done:
echo   deactivate
echo.
pause
