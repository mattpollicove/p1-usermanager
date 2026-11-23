#!/bin/bash
# Cleanup and restart the PingOne User Manager app
# This script kills any running instances before starting a fresh one

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/venv"
PYTHON="$VENV_PATH/bin/python3"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   PingOne User Manager - Clean Start   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo

# Check for running instances
echo -e "${BLUE}Checking for running instances...${NC}"
RUNNING_PIDS=$(ps aux | grep "python3 app.py" | grep -v grep | awk '{print $2}')

if [ -n "$RUNNING_PIDS" ]; then
    echo -e "${YELLOW}Found running instances:${NC}"
    ps aux | grep "python3 app.py" | grep -v grep | awk '{print "  PID " $2 " (started " $9 " " $10 ")"}'
    echo
    echo -e "${YELLOW}Terminating old instances...${NC}"
    
    for PID in $RUNNING_PIDS; do
        echo "  Killing PID $PID..."
        kill -9 "$PID" 2>/dev/null || true
    done
    
    sleep 1
    echo -e "${GREEN}✓ Old instances terminated${NC}"
else
    echo -e "${GREEN}✓ No running instances found${NC}"
fi

echo

# Now run the app using run.sh
echo -e "${BLUE}Starting fresh instance...${NC}"
exec "$SCRIPT_DIR/run.sh"
