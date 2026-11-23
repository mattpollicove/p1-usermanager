# Clean Start Runner - Close Old Instances Before Running

## Overview

The `cleanup_and_run` scripts automatically kill any running instances of the app before starting a fresh one. This ensures:
- Only one instance runs at a time
- No port conflicts
- Clean resource management
- Fresh start with updated code

## Usage

### Option 1: Bash Script (macOS/Linux)

```bash
./cleanup_and_run.sh
```

**What it does:**
1. Checks for running `python3 app.py` instances
2. Terminates any found instances
3. Starts a fresh app using `run.sh`

### Option 2: Python Script (Cross-platform)

```bash
python3 cleanup_and_run.py
# or
./cleanup_and_run.py
```

**What it does:**
1. Uses `ps` to find running instances
2. Gets process start time for reference
3. Kills all old instances with SIGKILL
4. Waits 1 second for cleanup
5. Starts a fresh app using `run.py`

## When to Use

**Use `cleanup_and_run` when:**
- Making code changes and testing
- Restarting after an error
- Switching between profiles
- Testing different scenarios
- Redeploying updated code

**Use `run.sh`/`run.py` when:**
- Starting for the first time
- You know no other instances are running
- Quick restart of same instance

## Examples

### Full Workflow
```bash
# Make code changes
# Then start fresh:
./cleanup_and_run.sh

# App restarts with new code
# Test your changes
# Exit when done (Cmd+Q)
```

### Python Script
```bash
# Cross-platform approach
python3 cleanup_and_run.py

# App starts fresh
# Any old instances killed
```

### Bash Script
```bash
# macOS/Linux specific
./cleanup_and_run.sh

# Shows which instances were killed
# Starts fresh app
```

## Output Example

```
╔════════════════════════════════════════╗
║   PingOne User Manager - Clean Start   ║
╚════════════════════════════════════════╝

Checking for running instances...
Found 2 running instance(s):
  PID 12345 (started: Sun Nov 23 12:00:00 2026)
  PID 12346 (started: Sun Nov 23 12:05:00 2026)

Terminating old instances...
  ✓ Killed PID 12345
  ✓ Killed PID 12346

✓ Terminated 2/2 instances

Starting fresh instance...
✓ Virtual environment found
✓ Python executable: venv/bin/python3
✓ All dependencies installed

╔════════════════════════════════════════╗
║      Starting Application...          ║
╚════════════════════════════════════════╝
```

## Operational Guidelines

Going forward, follow this rule:

1. **Before starting the app:** Check if old instances exist
2. **If old instances exist:** Use cleanup script to close them
3. **Then start fresh:** New instance launches with clean state

This applies when:
- Testing new features
- Debugging issues
- Deploying changes
- Switching between profiles
- After crashes or errors

## Files Provided

1. **cleanup_and_run.sh** (Bash)
   - For macOS and Linux
   - Colored output
   - Shows old instance PIDs
   - Clean termination and restart

2. **cleanup_and_run.py** (Python)
   - Cross-platform (macOS, Linux, Windows)
   - Detailed process information
   - Better error handling
   - Integrates with run.py

## Technical Details

### Process Finding
- Uses `ps aux` command
- Filters for `python3 app.py`
- Excludes grep command itself
- Extracts PID from process list

### Termination
- Uses SIGKILL (-9) for immediate termination
- Waits 1 second for cleanup
- Handles errors gracefully
- Counts successful kills

### Restart
- Calls the standard `run.sh` or `run.py`
- Ensures venv is properly activated
- Verifies dependencies
- Shows progress during startup

## Troubleshooting

### "No running instances found"
- This is fine, app will just start fresh
- Happens on first run

### Script doesn't have execute permission
```bash
chmod +x cleanup_and_run.sh
chmod +x cleanup_and_run.py
```

### Permission denied killing old instance
- May need elevated permissions
- Usually not required for your own processes
- Try running with `sudo` if necessary:
```bash
sudo ./cleanup_and_run.sh
```

### Old instance still running after cleanup
- Might be blocked by OS
- Try manual kill:
```bash
ps aux | grep "python3 app.py"
kill -9 <PID>
```

## Best Practices

✅ **DO:**
- Use cleanup scripts when making changes
- Kill old instances before testing
- Let scripts handle the cleanup
- Check output to confirm termination

❌ **DON'T:**
- Let multiple instances run simultaneously
- Ignore old processes
- Force kill without cleanup
- Restart without closing first

## Future Automation

The cleanup behavior could be automated further:

1. Auto-detect old instances on startup
2. Ask user before killing
3. Save state before terminating
4. Log all kills with timestamps

For now, explicit cleanup scripts provide:
- Clear visibility of what's happening
- Control over when cleanup occurs
- Safety (doesn't kill unexpected processes)
