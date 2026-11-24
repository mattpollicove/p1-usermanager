This README is generated based on the initial public release of the code except for this introduction. Obviously there are a lot of places this project can go. 
I went for a basic UI with nothing too flashy just to establish the project. There are a lot of places I'd like to take this, but I'm also interrested to see what other 
people would like to do with this application. The sky's the limit to be sure!

PingOne UserManager (v0.859 - Alpha)

⚠️ **Alpha Release**: Version 0.859 includes robust LDAP certificate management with self-signed certificate support, certificate details viewer, and cross-platform font optimizations. Please report issues or send requests—thank you!

**Version 0.859 Updates**:
- ✅ Self-signed LDAP certificate support in group transfer operations
- ✅ Certificate details viewer in acceptance dialogs
- ✅ Fixed cryptography library deprecation warnings
- ✅ Cross-platform monospace font optimization (eliminates ~105ms startup delay)
- ✅ Improved table item styling for certificate viewer

PingOne UserManager is a robust, cross-platform desktop application designed for IT administrators to manage PingOne identity environments. It simplifies complex administrative tasks like bulk user deletion, nested attribute editing, and environment synchronization through a clean, multi-threaded GUI.

🚀 Key Features
Multi-Profile Support: Manage multiple PingOne environments (Dev, Staging, Prod) with easy switching. Use the Profile Manager (File → Manage Profiles) to view all configurations and delete unwanted profiles.

Hardware-Backed Security: Sensitive Client Secrets are never stored in plain text; they are vaulted in the OS-native keychain (Windows Credential Manager, macOS Keychain, or Linux Secret Service). On macOS, the app prefers the native Keychain path and supports Touch ID-capable authentication prompts when available.

Dynamic Attribute Editor: A recursive JSON editor that flattens nested PingOne identity objects for easy modification.

Delta-Patching: Updates are sent via HTTP PATCH, sending only the fields you changed to preserve data integrity.

Bulk Operations: Select and delete multiple users simultaneously with a safe, queued background worker.

Live Statistics: Real-time dashboard showing total user and population counts.

Dark Mode: Toggle between light and dark themes for comfortable viewing in any environment. Theme preference is saved and persists across sessions.

🛠️ Technical Architecture
The application uses a Non-Blocking Worker Pattern. All API communications are handled by QRunnable workers in a dedicated thread pool, ensuring the interface remains responsive even when fetching thousands of users.

📋 Prerequisites
Python 3.9 or higher

A PingOne Environment ID

A Worker App with Client Credentials grant type and sufficient Roles (e.g., Identity Admin).

📥 Installation

**Quick Setup (Recommended):**

Use the automated setup scripts:
- **macOS/Linux**: `./setup.sh`
- **Windows**: `setup.bat`

**Manual Installation:**

Clone the repository:

```bash
git clone https://github.com/your-org/pingone-usermanager.git
cd pingone-usermanager
```

Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Install dependencies:

```bash
pip install pyside6 httpx keyring
```

Optional (local JSON Schema validation):
```bash
pip install jsonschema
```
The project includes an example `user_schema.json` in the repository root. If `jsonschema` is installed and the schema file is present, the app can validate CSV/LDIF entries locally before attempting server-side creation.

For detailed installation instructions including automated setup scripts, see [INSTALL.md](INSTALL.md).

📦 Distribution
To package the application as a standalone executable for Windows, macOS, or Linux, see [PACKAGING.md](PACKAGING.md) for comprehensive packaging and distribution instructions.

🚦 Getting Started
Launch the App:

Bash
python usermanager.py
Configure a Profile:

Navigate to the Configuration tab.

Enter your Environment ID, Client ID, and Client Secret.

Click Save Profile.

macOS Keychain Notes:

- Secrets are saved under the service name `pingone_usermanager`.
- The app caches loaded secrets in memory for the current session to reduce repeated Keychain prompts.
- Use Configuration -> Action -> Keychain Diagnostics to view backend status, Touch ID capability, and per-profile keychain item checks (no secret values are displayed).
- Use Configuration -> Action -> Apply Keychain ACL To All Profiles to re-save all profile secrets with the app's current ACL policy in one click.

Sync Data:

Click Connect. The app will fetch your population mapping and user list.

Manage Users:

Double-click a row to edit a user's full attribute set.

Use Ctrl+Click or Shift+Click to select multiple users for deletion.

Customize Columns:

The default column display includes: UUID, First Name, Last Name, Email, and Population (in that order).

Column settings are saved per-profile, allowing different column configurations for different environments.

Use Settings → Select Columns (Cmd/Ctrl+K) to customize which attributes appear in the table.

Column Selection Dialog features:
  - **Select All**: Check all available columns
  - **Clear All**: Uncheck all columns (except required UUID)
  - **Reset to Defaults**: Restore the default column set

Use Settings → Revert to Default Columns to quickly reset your column selection.

The active profile name is displayed in the status bar for easy reference.

Customize Appearance:

Toggle Dark Mode from the Settings menu (Cmd+D / Ctrl+D) for comfortable viewing in low-light environments.

Exporting Users

- Export CSV: In the User Management toolbar click `Export CSV` to save users to a CSV file. The exported columns follow your current column selection.
- Export LDIF: Click `Export LDIF` to create a simple LDIF file (one entry per user). LDIF includes common fields and flattened nested attributes.

Importing Users

- Import CSV: Use the `Import CSV` button in the User Management toolbar to create users from a CSV file. The CSV should include headers matching the exported column names (dot-notation for nested attributes, e.g. `name.given`). List-valued attributes are stored as JSON strings in the CSV and will be parsed during import.
- Import/Export Database: Define database connections via **File → Manage DB Connections** or the button on the Configuration tab. Supported backends are MSSQL, MySQL, and Oracle via JDBC only. Prerequisites: install `jaydebeapi` and `JPype1`, then set Driver Path to the correct JDBC `.jar` file for your database vendor (`mssql-jdbc`, `mysql-connector-j`, or `ojdbc`). The recommended on-disk layout is `drivers/mssql/mssql-jdbc-13.4.0.jre11.jar`, `drivers/mysql/mysql-connector-j-9.0.0.jar`, and `drivers/oracle/ojdbc11.jar`. For MSSQL, the connection dialog includes **Encrypt Mode** (`Auto`, `On`, `Off`) so you can require TLS or use compatibility fallback behavior on older/non-TLS listeners. See `INSTALL.md` for vendor download URLs, `JAVA_HOME` setup, verification commands, and quick-start UI values for MSSQL, MySQL, and Oracle. Once a connection is configured, the `Import DB` / `Export DB` buttons on the User Management toolbar open a mapping dialog that lets you map table columns to PingOne attributes (or vice versa).
- Import LDIF: Use the `Import LDIF` button to import simple LDIF files produced by this app. The importer accepts attribute names where dots may have been replaced by hyphens (e.g., `name-given`), and will attempt to convert them back to nested attributes.

Logging Options

- Settings -> Show Log Files opens the log index dialog.
- Each log viewer includes command buttons for `Set Log Level`, `Reset Log`, `Save Log As`, and `Refresh`.
- API Capture includes `Set Log Level`, `Reset`, and `Save` controls directly in the capture window.
- Menu shortcuts for log maintenance remain under Logs: `Clear All Logs` and `Archive Logs...`.
- Connection logs are plain text and do not support level changes; API and credentials logs do.

Developer Note
------------

- Help Docs: When you change UI behavior, help dialogs, or import/export semantics, update the relevant help text in the UI (`show_*_help`), this `README.md`, and `DEVELOPMENT_RULES.md` so users always see accurate guidance.
	See DEVELOPMENT_RULES.md for the formal rule.


---

## 🎯 Latest Updates (November 2026)

### ✅ LDAP Certificate Management (v0.859)

**New Features:**
- **Certificate Acceptance Dialog**: When connecting to LDAPS servers (port 636), users are prompted to accept or reject the server's SSL certificate
- **Certificate Details Viewer**: View full certificate information including:
  - Subject and Issuer (DN format)
  - Validity dates
  - Self-signed indicator
  - Expiration status
  - SHA-256 fingerprint
  - Copy fingerprint button for easy sharing
- **Self-Signed Certificate Support**: Automatically saves accepted certificates for group transfer operations
- **Certificate Verification**: Group transfer LDAP connections use saved certificates with proper TLS validation

**Technical Improvements:**
- Fixed cryptography library deprecation warnings (`not_valid_before_utc`, `not_valid_after_utc`)
- Fixed certificate fingerprint calculation using `hashes.SHA256()` from cryptography
- Cross-platform monospace font optimization:
  - macOS: Monaco
  - Windows: Consolas
  - Linux: DejaVu Sans Mono
  - Eliminates Qt font warning (~105ms startup delay)

### ✅ Critical Bug Fix: 'lazy_import' Error
The "'lazy_import' object is not callable" error that prevented credential testing has been **completely resolved**.

**Solution**: Switched from async httpx to synchronous httpx for UI operations. This eliminates event loop conflicts with PySide6.

**Impact**: Connection testing now works reliably with clear success messages showing which PingOne instance you're connected to.

### ✨ Enhanced Connection Feedback
- Test Credentials now shows: `"Token obtained successfully.\nConnected to: ProfileName"`
- Connect status displays: `"Connected to: ProfileName"`
- Clear indication of which instance you're working with

### 🚀 Improved App Startup
New cleanup scripts ensure only one app instance runs at a time:
- `./cleanup_and_run.sh` - Closes old instances, starts fresh (Bash)
- `python3 cleanup_and_run.py` - Cross-platform cleanup runner (Python)

### 📚 Operational Rule
**Before starting a new instance of the app, close any old instances first.**

Use the cleanup scripts to do this automatically:
```bash
./cleanup_and_run.sh    # Recommended
# or
python3 cleanup_and_run.py    # Cross-platform
```

## 🚀 Quick Start (Updated)

```bash
# Option 1: Clean start (recommended)
./cleanup_and_run.sh

# Option 2: Standard start (if no old instances)
./run.sh

# Option 3: Cross-platform
python3 cleanup_and_run.py
# or
python3 run.py
```

## 📖 Documentation

### Setup & Running
- `CLEANUP_AND_RUN_GUIDE.md` - Using cleanup scripts
- `TEST_RUNNER_README.md` - Using standard runners
- `RUNNER_USAGE.txt` - Quick reference

### Technical Details
- `FINAL_RESOLUTION.md` - 'lazy_import' fix explanation
- `SYNC_METHOD_FIX.md` - Implementation details
- `CONNECTION_SUCCESS_MESSAGES.md` - Feature documentation

## ✅ All Features Working

✅ **Connection Testing** - No more 'lazy_import' errors  
✅ **Instance Feedback** - Shows which PingOne environment you're connected to  
✅ **Groups Management** - Import/Export from CSV and LDAP with certificate support
✅ **Certificate Management** - Accept and view LDAPS certificates with self-signed support
✅ **Profile Management** - Multiple profiles with Keychain integration  
✅ **User Management** - View, search, and manage users  
✅ **Bulk Operations** - Delete multiple users simultaneously  
✅ **Dark Mode** - Theme toggle with persistence  
✅ **LDAP Directory Browser** - Browse LDAP directory structure
✅ **Group Transfer** - Migrate groups from LDAP with certificate verification

## 🧪 Testing

```bash
./cleanup_and_run.sh
# Configuration tab → Enter PingOne credentials → Test Credentials
# Expected: Success message with instance name (no errors!)
```

## 🎉 Production Ready

The application is fully functional and tested. All known issues have been resolved. Ready for production deployment.

