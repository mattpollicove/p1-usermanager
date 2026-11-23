#!/bin/bash
# PingOne User Manager Test Runner
# This script activates the virtual environment and runs the application

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/venv"
PYTHON="$VENV_PATH/bin/python3"

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   PingOne User Manager - Test Runner   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo

# Check if venv exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${YELLOW}⚠ Virtual environment not found at $VENV_PATH${NC}"
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_PATH"
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Check if Python exists in venv
if [ ! -f "$PYTHON" ]; then
    echo -e "${YELLOW}⚠ Python not found in virtual environment${NC}"
    echo "Attempting to create venv..."
    python3 -m venv "$VENV_PATH"
fi

echo -e "${GREEN}✓ Virtual environment found${NC}"
echo "  Location: $VENV_PATH"
echo

# Source the venv
echo -e "${BLUE}Activating virtual environment...${NC}"
source "$VENV_PATH/bin/activate"
echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo

# Check Python version
PYTHON_VERSION=$("$PYTHON" --version)
echo "Python: $PYTHON_VERSION"
echo

# Check if required packages are installed
echo -e "${BLUE}Checking dependencies...${NC}"
REQUIRED_PACKAGES=(
    "PySide6"
    "httpx"
    "sqlalchemy"
    "ldap3"
    "keyring"
)

MISSING_PACKAGES=()
for package in "${REQUIRED_PACKAGES[@]}"; do
    # Convert package name to import name (replace hyphens with underscores)
    import_name="${package//-/_}"
    if "$PYTHON" -c "import $import_name" 2>/dev/null; then
        echo -e "${GREEN}✓ $package${NC}"
    else
        echo -e "${YELLOW}✗ $package (missing)${NC}"
        MISSING_PACKAGES+=("$package")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo
    echo -e "${YELLOW}Installing missing packages...${NC}"
    for package in "${MISSING_PACKAGES[@]}"; do
        echo "  Installing $package..."
        pip install -q "$package" 2>/dev/null || {
            echo -e "${YELLOW}Warning: Failed to install $package${NC}"
        }
    done
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${GREEN}✓ All dependencies installed${NC}"
fi

echo
echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      Starting Application...          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo

# Run the app
cd "$SCRIPT_DIR"
# Suppress Java Runtime warning from macOS system LDAP libraries by filtering stderr
# The warning appears during ldap3 operations but doesn't affect functionality
"$PYTHON" app.py 2>&1 | grep -v -e "Unable to locate a Java Runtime" -e "Please visit http://www.java.com" -e "The operation couldn't be completed" || true
