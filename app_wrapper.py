#!/usr/bin/env python3
"""
Wrapper script to run app.py while suppressing Java Runtime warning from ldap3 on macOS.

This runs app.py and filters out the annoying "Unable to locate a Java Runtime" message
that appears on macOS even though the app works fine.
"""

import sys
import subprocess
import os

def run_app():
    """Run app.py while filtering Java Runtime warnings."""
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(script_dir, 'app.py')
    
    if not os.path.exists(app_path):
        print(f"Error: app.py not found at {app_path}", file=sys.stderr)
        sys.exit(1)
    
    # Launch app.py as subprocess to capture and filter output
    process = subprocess.Popen(
        [sys.executable, app_path],
        cwd=script_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1  # Line buffered
    )
    
    # Filter and forward output
    for line in iter(process.stdout.readline, ''):
        if line:
            # Skip Java Runtime warning lines
            if not any(keyword in line for keyword in [
                "Unable to locate a Java",
                "visit http://www.java.com",
                "The operation couldn't be completed"
            ]):
                sys.stdout.write(line)
                sys.stdout.flush()
    
    # Wait for process to complete and return its exit code
    return_code = process.wait()
    sys.exit(return_code)

if __name__ == '__main__':
    run_app()
