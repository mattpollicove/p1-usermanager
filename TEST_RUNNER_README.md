# PingOne User Manager - Test Runner Scripts

This directory contains convenient scripts to run the PingOne User Manager application with automatic virtual environment setup and dependency checking.

## Quick Start

### Option 1: Bash Script (Recommended for macOS/Linux)

```bash
./run.sh
```

### Option 2: Python Script (Cross-platform)

```bash
python3 run.py
# or
./run.py
```

### Option 3: Manual Setup

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies (if needed)
pip install -r requirements.txt

# Run the app
python3 app.py
```

## What the Scripts Do

Both `run.sh` and `run.py` automatically:

1. ✓ Check if virtual environment exists
2. ✓ Create virtual environment if needed
3. ✓ Verify Python installation
4. ✓ Check for required dependencies:
   - PySide6 (GUI framework)
   - httpx (HTTP client)
   - sqlalchemy (Database ORM)
   - ldap3 (LDAP support)
   - keyring (Credential storage)
5. ✓ Install missing packages automatically
6. ✓ Launch the application

## Script Features

### Bash Script (`run.sh`)
- Colored output for easy reading
- Clear progress indicators
- Works on macOS and Linux
- Fast startup

### Python Script (`run.py`)
- Cross-platform (macOS, Linux, Windows)
- More detailed error reporting
- Can be imported as a module
- Explicit environment variable handling

## Directory Structure

```
p1-usermanager/
├── run.sh              ← Bash test runner
├── run.py              ← Python test runner
├── app.py              ← Main application
├── venv/               ← Virtual environment (auto-created)
├── ui/                 ← User interface modules
├── api/                ← API client modules
└── requirements.txt    ← Python dependencies (optional)
```

## Troubleshooting

### "Permission denied" on run.sh
Make sure the script is executable:
```bash
chmod +x run.sh
```

### Virtual environment issues
To reset the virtual environment:
```bash
rm -rf venv
./run.sh  # or python3 run.py
```

### Missing dependencies
The scripts will automatically attempt to install missing packages. If that fails, manually install:
```bash
source venv/bin/activate
pip install PySide6 httpx sqlalchemy ldap3 keyring
```

### macOS Keychain Integration
On macOS, the app integrates with the native Keychain. For the first connection:
1. Enter your PingOne credentials in the Configuration tab
2. Click "Save Profile" 
3. You'll be prompted to allow Keychain access
4. Grant permission when prompted

## Testing the Changes

The app now includes enhanced connection feedback:

### Test Credentials Flow
1. Enter your PingOne credentials
2. Click "Test Credentials" (Cmd+T)
3. **New**: Success message shows instance name: `"Token obtained successfully.\nConnected to: ProfileName"`

### Connect Flow
1. Select a profile
2. Click "Connect" (Cmd+C)
3. **New**: Status bar shows: `"Connected to ProfileName"`

## Environment Variables

You can customize behavior with environment variables:

```bash
# Enable detailed API logging
API_LOGGING_ENABLED=1 ./run.sh

# Enable credential logging
CREDENTIALS_LOGGING_ENABLED=1 python3 run.py
```

## Tips

- Use `Cmd+Q` to quit the application
- Use `Cmd+T` to test credentials
- Use `Cmd+C` to connect to PingOne
- Check the status bar at the bottom for connection state
- Use the Groups tab to manage group imports/exports

## Support

For issues or questions about running the app, check:
- `CONNECTION_SUCCESS_MESSAGES.md` - Latest feature enhancements
- `GROUPS_TAB_README.md` - Groups tab documentation
- `credentials.log` - Connection error details
- `api_calls.log` - API call history (if API logging enabled)
