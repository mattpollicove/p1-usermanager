#!/bin/bash

# PingOne UserManager Setup Script (Unix/macOS)
# This script sets up the development environment

set -e  # Exit on error

echo "==================================="
echo "PingOne UserManager Setup"
echo "==================================="
echo ""

# Check if Python 3.9+ is available
echo "Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
else
    echo "❌ Error: Python is not installed or not in PATH"
    echo "Please install Python 3.9 or higher from https://www.python.org/"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
MAJOR_VERSION=$(echo $PYTHON_VERSION | cut -d. -f1)
MINOR_VERSION=$(echo $PYTHON_VERSION | cut -d. -f2)

echo "Found Python $PYTHON_VERSION"

if [ "$MAJOR_VERSION" -lt 3 ] || ([ "$MAJOR_VERSION" -eq 3 ] && [ "$MINOR_VERSION" -lt 9 ]); then
    echo "❌ Error: Python 3.9 or higher is required"
    echo "Current version: $PYTHON_VERSION"
    exit 1
fi

echo "✓ Python version check passed"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    echo "⚠️  Virtual environment already exists"
    read -p "Do you want to recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf venv
        $PYTHON_CMD -m venv venv
        echo "✓ Virtual environment recreated"
    else
        echo "Using existing virtual environment"
    fi
else
    $PYTHON_CMD -m venv venv
    echo "✓ Virtual environment created"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "✓ pip upgraded"
echo ""

# Install dependencies
echo "Installing dependencies from requirements.txt..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "✓ Dependencies installed"
else
    echo "❌ Error: requirements.txt not found"
    exit 1
fi
echo ""

echo "==================================="
echo "✓ Setup completed successfully!"
echo "==================================="
echo ""
echo "To run the application:"
echo "  1. Activate the virtual environment:"
echo "     source venv/bin/activate"
echo "  2. Run the application:"
echo "     python app.py"
echo ""
echo "To deactivate the virtual environment when done:"
echo "  deactivate"
echo ""
