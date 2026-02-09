# Packaging Guide

This guide explains how to package PingOne UserManager as a standalone application for Windows, macOS, and Linux distribution.

## Overview

Packaging creates a standalone executable that includes Python, all dependencies, and the application code. End users can run the application without installing Python or dependencies.

## Prerequisites

Before packaging, ensure you have:
- A working development environment (see [INSTALL.md](INSTALL.md))
- The application running successfully from source
- Sufficient disk space (~500 MB per platform)

## Packaging Tool

We use **PyInstaller** for creating standalone executables across all platforms. PyInstaller bundles Python, your code, and dependencies into a single package.

### Installing PyInstaller

Activate your virtual environment and install PyInstaller:

```bash
# Activate virtual environment first
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Install PyInstaller
pip install pyinstaller
```

## Platform-Specific Instructions

### Windows Packaging

Package on a Windows machine to create Windows executables.

#### Step 1: Basic Packaging

```cmd
pyinstaller --name="PingOne UserManager" ^
            --windowed ^
            --onefile ^
            --icon=icon.ico ^
            app.py
```

**Options explained:**
- `--name`: Application name
- `--windowed`: No console window (GUI only)
- `--onefile`: Single executable file
- `--icon`: Application icon (optional, .ico format)

#### Step 2: Advanced Packaging (Recommended)

Create a spec file for more control:

```cmd
pyi-makespec --name="PingOne UserManager" ^
             --windowed ^
             --onefile ^
             app.py
```

Edit the generated `PingOne UserManager.spec` file to add hidden imports:

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('user_schema.json', '.'),
        ('profiles.json', '.'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'httpx',
        'keyring.backends',
        'keyring.backends.Windows',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PingOne UserManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico'
)
```

Build using the spec file:

```cmd
pyinstaller "PingOne UserManager.spec"
```

#### Step 3: Create Installer (Optional)

Use **Inno Setup** to create a professional installer:

1. Download and install [Inno Setup](https://jrsoftware.org/isinfo.php)
2. Create an installer script (`setup.iss`):

```ini
[Setup]
AppName=PingOne UserManager
AppVersion=0.6
DefaultDirName={pf}\PingOne UserManager
DefaultGroupName=PingOne UserManager
OutputDir=installer
OutputBaseFilename=PingOneUserManager-Setup
Compression=lzma2
SolidCompression=yes

[Files]
Source: "dist\PingOne UserManager.exe"; DestDir: "{app}"

[Icons]
Name: "{group}\PingOne UserManager"; Filename: "{app}\PingOne UserManager.exe"
Name: "{commondesktop}\PingOne UserManager"; Filename: "{app}\PingOne UserManager.exe"
```

3. Compile with Inno Setup Compiler

**Output:** `dist\PingOne UserManager.exe` (~50-100 MB)

---

### macOS Packaging

Package on a Mac to create macOS application bundles.

#### Step 1: Basic Packaging

```bash
pyinstaller --name="PingOne UserManager" \
            --windowed \
            --onefile \
            --icon=icon.icns \
            app.py
```

**Note:** macOS icons use `.icns` format. Convert PNG to ICNS:
```bash
# Install iconutil is built-in on macOS
mkdir icon.iconset
# Add icon files (16x16, 32x32, 128x128, 256x256, 512x512, 1024x1024)
iconutil -c icns icon.iconset
```

#### Step 2: Advanced Packaging with Spec File

```bash
pyi-makespec --name="PingOne UserManager" \
             --windowed \
             --onefile \
             app.py
```

Edit `PingOne UserManager.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('user_schema.json', '.'),
        ('profiles.json', '.'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'httpx',
        'keyring.backends',
        'keyring.backends.macOS',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PingOne UserManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name='PingOne UserManager.app',
    icon='icon.icns',
    bundle_identifier='com.pingidentity.usermanager',
    info_plist={
        'CFBundleShortVersionString': '0.6',
        'CFBundleVersion': '0.6',
        'NSHighResolutionCapable': 'True',
        'NSRequiresAquaSystemAppearance': 'False',
    },
)
```

Build:

```bash
pyinstaller "PingOne UserManager.spec"
```

#### Step 3: Code Signing (Recommended)

For distribution outside the App Store, sign your app:

```bash
# Get your Developer ID
security find-identity -v -p codesigning

# Sign the app
codesign --deep --force --verify --verbose \
         --sign "Developer ID Application: Your Name" \
         "dist/PingOne UserManager.app"

# Verify signature
codesign --verify --deep --strict --verbose=2 \
         "dist/PingOne UserManager.app"
spctl -a -t exec -vv "dist/PingOne UserManager.app"
```

#### Step 4: Create DMG (Optional)

Create a distributable disk image:

```bash
# Install create-dmg
brew install create-dmg

# Create DMG
create-dmg \
  --volname "PingOne UserManager" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "PingOne UserManager.app" 175 120 \
  --hide-extension "PingOne UserManager.app" \
  --app-drop-link 425 120 \
  "PingOne-UserManager-0.6.dmg" \
  "dist/PingOne UserManager.app"
```

**Output:** `dist/PingOne UserManager.app` (~60-120 MB)

---

### Linux Packaging

Package on Linux to create Linux executables.

#### Step 1: Basic Packaging

```bash
pyinstaller --name="pingone-usermanager" \
            --windowed \
            --onefile \
            app.py
```

#### Step 2: Advanced Packaging with Spec File

```bash
pyi-makespec --name="pingone-usermanager" \
             --windowed \
             --onefile \
             app.py
```

Edit `pingone-usermanager.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('user_schema.json', '.'),
        ('profiles.json', '.'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'httpx',
        'keyring.backends',
        'keyring.backends.SecretService',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='pingone-usermanager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

Build:

```bash
pyinstaller pingone-usermanager.spec
```

#### Step 3: Create AppImage (Optional)

Create a portable AppImage:

1. Install `appimagetool`:
```bash
wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool-x86_64.AppImage
```

2. Create AppDir structure:
```bash
mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/share/applications
mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps

cp dist/pingone-usermanager AppDir/usr/bin/
```

3. Create desktop file (`AppDir/usr/share/applications/pingone-usermanager.desktop`):
```ini
[Desktop Entry]
Type=Application
Name=PingOne UserManager
Comment=Manage PingOne identity environments
Exec=pingone-usermanager
Icon=pingone-usermanager
Categories=Utility;System;
```

4. Build AppImage:
```bash
./appimagetool-x86_64.AppImage AppDir
```

#### Step 4: Create DEB Package (Debian/Ubuntu)

Create a `.deb` package structure:

```bash
mkdir -p pingone-usermanager_0.6/DEBIAN
mkdir -p pingone-usermanager_0.6/usr/bin
mkdir -p pingone-usermanager_0.6/usr/share/applications
mkdir -p pingone-usermanager_0.6/usr/share/icons

# Copy executable
cp dist/pingone-usermanager pingone-usermanager_0.6/usr/bin/

# Create control file
cat > pingone-usermanager_0.6/DEBIAN/control << EOF
Package: pingone-usermanager
Version: 0.6
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Your Name <your.email@example.com>
Description: PingOne UserManager
 Desktop application for managing PingOne identity environments
EOF

# Build package
dpkg-deb --build pingone-usermanager_0.6
```

**Output:** `dist/pingone-usermanager` (~60-120 MB)

---

## Common Packaging Issues

### Issue: Missing Modules

**Error:** `ModuleNotFoundError` when running packaged app

**Solution:** Add hidden imports to spec file:
```python
hiddenimports=[
    'module_name',
    'package.submodule',
],
```

### Issue: Data Files Missing

**Error:** Application can't find `user_schema.json` or other data files

**Solution:** Add to `datas` in spec file:
```python
datas=[
    ('user_schema.json', '.'),
    ('profiles.json', '.'),
],
```

### Issue: Large File Size

**Problem:** Executable is too large

**Solutions:**
1. Use `--exclude-module` to remove unused packages
2. Enable UPX compression: `upx=True`
3. Use one-folder mode instead of one-file: remove `--onefile`

### Issue: Slow Startup

**Problem:** Application takes long to start

**Solution:** Use one-folder mode instead of one-file distribution. One-file extracts to temp directory on each run.

### Issue: Antivirus False Positives

**Problem:** Windows Defender flags the executable

**Solutions:**
1. Code sign your executable
2. Submit to Microsoft for analysis
3. Use one-folder mode instead of one-file
4. Exclude PyInstaller bootloader with `--exclude-module`

## Testing Packaged Applications

### Windows Testing

1. Test on clean Windows VM without Python installed
2. Verify keyring integration with Windows Credential Manager
3. Test on Windows 10 and Windows 11
4. Check UAC prompts and permissions

### macOS Testing

1. Test on different macOS versions (10.15+)
2. Verify Keychain integration
3. Test on both Intel and Apple Silicon (M1/M2) if possible
4. Check for Gatekeeper warnings

### Linux Testing

1. Test on multiple distributions (Ubuntu, Fedora, Debian)
2. Verify Secret Service integration
3. Test with different desktop environments (GNOME, KDE)
4. Check dependencies with `ldd dist/pingone-usermanager`

## Distribution Checklist

Before distributing your packaged application:

- [ ] Test on clean system without Python
- [ ] Verify all features work (API calls, keyring, file operations)
- [ ] Check file size is reasonable
- [ ] Include README or user guide
- [ ] Add license file
- [ ] Code sign (macOS/Windows)
- [ ] Create installer/package for platform
- [ ] Test installation and uninstallation
- [ ] Document system requirements
- [ ] Create release notes

## Continuous Integration

Automate packaging with GitHub Actions:

```yaml
name: Build Releases

on:
  release:
    types: [created]

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt pyinstaller
      - run: pyinstaller "PingOne UserManager.spec"
      - uses: actions/upload-artifact@v3
        with:
          name: windows-build
          path: dist/PingOne UserManager.exe

  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt pyinstaller
      - run: pyinstaller "PingOne UserManager.spec"
      - run: ditto -c -k --sequesterRsrc --keepParent "dist/PingOne UserManager.app" "dist/PingOne-UserManager-macOS.zip"
      - uses: actions/upload-artifact@v3
        with:
          name: macos-build
          path: dist/PingOne-UserManager-macOS.zip

  build-linux:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt pyinstaller
      - run: pyinstaller pingone-usermanager.spec
      - uses: actions/upload-artifact@v3
        with:
          name: linux-build
          path: dist/pingone-usermanager
```

## Resources

- [PyInstaller Documentation](https://pyinstaller.org/en/stable/)
- [PySide6 Deployment Guide](https://doc.qt.io/qtforpython/deployment.html)
- [Inno Setup](https://jrsoftware.org/isinfo.php) (Windows installers)
- [create-dmg](https://github.com/sindresorhus/create-dmg) (macOS DMG creation)
- [AppImage Documentation](https://docs.appimage.org/) (Linux portable apps)

## Next Steps

After packaging:
- Review [INSTALL.md](INSTALL.md) for development setup
- Check [README.md](README.md) for feature documentation
- Update [CHANGELOG.md](CHANGELOG.md) with release notes
