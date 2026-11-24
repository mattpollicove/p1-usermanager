# Windows Batch Files for PingOne User Manager

This document describes the Windows batch file versions of the shell scripts used to run the PingOne User Manager application on Windows.

## Files

### `run.bat`
Activates the Python virtual environment and runs the application.

**Features:**
- Checks for and creates virtual environment if needed
- Verifies Python installation
- Checks for required dependencies (PySide6, httpx, sqlalchemy, ldap3, keyring)
- Installs missing packages automatically
- Runs the application (`app.py`)
- Deactivates virtual environment on exit

**Usage:**
```bash
run.bat
```

### `cleanup_and_run.bat`
Terminates any existing Python instances, then starts a fresh one.

**Features:**
- Detects running Python instances
- Terminates old instances forcefully
- Waits briefly for cleanup
- Calls `run.bat` to start fresh instance

**Usage:**
```bash
cleanup_and_run.bat
```

## Windows Compatibility

### ANSI Color Codes
The batch files use ANSI color codes for colored output. These work on:
- **Windows 10** Build 16257 and later (requires ANSI escape sequences enabled)
- **Windows 11** (enabled by default)

On older Windows versions or if colors don't appear:
- Output will still be readable (colors will be stripped)
- The scripts will function normally
- Consider enabling ANSI escape sequences if on Windows 10

### Python Virtual Environment
The batch files expect a virtual environment at `.\venv`
- Create with: `python -m venv venv`
- Automatically created by `run.bat` if missing
- Uses Windows-specific paths: `venv\Scripts\python.exe`

### Dependencies
Installs automatically via pip:
- **PySide6** - Qt GUI framework
- **httpx** - Async HTTP client
- **sqlalchemy** - Database ORM
- **ldap3** - LDAP library
- **keyring** - Credential storage

## Equivalent Shell Scripts

| Windows Batch | macOS/Linux Shell | Purpose |
|---------------|-------------------|---------|
| `run.bat` | `run.sh` | Setup and run application |
| `cleanup_and_run.bat` | `cleanup_and_run.sh` | Kill old instances and restart |

## Troubleshooting

### "Python not found"
- Ensure Python 3.11+ is installed and in PATH
- Run: `python --version`
- If not found, install from https://www.python.org

### "ANSI codes not working"
- On Windows 10, ensure build 16257+
- Try running: `reg add HKCU\Console /v VirtualTerminalLevel /t REG_DWORD /d 1`
- Restart terminal

### "Virtual environment error"
- Delete the `venv` folder
- Run `run.bat` to recreate it
- Let it rebuild automatically

### "Permission denied" on file execution
- Right-click `.bat` file → Properties → Unblock checkbox
- Or run PowerShell as Administrator:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

### "Module not found" error
- Run `run.bat` to install dependencies
- If specific module fails:
  ```bash
  python -m pip install <package_name>
  ```

## Advanced Usage

### Running from PowerShell
```powershell
# Run application
.\run.bat

# Clean restart
.\cleanup_and_run.bat
```

### Running from Command Prompt
```cmd
REM Run application
run.bat

REM Clean restart
cleanup_and_run.bat
```

### Running without color output (if issues)
Edit `.bat` file and change color codes to empty:
```batch
set "BLUE="
set "GREEN="
set "YELLOW="
set "RED="
set "NC="
```

## Technical Details

### Virtual Environment Activation
Windows batch uses: `call "%VENV_PATH%\Scripts\activate.bat"`

Equivalent to bash: `source "$VENV_PATH/bin/activate"`

### Process Termination
Windows batch uses: `taskkill /PID %%A /F`

Equivalent to bash: `kill -9 "$PID"`

### File Paths
Windows batch uses backslashes and handles:
- `%~dp0` - Script directory (with trailing backslash)
- `%VENV_PATH%` - Virtual environment directory
- `cd /d` - Change drive and directory

## Development Notes

The Windows batch files provide feature parity with their shell script counterparts:

1. **Virtual Environment Management** - Create, detect, and activate
2. **Dependency Checking** - Verify and install required packages
3. **Process Management** - Detect and terminate old instances
4. **User Feedback** - Colored status messages and progress indicators
5. **Error Handling** - Graceful fallbacks and error reporting

The color implementation uses ANSI escape sequences which are natively supported by modern Windows terminals.

## See Also

- [run.sh](run.sh) - Original shell script version
- [cleanup_and_run.sh](cleanup_and_run.sh) - Original shell script version
- [README.md](README.md) - Main project documentation
