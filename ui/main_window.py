import json
import copy
from pathlib import Path
from datetime import datetime
import asyncio
import functools
import logging
import httpx
import zipfile
import shutil
import sys
import platform
import threading
import os
import tempfile
import subprocess
import time

# If this file is executed directly (e.g. via the editor), ensure the
# project root is on `sys.path` so local packages like `api` and `workers`
# can be imported using absolute imports.
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from PySide6 import QtWidgets, QtCore, QtGui

MACOS_LOCAL_AUTH_AVAILABLE = False
MACOS_LOCAL_AUTH_IMPORT_ERROR = ""
if platform.system() == 'Darwin':
    try:
        import LocalAuthentication  # type: ignore
        MACOS_LOCAL_AUTH_AVAILABLE = True
    except Exception as _local_auth_err:
        MACOS_LOCAL_AUTH_IMPORT_ERROR = str(_local_auth_err)

KEYRING_AVAILABLE = True
KEYRING_UNAVAILABLE_REASON = ""
KEYRING_BACKEND_NAME = "Unavailable"
KEYRING_TOUCH_ID_SUPPORTED = False

try:
    import keyring  # type: ignore
except Exception as _keyring_import_error:
    KEYRING_AVAILABLE = False
    KEYRING_UNAVAILABLE_REASON = str(_keyring_import_error)

    class _UnavailableKeyring:
        """Fallback keyring shim when backend initialization/import fails."""

        def _raise(self):
            raise RuntimeError(f"Keyring unavailable: {_keyring_import_error}")

        def get_password(self, *_args, **_kwargs):
            self._raise()

        def set_password(self, *_args, **_kwargs):
            self._raise()

        def delete_password(self, *_args, **_kwargs):
            self._raise()

    keyring = _UnavailableKeyring()

if KEYRING_AVAILABLE:
    try:
        _active_backend = keyring.get_keyring()
        KEYRING_BACKEND_NAME = f"{_active_backend.__class__.__module__}.{_active_backend.__class__.__name__}"
    except Exception:
        _active_backend = None

    # On macOS, prefer native Keychain backend so system authentication
    # (including Touch ID when enabled by the OS) is used instead of a
    # fallback encrypted-file vault prompt.
    if platform.system() == 'Darwin':
        try:
            backend_module = ""
            if _active_backend is not None:
                backend_module = _active_backend.__class__.__module__.lower()

            if "keyring.backends.macos" not in backend_module:
                from keyring.backends import macOS as _macos_keyring  # type: ignore

                keyring.set_keyring(_macos_keyring.Keyring())
                _active_backend = keyring.get_keyring()
                backend_module = _active_backend.__class__.__module__.lower()

            KEYRING_TOUCH_ID_SUPPORTED = "keyring.backends.macos" in backend_module
            KEYRING_BACKEND_NAME = f"{_active_backend.__class__.__module__}.{_active_backend.__class__.__name__}"
        except Exception as _macos_backend_error:
            KEYRING_TOUCH_ID_SUPPORTED = False
            if not KEYRING_UNAVAILABLE_REASON:
                KEYRING_UNAVAILABLE_REASON = (
                    f"Unable to initialize macOS Keychain backend: {_macos_backend_error}"
                )

import api.client as api_client
from workers import UserFetchWorker, BulkDeleteWorker, UserUpdateWorker, BulkCreateWorker, BulkUpdateWorker
from tps_tracker import TPSTracker
from ui.dialogs import (
    EditUserDialog,
    ColumnSelectDialog,
    JSONViewDialog,
    AttributeMappingDialog,
    ProfileManagerDialog,
    DatabaseConnectionDialog,
    DBConnectionsManager,
    LDAPConnectionDialog,
    LDAPConnectionsManager,
    DatabaseMappingDialog,
    LDAPMappingDialog,
)
from ui.themes import ThemeManager

# Platform detection for cross-platform UI optimization
IS_MACOS = platform.system() == 'Darwin'
IS_WINDOWS = platform.system() == 'Windows'
IS_LINUX = platform.system() == 'Linux'

if IS_MACOS and shutil.which("security"):
    # Native Keychain path can offer Touch ID based on OS settings.
    KEYRING_TOUCH_ID_SUPPORTED = True

# Platform-aware keyboard shortcut modifier
SHORTCUT_MODIFIER = QtCore.Qt.KeyboardModifier.ControlModifier
if IS_MACOS:
    SHORTCUT_MODIFIER = QtCore.Qt.KeyboardModifier.MetaModifier

"""Main application window and UI glue.

This module builds the Qt UI, handles user interactions, and wires
background workers to update the table. The MainWindow exposes helper
methods used by dialogs to perform updates and to surface connection
logs/errors to the user.
"""

APP_NAME = "PingOne UserManager"
APP_VERSION = "0.84"
DEFAULT_PINGONE_CONSOLE_URL = "https://console.pingone.com/"
KEYRING_SERVICE = "pingone_usermanager"
KEYCHAIN_ALLOW_ALL_APPS = True


# Predefined help texts to avoid reallocating large strings on each call.
# Reminder: Update the UI help texts (show_*_help and related strings)
# whenever you change features or behavior. See DEVELOPMENT_RULES.md
# for the project rule about keeping help docs in sync.
HELP_CONFIG = """
Configuration Tab Help:

Connecting to PingOne:

1. Obtain your PingOne Environment ID, Client ID, and Client Secret from the 
   PingOne admin console.

2. Select an existing profile or create a new one using the "Active Profile" dropdown.

3. Enter the Environment ID, Client ID, and Client Secret in the respective fields.
    The Client Secret is stored securely in your system keychain.

4. Click "Save Profile" to persist credentials and settings.
    (Alternatively, use "New Connection" to clear fields and enter a new profile.)

5. Click "Connect" to authenticate and fetch users from PingOne.

Profile Settings:
- Credentials (Env ID, Client ID, Secret) are saved per-profile.
- On macOS, the app prefers native Keychain access for Touch ID-capable prompts.
- Secret reads are cached in memory for the current app session to reduce repeat prompts.
- Column selection and order are saved per-profile.
- Import/export preferences are saved per-profile when "Remember" is checked.
- The last active profile can auto-connect on startup (see Preferences).

Keychain Actions (Configuration -> Action):
- Keychain Diagnostics: shows backend, Touch ID capability, fallback risk, cache state, and per-profile item checks.
- Apply Keychain ACL To All Profiles: one-click re-save to apply current ACL policy to all saved profile secrets.

Managing Profiles:
- Use File → Manage Profiles (Cmd/Ctrl+Shift+M) to view all saved profiles.
- The Profile Manager shows environment IDs, client IDs, and column counts.
- Delete unwanted profiles from the Profile Manager dialog.
- The currently active profile cannot be deleted; switch profiles first.

Database Import/Export:
- Use File → Manage DB Connections (or the button in Configuration tab) to define connections.
- Supported types: MSSQL, MySQL, and Oracle via JDBC only.
- Provide JDBC Driver Path (.jar file) for the selected database type.
- After defining a connection you can import or export data via the toolbar buttons on the User Management tab.
- Mapping dialogs support common aliases and core fields including middle name, employee type, and address targets.
- Mapping choices include custom PingOne attributes discovered from tenant user data.
- LDAP directories are also supported via Manage LDAP Connections.
- Use the Configuration action "Open PingOne Console" to launch the active environment in your browser.

Status Bar:
- Shows live API call summaries when "Show API calls in status bar" is enabled.
- Displays connection status and recent operation results.
- API call logging can be toggled from the Preferences dialog.
- Use Logs -> Show Log Files to open log viewers with in-window controls.

Preferences:
- Access via File → Preferences (Cmd/Ctrl+,) or the application menu on macOS.
- Contains all application settings and runtime options.
- Dark Mode: Toggle between light and dark themes (Cmd/Ctrl+D).
- Set PingOne Console URL: Configure the base console URL used by the
    "Open PingOne Console" action.
- Auto-connect: Automatically connect to the last working profile on startup.
- Theme preference is saved and restored on startup.
- Dark mode applies a comfortable color scheme for low-light environments.

See the User Management help for information about working with users.
"""

HELP_USER = """
User Management Tab Help:

Viewing Users:
- The table displays users with selected columns (UUID, username, name, etc.).
- Click "Refresh" to reload users from PingOne.
- Use "Columns" to select which attributes to display.
- Use "Hide Links" in the User Management toolbar to hide columns with names or values that begin with `{` or `http`.
- Column selection and order are saved per-profile.
- Use the filter box to live-search across all visible columns.

Editing Users:
- Double-click on the UUID or username to open the edit dialog.
- Single-click selects a row without opening the editor.
- Double-click on email addresses to open your email client.
- Double-click on JSON-formatted attributes (name, address, etc.) to view/edit in a separate window.
- The context menu (right-click) offers "Delete Selected" only.

Importing Users:
- Click "Import CSV" or "Import LDIF" to bulk-create or update users.
- The mapping dialog lets you map file headers to PingOne attributes:
  • Required fields: username, email, name.given, name.family
    • Common additional fields: name.middle (middle name), employeeType/type, and address fields
    • Address targets include: address.streetAddress, address.locality, address.region, address.postalCode, address.countryCode
    • Common source aliases auto-suggest to targets (examples):
        - middlename/middleinitial -> name.middle
        - employeetype/employmenttype -> employeeType
        - street/streetaddress/addressline1 -> address.streetAddress
        - city -> address.locality
        - state/province/region -> address.region
        - zip/zipcode/postalcode -> address.postalCode
        - country -> address.countryCode
  • The 'enabled' field is a dropdown (true/false)
  • You can assign a fixed population to all imported users
  • Check "Remember mapping for this profile" to save mappings
- Database import: first define a connection via File → Manage DB Connections or the Configuration tab button, then click "Import DB" on the User Management toolbar and follow the prompts to select a table and map its columns.
- LDAP import: define a directory in "Manage LDAP Connections", then use Import and select "LDAP Directory" to map LDAP attributes to PingOne attributes.
- Imported attributes not currently shown are automatically added to the grid columns after import.
- For DB imports/exports, you can save custom queries and mapping selections in DB connection settings; saved queries auto-reuse their saved mappings.
- LDAP mappings can also be saved per LDAP connection for reuse.
- During import preparation, PingOne attributes are refreshed from live user data so custom attributes defined in your PingOne tenant appear in mapping choices.
- Usernames are normalized (whitespace trimmed, case-insensitive comparison).
- If a username already exists on the server, the import updates that user instead of creating a duplicate.
- Local JSON Schema validation is performed if jsonschema is installed and user_schema.json exists.

Exporting Users:
- Click "Export CSV" or "Export LDIF" to save users.
- Choose to export all users or selected rows only.
- Choose to export all columns or only visible columns.
- Optionally require selected attributes to be populated; only users matching all selected populated-attribute filters are exported.
- Check "Remember these choices" to save export preferences per-profile.
- Database export: click "Export DB" on the toolbar (after defining a connection) to map PingOne attributes to target table columns; the table will be created if it does not already exist.
- Export mapping includes standard fields (for example name.middle, employeeType, and address fields) and custom attributes discovered from your PingOne data.
- LDAP export: choose "Export → LDAP Directory" and map PingOne attributes to LDAP attributes; entries are created or updated by DN.

Deleting Users:
- Select one or more rows and click "Delete Selected" or use the context menu.
- Press Delete (or Backspace on macOS) in the user table to delete the selected/current row.
- A confirmation dialog will appear before deletion.
- In the confirmation dialog (or Preferences), you can choose whether to always prompt before deleting.
- Progress is shown for bulk deletions.

Logging & Log Viewers:
- Logs -> Show Log Files opens the log index dialog.
- Each log viewer window provides command buttons: Set Log Level, Reset Log, Save Log As, and Refresh.
- API Capture window also includes Set Log Level, Reset, and Save controls.
- Use Logs -> Clear All Logs to truncate all known logs.
- Use Logs -> Archive Logs to create a timestamped .zip archive (with optional rotation).
- Connection log is plain-text and does not support log levels; API and credentials logs do.
"""


class MainWindow(QtWidgets.QMainWindow):
    """Main application window for PingOne UserManager.

    Responsibilities:
    - Build and manage the configuration and user-management tabs
    - Start background workers and update UI when they complete
    - Provide helper methods for dialogs to trigger API updates
    - Surface connection logs and toggle API logging at runtime
    """
    secret_read_completed = QtCore.Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - v{APP_VERSION}")
        
        # Initialize theme manager
        self.theme_manager = ThemeManager()
        
        # Set DPI-aware window size (not full screen) and center on screen
        try:
            screen = QtWidgets.QApplication.primaryScreen()
            if screen:
                screen_geometry = screen.availableGeometry()
                dpi_scale = screen.devicePixelRatio()
                
                # Calculate 75% of screen as the initial/target size
                initial_width = int(screen_geometry.width() * 0.75)
                initial_height = int(screen_geometry.height() * 0.75)
                
                # Set minimum size to be smaller than 75% to allow window to be 75% or less
                # Use 800x600 as base minimum, adjusted for DPI
                min_width = min(int(800 * max(1.0, dpi_scale * 0.8)), initial_width)
                min_height = min(int(600 * max(1.0, dpi_scale * 0.8)), initial_height)
                self.setMinimumSize(min_width, min_height)
                
                # Set initial size to 75% of screen and center the window
                self.resize(initial_width, initial_height)
                # Center the window on screen
                x = screen_geometry.x() + (screen_geometry.width() - initial_width) // 2
                y = screen_geometry.y() + (screen_geometry.height() - initial_height) // 2
                self.move(x, y)
            else:
                self.setMinimumSize(800, 600)
                self.resize(1200, 800)
        except Exception:
            self.setMinimumSize(800, 600)
            self.resize(1200, 800)
        
        self.threadpool = QtCore.QThreadPool()
        self.config_file, self.users_cache, self.pop_map = Path("profiles.json"), [], {}
        self.columns = []
        # Default column order: UUID, first name, last name, email, phone,
        # work telephone, title, population.
        # This matches the requested default and ensures the UUID is always visible
        # as the left-most column.
        self.default_columns = ['id', 'name.given', 'name.family', 'email', 'phoneNumbers', 'workTelephone', 'title', 'population.name']
        self.selected_columns = self.default_columns.copy()
        self.all_columns = set()
        self.json_editing_enabled = False
        self.use_friendly_names = True
        self.pingone_console_url = DEFAULT_PINGONE_CONSOLE_URL
        self._closing = False
        self.hide_raw_http_columns = True
        self.show_user_update_success = True
        self.prompt_before_delete = True
        self._pending_user_tab_refresh = False
        self._active_profile_name = ""
        self.column_widths = {}
        # Cache keyring secrets in-memory for this app session to avoid
        # repeated keychain unlock prompts when switching profiles.
        self._secret_cache = {}
        # Track profiles we've already attempted to read from keyring this
        # session so we do not repeatedly trigger macOS keychain prompts.
        self._secret_read_attempted = set()
        # Track secret reads currently running in background threads.
        self._secret_read_inflight = set()
        self.secret_read_completed.connect(self._on_secret_read_complete)
        self._open_log_windows = {}
        self.friendly_names = {
            'username': 'Username',
            'name.given': 'First Name',
            'name.family': 'Last Name',
            'email': 'Email',
            'mail': 'Mail',
            'phoneNumbers': 'Phone',
            'workTelephone': 'Work Telephone',
            'title': 'Title',
            'population.name': 'Population',
            'id': 'UUID',
            'name': 'Name',
            'address': 'Address',
        }
        self.init_ui()
        self.load_profiles_from_disk()
        self.load_theme_preference()
        self._show_keyring_startup_warning()
        self._show_java_startup_warning()
        # Don't restore geometry here - do it in showEvent after window is shown

    def _show_keyring_startup_warning(self):
        """Show a startup warning when keyring support is unavailable."""
        if IS_MACOS and self._macos_keychain_cli_available() and MACOS_LOCAL_AUTH_AVAILABLE:
            return
        if KEYRING_AVAILABLE and not (IS_MACOS and not KEYRING_TOUCH_ID_SUPPORTED):
            return

        if not KEYRING_AVAILABLE:
            msg = "Keyring unavailable: saved client secrets may not persist on this system."
        elif IS_MACOS and not MACOS_LOCAL_AUTH_AVAILABLE:
            msg = (
                "Touch ID prompt library unavailable. Install pyobjc LocalAuthentication support "
                "to enable explicit Touch ID prompts."
            )
        else:
            msg = (
                "Touch ID unavailable for credential vault prompts. "
                "Native macOS Keychain CLI was not detected; install/enable Command Line Tools."
            )

        try:
            self._set_processing_message(msg, 15000)
        except Exception:
            pass

    def _show_java_startup_warning(self):
        """Show startup warning when Java runtime for JDBC is not discoverable."""
        try:
            from api import db_utils
            status = db_utils.get_java_runtime_status()
        except Exception:
            return

        if bool(status.get('available', False)):
            return

        msg = status.get('message') or (
            "Java runtime unavailable: database import/export features may not work until Java is configured."
        )
        try:
            self._set_processing_message(msg, 20000)
        except Exception:
            pass

    def _profile_cache_keys(self, profile_name: str) -> list:
        """Return cache keys for a profile name (raw + normalized)."""
        raw = str(profile_name or "")
        normalized = raw.strip()
        keys = []
        if raw:
            keys.append(raw)
        if normalized and normalized not in keys:
            keys.append(normalized)
        return keys

    def _keyring_usernames(self, profile_name: str) -> list:
        """Return keyring username variants for backward compatibility."""
        names = []
        for base in self._profile_cache_keys(profile_name):
            if base and base not in names:
                names.append(base)
            suffixed = f"{base}_client_secret" if base else ""
            if suffixed and suffixed not in names:
                names.append(suffixed)
        return names

    def _preferred_keyring_username(self, profile_name: str) -> str:
        """Return canonical keyring username for new writes."""
        keys = self._profile_cache_keys(profile_name)
        if not keys:
            return ""
        # Prefer normalized profile name for stable storage.
        return keys[-1]

    def _macos_keychain_cli_available(self) -> bool:
        """Return True when native macOS Keychain CLI is available."""
        return IS_MACOS and bool(shutil.which("security"))

    def _read_secret_from_macos_keychain(self, profile_name: str) -> str:
        """Read secret from macOS Keychain using known profile key variants."""
        if not self._macos_keychain_cli_available():
            return ""

        for username in self._keyring_usernames(profile_name):
            try:
                proc = subprocess.run(
                    ["security", "find-generic-password", "-s", KEYRING_SERVICE, "-a", username, "-w"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc.returncode == 0:
                    secret = (proc.stdout or "").rstrip("\n")
                    if secret:
                        return secret
            except Exception:
                continue
        return ""

    def _request_touch_id_auth(self, reason: str = "Authenticate to access saved credentials") -> bool:
        """Prompt for Touch ID (or device owner auth) on macOS when available."""
        if not IS_MACOS:
            return True
        if not MACOS_LOCAL_AUTH_AVAILABLE:
            return False

        try:
            context = LocalAuthentication.LAContext.alloc().init()
            policy = LocalAuthentication.LAPolicyDeviceOwnerAuthenticationWithBiometrics
            can_eval, _ = context.canEvaluatePolicy_error_(policy, None)
            if not can_eval:
                policy = LocalAuthentication.LAPolicyDeviceOwnerAuthentication
                can_eval, _ = context.canEvaluatePolicy_error_(policy, None)
                if not can_eval:
                    return False

            outcome = {"ok": False}
            done = threading.Event()

            def _reply(success, _error):
                outcome["ok"] = bool(success)
                done.set()

            context.evaluatePolicy_localizedReason_reply_(policy, reason, _reply)

            deadline = time.monotonic() + 20.0
            while not done.is_set() and time.monotonic() < deadline:
                QtWidgets.QApplication.processEvents()
                done.wait(0.05)

            return bool(outcome.get("ok", False))
        except Exception:
            return False

    def _write_secret_to_macos_keychain(self, profile_name: str, secret: str) -> tuple:
        """Write secret to macOS Keychain and return ``(ok, error_message)``."""
        if not self._macos_keychain_cli_available():
            return False, "Native macOS Keychain CLI is unavailable."

        username = self._preferred_keyring_username(profile_name)
        if not username:
            return False, "Profile name is empty."

        cmd = ["security", "add-generic-password", "-U"]
        if KEYCHAIN_ALLOW_ALL_APPS:
            # Allow all applications to read this item without per-app ACL prompts.
            cmd.append("-A")
        cmd.extend(["-s", KEYRING_SERVICE, "-a", username, "-w", secret or ""])

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as e:
            return False, str(e)

        if proc.returncode == 0:
            return True, ""

        err = (proc.stderr or proc.stdout or "unknown error").strip()
        return False, err

    def _delete_secret_from_macos_keychain(self, profile_name: str):
        """Delete secret from macOS Keychain for known profile key variants."""
        if not self._macos_keychain_cli_available():
            return

        for username in self._keyring_usernames(profile_name):
            try:
                subprocess.run(
                    ["security", "delete-generic-password", "-s", KEYRING_SERVICE, "-a", username],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except Exception:
                pass

    def _read_secret_from_keyring(self, profile_name: str, require_touch_id: bool = False) -> str:
        """Read secret from keyring using known profile key variants."""
        if require_touch_id and IS_MACOS:
            if not self._request_touch_id_auth("Use Touch ID to unlock saved client secret"):
                return ""

        # Prefer native Keychain access on macOS for Touch ID-capable prompts.
        native_secret = self._read_secret_from_macos_keychain(profile_name)
        if native_secret:
            return native_secret

        # When native macOS keychain access is available, do not fall back to
        # alternate keyring backends that can prompt for a vault password
        # without Touch ID support.
        if self._macos_keychain_cli_available():
            return ""

        if not KEYRING_AVAILABLE:
            return ""
        for username in self._keyring_usernames(profile_name):
            try:
                secret = keyring.get_password(KEYRING_SERVICE, username) or ""
                if secret:
                    return secret
            except Exception:
                continue
        return ""

    def _write_secret_to_keyring(self, profile_name: str, secret: str):
        """Write secret to keyring under all profile key variants."""
        native_ok = False
        native_err = ""
        if self._macos_keychain_cli_available():
            native_ok, native_err = self._write_secret_to_macos_keychain(profile_name, secret)
            if native_ok:
                # Native keychain write succeeded; avoid secondary backend writes
                # that can trigger unrelated vault/keychain backend failures.
                return

        if not KEYRING_AVAILABLE:
            if native_err:
                raise RuntimeError(native_err)
            return

        username = self._preferred_keyring_username(profile_name)
        if not username:
            return

        try:
            keyring.set_password(KEYRING_SERVICE, username, secret or "")
        except Exception as e:
            if native_err:
                raise RuntimeError(f"Native keychain save failed: {native_err}; fallback save failed: {e}")
            raise

    def _delete_secret_from_keyring(self, profile_name: str):
        """Delete secret from keyring for all profile key variants."""
        self._delete_secret_from_macos_keychain(profile_name)

        if not KEYRING_AVAILABLE:
            return
        for username in self._keyring_usernames(profile_name):
            try:
                keyring.delete_password(KEYRING_SERVICE, username)
            except Exception:
                pass

    def _cache_secret(self, profile_name: str, secret: str):
        """Store secret in session cache under raw and normalized profile keys."""
        for key in self._profile_cache_keys(profile_name):
            self._secret_cache[key] = secret or ""

    def _mark_secret_read_attempted(self, profile_name: str):
        """Mark profile key variants as already read-attempted this session."""
        for key in self._profile_cache_keys(profile_name):
            self._secret_read_attempted.add(key)

    def _was_secret_read_attempted(self, profile_name: str) -> bool:
        """Return True if keyring read already attempted this session."""
        for key in self._profile_cache_keys(profile_name):
            if key in self._secret_read_attempted:
                return True
        return False

    def _get_cached_secret(self, profile_name: str):
        """Return cached secret if present for the profile name."""
        for key in self._profile_cache_keys(profile_name):
            if key in self._secret_cache:
                return self._secret_cache.get(key) or ""
        return None

    def _is_secret_read_inflight(self, profile_name: str) -> bool:
        """Return True when a secret read is currently running for a profile."""
        for key in self._profile_cache_keys(profile_name):
            if key in self._secret_read_inflight:
                return True
        return False

    def _start_secret_read(self, profile_name: str):
        """Load a profile secret from keyring in a background thread."""
        if not KEYRING_AVAILABLE:
            self._mark_secret_read_attempted(profile_name)
            return
        if self._was_secret_read_attempted(profile_name):
            return
        if self._is_secret_read_inflight(profile_name):
            return

        keys = self._profile_cache_keys(profile_name)
        for key in keys:
            self._secret_read_inflight.add(key)
        self._mark_secret_read_attempted(profile_name)

        def worker():
            secret = ""
            try:
                secret = self._read_secret_from_keyring(profile_name)
            except Exception:
                secret = ""
            finally:
                self.secret_read_completed.emit(profile_name, secret)

        threading.Thread(target=worker, daemon=True).start()

    def _on_secret_read_complete(self, profile_name: str, secret: str):
        """Apply secret read completion on the UI thread."""
        for key in self._profile_cache_keys(profile_name):
            self._secret_read_inflight.discard(key)

        if secret:
            self._cache_secret(profile_name, secret)

        if self.profile_list.currentText() == profile_name:
            # Keep user's manual entry if present; otherwise fill with loaded secret.
            if not self.cl_sec.text().strip():
                self.cl_sec.setText(secret or "")

    def _connect_when_secret_ready(self, profile_name: str, retries_left: int = 20):
        """Auto-connect after secret load (or timeout) without blocking the UI."""
        if self.profile_list.currentText() != profile_name:
            return

        if self.cl_sec.text().strip():
            self.connect_only(interactive=False)
            return

        cached_secret = self._get_cached_secret(profile_name)
        if cached_secret:
            self.cl_sec.setText(cached_secret)
            self.connect_only(interactive=False)
            return

        if self._is_secret_read_inflight(profile_name) and retries_left > 0:
            QtCore.QTimer.singleShot(250, lambda: self._connect_when_secret_ready(profile_name, retries_left - 1))
            return

        self.connect_only(interactive=False)

    def _clear_cached_secret(self, profile_name: str):
        """Remove any cached secret entries for the profile name."""
        for key in self._profile_cache_keys(profile_name):
            self._secret_cache.pop(key, None)
            self._secret_read_attempted.discard(key)
            self._secret_read_inflight.discard(key)

    def show_about_dialog(self):
        """Show application About information."""
        keyring_line = "Available" if KEYRING_AVAILABLE else "Unavailable"
        lines = [
            f"{APP_NAME} v{APP_VERSION}",
            "",
            "Desktop administration tool for PingOne environments.",
            "",
            "Highlights:",
            "- User management and bulk operations",
            "- Import/export for CSV, LDIF, database, and LDAP",
            "- Live API capture and log viewers",
            "",
            f"Keyring: {keyring_line}",
            f"Keyring Backend: {KEYRING_BACKEND_NAME}",
        ]
        if IS_MACOS:
            lines.append(
                f"Touch ID for Keychain Prompts: {'Enabled' if (KEYRING_TOUCH_ID_SUPPORTED or self._macos_keychain_cli_available()) else 'Unavailable'}"
            )
            lines.append(
                f"Explicit LocalAuthentication Prompt: {'Available' if MACOS_LOCAL_AUTH_AVAILABLE else 'Unavailable'}"
            )
        if not KEYRING_AVAILABLE:
            lines.append("Saved client secrets may not persist on this system.")
        elif IS_MACOS and not (KEYRING_TOUCH_ID_SUPPORTED or self._macos_keychain_cli_available()):
            lines.append("macOS Keychain backend not active; vault password prompts may be shown without Touch ID.")
        QtWidgets.QMessageBox.about(self, f"About {APP_NAME}", "\n".join(lines))

    def show_keychain_diagnostics(self):
        """Show native Keychain diagnostics for configured profiles.

        This check avoids reading secrets. It only reports whether expected
        keychain items exist and whether macOS-native access paths are active.
        """
        lines = [
            "Keychain Diagnostics",
            "",
            f"Platform: {platform.system()}",
            f"Service: {KEYRING_SERVICE}",
            f"Keyring available: {'Yes' if KEYRING_AVAILABLE else 'No'}",
            f"Keyring backend: {KEYRING_BACKEND_NAME}",
            f"macOS security CLI available: {'Yes' if self._macos_keychain_cli_available() else 'No'}",
            f"Touch ID-capable path detected: {'Yes' if (KEYRING_TOUCH_ID_SUPPORTED or self._macos_keychain_cli_available()) else 'No'}",
            f"LocalAuthentication bridge: {'Available' if MACOS_LOCAL_AUTH_AVAILABLE else 'Unavailable'}",
        ]

        backend_lower = str(KEYRING_BACKEND_NAME or "").lower()
        backend_is_macos = "keyring.backends.macos" in backend_lower
        fallback_risk = (
            IS_MACOS
            and KEYRING_AVAILABLE
            and not self._macos_keychain_cli_available()
            and not backend_is_macos
        )

        lines.append("")
        if fallback_risk:
            lines.append("Fallback backend risk: HIGH (non-native backend may prompt for vault password)")
        elif IS_MACOS and (self._macos_keychain_cli_available() or backend_is_macos):
            lines.append("Fallback backend risk: LOW (native Keychain path available)")
        else:
            lines.append("Fallback backend risk: N/A for this platform")

        lines.append("")
        lines.append("Session cache state:")
        lines.append(f"- Cached secret entries: {len(getattr(self, '_secret_cache', {}) or {})}")
        lines.append(f"- Read-attempt markers: {len(getattr(self, '_secret_read_attempted', set()) or set())}")
        lines.append(f"- In-flight background reads: {len(getattr(self, '_secret_read_inflight', set()) or set())}")

        cfg = self._read_config()
        profile_names = []
        for name, value in cfg.items():
            if name == "__meta__":
                continue
            if isinstance(value, dict) and value.get("env_id") and value.get("cl_id"):
                profile_names.append(name)

        lines.append("")
        lines.append("Profile keychain item checks (no secrets read):")
        if not profile_names:
            lines.append("- No profiles found.")
        elif not self._macos_keychain_cli_available():
            lines.append("- Native security CLI unavailable; cannot verify per-item existence.")
        else:
            for profile_name in sorted(profile_names):
                usernames = self._keyring_usernames(profile_name)
                username_results = []
                for username in usernames:
                    exists = False
                    try:
                        proc = subprocess.run(
                            [
                                "security",
                                "find-generic-password",
                                "-s",
                                KEYRING_SERVICE,
                                "-a",
                                username,
                            ],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        exists = proc.returncode == 0
                    except Exception:
                        exists = False
                    username_results.append(f"{username}={'FOUND' if exists else 'MISSING'}")

                lines.append(f"- {profile_name}: " + ", ".join(username_results))

        lines.append("")
        lines.append("Recommendation:")
        lines.append("- Keep native Keychain path enabled and avoid non-native fallback backends.")
        lines.append("- Allow only required executables for this service/account in Keychain Access.")
        lines.append("- Save profile once so canonical account names exist for each profile.")

        self.show_detail_message_window("Keychain Diagnostics", "\n".join(lines))

    def apply_keychain_acl_all_profiles(self):
        """Re-save profile secrets to apply current macOS Keychain ACL policy."""
        if not IS_MACOS:
            QtWidgets.QMessageBox.information(
                self,
                "Apply Keychain ACL",
                "This action is only available on macOS.",
            )
            return

        if not self._macos_keychain_cli_available():
            QtWidgets.QMessageBox.warning(
                self,
                "Apply Keychain ACL",
                "Native macOS Keychain CLI is unavailable.",
            )
            return

        cfg = self._read_config()
        profile_names = []
        for name, value in cfg.items():
            if name == "__meta__":
                continue
            if isinstance(value, dict) and value.get("env_id") and value.get("cl_id"):
                profile_names.append(name)

        if not profile_names:
            QtWidgets.QMessageBox.information(
                self,
                "Apply Keychain ACL",
                "No saved profiles were found.",
            )
            return

        confirm = QtWidgets.QMessageBox.question(
            self,
            "Apply Keychain ACL",
            (
                "This will re-save keychain secrets for all saved profiles using the current ACL policy\n"
                "(Allow all applications for each item).\n\n"
                "Continue?"
            ),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        success = []
        skipped = []
        failed = []

        for profile_name in sorted(profile_names):
            secret = ""
            try:
                secret = self._read_secret_from_macos_keychain(profile_name)
            except Exception:
                secret = ""

            # If native lookup is empty but the user already loaded it this
            # session, reuse cache to apply ACL on canonical key name.
            if not secret:
                secret = self._get_cached_secret(profile_name) or ""

            if not secret:
                skipped.append(f"{profile_name}: no existing secret found")
                continue

            ok, err = self._write_secret_to_macos_keychain(profile_name, secret)
            if ok:
                self._cache_secret(profile_name, secret)
                success.append(profile_name)
            else:
                failed.append(f"{profile_name}: {err or 'unknown error'}")

        lines = [
            "Apply Keychain ACL To All Profiles",
            "",
            f"Profiles processed: {len(profile_names)}",
            f"Updated: {len(success)}",
            f"Skipped: {len(skipped)}",
            f"Failed: {len(failed)}",
        ]
        if success:
            lines.append("")
            lines.append("Updated profiles:")
            for name in success:
                lines.append(f"- {name}")
        if skipped:
            lines.append("")
            lines.append("Skipped profiles:")
            for row in skipped:
                lines.append(f"- {row}")
        if failed:
            lines.append("")
            lines.append("Failed profiles:")
            for row in failed:
                lines.append(f"- {row}")

        self.show_detail_message_window("Apply Keychain ACL", "\n".join(lines))
        try:
            self._set_processing_message(
                f"Keychain ACL apply complete: updated={len(success)}, skipped={len(skipped)}, failed={len(failed)}"
            )
        except Exception:
            pass

    def show_preferences_dialog(self):
        """Show the dedicated settings window for runtime application options."""
        try:
            # Create simple test dialog first
            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle("Preferences")
            dlg.setModal(True)
            dlg.resize(560, 520)

            lay = QtWidgets.QVBoxLayout(dlg)

            form_box = QtWidgets.QGroupBox("General Settings")
            form = QtWidgets.QFormLayout(form_box)

            auto_connect_cb = QtWidgets.QCheckBox("Auto-connect to last working profile on startup")
            auto_connect_cb.setChecked(self.auto_connect_cb.isChecked() if hasattr(self, 'auto_connect_cb') else False)

            json_cb = QtWidgets.QCheckBox("Enable JSON Editing")
            json_cb.setChecked(self.enable_json_edit_action.isChecked())

            friendly_cb = QtWidgets.QCheckBox("Use Friendly Column Names")
            friendly_cb.setChecked(self.use_friendly_names_action.isChecked())

            dark_cb = QtWidgets.QCheckBox("Dark Mode")
            dark_cb.setChecked(self.dark_mode_action.isChecked())

            success_cb = QtWidgets.QCheckBox("Show User Update Success Messages")
            success_cb.setChecked(self.show_user_update_success_action.isChecked())

            prompt_delete_cb = QtWidgets.QCheckBox("Always Prompt Before Deleting Users")
            prompt_delete_cb.setChecked(bool(getattr(self, 'prompt_before_delete', True)))

            hide_links_cb = QtWidgets.QCheckBox("Hide Link / JSON Reference Columns")
            hide_links_cb.setChecked(self.hide_raw_http_columns_cb.isChecked() if hasattr(self, 'hide_raw_http_columns_cb') else True)

            show_api_status_cb = QtWidgets.QCheckBox("Show Live API Calls In Status Bar")
            show_api_status_cb.setChecked(self.show_api_calls_cb.isChecked() if hasattr(self, 'show_api_calls_cb') else False)

            api_log_cb = QtWidgets.QCheckBox("Log All API Activity")
            api_log_cb.setChecked(self.enable_api_logging_action.isChecked())

            cred_log_cb = QtWidgets.QCheckBox("Enable Credentials Logging")
            cred_log_cb.setChecked(self.enable_credentials_logging_action.isChecked())

            validation_combo = QtWidgets.QComboBox()
            validation_combo.addItem("None", "none")
            validation_combo.addItem("Server Dry-Run", "server")
            validation_combo.addItem("Local Schema Validation", "local")
            if self.use_server_dryrun_action.isChecked():
                validation_combo.setCurrentIndex(validation_combo.findData("server"))
            elif self.use_local_schema_action.isChecked():
                validation_combo.setCurrentIndex(validation_combo.findData("local"))
            else:
                validation_combo.setCurrentIndex(validation_combo.findData("none"))

            form.addRow(auto_connect_cb)
            form.addRow(json_cb)
            form.addRow(friendly_cb)
            form.addRow(dark_cb)
            form.addRow(success_cb)
            form.addRow(prompt_delete_cb)
            form.addRow(hide_links_cb)
            form.addRow(show_api_status_cb)
            form.addRow(api_log_cb)
            form.addRow(cred_log_cb)
            form.addRow("Validation:", validation_combo)
            lay.addWidget(form_box)

            tools_box = QtWidgets.QGroupBox("Actions")
            tools_lay = QtWidgets.QHBoxLayout(tools_box)
            open_logs_btn = QtWidgets.QPushButton("Open Log Files")
            open_logs_btn.clicked.connect(self.show_log_files)
            open_capture_btn = QtWidgets.QPushButton("Open API Capture")
            open_capture_btn.clicked.connect(self.show_api_capture_dialog)
            revert_columns_btn = QtWidgets.QPushButton("Revert Columns")
            revert_columns_btn.clicked.connect(self.revert_to_default_columns)
            console_url_btn = QtWidgets.QPushButton("Set Console URL")
            console_url_btn.clicked.connect(self.set_pingone_console_url)
            tools_lay.addWidget(open_logs_btn)
            tools_lay.addWidget(open_capture_btn)
            tools_lay.addWidget(revert_columns_btn)
            tools_lay.addWidget(console_url_btn)
            lay.addWidget(tools_box)

            btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            lay.addWidget(btns)

            result = dlg.exec()
            
            if result != QtWidgets.QDialog.DialogCode.Accepted:
                return

            # Apply auto-connect setting
            if hasattr(self, 'auto_connect_cb'):
                self.auto_connect_cb.setChecked(auto_connect_cb.isChecked())
                self.save_app_settings()

            self.enable_json_edit_action.setChecked(json_cb.isChecked())
            self.toggle_json_editing()

            self.use_friendly_names_action.setChecked(friendly_cb.isChecked())
            self.toggle_friendly_names()

            self.dark_mode_action.setChecked(dark_cb.isChecked())
            self.toggle_theme()

            self.show_user_update_success_action.setChecked(success_cb.isChecked())
            self.on_show_user_update_success_toggled(self.show_user_update_success_action.isChecked())

            self.prompt_before_delete = bool(prompt_delete_cb.isChecked())

            if hasattr(self, 'hide_raw_http_columns_cb'):
                self.hide_raw_http_columns_cb.setChecked(hide_links_cb.isChecked())
            if hasattr(self, 'show_api_calls_cb'):
                self.show_api_calls_cb.setChecked(show_api_status_cb.isChecked())

            self.enable_api_logging_action.setChecked(api_log_cb.isChecked())
            self.toggle_api_logging()

            self.enable_credentials_logging_action.setChecked(cred_log_cb.isChecked())
            self.toggle_credentials_logging()

            mode = validation_combo.currentData()
            self.use_server_dryrun_action.setChecked(mode == "server")
            self.use_local_schema_action.setChecked(mode == "local")
            if mode == "server":
                self.toggle_server_dryrun()
            elif mode == "local":
                self.toggle_local_schema()
            else:
                msg = "Validation: none"
                try:
                    self._set_processing_message(msg)
                except Exception:
                    pass

            self.save_profile_option()
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(
                self,
                "Preferences Error",
                f"An error occurred while saving preferences:\n{str(e)}"
            )

    def showEvent(self, event):
        """Override showEvent to restore geometry after window is fully initialized."""
        super().showEvent(event)
        # Only restore geometry once
        if not hasattr(self, '_geometry_restored'):
            self._geometry_restored = True
            # Use a timer to restore geometry after the window is fully shown
            QtCore.QTimer.singleShot(0, self.restore_window_geometry)

    def init_ui(self):
        # Build the main UI widgets and wire actions to slots.
        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Menu Bar
        menubar = self.menuBar()
        # On macOS, use the native menu bar
        if IS_MACOS:
            menubar.setNativeMenuBar(True)
        
        # File menu first (standard on all platforms)
        file_menu = menubar.addMenu("File")
        manage_profiles_action = file_menu.addAction("Manage Profiles...")
        manage_profiles_action.triggered.connect(self.show_profile_manager)
        manage_profiles_action.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.KeyboardModifier.ShiftModifier | QtCore.Qt.Key.Key_M))
        
        # Rollback last import action
        rollback_import_action = file_menu.addAction("Rollback Last Import...")
        rollback_import_action.triggered.connect(self.rollback_last_import)
        rollback_import_action.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.KeyboardModifier.ShiftModifier | QtCore.Qt.Key.Key_R))
        file_menu.addSeparator()
        
        # Preferences action - accessible via File menu and keyboard shortcut
        self.preferences_action = QtGui.QAction("Preferences...", self)
        self.preferences_action.triggered.connect(self.show_preferences_dialog)
        self.preferences_action.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_Comma))
        self.preferences_action.setToolTip(f"Open application preferences ({'Cmd' if IS_MACOS else 'Ctrl'}+,)")
        file_menu.addAction(self.preferences_action)
        file_menu.addSeparator()
        quit_action = file_menu.addAction("Quit")
        quit_action.triggered.connect(self.close)
        quit_action.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_Q))
        quit_action.setToolTip(f"Quit application ({'Cmd' if IS_MACOS else 'Ctrl'}+Q)")
        if IS_MACOS:
            # On macOS, the quit action should have the QuitRole to appear in app menu
            quit_action.setMenuRole(QtGui.QAction.MenuRole.QuitRole)
        
        self.enable_json_edit_action = QtGui.QAction("Enable JSON Editing", self)
        self.enable_json_edit_action.setCheckable(True)
        self.enable_json_edit_action.setChecked(False)
        self.enable_json_edit_action.triggered.connect(self.toggle_json_editing)
        self.enable_json_edit_action.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_J))
        self.addAction(self.enable_json_edit_action)
        
        self.use_friendly_names_action = QtGui.QAction("Use Friendly Column Names", self)
        self.use_friendly_names_action.setCheckable(True)
        self.use_friendly_names_action.setChecked(True)
        self.use_friendly_names_action.triggered.connect(self.toggle_friendly_names)
        self.use_friendly_names_action.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_F))
        self.addAction(self.use_friendly_names_action)

        # Validation mode: server dry-run or local schema
        self.use_server_dryrun_action = QtGui.QAction("Use Server Dry-Run", self)
        self.use_server_dryrun_action.setCheckable(True)
        self.use_server_dryrun_action.setChecked(True)
        self.use_server_dryrun_action.triggered.connect(self.toggle_server_dryrun)

        self.use_local_schema_action = QtGui.QAction("Use Local Schema Validation", self)
        self.use_local_schema_action.setCheckable(True)
        self.use_local_schema_action.setChecked(False)
        self.use_local_schema_action.triggered.connect(self.toggle_local_schema)

        self.revert_columns_action = QtGui.QAction("Revert to Default Columns", self)
        self.revert_columns_action.triggered.connect(self.revert_to_default_columns)

        # Theme toggle
        self.dark_mode_action = QtGui.QAction("Dark Mode", self)
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.setChecked(False)
        self.dark_mode_action.triggered.connect(self.toggle_theme)
        self.dark_mode_action.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_D))
        self.addAction(self.dark_mode_action)

        # Credentials logging settings
        self.enable_credentials_logging_action = QtGui.QAction("Enable Credentials Logging", self)
        self.enable_credentials_logging_action.setCheckable(True)
        self.enable_credentials_logging_action.setChecked(True)
        self.enable_credentials_logging_action.triggered.connect(self.toggle_credentials_logging)

        # API logging toggle (log all API activity)
        self.enable_api_logging_action = QtGui.QAction("Log All API Activity", self)
        self.enable_api_logging_action.setCheckable(True)
        self.enable_api_logging_action.setChecked(False)
        self.enable_api_logging_action.triggered.connect(self.toggle_api_logging)

        self.show_user_update_success_action = QtGui.QAction("Show User Update Success Messages", self)
        self.show_user_update_success_action.setCheckable(True)
        self.show_user_update_success_action.setChecked(True)
        self.show_user_update_success_action.triggered.connect(self.on_show_user_update_success_toggled)

        self.capture_api_action = QtGui.QAction("Capture API Calls...", self)
        self.capture_api_action.triggered.connect(self.show_api_capture_dialog)

        self.set_console_url_action = QtGui.QAction("Set PingOne Console URL...", self)
        self.set_console_url_action.triggered.connect(self.set_pingone_console_url)

        # Separate Logs submenu for quick actions (reset, clear, archive)
        logs_menu = menubar.addMenu("Logs")
        self.logs_show_action = logs_menu.addAction("Show Log Files...")
        self.logs_show_action.triggered.connect(self.show_log_files)
        self.logs_show_user_mgmt_action = logs_menu.addAction("View User Mgmt Edit Logs...")
        self.logs_show_user_mgmt_action.triggered.connect(self.view_user_mgmt_edit_log)
        self.logs_clear_all = logs_menu.addAction("Clear All Logs")
        self.logs_clear_all.triggered.connect(self.clear_all_logs)
        self.logs_archive = logs_menu.addAction("Archive Logs...")
        self.logs_archive.triggered.connect(self.archive_logs)
        
        # Add a Settings menu for easy access to preferences
        settings_menu = menubar.addMenu("Settings")
        settings_preferences_action = settings_menu.addAction("Preferences...")
        settings_preferences_action.triggered.connect(self.show_preferences_dialog)
        settings_preferences_action.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.KeyboardModifier.ShiftModifier | QtCore.Qt.Key.Key_Comma))
        
        help_menu = menubar.addMenu("Help")
        
        # Add Preferences to Help menu for easy discoverability
        help_preferences_action = help_menu.addAction("Preferences...")
        help_preferences_action.triggered.connect(self.show_preferences_dialog)
        help_preferences_action.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_Comma))
        help_menu.addSeparator()
        
        config_help_action = help_menu.addAction("Configuration Help")
        config_help_action.triggered.connect(self.show_config_help)
        user_help_action = help_menu.addAction("User Management Help")
        user_help_action.triggered.connect(self.show_user_help)
        filter_help_action = help_menu.addAction("Filter Help")
        filter_help_action.triggered.connect(self.show_filter_help)
        tabs_help_action = help_menu.addAction("Tabs Overview")
        tabs_help_action.triggered.connect(self.show_tabs_help)
        full_help_action = help_menu.addAction("Full Help & Options")
        full_help_action.triggered.connect(self.show_full_help)
        app_help_action = help_menu.addAction("Application Help")
        app_help_action.triggered.connect(self.show_app_help)
        help_menu.addSeparator()
        self.about_action = help_menu.addAction("About PingOne UserManager")
        self.about_action.triggered.connect(self.show_about_dialog)
        if IS_MACOS:
            self.about_action.setMenuRole(QtGui.QAction.MenuRole.AboutRole)
        
        # --- Config Tab ---
        env_tab = QtWidgets.QWidget(); env_lay = QtWidgets.QVBoxLayout(env_tab)
        prof_group = QtWidgets.QGroupBox("Profiles")
        prof_form = QtWidgets.QFormLayout(prof_group)
        self.profile_list = QtWidgets.QComboBox()
        self.profile_list.currentIndexChanged[int].connect(self.load_selected_profile)
        prof_form.addRow("Active Profile:", self.profile_list)
        # Option: auto-connect to last working profile on startup
        self.auto_connect_cb = QtWidgets.QCheckBox("Auto-connect to last working profile on startup")
        prof_form.addRow(self.auto_connect_cb)
        
        cred_group = QtWidgets.QGroupBox("Credentials")
        cred_form = QtWidgets.QFormLayout(cred_group)
        self.env_id, self.cl_id = QtWidgets.QLineEdit(), QtWidgets.QLineEdit()
        # Ensure fields can accept/display up to 40 characters
        # Compute font metrics once and reuse to avoid repeated calls.
        fm = QtWidgets.QLineEdit().fontMetrics()
        small_width = fm.horizontalAdvance('M' * 40)
        for le in (self.env_id, self.cl_id):
            le.setMaxLength(40)
            le.setMinimumWidth(small_width)

        # Client secret with show/hide toggle — allow longer secrets.
        # Env ID / Client ID fields stay at 40 chars, but client secrets
        # can be longer (e.g. rotated/legacy secrets). Allow up to 100
        # characters and set the same visual width for consistency.
        self.cl_sec = QtWidgets.QLineEdit()
        # Accept up to 100 characters for client secrets.
        self.cl_sec.setMaxLength(100)
        # Use the previously computed font metrics to compute a reasonable
        # minimum width for longer client secrets instead of recomputing.
        long_width = fm.horizontalAdvance('M' * 100)
        self.cl_sec.setMinimumWidth(long_width)
        self.cl_sec.setEchoMode(QtWidgets.QLineEdit.Password)
        secret_layout = QtWidgets.QHBoxLayout()
        secret_layout.setContentsMargins(0, 0, 0, 0)
        secret_layout.addWidget(self.cl_sec)
        self._show_secret_btn = QtWidgets.QPushButton("Show")
        self._show_secret_btn.setCheckable(True)
        def _toggle_secret(checked):
            self.cl_sec.setEchoMode(QtWidgets.QLineEdit.Normal if checked else QtWidgets.QLineEdit.Password)
            self._show_secret_btn.setText("Hide" if checked else "Show")
        self._show_secret_btn.toggled.connect(_toggle_secret)
        secret_layout.addWidget(self._show_secret_btn)
        secret_widget = QtWidgets.QWidget()
        secret_widget.setLayout(secret_layout)

        # Monitor all three credential fields; when in new-connection mode and
        # all three are non-empty, a debounce timer triggers the save-profile
        # prompt automatically.
        for le in (self.env_id, self.cl_id, self.cl_sec):
            le.textChanged.connect(self._new_conn_field_edited)

        # Swap Test Credentials and Save Profile positions per request
        cred_form.addRow("Env ID:", self.env_id); cred_form.addRow("Client ID:", self.cl_id)
        cred_form.addRow("Secret:", secret_widget);
        self.config_action_combo = QtWidgets.QComboBox()
        self.config_action_combo.addItems([
            "Test Credentials",
            "New Connection",
            "Save Profile",
            "Connect",
            "Delete Profile",
            "View Connection Log",
            "Keychain Diagnostics",
            "Apply Keychain ACL To All Profiles",
            "Manage DB Connections",
            "Manage LDAP Connections",
            "Open Preferences",
        ])
        self.config_action_combo.setToolTip("Select a configuration action")
        self.config_action_execute_btn = QtWidgets.QPushButton("Execute")
        self.config_action_execute_btn.clicked.connect(self.execute_config_action)
        self.open_pingone_console_btn = QtWidgets.QPushButton("Open PingOne Console")
        self.open_pingone_console_btn.setToolTip("Launch the active PingOne environment in your browser")
        self.open_pingone_console_btn.clicked.connect(self.open_pingone_console)
        self.open_pingone_console_env_label = QtWidgets.QLabel(f"{self.pingone_console_url.rstrip('/')}/?env=")
        self.open_pingone_console_env_label.setToolTip("Full URL used for Open PingOne Console")
        self.open_pingone_console_env_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
            | QtCore.Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.open_pingone_console_env_label.setCursor(
            QtGui.QCursor(QtCore.Qt.CursorShape.IBeamCursor)
        )
        self.env_id.textChanged.connect(self.update_pingone_console_env_label)
        config_action_row = QtWidgets.QHBoxLayout()
        config_action_row.addWidget(self.config_action_combo)
        config_action_row.addWidget(self.config_action_execute_btn)
        config_action_row.addWidget(self.open_pingone_console_btn)
        config_action_row.addWidget(self.open_pingone_console_env_label)
        self.update_pingone_console_env_label(self.env_id.text())
        cred_form.addRow("Action:", config_action_row)

        # Preserve keyboard shortcuts for frequent configuration actions.
        self.shortcut_save_profile = QtGui.QShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_P), self)
        self.shortcut_save_profile.activated.connect(self.save_current_profile)
        self.shortcut_connect_profile = QtGui.QShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_N), self)
        self.shortcut_connect_profile.activated.connect(self.connect_only)
        self.shortcut_test_credentials = QtGui.QShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_T), self)
        self.shortcut_test_credentials.activated.connect(self.test_credentials)

        # Per-profile option: show live API calls in status bar (managed in Settings dialog)
        self.show_api_calls_cb = QtWidgets.QCheckBox('Show live API calls in status bar')
        self.show_api_calls_cb.setChecked(False)
        self.show_api_calls_cb.stateChanged.connect(self.on_show_api_calls_toggled)
        # Checkbox removed from UI - configured in Settings dialog
        
        self.lbl_stats = QtWidgets.QLabel("Users: -- | Populations: --")
        self.lbl_stats.setToolTip("Current Counts: Total number of users and populations loaded in the current environment")
        env_lay.addWidget(prof_group); env_lay.addWidget(cred_group); env_lay.addWidget(self.lbl_stats); env_lay.addStretch()

        # --- Users Tab ---
        user_tab = QtWidgets.QWidget(); user_lay = QtWidgets.QVBoxLayout(user_tab)
        toolbar = QtWidgets.QHBoxLayout()
        self.btn_del = None
        self.search_bar = QtWidgets.QLineEdit(); self.search_bar.setPlaceholderText("Filter...")
        self.search_bar.textChanged.connect(self.filter_table)
        # Create a shortcut to focus the search bar (QLineEdit doesn't have setShortcut method)
        search_shortcut = QtGui.QShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_L), self)
        search_shortcut.activated.connect(self.search_bar.setFocus)
        self.search_bar.setToolTip(f"Focus filter field ({'Cmd' if IS_MACOS else 'Ctrl'}+L)")

        toolbar.addWidget(self.search_bar)

        # Hide Links checkbox removed from toolbar - configured in Settings dialog
        self.hide_raw_http_columns_cb = QtWidgets.QCheckBox("Hide Links")
        self.hide_raw_http_columns_cb.setChecked(True)
        self.hide_raw_http_columns_cb.setToolTip("Hide columns whose names start with '{' or 'http'")
        self.hide_raw_http_columns_cb.stateChanged.connect(self.on_hide_raw_http_columns_toggled)

        self.command_combo = QtWidgets.QComboBox()
        self.command_combo.addItems([
            "Refresh Users",
            "Delete Selected",
            "Select Columns",
            "Save Layout",
            "Manage DB Connections",
            "Manage LDAP Connections",
        ])
        self.command_combo.setToolTip("Select a command for the user table")
        self.command_execute_btn = QtWidgets.QPushButton("Execute")
        self.command_execute_btn.clicked.connect(self.execute_user_command)
        toolbar.addWidget(self.command_combo)
        toolbar.addWidget(self.command_execute_btn)

        self.transfer_combo = QtWidgets.QComboBox()
        self.transfer_combo.addItems([
            "Import",
            "Export",
        ])
        self.transfer_combo.setToolTip("Select import/export action")
        self.transfer_execute_btn = QtWidgets.QPushButton("Execute")
        self.transfer_execute_btn.clicked.connect(self.execute_transfer_action)
        toolbar.addWidget(self.transfer_combo)
        toolbar.addWidget(self.transfer_execute_btn)

        # Keep keyboard shortcuts for commonly-used actions.
        self.shortcut_refresh = QtGui.QShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_R), self)
        self.shortcut_refresh.activated.connect(self.refresh_users)
        self.shortcut_import_csv = QtGui.QShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_I), self)
        self.shortcut_import_csv.activated.connect(self.import_from_csv)
        self.shortcut_import_ldif = QtGui.QShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.KeyboardModifier.ShiftModifier | QtCore.Qt.Key.Key_I), self)
        self.shortcut_import_ldif.activated.connect(self.import_from_ldif)
        self.shortcut_export_csv = QtGui.QShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_E), self)
        self.shortcut_export_csv.activated.connect(self.export_to_csv)
        self.shortcut_export_ldif = QtGui.QShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.KeyboardModifier.ShiftModifier | QtCore.Qt.Key.Key_E), self)
        self.shortcut_export_ldif.activated.connect(self.export_to_ldif)
        self.shortcut_import_db = QtGui.QShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.KeyboardModifier.AltModifier | QtCore.Qt.Key.Key_I), self)
        self.shortcut_import_db.activated.connect(self.import_from_database)
        self.shortcut_export_db = QtGui.QShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.KeyboardModifier.AltModifier | QtCore.Qt.Key.Key_E), self)
        self.shortcut_export_db.activated.connect(self.export_to_database)
        self.shortcut_columns = QtGui.QShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_K), self)
        self.shortcut_columns.activated.connect(self.select_columns)
        self.shortcut_save_layout = QtGui.QShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_S), self)
        self.shortcut_save_layout.activated.connect(self.save_columns_to_config)
        self.u_table = QtWidgets.QTableWidget(0, 0)
        self.u_table.setHorizontalHeaderLabels([])
        self.u_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.u_table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.u_table.setSortingEnabled(True)
        self.u_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.u_table.horizontalHeader().setStretchLastSection(False)
        self.u_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.u_table.customContextMenuRequested.connect(self.show_context_menu)
        self.u_table.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.u_table.itemClicked.connect(self.on_item_clicked)
        self.u_table.horizontalHeader().setSectionsMovable(True)
        self.u_table.horizontalHeader().sectionMoved.connect(self.on_column_moved)
        self.u_table.horizontalHeader().sectionResized.connect(self.on_column_resized)

        # Delete currently selected/current row from User Management table.
        self.shortcut_delete_users = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Delete), self.u_table)
        self.shortcut_delete_users.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
        self.shortcut_delete_users.activated.connect(self.delete_selected_users)
        self.shortcut_backspace_users = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Backspace), self.u_table)
        self.shortcut_backspace_users.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
        self.shortcut_backspace_users.activated.connect(self.delete_selected_users)
        
        # Progress bar with cancel button
        self.prog = QtWidgets.QProgressBar()
        self.prog.hide()
        self.cancel_btn = QtWidgets.QPushButton("Cancel Import")
        self.cancel_btn.hide()
        self.cancel_btn.clicked.connect(self._cancel_operation)
        self.cancel_requested = False
        self.last_import_record = None  # Track last import for rollback
        
        prog_layout = QtWidgets.QHBoxLayout()
        prog_layout.addWidget(self.prog)
        prog_layout.addWidget(self.cancel_btn)
        
        user_lay.addLayout(toolbar)
        user_lay.addLayout(prog_layout)
        user_lay.addWidget(self.u_table)
        # Add a persistent status bar so messages are visible across tabs
        self.status_label = QtWidgets.QLabel("Ready")
        self.api_calls_label = QtWidgets.QLabel("")
        self.api_calls_label.setToolTip("Live API activity: Shows real-time API calls as they are made to PingOne")
        
        self.profile_name_label = QtWidgets.QLabel("")
        self.profile_name_label.setToolTip("Current Profile: The active configuration profile with environment and credentials")
        
        self.last_source_label = QtWidgets.QLabel("Last source: none")
        self.last_source_label.setToolTip("Last Data Source: The most recent import or export source (CSV, LDIF, Database, or LDAP)")
        
        self.processing_label = QtWidgets.QLabel("")  # For import/export/processing messages
        self.processing_label.setToolTip(
            "Operation Status: Current import/export/processing activity\n\n"
            "When you see 'X concurrent':\n"
            "• Concurrent = Number of simultaneous API requests being made\n"
            "• Higher concurrency (up to 10) = faster processing for large operations\n"
            "• Used automatically when importing/deleting/updating >50-100 users"
        )
        
        self.last_tps_label = QtWidgets.QLabel("")
        self.last_tps_label.setToolTip(
            "Transactions Per Second (TPS): Performance metric for the last bulk operation\n\n"
            "Shows how many API transactions were completed per second\n"
            "Higher TPS = better performance (typical range: 2-10 TPS depending on operation)"
        )
        
        self.last_tps_stats = None  # Store last TPS stats for status bar
        user_lay.addWidget(self.status_label)
        user_lay.addWidget(self.api_calls_label)
        sb = QtWidgets.QStatusBar()
        self.setStatusBar(sb)
        # Mirror initial status and add permanent widgets to status bar
        try:
            # Don't use showMessage() - it appears at the start. Use processing_label instead.
            
            # Add permanent widgets with dividers
            self.statusBar().addPermanentWidget(self.profile_name_label)
            
            # Divider 1
            divider1 = QtWidgets.QFrame()
            divider1.setFrameShape(QtWidgets.QFrame.VLine)
            divider1.setFrameShadow(QtWidgets.QFrame.Sunken)
            self.statusBar().addPermanentWidget(divider1)
            
            self.statusBar().addPermanentWidget(self.last_source_label)
            
            # Divider 2
            divider2 = QtWidgets.QFrame()
            divider2.setFrameShape(QtWidgets.QFrame.VLine)
            divider2.setFrameShadow(QtWidgets.QFrame.Sunken)
            self.statusBar().addPermanentWidget(divider2)
            
            self.statusBar().addPermanentWidget(self.processing_label)
            
            # Divider 3
            divider3 = QtWidgets.QFrame()
            divider3.setFrameShape(QtWidgets.QFrame.VLine)
            divider3.setFrameShadow(QtWidgets.QFrame.Sunken)
            self.statusBar().addPermanentWidget(divider3)
            
            self.statusBar().addPermanentWidget(self.lbl_stats)
            
            # Divider 4
            divider4 = QtWidgets.QFrame()
            divider4.setFrameShape(QtWidgets.QFrame.VLine)
            divider4.setFrameShadow(QtWidgets.QFrame.Sunken)
            self.statusBar().addPermanentWidget(divider4)
            
            self.statusBar().addPermanentWidget(self.last_tps_label)
            
            # Divider 5
            divider5 = QtWidgets.QFrame()
            divider5.setFrameShape(QtWidgets.QFrame.VLine)
            divider5.setFrameShadow(QtWidgets.QFrame.Sunken)
            self.statusBar().addPermanentWidget(divider5)
            
            self.statusBar().addPermanentWidget(self.api_calls_label)
        except Exception:
            pass
        # Timer to poll live API events and display them in the status area
        self.api_timer = QtCore.QTimer(self)
        self.api_timer.setInterval(1000)
        self.api_timer.timeout.connect(self._poll_api_events)
        self.api_timer.start()

        # Wire auto-connect checkbox to persist app-level setting
        try:
            self.auto_connect_cb.stateChanged.connect(self.save_app_settings)
        except Exception:
            pass

        self.tabs.addTab(env_tab, "Configuration"); self.tabs.addTab(user_tab, "User Management")
        self.tabs.currentChanged.connect(self.on_main_tab_changed)

    def on_main_tab_changed(self, index):
        """Refresh users when entering User Management after a config switch."""
        try:
            if index < 0:
                return
            tab_text = self.tabs.tabText(index)
            if tab_text == "User Management" and self._pending_user_tab_refresh:
                self._pending_user_tab_refresh = False
                self.refresh_users()
        except Exception:
            pass

    def _get_native_file_dialog_options(self):
        """Return platform-appropriate file dialog options."""
        options = QtWidgets.QFileDialog.Option(0)
        # On macOS, use native dialogs for better integration
        if IS_MACOS:
            options |= QtWidgets.QFileDialog.Option.DontUseNativeDialog
            # Actually, we want native dialogs on macOS, so don't set this flag
            options = QtWidgets.QFileDialog.Option(0)
        elif IS_LINUX:
            # On Linux, Qt dialogs sometimes work better than native
            options |= QtWidgets.QFileDialog.Option.DontUseNativeDialog
        # Windows uses native by default, which is fine
        return options

    def execute_user_command(self):
        """Execute the selected command from the main user-command pulldown."""
        cmd = self.command_combo.currentText()
        handlers = {
            "Refresh Users": self.refresh_users,
            "Delete Selected": self.delete_selected_users,
            "Select Columns": self.select_columns,
            "Save Layout": self.save_columns_to_config,
            "Manage DB Connections": self.manage_db_connections,
            "Manage LDAP Connections": self.manage_ldap_connections,
        }
        fn = handlers.get(cmd)
        if fn:
            fn()

    def execute_config_action(self):
        """Execute the selected action from the configuration pulldown."""
        action = self.config_action_combo.currentText()
        handlers = {
            "Test Credentials": self.test_credentials,
            "New Connection": self.new_connection,
            "Save Profile": self.save_current_profile,
            "Connect": self.connect_only,
            "Delete Profile": self.delete_current_profile,
            "View Connection Log": self.view_connection_log,
            "Keychain Diagnostics": self.show_keychain_diagnostics,
            "Apply Keychain ACL To All Profiles": self.apply_keychain_acl_all_profiles,
            "Manage DB Connections": self.manage_db_connections,
            "Manage LDAP Connections": self.manage_ldap_connections,
            "Open Preferences": self.show_preferences_dialog,
        }
        fn = handlers.get(action)
        if fn:
            fn()

    def open_pingone_console(self):
        """Open the PingOne admin console for the active environment."""
        env = (self.env_id.text() or "").strip()
        
        # If the stored URL already contains query params or fragment, use it as-is
        if '?' in self.pingone_console_url or '#' in self.pingone_console_url:
            if not QtGui.QDesktopServices.openUrl(QtCore.QUrl(self.pingone_console_url)):
                QtWidgets.QMessageBox.warning(
                    self,
                    "PingOne Console",
                    f"Unable to open browser URL:\n{self.pingone_console_url}"
                )
            return
        
        # Otherwise, append the env_id as a query param
        if not env:
            QtWidgets.QMessageBox.information(self, "PingOne Console", "Enter an Environment ID first.")
            return
        
        base = self.pingone_console_url.rstrip('/')
        encoded_env = QtCore.QUrl.toPercentEncoding(env).data().decode()
        primary_url = f"{base}/?env={encoded_env}"
        fallback_url = f"{base}/"
        if not QtGui.QDesktopServices.openUrl(QtCore.QUrl(primary_url)):
            if not QtGui.QDesktopServices.openUrl(QtCore.QUrl(fallback_url)):
                QtWidgets.QMessageBox.warning(
                    self,
                    "PingOne Console",
                    f"Unable to open browser URL:\n{primary_url}\n\nFallback also failed:\n{fallback_url}"
                )

    def update_pingone_console_env_label(self, value=""):
        """Display the full URL used by the Open PingOne Console button."""
        env = (value or "").strip()
        
        # If URL already has query params or fragment, show as-is
        if '?' in self.pingone_console_url or '#' in self.pingone_console_url:
            self.open_pingone_console_env_label.setText(self.pingone_console_url)
        else:
            # Otherwise append env_id if provided
            base = self.pingone_console_url.rstrip('/')
            encoded_env = QtCore.QUrl.toPercentEncoding(env).data().decode() if env else ""
            self.open_pingone_console_env_label.setText(f"{base}/?env={encoded_env}")

    def _normalize_pingone_console_url(self, value: str) -> str:
        """Return a normalized PingOne console URL or raise ValueError."""
        raw = (value or "").strip()
        if not raw:
            return DEFAULT_PINGONE_CONSOLE_URL
        
        # Allow simple domain.com → https://domain.com
        if "://" not in raw:
            raw = f"https://{raw}"
        
        try:
            qurl = QtCore.QUrl(raw)
            if not qurl.isValid():
                raise ValueError(f"Invalid URL format: {raw}")
            
            host = qurl.host()
            if not host:
                raise ValueError(f"URL missing host: {raw}")
            
            # Return the full URL as entered (preserving query params, fragments, paths, etc)
            return raw
        except Exception as e:
            raise ValueError(f"Please enter a valid URL (e.g., https://console.pingone.com): {e}")

    def _apply_pingone_console_url(self, value: str, persist: bool = True) -> bool:
        """Apply a console URL, refresh the label, and optionally persist."""
        try:
            normalized = self._normalize_pingone_console_url(value)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "PingOne Console URL", str(exc))
            return False

        try:
            self.pingone_console_url = normalized
            
            # Update label: if URL has query/fragment, show as-is; otherwise append env_id
            if '?' in self.pingone_console_url or '#' in self.pingone_console_url:
                label_text = self.pingone_console_url
            else:
                env = (self.env_id.text() or "").strip()
                base = self.pingone_console_url.rstrip('/')
                encoded_env = QtCore.QUrl.toPercentEncoding(env).data().decode() if env else ""
                label_text = f"{base}/?env={encoded_env}"
            
            self.open_pingone_console_env_label.setText(label_text)
            self.open_pingone_console_env_label.repaint()
            
            if persist:
                self.save_app_settings()
                try:
                    msg = f"PingOne Console URL updated: {self.pingone_console_url}"
                    self._set_processing_message(msg, 3000)
                except Exception:
                    pass
            
            return True
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to update URL: {e}")
            return False

    def set_pingone_console_url(self):
        """Prompt the user to set a custom PingOne Console URL."""
        current = self.pingone_console_url
        url, ok = QtWidgets.QInputDialog.getText(
            self, "Set PingOne Console URL",
            "Enter the base URL for the PingOne Console:",
            QtWidgets.QLineEdit.EchoMode.Normal, current
        )
        if ok and url.strip():
            success = self._apply_pingone_console_url(url, persist=True)
            if success:
                QtWidgets.QMessageBox.information(
                    self, "PingOne Console URL",
                    f"URL updated and saved:\n{self.pingone_console_url}"
                )

    def execute_transfer_action(self):
        """Execute the selected import/export action from the transfer pulldown."""
        action = self.transfer_combo.currentText()
        
        if action == "Import":
            self._launch_import_wizard()
        elif action == "Export":
            # Show export options dialog
            self._show_export_menu()

    def _cancel_operation(self):
        """Cancel the current import/export operation."""
        self.cancel_requested = True
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancelling...")
        self.status_label.setText("Cancellation requested...")
        try:
            self._set_processing_message("Cancellation requested...", 3000)
        except Exception:
            pass
    
    def rollback_last_import(self):
        """Rollback the last import operation by deleting created users."""
        if not self.last_import_record:
            QtWidgets.QMessageBox.information(
                self, "No Import to Rollback", 
                "No recent import operation found to rollback."
            )
            return
        
        created_ids = self.last_import_record.get('created_ids', [])
        if not created_ids:
            QtWidgets.QMessageBox.information(
                self, "Nothing to Rollback",
                "No users were created in the last import operation."
            )
            return
        
        reply = QtWidgets.QMessageBox.question(
            self, "Rollback Import",
            f"This will delete {len(created_ids)} user(s) created in the last import.\n\n"
            "This action cannot be undone. Continue?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply != QtWidgets.QMessageBox.Yes:
            return
        
        # Execute rollback
        client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
        self.prog.show()
        self.prog.setRange(0, len(created_ids))
        
        worker = BulkDeleteWorker(client, created_ids)
        worker.signals.progress.connect(lambda cur, tot: self.prog.setValue(cur))
        worker.signals.status.connect(lambda msg: self._set_processing_message(msg))
        worker.signals.tps_update.connect(lambda tps_stats: self._update_tps_status_bar(tps_stats, "Rollback"))
        
        def on_rollback_done(res):
            self.prog.hide()
            deleted = res.get('deleted', 0)
            total = res.get('total', 0)
            tps_stats = res.get('tps_stats')
            
            if tps_stats and tps_stats.get('total_transactions', 0) > 0:
                self._show_tps_report(tps_stats, "Rollback")
            
            QtWidgets.QMessageBox.information(
                self, "Rollback Complete",
                f"Deleted {deleted}/{total} users from last import."
            )
            
            # Clear the import record after successful rollback
            self.last_import_record = None
            self.refresh_users()
        
        worker.signals.finished.connect(on_rollback_done)
        worker.signals.error.connect(lambda m: (self.prog.hide(), QtWidgets.QMessageBox.critical(self, "Rollback Error", m)))
        self.threadpool.start(worker)
        
        msg = "Rollback started"
        try:
            self._set_processing_message(msg)
        except Exception:
            pass

    def _get_last_transfer_method(self, direction: str) -> str:
        """Return the last used import or export method for the active profile."""
        key = f'last_{direction}_method'
        try:
            prof = self.profile_list.currentText()
            cfg = self._read_config()
            if prof and prof in cfg:
                return cfg[prof].get(key) or ''
        except Exception:
            pass
        return ''

    def _save_last_transfer_method(self, direction: str, method: str):
        """Persist the last used import or export method for the active profile."""
        key = f'last_{direction}_method'
        try:
            prof = self.profile_list.currentText()
            if not prof:
                return
            cfg = self._read_config()
            if prof not in cfg:
                cfg[prof] = {}
            cfg[prof][key] = method
            self._write_config(cfg)
        except Exception:
            pass

    def _launch_import_wizard(self):
        """Launch wizard-style import dialog with radio buttons for source selection."""
        from ui.dialogs import ImportWizardDialog
        
        cfg = self._read_config()
        dbs = cfg.get('db_connections', {})
        ldaps = cfg.get('ldap_connections', {})
        
        dlg = ImportWizardDialog(
            self,
            db_connections=dbs,
            ldap_connections=ldaps,
            manage_db_callback=self.manage_db_connections,
            manage_ldap_callback=self.manage_ldap_connections,
            last_method=self._get_last_transfer_method('import'),
        )
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return
        
        result = dlg.get_result()
        source_type = result.get('source_type')
        
        try:
            if source_type == 'csv':
                self._save_last_transfer_method('import', 'csv')
                self.import_from_csv()
            elif source_type == 'ldif':
                self._save_last_transfer_method('import', 'ldif')
                self.import_from_ldif()
            elif source_type == 'db':
                self._save_last_transfer_method('import', 'db')
                self.import_from_database_wizard(
                    connection_name=result.get('connection_name'),
                    query_mode=result.get('query_mode', 'table')
                )
            elif source_type == 'ldap':
                self._save_last_transfer_method('import', 'ldap')
                self.import_from_ldap_directory_wizard(
                    connection_name=result.get('connection_name')
                )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import Error", str(e))

    def _show_export_menu(self):
        """Show export options dialog for CSV, LDIF, Database, or LDAP Directory."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Export")
        dlg.setModal(True)
        layout = QtWidgets.QVBoxLayout(dlg)
        layout.addWidget(QtWidgets.QLabel("Select export format:"))

        rb_csv = QtWidgets.QRadioButton("CSV")
        rb_ldif = QtWidgets.QRadioButton("LDIF")
        rb_db = QtWidgets.QRadioButton("Database")
        rb_ldap = QtWidgets.QRadioButton("LDAP Directory")
        # pre-select the last used export method
        last_exp = self._get_last_transfer_method('export')
        {
            'csv': rb_csv,
            'ldif': rb_ldif,
            'db': rb_db,
            'ldap': rb_ldap,
        }.get(last_exp, rb_csv).setChecked(True)
        layout.addWidget(rb_csv)
        layout.addWidget(rb_ldif)
        layout.addWidget(rb_db)
        layout.addWidget(rb_ldap)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return

        if rb_csv.isChecked():
            self._save_last_transfer_method('export', 'csv')
            self.export_to_csv()
        elif rb_ldif.isChecked():
            self._save_last_transfer_method('export', 'ldif')
            self.export_to_ldif()
        elif rb_db.isChecked():
            self._save_last_transfer_method('export', 'db')
            self.export_to_database()
        elif rb_ldap.isChecked():
            self._save_last_transfer_method('export', 'ldap')
            self.export_to_ldap_directory()

    def _set_last_data_source(self, source: str):
        """Update status bar with the most recent DB connection or input file source."""
        if not source:
            return
        try:
            self.last_source_label.setText(f"Last source: {source}")
        except Exception:
            pass
    
    def _set_processing_message(self, message: str, timeout: int = 0):
        """Set a processing/status message in the status bar (appears after Last Source).
        
        Args:
            message: The message to display
            timeout: Optional timeout in milliseconds to clear the message (0 = no timeout)
        """
        try:
            self.processing_label.setText(message)
            if timeout > 0:
                # Clear message after timeout
                QtCore.QTimer.singleShot(timeout, lambda: self.processing_label.setText(""))
        except Exception:
            pass

    # --- Profile Methods ---
    def _read_config(self):
        if self.config_file.exists():
            with open(self.config_file, 'r') as f: return json.load(f)
        return {}

    def _write_config(self, data: dict):
        """Atomically persist profiles config to avoid truncated JSON on interruption."""
        cfg_path = Path(self.config_file)
        parent = cfg_path.parent if cfg_path.parent != Path("") else Path(".")
        parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=f".{cfg_path.name}.", suffix=".tmp", dir=str(parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(cfg_path))
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass

    def restore_window_geometry(self):
        """Restore saved window geometry from profiles.json __meta__ section."""
        try:
            cfg = self._read_config()
            meta = cfg.get('__meta__', {})
            
            # Check window state flags first
            was_maximized = meta.get('was_maximized', False)
            was_fullscreen = meta.get('was_fullscreen', False)
            
            # Only restore saved geometry if NOT maximized/fullscreen
            if not was_maximized and not was_fullscreen:
                # Manually restore size and position instead of using restoreGeometry
                width = meta.get('window_width')
                height = meta.get('window_height')
                x = meta.get('window_x')
                y = meta.get('window_y')
                
                if width and height:
                    # Get screen info to enforce limits
                    screen = QtWidgets.QApplication.primaryScreen()
                    if screen:
                        screen_geometry = screen.availableGeometry()
                        max_width = int(screen_geometry.width() * 0.75)
                        max_height = int(screen_geometry.height() * 0.75)
                        
                        # Enforce 75% width and height limits
                        if width > max_width:
                            width = max_width
                        if height > max_height:
                            height = max_height
                        
                        # Ensure position is valid
                        if x is None or y is None:
                            # Center the window
                            x = screen_geometry.x() + (screen_geometry.width() - width) // 2
                            y = screen_geometry.y() + (screen_geometry.height() - height) // 2
                        
                        # Force the window to be in normal state before setting geometry
                        self.setWindowState(QtCore.Qt.WindowState.WindowNoState)
                        
                        # Simply resize and move - minimum size is already set appropriately in __init__
                        self.resize(width, height)
                        self.move(x, y)
            
            # Explicitly set window state
            if was_fullscreen:
                self.setWindowState(QtCore.Qt.WindowState.WindowFullScreen)
            elif was_maximized:
                self.setWindowState(QtCore.Qt.WindowState.WindowMaximized)
            else:
                # Explicitly ensure normal state
                self.setWindowState(QtCore.Qt.WindowState.WindowNoState)
        except Exception:
            # If restore fails, keep default geometry
            pass

    def save_window_geometry(self):
        """Save window geometry to profiles.json __meta__ section."""
        try:
            cfg = self._read_config()
            if '__meta__' not in cfg:
                cfg['__meta__'] = {}
            
            # Save window state flags (maximized, fullscreen, etc.)
            state = self.windowState()
            is_maximized = bool(state & QtCore.Qt.WindowState.WindowMaximized)
            is_fullscreen = bool(state & QtCore.Qt.WindowState.WindowFullScreen)
            
            cfg['__meta__']['was_maximized'] = is_maximized
            cfg['__meta__']['was_fullscreen'] = is_fullscreen
            
            # Only save geometry if in normal state (not maximized/fullscreen)
            if not is_maximized and not is_fullscreen:
                # Get current screen to enforce 75% limits on save
                screen = QtWidgets.QApplication.primaryScreen()
                if screen:
                    screen_geometry = screen.availableGeometry()
                    max_width = int(screen_geometry.width() * 0.75)
                    max_height = int(screen_geometry.height() * 0.75)
                    
                    # Cap to 75% when saving
                    width = min(self.width(), max_width)
                    height = min(self.height(), max_height)
                    
                    cfg['__meta__']['window_width'] = width
                    cfg['__meta__']['window_height'] = height
                    cfg['__meta__']['window_x'] = self.x()
                    cfg['__meta__']['window_y'] = self.y()
                else:
                    # Fallback if screen not available
                    cfg['__meta__']['window_width'] = self.width()
                    cfg['__meta__']['window_height'] = self.height()
                    cfg['__meta__']['window_x'] = self.x()
                    cfg['__meta__']['window_y'] = self.y()
            
            self._write_config(cfg)
        except Exception:
            pass

    def closeEvent(self, event):
        """Override closeEvent to save window geometry before closing."""
        self._closing = True
        try:
            if hasattr(self, 'api_timer') and self.api_timer is not None:
                self.api_timer.stop()
        except Exception:
            pass
        self.save_window_geometry()
        super().closeEvent(event)

    def load_profiles_from_disk(self, skip_connect: bool = False):
        # Load profiles.json, migrate column definitions if needed,
        # and populate the profile selector.
        cfg = self._read_config()
        # Migrate any existing profiles on disk to ensure the default
        # columns appear first and any newly discovered columns will
        # be appended at the end when profiles are later loaded.
        migrated = self._migrate_profiles_columns(cfg)
        if migrated:
            # Persist the migrated config back to disk so the change is
            # visible on subsequent runs.
            self._write_config(cfg)

        self.profile_list.blockSignals(True); self.profile_list.clear()
        # Populate only profile names (filter out any __meta__ app-level keys)
        profile_names = [k for k in cfg.keys() if not (isinstance(k, str) and k.startswith('__'))]
        self.profile_list.addItems(profile_names)
        self.profile_list.blockSignals(False)
        # Load app-level auto-connect setting if present
        try:
            meta = cfg.get('__meta__', {})
            self.auto_connect_cb.setChecked(bool(meta.get('auto_connect_last', False)))
            saved_url = (meta.get('pingone_console_url', '') or '').strip()
            self._apply_pingone_console_url(saved_url or DEFAULT_PINGONE_CONSOLE_URL, persist=False)
            self.prompt_before_delete = bool(meta.get('prompt_before_delete', True))
        except Exception:
            pass
        if self.profile_list.count() > 0:
            # If auto-connect is enabled and there is a last working profile, select it
            try:
                meta = cfg.get('__meta__', {})
                last = meta.get('last_working_profile')
                if last and last in profile_names and self.auto_connect_cb.isChecked() and not skip_connect:
                    idx = profile_names.index(last)
                    # Block signal-driven duplicate load; perform one explicit load.
                    self.profile_list.blockSignals(True)
                    self.profile_list.setCurrentIndex(idx)
                    self.profile_list.blockSignals(False)
                    self.load_selected_profile()
                    # Delay connect slightly to allow UI/secret load to settle.
                    QtCore.QTimer.singleShot(250, lambda: self._connect_when_secret_ready(last, retries_left=20))
                else:
                    # simply load whichever profile is currently selected (first item)
                    self.load_selected_profile()
            except Exception:
                self.load_selected_profile()

    def _migrate_profiles_columns(self, cfg: dict) -> bool:
        """Migrate saved profile column lists to the new default ordering.

        This ensures the default column order (`self.default_columns`) is
        present at the front of each profile's column list (in that
        order), and appends any other existing columns after them in their
        original relative order. Returns True if any migration occurred.
        """
        if not isinstance(cfg, dict):
            return False
        migrated_any = False
        for name, data in cfg.items():
            cols = data.get('columns') if isinstance(data, dict) else None
            if not cols:
                # Nothing to migrate; initialize with defaults
                data['columns'] = self.default_columns.copy()
                migrated_any = True
                continue

            # Preserve the original relative order of non-default columns.
            remaining = [c for c in cols if c not in self.default_columns]

            # Build new ordered list: defaults first (if present in old
            # columns or to ensure they exist), then the remaining ones.
            new_cols = []
            for d in self.default_columns:
                if d in cols and d not in new_cols:
                    new_cols.append(d)
                elif d not in cols:
                    # If default wasn't present, add it so UUID etc are
                    # available by default for the profile.
                    new_cols.append(d)

            # Append any columns that were present but not part of defaults
            for c in remaining:
                if c not in new_cols:
                    new_cols.append(c)

            if new_cols != cols:
                data['columns'] = new_cols
                migrated_any = True

        return migrated_any

    def load_selected_profile(self, _arg=None):
        """Load the currently selected profile into the config fields.

        Accepts an optional `_arg` because `currentIndexChanged` may emit
        an int or str which Qt will pass to this slot.
        """
        name = self.profile_list.currentText()
        p = self._read_config()
        if name in p:
            if name != self._active_profile_name:
                self._pending_user_tab_refresh = True
                self._active_profile_name = name
            self.env_id.setText(p[name].get("env_id", ""))
            self.cl_id.setText(p[name].get("cl_id", ""))
            try:
                cached_secret = self._get_cached_secret(name)
                if cached_secret is None:
                    if self._was_secret_read_attempted(name):
                        secret = ""
                    else:
                        secret = ""
                        self._start_secret_read(name)
                else:
                    secret = cached_secret
                self.cl_sec.setText(secret)
            except Exception:
                # If keyring backend fails, leave secret blank and continue
                self.cl_sec.setText("")
            # Create a copy of the columns list to avoid shared references
            self.selected_columns = list(p[name].get("columns", self.default_columns.copy()))
            self.column_widths = p[name].get("column_widths", {}).copy()
            # Per-profile option: show live API calls in status bar
            try:
                checked = bool(p[name].get('status_show_api_calls', False))
                self.show_api_calls_cb.setChecked(checked)
                try:
                    api_client.enable_live_capture(checked)
                except Exception:
                    pass
            except Exception:
                pass
            try:
                hide_cols = bool(p[name].get('hide_raw_http_columns', True))
                self.hide_raw_http_columns = hide_cols
                self.hide_raw_http_columns_cb.setChecked(hide_cols)
            except Exception:
                pass
            try:
                show_success = bool(p[name].get('show_user_update_success', True))
                self.show_user_update_success = show_success
                self.show_user_update_success_action.setChecked(show_success)
            except Exception:
                pass
            try:
                self.prompt_before_delete = bool(p[name].get('prompt_before_delete', getattr(self, 'prompt_before_delete', True)))
            except Exception:
                pass
            try:
                msg = f"Profile loaded: {name}"
                try:
                    self._set_processing_message(msg)
                    self.profile_name_label.setText(f"Profile: {name}")
                except Exception:
                    pass
            except Exception:
                pass

    def save_current_profile(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "Save Profile", "Name:")
        if ok and name:
            p = self._read_config()
            p[name] = {"env_id": self.env_id.text(), "cl_id": self.cl_id.text()}
            p[name]["columns"] = self.selected_columns
            p[name]["column_widths"] = self.column_widths
            # Save per-profile UI options
            p[name]['status_show_api_calls'] = bool(getattr(self, 'show_api_calls_cb', QtWidgets.QCheckBox()).isChecked())
            p[name]['hide_raw_http_columns'] = bool(getattr(self, 'hide_raw_http_columns_cb', QtWidgets.QCheckBox()).isChecked())
            p[name]['show_user_update_success'] = bool(getattr(self, 'show_user_update_success_action', QtGui.QAction()).isChecked())
            p[name]['prompt_before_delete'] = bool(getattr(self, 'prompt_before_delete', True))
            # also update last working profile so auto-connect will remember this one
            meta = p.get('__meta__', {})
            meta['last_working_profile'] = name
            p['__meta__'] = meta
            self._write_config(p)
            try:
                self._write_secret_to_keyring(name, self.cl_sec.text())
                self._cache_secret(name, self.cl_sec.text())
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Keyring Error", f"Failed to save client secret to keyring: {e}\n\nCredentials will not be stored persistently.")
            # reload profiles without triggering another connection attempt
            # (saving shouldn't pop up an "Auth Failed" dialog unexpectedly)
            self.load_profiles_from_disk(skip_connect=True)

    def save_app_settings(self):
        """Persist app-level settings (auto-connect, theme) to config file under __meta__."""
        try:
            cfg = self._read_config()
            meta = cfg.get('__meta__', {})
            meta['auto_connect_last'] = bool(self.auto_connect_cb.isChecked())
            meta['theme'] = self.theme_manager.get_current_theme()
            meta['pingone_console_url'] = self.pingone_console_url
            meta['prompt_before_delete'] = bool(getattr(self, 'prompt_before_delete', True))
            cfg['__meta__'] = meta
            self._write_config(cfg)
        except Exception:
            pass

    def save_profile_option(self):
        """Persist per-profile UI options like showing API calls in status bar."""
        try:
            name = self.profile_list.currentText()
            if not name:
                return
            cfg = self._read_config()
            if name not in cfg:
                cfg[name] = {}
            cfg[name]['status_show_api_calls'] = bool(self.show_api_calls_cb.isChecked())
            cfg[name]['hide_raw_http_columns'] = bool(self.hide_raw_http_columns_cb.isChecked())
            cfg[name]['show_user_update_success'] = bool(self.show_user_update_success_action.isChecked())
            cfg[name]['prompt_before_delete'] = bool(getattr(self, 'prompt_before_delete', True))
            self._write_config(cfg)
        except Exception:
            pass

    def on_show_user_update_success_toggled(self, state):
        """Enable/disable success notifications after user update writes."""
        try:
            self.show_user_update_success = bool(state) if isinstance(state, (int, bool)) else bool(self.show_user_update_success_action.isChecked())
            self.save_profile_option()
        except Exception:
            pass

    def _notify_user_update_success(self, user_id: str, field_name: str):
        """Show a small success notification for user updates with mute option."""
        field = str(field_name or '').strip() or '<unknown>'
        msg = f"Updated user {user_id} ({field}) in PingOne."
        try:
            self._set_processing_message(msg, 5000)
        except Exception:
            pass

        if not bool(getattr(self, 'show_user_update_success', True)):
            return

        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Information)
        box.setWindowTitle("Update Succeeded")
        box.setText(msg)
        box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        mute_cb = QtWidgets.QCheckBox("Do not show this again")
        box.setCheckBox(mute_cb)
        box.exec()

        try:
            if mute_cb.isChecked():
                self.show_user_update_success = False
                self.show_user_update_success_action.setChecked(False)
                self.save_profile_option()
        except Exception:
            pass

    def _should_hide_column(self, column_name: str) -> bool:
        """Return True when the current view filter hides the column."""
        if not self.hide_raw_http_columns:
            return False
        name = str(column_name or '').lstrip().lower()
        if name.startswith('{') or name.startswith('http') or name.startswith('['):
            return True

        # Also hide columns whose displayed values are link-like/JSON references.
        # Check the first non-empty value found in the user cache.
        try:
            if self.users_cache:
                for user in self.users_cache[:200]:
                    val = self._get_value(user, column_name)
                    text = str(val or '').lstrip().lower()
                    if not text:
                        continue
                    return text.startswith('{') or text.startswith('http') or text.startswith('[')
        except Exception:
            pass
        return False

    def _get_visible_columns(self, preferred_columns, available_columns):
        """Return ordered columns that exist in data and pass view filters."""
        visible = []
        available = set(available_columns or [])
        for col in preferred_columns or []:
            if col in available and not self._should_hide_column(col):
                visible.append(col)
        return visible

    def on_hide_raw_http_columns_toggled(self, state):
        """Toggle filtering of columns that start with '{' or 'http'."""
        self.hide_raw_http_columns = bool(state)
        self.save_profile_option()
        self.refresh_table()

    def on_show_api_calls_toggled(self, state):
        """Enable or disable live API capture and persist the per-profile choice."""
        try:
            checked = bool(state) if isinstance(state, (int, bool)) else bool(self.show_api_calls_cb.isChecked())
            try:
                api_client.enable_live_capture(checked)
            except Exception:
                pass
            # persist choice
            self.save_profile_option()
        except Exception:
            pass

    def on_item_clicked(self, item):
        """Single-click handler: open edit dialog when clicking UUID or username."""
        try:
            row = item.row(); col = item.column()
            col_name = self.columns[col]
            # Only select the row on single click; do NOT open editor.
            self.u_table.selectRow(row)
        except Exception:
            pass

    def edit_user(self, user_id=None):
        """Open `EditUserDialog` for the selected user and perform update on OK."""
        try:
            if not user_id:
                sel = self.u_table.selectionModel().selectedRows()
                if not sel:
                    QtWidgets.QMessageBox.information(self, "Edit User", "No user selected.")
                    return
                row = sel[0].row()
                id_col = self.columns.index('id') if 'id' in self.columns else -1
                if id_col == -1:
                    return
                user_id = self.u_table.item(row, id_col).text()
            user_obj = next((u for u in self.users_cache if u.get('id') == user_id), None)
            if not user_obj:
                QtWidgets.QMessageBox.information(self, "Edit User", "User not found in cache.")
                return
            dlg = EditUserDialog(user_obj, self.pop_map, self)
            if dlg.exec() != QtWidgets.QDialog.Accepted:
                return
            new_data = self._sanitize_user_update_payload(dlg.get_data())
            # Spawn worker to update user
            client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
            self.prog.show()
            worker = UserUpdateWorker(client, user_id, new_data)

            # Always emit user-management update markers for troubleshooting.
            try:
                req_preview = json.dumps(new_data) if isinstance(new_data, (dict, list)) else str(new_data)
                if len(req_preview) > 3000:
                    req_preview = req_preview[:3000] + '...'
                marker = f"USER_MGMT_EDIT_REQUEST user_id={user_id} field=<dialog> payload={req_preview}"
                api_client.write_connection_log(marker)
                api_client.api_logger.info(marker)
            except Exception:
                pass

            def _on_edit_finished(result):
                try:
                    returned_user = result.get('user') if isinstance(result, dict) else result
                    resp_preview = json.dumps(returned_user) if isinstance(returned_user, (dict, list)) else str(returned_user)
                    if len(resp_preview) > 3000:
                        resp_preview = resp_preview[:3000] + '...'
                    marker = f"USER_MGMT_EDIT_RESPONSE user_id={user_id} field=<dialog> response={resp_preview}"
                    api_client.write_connection_log(marker)
                    api_client.api_logger.info(marker)
                except Exception:
                    pass
                self.prog.hide()
                self.refresh_users()
                changed = []
                try:
                    if isinstance(new_data, dict):
                        changed = sorted([str(k) for k in new_data.keys() if str(k)])
                except Exception:
                    changed = []
                label = ", ".join(changed[:3]) if changed else "dialog"
                if len(changed) > 3:
                    label += ", ..."
                self._notify_user_update_success(user_id, label)

            def _on_edit_error(message):
                try:
                    marker = f"USER_MGMT_EDIT_ERROR user_id={user_id} field=<dialog> error={message}"
                    api_client.write_connection_log(marker)
                    api_client.api_logger.error(marker)
                except Exception:
                    pass
                self.prog.hide()
                QtWidgets.QMessageBox.critical(self, "Error", message)

            worker.signals.finished.connect(_on_edit_finished)
            worker.signals.error.connect(_on_edit_error)
            self.threadpool.start(worker)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Edit User Error", str(e))

    def _poll_api_events(self):
        """Poll `api.client` live events and display them in the UI when enabled for profile."""
        try:
            if getattr(self, '_closing', False) or QtCore.QCoreApplication.closingDown():
                return
            if not hasattr(self, 'profile_list') or not hasattr(self, 'api_calls_label'):
                return
            events = api_client.get_and_clear_live_events()
            if not events:
                return
            # Only display when current profile has enabled the option
            name = self.profile_list.currentText()
            cfg = self._read_config()
            show = False
            if name in cfg:
                show = bool(cfg[name].get('status_show_api_calls', False))
            if show:
                # display most recent event (shortened)
                txt = events[-1]
                if len(txt) > 120:
                    txt = txt[:120] + '...'
                self.api_calls_label.setText(txt)
            else:
                self.api_calls_label.setText("")
        except Exception:
            pass

    # --- THE MISSING SLOT ---
    def refresh_users(self):
        """Fixes the AttributeError by providing the reload function."""
        self._capture_current_column_layout()
        # Create an API client using current UI credentials and start the
        # UserFetchWorker in the shared threadpool so the UI stays responsive.
        client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
        self.prog.show(); self.prog.setRange(0, 0)
        worker = UserFetchWorker(client)
        worker.signals.finished.connect(self.on_fetch_success)
        worker.signals.error.connect(self.on_connection_error)
        QtCore.QThreadPool.globalInstance().start(worker)

    def manage_db_connections(self):
        """Show the DB connections manager and persist any changes.

        The dialog itself does not expose Accept/Reject semantics (it merely has
        a Close button), so we write the updated connections regardless of the
        return value.  The caller can treat changes as authoritative because
        "save" flags and removal logic are handled by the manager itself.
        """
        try:
            cfg = self._read_config()
            dbs = cfg.get('db_connections', {})
            dlg = DBConnectionsManager(dbs.copy(), self)
            dlg.exec()
            # always persist whatever the manager reports (it filters out
            # connections marked not to be saved)
            new = dlg.get_connections()
            cfg['db_connections'] = new
            self._write_config(cfg)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "DB Connections", f"Failed to manage DB connections: {e}")

    def manage_ldap_connections(self):
        """Show LDAP connections manager and persist updates."""
        try:
            cfg = self._read_config()
            conns = cfg.get('ldap_connections', {})
            dlg = LDAPConnectionsManager(conns.copy(), self)
            dlg.exec()
            cfg['ldap_connections'] = dlg.get_connections()
            self._write_config(cfg)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "LDAP Connections", f"Failed to manage LDAP connections: {e}")

    def _save_ldap_connection_settings(self, connection_name: str, updates: dict):
        """Persist additional per-connection LDAP settings."""
        if not connection_name or not updates:
            return
        try:
            cfg = self._read_config()
            conns = cfg.get('ldap_connections', {})
            if connection_name not in conns:
                return
            conns[connection_name].update(updates)
            cfg['ldap_connections'] = conns
            self._write_config(cfg)
        except Exception:
            pass

    def _edit_ldap_connection(self, connection_name: str) -> str:
        """Edit one LDAP connection and persist changes.

        Returns the updated connection name, or the original name if cancelled.
        """
        if not connection_name:
            return connection_name
        try:
            cfg = self._read_config()
            conns = cfg.get('ldap_connections', {})
            if connection_name not in conns:
                return connection_name

            dlg = LDAPConnectionDialog(initial=conns.get(connection_name, {}), parent=self)
            if dlg.exec() != QtWidgets.QDialog.Accepted:
                return connection_name

            new_data = dlg.get_connection_data()
            if not new_data.get('save', True):
                if connection_name in conns:
                    del conns[connection_name]
                    cfg['ldap_connections'] = conns
                    self._write_config(cfg)
                return ''

            new_name = new_data.get('name', '').strip() or connection_name
            if new_name != connection_name and connection_name in conns:
                del conns[connection_name]
            conns[new_name] = new_data
            cfg['ldap_connections'] = conns
            self._write_config(cfg)
            return new_name
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Edit LDAP Connection", str(e))
            return connection_name

    def _create_new_ldap_connection(self) -> str:
        """Create a new LDAP connection using the dialog.
        
        Returns the new connection name if created and saved, empty string otherwise.
        """
        try:
            dlg = LDAPConnectionDialog(initial={}, parent=self)
            if dlg.exec() != QtWidgets.QDialog.Accepted:
                return ''
            
            new_data = dlg.get_connection_data()
            if not new_data.get('save', True):
                return ''
            
            new_name = new_data.get('name', '').strip()
            if not new_name:
                QtWidgets.QMessageBox.warning(self, "Create LDAP Connection", "Connection name cannot be empty.")
                return ''
            
            # Save the new connection
            cfg = self._read_config()
            conns = cfg.get('ldap_connections', {})
            conns[new_name] = new_data
            cfg['ldap_connections'] = conns
            self._write_config(cfg)
            
            return new_name
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Create LDAP Connection", str(e))
            return ''

    def _choose_db_connection(self, title: str = "Select Database Connection"):
        """Choose a database connection with inline Edit/Manage/Create actions.

        Returns ``(name, conns)`` or ``(None, conns)`` when cancelled.
        """
        create_opt = "<Create New Database Connection...>"
        while True:
            cfg = self._read_config()
            conns = cfg.get('db_connections', {})
            
            # Allow creating first connection if none exist
            if not conns:
                create_new = QtWidgets.QMessageBox.question(
                    self,
                    title,
                    "No database connections defined. Would you like to create one now?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                if create_new == QtWidgets.QMessageBox.Yes:
                    new_conn_name = self._create_new_db_connection()
                    if new_conn_name:
                        cfg = self._read_config()
                        conns = cfg.get('db_connections', {})
                        if new_conn_name in conns:
                            return new_conn_name, conns
                return None, conns

            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle(title)
            dlg.setModal(True)
            layout = QtWidgets.QVBoxLayout(dlg)
            layout.addWidget(QtWidgets.QLabel("Connection:"))

            combo = QtWidgets.QComboBox()
            names = [create_opt] + list(conns.keys())
            combo.addItems(names)
            # Select first non-create option by default
            if len(names) > 1:
                combo.setCurrentIndex(1)
            layout.addWidget(combo)

            action = {'value': 'ok'}

            action_row = QtWidgets.QHBoxLayout()
            test_btn = QtWidgets.QPushButton("Test Connection")
            edit_btn = QtWidgets.QPushButton("Edit...")
            remove_btn = QtWidgets.QPushButton("Remove")
            manage_btn = QtWidgets.QPushButton("Manage...")
            action_row.addWidget(test_btn)
            action_row.addWidget(edit_btn)
            action_row.addWidget(remove_btn)
            action_row.addWidget(manage_btn)
            action_row.addStretch()
            layout.addLayout(action_row)

            btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            layout.addWidget(btns)

            def _test_selected():
                """Test the selected database connection."""
                selected = combo.currentText().strip()
                if not selected or selected == create_opt or selected not in conns:
                    QtWidgets.QMessageBox.warning(dlg, "Test Connection", "Please select a valid connection to test.")
                    return
                
                conn = conns[selected]
                try:
                    from api import db_utils
                    ok, err = db_utils.test_connection(
                        conn['type'], conn['host'], conn['port'], 
                        conn['database'], conn['user'], conn['password'], 
                        conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
                    )
                    if ok:
                        QtWidgets.QMessageBox.information(
                            dlg, 
                            "Test Connection", 
                            f"Successfully connected to database '{conn['database']}' on {conn['host']}:{conn['port']}"
                        )
                    else:
                        # Show error and offer to edit connection
                        error_msg = f"Connection test failed.\n\n{err or 'Unknown error'}\n\nWould you like to edit this connection?"
                        reply = QtWidgets.QMessageBox.question(
                            dlg,
                            "Test Connection Failed",
                            error_msg,
                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                        )
                        if reply == QtWidgets.QMessageBox.Yes:
                            action['value'] = 'edit'
                            dlg.accept()
                except ModuleNotFoundError:
                    QtWidgets.QMessageBox.critical(
                        dlg,
                        "Test Connection",
                        "SQLAlchemy is not installed. Please run `pip install -r requirements.txt`."
                    )
                except Exception as e:
                    QtWidgets.QMessageBox.critical(dlg, "Test Connection", f"Test failed: {str(e)}")

            def _edit_selected():
                action['value'] = 'edit'
                dlg.accept()

            def _remove_selected():
                selected = combo.currentText().strip()
                if not selected or selected == create_opt or selected not in conns:
                    QtWidgets.QMessageBox.warning(dlg, "Remove Connection", "Please select a valid connection to remove.")
                    return
                
                reply = QtWidgets.QMessageBox.question(
                    dlg,
                    "Remove Connection",
                    f"Are you sure you want to remove the database connection '{selected}'?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                if reply == QtWidgets.QMessageBox.Yes:
                    action['value'] = 'remove'
                    dlg.accept()

            def _manage_all():
                action['value'] = 'manage'
                dlg.accept()

            test_btn.clicked.connect(_test_selected)
            edit_btn.clicked.connect(_edit_selected)
            remove_btn.clicked.connect(_remove_selected)
            manage_btn.clicked.connect(_manage_all)

            if dlg.exec() != QtWidgets.QDialog.Accepted:
                return None, conns

            selected = combo.currentText().strip()
            
            # Handle create new option
            if selected == create_opt:
                new_conn_name = self._create_new_db_connection()
                if new_conn_name:
                    cfg = self._read_config()
                    conns = cfg.get('db_connections', {})
                    if new_conn_name in conns:
                        return new_conn_name, conns
                continue
            
            if action['value'] == 'manage':
                self.manage_db_connections()
                continue

            if action['value'] == 'edit':
                if selected and selected != create_opt and selected in conns:
                    self._edit_db_connection(selected)
                continue
            
            if action['value'] == 'remove':
                if selected and selected != create_opt and selected in conns:
                    # Remove the connection
                    del conns[selected]
                    cfg['db_connections'] = conns
                    self._write_config(cfg)
                    QtWidgets.QMessageBox.information(self, "Remove Connection", f"Database connection '{selected}' has been removed.")
                continue

            if selected and selected in conns:
                return selected, conns

    def _create_new_db_connection(self) -> str:
        """Create a new database connection using the dialog.
        
        Returns the new connection name if created and saved, empty string otherwise.
        """
        try:
            dlg = DatabaseConnectionDialog(initial={}, parent=self)
            if dlg.exec() != QtWidgets.QDialog.Accepted:
                return ''
            
            new_data = dlg.get_connection_data()
            if not new_data.get('save', True):
                return ''
            
            new_name = new_data.get('name', '').strip()
            if not new_name:
                QtWidgets.QMessageBox.warning(self, "Create Database Connection", "Connection name cannot be empty.")
                return ''
            
            # Save the new connection
            cfg = self._read_config()
            conns = cfg.get('db_connections', {})
            conns[new_name] = new_data
            cfg['db_connections'] = conns
            self._write_config(cfg)
            
            return new_name
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Create Database Connection", str(e))
            return ''

    def _edit_db_connection(self, connection_name: str) -> str:
        """Edit one database connection and persist changes.

        Returns the updated connection name, or the original name if cancelled.
        """
        if not connection_name:
            return connection_name
        try:
            cfg = self._read_config()
            conns = cfg.get('db_connections', {})
            if connection_name not in conns:
                return connection_name

            dlg = DatabaseConnectionDialog(initial=conns.get(connection_name, {}), parent=self)
            if dlg.exec() != QtWidgets.QDialog.Accepted:
                return connection_name

            new_data = dlg.get_connection_data()
            if not new_data.get('save', True):
                if connection_name in conns:
                    del conns[connection_name]
                    cfg['db_connections'] = conns
                    self._write_config(cfg)
                return ''

            new_name = new_data.get('name', '').strip() or connection_name
            if new_name != connection_name and connection_name in conns:
                del conns[connection_name]
            conns[new_name] = new_data
            cfg['db_connections'] = conns
            self._write_config(cfg)
            return new_name
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Database Connection", f"Failed to edit database connection: {e}")
            return connection_name

    def _choose_ldap_connection(self, title: str = "Select LDAP Connection"):
        """Choose an LDAP connection with inline Edit/Manage/Create actions.

        Returns ``(name, conns)`` or ``(None, conns)`` when cancelled.
        """
        create_opt = "<Create New LDAP Connection...>"
        while True:
            cfg = self._read_config()
            conns = cfg.get('ldap_connections', {})
            
            # Allow creating first connection if none exist
            if not conns:
                create_new = QtWidgets.QMessageBox.question(
                    self,
                    title,
                    "No LDAP connections defined. Would you like to create one now?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                if create_new == QtWidgets.QMessageBox.Yes:
                    new_conn_name = self._create_new_ldap_connection()
                    if new_conn_name:
                        cfg = self._read_config()
                        conns = cfg.get('ldap_connections', {})
                        if new_conn_name in conns:
                            return new_conn_name, conns
                return None, conns

            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle(title)
            dlg.setModal(True)
            layout = QtWidgets.QVBoxLayout(dlg)
            layout.addWidget(QtWidgets.QLabel("Connection:"))

            combo = QtWidgets.QComboBox()
            names = [create_opt] + list(conns.keys())
            combo.addItems(names)
            # Select first non-create option by default
            if len(names) > 1:
                combo.setCurrentIndex(1)
            layout.addWidget(combo)

            action = {'value': 'ok'}

            action_row = QtWidgets.QHBoxLayout()
            test_btn = QtWidgets.QPushButton("Test Connection")
            edit_btn = QtWidgets.QPushButton("Edit...")
            remove_btn = QtWidgets.QPushButton("Remove")
            manage_btn = QtWidgets.QPushButton("Manage...")
            action_row.addWidget(test_btn)
            action_row.addWidget(edit_btn)
            action_row.addWidget(remove_btn)
            action_row.addWidget(manage_btn)
            action_row.addStretch()
            layout.addLayout(action_row)

            btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            layout.addWidget(btns)

            def _test_selected():
                """Test the selected LDAP connection."""
                selected = combo.currentText().strip()
                if not selected or selected == create_opt or selected not in conns:
                    QtWidgets.QMessageBox.warning(dlg, "Test Connection", "Please select a valid connection to test.")
                    return
                
                conn = conns[selected]
                try:
                    from api import ldap_utils
                    ok, err = ldap_utils.test_connection(
                        conn.get('host', ''),
                        int(conn.get('port', 0) or 0),
                        bool(conn.get('use_ssl', False)),
                        conn.get('bind_dn', ''),
                        conn.get('password', ''),
                        conn.get('base_dn', ''),
                        bool(conn.get('start_tls', False)),
                        timeout=int(conn.get('timeout', 30) or 30),
                    )
                    if ok:
                        QtWidgets.QMessageBox.information(
                            dlg,
                            "Test Connection",
                            f"Successfully connected to LDAP server '{conn.get('host', '')}' \nBase DN: {conn.get('base_dn', '')}"
                        )
                    else:
                        # Show error and offer to edit connection
                        error_msg = f"Connection test failed.\n\n{err or 'Unknown error'}\n\nWould you like to edit this connection?"
                        reply = QtWidgets.QMessageBox.question(
                            dlg,
                            "Test Connection Failed",
                            error_msg,
                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                        )
                        if reply == QtWidgets.QMessageBox.Yes:
                            action['value'] = 'edit'
                            dlg.accept()
                except ModuleNotFoundError:
                    QtWidgets.QMessageBox.critical(
                        dlg,
                        "Test Connection",
                        "ldap3 is not installed. Please run `pip install -r requirements.txt`."
                    )
                except Exception as e:
                    QtWidgets.QMessageBox.critical(dlg, "Test Connection", f"Test failed: {str(e)}")

            def _edit_selected():
                action['value'] = 'edit'
                dlg.accept()

            def _remove_selected():
                selected = combo.currentText().strip()
                if not selected or selected == create_opt or selected not in conns:
                    QtWidgets.QMessageBox.warning(dlg, "Remove Connection", "Please select a valid connection to remove.")
                    return
                
                reply = QtWidgets.QMessageBox.question(
                    dlg,
                    "Remove Connection",
                    f"Are you sure you want to remove the LDAP connection '{selected}'?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                if reply == QtWidgets.QMessageBox.Yes:
                    action['value'] = 'remove'
                    dlg.accept()

            def _manage_all():
                action['value'] = 'manage'
                dlg.accept()

            test_btn.clicked.connect(_test_selected)
            edit_btn.clicked.connect(_edit_selected)
            remove_btn.clicked.connect(_remove_selected)
            manage_btn.clicked.connect(_manage_all)

            if dlg.exec() != QtWidgets.QDialog.Accepted:
                return None, conns

            selected = combo.currentText().strip()
            
            # Handle create new option
            
            if action['value'] == 'remove':
                if selected and selected != create_opt and selected in conns:
                    # Remove the connection
                    del conns[selected]
                    cfg['ldap_connections'] = conns
                    self._write_config(cfg)
                    QtWidgets.QMessageBox.information(self, "Remove Connection", f"LDAP connection '{selected}' has been removed.")
                continue
            if selected == create_opt:
                new_conn_name = self._create_new_ldap_connection()
                if new_conn_name:
                    cfg = self._read_config()
                    conns = cfg.get('ldap_connections', {})
                    if new_conn_name in conns:
                        return new_conn_name, conns
                continue
            
            if action['value'] == 'manage':
                self.manage_ldap_connections()
                continue

            if action['value'] == 'edit':
                if selected and selected != create_opt and selected in conns:
                    self._edit_ldap_connection(selected)
                continue

            if selected and selected in conns:
                return selected, conns

    def import_from_ldap_directory_wizard(self, connection_name: str):
        """Import users from a selected LDAP connection (wizard entry point)."""
        try:
            cfg = self._read_config()
            conns = cfg.get('ldap_connections', {})
            if not connection_name or connection_name not in conns:
                QtWidgets.QMessageBox.critical(self, "Import LDAP", "Connection not found.")
                return
            
            conn = conns[connection_name]
            
            # Offer to test connection before proceeding
            test_msg = QtWidgets.QMessageBox(self)
            test_msg.setWindowTitle("Import from LDAP")
            test_msg.setText(f"Ready to import from LDAP connection: {connection_name}")
            test_msg.setInformativeText("Would you like to test the connection before proceeding?")
            test_msg.setStandardButtons(
                QtWidgets.QMessageBox.Yes | 
                QtWidgets.QMessageBox.No | 
                QtWidgets.QMessageBox.Cancel
            )
            test_msg.button(QtWidgets.QMessageBox.Yes).setText("Test Connection")
            test_msg.button(QtWidgets.QMessageBox.No).setText("Skip Test")
            test_msg.setDefaultButton(QtWidgets.QMessageBox.No)
            
            test_choice = test_msg.exec()
            
            if test_choice == QtWidgets.QMessageBox.Cancel:
                return
            elif test_choice == QtWidgets.QMessageBox.Yes:
                # Test the connection
                try:
                    from api import ldap_utils
                    ok, err = ldap_utils.test_connection(
                        conn.get('host', ''),
                        int(conn.get('port', 0) or 0),
                        bool(conn.get('use_ssl', False)),
                        conn.get('bind_dn', ''),
                        conn.get('password', ''),
                        conn.get('base_dn', ''),
                        bool(conn.get('start_tls', False)),
                        timeout=int(conn.get('timeout', 30) or 30),
                    )
                    if ok:
                        QtWidgets.QMessageBox.information(
                            self,
                            "Test Connection",
                            f"Successfully connected to LDAP server '{conn.get('host', '')}'\nBase DN: {conn.get('base_dn', '')}"
                        )
                    else:
                        # Show error and offer to edit connection
                        error_msg = f"Connection test failed.\n\n{err or 'Unknown error'}\n\nWould you like to edit this connection?"
                        reply = QtWidgets.QMessageBox.question(
                            self,
                            "Test Connection Failed",
                            error_msg,
                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                        )
                        if reply == QtWidgets.QMessageBox.Yes:
                            self._edit_ldap_connection(connection_name)
                            # After editing, ask if they want to retry
                            retry = QtWidgets.QMessageBox.question(
                                self,
                                "Continue Import",
                                "Connection edited. Would you like to continue with the import?",
                                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                            )
                            if retry != QtWidgets.QMessageBox.Yes:
                                return
                            # Reload connection after edit
                            cfg = self._read_config()
                            conns = cfg.get('ldap_connections', {})
                            if connection_name not in conns:
                                QtWidgets.QMessageBox.warning(self, "Import LDAP", "Connection no longer exists.")
                                return
                            conn = conns[connection_name]
                        else:
                            return
                except ModuleNotFoundError:
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Test Connection",
                        "ldap3 is not installed. Please run `pip install -r requirements.txt`."
                    )
                    return
                except Exception as e:
                    QtWidgets.QMessageBox.critical(self, "Test Connection", f"Test failed: {str(e)}")
                    return
            
            # Prompt for filter mode (moved outside the test connection block to ensure it always runs)
            try:
                # Debug: Log that we're about to show filter dialog
                import api.client as _api_client
                _api_client.write_connection_log(f"LDAP Import: About to show filter mode dialog for connection {connection_name}")
            except Exception:
                pass
            
            try:
                filter_mode, ok = QtWidgets.QInputDialog.getItem(
                    self,
                    "Import Filter",
                    "Import using:",
                    ["Default Filter", "Custom Filter"],
                    editable=False,
                )
                if not ok or not filter_mode:
                    try:
                        import api.client as _api_client
                        _api_client.write_connection_log(f"LDAP Import: User cancelled filter mode dialog (ok={ok}, filter_mode={filter_mode})")
                    except Exception:
                        pass
                    return
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Import Filter Error", f"Failed to prompt for filter: {str(e)}")
                return
            
            custom_filter = None
            filter_saved = False
            if filter_mode == "Custom Filter":
                custom_filter, filter_saved = self._prompt_custom_ldap_filter_from_connection(conn, connection_name)
                if not custom_filter:
                    return
            
            self._import_from_ldap_connection(connection_name, conn, custom_filter, filter_saved)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import LDAP", str(e))

    def import_from_ldap_directory(self):
        """Initiate import flow from an LDAP directory."""
        try:
            name, conns = self._choose_ldap_connection("Select LDAP Connection")
            if not name:
                return
            
            conn = conns[name]
            
            # Prompt for filter mode similar to database import
            filter_mode, ok = QtWidgets.QInputDialog.getItem(
                self,
                "Import Filter",
                "Import using:",
                ["Default Filter", "Custom Filter"],
                editable=False,
            )
            if not ok or not filter_mode:
                return
            
            custom_filter = None
            filter_saved = False
            if filter_mode == "Custom Filter":
                custom_filter, filter_saved = self._prompt_custom_ldap_filter_from_connection(conn, name)
                if not custom_filter:
                    return
            
            self._import_from_ldap_connection(name, conn, custom_filter, filter_saved)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import LDAP", str(e))

    def _import_from_ldap_connection(self, connection_name: str, conn: dict, custom_filter: str = None, filter_saved: bool = False):
        """Import users from an LDAP connection using the mapping dialog flow."""
        try:
            from api import ldap_utils
        except ModuleNotFoundError:
            QtWidgets.QMessageBox.critical(
                self,
                "Import LDAP",
                "ldap3 is not installed. Please run `pip install -r requirements.txt`."
            )
            return

        ok, err = ldap_utils.test_connection(
            conn.get('host', ''),
            int(conn.get('port', 0) or 0),
            bool(conn.get('use_ssl', False)),
            conn.get('bind_dn', ''),
            conn.get('password', ''),
            conn.get('base_dn', ''),
            bool(conn.get('start_tls', False)),
            timeout=int(conn.get('timeout', 30) or 30),
        )
        if not ok:
            QtWidgets.QMessageBox.critical(self, "Import LDAP", f"Unable to connect with provided settings.\n\n{err or ''}")
            return

        # Use custom filter if provided, otherwise use default filter from connection
        if custom_filter:
            search_filter = custom_filter
        else:
            search_filter = conn.get('search_filter', '(objectClass=person)') or '(objectClass=person)'
        
        try:
            # Show progress dialog while reading LDAP
            progress = QtWidgets.QProgressDialog(
                "Reading entries from LDAP directory...",
                "Cancel",
                0, 0,
                self
            )
            progress.setWindowTitle("Import from LDAP")
            progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(500)  # Show after 500ms
            progress.setValue(0)
            QtWidgets.QApplication.processEvents()
            
            rows = ldap_utils.get_entries(
                conn.get('host', ''),
                int(conn.get('port', 0) or 0),
                bool(conn.get('use_ssl', False)),
                conn.get('bind_dn', ''),
                conn.get('password', ''),
                conn.get('base_dn', ''),
                search_filter=search_filter,
                attributes=None,
                limit=None,
                start_tls=bool(conn.get('start_tls', False)),
                timeout=int(conn.get('timeout', 30) or 30),
            )
            
            progress.close()
        except Exception as e:
            progress.close()
            QtWidgets.QMessageBox.critical(self, "Import LDAP", f"Failed to read LDAP entries: {e}")
            return

        if not rows:
            QtWidgets.QMessageBox.information(self, "Import LDAP", "No matching LDAP entries were found.")
            return
        
        # Show status message with entry count
        self._set_processing_message(f"Read {len(rows)} entries from LDAP directory", 5000)

        # Discover populated attributes from first 10 entries
        source_fields = self._discover_populated_attributes_from_entries(rows, max_sample=10)
        sample = rows[0] if rows else {}

        client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
        pops = {}
        try:
            token = asyncio.run(client.get_token())
            if token:
                pops, _ = asyncio.run(client.get_populations())
        except Exception:
            pass

        ping_attrs = self._get_pingone_attributes_for_import(client)
        initial_mapping = conn.get('ldap_import_mapping', {})
        # If using a custom filter, check for filter-specific mapping
        if custom_filter:
            by_filter = conn.get('ldap_import_mappings_by_filter', {}) or {}
            if custom_filter in by_filter:
                initial_mapping = by_filter.get(custom_filter, initial_mapping)
        dlg = LDAPMappingDialog(
            source_fields,
            ping_attrs,
            direction='import',
            sample_row=sample,
            initial_mapping=initial_mapping,
            parent=self,
        )
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return

        mapping = dlg.get_mapping()
        if not mapping:
            QtWidgets.QMessageBox.information(self, "Import LDAP", "No attributes were mapped; import cancelled.")
            return
        if dlg.remember_mapping() or (custom_filter and filter_saved):
            updates = {'ldap_import_mapping': mapping}
            # If using a saved custom filter, save the mapping for this specific filter
            if custom_filter and filter_saved:
                by_filter = dict(conn.get('ldap_import_mappings_by_filter', {}) or {})
                by_filter[custom_filter] = mapping
                updates['ldap_import_mappings_by_filter'] = by_filter
            self._save_ldap_connection_settings(connection_name, updates)

        users = self._convert_rows_to_users(rows, mapping, client, pops)
        # Update data source to include filter info
        if custom_filter:
            self._set_last_data_source(f"LDAP {connection_name}: custom filter")
        else:
            self._set_last_data_source(f"LDAP {connection_name}: {conn.get('base_dn', '')}")
        
        # Prompt for population selection
        if not pops:
            pops, default_pop_id = asyncio.run(client.get_populations())
        else:
            # Get default population even if we already have pops
            try:
                _, default_pop_id = asyncio.run(client.get_populations())
            except Exception:
                default_pop_id = None
        
        fixed_pop_id = None
        if pops:
            # Create population selection dialog
            pop_dlg = QtWidgets.QDialog(self)
            pop_dlg.setWindowTitle("Select Population for Import")
            pop_layout = QtWidgets.QVBoxLayout(pop_dlg)
            
            pop_layout.addWidget(QtWidgets.QLabel("Assign all imported users to a population:"))
            
            # Combo box and refresh button in horizontal layout
            pop_combo_layout = QtWidgets.QHBoxLayout()
            pop_combo = QtWidgets.QComboBox()
            pop_combo.addItem("<Use population from data>", None)
            for pop_name, pop_id in sorted(pops.items()):
                pop_combo.addItem(pop_name, pop_id)
            pop_combo_layout.addWidget(pop_combo)
            
            # Set default to the environment's default population if one exists
            if default_pop_id:
                idx = pop_combo.findData(default_pop_id)
                if idx != -1:
                    pop_combo.setCurrentIndex(idx)
            
            refresh_pop_btn = QtWidgets.QPushButton("Refresh")
            refresh_pop_btn.setToolTip("Query PingOne for updated population list")
            
            def refresh_populations():
                nonlocal default_pop_id
                try:
                    QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
                    current_selection = pop_combo.currentData()
                    token = asyncio.run(client.get_token())
                    if token:
                        new_pops, new_default_pop_id = asyncio.run(client.get_populations())
                        pops.clear()
                        pops.update(new_pops or {})
                        default_pop_id = new_default_pop_id
                        
                        # Rebuild combo
                        pop_combo.clear()
                        pop_combo.addItem("<Use population from data>", None)
                        for pop_name, pop_id in sorted(pops.items()):
                            pop_combo.addItem(pop_name, pop_id)
                        
                        # Restore selection if still exists, otherwise use default
                        if current_selection:
                            idx = pop_combo.findData(current_selection)
                            if idx != -1:
                                pop_combo.setCurrentIndex(idx)
                            elif default_pop_id:
                                # Selection no longer exists, use default
                                idx = pop_combo.findData(default_pop_id)
                                if idx != -1:
                                    pop_combo.setCurrentIndex(idx)
                        elif default_pop_id:
                            # No previous selection, use default
                            idx = pop_combo.findData(default_pop_id)
                            if idx != -1:
                                pop_combo.setCurrentIndex(idx)
                        
                        QtWidgets.QMessageBox.information(
                            pop_dlg,
                            "Refresh Populations",
                            f"Successfully refreshed. Found {len(pops)} population(s)."
                        )
                    else:
                        QtWidgets.QMessageBox.warning(
                            pop_dlg,
                            "Refresh Populations",
                            "Failed to authenticate with PingOne."
                        )
                except Exception as e:
                    QtWidgets.QMessageBox.critical(
                        pop_dlg,
                        "Refresh Populations",
                        f"Failed to refresh: {str(e)}"
                    )
                finally:
                    QtWidgets.QApplication.restoreOverrideCursor()
            
            refresh_pop_btn.clicked.connect(refresh_populations)
            pop_combo_layout.addWidget(refresh_pop_btn)
            
            pop_layout.addLayout(pop_combo_layout)
            
            pop_btns = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
            )
            pop_btns.accepted.connect(pop_dlg.accept)
            pop_btns.rejected.connect(pop_dlg.reject)
            pop_layout.addWidget(pop_btns)
            
            if pop_dlg.exec() == QtWidgets.QDialog.Accepted:
                fixed_pop_id = pop_combo.currentData()
            else:
                return  # User cancelled
        
        self._perform_import_sequence(users, client, pops, fixed_pop_id=fixed_pop_id)

    def export_to_ldap_directory(self):
        """Initiate export flow from PingOne users to LDAP entries."""
        if not self.users_cache:
            QtWidgets.QMessageBox.information(self, "Export LDAP", "No users to export.")
            return
        try:
            name, conns = self._choose_ldap_connection("Select LDAP Connection")
            if not name:
                return
            conn = conns[name]

            try:
                from api import ldap_utils
            except ModuleNotFoundError:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Export LDAP",
                    "ldap3 is not installed. Please run `pip install -r requirements.txt`."
                )
                return

            ok, err = ldap_utils.test_connection(
                conn.get('host', ''),
                int(conn.get('port', 0) or 0),
                bool(conn.get('use_ssl', False)),
                conn.get('bind_dn', ''),
                conn.get('password', ''),
                conn.get('base_dn', ''),
                bool(conn.get('start_tls', False)),
                timeout=int(conn.get('timeout', 30) or 30),
            )
            if not ok:
                QtWidgets.QMessageBox.critical(self, "Export LDAP", f"Unable to connect with provided settings.\n\n{err or ''}")
                return

            profile_name = self.profile_list.currentText()
            prefer_selected = True
            only_visible_default = True
            try:
                cfg = self._read_config()
                if profile_name and profile_name in cfg:
                    prefer_selected = cfg[profile_name].get('export_prefer_selected', prefer_selected)
                    only_visible_default = cfg[profile_name].get('export_only_visible_columns', only_visible_default)
            except Exception:
                pass

            selected = self.u_table.selectionModel().selectedRows()
            from ui.dialogs import ExportOptionsDialog
            populated_attrs = self._get_populated_export_attributes(self.users_cache)
            populated_attr_samples = self._get_populated_export_attribute_samples(self.users_cache, populated_attrs)
            metadata_cols = self._get_metadata_columns(self.users_cache)
            
            # Load saved excluded metadata and selected populations from profile
            excluded_metadata = []
            selected_populations = []
            try:
                cfg = self._read_config()
                if profile_name and profile_name in cfg:
                    excluded_metadata = cfg[profile_name].get('export_excluded_metadata', [])
                    selected_populations = cfg[profile_name].get('export_selected_populations', [])
            except Exception:
                pass
            
            export_dlg = ExportOptionsDialog(
                bool(selected),
                only_visible_default,
                prefer_selected,
                self,
                populated_attributes=populated_attrs,
                populated_attribute_samples=populated_attr_samples,
                metadata_columns=metadata_cols,
                excluded_metadata=excluded_metadata,
                populations=self.pop_map,
                selected_populations=selected_populations,
            )
            if export_dlg.exec() != QtWidgets.QDialog.Accepted:
                return
            opts = export_dlg.get_options()
            
            # Persist choices if requested
            if opts.get('remember') and profile_name:
                try:
                    cfg = self._read_config()
                    if profile_name not in cfg:
                        cfg[profile_name] = {}
                    cfg[profile_name]['export_prefer_selected'] = (opts.get('rows') == 'selected')
                    cfg[profile_name]['export_only_visible_columns'] = bool(opts.get('only_visible_columns'))
                    cfg[profile_name]['export_excluded_metadata'] = opts.get('excluded_metadata', [])
                    cfg[profile_name]['export_selected_populations'] = opts.get('selected_populations', [])
                    self._write_config(cfg)
                except Exception:
                    pass

            if opts.get('rows') == 'selected' and selected:
                id_col = self.columns.index('id') if 'id' in self.columns else -1
                if id_col != -1:
                    ids = [self.u_table.item(r.row(), id_col).text() for r in selected]
                    export_users = [u for u in self.users_cache if u.get('id') in ids]
                else:
                    export_users = list(self.users_cache)
            else:
                export_users = list(self.users_cache)

            required_attrs = opts.get('required_populated_attributes') or []
            filtered_out = 0
            if required_attrs:
                export_users, filtered_out = self._filter_users_by_populated_attributes(export_users, required_attrs)

            # Filter by selected populations
            selected_populations_filter = opts.get('selected_populations', [])
            pop_filtered_out = 0
            if selected_populations_filter:
                export_users, pop_filtered_out = self._filter_users_by_populations(export_users, selected_populations_filter)

            sample_entry = None
            ldap_attrs = [
                'uid', 'cn', 'sn', 'givenName', 'mail', 'userPrincipalName',
                'telephoneNumber', 'mobile', 'displayName', 'description'
            ]
            try:
                sample_entry = ldap_utils.get_entry_sample(
                    conn.get('host', ''),
                    int(conn.get('port', 0) or 0),
                    bool(conn.get('use_ssl', False)),
                    conn.get('bind_dn', ''),
                    conn.get('password', ''),
                    conn.get('base_dn', ''),
                    search_filter=conn.get('search_filter', '(objectClass=person)') or '(objectClass=person)',
                    start_tls=bool(conn.get('start_tls', False)),
                    timeout=int(conn.get('timeout', 30) or 30),
                )
                if sample_entry:
                    ldap_attrs = sorted(set(ldap_attrs).union({k for k in sample_entry.keys() if k and str(k).lower() != 'dn'}))
            except Exception:
                pass

            all_ping_attrs = self._get_pingone_attributes()
            required_ping_attrs = {'username', 'email', 'name.given', 'name.family'}
            # PingOne read-only / internal fields that must never be written to an LDAP schema
            _pingone_ldap_blocked = {
                'id', 'createdAt', 'updatedAt', 'account.status', 'mfaEnabled',
                '_links', 'lifecycle.status', 'identityProvider.type',
                'identityProvider.id',
            }
            
            # Apply export options to filter PingOne attributes
            if opts.get('only_visible_columns'):
                # Use only visible columns
                visible_ping_attrs = set()
                try:
                    for idx, col in enumerate(self.columns or []):
                        if idx < self.u_table.columnCount() and not self.u_table.isColumnHidden(idx):
                            visible_ping_attrs.add(str(col))
                except Exception:
                    visible_ping_attrs = set(self.columns or [])
                allowed_ping_attrs = required_ping_attrs.union(visible_ping_attrs)
            else:
                # Use all attributes
                allowed_ping_attrs = set(all_ping_attrs)
            
            # Filter out excluded metadata and blocked fields
            excluded_metadata_set = set(opts.get('excluded_metadata', []))
            ping_attrs = [
                a for a in all_ping_attrs
                if a in allowed_ping_attrs
                and not str(a).lower().startswith('population.')
                and str(a) not in _pingone_ldap_blocked
                and str(a) not in excluded_metadata_set
            ]
            for req in sorted(required_ping_attrs):
                if req not in ping_attrs:
                    ping_attrs.append(req)

            sample_p1 = {}
            try:
                if export_users:
                    sample_p1 = self._flatten_user(export_users[0])
            except Exception:
                sample_p1 = {}

            initial_mapping = conn.get('ldap_export_mapping', {})
            map_dlg = LDAPMappingDialog(
                ldap_attrs,
                ping_attrs,
                direction='export',
                sample_row=sample_p1,
                initial_mapping=initial_mapping,
                parent=self,
            )
            if map_dlg.exec() != QtWidgets.QDialog.Accepted:
                return
            mapping = map_dlg.get_mapping()
            if not mapping:
                QtWidgets.QMessageBox.information(self, "Export LDAP", "No attributes were mapped; export cancelled.")
                return
            if map_dlg.remember_mapping():
                self._save_ldap_connection_settings(name, {'ldap_export_mapping': mapping})

            rdn_attr = (conn.get('rdn_attribute', 'uid') or 'uid').strip()
            rdn_aliases = {
                'username': 'uid',
                'email': 'mail',
                'population.name': 'ou',
                'population.id': 'employeeNumber',
            }
            rdn_attr = rdn_aliases.get(str(rdn_attr).lower(), rdn_attr)
            object_classes = conn.get('object_classes') or ['top', 'person', 'organizationalPerson', 'inetOrgPerson']
            
            # Start TPS tracking
            tracker = TPSTracker()
            tracker.start()
            
            entries = []
            skipped = 0
            for user in export_users:
                flat = self._flatten_user(user)
                attrs = {}
                for ping_attr, ldap_attr in mapping.items():
                    # Never write PingOne-internal system fields to LDAP entries
                    if str(ping_attr) in _pingone_ldap_blocked:
                        continue
                    # Guard against LDAP target literally named 'id' (not a valid schema attr)
                    if str(ldap_attr).strip().lower() == 'id':
                        continue
                    val = flat.get(ping_attr)
                    if val is None or val == '':
                        continue
                    attrs[ldap_attr] = val

                rdn_value = attrs.get(rdn_attr) or flat.get('username') or flat.get('email')
                if not rdn_value:
                    skipped += 1
                    continue
                base_dn = (conn.get('base_dn', '') or '').strip()
                dn = f"{rdn_attr}={rdn_value},{base_dn}" if base_dn else f"{rdn_attr}={rdn_value}"
                entries.append({'dn': dn, 'attributes': attrs, 'object_classes': object_classes})
                tracker.record_transaction()

            if not entries:
                QtWidgets.QMessageBox.information(self, "Export LDAP", "No exportable users found after mapping.")
                return

            result = ldap_utils.upsert_entries(
                conn.get('host', ''),
                int(conn.get('port', 0) or 0),
                bool(conn.get('use_ssl', False)),
                conn.get('bind_dn', ''),
                conn.get('password', ''),
                entries,
                start_tls=bool(conn.get('start_tls', False)),
                timeout=int(conn.get('timeout', 30) or 30),
                auto_create_parents=bool(conn.get('auto_create_parents', True)),
            )
            
            # Finish tracking and get statistics
            tracker.finish()
            tps_stats = tracker.get_statistics()

            summary = f"Created {result.get('created', 0)}, updated {result.get('updated', 0)} LDAP entries"
            if skipped:
                summary += f"; skipped {skipped} users without {rdn_attr}"
            if filtered_out:
                summary += f"; filtered out {filtered_out} users by populated-attribute filter"
            if pop_filtered_out:
                summary += f"; filtered out {pop_filtered_out} users by population filter"
            errors = result.get('errors', []) or []
            if errors:
                dlg = QtWidgets.QDialog(self)
                dlg.setWindowTitle("Export LDAP Result")
                lay = QtWidgets.QVBoxLayout(dlg)
                lay.addWidget(QtWidgets.QLabel(summary))
                te = QtWidgets.QTextEdit()
                te.setReadOnly(True)
                te.setPlainText('\n'.join(errors))
                lay.addWidget(te)
                btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
                btns.accepted.connect(dlg.accept)
                lay.addWidget(btns)
                dlg.resize(820, 460)
                dlg.exec()
            else:
                QtWidgets.QMessageBox.information(self, "Export LDAP", summary)

            self._set_last_data_source(f"LDAP {name}: {conn.get('base_dn', '')}")
            try:
                self._set_processing_message(summary)
            except Exception:
                pass
            
            # Show TPS report
            self._show_tps_report(tps_stats, "LDAP Export")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export LDAP", str(e))

    def import_from_database(self):
        """Initiate import flow from a database table."""
        try:
            # Use the new connection chooser with create option
            name, dbs = self._choose_db_connection("Select Database Connection for Import")
            if not name:
                return
            conn = dbs[name]

            source_mode, ok = QtWidgets.QInputDialog.getItem(
                self,
                "Import Source",
                "Import from:",
                ["Table", "Custom Query"],
                editable=False,
            )
            if not ok or not source_mode:
                return

            query_text = None
            query_saved = False
            table = None
            if source_mode == "Custom Query":
                query_text, query_saved = self._prompt_custom_query_from_connection(conn, name)
                if not query_text:
                    return
            else:
                table = self._prompt_import_table_from_connection(conn, name)
                if not table:
                    return
            # test connection
            try:
                from api import db_utils
            except ModuleNotFoundError:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Import DB",
                    "SQLAlchemy is not installed. Please run `pip install -r requirements.txt`."
                )
                return

            ok, _ = db_utils.test_connection(conn['type'], conn['host'], conn['port'], conn['database'], conn['user'], conn['password'], conn.get('driver'), encrypt_mode=conn.get('encrypt_mode'))
            if not ok:
                QtWidgets.QMessageBox.critical(self, "Import DB", "Unable to connect with provided credentials.")
                return
            # fetch columns and discover populated attributes from first 10 rows
            try:
                if source_mode == "Custom Query":
                    cols = db_utils.get_query_columns(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], query_text, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
                    )
                    # Get first 10 rows to discover populated attributes
                    try:
                        sample_rows = db_utils.get_query_rows(
                            conn['type'], conn['host'], conn['port'], conn['database'],
                            conn['user'], conn['password'], query_text, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode'),
                            limit=10
                        )
                        cols = self._discover_populated_attributes_from_entries(sample_rows, max_sample=10) if sample_rows else cols
                        sample = sample_rows[0] if sample_rows else {}
                    except Exception:
                        # Fall back to single sample
                        sample = db_utils.get_query_sample(
                            conn['type'], conn['host'], conn['port'], conn['database'],
                            conn['user'], conn['password'], query_text, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
                        )
                else:
                    cols = db_utils.get_table_columns(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], table, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
                    )
                    # Get first 10 rows to discover populated attributes
                    try:
                        sample_rows = db_utils.get_table_rows(
                            conn['type'], conn['host'], conn['port'], conn['database'],
                            conn['user'], conn['password'], table, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode'),
                            limit=10
                        )
                        cols = self._discover_populated_attributes_from_entries(sample_rows, max_sample=10) if sample_rows else cols
                        sample = sample_rows[0] if sample_rows else {}
                    except Exception:
                        # Fall back to single sample
                        sample = db_utils.get_table_sample(
                            conn['type'], conn['host'], conn['port'], conn['database'],
                            conn['user'], conn['password'], table, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
                        )
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Import DB", f"Failed to read table metadata: {e}")
                return
            client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
            ping_attrs = self._get_pingone_attributes_for_import(client)
            initial_mapping = conn.get('db_import_mapping', {})
            if source_mode == "Custom Query" and query_text:
                by_query = conn.get('db_import_mappings_by_query', {}) or {}
                if query_text in by_query:
                    initial_mapping = by_query.get(query_text, initial_mapping)
            dlg = DatabaseMappingDialog(
                cols,
                ping_attrs,
                direction='import',
                sample_row=sample,
                initial_mapping=initial_mapping,
                parent=self,
            )
            if dlg.exec() == QtWidgets.QDialog.Accepted:
                mapping = dlg.get_mapping()
                if not mapping:
                    QtWidgets.QMessageBox.information(self, "Import DB", "No columns were mapped; import cancelled.")
                    return
                if dlg.remember_mapping() or (source_mode == "Custom Query" and query_saved):
                    updates = {'db_import_mapping': mapping}
                    if source_mode == "Custom Query" and query_saved and query_text:
                        by_query = dict(conn.get('db_import_mappings_by_query', {}) or {})
                        by_query[query_text] = mapping
                        updates['db_import_mappings_by_query'] = by_query
                    self._save_db_connection_settings(name, updates)
                
                # PHASE 2 OPTIMIZATION: Use streaming reads for large imports
                # First, count rows to show progress
                try:
                    # Count total rows for progress tracking
                    progress = QtWidgets.QProgressDialog(
                        "Reading data from database...",
                        "Cancel",
                        0, 0,
                        self
                    )
                    progress.setWindowTitle("Import from Database")
                    progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
                    progress.setMinimumDuration(500)
                    progress.setValue(0)
                    QtWidgets.QApplication.processEvents()
                    
                    # Collect all users by streaming in batches
                    all_users = []
                    batch_count = 0
                    
                    if source_mode == "Custom Query":
                        row_generator = db_utils.stream_query_rows(
                            conn['type'], conn['host'], conn['port'], conn['database'],
                            conn['user'], conn['password'], query_text, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode'),
                            batch_size=1000
                        )
                        self._set_last_data_source(f"DB {name}: custom query")
                    else:
                        row_generator = db_utils.stream_table_rows(
                            conn['type'], conn['host'], conn['port'], conn['database'],
                            conn['user'], conn['password'], table, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode'),
                            batch_size=1000
                        )
                        self._set_last_data_source(f"DB {name}: {table}")
                    
                    # Stream and collect all rows
                    for batch in row_generator:
                        batch_count += 1
                        all_users.extend(batch)
                        progress.setLabelText(f"Reading batch {batch_count} ({len(all_users)} rows so far)...")
                        QtWidgets.QApplication.processEvents()
                        
                        if progress.wasCanceled():
                            progress.close()
                            return
                    
                    rows = all_users
                    progress.close()
                    
                except Exception as e:
                    try:
                        progress.close()
                    except:
                        pass
                    QtWidgets.QMessageBox.critical(self, "Import DB", f"Failed to read table rows: {e}")
                    return
                
                if not rows:
                    QtWidgets.QMessageBox.information(self, "Import DB", "No rows found in table.")
                    return
                
                # Show status message with row count
                self._set_processing_message(f"Read {len(rows)} rows from database", 5000)
                # prepare API client and optional population cache
                pops = {}
                try:
                    token = asyncio.run(client.get_token())
                    if token:
                        pops, _ = asyncio.run(client.get_populations())
                except Exception:
                    pass
                # convert DB rows to PingOne users
                debug_stats = {}
                users = self._convert_rows_to_users(rows, mapping, client, pops, debug_stats=debug_stats)
                self._set_processing_message(self._format_import_mapping_debug_summary(debug_stats), 10000)
                sampled_skips = debug_stats.get('sampled_skips', []) if isinstance(debug_stats, dict) else []
                if sampled_skips:
                    self._set_processing_message(f"Sample skipped rows: {' | '.join(sampled_skips)}", 12000)
                # run common import sequence
                self._perform_import_sequence(users, client, pops, debug_stats=debug_stats)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import DB", str(e))

    def _prompt_import_table_from_connection(self, conn: dict, connection_name: str) -> str:
        """Prompt for table name using an available-table dropdown when possible."""
        default_tbl = (conn.get('table', '') or '').strip()
        table_names = []
        list_error = None
        try:
            from api import db_utils
            table_names = db_utils.get_table_names(
                conn['type'], conn['host'], conn['port'], conn['database'],
                conn['user'], conn['password'], conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
            )
            table_names = [str(t).strip() for t in table_names if str(t).strip()]
        except Exception as e:
            list_error = str(e)
            table_names = []

        if table_names:
            options = list(table_names)
            if default_tbl and default_tbl not in options:
                options.insert(0, default_tbl)
            table, ok = QtWidgets.QInputDialog.getItem(
                self,
                "Select Table",
                f"Database table to import from ({connection_name}):",
                options,
                0,
                True,
            )
        else:
            if list_error:
                err_lower = list_error.lower()
                if "permission" in err_lower or "denied" in err_lower or "privilege" in err_lower:
                    QtWidgets.QMessageBox.information(
                        self,
                        "Table List Unavailable",
                        "This account does not have enough permissions to list tables automatically.\n\n"
                        "Enter the table name manually."
                    )
            table, ok = QtWidgets.QInputDialog.getText(
                self,
                "Table Name",
                "Database table to import from:",
                text=default_tbl,
            )

        if not ok or not table:
            return ""
        table = table.strip()
        if not table:
            QtWidgets.QMessageBox.warning(self, "Table Name", "Table name cannot be empty.")
            return ""
        return table

    def _prompt_export_table_from_connection(self, conn: dict, connection_name: str) -> str:
        """Prompt for export target table using available-table dropdown when possible."""
        default_tbl = (conn.get('table', '') or '').strip()
        table_names = []
        list_error = None
        try:
            from api import db_utils
            table_names = db_utils.get_table_names(
                conn['type'], conn['host'], conn['port'], conn['database'],
                conn['user'], conn['password'], conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
            )
            table_names = [str(t).strip() for t in table_names if str(t).strip()]
        except Exception as e:
            list_error = str(e)
            table_names = []

        if table_names:
            options = list(table_names)
            if default_tbl and default_tbl not in options:
                options.insert(0, default_tbl)
            table, ok = QtWidgets.QInputDialog.getItem(
                self,
                "Select Table",
                f"Database table to export to ({connection_name}):",
                options,
                0,
                True,
            )
        else:
            if list_error:
                err_lower = list_error.lower()
                if "permission" in err_lower or "denied" in err_lower or "privilege" in err_lower:
                    QtWidgets.QMessageBox.information(
                        self,
                        "Table List Unavailable",
                        "This account does not have enough permissions to list tables automatically.\n\n"
                        "Enter the table name manually."
                    )
            table, ok = QtWidgets.QInputDialog.getText(
                self,
                "Table Name",
                "Database table to export to (will be created if it does not exist):",
                text=default_tbl,
            )

        if not ok or not table:
            return ""
        table = table.strip()
        if not table:
            QtWidgets.QMessageBox.warning(self, "Table Name", "Table name cannot be empty.")
            return ""
        return table

    def _save_db_connection_settings(self, connection_name: str, updates: dict):
        """Persist additional per-connection settings under db_connections."""
        if not connection_name or not updates:
            return
        try:
            cfg = self._read_config()
            dbs = cfg.get('db_connections', {})
            if connection_name not in dbs:
                return
            dbs[connection_name].update(updates)
            cfg['db_connections'] = dbs
            self._write_config(cfg)
        except Exception:
            pass

    def _get_saved_dialog_size(self, prefs_key: str):
        """Return saved dialog size for the active profile (fallback to app meta)."""
        try:
            cfg = self._read_config()
            prof_name = self.profile_list.currentText() if hasattr(self, 'profile_list') else ''
            if prof_name and prof_name in cfg and isinstance(cfg.get(prof_name), dict):
                prof_sizes = cfg[prof_name].get('dialog_sizes', {})
                if isinstance(prof_sizes, dict):
                    size = prof_sizes.get(prefs_key)
                    if isinstance(size, dict):
                        w = int(size.get('width', 0) or 0)
                        h = int(size.get('height', 0) or 0)
                        if w > 0 and h > 0:
                            return w, h
            meta = cfg.get('__meta__', {}) if isinstance(cfg, dict) else {}
            global_sizes = meta.get('dialog_sizes', {}) if isinstance(meta, dict) else {}
            size = global_sizes.get(prefs_key) if isinstance(global_sizes, dict) else None
            if isinstance(size, dict):
                w = int(size.get('width', 0) or 0)
                h = int(size.get('height', 0) or 0)
                if w > 0 and h > 0:
                    return w, h
        except Exception:
            pass
        return None

    def _save_dialog_size(self, prefs_key: str, width: int, height: int):
        """Persist dialog size for the active profile, with app-level fallback."""
        try:
            w = int(width or 0)
            h = int(height or 0)
            if w <= 0 or h <= 0:
                return
            cfg = self._read_config()
            prof_name = self.profile_list.currentText() if hasattr(self, 'profile_list') else ''
            if prof_name:
                if prof_name not in cfg or not isinstance(cfg.get(prof_name), dict):
                    cfg[prof_name] = {}
                prof_sizes = cfg[prof_name].get('dialog_sizes', {})
                if not isinstance(prof_sizes, dict):
                    prof_sizes = {}
                prof_sizes[prefs_key] = {'width': w, 'height': h}
                cfg[prof_name]['dialog_sizes'] = prof_sizes
            else:
                meta = cfg.get('__meta__', {})
                if not isinstance(meta, dict):
                    meta = {}
                global_sizes = meta.get('dialog_sizes', {})
                if not isinstance(global_sizes, dict):
                    global_sizes = {}
                global_sizes[prefs_key] = {'width': w, 'height': h}
                meta['dialog_sizes'] = global_sizes
                cfg['__meta__'] = meta
            self._write_config(cfg)
        except Exception:
            pass

    def _prompt_bounded_multiline_text(self, title: str, prompt: str, default_text: str, prefs_key: str = 'multiline_input'):
        """Prompt for multiline text using a dialog bounded to screen size."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setModal(True)

        layout = QtWidgets.QVBoxLayout(dlg)
        label = QtWidgets.QLabel(prompt)
        label.setWordWrap(True)
        layout.addWidget(label)

        editor = QtWidgets.QTextEdit(dlg)
        editor.setPlainText(str(default_text or ''))
        # Keep long SQL/LDAP text usable without forcing giant window expansion.
        editor.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        layout.addWidget(editor)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            parent=dlg,
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        try:
            screen = QtWidgets.QApplication.primaryScreen()
            geom = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1280, 800)
            max_w = max(640, geom.width() - 40)
            max_h = max(420, geom.height() - 40)
            target_w = min(980, int(geom.width() * 0.78), max_w)
            target_h = min(620, int(geom.height() * 0.62), max_h)
            saved_size = self._get_saved_dialog_size(prefs_key)
            if saved_size:
                target_w = min(max_w, max(680, int(saved_size[0])))
                target_h = min(max_h, max(420, int(saved_size[1])))
            dlg.resize(max(680, target_w), max(420, target_h))
            dlg.setMaximumSize(max_w, max_h)
        except Exception:
            dlg.resize(900, 560)

        accepted = dlg.exec() == QtWidgets.QDialog.Accepted
        try:
            self._save_dialog_size(prefs_key, dlg.width(), dlg.height())
        except Exception:
            pass
        if not accepted:
            return "", False
        text = editor.toPlainText()
        return text, True

    def _prompt_saved_text_choice(self, title: str, prompt: str, items: list, new_label: str, prefs_key: str):
        """Prompt to select from saved long text values in a bounded dialog."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setModal(True)

        layout = QtWidgets.QVBoxLayout(dlg)
        label = QtWidgets.QLabel(prompt)
        label.setWordWrap(True)
        layout.addWidget(label)

        list_widget = QtWidgets.QListWidget(dlg)

        def _shorten(text: str, max_len: int = 120) -> str:
            s = str(text or '').replace('\n', ' ').strip()
            if len(s) <= max_len:
                return s
            return s[: max_len - 3] + '...'

        new_item = QtWidgets.QListWidgetItem(new_label)
        new_item.setData(QtCore.Qt.UserRole, new_label)
        list_widget.addItem(new_item)

        for saved in items or []:
            shown = _shorten(saved)
            item = QtWidgets.QListWidgetItem(shown)
            item.setToolTip(str(saved))
            item.setData(QtCore.Qt.UserRole, str(saved))
            list_widget.addItem(item)

        list_widget.setCurrentRow(0)
        list_widget.itemDoubleClicked.connect(lambda _item: dlg.accept())
        layout.addWidget(list_widget)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            parent=dlg,
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        try:
            screen = QtWidgets.QApplication.primaryScreen()
            geom = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1280, 800)
            max_w = max(560, geom.width() - 40)
            max_h = max(320, geom.height() - 40)
            target_w = min(900, int(geom.width() * 0.7), max_w)
            target_h = min(520, int(geom.height() * 0.55), max_h)
            saved_size = self._get_saved_dialog_size(prefs_key)
            if saved_size:
                target_w = min(max_w, max(560, int(saved_size[0])))
                target_h = min(max_h, max(320, int(saved_size[1])))
            dlg.resize(max(560, target_w), max(320, target_h))
            dlg.setMaximumSize(max_w, max_h)
        except Exception:
            dlg.resize(760, 420)

        accepted = dlg.exec() == QtWidgets.QDialog.Accepted
        try:
            self._save_dialog_size(prefs_key, dlg.width(), dlg.height())
        except Exception:
            pass
        if not accepted:
            return "", False

        current = list_widget.currentItem()
        if not current:
            return "", False
        selected = current.data(QtCore.Qt.UserRole)
        return str(selected or ''), True

    def _prompt_custom_query_from_connection(self, conn: dict, connection_name: str):
        """Prompt for SQL query and return (query_text, query_saved)."""
        saved_queries = [q for q in (conn.get('saved_custom_queries', []) or []) if str(q).strip()]
        default_query = (conn.get('last_custom_query') or '').strip() or "SELECT * FROM your_table"

        # If queries were previously saved, let the user start from one.
        if saved_queries:
            selected, ok = self._prompt_saved_text_choice(
                "Saved Custom Queries",
                f"Select a saved query for {connection_name} or choose '<Type new query>':",
                saved_queries,
                "<Type new query>",
                prefs_key='saved_custom_query_picker',
            )
            if not ok:
                return "", False
            if selected and selected != "<Type new query>":
                default_query = selected

        query_text, ok = self._prompt_bounded_multiline_text(
            "Custom Query",
            "Enter SQL query (SELECT):",
            default_query,
            prefs_key='custom_query_input',
        )
        if not ok or not query_text or not query_text.strip():
            return "", False

        query_text = query_text.strip()

        if query_text in saved_queries:
            self._save_db_connection_settings(connection_name, {'last_custom_query': query_text})
            return query_text, True

        save = QtWidgets.QMessageBox.question(
            self,
            "Save Custom Query",
            "Save this query in the selected DB connection settings for reuse?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes,
        )
        if save == QtWidgets.QMessageBox.Yes:
            merged = [query_text] + [q for q in saved_queries if q != query_text]
            self._save_db_connection_settings(
                connection_name,
                {
                    'last_custom_query': query_text,
                    'saved_custom_queries': merged[:10],
                },
            )
            return query_text, True

        return query_text, False

    def _prompt_custom_ldap_filter_from_connection(self, conn: dict, connection_name: str):
        """Prompt for LDAP filter and return (filter_text, filter_saved)."""
        saved_filters = [f for f in (conn.get('saved_custom_filters', []) or []) if str(f).strip()]
        default_filter = (conn.get('last_custom_filter') or '').strip() or "(objectClass=person)"

        # If filters were previously saved, let the user start from one.
        if saved_filters:
            selected, ok = self._prompt_saved_text_choice(
                "Saved Custom Filters",
                f"Select a saved filter for {connection_name} or choose '<Type new filter>':",
                saved_filters,
                "<Type new filter>",
                prefs_key='saved_custom_filter_picker',
            )
            if not ok:
                return "", False
            if selected and selected != "<Type new filter>":
                default_filter = selected

        filter_text, ok = self._prompt_bounded_multiline_text(
            "Custom LDAP Filter",
            "Enter LDAP filter (e.g., (&(objectClass=person)(ou=users))):",
            default_filter,
            prefs_key='custom_ldap_filter_input',
        )
        if not ok or not filter_text or not filter_text.strip():
            return "", False

        filter_text = filter_text.strip()

        # Validate basic LDAP filter syntax
        if not filter_text.startswith('(') or not filter_text.endswith(')'):
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid LDAP Filter",
                "LDAP filters must be enclosed in parentheses, e.g., (objectClass=person)"
            )
            return "", False
        
        # Basic validation for balanced parentheses and suspicious patterns
        if filter_text.count('(') != filter_text.count(')'):
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid LDAP Filter",
                "LDAP filter has unbalanced parentheses"
            )
            return "", False
        
        # Warn about potentially dangerous patterns (but allow them)
        suspicious_patterns = ['*)(', ')(', '**']
        has_suspicious = any(pattern in filter_text for pattern in suspicious_patterns)
        if has_suspicious:
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Question)
            msg_box.setWindowTitle("Unusual LDAP Filter")
            msg_box.setText("This filter contains unusual patterns that might return unexpected results.\n\nContinue anyway?")
            
            # Optional detailed information (collapsible)
            detailed_info = (
                "Possible issues:\n"
                "• Patterns like '*)(', or ')(': May break filter logic or bypass intended restrictions\n"
                "• Multiple wildcards '**': Can cause poor performance or overly broad matches\n"
                "• Malformed structure: May return more/fewer entries than expected\n\n"
                "These patterns could result in:\n"
                "- Importing the wrong users\n"
                "- Missing users you intended to import\n"
                "- Performance degradation or timeouts"
            )
            msg_box.setDetailedText(detailed_info)
            msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            msg_box.setDefaultButton(QtWidgets.QMessageBox.No)
            
            reply = msg_box.exec()
            if reply != QtWidgets.QMessageBox.Yes:
                return "", False

        if filter_text in saved_filters:
            self._save_ldap_connection_settings(connection_name, {'last_custom_filter': filter_text})
            return filter_text, True

        save = QtWidgets.QMessageBox.question(
            self,
            "Save Custom Filter",
            "Save this filter in the selected LDAP connection settings for reuse?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes,
        )
        if save == QtWidgets.QMessageBox.Yes:
            merged = [filter_text] + [f for f in saved_filters if f != filter_text]
            self._save_ldap_connection_settings(
                connection_name,
                {
                    'last_custom_filter': filter_text,
                    'saved_custom_filters': merged[:10],
                },
            )
            return filter_text, True

        return filter_text, False

    def _get_pingone_attributes_for_import(self, client) -> list:
        """Refresh available PingOne attributes from live user data."""
        attrs = set(self._get_pingone_attributes())
        try:
            token = asyncio.run(client.get_token())
            if not token:
                return sorted(attrs)

            async def _fetch_attrs():
                headers = client._get_auth_headers(token)
                url = f"{client.base_url}/users"
                pages = 0
                async with httpx.AsyncClient(timeout=10.0) as session:
                    while url and pages < 5:
                        resp = await session.get(url, headers=headers)
                        resp.raise_for_status()
                        data = resp.json()
                        for u in data.get("_embedded", {}).get("users", []):
                            self._collect_keys(u, '', attrs)
                        url = data.get("_links", {}).get("next", {}).get("href")
                        pages += 1

            asyncio.run(_fetch_attrs())
        except Exception:
            pass

        if 'population.id' in attrs:
            attrs.add('population.name')
        return sorted(attrs)


    def import_from_database_wizard(self, connection_name: str, query_mode: str = 'table'):
        """Import from database with parameters provided by wizard dialog."""
        try:
            cfg = self._read_config()
            dbs = cfg.get('db_connections', {})
            
            if not connection_name or connection_name not in dbs:
                QtWidgets.QMessageBox.critical(self, "Import DB", "Connection not found.")
                return
            
            conn = dbs[connection_name]
            
            # Prompt for table name or custom query
            if query_mode == 'custom':
                query_text, query_saved = self._prompt_custom_query_from_connection(conn, connection_name)
                if not query_text:
                    return
                table = None
            else:
                query_saved = False
                table = self._prompt_import_table_from_connection(conn, connection_name)
                if not table:
                    return
                query_text = None
            
            # Test connection and fetch data
            try:
                from api import db_utils
            except ModuleNotFoundError:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Import DB",
                    "SQLAlchemy is not installed. Please run `pip install -r requirements.txt`."
                )
                return
            
            ok, _ = db_utils.test_connection(
                conn['type'], conn['host'], conn['port'], conn['database'],
                conn['user'], conn['password'], conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
            )
            if not ok:
                QtWidgets.QMessageBox.critical(self, "Import DB", "Unable to connect with provided credentials.")
                return
            
            # Fetch columns and discover populated attributes from first 10 rows
            try:
                if query_text:
                    cols = db_utils.get_query_columns(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], query_text, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
                    )
                    # Get first 10 rows to discover populated attributes
                    sample_rows = db_utils.get_query_rows(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], query_text, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode'),
                        limit=10
                    )
                    cols = self._discover_populated_attributes_from_entries(sample_rows, max_sample=10) if sample_rows else cols
                    sample = sample_rows[0] if sample_rows else {}
                else:
                    cols = db_utils.get_table_columns(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], table, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
                    )
                    # Get first 10 rows to discover populated attributes
                    sample_rows = db_utils.get_table_rows(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], table, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode'),
                        limit=10
                    )
                    cols = self._discover_populated_attributes_from_entries(sample_rows, max_sample=10) if sample_rows else cols
                    sample = sample_rows[0] if sample_rows else {}
            except Exception as e:
                # Fall back to old method if new method fails
                try:
                    if query_text:
                        cols = db_utils.get_query_columns(
                            conn['type'], conn['host'], conn['port'], conn['database'],
                            conn['user'], conn['password'], query_text, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
                        )
                        sample = db_utils.get_query_sample(
                            conn['type'], conn['host'], conn['port'], conn['database'],
                            conn['user'], conn['password'], query_text, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
                        )
                    else:
                        cols = db_utils.get_table_columns(
                            conn['type'], conn['host'], conn['port'], conn['database'],
                            conn['user'], conn['password'], table, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
                        )
                        sample = db_utils.get_table_sample(
                            conn['type'], conn['host'], conn['port'], conn['database'],
                            conn['user'], conn['password'], table, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
                        )
                except Exception as inner_e:
                    QtWidgets.QMessageBox.critical(self, "Import DB", f"Failed to read table metadata: {inner_e}")
                    return
            
            # Convert any dotted column names to underscore equivalents
            converted_cols = [self._convert_dotted_to_underscore(col) for col in cols]
            # Also convert sample row keys
            if sample:
                converted_sample = {self._convert_dotted_to_underscore(k): v for k, v in sample.items()}
            else:
                converted_sample = {}
            
            # Check if any columns were actually converted and show confirmation
            adjustments = [(orig, converted) for orig, converted in zip(cols, converted_cols) if orig != converted]
            if adjustments:
                msg = "Adjusted column names for SQL compatibility:\n\n"
                for orig, converted in adjustments:
                    msg += f"  {orig} → {converted}\n"
                msg += "\nProceed with import using the _ values?"
                
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Column Name Adjustments",
                    msg,
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.Yes
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return
            
            client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
            ping_attrs = self._get_pingone_attributes_for_import(client)
            from ui.dialogs import DatabaseMappingDialog
            initial_mapping = conn.get('db_import_mapping', {})
            if query_mode == 'custom' and query_text:
                by_query = conn.get('db_import_mappings_by_query', {}) or {}
                if query_text in by_query:
                    initial_mapping = by_query.get(query_text, initial_mapping)
            dlg = DatabaseMappingDialog(
                converted_cols,
                ping_attrs,
                direction='import',
                sample_row=converted_sample,
                initial_mapping=initial_mapping,
                parent=self,
            )
            
            if dlg.exec() == QtWidgets.QDialog.Accepted:
                mapping = dlg.get_mapping()
                if not mapping:
                    QtWidgets.QMessageBox.information(self, "Import DB", "No columns were mapped; import cancelled.")
                    return
                if dlg.remember_mapping() or (query_mode == 'custom' and query_saved):
                    updates = {'db_import_mapping': mapping}
                    if query_mode == 'custom' and query_saved and query_text:
                        by_query = dict(conn.get('db_import_mappings_by_query', {}) or {})
                        by_query[query_text] = mapping
                        updates['db_import_mappings_by_query'] = by_query
                    self._save_db_connection_settings(connection_name, updates)
                
                # PHASE 2 OPTIMIZATION: Use streaming reads for large imports
                try:
                    # Show progress dialog while reading database
                    progress = QtWidgets.QProgressDialog(
                        "Reading data from database...",
                        "Cancel",
                        0, 0,
                        self
                    )
                    progress.setWindowTitle("Import from Database")
                    progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
                    progress.setMinimumDuration(500)
                    progress.setValue(0)
                    QtWidgets.QApplication.processEvents()
                    
                    # Collect all users by streaming in batches
                    all_users = []
                    batch_count = 0
                    
                    if query_text:
                        row_generator = db_utils.stream_query_rows(
                            conn['type'], conn['host'], conn['port'], conn['database'],
                            conn['user'], conn['password'], query_text, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode'),
                            batch_size=1000
                        )
                        self._set_last_data_source(f"DB {connection_name}: custom query")
                    else:
                        row_generator = db_utils.stream_table_rows(
                            conn['type'], conn['host'], conn['port'], conn['database'],
                            conn['user'], conn['password'], table, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode'),
                            batch_size=1000
                        )
                        self._set_last_data_source(f"DB {connection_name}: {table}")
                    
                    # Stream and collect all rows
                    for batch in row_generator:
                        batch_count += 1
                        all_users.extend(batch)
                        progress.setLabelText(f"Reading batch {batch_count} ({len(all_users)} rows so far)...")
                        QtWidgets.QApplication.processEvents()
                        
                        if progress.wasCanceled():
                            progress.close()
                            return
                    
                    rows = all_users
                    progress.close()
                    
                except Exception as e:
                    try:
                        progress.close()
                    except:
                        pass
                    QtWidgets.QMessageBox.critical(self, "Import DB", f"Failed to read table rows: {e}")
                    return
                
                if not rows:
                    QtWidgets.QMessageBox.information(self, "Import DB", "No rows found in table.")
                    return
                
                # Show status message with row count
                self._set_processing_message(f"Read {len(rows)} rows from database", 5000)
                
                # Normalize DB row keys to Python strings.
                converted_rows = []
                for row in rows:
                    converted_row = {str(k): v for k, v in row.items()}
                    converted_rows.append(converted_row)
                
                # Prepare client and import
                pops = {}
                default_pop_id = None
                try:
                    token = asyncio.run(client.get_token())
                    if token:
                        pops, default_pop_id = asyncio.run(client.get_populations())
                except Exception:
                    token = None
                
                debug_stats = {}
                users = self._convert_rows_to_users(converted_rows, mapping, client, pops, debug_stats=debug_stats)
                self._set_processing_message(self._format_import_mapping_debug_summary(debug_stats), 10000)
                sampled_skips = debug_stats.get('sampled_skips', []) if isinstance(debug_stats, dict) else []
                if sampled_skips:
                    self._set_processing_message(f"Sample skipped rows: {' | '.join(sampled_skips)}", 12000)
                
                # Prompt for population selection
                if not pops:
                    pops, default_pop_id = asyncio.run(client.get_populations())
                
                fixed_pop_id = None
                if pops:
                    # Create population selection dialog
                    pop_dlg = QtWidgets.QDialog(self)
                    pop_dlg.setWindowTitle("Select Population for Import")
                    pop_layout = QtWidgets.QVBoxLayout(pop_dlg)
                    
                    pop_layout.addWidget(QtWidgets.QLabel("Assign all imported users to a population:"))
                    
                    # Combo box and refresh button in horizontal layout
                    pop_combo_layout = QtWidgets.QHBoxLayout()
                    pop_combo = QtWidgets.QComboBox()
                    pop_combo.addItem("<Use population from data>", None)
                    for pop_name, pop_id in sorted(pops.items()):
                        pop_combo.addItem(pop_name, pop_id)
                    pop_combo_layout.addWidget(pop_combo)
                    
                    # Set default to the environment's default population if one exists
                    if default_pop_id:
                        idx = pop_combo.findData(default_pop_id)
                        if idx != -1:
                            pop_combo.setCurrentIndex(idx)
                    
                    refresh_pop_btn = QtWidgets.QPushButton("Refresh")
                    refresh_pop_btn.setToolTip("Query PingOne for updated population list")
                    
                    def refresh_populations():
                        nonlocal default_pop_id
                        try:
                            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
                            current_selection = pop_combo.currentData()
                            token = asyncio.run(client.get_token())
                            if token:
                                new_pops, new_default_pop_id = asyncio.run(client.get_populations())
                                pops.clear()
                                pops.update(new_pops or {})
                                default_pop_id = new_default_pop_id
                                
                                # Rebuild combo
                                pop_combo.clear()
                                pop_combo.addItem("<Use population from data>", None)
                                for pop_name, pop_id in sorted(pops.items()):
                                    pop_combo.addItem(pop_name, pop_id)
                                
                                # Restore selection if still exists, otherwise use default
                                if current_selection:
                                    idx = pop_combo.findData(current_selection)
                                    if idx != -1:
                                        pop_combo.setCurrentIndex(idx)
                                    elif default_pop_id:
                                        # Selection no longer exists, use default
                                        idx = pop_combo.findData(default_pop_id)
                                        if idx != -1:
                                            pop_combo.setCurrentIndex(idx)
                                elif default_pop_id:
                                    # No previous selection, use default
                                    idx = pop_combo.findData(default_pop_id)
                                    if idx != -1:
                                        pop_combo.setCurrentIndex(idx)
                                
                                QtWidgets.QMessageBox.information(
                                    pop_dlg,
                                    "Refresh Populations",
                                    f"Successfully refreshed. Found {len(pops)} population(s)."
                                )
                            else:
                                QtWidgets.QMessageBox.warning(
                                    pop_dlg,
                                    "Refresh Populations",
                                    "Failed to authenticate with PingOne."
                                )
                        except Exception as e:
                            QtWidgets.QMessageBox.critical(
                                pop_dlg,
                                "Refresh Populations",
                                f"Failed to refresh: {str(e)}"
                            )
                        finally:
                            QtWidgets.QApplication.restoreOverrideCursor()
                    
                    refresh_pop_btn.clicked.connect(refresh_populations)
                    pop_combo_layout.addWidget(refresh_pop_btn)
                    
                    pop_layout.addLayout(pop_combo_layout)
                    
                    pop_btns = QtWidgets.QDialogButtonBox(
                        QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
                    )
                    pop_btns.accepted.connect(pop_dlg.accept)
                    pop_btns.rejected.connect(pop_dlg.reject)
                    pop_layout.addWidget(pop_btns)
                    
                    if pop_dlg.exec() == QtWidgets.QDialog.Accepted:
                        fixed_pop_id = pop_combo.currentData()
                    else:
                        return  # User cancelled
                
                self._perform_import_sequence(users, client, pops, fixed_pop_id=fixed_pop_id, debug_stats=debug_stats)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import Error", str(e))

    def export_to_database(self):
        """Initiate export flow to a database table."""
        try:
            # Use the new connection chooser with create option
            name, dbs = self._choose_db_connection("Select Database Connection for Export")
            if not name:
                return
            conn = dbs[name]
            self._set_last_data_source(f"DB {name}")
            table = self._prompt_export_table_from_connection(conn, name)
            if not table:
                return
            # test connection
            try:
                from api import db_utils
            except ModuleNotFoundError:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Export DB",
                    "SQLAlchemy is not installed. Please run `pip install -r requirements.txt`."
                )
                return

            ok, _ = db_utils.test_connection(conn['type'], conn['host'], conn['port'], conn['database'], conn['user'], conn['password'], conn.get('driver'), encrypt_mode=conn.get('encrypt_mode'))
            if not ok:
                QtWidgets.QMessageBox.critical(self, "Export DB", "Unable to connect with provided credentials.")
                return
            
            # Show export options dialog to let user choose which fields to export
            if not self.users_cache:
                QtWidgets.QMessageBox.information(self, "Export DB", "No users to export.")
                return
            
            profile_name = self.profile_list.currentText()
            prefer_selected = True
            only_visible_default = True
            try:
                cfg = self._read_config()
                if profile_name and profile_name in cfg:
                    prefer_selected = cfg[profile_name].get('export_prefer_selected', prefer_selected)
                    only_visible_default = cfg[profile_name].get('export_only_visible_columns', only_visible_default)
            except Exception:
                pass
            
            selected = self.u_table.selectionModel().selectedRows()
            from ui.dialogs import ExportOptionsDialog
            populated_attrs = self._get_populated_export_attributes(self.users_cache)
            populated_attr_samples = self._get_populated_export_attribute_samples(self.users_cache, populated_attrs)
            metadata_cols = self._get_metadata_columns(self.users_cache)
            
            # Load saved excluded metadata from profile
            excluded_metadata = []
            try:
                cfg = self._read_config()
                if profile_name and profile_name in cfg:
                    excluded_metadata = cfg[profile_name].get('export_excluded_metadata', [])
            except Exception:
                pass
            
            export_dlg = ExportOptionsDialog(
                bool(selected),
                only_visible_default,
                prefer_selected,
                self,
                populated_attributes=populated_attrs,
                populated_attribute_samples=populated_attr_samples,
                metadata_columns=metadata_cols,
                excluded_metadata=excluded_metadata,
            )
            if export_dlg.exec() != QtWidgets.QDialog.Accepted:
                return
            opts = export_dlg.get_options()
            
            # Persist choices if requested
            if opts.get('remember') and profile_name:
                try:
                    cfg = self._read_config()
                    if profile_name not in cfg:
                        cfg[profile_name] = {}
                    cfg[profile_name]['export_prefer_selected'] = (opts.get('rows') == 'selected')
                    cfg[profile_name]['export_only_visible_columns'] = bool(opts.get('only_visible_columns'))
                    cfg[profile_name]['export_excluded_metadata'] = opts.get('excluded_metadata', [])
                    self._write_config(cfg)
                except Exception:
                    pass
            
            # fetch column names if table exists, otherwise use empty list
            cols = []
            try:
                cols = db_utils.get_table_columns(conn['type'], conn['host'], conn['port'], conn['database'], conn['user'], conn['password'], table, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode'))
            except Exception:
                cols = []
            
            # Filter out metadata columns from existing table columns
            # This prevents metadata fields from being included in exports
            if cols:
                metadata_cols_all = self._get_metadata_columns(self.users_cache) if self.users_cache else []
                metadata_set = set(metadata_cols_all)
                cols = [c for c in cols if str(c) not in metadata_set]

            # Offer one-click migration for legacy dotted column names.
            dotted_cols = [c for c in cols if '.' in str(c)]
            if dotted_cols:
                rename_map = self._build_db_column_rename_map(cols)
                if rename_map:
                    details = "\n".join(f"{old} -> {new}" for old, new in rename_map.items())
                    answer = QtWidgets.QMessageBox.question(
                        self,
                        "Migrate Legacy Columns",
                        "This table contains legacy dotted column names.\n\n"
                        "Rename them to underscored names now for better compatibility?\n\n"
                        + details,
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.Yes,
                    )
                    if answer == QtWidgets.QMessageBox.Yes:
                        try:
                            db_utils.rename_table_columns(
                                conn['type'], conn['host'], conn['port'], conn['database'],
                                conn['user'], conn['password'], table, rename_map, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
                            )
                            cols = db_utils.get_table_columns(
                                conn['type'], conn['host'], conn['port'], conn['database'],
                                conn['user'], conn['password'], table, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
                            )
                            # Filter metadata columns after migration too
                            if cols:
                                metadata_cols_all = self._get_metadata_columns(self.users_cache) if self.users_cache else []
                                metadata_set = set(metadata_cols_all)
                                cols = [c for c in cols if str(c) not in metadata_set]
                            QtWidgets.QMessageBox.information(self, "Migrate Legacy Columns", "Column rename migration completed.")
                        except NotImplementedError as e:
                            QtWidgets.QMessageBox.information(self, "Migrate Legacy Columns", str(e))
                        except Exception as e:
                            QtWidgets.QMessageBox.warning(self, "Migrate Legacy Columns", f"Migration failed: {e}")

            ping_attrs = self._get_pingone_attributes()
            try:
                client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
                ping_attrs = self._get_pingone_attributes_for_import(client)
            except Exception:
                pass
            
            # Filter PingOne attributes based on export options
            if opts.get('only_visible_columns'):
                # Use only visible columns
                visible_attrs = set(self.columns or [])
                ping_attrs = [attr for attr in ping_attrs if attr in visible_attrs]
            
            # Filter out excluded metadata fields
            excluded_metadata_set = set(opts.get('excluded_metadata', []))
            ping_attrs_filtered = [attr for attr in ping_attrs if attr not in excluded_metadata_set]
            
            sample_p1 = {}
            try:
                sample_user = None
                if selected:
                    id_col = self.columns.index('id') if 'id' in self.columns else -1
                    if id_col != -1:
                        sample_id = self.u_table.item(selected[0].row(), id_col).text()
                        sample_user = next((u for u in self.users_cache if u.get('id') == sample_id), None)
                if sample_user is None and self.users_cache:
                    sample_user = self.users_cache[0]
                if sample_user:
                    sample_p1 = self._flatten_user(sample_user)
            except Exception:
                sample_p1 = {}
            initial_mapping = conn.get('db_export_mapping', {})
            # Filter excluded metadata fields from saved mapping
            if initial_mapping:
                excluded_metadata_set = set(opts.get('excluded_metadata', []))
                initial_mapping = {k: v for k, v in initial_mapping.items() if k not in excluded_metadata_set}
            dlg = DatabaseMappingDialog(
                cols or ping_attrs_filtered,
                ping_attrs_filtered,
                direction='export',
                sample_row=sample_p1,
                initial_mapping=initial_mapping,
                parent=self,
            )
            if dlg.exec() == QtWidgets.QDialog.Accepted:
                mapping = dlg.get_mapping()
                if not mapping:
                    QtWidgets.QMessageBox.information(self, "Export DB", "No attributes were mapped; export cancelled.")
                    return
                
                # Final safeguard: filter out any excluded metadata fields from the mapping
                excluded_metadata_set = set(opts.get('excluded_metadata', []))
                mapping = {k: v for k, v in mapping.items() if k not in excluded_metadata_set}
                
                if not mapping:
                    QtWidgets.QMessageBox.information(self, "Export DB", "All mapped attributes were metadata fields; export cancelled.")
                    return
                
                if dlg.remember_mapping():
                    self._save_db_connection_settings(name, {'db_export_mapping': mapping})
                
                # Always sanitize column names for SQL compatibility (both new and existing tables)
                effective_mapping = {}
                renamed_columns = {}
                used_names = set()
                for ping_attr, target_col in mapping.items():
                    base_name = self._sanitize_db_column_name(target_col)
                    candidate = base_name
                    suffix = 2
                    while candidate in used_names:
                        candidate = f"{base_name}_{suffix}"
                        suffix += 1
                    used_names.add(candidate)
                    effective_mapping[ping_attr] = candidate
                    if candidate != target_col:
                        renamed_columns[target_col] = candidate
                
                if renamed_columns:
                    details = "\n".join(f"{old} -> {new}" for old, new in renamed_columns.items())
                    QtWidgets.QMessageBox.information(
                        self,
                        "Export DB",
                        "Adjusted column names for SQL compatibility:\n\n" + details,
                    )
                # compute list of users to export based on export options
                if opts.get('rows') == 'selected' and selected:
                    id_col = self.columns.index('id') if 'id' in self.columns else -1
                    if id_col != -1:
                        ids = [self.u_table.item(r.row(), id_col).text() for r in selected]
                        export_users = [u for u in self.users_cache if u.get('id') in ids]
                    else:
                        export_users = list(self.users_cache)
                else:
                    export_users = list(self.users_cache)
                
                required_attrs = opts.get('required_populated_attributes') or []
                filtered_out = 0
                if required_attrs:
                    export_users, filtered_out = self._filter_users_by_populated_attributes(export_users, required_attrs)
                
                # Filter by selected populations
                selected_populations = opts.get('selected_populations', [])
                pop_filtered_out = 0
                if selected_populations:
                    export_users, pop_filtered_out = self._filter_users_by_populations(export_users, selected_populations)
                
                # Start TPS tracking
                tracker = TPSTracker()
                tracker.start()
                
                # build rows for insertion based on mapping
                rows = []
                total_users = len(export_users)
                for idx, u in enumerate(export_users, 1):
                    flat = self._flatten_user(u)
                    row = {}
                    for ping_attr, col in effective_mapping.items():
                        val = flat.get(ping_attr)
                        if isinstance(val, (dict, list)):
                            try:
                                val = json.dumps(val)
                            except Exception:
                                pass
                        row[col] = val
                    rows.append(row)
                    tracker.record_transaction()
                    # Update status every 10 users or on last user
                    if idx % 10 == 0 or idx == total_users:
                        try:
                            percentage = int(idx / total_users * 100)
                            self.status_label.setText(f"Preparing {idx}/{total_users} ({percentage}%) users for export...")
                            self._set_processing_message(f"Preparing {idx}/{total_users} ({percentage}%) users for export...")
                        except Exception:
                            pass
                
                # Finish tracking and get statistics
                tracker.finish()
                tps_stats = tracker.get_statistics()
                
                # ensure table exists and insert
                try:
                    # Create table if it doesn't exist
                    db_utils.create_table_if_not_exists(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], table, list(effective_mapping.values()), conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
                    )
                    
                    # Add any missing columns to existing table
                    added_cols = db_utils.add_missing_columns(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], table, list(effective_mapping.values()), conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
                    )
                    
                    if added_cols:
                        cols_list = ", ".join(added_cols[:5])
                        if len(added_cols) > 5:
                            cols_list += f" (and {len(added_cols) - 5} more)"
                        self._set_processing_message(f"Added {len(added_cols)} missing columns to table: {cols_list}", 5000)
                    
                    # Insert the data
                    db_utils.insert_rows(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], table, rows, conn.get('driver'), encrypt_mode=conn.get('encrypt_mode')
                    )
                    msg = f"Exported {len(rows)} users to table {table}."
                    if filtered_out:
                        msg += f"\n\n(Filtered out {filtered_out} users by populated-attribute filter)"
                    if pop_filtered_out:
                        msg += f"\n\n(Filtered out {pop_filtered_out} users by population filter)"
                    QtWidgets.QMessageBox.information(self, "Export DB", msg)
                    # Show TPS report
                    self._show_tps_report(tps_stats, "Database Export")
                except Exception as e:
                    QtWidgets.QMessageBox.critical(self, "Export DB", f"Export failed: {e}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export DB", str(e))

    def _get_pingone_attributes(self) -> list:
        """Return schema-informed PingOne attribute names for mapping dialogs."""
        attrs = set()

        def _is_mappable_attr(name: str) -> bool:
            token = str(name or '').strip()
            if not token:
                return False
            return not (token.startswith('_links') or token.startswith('_embedded'))

        def _walk_schema(node, prefix=''):
            if not isinstance(node, dict):
                return
            props = node.get('properties')
            if isinstance(props, dict):
                for key, child in props.items():
                    full = f"{prefix}.{key}" if prefix else key
                    attrs.add(full)
                    _walk_schema(child, full)

        try:
            schema_path = Path('user_schema.json')
            if schema_path.exists():
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema = json.load(f)
                _walk_schema(schema)
        except Exception:
            pass

        extras = {
            'username', 'email', 'name.given', 'name.middle', 'name.family',
            'population.id', 'population.name',
            'phoneNumbers.mobile', 'phoneNumbers.work', 'phoneNumbers.home',
            'address',
            'address.streetAddress', 'address.street',
            'address.locality', 'address.city',
            'address.region', 'address.state',
            'address.postalCode', 'address.zip',
            'address.countryCode', 'address.country',
            'address.formatted',
            'employeeType', 'type',
            'title', 'department', 'organization',
            'enabled', 'id',
        }
        attrs.update(extras)

        # Include custom attributes present on already-loaded PingOne users.
        # This keeps mapping dialogs aware of tenant-specific schema extensions.
        try:
            for user in (self.users_cache or []):
                if not isinstance(user, dict):
                    continue
                self._collect_keys(user, '', attrs, depth=0, max_depth=6)
                flat_user = self._flatten_user(user)
                for key in flat_user.keys():
                    if _is_mappable_attr(key):
                        attrs.add(str(key))
        except Exception:
            pass

        attrs = {a for a in attrs if _is_mappable_attr(a)}
        return sorted(attrs)

    def connect_only(self, interactive: bool = True):
        """Attempt to obtain a token using the UI credentials and log success/failure."""
        client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
        profile_name = self.profile_list.currentText().strip() if hasattr(self, 'profile_list') else ""
        if not self.cl_sec.text().strip() and profile_name:
            # Manual connect/test should actively try keychain so macOS can show
            # Touch ID/password auth when needed.
            loaded_secret = ""
            try:
                loaded_secret = self._read_secret_from_keyring(profile_name, require_touch_id=True)
            except Exception:
                loaded_secret = ""
            if loaded_secret:
                self.cl_sec.setText(loaded_secret)
                self._cache_secret(profile_name, loaded_secret)
                client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
            elif self._macos_keychain_cli_available():
                QtWidgets.QMessageBox.information(
                    self,
                    "Missing Keychain Secret",
                    (
                        f"No native macOS Keychain secret was found for profile '{profile_name}'.\n\n"
                        "Enter the Client Secret in Configuration and use Save Profile once to store it in native Keychain.\n"
                        "After that, future retrieval uses the native Keychain path (Touch ID-capable)."
                    ),
                )
        self.prog.show(); self.prog.setRange(0, 0)
        try:
            token = asyncio.run(client.get_token())
        except Exception as e:
            token = None
            err = str(e)
        self.prog.hide()
        if token:
            # Record successful connection in connection log and credential logger
            try:
                api_client.write_connection_log(f"Successful connect for env={client.env_id}, client_id={client.client_id}")
            except Exception:
                pass
            try:
                if api_client.CREDENTIALS_LOGGING_ENABLED:
                    api_client.credential_logger.info(f"Connect succeeded: env={client.env_id}, client_id={client.client_id}")
            except Exception:
                pass
            # Show connection success in the status area instead of a modal dialog
            self.status_label.setText("Connected")
            try:
                self._set_processing_message("Connected")
            except Exception:
                pass
            # After successful connect, update users/populations counts
            try:
                self.refresh_users()
            except Exception:
                pass
            # Record last working profile in app meta so auto-connect can use it
            try:
                prof_name = self.profile_list.currentText()
                cfg = self._read_config()
                meta = cfg.get('__meta__', {})
                meta['last_working_profile'] = prof_name
                cfg['__meta__'] = meta
                self._write_config(cfg)
            except Exception:
                pass
        else:
            if interactive:
                QtWidgets.QMessageBox.critical(self, "Connect", "Auth Failed. Check credentials.")
            try:
                api_client.write_connection_log(f"Connect failed for env={client.env_id}, client_id={client.client_id}")
            except Exception:
                pass
            self.status_label.setText("Connection failed")
            try:
                self._set_processing_message("Connection failed")
            except Exception:
                pass

    def delete_current_profile(self):
        """Delete the currently selected profile from disk and keyring."""
        name = self.profile_list.currentText()
        if not name:
            QtWidgets.QMessageBox.information(self, "Delete Profile", "No profile selected.")
            return
        if QtWidgets.QMessageBox.question(self, "Delete Profile", f"Delete profile '{name}'? This will remove saved credentials.") != QtWidgets.QMessageBox.Yes:
            return
        p = self._read_config()
        if name in p:
            try:
                # Remove saved profile and associated keyring secret
                del p[name]
                self._write_config(p)
                try:
                    self._delete_secret_from_keyring(name)
                except Exception:
                    pass
                self._clear_cached_secret(name)
                self.load_profiles_from_disk()
                self.status_label.setText(f"Deleted profile {name}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Delete Profile", f"Failed to delete profile: {e}")
        else:
            QtWidgets.QMessageBox.information(self, "Delete Profile", "Profile not found.")

    def show_profile_manager(self):
        """Show the profile manager dialog to view and delete profiles."""
        try:
            cfg = self._read_config()
            current_profile = self.profile_list.currentText()
            
            # Show dialog
            dialog = ProfileManagerDialog(cfg, current_profile, self)
            
            # Provide a connection callback for testing new profiles
            def test_connection():
                """Test connection and return True if successful."""
                new_profile = dialog.get_new_profile_name()
                new_credentials = dialog.get_new_profile_credentials()
                
                if not new_profile or not new_credentials:
                    return False
                
                # Save the config and credentials first
                self._write_config(cfg)
                
                # Save credentials to keyring
                env_id, client_id, secret = new_credentials
                try:
                    if secret:
                        self._write_secret_to_keyring(new_profile, secret)
                        self._cache_secret(new_profile, secret)
                except Exception as e:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Keyring Error",
                        f"Failed to save client secret to keyring: {e}\n\nYou can enter it manually in the Configuration tab."
                    )
                
                # Reload profiles and switch to new one (don't trigger an auto-connect
                # while we're still inside the profile manager dialog)
                self.load_profiles_from_disk(skip_connect=True)
                idx = self.profile_list.findText(new_profile)
                if idx >= 0:
                    self.profile_list.setCurrentIndex(idx)
                
                # Test the connection synchronously
                client = api_client.PingOneClient(env_id, client_id, secret)
                err = None
                try:
                    token = asyncio.run(client.get_token())
                    if token:
                        # Update status
                        self.status_label.setText(f"Connected to profile '{new_profile}'")
                        try:
                            self._set_processing_message(f"Connected to profile '{new_profile}'")
                        except Exception:
                            pass
                        # Refresh users
                        try:
                            self.refresh_users()
                        except Exception:
                            pass
                        return True
                except Exception as e:
                    err = str(e)
                
                # report failure with details to the dialog so user can troubleshoot
                msg = "Could not connect with provided credentials. Please check and try again."
                if err:
                    msg += f"\n\n{err.splitlines()[0]}"
                QtWidgets.QMessageBox.critical(dialog, "Connection Failed", msg)
                return False
            
            dialog.set_connection_callback(test_connection)
            
            # Execute the dialog (blocks until closed)
            result = dialog.exec()
            
            # Check if a new profile was created (but not auto-connected)
            new_profile = dialog.get_new_profile_name()
            new_credentials = dialog.get_new_profile_credentials()
            auto_connect = dialog.should_auto_connect()
            
            # Process any deletions
            deleted = dialog.get_deleted_profiles()
            
            # Save if there were any changes (and connection wasn't already tested)
            if (deleted or new_profile) and not auto_connect:
                # Save updated config
                self._write_config(cfg)
                
                # Save credentials to keyring if provided
                if new_profile and new_credentials:
                    env_id, client_id, secret = new_credentials
                    try:
                        if secret:
                            self._write_secret_to_keyring(new_profile, secret)
                            self._cache_secret(new_profile, secret)
                    except Exception as e:
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Keyring Error",
                            f"Failed to save client secret to keyring: {e}\n\nYou can enter it manually in the Configuration tab."
                        )
                
                # Reload profiles in the UI (skip any automatic connection attempt)
                self.load_profiles_from_disk(skip_connect=True)
                
                # Switch to the new profile
                if new_profile:
                    try:
                        idx = self.profile_list.findText(new_profile)
                        if idx >= 0:
                            self.profile_list.setCurrentIndex(idx)
                    except Exception:
                        pass
                
                # Build status message
                msg_parts = []
                if deleted:
                    msg_parts.append(f"Deleted {len(deleted)} profile(s)")
                if new_profile:
                    msg_parts.append(f"Created profile '{new_profile}'")
                
                msg = "; ".join(msg_parts)
                try:
                    self._set_processing_message(msg)
                except Exception:
                    pass
            
            # Clean up keyring entries for deleted profiles
            if deleted:
                for profile_name in deleted:
                    try:
                        self._delete_secret_from_keyring(profile_name)
                    except Exception:
                        pass
                    self._clear_cached_secret(profile_name)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Profile Manager", f"Error opening profile manager: {e}")

    def on_fetch_success(self, data):
        # Called when UserFetchWorker finishes; populate the table and
        # update UI state. Keep sorting temporarily disabled while
        # repopulating to avoid unnecessary reorders.
        self.prog.hide(); self.u_table.setSortingEnabled(False)
        self.lbl_stats.setText(f"Users: {data['user_count']} | Populations: {data['pop_count']}")
        # Log successful fetch/connect for debugging/audit purposes
        try:
            api_client.write_connection_log(f"Fetch success: users={data.get('user_count',0)}, pops={data.get('pop_count',0)}")
        except Exception:
            pass
        self.pop_map, self.users_cache = data['pop_map'], data['users']
        
        self.all_columns = self._get_all_columns(self.users_cache)
        # Use saved column configuration, filtering to only columns present in dataset
        self.columns = self._get_visible_columns(self.selected_columns, self.all_columns)
        
        # Disable sorting during table rebuild for better performance
        self.u_table.setSortingEnabled(False)
        self.u_table.setColumnCount(len(self.columns))
        self.u_table.setHorizontalHeaderLabels(self._get_column_labels())
        self.u_table.setRowCount(len(self.users_cache))
        
        # Populate table rows
        for row_idx, user in enumerate(self.users_cache):
            for col_idx, col in enumerate(self.columns):
                value = self._get_value(user, col)
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setData(QtCore.Qt.UserRole, value)
                self.u_table.setItem(row_idx, col_idx, item)
        
        self.u_table.setSortingEnabled(True)
        msg = f"Loaded {data['user_count']} users, {data['pop_count']} populations"
        try:
            self._set_processing_message(msg)
        except Exception:
            pass
        
        # Update TPS in status bar if available
        tps_stats = data.get('tps_stats')
        if tps_stats and tps_stats.get('total_transactions', 0) > 0:
            self._update_tps_status_bar(tps_stats, "Refresh")

    def _get_all_columns(self, users):
        """Get list of all available columns based on populated attributes in users."""
        all_keys = set()
        for u in users:
            self._collect_keys(u, '', all_keys)
        # Filter to only include keys that have at least one non-empty value
        populated_keys = set()
        for u in users:
            for key in all_keys:
                if self._get_value(u, key).strip():
                    populated_keys.add(key)
        # Replace population.id with population.name for display
        if 'population.id' in populated_keys:
            populated_keys.discard('population.id')
            populated_keys.add('population.name')

        # PingOne work-email aliases should appear as `mail` in User Management.
        _work_aliases = {'workEmail', 'workemail', 'trilogieWorkEmail'}
        if any(a in populated_keys for a in _work_aliases):
            for a in _work_aliases:
                populated_keys.discard(a)
            populated_keys.add('mail')

        # PingOne work-telephone aliases should appear as `workTelephone`.
        _work_tel_aliases = {'workTelephone', 'workTel', 'trilogieWorkTel'}
        has_work_phone = False
        for u in users or []:
            try:
                for a in _work_tel_aliases:
                    v = u.get(a, '')
                    if isinstance(v, str) and v.strip():
                        has_work_phone = True
                        break
                if has_work_phone:
                    break
                phones = u.get('phoneNumbers', [])
                if isinstance(phones, list):
                    for ph in phones:
                        if not isinstance(ph, dict):
                            continue
                        ptype = str(ph.get('type', '')).strip().lower()
                        pnum = str(ph.get('number', '')).strip()
                        if ptype == 'work' and pnum:
                            has_work_phone = True
                            break
                if has_work_phone:
                    break
            except Exception:
                pass
        if any(a in populated_keys for a in _work_tel_aliases) or has_work_phone:
            for a in _work_tel_aliases:
                populated_keys.discard(a)
            populated_keys.add('workTelephone')

        return sorted(populated_keys)

    def _collect_keys(self, obj, prefix, keys, depth=0, max_depth=3):
        """Recursively collect keys from dict/object."""
        if depth > max_depth:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                full_key = f"{prefix}.{k}" if prefix else k
                keys.add(full_key)
                self._collect_keys(v, full_key, keys, depth + 1, max_depth)
        elif isinstance(obj, list):
            for item in obj[:5]:
                self._collect_keys(item, prefix, keys, depth + 1, max_depth)

    def _get_value(self, user, key):
        """Get value from user dict using dot notation."""
        # Special case: phoneNumbers - extract the first number as a readable string.
        if key == 'phoneNumbers':
            try:
                phones = user.get('phoneNumbers', [])
                if isinstance(phones, list) and phones:
                    first = phones[0]
                    if isinstance(first, dict):
                        return str(first.get('number', '') or '')
                    return str(first) if first else ''
            except Exception:
                pass
            return ''
        # Alias PingOne work-email fields to `mail` in the grid.
        if key == 'mail':
            try:
                if isinstance(user.get('mail'), str) and user.get('mail').strip():
                    return user.get('mail').strip()
            except Exception:
                pass
            for alt in ('workEmail', 'workemail', 'trilogieWorkEmail'):
                try:
                    v = user.get(alt, '')
                    if isinstance(v, str) and v.strip():
                        return v.strip()
                except Exception:
                    pass
            return ''
        # Alias PingOne work telephone fields to `workTelephone` in the grid.
        if key == 'workTelephone':
            for alt in ('workTelephone', 'workTel', 'trilogieWorkTel'):
                try:
                    v = user.get(alt, '')
                    if isinstance(v, str) and v.strip():
                        return v.strip()
                except Exception:
                    pass
            try:
                phones = user.get('phoneNumbers', [])
                if isinstance(phones, list):
                    for ph in phones:
                        if not isinstance(ph, dict):
                            continue
                        ptype = str(ph.get('type', '')).strip().lower()
                        pnum = str(ph.get('number', '')).strip()
                        if ptype == 'work' and pnum:
                            return pnum
            except Exception:
                pass
            return ''
        parts = key.split('.')
        current = user
        try:
            for part in parts:
                if isinstance(current, dict):
                    current = current.get(part, '')
                else:
                    return ''
            if key == 'population.id':
                return self.pop_map.get(current, current) if current else ''
            elif key == 'population.name':
                p_id = user.get('population', {}).get('id', '')
                return self.pop_map.get(p_id, p_id)
            return str(current) if current else ''
        except:
            return ''

    def _set_user_value(self, user: dict, key: str, value):
        """Set a user value by key, supporting dotted paths for nested fields."""
        if not isinstance(user, dict):
            return
        key = str(key or '').strip()
        if not key:
            return

        # Keep `mail` mapped to whichever work-email field exists in payload.
        if key == 'mail':
            target = None
            for alt in ('workEmail', 'workemail', 'trilogieWorkEmail', 'mail'):
                if alt in user:
                    target = alt
                    break
            user[target or 'mail'] = value
            return

        # Keep work telephone mapped to whichever work-tel field exists.
        if key == 'workTelephone':
            target = None
            for alt in ('workTelephone', 'workTel', 'trilogieWorkTel'):
                if alt in user:
                    target = alt
                    break
            val = str(value or '').strip()
            if target:
                user[target] = val
                return

            # Fallback to typed phoneNumbers entry if no dedicated field exists.
            phones = user.get('phoneNumbers') if isinstance(user.get('phoneNumbers'), list) else []
            if not isinstance(phones, list):
                phones = []
            updated = False
            for ph in phones:
                if not isinstance(ph, dict):
                    continue
                if str(ph.get('type', '')).strip().lower() == 'work':
                    ph['number'] = val
                    updated = True
                    break
            if not updated and val:
                phones.append({'type': 'work', 'number': val})
            if phones:
                user['phoneNumbers'] = phones
            elif 'phoneNumbers' in user:
                user.pop('phoneNumbers', None)
            return

        # Common display/edit aliases that need shape-aware writes.
        if key == 'phoneNumbers' and isinstance(value, str):
            val = value.strip()
            if val:
                user['phoneNumbers'] = [{'type': 'mobile', 'number': val}]
            else:
                user.pop('phoneNumbers', None)
            return

        if key == 'population.name':
            name = str(value or '').strip()
            pop_id = self.pop_map.get(name, '')
            pop = user.get('population') if isinstance(user.get('population'), dict) else {}
            if pop_id:
                pop['id'] = pop_id
            elif name:
                pop['name'] = name
            user['population'] = pop
            return

        if key == 'population.id':
            pop = user.get('population') if isinstance(user.get('population'), dict) else {}
            pop['id'] = value
            user['population'] = pop
            return

        if '.' not in key:
            user[key] = value
            return

        parts = key.split('.')
        cur = user
        for part in parts[:-1]:
            nxt = cur.get(part)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[part] = nxt
            cur = nxt
        cur[parts[-1]] = value

    def _sanitize_user_update_payload(self, payload: dict) -> dict:
        """Remove read-only/internal fields before sending a user PUT update."""
        if not isinstance(payload, dict):
            return {}

        out = copy.deepcopy(payload)
        blocked_top_level = {
            'id',
            '_links',
            'account',
            'environment',
            'lifecycle',
            'identityProvider',
            'createdAt',
            'updatedAt',
            'lastSignOn',
            'mfaEnabled',
            'verifyStatus',
        }
        for key in blocked_top_level:
            out.pop(key, None)

        # Keep only writable population shape.
        pop = out.get('population')
        if isinstance(pop, dict):
            pop_id = pop.get('id')
            out['population'] = {'id': pop_id} if pop_id else {}
            if not out['population']:
                out.pop('population', None)
        elif pop is not None:
            out.pop('population', None)

        # Remove invalid address values - PingOne requires address to be a COMPLEX
        # object with at least one sub-attribute, or omitted entirely.
        # String values, empty objects, and None are all invalid.
        addr = out.get('address')
        if addr is None or addr == '' or addr == []:
            out.pop('address', None)
        elif isinstance(addr, str):
            # Address was provided as a simple string - remove it since PingOne
            # requires a complex object with sub-attributes like streetAddress, locality.
            out.pop('address', None)
        elif isinstance(addr, dict):
            # Remove empty string values and None values from address
            cleaned_addr = {k: v for k, v in addr.items() if v not in (None, '', [])}
            if cleaned_addr:
                out['address'] = cleaned_addr
            else:
                out.pop('address', None)

        return out

    def delete_selected_users(self):
        rows = self.u_table.selectionModel().selectedRows()
        if not rows:
            current_row = self.u_table.currentRow()
            if current_row >= 0:
                self.u_table.selectRow(current_row)
                rows = self.u_table.selectionModel().selectedRows()
        if not rows:
            return
        id_col = self.columns.index('id') if 'id' in self.columns else -1
        if id_col == -1:
            return
        uids = [self.u_table.item(r.row(), id_col).text() for r in rows]
        if not self._confirm_user_deletion(len(uids)):
            return

        client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
        self.cancel_requested = False
        self.cancel_btn.setText("Cancel Delete")
        self.cancel_btn.setEnabled(True)
        self.prog.show()
        self.cancel_btn.show()
        
        # PHASE 2 OPTIMIZATION: Use parallel processing for large deletions
        concurrency = 5 if len(uids) > 50 else 1  # Use 5 concurrent requests for >50 users
        w = BulkDeleteWorker(client, uids, cancel_check=lambda: self.cancel_requested, concurrency=concurrency)
        w.signals.status.connect(lambda msg: self._set_processing_message(msg))
        w.signals.tps_update.connect(lambda tps_stats: self._update_tps_status_bar(tps_stats, "Delete"))
        
        def on_delete_done(res):
            self.prog.hide()
            self.cancel_btn.hide()
            deleted = res.get('deleted', 0)
            failed = res.get('failed', 0)
            total = res.get('total', 0)
            tps_stats = res.get('tps_stats')
            failed_ids = res.get('failed_ids', [])
            
            # Show TPS report if available
            if tps_stats and tps_stats.get('total_transactions', 0) > 0:
                self._show_tps_report(tps_stats, "Delete")
            
            # Show result message
            msg = f"Deleted {deleted}/{total} users"
            if failed > 0:
                msg += f" ({failed} failed)"
            
            try:
                self._set_processing_message(msg, 5000)
            except Exception:
                pass
            
            # Show failed IDs if any
            if failed_ids:
                failed_msg = f"{failed} deletion(s) failed.\n\nFailed user IDs:\n" + "\n".join(failed_ids[:20])
                if len(failed_ids) > 20:
                    failed_msg += f"\n... and {len(failed_ids) - 20} more"
                QtWidgets.QMessageBox.warning(self, "Delete Errors", failed_msg)
            
            self.refresh_users()
        
        w.signals.finished.connect(on_delete_done)
        self.threadpool.start(w)

    def _confirm_user_deletion(self, count: int) -> bool:
        """Return True when deletion should proceed based on prompt preference."""
        if count <= 0:
            return False

        if not bool(getattr(self, 'prompt_before_delete', True)):
            return True

        noun = "user" if count == 1 else "users"
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Warning)
        box.setWindowTitle("Delete")
        box.setText(f"Delete {count} {noun}?")
        box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        box.setDefaultButton(QtWidgets.QMessageBox.No)
        prompt_cb = QtWidgets.QCheckBox("Always prompt before deleting users")
        prompt_cb.setChecked(bool(getattr(self, 'prompt_before_delete', True)))
        box.setCheckBox(prompt_cb)
        result = box.exec()

        try:
            self.prompt_before_delete = bool(prompt_cb.isChecked())
            self.save_profile_option()
            self.save_app_settings()
        except Exception:
            pass

        return result == QtWidgets.QMessageBox.Yes

    def filter_table(self):
        txt = self.search_bar.text().lower()
        for i in range(self.u_table.rowCount()):
            match = any(txt in (self.u_table.item(i, j).text() or "").lower() for j in range(self.u_table.columnCount()))
            self.u_table.setRowHidden(i, not match)

    def toggle_json_editing(self):
        """Toggle JSON editing mode."""
        self.json_editing_enabled = self.enable_json_edit_action.isChecked()

    def toggle_api_logging(self):
        """Toggle API logging to file."""
        # Use the API client's runtime setter so workers and client see the change
        enabled = self.enable_api_logging_action.isChecked()
        api_client.set_api_logging(enabled)
        # The UI also provides quick feedback showing where logs are written
        # so users can open them or share with support when debugging.
        if enabled:
            api_client.api_logger.info(f"API Logging enabled at {datetime.now()}")
            try:
                path = api_client.LOG_FILE.resolve()
            except Exception:
                path = api_client.LOG_FILE
            msg = f"API logging enabled - File: {path}"
            try:
                self._set_processing_message(msg)
            except Exception:
                pass
        else:
            api_client.api_logger.info(f"API Logging disabled at {datetime.now()}")
            msg = "API logging disabled"
            try:
                self._set_processing_message(msg)
            except Exception:
                pass

    def toggle_credentials_logging(self):
        """Enable/disable credential event logging to credentials.log."""
        enabled = self.enable_credentials_logging_action.isChecked()
        try:
            api_client.set_credentials_logging(enabled)
            msg = "Credentials logging enabled" if enabled else "Credentials logging disabled"
            try:
                self._set_processing_message(msg)
            except Exception:
                pass
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Logging", f"Failed to change credential logging: {e}")

    def set_credentials_log_level(self):
        """Prompt user to select a credentials log level."""
        self._prompt_set_log_level("credentials")

    def _prompt_set_log_level(self, log_kind: str):
        """Prompt and apply a log level for supported log types."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        current_idx = 1
        if log_kind == "api":
            try:
                lvl_name = logging.getLevelName(api_client.api_logger.level)
                if lvl_name in levels:
                    current_idx = levels.index(lvl_name)
            except Exception:
                pass
            title = "API Log Level"
        elif log_kind == "credentials":
            try:
                lvl_name = logging.getLevelName(api_client.credential_logger.level)
                if lvl_name in levels:
                    current_idx = levels.index(lvl_name)
            except Exception:
                pass
            title = "Credentials Log Level"
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Log Level Not Available",
                "Connection log entries are plain text and do not support log levels."
            )
            return

        lvl, ok = QtWidgets.QInputDialog.getItem(self, title, "Level:", levels, current_idx, False)
        if not ok or not lvl:
            return
        try:
            if log_kind == "api":
                api_client.api_logger.setLevel(getattr(logging, lvl, logging.INFO))
            else:
                api_client.set_credentials_log_level(lvl)
            try:
                self._set_processing_message(f"{title} set to {lvl}")
            except Exception:
                pass
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Logging", f"Failed to set log level: {e}")

    def _show_log_viewer(self, title: str, path: Path, log_kind: str, include_filter: str = ""):
        """Show a log viewer with Set Level, Reset, and Save commands."""
        p = Path(path)
        key = (str(p.resolve() if p.exists() else p), str(include_filter or ''))

        # Reuse existing viewer window for the same log/filter combination.
        existing = self._open_log_windows.get(key)
        if existing is not None:
            try:
                existing.show()
                existing.raise_()
                existing.activateWindow()
                return
            except Exception:
                self._open_log_windows.pop(key, None)

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setModal(False)
        dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        dlg.setWindowFlag(QtCore.Qt.Window, True)
        lay = QtWidgets.QVBoxLayout(dlg)

        cmd_row = QtWidgets.QHBoxLayout()
        set_level_btn = QtWidgets.QPushButton("Set Log Level")
        reset_btn = QtWidgets.QPushButton("Reset Log")
        save_btn = QtWidgets.QPushButton("Save Log As...")
        refresh_btn = QtWidgets.QPushButton("Refresh")
        close_btn = QtWidgets.QPushButton("Close")
        cmd_row.addWidget(set_level_btn)
        cmd_row.addWidget(reset_btn)
        cmd_row.addWidget(save_btn)
        cmd_row.addWidget(refresh_btn)
        cmd_row.addStretch()
        cmd_row.addWidget(close_btn)
        lay.addLayout(cmd_row)

        path_line = QtWidgets.QLineEdit(str(p.resolve() if p.exists() else p))
        path_line.setReadOnly(True)
        lay.addWidget(path_line)

        if include_filter:
            filter_line = QtWidgets.QLineEdit(f"Filter: {include_filter}")
            filter_line.setReadOnly(True)
            lay.addWidget(filter_line)

        te = QtWidgets.QTextEdit()
        te.setReadOnly(True)
        lay.addWidget(te)

        def refresh_text():
            try:
                if p.exists():
                    content = p.read_text(encoding='utf-8', errors='replace')
                    if include_filter:
                        lines = [ln for ln in content.splitlines() if include_filter in ln]
                        content = "\n".join(lines)
                    te.setPlainText(content)
                else:
                    te.setPlainText(f"Log file does not exist yet: {p}")
                te.moveCursor(QtGui.QTextCursor.End)
            except Exception as e:
                te.setPlainText(f"Failed to read log file:\n{e}")

        def reset_and_refresh():
            self.reset_log_file(p)
            refresh_text()

        def save_copy():
            options = self._get_native_file_dialog_options()
            default_name = f"{p.stem}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}{p.suffix or '.log'}"
            out_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Save Log Copy",
                default_name,
                "Log Files (*.log *.txt);;All Files (*)",
                options=options,
            )
            if not out_path:
                return
            try:
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(te.toPlainText())
                QtWidgets.QMessageBox.information(self, "Save Log", f"Saved log copy to {out_path}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Save Log", f"Failed to save log copy: {e}")

        set_level_btn.clicked.connect(lambda: self._prompt_set_log_level(log_kind))
        reset_btn.clicked.connect(reset_and_refresh)
        save_btn.clicked.connect(save_copy)
        refresh_btn.clicked.connect(refresh_text)
        close_btn.clicked.connect(dlg.close)

        def _on_destroyed(*_args):
            try:
                self._open_log_windows.pop(key, None)
            except Exception:
                pass

        dlg.destroyed.connect(_on_destroyed)
        self._open_log_windows[key] = dlg

        refresh_text()
        dlg.resize(980, 520)
        dlg.show()

    def show_log_files(self):
        """Display a small dialog listing the log files and allow opening them."""
        logs = [
            ("API Calls Log", getattr(api_client, 'LOG_FILE', Path('api_calls.log')), "api"),
            ("Connection Log", getattr(api_client, 'CONNECTION_LOG', Path('connection_errors.log')), "connection"),
            ("Credentials Log", getattr(api_client, 'CREDENTIALS_LOG', Path('credentials.log')), "credentials"),
        ]
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Log Files")
        lay = QtWidgets.QVBoxLayout(dlg)
        for label, p, kind in logs:
            try:
                pth = p.resolve()
            except Exception:
                pth = p
            row = QtWidgets.QHBoxLayout()
            lbl = QtWidgets.QLabel(f"{label}:")
            val = QtWidgets.QLineEdit(str(pth))
            val.setReadOnly(True)
            btn = QtWidgets.QPushButton("View")
            btn.clicked.connect(functools.partial(self._show_log_viewer, label, pth, kind))
            row.addWidget(lbl)
            row.addWidget(val)
            row.addWidget(btn)
            lay.addLayout(row)
        # Clear all logs button
        btn_row = QtWidgets.QHBoxLayout()
        clear_all_btn = QtWidgets.QPushButton("Clear All Logs")
        def _clear_all():
            try:
                if QtWidgets.QMessageBox.question(self, "Clear All Logs", "Truncate all known log files? This cannot be undone.") != QtWidgets.QMessageBox.Yes:
                    return
                for _lbl, p in logs:
                    try:
                        with open(p, 'w', encoding='utf-8'):
                            pass
                    except Exception:
                        pass
                QtWidgets.QMessageBox.information(self, "Clear All Logs", "All known logs truncated.")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Clear All Logs", f"Failed to clear logs: {e}")
        clear_all_btn.clicked.connect(_clear_all)
        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(dlg.accept)
        btn_row.addWidget(clear_all_btn)
        btn_row.addStretch()
        btn_row.addWidget(close)
        lay.addLayout(btn_row)
        dlg.resize(800, 120)
        dlg.exec()

    def view_user_mgmt_edit_log(self):
        """Open connection log filtered to USER_MGMT_EDIT_ entries."""
        p = getattr(api_client, 'CONNECTION_LOG', Path('connection_errors.log'))
        self._show_log_viewer(
            "Connection Log - User Mgmt Edit Entries",
            p,
            "connection",
            include_filter="USER_MGMT_EDIT_",
        )

    def show_api_capture_dialog(self):
        """Open a dialog to start/stop a live API-capture session and view events."""
        key = ("__api_capture__", "")
        existing = self._open_log_windows.get(key)
        if existing is not None:
            try:
                existing.show()
                existing.raise_()
                existing.activateWindow()
                return
            except Exception:
                self._open_log_windows.pop(key, None)

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("API Capture")
        dlg.setModal(False)
        dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        dlg.setWindowFlag(QtCore.Qt.Window, True)
        lay = QtWidgets.QVBoxLayout(dlg)
        te = QtWidgets.QTextEdit(); te.setReadOnly(True)
        btn_row = QtWidgets.QHBoxLayout()
        start_btn = QtWidgets.QPushButton("Start Capture")
        stop_btn = QtWidgets.QPushButton("Stop Capture")
        stop_btn.setEnabled(False)
        set_level_btn = QtWidgets.QPushButton("Set Log Level")
        reset_btn = QtWidgets.QPushButton("Reset")
        save_btn = QtWidgets.QPushButton("Save...")
        close_btn = QtWidgets.QPushButton("Close")
        btn_row.addWidget(start_btn)
        btn_row.addWidget(stop_btn)
        btn_row.addWidget(set_level_btn)
        btn_row.addWidget(reset_btn)
        btn_row.addWidget(save_btn)
        stats_lbl = QtWidgets.QLabel("Refreshes: 0 | Events: 0")
        btn_row.addWidget(stats_lbl)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row); lay.addWidget(te)

        timer = QtCore.QTimer(dlg)
        timer.setInterval(500)
        refresh_count = 0
        event_count = 0

        def poll_events():
            nonlocal refresh_count, event_count
            try:
                refresh_count += 1
                events = api_client.get_and_clear_live_events()
                if events:
                    event_count += len(events)
                    te.moveCursor(QtGui.QTextCursor.End)
                    te.insertPlainText("\n".join(events) + "\n")
                    te.moveCursor(QtGui.QTextCursor.End)
                stats_lbl.setText(f"Refreshes: {refresh_count} | Events: {event_count}")
            except Exception:
                pass

        timer.timeout.connect(poll_events)

        def start():
            api_client.enable_live_capture(True)
            # enable API logging to ensure calls are recorded
            self.enable_api_logging_action.setChecked(True)
            api_client.set_api_logging(True)
            start_btn.setEnabled(False); stop_btn.setEnabled(True)
            te.clear()
            nonlocal refresh_count, event_count
            refresh_count = 0
            event_count = 0
            stats_lbl.setText("Refreshes: 0 | Events: 0")
            timer.start()

        def stop():
            timer.stop()
            api_client.enable_live_capture(False)
            # leave API logging state as-is; UI shows the toggle
            start_btn.setEnabled(True); stop_btn.setEnabled(False)

        def save():
            options = self._get_native_file_dialog_options()
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save Capture", "api_capture.txt", "Text Files (*.txt);;All Files (*)", options=options
            )
            if not path:
                return
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(te.toPlainText())
                QtWidgets.QMessageBox.information(self, "Saved", f"Saved capture to {path}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Save Failed", str(e))

        def reset_capture():
            nonlocal refresh_count, event_count
            te.clear()
            refresh_count = 0
            event_count = 0
            stats_lbl.setText("Refreshes: 0 | Events: 0")

        def set_level():
            self._prompt_set_log_level("api")

        start_btn.clicked.connect(start)
        stop_btn.clicked.connect(stop)
        set_level_btn.clicked.connect(set_level)
        reset_btn.clicked.connect(reset_capture)
        save_btn.clicked.connect(save)
        close_btn.clicked.connect(lambda: (stop(), dlg.close()))

        def _on_destroyed(*_args):
            try:
                self._open_log_windows.pop(key, None)
            except Exception:
                pass

        dlg.destroyed.connect(_on_destroyed)
        self._open_log_windows[key] = dlg

        dlg.resize(900, 400)
        dlg.show()

    def reset_log_file(self, path: Path):
        """Truncate the given log file after confirmation."""
        try:
            try:
                p = Path(path)
            except Exception:
                p = Path(str(path))
            if not p.exists():
                QtWidgets.QMessageBox.information(self, "Reset Log", f"Log file does not exist: {p}")
                return
            if QtWidgets.QMessageBox.question(self, "Reset Log", f"Truncate {p}? This cannot be undone.") != QtWidgets.QMessageBox.Yes:
                return
            with open(p, 'w', encoding='utf-8'):
                pass
            QtWidgets.QMessageBox.information(self, "Reset Log", f"Truncated {p}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Reset Log", f"Failed to truncate {path}: {e}")

    def clear_all_logs(self):
        """Truncate all known log files without archiving."""
        logs = [getattr(api_client, 'LOG_FILE', Path('api_calls.log')), getattr(api_client, 'CONNECTION_LOG', Path('connection_errors.log')), getattr(api_client, 'CREDENTIALS_LOG', Path('credentials.log'))]
        if QtWidgets.QMessageBox.question(self, "Clear All Logs", "Truncate all known log files? This cannot be undone.") != QtWidgets.QMessageBox.Yes:
            return
        errs = []
        for p in logs:
            try:
                with open(p, 'w', encoding='utf-8'):
                    pass
            except Exception as e:
                errs.append(f"{p}: {e}")
        if errs:
            QtWidgets.QMessageBox.warning(self, "Clear All Logs", "Some logs could not be truncated:\n" + "\n".join(errs))
        else:
            QtWidgets.QMessageBox.information(self, "Clear All Logs", "All known logs truncated.")

    def archive_logs(self):
        """Create a zip archive containing all known logs (timestamped).

        The archive is written to the selected directory. Originals are left in place.
        """
        logs = [getattr(api_client, 'LOG_FILE', Path('api_calls.log')), getattr(api_client, 'CONNECTION_LOG', Path('connection_errors.log')), getattr(api_client, 'CREDENTIALS_LOG', Path('credentials.log'))]
        existing = [p for p in logs if Path(p).exists()]
        if not existing:
            QtWidgets.QMessageBox.information(self, "Archive Logs", "No log files found to archive.")
            return
        options = self._get_native_file_dialog_options()
        dest_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Archive Directory", str(Path.cwd()), options=options
        )
        if not dest_dir:
            return
        ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        archive_name = Path(dest_dir) / f"logs_archive_{ts}.zip"
        try:
            with zipfile.ZipFile(archive_name, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                for p in existing:
                    try:
                        zf.write(str(p), arcname=Path(p).name)
                    except Exception:
                        pass
            # Ask whether to rotate (truncate) originals after archiving
            rotate = QtWidgets.QMessageBox.question(self, "Archive Logs", f"Archived logs to {archive_name}.\n\nRotate logs (truncate originals) now?")
            if rotate == QtWidgets.QMessageBox.Yes:
                errs = []
                for p in existing:
                    try:
                        with open(p, 'w', encoding='utf-8'):
                            pass
                    except Exception as e:
                        errs.append(f"{p}: {e}")
                if errs:
                    QtWidgets.QMessageBox.warning(self, "Archive Logs", "Archived but failed to rotate some logs:\n" + "\n".join(errs))
                else:
                    QtWidgets.QMessageBox.information(self, "Archive Logs", f"Archived and rotated logs to {archive_name}")
            else:
                QtWidgets.QMessageBox.information(self, "Archive Logs", f"Archived logs to {archive_name}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Archive Logs", f"Failed to archive logs: {e}")

    def test_credentials(self):
        """Attempt to obtain a token using provided credentials and report result.

        The user flow frequently runs into failures that are not strictly
        "bad client ID/secret" (network errors, mis‑typed environment ID, etc.);
        the original implementation swallowed the exception message and always
        displayed the generic
        "Auth Failed. Check credentials." dialog. That's confusing during
        debugging, so we now offer the underlying error text in a separate
        detail window when available.
        """
        client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
        profile_name = self.profile_list.currentText().strip() if hasattr(self, 'profile_list') else ""
        if not self.cl_sec.text().strip() and profile_name:
            loaded_secret = ""
            try:
                loaded_secret = self._read_secret_from_keyring(profile_name, require_touch_id=True)
            except Exception:
                loaded_secret = ""
            if loaded_secret:
                self.cl_sec.setText(loaded_secret)
                self._cache_secret(profile_name, loaded_secret)
                client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
            elif self._macos_keychain_cli_available():
                QtWidgets.QMessageBox.information(
                    self,
                    "Missing Keychain Secret",
                    (
                        f"No native macOS Keychain secret was found for profile '{profile_name}'.\n\n"
                        "Enter the Client Secret in Configuration and use Save Profile once to store it in native Keychain.\n"
                        "After that, future retrieval uses the native Keychain path (Touch ID-capable)."
                    ),
                )
        err = None
        try:
            token = asyncio.run(client.get_token())
        except Exception as e:
            token = None
            err = str(e)
        if token:
            QtWidgets.QMessageBox.information(self, "Test Credentials", "Token obtained successfully.")
            try:
                api_client.credential_logger.info(f"Test credentials succeeded: env={client.env_id}, client_id={client.client_id}")
            except Exception:
                pass
            try:
                self._set_processing_message("Credentials valid")
            except Exception:
                pass
        else:
            if not err:
                err = client.last_error
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Critical)
            msg_box.setWindowTitle("Test Credentials")
            msg_box.setText("Auth Failed. Check credentials.")
            if err:
                msg_box.setInformativeText("Would you like to view the detailed error message?")
                msg_box.setStandardButtons(
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
                )
                msg_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Yes)
            else:
                msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
            result = msg_box.exec()
            if err and result == QtWidgets.QMessageBox.StandardButton.Yes:
                self.show_detail_message_window("Credential Test Details", err)
            try:
                api_client.credential_logger.error(f"Test credentials failed: env={client.env_id}, client_id={client.client_id} - {err}")
            except Exception:
                pass
            try:
                self._set_processing_message("Credentials invalid")
            except Exception:
                pass

    def show_detail_message_window(self, title: str, message: str):
        """Show a read-only detail window for longer error messages."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(760, 420)

        layout = QtWidgets.QVBoxLayout(dlg)
        text = QtWidgets.QTextEdit(dlg)
        text.setReadOnly(True)
        text.setPlainText(message or "")
        layout.addWidget(text)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close, parent=dlg)
        buttons.rejected.connect(dlg.reject)
        buttons.accepted.connect(dlg.accept)
        layout.addWidget(buttons)
        dlg.exec()

    def new_connection(self):
        """Clear credential fields and prepare to save a profile once entry is complete."""
        self.env_id.clear()
        self.cl_id.clear()
        self.cl_sec.clear()
        self.env_id.setFocus()
        # track that we should prompt when all three fields are filled
        self._new_conn_mode = True

    def _new_conn_field_edited(self):
        """Called on textChanged for any credential field while in new-connection mode.

        Starts a short debounce timer so the save dialog appears automatically
        once all three fields are non-empty, regardless of which field was
        edited last or whether focus has moved.
        """
        if not getattr(self, '_new_conn_mode', False):
            return
        if not (self.env_id.text().strip() and self.cl_id.text().strip() and self.cl_sec.text().strip()):
            # Not all fields filled yet; cancel any pending prompt.
            if hasattr(self, '_new_conn_timer'):
                self._new_conn_timer.stop()
            return
        # All three are filled — (re)start debounce timer.
        if not hasattr(self, '_new_conn_timer'):
            self._new_conn_timer = QtCore.QTimer(self)
            self._new_conn_timer.setSingleShot(True)
            self._new_conn_timer.timeout.connect(self._prompt_save_new_profile)
        self._new_conn_timer.start(600)

    def _prompt_save_new_profile(self):
        """Show the save-profile dialog after the debounce period has elapsed."""
        if not getattr(self, '_new_conn_mode', False):
            return
        if not (self.env_id.text().strip() and self.cl_id.text().strip() and self.cl_sec.text().strip()):
            return
        self._new_conn_mode = False
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Save New Profile", "Profile name:"
        )
        if ok and name:
            p = self._read_config()
            p[name] = {
                "env_id": self.env_id.text().strip(),
                "cl_id": self.cl_id.text().strip(),
                "columns": self.selected_columns,
                "column_widths": self.column_widths,
                "status_show_api_calls": bool(
                    getattr(self, "show_api_calls_cb", QtWidgets.QCheckBox()).isChecked()
                ),
                "hide_raw_http_columns": bool(
                    getattr(self, "hide_raw_http_columns_cb", QtWidgets.QCheckBox()).isChecked()
                ),
            }
            meta = p.get("__meta__", {})
            meta["last_working_profile"] = name
            p["__meta__"] = meta
            with open(self.config_file, "w") as f:
                json.dump(p, f, indent=4)
            try:
                self._write_secret_to_keyring(name, self.cl_sec.text())
                self._cache_secret(name, self.cl_sec.text())
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Keyring Error",
                    f"Failed to save client secret to keyring: {e}\n\nCredentials will not be stored persistently.",
                )
            self.load_profiles_from_disk(skip_connect=True)
            idx = self.profile_list.findText(name)
            if idx >= 0:
                self.profile_list.setCurrentIndex(idx)
            # Reset action combo back to "Test Credentials"
            self.config_action_combo.setCurrentIndex(0)

    def toggle_server_dryrun(self):
        enabled = self.use_server_dryrun_action.isChecked()
        if enabled:
            self.use_local_schema_action.setChecked(False)
        msg = "Validation: Server dry-run" if enabled else "Validation: none"
        try:
            self._set_processing_message(msg)
        except Exception:
            pass

    def toggle_local_schema(self):
        enabled = self.use_local_schema_action.isChecked()
        if enabled:
            self.use_server_dryrun_action.setChecked(False)
        msg = "Validation: Local schema" if enabled else "Validation: none"
        try:
            self._set_processing_message(msg)
        except Exception:
            pass

    def toggle_friendly_names(self):
        """Toggle between friendly names and attribute names for columns."""
        self.use_friendly_names = self.use_friendly_names_action.isChecked()
        self.refresh_table_headers()

    def toggle_theme(self):
        """Toggle between light and dark mode."""
        enabled = self.dark_mode_action.isChecked()
        theme = ThemeManager.DARK if enabled else ThemeManager.LIGHT
        app = QtWidgets.QApplication.instance()
        if app:
            self.theme_manager.set_theme(theme, app)
            # Update delete button style to match new theme
            if hasattr(self, 'btn_del') and self.btn_del is not None:
                self.btn_del.setStyleSheet(self.theme_manager.get_delete_button_style())
            self.save_app_settings()
            msg = "Dark mode enabled" if enabled else "Light mode enabled"


    def load_theme_preference(self):
        """Load and apply saved theme preference from config."""
        try:
            cfg = self._read_config()
            meta = cfg.get('__meta__', {})
            theme = meta.get('theme', ThemeManager.LIGHT)
            app = QtWidgets.QApplication.instance()
            if app:
                self.theme_manager.set_theme(theme, app)
                self.dark_mode_action.setChecked(theme == ThemeManager.DARK)
                # Update delete button style to match loaded theme
                if hasattr(self, 'btn_del') and self.btn_del is not None:
                    self.btn_del.setStyleSheet(self.theme_manager.get_delete_button_style())
        except Exception:
            pass

    def revert_to_default_columns(self):
        """Revert selected columns to default."""
        self.selected_columns = self.default_columns.copy()
        self.save_columns_to_config()
        self.refresh_table()
        msg = "Reverted to default columns"
        try:
            self._set_processing_message(msg)
        except Exception:
            pass

    def _get_column_labels(self):
        """Get column labels based on friendly name setting."""
        return [self.friendly_names.get(col, col) for col in self.columns] if self.use_friendly_names else self.columns

    def _flatten_user(self, user: dict) -> dict:
        """Return a flat dict of user attributes using dot-notation keys."""
        flat = {}
        def _rec(o, prefix=''):
            if isinstance(o, dict):
                for k, v in o.items():
                    full = f"{prefix}.{k}" if prefix else k
                    if isinstance(v, (dict, list)):
                        _rec(v, full)
                    else:
                        flat[full] = v
            elif isinstance(o, list):
                # store list as JSON string for export
                flat[prefix] = json.dumps(o)
        _rec(user)
        # population.name derivation
        pop_id = user.get('population', {}).get('id', '')
        if pop_id:
            flat['population.name'] = self.pop_map.get(pop_id, pop_id)
        return flat

    def _rows_from_users(self, users, columns):
        """Yield ordered rows (lists) for given users and columns."""
        for u in users:
            flat = self._flatten_user(u)
            row = [flat.get(col, '') for col in columns]
            yield row

    def _is_populated_export_value(self, value) -> bool:
        """Return True when a flattened export value should be treated as populated."""
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (list, tuple, dict, set)):
            return len(value) > 0
        return True

    def _get_metadata_columns(self, users: list) -> list:
        """Return sorted list of metadata column names (those starting with '_')."""
        metadata_cols = set()
        for user in users or []:
            try:
                flat = self._flatten_user(user)
                for key in flat.keys():
                    if key and str(key).startswith('_'):
                        metadata_cols.add(str(key))
            except Exception:
                pass
        return sorted(metadata_cols)

    def _filter_metadata_columns(self, columns: list, excluded_metadata: list) -> list:
        """Filter out metadata columns from the column list based on exclusion list."""
        if not excluded_metadata:
            return list(columns)
        excluded_set = set(str(m) for m in excluded_metadata)
        return [c for c in columns if str(c) not in excluded_set]

    def _get_populated_export_attributes(self, users: list) -> list:
        """Return sorted flattened attribute names that are populated in at least one user."""
        attrs = set()
        for user in users or []:
            try:
                flat = self._flatten_user(user)
                for key, value in flat.items():
                    if key and self._is_populated_export_value(value):
                        attrs.add(str(key))
            except Exception:
                pass
        return sorted(attrs)

    def _get_populated_export_attribute_samples(self, users: list, attrs: list) -> dict:
        """Return first non-empty sample value per flattened attribute."""
        sample_map = {}
        attr_order = [str(a) for a in (attrs or []) if str(a)]
        if not attr_order:
            return sample_map

        wanted = set(attr_order)
        for user in users or []:
            missing = wanted.difference(sample_map.keys())
            if not missing:
                break
            try:
                flat = self._flatten_user(user)
            except Exception:
                flat = {}
            for attr in list(missing):
                value = flat.get(attr)
                if not self._is_populated_export_value(value):
                    continue
                if isinstance(value, (dict, list, tuple, set)):
                    try:
                        text = json.dumps(value, ensure_ascii=False)
                    except Exception:
                        text = str(value)
                else:
                    text = str(value)
                if len(text) > 140:
                    text = text[:140] + '...'
                sample_map[attr] = text
        return sample_map

    def _filter_users_by_populated_attributes(self, users: list, required_attrs: list) -> tuple:
        """Filter users to those with all required flattened attributes populated."""
        required = [str(a).strip() for a in (required_attrs or []) if str(a).strip()]
        if not required:
            return list(users or []), 0

        filtered = []
        for user in users or []:
            try:
                flat = self._flatten_user(user)
            except Exception:
                flat = {}
            keep = True
            for attr in required:
                if not self._is_populated_export_value(flat.get(attr)):
                    keep = False
                    break
            if keep:
                filtered.append(user)
        return filtered, max(0, len(users or []) - len(filtered))

    def _filter_users_by_populations(self, users: list, selected_population_ids: list) -> tuple:
        """Filter users to those belonging to the selected populations.
        
        Args:
            users: List of user dictionaries
            selected_population_ids: List of population IDs to include
            
        Returns:
            Tuple of (filtered_users, count_filtered_out)
        """
        if not selected_population_ids:
            return list(users or []), 0
        
        pop_id_set = set(str(pid).strip() for pid in selected_population_ids if str(pid).strip())
        if not pop_id_set:
            return list(users or []), 0
        
        filtered = []
        for user in users or []:
            try:
                pop = user.get('population', {})
                if isinstance(pop, dict):
                    user_pop_id = str(pop.get('id', '')).strip()
                    if user_pop_id in pop_id_set:
                        filtered.append(user)
                elif isinstance(pop, str):
                    # Handle case where population is just an ID string
                    if str(pop).strip() in pop_id_set:
                        filtered.append(user)
            except Exception:
                # Skip users with malformed population data
                continue
        
        return filtered, max(0, len(users or []) - len(filtered))

    def _sanitize_db_column_name(self, name: str) -> str:
        """Return a SQL-friendly column name for new table creation."""
        raw = str(name or '').strip()
        if not raw:
            return 'col'
        safe = ''.join(ch if (ch.isalnum() or ch == '_') else '_' for ch in raw)
        safe = safe.strip('_') or 'col'
        if safe[0].isdigit():
            safe = f"col_{safe}"
        return safe

    def _convert_dotted_to_underscore(self, name: str) -> str:
        """Convert dotted.attribute names to underscore_attribute for SQL compatibility."""
        mapping = {
            'address.city': 'address_city',
            'address.street': 'address_street',
            'address.streetAddress': 'address_street',
            'address.locality': 'address_city',
            'name.family': 'name_family',
            'name.given': 'name_given',
            'phoneNumbers.home': 'phoneNumbers_home',
            'phoneNumbers.mobile': 'phoneNumbers_mobile',
            'phoneNumbers.work': 'phoneNumbers_work',
            'population.id': 'population_id',
            'population.name': 'population_name',
        }
        return mapping.get(name, name.replace('.', '_') if '.' in name else name)

    def _build_db_column_rename_map(self, existing_columns: list) -> dict:
        """Build a non-conflicting rename map for legacy dotted DB columns."""
        rename_map = {}
        used = set(existing_columns or [])
        for old_col in existing_columns or []:
            if '.' not in str(old_col):
                continue
            base = self._sanitize_db_column_name(old_col)
            candidate = base
            suffix = 2
            while candidate in used and candidate != old_col:
                candidate = f"{base}_{suffix}"
                suffix += 1
            if candidate != old_col:
                rename_map[old_col] = candidate
                used.add(candidate)
        return rename_map

    # --- shared import helpers ------------------------------------------------
    def _convert_rows_to_users(self, rows: list, mapping: dict,
                               client, pops: dict = None,
                               fixed_pop_id=None, fixed_enabled=None,
                               debug_stats: dict = None) -> list:
        """Apply a column-to-attribute mapping to a list of row dicts.

        Returns a list of PingOne user dicts suitable for import.  This logic is
        essentially the same as the CSV import path but operates on an already-
        populated ``rows`` list instead of reading from a file.
        ``mapping`` should map source column names to PingOne attribute names.
        """
        users = []
        if isinstance(debug_stats, dict):
            debug_stats['total_rows'] = len(rows or [])
            debug_stats['mapped_rows'] = 0
            debug_stats['skipped_rows'] = 0
            debug_stats['skip_reasons'] = {}
            debug_stats['sampled_skips'] = []

        for idx, row in enumerate(rows, start=1):
            # Normalize row keys from JDBC/JPype sources to Python strings.
            row_str = {str(k): v for k, v in (row or {}).items()}
            # Also keep trimmed-key aliases (drivers can include padded metadata labels).
            row_trimmed = {}
            for k, v in row_str.items():
                try:
                    k_trim = str(k).strip()
                except Exception:
                    k_trim = str(k)
                if k_trim and k_trim not in row_trimmed:
                    row_trimmed[k_trim] = v
            # Case-insensitive lookup map for DB drivers that normalize key casing.
            row_lower = {str(k).lower(): v for k, v in row_str.items()}
            row_lower.update({str(k).lower(): v for k, v in row_trimmed.items()})
            # Tokenized lookup map for loose matching (e.g. [User Name], user_name, USERNAME).
            row_token = {}
            for k, v in row_trimmed.items():
                token = ''.join(ch for ch in str(k).lower() if ch.isalnum())
                if token and token not in row_token:
                    row_token[token] = v
            flat = {}
            phone_by_type = {}

            for src_key, target in mapping.items():
                source_name = str(src_key).strip()
                source_phone_type = None
                if '::' in source_name:
                    source_name, source_phone_type = source_name.split('::', 1)
                    source_name = source_name.strip()
                    source_phone_type = str(source_phone_type).strip()

                source_candidates = []
                source_candidates.append(source_name)
                dot_to_us = self._convert_dotted_to_underscore(source_name)
                if dot_to_us not in source_candidates:
                    source_candidates.append(dot_to_us)
                if '.' in source_name:
                    us_variant = source_name.replace('.', '_')
                    if us_variant not in source_candidates:
                        source_candidates.append(us_variant)
                if '_' in source_name:
                    dot_variant = source_name.replace('_', '.')
                    if dot_variant not in source_candidates:
                        source_candidates.append(dot_variant)

                v = None
                for cand in source_candidates:
                    cand_trim = str(cand).strip()
                    if cand_trim in row_trimmed:
                        v = row_trimmed.get(cand_trim)
                        break
                    if cand in row_str:
                        v = row_str.get(cand)
                        break
                    cand_lower = cand.lower()
                    if cand_lower in row_lower:
                        v = row_lower.get(cand_lower)
                        break
                    cand_token = ''.join(ch for ch in cand_lower if ch.isalnum())
                    if cand_token and cand_token in row_token:
                        v = row_token.get(cand_token)
                        break
                if v is None or v == '':
                    continue

                # Extract typed phone value when mapping comes from expanded phone rows.
                if source_phone_type:
                    extracted = None
                    source_val = v
                    if isinstance(source_val, str):
                        s = source_val.strip()
                        if s.startswith('[') or s.startswith('{'):
                            try:
                                source_val = json.loads(s)
                            except Exception:
                                source_val = v
                    if isinstance(source_val, list):
                        for item in source_val:
                            if isinstance(item, dict) and str(item.get('type', '')).lower() == source_phone_type.lower():
                                extracted = item.get('number')
                                break
                    elif isinstance(source_val, dict):
                        # support dict payloads keyed by phone type
                        extracted = source_val.get(source_phone_type) or source_val.get('number')
                    if extracted is not None:
                        v = extracted

                # Skip any mapping that resolves to an empty/blank target
                if not target or (isinstance(target, str) and not target.strip()):
                    continue

                if isinstance(target, str):
                    target = target.strip()

                # Treat any 'uid' mapping as username (avoid importing as system id)
                try:
                    if isinstance(target, str) and target.lower() == 'uid':
                        target = 'username'
                except Exception:
                    pass

                # Show ID columns in the mapping UI but do NOT import ID values.
                if target == 'id':
                    continue

                # Phone targets are explicitly type-aware in mapping dialogs.
                if isinstance(target, str) and target.startswith('phoneNumbers.'):
                    ptype = target.split('.', 1)[1].strip().lower()
                    if ptype in ('mobile', 'work', 'home'):
                        val = str(v).strip()
                        if val:
                            phone_by_type[ptype] = val
                    continue

                # convert enabled values to booleans when mapped
                if target == 'enabled':
                    try:
                        low = str(v).strip().lower()
                        if low in ('true', '1', 'yes', 'y', 't'):
                            flat[target] = True
                        elif low in ('false', '0', 'no', 'n', 'f'):
                            flat[target] = False
                        else:
                            flat[target] = v
                    except Exception:
                        flat[target] = v
                else:
                    # PingOne expects strings for scalar fields (e.g. employeeNumber,
                    # address.postalCode). LDAP/DB sources may return integers when the
                    # source schema treats numeric-looking values as numbers.
                    if not isinstance(v, (bool, dict, list)):
                        v = str(v)
                    flat[target] = v

            if phone_by_type:
                ordered = []
                for t in ('mobile', 'work', 'home'):
                    if t in phone_by_type:
                        ordered.append({'type': t, 'number': phone_by_type[t]})
                if ordered:
                    flat['phoneNumbers'] = ordered
            user = self._unflatten_user(flat)
            # normalize username whitespace
            try:
                if isinstance(user.get('username'), str):
                    user['username'] = user['username'].strip()
            except Exception:
                pass
            # Remove invalid address values - PingOne requires address to be a COMPLEX
            # object with at least one sub-attribute, or omitted entirely.
            # String values, empty objects, and None are all invalid.
            try:
                addr = user.get('address')
                if addr is None or addr == '' or addr == []:
                    user.pop('address', None)
                elif isinstance(addr, str):
                    # Address was mapped as a simple string - remove it since PingOne
                    # requires a complex object with sub-attributes like streetAddress, locality.
                    user.pop('address', None)
                elif isinstance(addr, dict):
                    # Remove empty string values and None values from address
                    cleaned_addr = {k: v for k, v in addr.items() if v not in (None, '', [])}
                    if cleaned_addr:
                        user['address'] = cleaned_addr
                    else:
                        user.pop('address', None)
            except Exception:
                pass
            # apply fixed enabled setting if provided
            if fixed_enabled is not None:
                user['enabled'] = bool(fixed_enabled)

            # Fallback: derive username from common identity columns when mapping
            # does not populate username (common in HR-style tables).
            uname_val = user.get('username')
            if uname_val is None or not str(uname_val).strip():
                fallback_tokens = [
                    'username', 'userid', 'userprincipalname', 'samaccountname',
                    'login', 'uid', 'employeeid', 'employeenumber', 'mail', 'email'
                ]
                derived_username = None
                for tok in fallback_tokens:
                    candidate = row_token.get(tok)
                    if candidate is None:
                        continue
                    candidate_str = str(candidate).strip()
                    if not candidate_str:
                        continue
                    derived_username = candidate_str
                    break
                if derived_username:
                    user['username'] = derived_username
                    if isinstance(debug_stats, dict):
                        debug_stats['derived_usernames'] = debug_stats.get('derived_usernames', 0) + 1
                        samples = debug_stats.setdefault('derived_username_samples', [])
                        if len(samples) < 5:
                            samples.append(f"Row {idx}: username='{derived_username}'")

            skip_reason = None
            if not user:
                skip_reason = 'no mapped attributes'
            else:
                uname = user.get('username')
                if uname is None:
                    skip_reason = 'missing username'
                elif not str(uname).strip():
                    skip_reason = 'blank username'

            if skip_reason:
                if isinstance(debug_stats, dict):
                    debug_stats['skipped_rows'] = debug_stats.get('skipped_rows', 0) + 1
                    reasons = debug_stats.setdefault('skip_reasons', {})
                    reasons[skip_reason] = reasons.get(skip_reason, 0) + 1
                    if skip_reason == 'missing username':
                        key_samples = debug_stats.setdefault('username_key_samples', [])
                        if len(key_samples) < 5:
                            shown_keys = list(row_trimmed.keys())[:8]
                            key_samples.append(f"Row {idx} keys: {shown_keys}")
                    sampled = debug_stats.setdefault('sampled_skips', [])
                    if len(sampled) < 10:
                        sampled.append(f"Row {idx}: {skip_reason}")
                continue

            if isinstance(debug_stats, dict):
                debug_stats['mapped_rows'] = debug_stats.get('mapped_rows', 0) + 1
            users.append(user)
        # Normalize population values: convert names to IDs where possible
        try:
            if not pops:
                pops, _ = asyncio.run(client.get_populations())
            for u in users:
                if fixed_pop_id:
                    u['population'] = {'id': fixed_pop_id}
                    continue
                pop = u.get('population')
                if isinstance(pop, dict):
                    # If population provided as { 'name': 'X' }
                    name = pop.get('name')
                    if name and name in pops:
                        u['population'] = {'id': pops[name]}
                        continue
                    # If population provided as { 'id': 'maybe-name-or-id' }
                    val = pop.get('id')
                    if val:
                        # If it's already a known id, keep it
                        if val in pops.values():
                            u['population'] = {'id': val}
                        # If it's a population name, map to id
                        elif val in pops:
                            u['population'] = {'id': pops[val]}
        except Exception:
            pass
        return users

    def _format_import_mapping_debug_summary(self, debug_stats: dict) -> str:
        """Build a compact one-line import conversion summary for UI status."""
        total = int((debug_stats or {}).get('total_rows', 0) or 0)
        mapped = int((debug_stats or {}).get('mapped_rows', 0) or 0)
        skipped = int((debug_stats or {}).get('skipped_rows', 0) or 0)
        derived = int((debug_stats or {}).get('derived_usernames', 0) or 0)
        reasons = (debug_stats or {}).get('skip_reasons', {}) or {}
        reason_str = '; '.join(f"{k}: {v}" for k, v in sorted(reasons.items(), key=lambda item: item[0]))
        if reason_str:
            return f"Row mapping: total={total}, mapped={mapped}, skipped={skipped}, derived_username={derived} ({reason_str})"
        return f"Row mapping: total={total}, mapped={mapped}, skipped={skipped}, derived_username={derived}"

    def _perform_import_sequence(self, users: list, client, pops: dict = None,
                                 fixed_pop_id=None, fixed_enabled=None,
                                 debug_stats: dict = None):
        """Common logic used by both CSV and database import flows.

        ``users`` should be a list of pre-processed user dicts (i.e. the output
        of ``_convert_rows_to_users`` or the CSV reader loop).  This method
        handles credential validation, pre-checks, local validation, and kicking
        off the background worker.
        """
        if not users:
            summary = self._format_import_mapping_debug_summary(debug_stats) if isinstance(debug_stats, dict) else "No users to import."
            sampled_skips = []
            if isinstance(debug_stats, dict):
                sampled_skips = debug_stats.get('sampled_skips', []) or []
                username_key_samples = debug_stats.get('username_key_samples', []) or []
                derived_username_samples = debug_stats.get('derived_username_samples', []) or []
            else:
                username_key_samples = []
                derived_username_samples = []

            message_lines = ["No users to import."]
            if summary:
                message_lines.append("")
                message_lines.append(summary)
            if sampled_skips:
                message_lines.append("")
                message_lines.append("Sample skipped rows:")
                message_lines.extend(sampled_skips[:10])
            if username_key_samples:
                message_lines.append("")
                message_lines.append("Observed source keys (first rows):")
                message_lines.extend(username_key_samples[:5])
            if derived_username_samples:
                message_lines.append("")
                message_lines.append("Derived usernames (first rows):")
                message_lines.extend(derived_username_samples[:5])

            try:
                import api.client as _api_client
                _api_client.write_connection_log("Import conversion produced zero users")
                _api_client.write_connection_log(summary)
                for sample in sampled_skips[:10]:
                    _api_client.write_connection_log(sample)
                for sample in username_key_samples[:5]:
                    _api_client.write_connection_log(sample)
                for sample in derived_username_samples[:5]:
                    _api_client.write_connection_log(sample)
            except Exception:
                pass

            QtWidgets.QMessageBox.information(self, "Import", "\n".join(message_lines))
            return
        # Validate credentials by obtaining a token before starting the worker
        try:
            token = asyncio.run(client.get_token())
        except Exception:
            token = None
        if not token:
            QtWidgets.QMessageBox.critical(self, "Auth Failed", "Auth Failed. Check credentials.")
            return
        # Pre-check for username collisions against existing users and within the import set
        existing_user_map = {}
        try:
            token = asyncio.run(client.get_token())
            if token:
                import httpx as _httpx
                async def _fetch_usernames():
                    headers = client._get_auth_headers(token)
                    async with _httpx.AsyncClient(timeout=10.0) as session:
                        url = f"{client.base_url}/users"
                        while url:
                            resp = await session.get(url, headers=headers)
                            data = resp.json()
                            for uu in data.get("_embedded", {}).get("users", []):
                                if uu.get('username') and uu.get('id'):
                                    try:
                                        existing_user_map[uu.get('username').strip().lower()] = uu.get('id')
                                    except Exception:
                                        existing_user_map[uu.get('username')] = uu.get('id')
                            url = data.get("_links", {}).get("next", {}).get("href")
                try:
                    asyncio.run(_fetch_usernames())
                except Exception:
                    pass
        except Exception:
            # fall back to local cache if network fetch fails; build name->id map
            existing_user_map = {}
            for uu in (u for u in self.users_cache if u.get('username') and u.get('id')):
                try:
                    existing_user_map[uu.get('username').strip().lower()] = uu.get('id')
                except Exception:
                    existing_user_map[uu.get('username')] = uu.get('id')
        # Log a short snapshot of existing usernames for debugging
        try:
            import api.client as _api_client
            sample = list(existing_user_map.items())[:200]
            _api_client.write_connection_log(f"Pre-check existing_user_map (sample {len(sample)}): {sample}")
        except Exception:
            pass
        # Split users into creates and updates based on existing username map
        seen_usernames = set()
        pre_errors = []
        create_users = []
        update_pairs = []
        for u in users:
            uname = u.get('username')
            if not uname:
                continue
            try:
                uname_norm = uname.strip().lower()
            except Exception:
                uname_norm = uname
            if uname_norm in seen_usernames:
                pre_errors.append(f"Duplicate username in import: {uname}")
                continue
            seen_usernames.add(uname_norm)
            if uname_norm in existing_user_map:
                uid = existing_user_map.get(uname_norm)
                update_pairs.append((uid, u))
            else:
                create_users.append(u)
        if pre_errors:
            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle("Validation Failed")
            lay = QtWidgets.QVBoxLayout(dlg)
            lab = QtWidgets.QLabel(f"{len(pre_errors)} validation errors detected. Import aborted.")
            te = QtWidgets.QTextEdit()
            te.setReadOnly(True)
            te.setPlainText('\n'.join(pre_errors))
            te.setMinimumHeight(200)
            lay.addWidget(lab)
            lay.addWidget(te)
            btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
            btns.accepted.connect(dlg.accept)
            lay.addWidget(btns)
            try:
                screen = QtWidgets.QApplication.primaryScreen()
                geom = screen.availableGeometry()
                w = min(int(geom.width() * 0.6), 900)
                h = min(int(geom.height() * 0.4), 400)
                dlg.resize(max(500, w), max(200, h))
            except Exception:
                dlg.resize(600, 240)
            dlg.exec()
            return

        # Validate create-users with server-side dry-run and validate updates locally
        val_errors = []
        # Clean users of any accidental empty-string keys before validation
        coerced_total = 0
        for uu in users:
            try:
                self._remove_empty_keys(uu)
                coerced_total += self._coerce_numeric_scalars_to_strings(uu)
            except Exception:
                pass
        try:
            if coerced_total:
                self._set_processing_message(
                    f"Import normalization: converted {coerced_total} numeric scalar value(s) to strings.",
                    5000,
                )
        except Exception:
            pass

        # Validate creates locally (removed server dry-run validation)
        if create_users:
            for u in create_users:
                try:
                    if self.use_local_schema_action.isChecked():
                        try:
                            client.local_validate_user(u)
                        except Exception as le:
                            val_errors.append(f"User {u.get('username') or u.get('id')}: local validation error: {le}")
                            continue
                except Exception as e:
                    val_errors.append(f"User {u.get('username') or u.get('id')}: unexpected validation error: {e}")

        # Validate updates locally if requested (server dry-run not available for updates)
        if update_pairs:
            for uid, u in update_pairs:
                try:
                    if self.use_local_schema_action.isChecked():
                        try:
                            client.local_validate_user(u)
                        except Exception as le:
                            val_errors.append(f"User {u.get('username') or uid}: local validation error: {le}")
                except Exception as e:
                    val_errors.append(f"User {u.get('username') or uid}: unexpected validation error: {e}")

        if val_errors:
            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle("Validation Failed")
            lay = QtWidgets.QVBoxLayout(dlg)
            lab = QtWidgets.QLabel(f"{len(val_errors)} validation errors detected. Import aborted.")
            te = QtWidgets.QTextEdit()
            te.setReadOnly(True)
            te.setPlainText('\n'.join(val_errors))
            te.setMinimumHeight(300)
            lay.addWidget(lab)
            lay.addWidget(te)
            btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
            btns.accepted.connect(dlg.accept)
            lay.addWidget(btns)
            try:
                screen = QtWidgets.QApplication.primaryScreen()
                geom = screen.availableGeometry()
                w = min(int(geom.width() * 0.75), 1100)
                h = min(int(geom.height() * 0.6), 800)
                dlg.resize(max(700, w), max(400, h))
            except Exception:
                dlg.resize(900, 500)
            dlg.exec()
            return

        # Start create worker (if any) and then update worker (if any)
        self.cancel_requested = False
        self.cancel_btn.setText("Cancel Import")
        self.cancel_btn.setEnabled(True)
        self.prog.show()
        self.cancel_btn.show()
        self.prog.setRange(0, len(create_users) if create_users else (len(update_pairs) or 0))
        # Map population names to IDs if provided in CSV or apply fixed population
        try:
            if not pops:
                pops, _ = asyncio.run(client.get_populations())
            # convert any user with population.name -> population.id
            for u in users:
                if fixed_pop_id:
                    u['population'] = {'id': fixed_pop_id}
                    continue
                pop = u.get('population')
                if isinstance(pop, dict):
                    # support population.name -> id
                    name = pop.get('name')
                    if name and name in pops:
                        u['population'] = {'id': pops[name]}
                        continue
                    # support population.id coming from CSV; if value looks
                    # like a name, map it to id; if it is already an id, leave it
                    val = pop.get('id')
                    if val:
                        if val in pops.values():
                            u['population'] = {'id': val}
                        elif val in pops:
                            u['population'] = {'id': pops[val]}
        except Exception:
            pass
        
        # PHASE 2 OPTIMIZATION: Use parallel processing for large imports
        concurrency = 5 if len(create_users) > 100 else 1  # Use 5 concurrent requests for >100 users
        w = BulkCreateWorker(client, create_users, cancel_check=lambda: self.cancel_requested, concurrency=concurrency)
        w.signals.progress.connect(lambda cur, tot: self.prog.setValue(cur))
        w.signals.status.connect(lambda msg: self._set_processing_message(msg))
        w.signals.tps_update.connect(lambda tps_stats: self._update_tps_status_bar(tps_stats, "Import"))
        def on_done(res):
            self.prog.hide()
            self.cancel_btn.hide()
            created = res.get('created', 0)
            updated_on_retry = res.get('updated_on_retry', 0)
            total = res.get('total', 0)
            errors = res.get('errors', []) or []
            tps_stats = res.get('tps_stats')
            created_ids = res.get('created_ids', [])
            
            # Track this import for rollback
            if created_ids:
                self.last_import_record = {
                    'created_ids': created_ids,
                    'timestamp': datetime.now().isoformat(),
                    'created_count': created,
                }
            
            summary = f"Created {created}/{total} users"
            if updated_on_retry:
                summary += f"; Updated on retry {updated_on_retry}"
            
            # Show TPS report if available
            if tps_stats and tps_stats.get('total_transactions', 0) > 0:
                self._show_tps_report(tps_stats, "Import")
            
            if created == 0 and updated_on_retry == 0 and errors:
                dlg = QtWidgets.QDialog(self)
                dlg.setWindowTitle("Import Result")
                lay = QtWidgets.QVBoxLayout(dlg)
                lab = QtWidgets.QLabel(f"{summary}. No users were created.")
                te = QtWidgets.QTextEdit()
                te.setReadOnly(True)
                te.setPlainText('\n'.join(errors))
                te.setMinimumHeight(300)
                lay.addWidget(lab)
                lay.addWidget(te)
                btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
                btns.accepted.connect(dlg.accept)
                lay.addWidget(btns)
                try:
                    screen = QtWidgets.QApplication.primaryScreen()
                    geom = screen.availableGeometry()
                    w = min(int(geom.width() * 0.75), 1100)
                    h = min(int(geom.height() * 0.6), 800)
                    dlg.resize(max(700, w), max(400, h))
                except Exception:
                    dlg.resize(900, 500)
                dlg.exec()
            elif errors:
                dlg = QtWidgets.QDialog(self)
                dlg.setWindowTitle("Import Result")
                lay = QtWidgets.QVBoxLayout(dlg)
                lab = QtWidgets.QLabel(summary)
                te = QtWidgets.QTextEdit()
                te.setReadOnly(True)
                te.setPlainText('\n'.join(errors))
                te.setMinimumHeight(300)
                lay.addWidget(lab)
                lay.addWidget(te)
                btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
                btns.accepted.connect(dlg.accept)
                lay.addWidget(btns)
                try:
                    screen = QtWidgets.QApplication.primaryScreen()
                    geom = screen.availableGeometry()
                    w = min(int(geom.width() * 0.75), 1100)
                    h = min(int(geom.height() * 0.6), 800)
                    dlg.resize(max(700, w), max(400, h))
                except Exception:
                    dlg.resize(900, 500)
                dlg.exec()
            else:
                QtWidgets.QMessageBox.information(self, "Import Complete", summary)
            self._include_import_attributes_in_grid(users)
            self.refresh_users()
        w.signals.finished.connect(on_done)
        w.signals.error.connect(lambda m: (self.prog.hide(), self.cancel_btn.hide(), QtWidgets.QMessageBox.critical(self, "Import Error", m)))
        self.threadpool.start(w)
        msg = f"Import started: {len(users)} users"
        try:
            self._set_processing_message(msg)
        except Exception:
            pass

    def _apply_column_widths(self):
        """Apply saved column widths to the table."""
        for c, col in enumerate(self.columns):
            if col in self.column_widths:
                self.u_table.setColumnWidth(c, self.column_widths[col])

    def refresh_table_headers(self):
        """Refresh only the table headers."""
        self.u_table.setHorizontalHeaderLabels(self._get_column_labels())

    def update_user_field(self, user_id, col_name, new_data):
        """Update a specific field of a user via API."""
        user = next((u for u in self.users_cache if u['id'] == user_id), None)
        if user:
            payload = copy.deepcopy(user)
            self._set_user_value(payload, col_name, new_data)

            # Cleanup legacy malformed keys from older direct-assignment behavior
            # (e.g. top-level 'name.given' created in cache by prior edits).
            for k in list(payload.keys()):
                if isinstance(k, str) and '.' in k:
                    payload.pop(k, None)

            payload = self._sanitize_user_update_payload(payload)

            client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
            # Spawn a UserUpdateWorker to perform the API PUT off the UI
            # thread; the worker will refresh the UI upon success.
            self.prog.show()
            worker = UserUpdateWorker(client, user_id, payload)

            # Targeted request/response logging for user-management edits.
            # This captures the exact payload sent and the object returned.
            try:
                req_preview = json.dumps(payload) if isinstance(payload, (dict, list)) else str(payload)
                if len(req_preview) > 3000:
                    req_preview = req_preview[:3000] + '...'
                marker = f"USER_MGMT_EDIT_REQUEST user_id={user_id} field={col_name} payload={req_preview}"
                api_client.write_connection_log(marker)
                api_client.api_logger.info(marker)
            except Exception:
                pass

            def _on_update_finished(result):
                try:
                    returned_user = result.get('user') if isinstance(result, dict) else result
                    resp_preview = json.dumps(returned_user) if isinstance(returned_user, (dict, list)) else str(returned_user)
                    if len(resp_preview) > 3000:
                        resp_preview = resp_preview[:3000] + '...'
                    marker = f"USER_MGMT_EDIT_RESPONSE user_id={user_id} field={col_name} response={resp_preview}"
                    api_client.write_connection_log(marker)
                    api_client.api_logger.info(marker)
                except Exception:
                    pass
                self.prog.hide()
                self.refresh_users()
                self._notify_user_update_success(user_id, col_name)

            def _on_update_error(message):
                try:
                    marker = f"USER_MGMT_EDIT_ERROR user_id={user_id} field={col_name} error={message}"
                    api_client.write_connection_log(marker)
                    api_client.api_logger.error(marker)
                except Exception:
                    pass
                self.prog.hide()
                QtWidgets.QMessageBox.critical(self, "Error", message)

            worker.signals.finished.connect(_on_update_finished)
            worker.signals.error.connect(_on_update_error)
            self.threadpool.start(worker)

    def _show_text_help_dialog(self, title: str, content: str):
        """Show help text in a resizable dialog that scales with screen size."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(title)
        lay = QtWidgets.QVBoxLayout(dlg)
        txt = QtWidgets.QTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(content)
        lay.addWidget(txt)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        btns.rejected.connect(dlg.reject)
        btns.accepted.connect(dlg.accept)
        lay.addWidget(btns)

        try:
            screen = dlg.screen() or QtWidgets.QApplication.primaryScreen()
            geom = screen.availableGeometry()
            w = min(1100, int(geom.width() * 0.78))
            h = min(820, int(geom.height() * 0.78))
            dlg.resize(max(760, w), max(460, h))
        except Exception:
            dlg.resize(900, 600)

        dlg.exec()

    def show_config_help(self):
        self._show_text_help_dialog("Configuration Help", HELP_CONFIG)

    def show_user_help(self):
        self._show_text_help_dialog("User Management Help", HELP_USER)

    def show_filter_help(self):
        filter_text = (
            "Filter Help:\n\n"
            "The filter box on the User Management toolbar performs a case-insensitive contains match across all visible cells in each row.\n\n"
            "How it behaves:\n"
            "- As you type, rows update immediately.\n"
            "- A row stays visible if any column contains the typed text.\n"
            "- Clearing the filter restores all rows.\n"
            "- Shortcut: Cmd/Ctrl+L focuses the filter field.\n\n"
            "Example queries:\n"
            "- To narrow to users with last name Doe, type: Doe\n"
            "- To narrow toward first name Jane and last name Doe, type: Jane Doe\n\n"
            "Note:\n"
            "- The filter is a simple contains search, not a field-specific parser.\n"
            "- Queries such as 'last name = Doe' or 'first name = Jane, last name = Doe' are not interpreted literally; instead, type the values you want to match."
        )
        self._show_text_help_dialog("Filter Help", filter_text)

    def show_full_help(self):
        """Show comprehensive help covering all UI options and configuration."""
        combined = f"{HELP_CONFIG}\n\n{HELP_USER}"
        self._show_text_help_dialog("Full Help & Options", combined)

    def show_tabs_help(self):
        """Show a focused help dialog describing the Connection and User tabs."""
        tabs_text = """
Tabs Overview:

Configuration Tab:
- Connect to PingOne environments using worker app credentials
- Manage multiple profiles with saved credentials and column preferences
- View status bar updates for API calls and operations

User Management Tab:
- View, edit, import, export, and delete users
- Customize table columns per-profile
- Import/export CSV and LDIF formats with attribute mapping
- Update existing users during import (no duplicates)

See Configuration Help and User Management Help from the Help menu for detailed information.
"""
        self._show_text_help_dialog("Tabs Overview", tabs_text)

    def show_app_help(self):
        """Show the project's README.md as application help in a resizable dialog."""
        readme = Path('README.md')
        content = ''
        try:
            if readme.exists():
                with open(readme, 'r', encoding='utf-8') as f:
                    content = f.read()
            else:
                content = f"{HELP_CONFIG}\n\n{HELP_USER}"
        except Exception as e:
            content = f"Failed to load README.md: {e}\n\nFallback help:\n{HELP_CONFIG}\n\n{HELP_USER}"

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle('Application Help')
        lay = QtWidgets.QVBoxLayout(dlg)
        search_row = QtWidgets.QHBoxLayout()
        search = QtWidgets.QLineEdit(); search.setPlaceholderText('Search help...')
        btn_open = QtWidgets.QPushButton('Open README')
        search_row.addWidget(search); search_row.addWidget(btn_open)
        lay.addLayout(search_row)
        te = QtWidgets.QTextEdit(); te.setReadOnly(True)
        te.setPlainText(content)
        lay.addWidget(te)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        btns.rejected.connect(dlg.reject)
        btns.accepted.connect(dlg.accept)
        lay.addWidget(btns)

        def do_search(text):
            # simple search: select next occurrence
            if not text:
                return
            cursor = te.textCursor()
            # search from current position
            pos = te.toPlainText().find(text, cursor.position())
            if pos == -1:
                # wrap around
                pos = te.toPlainText().find(text)
            if pos != -1:
                cursor.setPosition(pos)
                cursor.movePosition(QtGui.QTextCursor.Right, QtGui.QTextCursor.KeepAnchor, len(text))
                te.setTextCursor(cursor)

        search.textChanged.connect(do_search)

        def open_readme():
            try:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(readme.resolve())))
            except Exception:
                pass

        btn_open.clicked.connect(open_readme)
        try:
            screen = QtWidgets.QApplication.primaryScreen()
            geom = screen.availableGeometry()
            dlg.resize(min(1100, int(geom.width() * 0.8)), min(800, int(geom.height() * 0.8)))
        except Exception:
            dlg.resize(900, 600)
        dlg.exec()

    def select_columns(self):
        """Open the column selection dialog to choose which columns to display."""
        if not self.all_columns:
            QtWidgets.QMessageBox.information(self, "Info", "Load users first to see available columns.")
            return
        available_cols = sorted([c for c in self.all_columns if not self._should_hide_column(c)])
        selected_cols = [c for c in self.selected_columns if c in available_cols]
        dialog = ColumnSelectDialog(available_cols, selected_cols, self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.selected_columns = dialog.get_selected()
            self.save_columns_to_config(show_notification=True)
            self.refresh_table()
            msg = "Column selection updated"
            try:
                self._set_processing_message(msg)
            except Exception:
                pass

    def export_to_csv(self):
        """Export current users (visible or all) to CSV using selected columns."""
        if not self.users_cache:
            QtWidgets.QMessageBox.information(self, "Export", "No users to export.")
            return
        options = self._get_native_file_dialog_options()
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export CSV", "users.csv", "CSV Files (*.csv);;All Files (*)", options=options
        )
        if not path:
            return
        # Load per-profile defaults (if any)
        prof_name = self.profile_list.currentText()
        prefer_selected = True
        only_visible_default = True
        try:
            cfg = self._read_config()
            if prof_name and prof_name in cfg:
                prefer_selected = cfg[prof_name].get('export_prefer_selected', prefer_selected)
                only_visible_default = cfg[prof_name].get('export_only_visible_columns', only_visible_default)
        except Exception:
            pass

        selected = self.u_table.selectionModel().selectedRows()
        # Show options dialog so user can choose selected/all and visible/all columns
        from ui.dialogs import ExportOptionsDialog
        populated_attrs = self._get_populated_export_attributes(self.users_cache)
        populated_attr_samples = self._get_populated_export_attribute_samples(self.users_cache, populated_attrs)
        metadata_cols = self._get_metadata_columns(self.users_cache)
        
        # Load saved excluded metadata and selected populations from profile
        excluded_metadata = []
        selected_populations = []
        try:
            cfg = self._read_config()
            if prof_name and prof_name in cfg:
                excluded_metadata = cfg[prof_name].get('export_excluded_metadata', [])
                selected_populations = cfg[prof_name].get('export_selected_populations', [])
        except Exception:
            pass
        
        dlg = ExportOptionsDialog(
            bool(selected),
            only_visible_default,
            prefer_selected,
            self,
            populated_attributes=populated_attrs,
            populated_attribute_samples=populated_attr_samples,
            metadata_columns=metadata_cols,
            excluded_metadata=excluded_metadata,
            populations=self.pop_map,
            selected_populations=selected_populations,
        )
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return
        opts = dlg.get_options()
        # persist choices if requested
        if opts.get('remember') and prof_name:
            try:
                cfg = self._read_config()
                if prof_name not in cfg:
                    cfg[prof_name] = {}
                cfg[prof_name]['export_prefer_selected'] = (opts.get('rows') == 'selected')
                cfg[prof_name]['export_only_visible_columns'] = bool(opts.get('only_visible_columns'))
                cfg[prof_name]['export_excluded_metadata'] = opts.get('excluded_metadata', [])
                cfg[prof_name]['export_selected_populations'] = opts.get('selected_populations', [])
                self._write_config(cfg)
            except Exception:
                pass

        # choose columns
        if opts.get('only_visible_columns'):
            cols = self.columns or self.selected_columns
        else:
            cols = sorted(self.all_columns)
        
        # Filter out excluded metadata columns
        cols = self._filter_metadata_columns(cols, opts.get('excluded_metadata', []))

        # compute export users
        try:
            if opts.get('rows') == 'selected' and selected:
                id_col = self.columns.index('id') if 'id' in self.columns else -1
                if id_col != -1:
                    ids = [self.u_table.item(r.row(), id_col).text() for r in selected]
                    export_users = [u for u in self.users_cache if u.get('id') in ids]
                else:
                    export_users = []
                    for r in selected:
                        try:
                            val = self.u_table.item(r.row(), 0).text()
                            found = next((u for u in self.users_cache if u.get('username') == val or u.get('id') == val), None)
                            if found:
                                export_users.append(found)
                        except Exception:
                            pass
            else:
                export_users = list(self.users_cache)

            required_attrs = opts.get('required_populated_attributes') or []
            filtered_out = 0
            if required_attrs:
                export_users, filtered_out = self._filter_users_by_populated_attributes(export_users, required_attrs)

            # Filter by selected populations
            selected_populations = opts.get('selected_populations', [])
            pop_filtered_out = 0
            if selected_populations:
                export_users, pop_filtered_out = self._filter_users_by_populations(export_users, selected_populations)

            import csv
            # Start TPS tracking
            tracker = TPSTracker()
            tracker.start()
            
            total_users = len(export_users)
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                for idx, row in enumerate(self._rows_from_users(export_users, cols), 1):
                    writer.writerow([str(v) for v in row])
                    tracker.record_transaction()
                    # Update status every 10 rows or on last row
                    if idx % 10 == 0 or idx == total_users:
                        try:
                            percentage = int(idx / total_users * 100)
                            self.status_label.setText(f"Exporting {idx}/{total_users} ({percentage}%) users...")
                            self._set_processing_message(f"Exporting {idx}/{total_users} ({percentage}%) users...")
                        except Exception:
                            pass
            
            # Finish tracking and get statistics
            tracker.finish()
            tps_stats = tracker.get_statistics()
            
            self._set_last_data_source(f"File {path}")
            msg = f"Exported {len(export_users)} users to {path}"
            if filtered_out:
                msg += f" (filtered out {filtered_out} by populated-attribute filter)"
            if pop_filtered_out:
                msg += f" (filtered out {pop_filtered_out} by population filter)"
            try:
                self._set_processing_message(msg)
            except Exception:
                pass
            
            # Show TPS report
            self._show_tps_report(tps_stats, "CSV Export")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export Error", str(e))

    def export_to_ldif(self):
        """Export current users to LDIF. This produces simple entries per user."""
        if not self.users_cache:
            QtWidgets.QMessageBox.information(self, "Export", "No users to export.")
            return
        options = self._get_native_file_dialog_options()
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export LDIF", "users.ldif", "LDIF Files (*.ldif);;All Files (*)", options=options
        )
        if not path:
            return
        # Load per-profile defaults (if any)
        prof_name = self.profile_list.currentText()
        prefer_selected = True
        only_visible_default = True
        try:
            cfg = self._read_config()
            if prof_name and prof_name in cfg:
                prefer_selected = cfg[prof_name].get('export_prefer_selected', prefer_selected)
                only_visible_default = cfg[prof_name].get('export_only_visible_columns', only_visible_default)
        except Exception:
            pass

        selected = self.u_table.selectionModel().selectedRows()
        from ui.dialogs import ExportOptionsDialog
        populated_attrs = self._get_populated_export_attributes(self.users_cache)
        populated_attr_samples = self._get_populated_export_attribute_samples(self.users_cache, populated_attrs)
        metadata_cols = self._get_metadata_columns(self.users_cache)
        
        # Load saved excluded metadata and selected populations from profile
        excluded_metadata = []
        selected_populations = []
        try:
            cfg = self._read_config()
            if prof_name and prof_name in cfg:
                excluded_metadata = cfg[prof_name].get('export_excluded_metadata', [])
                selected_populations = cfg[prof_name].get('export_selected_populations', [])
        except Exception:
            pass
        
        dlg = ExportOptionsDialog(
            bool(selected),
            only_visible_default,
            prefer_selected,
            self,
            populated_attributes=populated_attrs,
            populated_attribute_samples=populated_attr_samples,
            metadata_columns=metadata_cols,
            excluded_metadata=excluded_metadata,
            populations=self.pop_map,
            selected_populations=selected_populations,
        )
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return
        opts = dlg.get_options()
        if opts.get('remember') and prof_name:
            try:
                cfg = self._read_config()
                if prof_name not in cfg:
                    cfg[prof_name] = {}
                cfg[prof_name]['export_prefer_selected'] = (opts.get('rows') == 'selected')
                cfg[prof_name]['export_only_visible_columns'] = bool(opts.get('only_visible_columns'))
                cfg[prof_name]['export_excluded_metadata'] = opts.get('excluded_metadata', [])
                cfg[prof_name]['export_selected_populations'] = opts.get('selected_populations', [])
                self._write_config(cfg)
            except Exception:
                pass

        if opts.get('only_visible_columns'):
            cols_check = self.columns or self.selected_columns
        else:
            cols_check = sorted(self.all_columns)
        
        # Filter out excluded metadata columns
        cols_check = self._filter_metadata_columns(cols_check, opts.get('excluded_metadata', []))

        try:
            if opts.get('rows') == 'selected' and selected:
                id_col = self.columns.index('id') if 'id' in self.columns else -1
                if id_col != -1:
                    ids = [self.u_table.item(r.row(), id_col).text() for r in selected]
                    export_users = [u for u in self.users_cache if u.get('id') in ids]
                else:
                    export_users = []
                    for r in selected:
                        try:
                            val = self.u_table.item(r.row(), 0).text()
                            found = next((u for u in self.users_cache if u.get('username') == val or u.get('id') == val), None)
                            if found:
                                export_users.append(found)
                        except Exception:
                            pass
            else:
                export_users = list(self.users_cache)

            required_attrs = opts.get('required_populated_attributes') or []
            filtered_out = 0
            if required_attrs:
                export_users, filtered_out = self._filter_users_by_populated_attributes(export_users, required_attrs)

            # Filter by selected populations
            selected_populations = opts.get('selected_populations', [])
            pop_filtered_out = 0
            if selected_populations:
                export_users, pop_filtered_out = self._filter_users_by_populations(export_users, selected_populations)

            # Start TPS tracking
            tracker = TPSTracker()
            tracker.start()
            
            total_users = len(export_users)
            with open(path, 'w', encoding='utf-8') as f:
                for idx, u in enumerate(export_users, 1):
                    flat = self._flatten_user(u)
                    uid = flat.get('username') or flat.get('id') or ''
                    if not uid:
                        continue
                    # Naive DN: uid=<username>
                    f.write(f"dn: uid={uid}\n")
                    f.write("objectClass: inetOrgPerson\n")
                    # write common attributes if present
                    for attr in ['username', 'id', 'email', 'name.given', 'name.family', 'population.name']:
                        val = flat.get(attr)
                        if val:
                            key = attr.replace('.', '-') if '.' in attr else attr
                            f.write(f"{key}: {val}\n")
                    # any other attributes
                    for k, v in flat.items():
                        if k in ['username', 'id', 'email', 'name.given', 'name.family', 'population.name']:
                            continue
                        f.write(f"{k}: {v}\n")
                    f.write('\n')
                    tracker.record_transaction()
                    # Update status every 10 users or on last user
                    if idx % 10 == 0 or idx == total_users:
                        try:
                            percentage = int(idx / total_users * 100)
                            self.status_label.setText(f"Exporting {idx}/{total_users} ({percentage}%) users...")
                            self._set_processing_message(f"Exporting {idx}/{total_users} ({percentage}%) users...")
                        except Exception:
                            pass
            
            # Finish tracking and get statistics
            tracker.finish()
            tps_stats = tracker.get_statistics()
            
            self._set_last_data_source(f"File {path}")
            msg = f"Exported {len(export_users)} users to {path}"
            if filtered_out:
                msg += f" (filtered out {filtered_out} by populated-attribute filter)"
            if pop_filtered_out:
                msg += f" (filtered out {pop_filtered_out} by population filter)"
            try:
                self._set_processing_message(msg)
                # Show TPS report
                self._show_tps_report(tps_stats, "LDIF Export")
            except Exception:
                pass
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export Error", str(e))

    def _unflatten_user(self, flat: dict) -> dict:
        """Convert a flat dict with dot-notation keys into a nested dict.

        Example: {'name.given': 'Joe', 'name.family': 'Bloggs'} -> {'name': {'given': 'Joe', 'family': 'Bloggs'}}
        """
        result = {}
        for k, v in flat.items():
            # ignore empty keys which may be produced by malformed mappings
            if not k or (isinstance(k, str) and not k.strip()):
                continue
            # convert LDIF-exported keys that replaced dots with hyphens back to dots
            key = k.replace('-', '.') if '-' in k and '.' not in k else k
            parts = key.split('.')
            cur = result
            for p in parts[:-1]:
                if p not in cur or not isinstance(cur[p], dict):
                    cur[p] = {}
                cur = cur[p]
            # Try to parse JSON values that were stored for lists/complex fields
            if isinstance(v, str):
                # Be tolerant of CSV-escaped JSON (e.g. doubled quotes)
                s = v.strip()
                # Only parse structured JSON values. Parsing scalar tokens like
                # "75038" would cast them to ints and violate PingOne's string
                # expectations for fields such as address.postalCode.
                if s.startswith('{') or s.startswith('['):
                    try:
                        parsed = json.loads(s)
                        cur[parts[-1]] = parsed
                        continue
                    except Exception:
                        pass
                    # Try to normalize doubled quotes often produced by CSV quoting
                    if '""' in s:
                        try:
                            parsed = json.loads(s.replace('""', '"'))
                            cur[parts[-1]] = parsed
                            continue
                        except Exception:
                            pass
                # Fallback: store raw string
                cur[parts[-1]] = v
            else:
                cur[parts[-1]] = v
        return result

    def _discover_populated_attributes_from_entries(self, entries: list, max_sample: int = 10) -> list:
        """Discover which attributes are actually populated by examining first N entries.
        
        Returns a sorted list of attribute keys that have non-empty values in at least
        one of the sampled entries. This helps show users only relevant attributes
        for mapping instead of all possible columns.
        """
        if not entries:
            return []
        
        sample_entries = entries[:max_sample]
        populated_keys = set()
        
        for entry in sample_entries:
            if not isinstance(entry, dict):
                continue
            for key, val in entry.items():
                # Skip DN and other metadata keys
                if not key or (isinstance(key, str) and str(key).lower() in ('dn', '')):
                    continue
                # Check if value is non-empty
                if val is None or val == '' or val == [] or val == {}:
                    continue
                # Handle list values - check if list has non-empty items
                if isinstance(val, list):
                    has_content = any(
                        item not in (None, '', [], {}) 
                        for item in val
                    )
                    if has_content:
                        populated_keys.add(key)
                else:
                    populated_keys.add(key)
        
        return sorted(populated_keys)

    def _coerce_numeric_scalars_to_strings(self, obj, path: str = "") -> int:
        """Recursively coerce numeric scalars to strings in import payloads."""
        converted = 0
        try:
            if isinstance(obj, dict):
                for key in list(obj.keys()):
                    val = obj.get(key)
                    child_path = f"{path}.{key}" if path else str(key)
                    if isinstance(val, (dict, list)):
                        converted += self._coerce_numeric_scalars_to_strings(val, child_path)
                    elif isinstance(val, bytes):
                        try:
                            obj[key] = val.decode('utf-8')
                        except Exception:
                            obj[key] = str(val)
                        converted += 1
                    elif isinstance(val, (int, float)) and not isinstance(val, bool):
                        obj[key] = str(val)
                        converted += 1
            elif isinstance(obj, list):
                for idx, val in enumerate(obj):
                    child_path = f"{path}[{idx}]" if path else f"[{idx}]"
                    if isinstance(val, (dict, list)):
                        converted += self._coerce_numeric_scalars_to_strings(val, child_path)
                    elif isinstance(val, bytes):
                        try:
                            obj[idx] = val.decode('utf-8')
                        except Exception:
                            obj[idx] = str(val)
                        converted += 1
                    elif isinstance(val, (int, float)) and not isinstance(val, bool):
                        obj[idx] = str(val)
                        converted += 1
        except Exception:
            pass
        return converted

    def _remove_empty_keys(self, obj):
        """Recursively remove empty-string keys from dicts/lists in-place."""
        try:
            if isinstance(obj, dict):
                keys = list(obj.keys())
                for k in keys:
                    if not k or (isinstance(k, str) and not k.strip()):
                        try:
                            del obj[k]
                        except Exception:
                            pass
                        continue
                    v = obj.get(k)
                    if isinstance(v, (dict, list)):
                        self._remove_empty_keys(v)
            elif isinstance(obj, list):
                for item in obj:
                    if isinstance(item, (dict, list)):
                        self._remove_empty_keys(item)
        except Exception:
            pass

    def import_from_csv(self):
        """Import users from a CSV file. CSV must have headers matching exported columns (dot-notation)."""
        options = self._get_native_file_dialog_options()
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import CSV", "", "CSV Files (*.csv);;All Files (*)", options=options
        )
        if not path:
            return
        self._set_last_data_source(f"File {path}")
        try:
            import csv as _csv
            # read all rows first so we can re-use them after showing mapping dialog
            with open(path, 'r', encoding='utf-8') as f:
                reader = _csv.DictReader(f)
                headers = reader.fieldnames or []
                raw_rows = list(reader)

            # Discover populated attributes from first 10 rows
            populated_headers = self._discover_populated_attributes_from_entries(raw_rows, max_sample=10)
            # Use populated headers but fall back to all headers if none found
            headers = populated_headers if populated_headers else headers

            # Check if headers have dotted names that need adjustment
            adjusted_headers = [self._convert_dotted_to_underscore(h) for h in headers]
            adjustments = [(orig, converted) for orig, converted in zip(headers, adjusted_headers) if orig != converted]
            
            if adjustments:
                msg = "Adjusted column names for SQL compatibility:\n\n"
                for orig, converted in adjustments:
                    msg += f"  {orig} → {converted}\n"
                msg += "\nProceed with import using the _ values?"
                
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Column Name Adjustments",
                    msg,
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.Yes
                )
                if reply != QtWidgets.QMessageBox.Yes:
                    return
                
                # Apply adjustments to headers and rows
                headers = adjusted_headers
                raw_rows = [{self._convert_dotted_to_underscore(k): v for k, v in row.items()} for row in raw_rows]

            # prepare client & populate list for mapping UI
            client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
            pops = {}
            try:
                token = asyncio.run(client.get_token())
                if token:
                    pops, _ = asyncio.run(client.get_populations())
            except Exception:
                token = None

            # show mapping dialog
            prof_name = self.profile_list.currentText()
            initial_mapping = None
            initial_fixed = None
            try:
                cfg = self._read_config()
                if prof_name and prof_name in cfg:
                    initial_mapping = cfg[prof_name].get('mappings')
                    initial_fixed = cfg[prof_name].get('fixed_population_id')
            except Exception:
                pass
            initial_enabled = None
            try:
                if prof_name and prof_name in cfg:
                    initial_enabled = cfg[prof_name].get('fixed_enabled')
            except Exception:
                pass

            pingone_attrs = self._get_pingone_attributes()
            try:
                pingone_attrs = self._get_pingone_attributes_for_import(client)
            except Exception:
                pass

            map_dialog = AttributeMappingDialog(headers, self, pop_map=pops,
                                               initial_mapping=initial_mapping,
                                               initial_fixed_pop_id=initial_fixed,
                                               initial_fixed_enabled=initial_enabled,
                                               pingone_attrs=pingone_attrs,
                                               sample_row=(raw_rows[0] if raw_rows else None),
                                               client=client)
            if map_dialog.exec() != QtWidgets.QDialog.Accepted:
                return
            mapping, fixed_pop_id, fixed_enabled, remember = map_dialog.get_mapping()

            # persist mapping if requested
            try:
                if prof_name and remember:
                    cfg = self._read_config()
                    if prof_name not in cfg:
                        cfg[prof_name] = {}
                    cfg[prof_name]['mappings'] = mapping
                    cfg[prof_name]['fixed_population_id'] = fixed_pop_id
                    cfg[prof_name]['fixed_enabled'] = fixed_enabled
                    self._write_config(cfg)
            except Exception:
                pass

            # convert rows into users via shared helper
            debug_stats = {}
            users = self._convert_rows_to_users(raw_rows, mapping, client, pops,
                                                fixed_pop_id, fixed_enabled, debug_stats=debug_stats)
            self._set_processing_message(self._format_import_mapping_debug_summary(debug_stats), 10000)
            sampled_skips = debug_stats.get('sampled_skips', []) if isinstance(debug_stats, dict) else []
            if sampled_skips:
                self._set_processing_message(f"Sample skipped rows: {' | '.join(sampled_skips)}", 12000)
            # hand off to common import logic
            self._perform_import_sequence(users, client, pops, fixed_pop_id, fixed_enabled, debug_stats=debug_stats)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import Error", str(e))

    def import_from_ldif(self):
        """Import users from a simple LDIF file created by this app's export."""
        options = self._get_native_file_dialog_options()
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Import LDIF", "", "LDIF Files (*.ldif);;All Files (*)", options=options
        )
        if not path:
            return
        self._set_last_data_source(f"File {path}")
        try:
            users = []
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            entries = [e.strip() for e in content.split('\n\n') if e.strip()]
            
            # Parse first 10 entries to discover populated attributes
            sample_entries = []
            for ent in entries[:10]:
                flat = {}
                for line in ent.splitlines():
                    if not line or ':' not in line:
                        continue
                    key, val = line.split(':', 1)
                    key = key.strip()
                    val = val.strip()
                    if key.lower() == 'dn':
                        continue
                    # convert hyphenated keys to dot-notation
                    if '-' in key and '.' not in key:
                        key = key.replace('-', '.')
                    flat[key] = val
                if flat:
                    sample_entries.append(flat)
            
            # Discover which attributes are actually populated
            first_flat_keys = self._discover_populated_attributes_from_entries(sample_entries, max_sample=10)
            first_sample = sample_entries[0] if sample_entries else {}
            # Create API client early to fetch populations for mapping UI
            client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
            pops = {}
            try:
                token = asyncio.run(client.get_token())
                if token:
                    pops, _ = asyncio.run(client.get_populations())
            except Exception:
                token = None
            # Pass saved mappings for profile to LDIF mapping dialog as well
            initial_mapping = None
            initial_fixed = None
            initial_enabled = None
            prof_name = self.profile_list.currentText()
            try:
                cfg = self._read_config()
                if prof_name and prof_name in cfg:
                    initial_mapping = cfg[prof_name].get('mappings')
                    initial_fixed = cfg[prof_name].get('fixed_population_id')
                    initial_enabled = cfg[prof_name].get('fixed_enabled')
            except Exception:
                initial_mapping = None
                initial_fixed = None
            pingone_attrs = self._get_pingone_attributes()
            try:
                pingone_attrs = self._get_pingone_attributes_for_import(client)
            except Exception:
                pass

            map_dialog = AttributeMappingDialog(
                first_flat_keys,
                self,
                pop_map=pops,
                initial_mapping=initial_mapping,
                initial_fixed_pop_id=initial_fixed,
                initial_fixed_enabled=initial_enabled,
                pingone_attrs=pingone_attrs,
                sample_row=first_sample,
                client=client,
            )
            if map_dialog.exec() != QtWidgets.QDialog.Accepted:
                return
            mapping, fixed_pop_id, fixed_enabled, remember = map_dialog.get_mapping()
            try:
                if prof_name and remember:
                    cfg = self._read_config()
                    if prof_name not in cfg:
                        cfg[prof_name] = {}
                    cfg[prof_name]['mappings'] = mapping
                    cfg[prof_name]['fixed_population_id'] = fixed_pop_id
                    cfg[prof_name]['fixed_enabled'] = fixed_enabled
                    self._write_config(cfg)
            except Exception:
                pass
            for ent in entries:
                flat = {}
                for line in ent.splitlines():
                    if not line or ':' not in line:
                        continue
                    key, val = line.split(':', 1)
                    key = key.strip()
                    val = val.strip()
                    if key.lower() == 'dn':
                        continue
                    # convert hyphenated keys back to dot-notation if appropriate
                    if '-' in key and '.' not in key:
                        key = key.replace('-', '.')
                    # map key
                    target = mapping.get(key, key)
                    # Skip any mapping that resolves to an empty/blank target
                    if not target or (isinstance(target, str) and not target.strip()):
                        continue
                    # Treat 'uid' as username to avoid mapping to system id
                    try:
                        if isinstance(target, str) and target.lower() == 'uid':
                            target = 'username'
                    except Exception:
                        pass
                    # Skip ID mapping — do not import id values from LDIF
                    if target == 'id':
                        continue
                    # do not overwrite existing keys
                    if target in flat:
                        # convert to list for multi-value attributes
                        if not isinstance(flat[target], list):
                            flat[target] = [flat[target]]
                        # convert enabled to boolean when appropriate
                        if target == 'enabled':
                            low = val.strip().lower()
                            if low in ('true', '1', 'yes', 'y', 't'):
                                flat[target].append(True)
                            elif low in ('false', '0', 'no', 'n', 'f'):
                                flat[target].append(False)
                            else:
                                flat[target].append(val)
                        else:
                            flat[target].append(val)
                    else:
                        if target == 'enabled':
                            low = val.strip().lower()
                            if low in ('true', '1', 'yes', 'y', 't'):
                                flat[target] = True
                            elif low in ('false', '0', 'no', 'n', 'f'):
                                flat[target] = False
                            else:
                                flat[target] = val
                        else:
                            flat[target] = val
                if flat:
                    u = self._unflatten_user(flat)
                    # normalize username whitespace
                    try:
                        if isinstance(u.get('username'), str):
                            u['username'] = u['username'].strip()
                    except Exception:
                        pass
                    if fixed_enabled is not None:
                        u['enabled'] = bool(fixed_enabled)
                    users.append(u)
            if not users:
                QtWidgets.QMessageBox.information(self, "Import", "No users found in LDIF.")
                return
            client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
            try:
                token = asyncio.run(client.get_token())
            except Exception:
                token = None
            if not token:
                QtWidgets.QMessageBox.critical(self, "Auth Failed", "Auth Failed. Check credentials.")
                return
            self.prog.show(); self.prog.setRange(0, len(users))
            # Map population names to IDs if provided in LDIF or apply fixed population
            from contextlib import suppress
            with suppress(Exception):
                if not pops:
                    pops, _ = asyncio.run(client.get_populations())
                # Pre-check for username collisions against existing users and within the import set
                # Refresh existing usernames from the server to avoid stale cache
                existing_user_map = {}
                try:
                    token = asyncio.run(client.get_token())
                    if token:
                        import httpx as _httpx
                        async def _fetch_usernames_ldif():
                            headers = client._get_auth_headers(token)
                            async with _httpx.AsyncClient(timeout=10.0) as session:
                                url = f"{client.base_url}/users"
                                while url:
                                    resp = await session.get(url, headers=headers)
                                    data = resp.json()
                                    for uu in data.get("_embedded", {}).get("users", []):
                                                if uu.get('username') and uu.get('id'):
                                                    try:
                                                        existing_user_map[uu.get('username').strip().lower()] = uu.get('id')
                                                    except Exception:
                                                        existing_user_map[uu.get('username')] = uu.get('id')
                                    url = data.get("_links", {}).get("next", {}).get("href")
                        try:
                            asyncio.run(_fetch_usernames_ldif())
                        except Exception:
                            pass
                except Exception:
                    existing_user_map = {}
                    for uu in (u for u in self.users_cache if u.get('username') and u.get('id')):
                        try:
                            existing_user_map[uu.get('username').strip().lower()] = uu.get('id')
                        except Exception:
                            existing_user_map[uu.get('username')] = uu.get('id')
                # Log a short snapshot of existing usernames for debugging
                try:
                    import api.client as _api_client
                    sample = list(existing_user_map.items())[:200]
                    _api_client.write_connection_log(f"Pre-check existing_user_map (sample {len(sample)}): {sample}")
                except Exception:
                    pass
                # Split into creates and updates
                seen_usernames = set()
                pre_errors = []
                create_users = []
                update_pairs = []
                for u in users:
                    uname = u.get('username')
                    if not uname:
                        continue
                    try:
                        uname_norm = uname.strip().lower()
                    except Exception:
                        uname_norm = uname
                    if uname_norm in seen_usernames:
                        pre_errors.append(f"Duplicate username in import: {uname}")
                        continue
                    seen_usernames.add(uname_norm)
                    if uname_norm in existing_user_map:
                        update_pairs.append((existing_user_map.get(uname_norm), u))
                    else:
                        create_users.append(u)
                if pre_errors:
                    dlg = QtWidgets.QDialog(self)
                    dlg.setWindowTitle("Validation Failed")
                    lay = QtWidgets.QVBoxLayout(dlg)
                    lab = QtWidgets.QLabel(f"{len(pre_errors)} validation errors detected. Import aborted.")
                    te = QtWidgets.QTextEdit()
                    te.setReadOnly(True)
                    te.setPlainText('\n'.join(pre_errors))
                    te.setMinimumHeight(200)
                    lay.addWidget(lab)
                    lay.addWidget(te)
                    btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
                    btns.accepted.connect(dlg.accept)
                    lay.addWidget(btns)
                    try:
                        screen = QtWidgets.QApplication.primaryScreen()
                        geom = screen.availableGeometry()
                        w = min(int(geom.width() * 0.6), 900)
                        h = min(int(geom.height() * 0.4), 400)
                        dlg.resize(max(500, w), max(200, h))
                    except Exception:
                        dlg.resize(600, 240)
                    dlg.exec()
                    return

                # Always perform server dry-run validation for LDIF imports too
                val_errors = []
                # Clean users of any accidental empty-string keys before validation
                for uu in users:
                    try:
                        self._remove_empty_keys(uu)
                    except Exception:
                        pass

                # Validate create_users via server dry-run
                if create_users:
                    for u in create_users:
                        try:
                            if self.use_local_schema_action.isChecked():
                                try:
                                    client.local_validate_user(u)
                                except Exception as le:
                                    val_errors.append(f"User {u.get('username') or u.get('id')}: local validation error: {le}")
                                    continue
                            try:
                                asyncio.run(client.validate_user(u, dry_run=True))
                            except Exception as se:
                                val_errors.append(f"User {u.get('username') or u.get('id')}: {se}")
                        except Exception as e:
                            val_errors.append(f"User {u.get('username') or u.get('id')}: unexpected validation error: {e}")

                # Validate updates locally if requested
                if update_pairs:
                    for uid, u in update_pairs:
                        try:
                            if self.use_local_schema_action.isChecked():
                                try:
                                    client.local_validate_user(u)
                                except Exception as le:
                                    val_errors.append(f"User {u.get('username') or uid}: local validation error: {le}")
                        except Exception as e:
                            val_errors.append(f"User {u.get('username') or uid}: unexpected validation error: {e}")

                if val_errors:
                    dlg = QtWidgets.QDialog(self)
                    dlg.setWindowTitle("Validation Failed")
                    lay = QtWidgets.QVBoxLayout(dlg)
                    lab = QtWidgets.QLabel(f"{len(val_errors)} validation errors detected. Import aborted.")
                    te = QtWidgets.QTextEdit()
                    te.setReadOnly(True)
                    te.setPlainText('\n'.join(val_errors))
                    te.setMinimumHeight(300)
                    lay.addWidget(lab)
                    lay.addWidget(te)
                    btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
                    btns.accepted.connect(dlg.accept)
                    lay.addWidget(btns)
                    try:
                        screen = QtWidgets.QApplication.primaryScreen()
                        geom = screen.availableGeometry()
                        w = min(int(geom.width() * 0.75), 1100)
                        h = min(int(geom.height() * 0.6), 800)
                        dlg.resize(max(700, w), max(400, h))
                    except Exception:
                        dlg.resize(900, 500)
                    dlg.exec()
                    return

                # Map population names to IDs for both creates and updates
                try:
                    if not pops:
                        pops, _ = asyncio.run(client.get_populations())
                    targets = []
                    if create_users:
                        targets.extend(create_users)
                    if update_pairs:
                        targets.extend([u for (_id, u) in update_pairs])
                    for u in targets:
                        if fixed_pop_id:
                            u['population'] = {'id': fixed_pop_id}
                            continue
                        pop = u.get('population')
                        if isinstance(pop, dict):
                            name = pop.get('name')
                            if name and name in pops:
                                u['population'] = {'id': pops[name]}
                                continue
                            val = pop.get('id')
                            if val:
                                if val in pops.values():
                                    u['population'] = {'id': val}
                                elif val in pops:
                                    u['population'] = {'id': pops[val]}
                except Exception:
                    pass

                # Start create worker then update worker (if any)
                if create_users:
                    self.prog.show()
                    self.prog.setRange(0, len(create_users))
                    w = BulkCreateWorker(client, create_users)
                    w.signals.progress.connect(lambda cur, tot: self.prog.setValue(cur))
                    w.signals.status.connect(lambda msg: self._set_processing_message(msg))

                    def on_done(res):
                        created = res.get('created', 0)
                        updated_on_retry = res.get('updated_on_retry', 0)
                        total = res.get('total', 0)
                        errors = res.get('errors', []) or []
                        create_tps_stats = res.get('tps_stats')

                        def _on_updates_done(res2):
                            self.prog.hide()
                            self.cancel_btn.hide()
                            updated = res2.get('updated', 0)
                            total_upd = res2.get('total', 0)
                            upd_errors = res2.get('errors', []) or []
                            update_tps_stats = res2.get('tps_stats')
                            result_msg = f"Created {created}/{total} users"
                            if updated_on_retry:
                                result_msg += f"; Updated on retry {updated_on_retry}"
                            result_msg += f"; Updated {updated}/{total_upd} users"
                            
                            # Combine TPS stats from create and update operations
                            combined_tps = None
                            if create_tps_stats or update_tps_stats:
                                combined_tps = {
                                    'total_transactions': 0,
                                    'total_duration': 0.0,
                                    'average_tps': 0.0,
                                    'mean_tps': 0.0,
                                    'peak_tps': 0.0,
                                }
                                if create_tps_stats:
                                    combined_tps['total_transactions'] += create_tps_stats.get('total_transactions', 0)
                                    combined_tps['total_duration'] += create_tps_stats.get('total_duration', 0.0)
                                    combined_tps['peak_tps'] = max(combined_tps['peak_tps'], create_tps_stats.get('peak_tps', 0.0))
                                if update_tps_stats:
                                    combined_tps['total_transactions'] += update_tps_stats.get('total_transactions', 0)
                                    combined_tps['total_duration'] += update_tps_stats.get('total_duration', 0.0)
                                    combined_tps['peak_tps'] = max(combined_tps['peak_tps'], update_tps_stats.get('peak_tps', 0.0))
                                
                                # Recalculate average and mean
                                if combined_tps['total_duration'] > 0:
                                    combined_tps['average_tps'] = combined_tps['total_transactions'] / combined_tps['total_duration']
                                # Mean is approximated as weighted average
                                total_weight = 0
                                weighted_sum = 0
                                if create_tps_stats and create_tps_stats.get('total_duration', 0) > 0:
                                    weighted_sum += create_tps_stats.get('mean_tps', 0) * create_tps_stats.get('total_duration', 0)
                                    total_weight += create_tps_stats.get('total_duration', 0)
                                if update_tps_stats and update_tps_stats.get('total_duration', 0) > 0:
                                    weighted_sum += update_tps_stats.get('mean_tps', 0) * update_tps_stats.get('total_duration', 0)
                                    total_weight += update_tps_stats.get('total_duration', 0)
                                if total_weight > 0:
                                    combined_tps['mean_tps'] = weighted_sum / total_weight
                            
                            # Show TPS report if available
                            if combined_tps and combined_tps.get('total_transactions', 0) > 0:
                                self._show_tps_report(combined_tps, "Import")
                            
                            errors_combined = errors + upd_errors
                            if errors_combined:
                                dlg = QtWidgets.QDialog(self)
                                dlg.setWindowTitle("Import Result")
                                lay = QtWidgets.QVBoxLayout(dlg)
                                lab = QtWidgets.QLabel(result_msg)
                                te = QtWidgets.QTextEdit()
                                te.setReadOnly(True)
                                te.setPlainText('\n'.join(errors_combined))
                                te.setMinimumHeight(300)
                                lay.addWidget(lab)
                                lay.addWidget(te)
                                btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
                                btns.accepted.connect(dlg.accept)
                                lay.addWidget(btns)
                                try:
                                    screen = QtWidgets.QApplication.primaryScreen()
                                    geom = screen.availableGeometry()
                                    wdt = min(int(geom.width() * 0.75), 1100)
                                    hgt = min(int(geom.height() * 0.6), 800)
                                    dlg.resize(max(700, wdt), max(400, hgt))
                                except Exception:
                                    dlg.resize(900, 500)
                                dlg.exec()
                            else:
                                QtWidgets.QMessageBox.information(self, "Import Complete", result_msg)
                            self._include_import_attributes_in_grid(users)
                            self.refresh_users()

                        if update_pairs:
                            self.prog.show()
                            self.cancel_btn.show()
                            self.prog.setRange(0, len(update_pairs))
                            # PHASE 2 OPTIMIZATION: Use parallel processing for large updates
                            concurrency = 5 if len(update_pairs) > 100 else 1
                            upd_w = BulkUpdateWorker(client, update_pairs, cancel_check=lambda: self.cancel_requested, concurrency=concurrency)
                            upd_w.signals.progress.connect(lambda cur, tot: self.prog.setValue(cur))
                            upd_w.signals.tps_update.connect(lambda tps_stats: self._update_tps_status_bar(tps_stats, "Update"))
                            upd_w.signals.finished.connect(_on_updates_done)
                            upd_w.signals.error.connect(lambda m: (self.prog.hide(), self.cancel_btn.hide(), QtWidgets.QMessageBox.critical(self, "Update Error", m)))
                            self.threadpool.start(upd_w)
                        else:
                            _on_updates_done({"updated": 0, "total": 0, "errors": []})

                    w.signals.finished.connect(on_done)
                    w.signals.error.connect(lambda m: (self.prog.hide(), QtWidgets.QMessageBox.critical(self, "Import Error", m)))
                    self.threadpool.start(w)
                    msg = f"Import started: {len(create_users)} users to create; {len(update_pairs)} to update"
                else:
                    # no creates; run updates directly
                    if update_pairs:
                        self.prog.show()
                        self.cancel_btn.show()
                        self.prog.setRange(0, len(update_pairs))
                        # PHASE 2 OPTIMIZATION: Use parallel processing for large updates
                        concurrency = 5 if len(update_pairs) > 100 else 1
                        upd_w = BulkUpdateWorker(client, update_pairs, cancel_check=lambda: self.cancel_requested, concurrency=concurrency)
                        upd_w.signals.tps_update.connect(lambda tps_stats: self._update_tps_status_bar(tps_stats, "Update"))
                        upd_w.signals.progress.connect(lambda cur, tot: self.prog.setValue(cur))

                        def _on_updates_done2(res):
                            self.prog.hide()
                            self.cancel_btn.hide()
                            updated = res.get('updated', 0)
                            total_upd = res.get('total', 0)
                            upd_errors = res.get('errors', []) or []
                            tps_stats = res.get('tps_stats')
                            result_msg = f"Updated {updated}/{total_upd} users"
                            
                            # Show TPS report if available
                            if tps_stats and tps_stats.get('total_transactions', 0) > 0:
                                self._show_tps_report(tps_stats, "Import")
                            
                            if upd_errors:
                                dlg = QtWidgets.QDialog(self)
                                dlg.setWindowTitle("Import Result")
                                lay = QtWidgets.QVBoxLayout(dlg)
                                lab = QtWidgets.QLabel(result_msg)
                                te = QtWidgets.QTextEdit()
                                te.setReadOnly(True)
                                te.setPlainText('\n'.join(upd_errors))
                                te.setMinimumHeight(300)
                                lay.addWidget(lab)
                                lay.addWidget(te)
                                btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
                                btns.accepted.connect(dlg.accept)
                                lay.addWidget(btns)
                                try:
                                    screen = QtWidgets.QApplication.primaryScreen()
                                    geom = screen.availableGeometry()
                                    wdt = min(int(geom.width() * 0.75), 1100)
                                    hgt = min(int(geom.height() * 0.6), 800)
                                    dlg.resize(max(700, wdt), max(400, hgt))
                                except Exception:
                                    dlg.resize(900, 500)
                                dlg.exec()
                            else:
                                QtWidgets.QMessageBox.information(self, "Import Complete", result_msg)
                            self._include_import_attributes_in_grid(users)
                            self.refresh_users()

                        upd_w.signals.finished.connect(_on_updates_done2)
                        upd_w.signals.error.connect(lambda m: (self.prog.hide(), QtWidgets.QMessageBox.critical(self, "Update Error", m)))
                        self.threadpool.start(upd_w)
                        msg = f"Import started: {len(update_pairs)} users to update"
                    else:
                        QtWidgets.QMessageBox.information(self, "Import", "No users to create or update.")
                try:
                    self._set_processing_message(msg)
                except Exception:
                    pass
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import Error", str(e))

    def _include_import_attributes_in_grid(self, imported_users: list):
        """Append additional imported attributes to currently selected columns."""
        try:
            if not imported_users:
                return
            imported_cols = self._get_all_columns(imported_users)
            added = [c for c in imported_cols if c not in self.selected_columns]
            if not added:
                return
            self.selected_columns.extend(added)
            self.save_columns_to_config()
            msg = f"Added {len(added)} imported attribute column(s) to grid"
            try:
                self._set_processing_message(msg, 4000)
            except Exception:
                pass
        except Exception:
            pass

    def save_columns_to_config(self, show_notification=False):
        """Save the selected columns to the current profile's configuration."""
        name = self.profile_list.currentText()
        if not name:
            return
        p = self._read_config()
        if name in p:
            p[name]["columns"] = self.selected_columns
            self._write_config(p)
            if show_notification:
                msg = f"Column layout saved for profile '{name}'"
                self.status_label.setText(msg)
                try:
                    self._set_processing_message(msg, 3000)
                except Exception:
                    pass

    # --- Connection logging helpers ---
    @property
    def connection_log_path(self):
        return Path("connection_errors.log")

    def log_connection_error(self, message: str):
        try:
            ts = datetime.utcnow().isoformat() + "Z"
            with open(self.connection_log_path, 'a', encoding='utf-8') as f:
                f.write(f"[{ts}] {message}\n")
        except Exception:
            pass

    def _log_tps_statistics(self, tps_stats: dict, operation_name: str = "Operation"):
        """Log TPS statistics to a CSV file for reporting purposes.
        
        Args:
            tps_stats: Dictionary with TPS statistics from TPSTracker
            operation_name: Name of the operation (e.g., "Import", "Export", "Delete")
        """
        if not tps_stats:
            return
        
        try:
            from datetime import datetime
            import os
            import csv
            
            # Get statistics
            total_transactions = tps_stats.get('total_transactions', 0)
            total_duration = tps_stats.get('total_duration', 0.0)
            average_tps = tps_stats.get('average_tps', 0.0)
            mean_tps = tps_stats.get('mean_tps', 0.0)
            peak_tps = tps_stats.get('peak_tps', 0.0)
            start_time = tps_stats.get('start_time')
            end_time = tps_stats.get('end_time')
            
            # Format timestamps
            start_str = ""
            end_str = ""
            if start_time:
                start_str = datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')
            if end_time:
                end_str = datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')
            
            # Current timestamp for log entry
            log_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # CSV file path
            csv_file = "performance_stats.csv"
            
            # Check if file exists to determine if we need to write header
            write_header = not os.path.exists(csv_file)
            
            # Write to CSV file
            with open(csv_file, 'a', newline='', encoding='utf-8') as f:
                csv_writer = csv.writer(f)
                
                if write_header:
                    # Write CSV header
                    csv_writer.writerow([
                        'log_timestamp',
                        'operation',
                        'start_time',
                        'end_time',
                        'total_transactions',
                        'total_duration_seconds',
                        'average_tps',
                        'mean_tps',
                        'peak_tps'
                    ])
                
                # Write data row
                csv_writer.writerow([
                    log_timestamp,
                    operation_name,
                    start_str,
                    end_str,
                    total_transactions,
                    f"{total_duration:.2f}",
                    f"{average_tps:.2f}",
                    f"{mean_tps:.2f}",
                    f"{peak_tps:.0f}"
                ])
                
        except Exception as e:
            # Silently fail if logging doesn't work - don't interrupt the user's workflow
            try:
                import api.client as api_client
                if api_client.API_LOGGING_ENABLED:
                    api_client.api_logger.error(f"Failed to log TPS statistics: {e}")
            except Exception:
                pass
    
    def _show_tps_report(self, tps_stats: dict, operation_name: str = "Operation"):
        """Display a TPS (Transactions Per Second) report dialog.
        
        Args:
            tps_stats: Dictionary with TPS statistics from TPSTracker
            operation_name: Name of the operation (e.g., "Import", "Export")
        """
        if not tps_stats:
            return
        
        # Log statistics to file
        self._log_tps_statistics(tps_stats, operation_name)
        
        # Update status bar with last TPS
        self._update_tps_status_bar(tps_stats, operation_name)
        
        total_transactions = tps_stats.get('total_transactions', 0)
        total_duration = tps_stats.get('total_duration', 0.0)
        average_tps = tps_stats.get('average_tps', 0.0)
        mean_tps = tps_stats.get('mean_tps', 0.0)
        peak_tps = tps_stats.get('peak_tps', 0.0)
        start_time = tps_stats.get('start_time')
        end_time = tps_stats.get('end_time')
        
        # Format start/end times
        from datetime import datetime
        start_str = ""
        end_str = ""
        if start_time:
            start_str = datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')
        if end_time:
            end_str = datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')
        
        # Create dialog
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"{operation_name} - TPS Report")
        lay = QtWidgets.QVBoxLayout(dlg)
        
        # Title label
        title = QtWidgets.QLabel(f"<b>{operation_name} Performance Report</b>")
        title.setAlignment(QtCore.Qt.AlignCenter)
        lay.addWidget(title)
        
        # Statistics - include start/end times
        stats_text = f"""
<table style="margin: 10px;">
<tr><td><b>Start Time:</b></td><td>{start_str}</td></tr>
<tr><td><b>End Time:</b></td><td>{end_str}</td></tr>
<tr><td></td><td></td></tr>
<tr><td><b>Total Transactions:</b></td><td>{total_transactions}</td></tr>
<tr><td><b>Total Duration:</b></td><td>{total_duration:.2f} seconds</td></tr>
<tr><td></td><td></td></tr>
<tr><td><b>Average TPS:</b></td><td>{average_tps:.2f} transactions/second</td></tr>
<tr><td><b>Mean TPS:</b></td><td>{mean_tps:.2f} transactions/second</td></tr>
<tr><td><b>Peak TPS:</b></td><td>{peak_tps:.0f} transactions/second</td></tr>
</table>
"""
        stats_label = QtWidgets.QLabel(stats_text)
        stats_label.setTextFormat(QtCore.Qt.RichText)
        stats_label.setAlignment(QtCore.Qt.AlignLeft)
        lay.addWidget(stats_label)
        
        # Explanation
        explanation = QtWidgets.QLabel(
            "<i>Average TPS = Total transactions ÷ Total duration<br>"
            "Mean TPS = Average of all 1-second window values<br>"
            "Peak TPS = Maximum transactions in any 1-second window</i>"
        )
        explanation.setTextFormat(QtCore.Qt.RichText)
        explanation.setWordWrap(True)
        lay.addWidget(explanation)

        # Countdown indicator for auto-close behavior.
        countdown_seconds = 5
        countdown_label = QtWidgets.QLabel()
        countdown_label.setTextFormat(QtCore.Qt.RichText)
        countdown_label.setAlignment(QtCore.Qt.AlignCenter)
        lay.addWidget(countdown_label)
        
        # Close button
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        btns.accepted.connect(dlg.accept)
        lay.addWidget(btns)

        # Auto-close the TPS report after 5 seconds and update visible countdown.
        countdown_timer = QtCore.QTimer(dlg)
        countdown_timer.setInterval(1000)

        def _format_countdown_text(seconds: int) -> str:
            second_word = "second" if seconds == 1 else "seconds"
            if seconds <= 2:
                return (
                    f"<b><span style='color:#b00020;'>"
                    f"This report will close automatically in {seconds} {second_word}."
                    f"</span></b>"
                )
            return f"<i>This report will close automatically in {seconds} {second_word}.</i>"

        def _update_countdown() -> None:
            nonlocal countdown_seconds
            countdown_seconds -= 1
            if countdown_seconds <= 0:
                countdown_timer.stop()
                dlg.accept()
                return
            countdown_label.setText(_format_countdown_text(countdown_seconds))

        countdown_label.setText(_format_countdown_text(countdown_seconds))
        countdown_timer.timeout.connect(_update_countdown)
        countdown_timer.start()
        
        dlg.exec()
    
    def _update_tps_status_bar(self, tps_stats: dict, operation_name: str = "Operation"):
        """Update the status bar with the last TPS statistics.
        
        Args:
            tps_stats: Dictionary with TPS statistics from TPSTracker
            operation_name: Name of the operation (e.g., "Import", "Export")
        """
        if not tps_stats:
            return
        
        self.last_tps_stats = tps_stats
        average_tps = tps_stats.get('average_tps', 0.0)
        
        # Format the TPS display for the status bar
        tps_text = f"Last TPS ({operation_name}): {average_tps:.2f} trans/sec"
        self.last_tps_label.setText(tps_text)
        try:
            # Ensure the label is visible
            self.last_tps_label.show()
        except Exception:
            pass

    def on_connection_error(self, message: str):
        self.prog.hide()
        # log to file
        self.log_connection_error(message)
        # show modal error
        QtWidgets.QMessageBox.critical(self, "Error", message)

    def view_connection_log(self):
        try:
            if not self.connection_log_path.exists():
                QtWidgets.QMessageBox.information(self, "Connection Log", "No connection log entries yet.")
                return
            with open(self.connection_log_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            content = f"Failed to read connection log: {e}"
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Connection Log")
        lay = QtWidgets.QVBoxLayout(dlg)
        te = QtWidgets.QTextEdit(); te.setReadOnly(True); te.setPlainText(content)
        lay.addWidget(te)
        btn = QtWidgets.QPushButton("Close"); btn.clicked.connect(dlg.accept)
        lay.addWidget(btn)
        dlg.resize(800, 400)
        dlg.exec()

    def refresh_table(self):
        """Refresh the user table with the currently selected columns."""
        if not self.users_cache:
            return
        
        # Filter columns to only those present in dataset
        self.columns = self._get_visible_columns(self.selected_columns, self.all_columns)
        
        # Disable sorting during table rebuild for better performance
        self.u_table.setSortingEnabled(False)
        self.u_table.setColumnCount(len(self.columns))
        self.u_table.setHorizontalHeaderLabels(self._get_column_labels())
        self.u_table.setRowCount(len(self.users_cache))
        
        # Populate table rows
        for row_idx, user in enumerate(self.users_cache):
            for col_idx, col in enumerate(self.columns):
                value = self._get_value(user, col)
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setData(QtCore.Qt.UserRole, value)
                self.u_table.setItem(row_idx, col_idx, item)
        
        self.u_table.setSortingEnabled(True)
        self._apply_column_widths()

    def on_item_double_clicked(self, item):
        """Handle double-click on table items: edit on ID, email, JSON for name/address."""
        row = item.row()
        col = item.column()
        col_name = self.columns[col]
        id_col = self.columns.index('id') if 'id' in self.columns else -1
        if id_col == -1: return
        user_id = self.u_table.item(row, id_col).text()
        # Open editor when double-clicking UUID, username, or email.
        # Email no longer launches mailto, but remains editable via dialog.
        if col_name in ('id', 'username', 'email'):
            self.u_table.selectRow(row)
            self.edit_user()
            return
        # Prefer using the original user payload for JSON-like attributes
        # (e.g. `name`, `address`) rather than the stringified table value.
        data = item.data(QtCore.Qt.UserRole)
        # If the cell contains a URL, open it. If it contains JSON or a blob,
        # show it in an appropriate dialog.
        text = item.text() or ''
        # quick URL detection
        import re, json as _json
        url_match = re.search(r'(https?://\S+)', text)
        if url_match:
            url = url_match.group(1)
            if QtWidgets.QMessageBox.question(self, "Open Link", f"Open link {url}?") == QtWidgets.QMessageBox.Yes:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))
            return

        # If the underlying data is a dict/list prefer JSON view
        if isinstance(data, (dict, list)):
            dialog = JSONViewDialog(data, self.json_editing_enabled, self, user_id, col_name)
            dialog.exec()
            return

        # For name/address columns, prefer nested object from user cache
        if col_name in ['name', 'address']:
            user_obj = next((u for u in self.users_cache if u.get('id') == user_id), None)
            if user_obj:
                nested = user_obj.get(col_name, {})
                if isinstance(nested, (dict, list)):
                    dialog = JSONViewDialog(nested, self.json_editing_enabled, self, user_id, col_name)
                    dialog.exec()
                    return

        # Try parse JSON from text
        stripped = text.strip()
        if stripped.startswith('{') or stripped.startswith('['):
            try:
                parsed = _json.loads(stripped)
                dialog = JSONViewDialog(parsed, self.json_editing_enabled, self, user_id, col_name)
                dialog.exec()
                return
            except Exception:
                pass

        # If long or multiline, show in TextViewDialog
        if '\n' in text or len(text) > 180:
            from ui.dialogs import TextViewDialog
            dlg = TextViewDialog(text, title=f"{col_name} content", parent=self, editable=self.json_editing_enabled, user_id=user_id, col_name=col_name)
            dlg.exec()
            return

    def on_column_moved(self, logicalIndex, oldVisualIndex, newVisualIndex):
        """Update the selected columns order after user reorders table columns."""
        self._capture_current_column_layout()
        msg = "Column order updated"
        try:
            self._set_processing_message(msg)
        except Exception:
            pass

    def _capture_current_column_layout(self):
        """Persist current visual column order (and widths) into selected_columns."""
        try:
            if not hasattr(self, 'u_table') or self.u_table.columnCount() == 0:
                return
            if not self.columns:
                return
            header = self.u_table.horizontalHeader()
            visual_order = []
            for visual_idx in range(self.u_table.columnCount()):
                logical_idx = header.logicalIndex(visual_idx)
                if 0 <= logical_idx < len(self.columns):
                    visual_order.append(self.columns[logical_idx])
            if visual_order:
                # Keep non-visible selected columns (if any) appended in original order.
                remaining = [c for c in self.selected_columns if c not in visual_order]
                self.selected_columns = visual_order + remaining
                self.save_columns_to_config()
        except Exception:
            pass

    def on_column_resized(self, logicalIndex, oldSize, newSize):
        """Save column width when resized."""
        if logicalIndex < len(self.columns):
            col_name = self.columns[logicalIndex]
            self.column_widths[col_name] = newSize
            self.save_columns_to_config()

    def show_context_menu(self, position):
        """Show context menu for the user table (Edit / Delete Selected)."""
        menu = QtWidgets.QMenu(self)
        # Only allow deletion from context menu; editing is via double-click on id/username.
        delete_action = menu.addAction("Delete Selected")
        action = menu.exec(self.u_table.mapToGlobal(position))
        if action == delete_action:
            self.delete_selected_users()
