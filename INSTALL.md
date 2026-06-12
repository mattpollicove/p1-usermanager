# Installation Guide

This guide will help you install and set up PingOne UserManager on your system.

## Prerequisites

Before installing PingOne UserManager, ensure you have the following:

### System Requirements
- **Python**: Version 3.9 or higher
- **Operating System**: Windows, macOS, or Linux
- **Disk Space**: At least 500 MB for Python dependencies

### PingOne Requirements
- A PingOne Environment ID
- A Worker App with Client Credentials grant type
- Sufficient Roles (e.g., Identity Admin) assigned to the Worker App

## Installation Methods

### Method 1: Automated Setup (Recommended)

The easiest way to set up the application is using the provided setup scripts.

#### On macOS/Linux:
```bash
./setup.sh
```

#### On Windows:
```cmd
setup.bat
```

The setup script will:
1. Verify your Python version
2. Create a virtual environment
3. Upgrade pip to the latest version
4. Install all required dependencies

### Method 2: Manual Installation

If you prefer to install manually or need more control:

#### Step 1: Verify Python Installation

Check your Python version:
```bash
python --version
# or
python3 --version
```

Ensure it's Python 3.9 or higher.

#### Step 2: Clone the Repository

```bash
git clone https://github.com/your-org/pingone-usermanager.git
cd pingone-usermanager
```

#### Step 3: Create Virtual Environment

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

#### Step 4: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

The required packages are:
- `pyside6` - Qt framework for the GUI
- `httpx` - Async HTTP client for API calls
- `keyring` - Secure credential storage

#### Optional: Install JSON Schema Validation
```bash
pip install jsonschema
```

#### Optional: Database Import/Export (JDBC-only)

Database support in this app is JDBC-only for:
- MSSQL
- MySQL
- Oracle

Install Python JDBC bridge prerequisites:

```bash
pip install jaydebeapi JPype1
```

Then download the vendor JDBC jar and set **Driver Path** in the database connection dialog:

- MSSQL: [Microsoft JDBC Driver for SQL Server](https://learn.microsoft.com/en-us/sql/connect/jdbc/download-microsoft-jdbc-driver-for-sql-server)
- MySQL: [MySQL Connector/J](https://dev.mysql.com/downloads/connector/j/)
- Oracle: [Oracle JDBC Drivers (ojdbc)](https://www.oracle.com/database/technologies/appdev/jdbc-downloads.html)

Recommended jar filenames:
- MSSQL: `mssql-jdbc-13.4.0.jre11.jar`
- MySQL: `mysql-connector-j-9.0.0.jar`
- Oracle: `ojdbc11.jar`

Recommended project folder layout:

```text
p1-usermanager/
   drivers/
      mssql/
         mssql-jdbc-13.4.0.jre11.jar
      mysql/
         mysql-connector-j-9.0.0.jar
      oracle/
         ojdbc11.jar
```

Recommended Driver Path values in the app:
- MSSQL: `drivers/mssql/mssql-jdbc-13.4.0.jre11.jar`
- MySQL: `drivers/mysql/mysql-connector-j-9.0.0.jar`
- Oracle: `drivers/oracle/ojdbc11.jar`

macOS Java setup for JPype/JDBC:

Add this to `~/.zshrc` when Java is installed via Homebrew:

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk/libexec/openjdk.jdk/Contents/Home
export PATH="$JAVA_HOME/bin:$PATH"
```

Reload your shell:

```bash
source ~/.zshrc
```

Verify Java + JPype + jar access:

```bash
java -version
python3 -c "import jaydebeapi, jpype; print('jaydebeapi ok'); print('jpype ok')"
```

MSSQL jar load verification example:

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk/libexec/openjdk.jdk/Contents/Home
venv/bin/python -c "import jpype; jar='drivers/mssql/mssql-jdbc-13.4.0.jre11.jar'; jpype.startJVM(classpath=[jar]); print('jvm started with jar'); jpype.shutdownJVM()"
```

Quick-start values for the DB connection dialog:

**MSSQL**
- Type: `MSSQL`
- Encrypt Mode: `Auto` (recommended), `On` (require TLS), or `Off` (no TLS)
- Host: your SQL Server host or IP
- Port: `1433`
- Database: target SQL Server database name
- Driver Path: `drivers/mssql/mssql-jdbc-13.4.0.jre11.jar`
- Download URL: https://learn.microsoft.com/en-us/sql/connect/jdbc/download-microsoft-jdbc-driver-for-sql-server

**MySQL**
- Type: `MySQL`
- Host: your MySQL host or IP
- Port: `3306`
- Database: target MySQL database name
- Driver Path: `drivers/mysql/mysql-connector-j-9.0.0.jar`
- Download URL: https://dev.mysql.com/downloads/connector/j/

**Oracle**
- Type: `Oracle`
- Host: your Oracle host or IP
- Port: `1521`
- Database: Oracle service name
- Driver Path: `drivers/oracle/ojdbc11.jar`
- Download URL: https://www.oracle.com/database/technologies/appdev/jdbc-downloads.html

Notes:
- Use port `1433` for MSSQL, `3306` for MySQL, and `1521` for Oracle unless your environment uses custom ports.
- For Oracle, enter the service name in the **Database** field.
- For MSSQL, use the database name in the **Database** field and port `1433` unless your SQL Server uses a custom listener.
- MSSQL Encrypt Mode behavior:
   - `Auto`: secure-first (`encrypt=true;trustServerCertificate=true`) with one fallback retry to `encrypt=false` on TLS handshake errors.
   - `On`: secure-only; no fallback.
   - `Off`: disables TLS for environments that do not support encrypted SQL Server listener connections.

## Configuration

### First-Time Setup

1. Launch the application:
   ```bash
   python app.py
   ```

2. On first run, you'll be prompted to create a profile:
   - **Profile Name**: A friendly name (e.g., "Dev Environment")
   - **Environment ID**: Your PingOne Environment ID
   - **Client ID**: Your Worker App Client ID
   - **Client Secret**: Your Worker App Client Secret (stored securely in system keychain)
   - **Region**: Your PingOne region (e.g., NA, EU, ASIA)

3. Click "Save" to create your first profile.

### Managing Multiple Profiles

To manage multiple PingOne environments:
1. Go to **File → Manage Profiles**
2. Click "New Profile" to add additional environments
3. Switch between profiles using the dropdown in the main window

## Running the Application

### After Installation

1. **Activate the virtual environment** (if not already active):
   
   **macOS/Linux:**
   ```bash
   source venv/bin/activate
   ```
   
   **Windows:**
   ```cmd
   venv\Scripts\activate
   ```

2. **Run the application:**
   ```bash
   python app.py
   ```

3. **Deactivate when done:**
   ```bash
   deactivate
   ```

### Creating a Desktop Shortcut (Optional)

#### macOS
Create a simple shell script:
```bash
#!/bin/bash
cd /path/to/pingone-usermanager
source venv/bin/activate
python app.py
```
Save as `UserManager.command`, make it executable (`chmod +x UserManager.command`), and drag to your dock.

#### Windows
Create a batch file:
```cmd
@echo off
cd C:\path\to\pingone-usermanager
call venv\Scripts\activate
python app.py
```
Save as `UserManager.bat` and create a shortcut to it.

## Troubleshooting

### Common Issues

#### Python Not Found
**Error:** `python: command not found` or `python3: command not found`

**Solution:** Install Python from [python.org](https://www.python.org/) and ensure it's added to your PATH.

#### Permission Denied (macOS/Linux)
**Error:** `Permission denied` when running `./setup.sh`

**Solution:**
```bash
chmod +x setup.sh
./setup.sh
```

#### Virtual Environment Activation Issues (Windows)
**Error:** Script execution is disabled

**Solution:** Run PowerShell as Administrator and execute:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### Missing Dependencies
**Error:** `ModuleNotFoundError: No module named 'PySide6'`

**Solution:** Ensure your virtual environment is activated and reinstall dependencies:
```bash
pip install -r requirements.txt
```

#### Keyring Backend Issues (Linux)
**Error:** `No recommended backend was available`

**Solution:** Install a keyring backend:
```bash
# For GNOME/Ubuntu
sudo apt-get install gnome-keyring

# For KDE
sudo apt-get install kwalletmanager
```

#### API Connection Issues
**Error:** Connection errors or authentication failures

**Solution:**
1. Verify your PingOne credentials are correct
2. Check that your Worker App has the necessary roles
3. Ensure your firewall allows outbound HTTPS connections
4. Verify the correct region is selected

### Getting Help

If you encounter issues not covered here:
1. Check the [README.md](README.md) for additional information
2. Review the [CHANGELOG.md](CHANGELOG.md) for version-specific notes
3. Open an issue on the project repository

## Updating

To update to the latest version:

```bash
# Pull latest changes
git pull origin main

# Activate virtual environment
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Update dependencies
pip install -r requirements.txt --upgrade
```

## Uninstalling

To remove the application:

1. Deactivate the virtual environment if active:
   ```bash
   deactivate
   ```

2. Delete the project directory:
   ```bash
   rm -rf pingone-usermanager
   ```

3. Remove stored credentials from system keychain:
   - **macOS:** Open Keychain Access, search for "pingone", and delete entries
   - **Windows:** Open Credential Manager, search for "pingone", and remove entries
   - **Linux:** Use your distribution's credential manager

## Next Steps

After successful installation:
- Read the [README.md](README.md) for feature documentation
- Review [DEVELOPMENT_SPEC.md](DEVELOPMENT_SPEC.md) if you plan to contribute
- Configure your first profile and start managing users!
