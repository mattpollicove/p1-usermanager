#!/usr/bin/env python3
"""
PingOne User Manager - Test Runner

This script activates the virtual environment and runs the application.
It can be used as an alternative to the shell script runner.

Usage:
    python3 run.py
    or
    ./run.py
"""

import os
import sys
import subprocess
import venv
from pathlib import Path

# ANSI color codes
GREEN = '\033[0;32m'
BLUE = '\033[0;34m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color

def print_header():
    print(f"{BLUE}╔════════════════════════════════════════╗{NC}")
    print(f"{BLUE}║   PingOne User Manager - Test Runner   ║{NC}")
    print(f"{BLUE}╚════════════════════════════════════════╝{NC}")
    print()

def print_step(message):
    print(f"{BLUE}{message}{NC}")

def print_success(message):
    print(f"{GREEN}✓ {message}{NC}")

def print_warning(message):
    print(f"{YELLOW}⚠ {message}{NC}")

def print_error(message):
    print(f"{RED}✗ {message}{NC}")

def setup_venv(venv_path):
    """Setup virtual environment if it doesn't exist"""
    if venv_path.exists():
        print_success(f"Virtual environment found at {venv_path}")
        return
    
    print_warning(f"Virtual environment not found at {venv_path}")
    print_step("Creating virtual environment...")
    
    try:
        venv.create(str(venv_path), with_pip=True)
        print_success("Virtual environment created")
    except Exception as e:
        print_error(f"Failed to create virtual environment: {e}")
        sys.exit(1)

def get_python_exe(venv_path):
    """Get path to Python executable in venv"""
    if sys.platform == "win32":
        return venv_path / "Scripts" / "python.exe"
    else:
        return venv_path / "bin" / "python3"

def check_dependencies(python_exe):
    """Check if all required packages are installed"""
    required_packages = {
        "PySide6": "PySide6",
        "httpx": "httpx",
        "sqlalchemy": "sqlalchemy",
        "ldap3": "ldap3",
        "keyring": "keyring",
    }
    
    print_step("Checking dependencies...")
    missing = []
    
    for display_name, import_name in required_packages.items():
        try:
            __import__(import_name)
            print_success(display_name)
        except ImportError:
            print_warning(f"{display_name} (missing)")
            missing.append(display_name)
    
    if missing:
        print()
        print_step("Installing missing packages...")
        for package in missing:
            print(f"  Installing {package}...")
            result = subprocess.run(
                [str(python_exe), "-m", "pip", "install", "-q", package],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print_success(f"Installed {package}")
            else:
                print_warning(f"Failed to install {package}: {result.stderr}")
    else:
        print_success("All dependencies installed")

def main():
    print_header()
    
    # Determine project directory
    script_dir = Path(__file__).parent.resolve()
    venv_path = script_dir / "venv"
    
    # Setup virtual environment
    setup_venv(venv_path)
    
    # Get Python executable
    python_exe = get_python_exe(venv_path)
    if not python_exe.exists():
        print_error(f"Python executable not found at {python_exe}")
        sys.exit(1)
    
    print_success(f"Python executable: {python_exe}")
    
    # Get Python version
    result = subprocess.run(
        [str(python_exe), "--version"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print(f"  {result.stdout.strip()}")
    print()
    
    # Activate virtual environment (for subprocesses)
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(venv_path)
    env["PATH"] = f"{venv_path / ('Scripts' if sys.platform == 'win32' else 'bin')}:{env.get('PATH', '')}"
    
    # Check dependencies
    check_dependencies(python_exe)
    print()
    
    # Start application
    print(f"{BLUE}╔════════════════════════════════════════╗{NC}")
    print(f"{BLUE}║      Starting Application...          ║{NC}")
    print(f"{BLUE}╚════════════════════════════════════════╝{NC}")
    print()
    
    # Run the app
    app_script = script_dir / "app.py"
    if not app_script.exists():
        print_error(f"app.py not found at {app_script}")
        sys.exit(1)
    
    try:
        # Run app with stderr filtering to suppress Java Runtime warning from ldap3 on macOS
        process = subprocess.Popen(
            [str(python_exe), str(app_script)],
            cwd=str(script_dir),
            env=env,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Filter and forward output, suppressing Java Runtime warning and related messages
        for line in iter(process.stdout.readline, ''):
            if line and not any(x in line for x in ["Unable to locate a Java", "visit http://www.java.com"]):
                print(line, end='')
        
        for line in iter(process.stderr.readline, ''):
            if line and not any(x in line for x in ["Unable to locate a Java", "visit http://www.java.com"]):
                print(line, end='', file=sys.stderr)
        
        process.wait()
    except KeyboardInterrupt:
        print()
        print_warning("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        print_error(f"Failed to run application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
