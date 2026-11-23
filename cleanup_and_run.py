#!/usr/bin/env python3
"""
Clean Start Runner - Closes old instances before starting new one

Usage:
    python3 cleanup_and_run.py
    or
    ./cleanup_and_run.py
"""

import os
import sys
import subprocess
import signal
import time
from pathlib import Path

# ANSI color codes
RED = '\033[0;31m'
GREEN = '\033[0;32m'
BLUE = '\033[0;34m'
YELLOW = '\033[1;33m'
NC = '\033[0m'

def print_header():
    print(f"{BLUE}╔════════════════════════════════════════╗{NC}")
    print(f"{BLUE}║   PingOne User Manager - Clean Start   ║{NC}")
    print(f"{BLUE}╚════════════════════════════════════════╝{NC}")
    print()

def find_running_instances():
    """Find all running python app.py instances"""
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True
        )
        pids = []
        for line in result.stdout.split('\n'):
            if 'python3 app.py' in line and 'grep' not in line:
                parts = line.split()
                if len(parts) > 1:
                    pids.append(int(parts[1]))
        return pids
    except Exception:
        return []

def kill_process(pid):
    """Kill a process by PID"""
    try:
        os.kill(pid, signal.SIGKILL)
        return True
    except ProcessLookupError:
        return False
    except Exception as e:
        print(f"{RED}Error killing PID {pid}: {e}{NC}")
        return False

def get_process_info(pid):
    """Get process start time"""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "lstart="],
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"

def main():
    print_header()
    
    # Find running instances
    print(f"{BLUE}Checking for running instances...{NC}")
    pids = find_running_instances()
    
    if pids:
        print(f"{YELLOW}Found {len(pids)} running instance(s):{NC}")
        for pid in pids:
            start_time = get_process_info(pid)
            print(f"  {YELLOW}PID {pid}{NC} (started: {start_time})")
        
        print()
        print(f"{YELLOW}Terminating old instances...{NC}")
        
        killed = 0
        for pid in pids:
            if kill_process(pid):
                print(f"  {GREEN}✓ Killed PID {pid}{NC}")
                killed += 1
            else:
                print(f"  {RED}✗ Failed to kill PID {pid}{NC}")
        
        time.sleep(1)
        print(f"{GREEN}✓ Terminated {killed}/{len(pids)} instances{NC}")
    else:
        print(f"{GREEN}✓ No running instances found{NC}")
    
    print()
    
    # Now run run.py
    print(f"{BLUE}Starting fresh instance...{NC}")
    print()
    
    script_dir = Path(__file__).parent.resolve()
    run_script = script_dir / "run.py"
    
    try:
        subprocess.run([sys.executable, str(run_script)])
    except KeyboardInterrupt:
        print()
        print(f"{YELLOW}Application interrupted by user{NC}")
        sys.exit(0)
    except Exception as e:
        print(f"{RED}Error running app: {e}{NC}")
        sys.exit(1)

if __name__ == "__main__":
    main()
