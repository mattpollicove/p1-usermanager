import json
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

# If this file is executed directly (e.g. via the editor), ensure the
# project root is on `sys.path` so local packages like `api` and `workers`
# can be imported using absolute imports.
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import keyring
from PySide6 import QtWidgets, QtCore, QtGui

import api.client as api_client
from workers import UserFetchWorker, BulkDeleteWorker, UserUpdateWorker, BulkCreateWorker, BulkUpdateWorker
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
APP_VERSION = "0.71"
DEFAULT_PINGONE_CONSOLE_URL = "https://console.pingone.com/"


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
   The Client Secret is stored securely in your system's keyring.

4. Click "Save Profile" to persist the credentials and settings.  (Alternatively, use the new "New Connection" button to clear the boxes and enter a fresh set of credentials.)

5. Click "Connect & Sync" to authenticate and fetch users from PingOne.

Profile Settings:
- Credentials (Env ID, Client ID, Secret) are saved per-profile.
- Column selection and order are saved per-profile.
- Import/export preferences are saved per-profile when "Remember" is checked.
- The last active profile can auto-connect on startup (see Settings menu).

Managing Profiles:
- Use File → Manage Profiles (Cmd/Ctrl+Shift+M) to view all saved profiles.
- The Profile Manager shows environment IDs, client IDs, and column counts.
- Delete unwanted profiles from the Profile Manager dialog.
- The currently active profile cannot be deleted; switch profiles first.

Database Import/Export:
- Use File → Manage DB Connections (or the button in Configuration tab) to define connections.
- Supported types: MSSQL and MariaDB/MySQL. Provide JDBC/ODBC driver path if needed.
- After defining a connection you can import or export data via the toolbar buttons on the User Management tab.
- LDAP directories are also supported via Manage LDAP Connections.
- Use the Configuration action "Open PingOne Console" to launch the active environment in your browser.

Status Bar:
- Shows live API call summaries when "Show API calls in status bar" is enabled.
- Displays connection status and recent operation results.
- API call logging can be toggled from the Settings menu.
- Use Settings -> Show Log Files to open log viewers with in-window controls.

Settings Menu:
- Dark Mode: Toggle between light and dark themes (Cmd+D / Ctrl+D).
- Set PingOne Console URL: Configure the base console URL used by the
    "Open PingOne Console" action.
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
  • The 'enabled' field is a dropdown (true/false)
  • You can assign a fixed population to all imported users
  • Check "Remember mapping for this profile" to save mappings
- Database import: first define a connection via File → Manage DB Connections or the Configuration tab button, then click "Import DB" on the User Management toolbar and follow the prompts to select a table and map its columns.
- LDAP import: define a directory in "Manage LDAP Connections", then use Import and select "LDAP Directory" to map LDAP attributes to PingOne attributes.
- Imported attributes not currently shown are automatically added to the grid columns after import.
- For DB imports/exports, you can save custom queries and mapping selections in DB connection settings; saved queries auto-reuse their saved mappings.
- LDAP mappings can also be saved per LDAP connection for reuse.
- During import preparation, PingOne attributes are refreshed from live user data so custom attributes appear in mapping choices.
- Usernames are normalized (whitespace trimmed, case-insensitive comparison).
- If a username already exists on the server, the import updates that user instead of creating a duplicate.
- Local JSON Schema validation is performed if jsonschema is installed and user_schema.json exists.

Exporting Users:
- Click "Export CSV" or "Export LDIF" to save users.
- Choose to export all users or selected rows only.
- Choose to export all columns or only visible columns.
- Check "Remember these choices" to save export preferences per-profile.
- Database export: click "Export DB" on the toolbar (after defining a connection) to map PingOne attributes to target table columns; the table will be created if it does not already exist.
- LDAP export: choose "Export → LDAP Directory" and map PingOne attributes to LDAP attributes; entries are created or updated by DN.

Deleting Users:
- Select one or more rows and click "Delete Selected" or use the context menu.
- A confirmation dialog will appear before deletion.
- Progress is shown for bulk deletions.

Logging & Log Viewers:
- Settings -> Show Log Files opens the log index dialog.
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
        # Default column order: UUID, first name, last name, email, population.
        # This matches the requested default and ensures the UUID is always visible
        # as the left-most column.
        self.default_columns = ['id', 'name.given', 'name.family', 'email', 'population.name']
        self.selected_columns = self.default_columns.copy()
        self.all_columns = set()
        self.json_editing_enabled = False
        self.use_friendly_names = True
        self.pingone_console_url = DEFAULT_PINGONE_CONSOLE_URL
        self._closing = False
        self.hide_raw_http_columns = False
        self.column_widths = {}
        self.friendly_names = {
            'username': 'Username',
            'name.given': 'First Name',
            'name.family': 'Last Name',
            'email': 'Email',
            'phoneNumbers': 'Phone',
            'population.name': 'Population',
            'id': 'UUID',
            'name': 'Name',
            'address': 'Address',
        }
        self.init_ui()
        self.load_profiles_from_disk()
        self.load_theme_preference()
        # Don't restore geometry here - do it in showEvent after window is shown

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
        file_menu.addSeparator()
        quit_action = file_menu.addAction("Quit")
        quit_action.triggered.connect(self.close)
        quit_action.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_Q))
        quit_action.setToolTip(f"Quit application ({'Cmd' if IS_MACOS else 'Ctrl'}+Q)")
        if IS_MACOS:
            # On macOS, the quit action should have the QuitRole to appear in app menu
            quit_action.setMenuRole(QtGui.QAction.MenuRole.QuitRole)
        
        settings_menu = menubar.addMenu("Settings")
        self.enable_json_edit_action = settings_menu.addAction("Enable JSON Editing")
        self.enable_json_edit_action.setCheckable(True)
        self.enable_json_edit_action.setChecked(False)
        self.enable_json_edit_action.triggered.connect(self.toggle_json_editing)
        self.enable_json_edit_action.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_J))
        
        self.use_friendly_names_action = settings_menu.addAction("Use Friendly Column Names")
        self.use_friendly_names_action.setCheckable(True)
        self.use_friendly_names_action.setChecked(True)
        self.use_friendly_names_action.triggered.connect(self.toggle_friendly_names)
        self.use_friendly_names_action.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_F))
        # Validation mode: server dry-run or local schema
        settings_menu.addSeparator()
        self.use_server_dryrun_action = settings_menu.addAction("Use Server Dry-Run")
        self.use_server_dryrun_action.setCheckable(True)
        self.use_server_dryrun_action.setChecked(True)
        self.use_server_dryrun_action.triggered.connect(self.toggle_server_dryrun)
        self.use_local_schema_action = settings_menu.addAction("Use Local Schema Validation")
        self.use_local_schema_action.setCheckable(True)
        self.use_local_schema_action.setChecked(False)
        self.use_local_schema_action.triggered.connect(self.toggle_local_schema)
        self.revert_columns_action = settings_menu.addAction("Revert to Default Columns")
        self.revert_columns_action.triggered.connect(self.revert_to_default_columns)
        settings_menu.addSeparator()
        # Theme toggle
        self.dark_mode_action = settings_menu.addAction("Dark Mode")
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.setChecked(False)
        self.dark_mode_action.triggered.connect(self.toggle_theme)
        self.dark_mode_action.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_D))
        settings_menu.addSeparator()
        # Credentials logging settings
        self.enable_credentials_logging_action = settings_menu.addAction("Enable Credentials Logging")
        self.enable_credentials_logging_action.setCheckable(True)
        self.enable_credentials_logging_action.setChecked(True)
        self.enable_credentials_logging_action.triggered.connect(self.toggle_credentials_logging)
        settings_menu.addSeparator()
        # API logging toggle (log all API activity)
        self.enable_api_logging_action = settings_menu.addAction("Log All API Activity")
        self.enable_api_logging_action.setCheckable(True)
        self.enable_api_logging_action.setChecked(False)
        self.enable_api_logging_action.triggered.connect(self.toggle_api_logging)
        self.capture_api_action = settings_menu.addAction("Capture API Calls...")
        self.capture_api_action.triggered.connect(self.show_api_capture_dialog)
        # Show where logs are written on disk (also available under Logs menu)
        self.show_logs_action = settings_menu.addAction("Show Log Files...")
        self.show_logs_action.triggered.connect(self.show_log_files)
        settings_menu.addSeparator()
        self.set_console_url_action = settings_menu.addAction("Set PingOne Console URL...")
        self.set_console_url_action.triggered.connect(self.set_pingone_console_url)

        # Separate Logs submenu for quick actions (reset, clear, archive)
        logs_menu = menubar.addMenu("Logs")
        self.logs_show_action = logs_menu.addAction("Show Log Files...")
        self.logs_show_action.triggered.connect(self.show_log_files)
        self.logs_clear_all = logs_menu.addAction("Clear All Logs")
        self.logs_clear_all.triggered.connect(self.clear_all_logs)
        self.logs_archive = logs_menu.addAction("Archive Logs...")
        self.logs_archive.triggered.connect(self.archive_logs)
        
        help_menu = menubar.addMenu("Help")
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
        
        # --- Config Tab ---
        env_tab = QtWidgets.QWidget(); env_lay = QtWidgets.QVBoxLayout(env_tab)
        prof_group = QtWidgets.QGroupBox("Profiles")
        prof_form = QtWidgets.QFormLayout(prof_group)
        self.profile_list = QtWidgets.QComboBox()
        self.profile_list.currentIndexChanged.connect(self.load_selected_profile)
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
            "Manage DB Connections",
            "Manage LDAP Connections",
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

        # Per-profile option: show live API calls in status bar
        self.show_api_calls_cb = QtWidgets.QCheckBox('Show live API calls in status bar')
        self.show_api_calls_cb.setChecked(False)
        self.show_api_calls_cb.stateChanged.connect(self.on_show_api_calls_toggled)
        cred_form.addRow(self.show_api_calls_cb)
        
        self.lbl_stats = QtWidgets.QLabel("Users: -- | Populations: --")
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

        self.hide_raw_http_columns_cb = QtWidgets.QCheckBox("Hide Links")
        self.hide_raw_http_columns_cb.setChecked(False)
        self.hide_raw_http_columns_cb.setToolTip("Hide columns whose names start with '{' or 'http'")
        self.hide_raw_http_columns_cb.stateChanged.connect(self.on_hide_raw_http_columns_toggled)
        toolbar.addWidget(self.hide_raw_http_columns_cb)

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
        if IS_MACOS:
            self.shortcut_delete_users = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Backspace), self)
        else:
            self.shortcut_delete_users = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Delete), self)
        self.shortcut_delete_users.activated.connect(self.delete_selected_users)
        
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
        
        self.prog = QtWidgets.QProgressBar(); self.prog.hide()
        user_lay.addLayout(toolbar); user_lay.addWidget(self.prog); user_lay.addWidget(self.u_table)
        # Add a persistent status bar so messages are visible across tabs
        self.status_label = QtWidgets.QLabel("Ready")
        self.api_calls_label = QtWidgets.QLabel("")
        self.profile_name_label = QtWidgets.QLabel("")
        self.last_source_label = QtWidgets.QLabel("Last source: none")
        user_lay.addWidget(self.status_label)
        user_lay.addWidget(self.api_calls_label)
        sb = QtWidgets.QStatusBar()
        self.setStatusBar(sb)
        # Mirror initial status and add permanent widgets to status bar
        try:
            self.statusBar().showMessage(self.status_label.text())
            self.statusBar().addPermanentWidget(self.profile_name_label)
            self.statusBar().addPermanentWidget(self.last_source_label)
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
            "Manage DB Connections": self.manage_db_connections,
            "Manage LDAP Connections": self.manage_ldap_connections,
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
                    self.statusBar().showMessage(msg, 3000)
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
        )
        if dlg.exec() != QtWidgets.QDialog.Accepted:
            return
        
        result = dlg.get_result()
        source_type = result.get('source_type')
        
        try:
            if source_type == 'csv':
                self.import_from_csv()
            elif source_type == 'ldif':
                self.import_from_ldif()
            elif source_type == 'db':
                self.import_from_database_wizard(
                    connection_name=result.get('connection_name'),
                    query_mode=result.get('query_mode', 'table')
                )
            elif source_type == 'ldap':
                self.import_from_ldap_directory_wizard(
                    connection_name=result.get('connection_name')
                )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import Error", str(e))

    def _show_export_menu(self):
        """Show export options dialog for CSV, LDIF, or Database."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Export")
        dlg.setModal(True)
        layout = QtWidgets.QVBoxLayout(dlg)
        layout.addWidget(QtWidgets.QLabel("Select export format:"))

        rb_csv = QtWidgets.QRadioButton("CSV")
        rb_ldif = QtWidgets.QRadioButton("LDIF")
        rb_db = QtWidgets.QRadioButton("Database")
        rb_ldap = QtWidgets.QRadioButton("LDAP Directory")
        rb_csv.setChecked(True)
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
            self.export_to_csv()
        elif rb_ldif.isChecked():
            self.export_to_ldif()
        elif rb_db.isChecked():
            self.export_to_database()
        elif rb_ldap.isChecked():
            self.export_to_ldap_directory()

    def _set_last_data_source(self, source: str):
        """Update status bar with the most recent DB connection or input file source."""
        if not source:
            return
        try:
            self.last_source_label.setText(f"Last source: {source}")
        except Exception:
            pass

    # --- Profile Methods ---
    def _read_config(self):
        if self.config_file.exists():
            with open(self.config_file, 'r') as f: return json.load(f)
        return {}

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
            
            with open(self.config_file, 'w') as f:
                json.dump(cfg, f, indent=4)
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
            with open(self.config_file, 'w') as f:
                json.dump(cfg, f, indent=4)

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
        except Exception:
            pass
        if self.profile_list.count() > 0:
            # If auto-connect is enabled and there is a last working profile, select it
            try:
                meta = cfg.get('__meta__', {})
                last = meta.get('last_working_profile')
                if last and last in profile_names and self.auto_connect_cb.isChecked() and not skip_connect:
                    idx = profile_names.index(last)
                    self.profile_list.setCurrentIndex(idx)
                    # Ensure profile fields are loaded before attempting connect
                    try:
                        self.load_selected_profile()
                    except Exception:
                        pass
                    # Delay connect slightly to allow UI to settle
                    QtCore.QTimer.singleShot(250, self.connect_only)
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
            self.env_id.setText(p[name].get("env_id", ""))
            self.cl_id.setText(p[name].get("cl_id", ""))
            try:
                self.cl_sec.setText(keyring.get_password("pingone_usermanager", name) or "")
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
                hide_cols = bool(p[name].get('hide_raw_http_columns', False))
                self.hide_raw_http_columns = hide_cols
                self.hide_raw_http_columns_cb.setChecked(hide_cols)
            except Exception:
                pass
            try:
                msg = f"Profile loaded: {name}"
                self.status_label.setText(msg)
                try:
                    self.statusBar().showMessage(msg)
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
            # also update last working profile so auto-connect will remember this one
            meta = p.get('__meta__', {})
            meta['last_working_profile'] = name
            p['__meta__'] = meta
            with open(self.config_file, 'w') as f:
                json.dump(p, f, indent=4)
            try:
                keyring.set_password("pingone_usermanager", name, self.cl_sec.text())
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
            cfg['__meta__'] = meta
            with open(self.config_file, 'w') as f:
                json.dump(cfg, f, indent=4)
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
            with open(self.config_file, 'w') as f:
                json.dump(cfg, f, indent=4)
        except Exception:
            pass

    def _should_hide_column(self, column_name: str) -> bool:
        """Return True when the current view filter hides the column."""
        if not self.hide_raw_http_columns:
            return False
        name = str(column_name or '').lstrip().lower()
        if name.startswith('{') or name.startswith('http'):
            return True

        # Also hide columns whose displayed values are link-like/JSON-like.
        # This matches the "Hide Links" intent for dynamically-named columns.
        try:
            if self.users_cache:
                for user in self.users_cache[:200]:
                    val = self._get_value(user, column_name)
                    text = str(val or '').lstrip().lower()
                    if not text:
                        continue
                    return text.startswith('{') or text.startswith('http')
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
            new_data = dlg.get_data()
            # Spawn worker to update user
            client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
            self.prog.show()
            worker = UserUpdateWorker(client, user_id, new_data)
            worker.signals.finished.connect(lambda r: (self.prog.hide(), self.refresh_users()))
            worker.signals.error.connect(lambda m: (self.prog.hide(), QtWidgets.QMessageBox.critical(self, "Error", m)))
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
            with open(self.config_file, 'w') as f:
                json.dump(cfg, f, indent=4)
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
            with open(self.config_file, 'w') as f:
                json.dump(cfg, f, indent=4)
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
            with open(self.config_file, 'w') as f:
                json.dump(cfg, f, indent=4)
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
                    with open(self.config_file, 'w') as f:
                        json.dump(cfg, f, indent=4)
                return ''

            new_name = new_data.get('name', '').strip() or connection_name
            if new_name != connection_name and connection_name in conns:
                del conns[connection_name]
            conns[new_name] = new_data
            cfg['ldap_connections'] = conns
            with open(self.config_file, 'w') as f:
                json.dump(cfg, f, indent=4)
            return new_name
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "LDAP Connections", f"Failed to edit LDAP connection: {e}")
            return connection_name

    def _choose_ldap_connection(self, title: str = "Select LDAP Connection"):
        """Choose an LDAP connection with inline Edit/Manage actions.

        Returns ``(name, conns)`` or ``(None, conns)`` when cancelled.
        """
        create_opt = "<Create New LDAP Config...>"
        while True:
            cfg = self._read_config()
            conns = cfg.get('ldap_connections', {})
            if not conns:
                QtWidgets.QMessageBox.information(self, title, "No LDAP connections defined. Please create one first.")
                self.manage_ldap_connections()
                cfg = self._read_config()
                conns = cfg.get('ldap_connections', {})
                if not conns:
                    return None, conns

            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle(title)
            dlg.setModal(True)
            layout = QtWidgets.QVBoxLayout(dlg)
            layout.addWidget(QtWidgets.QLabel("Connection:"))

            combo = QtWidgets.QComboBox()
            names = [create_opt] + list(conns.keys())
            combo.addItems(names)
            layout.addWidget(combo)

            action = {'value': 'ok'}

            action_row = QtWidgets.QHBoxLayout()
            edit_btn = QtWidgets.QPushButton("Edit...")
            manage_btn = QtWidgets.QPushButton("Manage...")
            action_row.addWidget(edit_btn)
            action_row.addWidget(manage_btn)
            action_row.addStretch()
            layout.addLayout(action_row)

            btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            layout.addWidget(btns)

            def _edit_selected():
                action['value'] = 'edit'
                dlg.accept()

            def _manage_all():
                action['value'] = 'manage'
                dlg.accept()

            edit_btn.clicked.connect(_edit_selected)
            manage_btn.clicked.connect(_manage_all)

            if dlg.exec() != QtWidgets.QDialog.Accepted:
                return None, conns

            selected = combo.currentText().strip()
            if action['value'] == 'manage' or selected == create_opt:
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
            self._import_from_ldap_connection(connection_name, conns[connection_name])
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import LDAP", str(e))

    def import_from_ldap_directory(self):
        """Initiate import flow from an LDAP directory."""
        try:
            name, conns = self._choose_ldap_connection("Select LDAP Connection")
            if not name:
                return
            self._import_from_ldap_connection(name, conns[name])
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import LDAP", str(e))

    def _import_from_ldap_connection(self, connection_name: str, conn: dict):
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

        search_filter = conn.get('search_filter', '(objectClass=person)') or '(objectClass=person)'
        try:
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
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import LDAP", f"Failed to read LDAP entries: {e}")
            return

        if not rows:
            QtWidgets.QMessageBox.information(self, "Import LDAP", "No matching LDAP entries were found.")
            return

        sample = rows[0]
        source_fields = sorted([k for k in sample.keys() if k and k.lower() != 'dn'])

        client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
        pops = {}
        try:
            token = asyncio.run(client.get_token())
            if token:
                pops = asyncio.run(client.get_populations())
        except Exception:
            pass

        ping_attrs = self._get_pingone_attributes_for_import(client)
        initial_mapping = conn.get('ldap_import_mapping', {})
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
        if dlg.remember_mapping():
            self._save_ldap_connection_settings(connection_name, {'ldap_import_mapping': mapping})

        users = self._convert_rows_to_users(rows, mapping, client, pops)
        self._set_last_data_source(f"LDAP {connection_name}: {conn.get('base_dn', '')}")
        self._perform_import_sequence(users, client, pops)

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
            export_dlg = ExportOptionsDialog(bool(selected), only_visible_default, prefer_selected, self)
            if export_dlg.exec() != QtWidgets.QDialog.Accepted:
                return
            opts = export_dlg.get_options()

            if opts.get('rows') == 'selected' and selected:
                id_col = self.columns.index('id') if 'id' in self.columns else -1
                if id_col != -1:
                    ids = [self.u_table.item(r.row(), id_col).text() for r in selected]
                    export_users = [u for u in self.users_cache if u.get('id') in ids]
                else:
                    export_users = list(self.users_cache)
            else:
                export_users = list(self.users_cache)

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
                    ldap_attrs = sorted(set(ldap_attrs).union({k for k in sample_entry.keys() if k and k.lower() != 'dn'}))
            except Exception:
                pass

            all_ping_attrs = self._get_pingone_attributes()
            required_ping_attrs = {'username', 'email', 'name.given', 'name.family'}
            visible_ping_attrs = set()
            try:
                for idx, col in enumerate(self.columns or []):
                    if idx < self.u_table.columnCount() and not self.u_table.isColumnHidden(idx):
                        visible_ping_attrs.add(str(col))
            except Exception:
                visible_ping_attrs = set(self.columns or [])
            allowed_ping_attrs = required_ping_attrs.union(visible_ping_attrs)
            ping_attrs = [
                a for a in all_ping_attrs
                if a in allowed_ping_attrs and not str(a).lower().startswith('population.')
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
            rdn_attr = rdn_aliases.get(rdn_attr.lower(), rdn_attr)
            object_classes = conn.get('object_classes') or ['top', 'person', 'organizationalPerson', 'inetOrgPerson']
            entries = []
            skipped = 0
            for user in export_users:
                flat = self._flatten_user(user)
                attrs = {}
                for ping_attr, ldap_attr in mapping.items():
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

            summary = f"Created {result.get('created', 0)}, updated {result.get('updated', 0)} LDAP entries"
            if skipped:
                summary += f"; skipped {skipped} users without {rdn_attr}"
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
            self.status_label.setText(summary)
            try:
                self.statusBar().showMessage(summary)
            except Exception:
                pass
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export LDAP", str(e))

    def import_from_database(self):
        """Initiate import flow from a database table."""
        try:
            cfg = self._read_config()
            dbs = cfg.get('db_connections', {})
            if not dbs:
                QtWidgets.QMessageBox.information(self, "Import DB", "No database connections defined. Please create one first.")
                self.manage_db_connections()
                cfg = self._read_config(); dbs = cfg.get('db_connections', {})
                if not dbs:
                    return
            # let user select connection
            names = list(dbs.keys())
            name, ok = QtWidgets.QInputDialog.getItem(self, "Select Connection", "Connection:", names, editable=False)
            if not ok or not name:
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

            ok, _ = db_utils.test_connection(conn['type'], conn['host'], conn['port'], conn['database'], conn['user'], conn['password'], conn.get('driver'))
            if not ok:
                QtWidgets.QMessageBox.critical(self, "Import DB", "Unable to connect with provided credentials.")
                return
            # fetch columns and sample row
            try:
                if source_mode == "Custom Query":
                    cols = db_utils.get_query_columns(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], query_text, conn.get('driver')
                    )
                    sample = db_utils.get_query_sample(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], query_text, conn.get('driver')
                    )
                else:
                    cols = db_utils.get_table_columns(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], table, conn.get('driver')
                    )
                    sample = db_utils.get_table_sample(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], table, conn.get('driver')
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
                # retrieve rows from the selected table
                try:
                    if source_mode == "Custom Query":
                        rows = db_utils.get_query_rows(
                            conn['type'], conn['host'], conn['port'], conn['database'],
                            conn['user'], conn['password'], query_text, conn.get('driver')
                        )
                        self._set_last_data_source(f"DB {name}: custom query")
                    else:
                        rows = db_utils.get_table_rows(
                            conn['type'], conn['host'], conn['port'], conn['database'],
                            conn['user'], conn['password'], table, conn.get('driver')
                        )
                        self._set_last_data_source(f"DB {name}: {table}")
                except Exception as e:
                    QtWidgets.QMessageBox.critical(self, "Import DB", f"Failed to read table rows: {e}")
                    return
                if not rows:
                    QtWidgets.QMessageBox.information(self, "Import DB", "No rows found in table.")
                    return
                # prepare API client and optional population cache
                pops = {}
                try:
                    token = asyncio.run(client.get_token())
                    if token:
                        pops = asyncio.run(client.get_populations())
                except Exception:
                    pass
                # convert DB rows to PingOne users
                users = self._convert_rows_to_users(rows, mapping, client, pops)
                # run common import sequence
                self._perform_import_sequence(users, client, pops)
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
                conn['user'], conn['password'], conn.get('driver')
            )
            table_names = [t.strip() for t in table_names if str(t).strip()]
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
                conn['user'], conn['password'], conn.get('driver')
            )
            table_names = [t.strip() for t in table_names if str(t).strip()]
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
            with open(self.config_file, 'w') as f:
                json.dump(cfg, f, indent=4)
        except Exception:
            pass

    def _prompt_custom_query_from_connection(self, conn: dict, connection_name: str):
        """Prompt for SQL query and return (query_text, query_saved)."""
        saved_queries = [q for q in (conn.get('saved_custom_queries', []) or []) if str(q).strip()]
        default_query = (conn.get('last_custom_query') or '').strip() or "SELECT * FROM your_table"

        # If queries were previously saved, let the user start from one.
        if saved_queries:
            options = ["<Type new query>"] + saved_queries
            selected, ok = QtWidgets.QInputDialog.getItem(
                self,
                "Saved Custom Queries",
                f"Select a saved query for {connection_name} or choose '<Type new query>':",
                options,
                0,
                False,
            )
            if not ok:
                return "", False
            if selected and selected != "<Type new query>":
                default_query = selected

        query_text, ok = QtWidgets.QInputDialog.getMultiLineText(
            self,
            "Custom Query",
            "Enter SQL query (SELECT):",
            default_query,
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
            attrs.discard('population.id')
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
                conn['user'], conn['password'], conn.get('driver')
            )
            if not ok:
                QtWidgets.QMessageBox.critical(self, "Import DB", "Unable to connect with provided credentials.")
                return
            
            # Fetch columns and convert any dotted names
            try:
                if query_text:
                    cols = db_utils.get_query_columns(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], query_text, conn.get('driver')
                    )
                    sample = db_utils.get_query_sample(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], query_text, conn.get('driver')
                    )
                else:
                    cols = db_utils.get_table_columns(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], table, conn.get('driver')
                    )
                    sample = db_utils.get_table_sample(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], table, conn.get('driver')
                    )
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Import DB", f"Failed to read table metadata: {e}")
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
                
                # Retrieve rows and convert keys
                try:
                    if query_text:
                        rows = db_utils.get_query_rows(
                            conn['type'], conn['host'], conn['port'], conn['database'],
                            conn['user'], conn['password'], query_text, conn.get('driver')
                        )
                        self._set_last_data_source(f"DB {connection_name}: custom query")
                    else:
                        rows = db_utils.get_table_rows(
                            conn['type'], conn['host'], conn['port'], conn['database'],
                            conn['user'], conn['password'], table, conn.get('driver')
                        )
                        self._set_last_data_source(f"DB {connection_name}: {table}")
                except Exception as e:
                    QtWidgets.QMessageBox.critical(self, "Import DB", f"Failed to read table rows: {e}")
                    return
                
                if not rows:
                    QtWidgets.QMessageBox.information(self, "Import DB", "No rows found in table.")
                    return
                
                # Convert row keys to underscore versions
                converted_rows = []
                for row in rows:
                    converted_row = {self._convert_dotted_to_underscore(k): v for k, v in row.items()}
                    converted_rows.append(converted_row)
                
                # Prepare client and import
                pops = {}
                try:
                    token = asyncio.run(client.get_token())
                    if token:
                        pops = asyncio.run(client.get_populations())
                except Exception:
                    token = None
                
                users = self._convert_rows_to_users(converted_rows, mapping, client, pops)
                self._perform_import_sequence(users, client, pops)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Import Error", str(e))

    def export_to_database(self):
        """Initiate export flow to a database table."""
        try:
            cfg = self._read_config()
            dbs = cfg.get('db_connections', {})
            if not dbs:
                QtWidgets.QMessageBox.information(self, "Export DB", "No database connections defined. Please create one first.")
                self.manage_db_connections()
                cfg = self._read_config(); dbs = cfg.get('db_connections', {})
                if not dbs:
                    return
            names = list(dbs.keys())
            name, ok = QtWidgets.QInputDialog.getItem(self, "Select Connection", "Connection:", names, editable=False)
            if not ok or not name:
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

            ok, _ = db_utils.test_connection(conn['type'], conn['host'], conn['port'], conn['database'], conn['user'], conn['password'], conn.get('driver'))
            if not ok:
                QtWidgets.QMessageBox.critical(self, "Export DB", "Unable to connect with provided credentials.")
                return
            # fetch column names if table exists, otherwise use empty list
            cols = []
            try:
                cols = db_utils.get_table_columns(conn['type'], conn['host'], conn['port'], conn['database'], conn['user'], conn['password'], table, conn.get('driver'))
            except Exception:
                cols = []

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
                                conn['user'], conn['password'], table, rename_map, conn.get('driver')
                            )
                            cols = db_utils.get_table_columns(
                                conn['type'], conn['host'], conn['port'], conn['database'],
                                conn['user'], conn['password'], table, conn.get('driver')
                            )
                            QtWidgets.QMessageBox.information(self, "Migrate Legacy Columns", "Column rename migration completed.")
                        except NotImplementedError as e:
                            QtWidgets.QMessageBox.information(self, "Migrate Legacy Columns", str(e))
                        except Exception as e:
                            QtWidgets.QMessageBox.warning(self, "Migrate Legacy Columns", f"Migration failed: {e}")

            ping_attrs = self._get_pingone_attributes()
            sample_p1 = {}
            try:
                selected = self.u_table.selectionModel().selectedRows()
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
            dlg = DatabaseMappingDialog(
                cols or ping_attrs,
                ping_attrs,
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
                if dlg.remember_mapping():
                    self._save_db_connection_settings(name, {'db_export_mapping': mapping})
                effective_mapping = dict(mapping)
                renamed_columns = {}
                # When creating a new table, normalize invalid SQL identifiers.
                if not cols:
                    effective_mapping = {}
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
                # compute list of users to export
                if not self.users_cache:
                    QtWidgets.QMessageBox.information(self, "Export DB", "No users to export.")
                    return
                selected = self.u_table.selectionModel().selectedRows()
                if selected:
                    id_col = self.columns.index('id') if 'id' in self.columns else -1
                    if id_col != -1:
                        ids = [self.u_table.item(r.row(), id_col).text() for r in selected]
                        export_users = [u for u in self.users_cache if u.get('id') in ids]
                    else:
                        export_users = list(self.users_cache)
                else:
                    export_users = list(self.users_cache)
                # build rows for insertion based on mapping
                rows = []
                for u in export_users:
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
                # ensure table exists and insert
                try:
                    db_utils.create_table_if_not_exists(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], table, list(effective_mapping.values()), conn.get('driver')
                    )
                    db_utils.insert_rows(
                        conn['type'], conn['host'], conn['port'], conn['database'],
                        conn['user'], conn['password'], table, rows, conn.get('driver')
                    )
                    QtWidgets.QMessageBox.information(self, "Export DB", f"Exported {len(rows)} users to table {table}.")
                except Exception as e:
                    QtWidgets.QMessageBox.critical(self, "Export DB", f"Export failed: {e}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export DB", str(e))

    def _get_pingone_attributes(self) -> list:
        """Return schema-informed PingOne attribute names for mapping dialogs."""
        attrs = set()

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
            'username', 'email', 'name.given', 'name.family',
            'population.id', 'population.name',
            'phoneNumbers.mobile', 'phoneNumbers.work', 'phoneNumbers.home',
            'title', 'organization', 'enabled', 'id',
        }
        attrs.update(extras)
        return sorted(attrs)

    def connect_only(self):
        """Attempt to obtain a token using the UI credentials and log success/failure."""
        client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
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
                self.statusBar().showMessage("Connected")
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
                with open(self.config_file, 'w') as f:
                    json.dump(cfg, f, indent=4)
            except Exception:
                pass
        else:
            QtWidgets.QMessageBox.critical(self, "Connect", "Auth Failed. Check credentials.")
            try:
                api_client.write_connection_log(f"Connect failed for env={client.env_id}, client_id={client.client_id}")
            except Exception:
                pass
            self.status_label.setText("Connection failed")
            try:
                self.statusBar().showMessage("Connection failed")
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
                with open(self.config_file, 'w') as f:
                    json.dump(p, f, indent=4)
                try:
                    keyring.delete_password("pingone_usermanager", name)
                except Exception:
                    pass
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
                with open(self.config_file, 'w') as f:
                    json.dump(cfg, f, indent=4)
                
                # Save credentials to keyring
                import keyring
                env_id, client_id, secret = new_credentials
                try:
                    if secret:
                        keyring.set_password("pingone_usermanager", new_profile, secret)
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
                    self.load_selected_profile()
                
                # Test the connection synchronously
                client = api_client.PingOneClient(env_id, client_id, secret)
                err = None
                try:
                    token = asyncio.run(client.get_token())
                    if token:
                        # Update status
                        self.status_label.setText(f"Connected to profile '{new_profile}'")
                        try:
                            self.statusBar().showMessage(f"Connected to profile '{new_profile}'")
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
                with open(self.config_file, 'w') as f:
                    json.dump(cfg, f, indent=4)
                
                # Save credentials to keyring if provided
                if new_profile and new_credentials:
                    import keyring
                    env_id, client_id, secret = new_credentials
                    try:
                        if secret:
                            keyring.set_password("pingone_usermanager", new_profile, secret)
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
                            self.load_selected_profile()
                    except Exception:
                        pass
                
                # Build status message
                msg_parts = []
                if deleted:
                    msg_parts.append(f"Deleted {len(deleted)} profile(s)")
                if new_profile:
                    msg_parts.append(f"Created profile '{new_profile}'")
                
                msg = "; ".join(msg_parts)
                self.status_label.setText(msg)
                try:
                    self.statusBar().showMessage(msg)
                except Exception:
                    pass
            
            # Clean up keyring entries for deleted profiles
            if deleted:
                import keyring
                for profile_name in deleted:
                    try:
                        keyring.delete_password("pingone_usermanager", profile_name)
                    except Exception:
                        pass
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
        self.status_label.setText(msg)
        try:
            self.statusBar().showMessage(msg)
        except Exception:
            pass

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

    def delete_selected_users(self):
        rows = self.u_table.selectionModel().selectedRows()
        if not rows: return
        id_col = self.columns.index('id') if 'id' in self.columns else -1
        if id_col == -1: return
        uids = [self.u_table.item(r.row(), id_col).text() for r in rows]
        if QtWidgets.QMessageBox.question(self, "Delete", f"Delete {len(uids)} users?") == QtWidgets.QMessageBox.Yes:
            client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
            self.prog.show()
            w = BulkDeleteWorker(client, uids)
            w.signals.finished.connect(lambda r: (self.prog.hide(), self.refresh_users()))
            self.threadpool.start(w)

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
            self.status_label.setText(msg)
            try:
                self.statusBar().showMessage(msg)
            except Exception:
                pass
        else:
            api_client.api_logger.info(f"API Logging disabled at {datetime.now()}")
            msg = "API logging disabled"
            self.status_label.setText(msg)
            try:
                self.statusBar().showMessage(msg)
            except Exception:
                pass

    def toggle_credentials_logging(self):
        """Enable/disable credential event logging to credentials.log."""
        enabled = self.enable_credentials_logging_action.isChecked()
        try:
            api_client.set_credentials_logging(enabled)
            msg = "Credentials logging enabled" if enabled else "Credentials logging disabled"
            self.status_label.setText(msg)
            try:
                self.statusBar().showMessage(msg)
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
            self.status_label.setText(f"{title} set to {lvl}")
            try:
                self.statusBar().showMessage(f"{title} set to {lvl}")
            except Exception:
                pass
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Logging", f"Failed to set log level: {e}")

    def _show_log_viewer(self, title: str, path: Path, log_kind: str):
        """Show a log viewer with Set Level, Reset, and Save commands."""
        p = Path(path)
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(title)
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

        te = QtWidgets.QTextEdit()
        te.setReadOnly(True)
        lay.addWidget(te)

        def refresh_text():
            try:
                if p.exists():
                    te.setPlainText(p.read_text(encoding='utf-8', errors='replace'))
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
        close_btn.clicked.connect(dlg.accept)

        refresh_text()
        dlg.resize(980, 520)
        dlg.exec()

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

    def show_api_capture_dialog(self):
        """Open a dialog to start/stop a live API-capture session and view events."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("API Capture")
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
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row); lay.addWidget(te)

        timer = QtCore.QTimer(dlg)
        timer.setInterval(500)

        def poll_events():
            try:
                events = api_client.get_and_clear_live_events()
                if events:
                    te.moveCursor(QtGui.QTextCursor.End)
                    te.insertPlainText("\n".join(events) + "\n")
                    te.moveCursor(QtGui.QTextCursor.End)
            except Exception:
                pass

        timer.timeout.connect(poll_events)

        def start():
            api_client.enable_live_capture(True)
            # enable API logging to ensure calls are recorded
            self.enable_api_logging_action.setChecked(True)
            api_client.set_api_logging(True)
            start_btn.setEnabled(False); stop_btn.setEnabled(True)
            te.clear(); timer.start()

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
            te.clear()

        def set_level():
            self._prompt_set_log_level("api")

        start_btn.clicked.connect(start)
        stop_btn.clicked.connect(stop)
        set_level_btn.clicked.connect(set_level)
        reset_btn.clicked.connect(reset_capture)
        save_btn.clicked.connect(save)
        close_btn.clicked.connect(lambda: (stop(), dlg.accept()))

        dlg.resize(900, 400)
        dlg.exec()

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
            self.status_label.setText("Credentials valid")
            try:
                self.statusBar().showMessage("Credentials valid")
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
            self.status_label.setText("Credentials invalid")
            try:
                self.statusBar().showMessage("Credentials invalid")
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
                keyring.set_password("pingone_usermanager", name, self.cl_sec.text())
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
        self.status_label.setText(msg)
        try:
            self.statusBar().showMessage(msg)
        except Exception:
            pass

    def toggle_local_schema(self):
        enabled = self.use_local_schema_action.isChecked()
        if enabled:
            self.use_server_dryrun_action.setChecked(False)
        msg = "Validation: Local schema" if enabled else "Validation: none"
        self.status_label.setText(msg)
        try:
            self.statusBar().showMessage(msg)
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
            self.status_label.setText(msg)
            try:
                self.statusBar().showMessage(msg)
            except Exception:
                pass

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
        self.status_label.setText(msg)
        try:
            self.statusBar().showMessage(msg)
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
                               fixed_pop_id=None, fixed_enabled=None) -> list:
        """Apply a column-to-attribute mapping to a list of row dicts.

        Returns a list of PingOne user dicts suitable for import.  This logic is
        essentially the same as the CSV import path but operates on an already-
        populated ``rows`` list instead of reading from a file.
        ``mapping`` should map source column names to PingOne attribute names.
        """
        users = []
        for row in rows:
            flat = {}
            phone_by_type = {}

            for src_key, target in mapping.items():
                source_name = src_key
                source_phone_type = None
                if isinstance(src_key, str) and '::' in src_key:
                    source_name, source_phone_type = src_key.split('::', 1)

                v = row.get(source_name)
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
            # apply fixed enabled setting if provided
            if fixed_enabled is not None:
                user['enabled'] = bool(fixed_enabled)
            users.append(user)
        # Normalize population values: convert names to IDs where possible
        try:
            if not pops:
                pops = asyncio.run(client.get_populations())
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

    def _perform_import_sequence(self, users: list, client, pops: dict = None,
                                 fixed_pop_id=None, fixed_enabled=None):
        """Common logic used by both CSV and database import flows.

        ``users`` should be a list of pre-processed user dicts (i.e. the output
        of ``_convert_rows_to_users`` or the CSV reader loop).  This method
        handles credential validation, pre-checks, local validation, and kicking
        off the background worker.
        """
        if not users:
            QtWidgets.QMessageBox.information(self, "Import", "No users to import.")
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
        for uu in users:
            try:
                self._remove_empty_keys(uu)
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
        self.prog.show(); self.prog.setRange(0, len(create_users) if create_users else (len(update_pairs) or 0))
        # Map population names to IDs if provided in CSV or apply fixed population
        try:
            if not pops:
                pops = asyncio.run(client.get_populations())
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
        w = BulkCreateWorker(client, users)
        w.signals.progress.connect(lambda cur, tot: self.prog.setValue(cur))
        w.signals.status.connect(lambda msg: (self.status_label.setText(msg), self.statusBar().showMessage(msg)))
        def on_done(res):
            self.prog.hide()
            created = res.get('created', 0)
            updated_on_retry = res.get('updated_on_retry', 0)
            total = res.get('total', 0)
            errors = res.get('errors', []) or []
            summary = f"Created {created}/{total} users"
            if updated_on_retry:
                summary += f"; Updated on retry {updated_on_retry}"
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
        w.signals.error.connect(lambda m: (self.prog.hide(), QtWidgets.QMessageBox.critical(self, "Import Error", m)))
        self.threadpool.start(w)
        msg = f"Import started: {len(users)} users"
        self.status_label.setText(msg)
        try:
            self.statusBar().showMessage(msg)
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
            user[col_name] = new_data
            client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
            # Spawn a UserUpdateWorker to perform the API PUT off the UI
            # thread; the worker will refresh the UI upon success.
            self.prog.show()
            worker = UserUpdateWorker(client, user_id, user)
            worker.signals.finished.connect(lambda r: (self.prog.hide(), self.refresh_users()))
            worker.signals.error.connect(lambda m: (self.prog.hide(), QtWidgets.QMessageBox.critical(self, "Error", m)))
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
            self.status_label.setText(msg)
            try:
                self.statusBar().showMessage(msg)
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
        dlg = ExportOptionsDialog(bool(selected), only_visible_default, prefer_selected, self)
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
                with open(self.config_file, 'w') as f:
                    json.dump(cfg, f, indent=4)
            except Exception:
                pass

        # choose columns
        if opts.get('only_visible_columns'):
            cols = self.columns or self.selected_columns
        else:
            cols = sorted(self.all_columns)

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

            import csv
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                for row in self._rows_from_users(export_users, cols):
                    writer.writerow([str(v) for v in row])
            self._set_last_data_source(f"File {path}")
            msg = f"Exported {len(export_users)} users to {path}"
            self.status_label.setText(msg)
            try:
                self.statusBar().showMessage(msg)
            except Exception:
                pass
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
        dlg = ExportOptionsDialog(bool(selected), only_visible_default, prefer_selected, self)
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
                with open(self.config_file, 'w') as f:
                    json.dump(cfg, f, indent=4)
            except Exception:
                pass

        if opts.get('only_visible_columns'):
            cols_check = self.columns or self.selected_columns
        else:
            cols_check = sorted(self.all_columns)

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

            with open(path, 'w', encoding='utf-8') as f:
                for u in export_users:
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
            self._set_last_data_source(f"File {path}")
            msg = f"Exported {len(export_users)} users to {path}"
            self.status_label.setText(msg)
            try:
                self.statusBar().showMessage(msg)
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
                    pops = asyncio.run(client.get_populations())
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

            map_dialog = AttributeMappingDialog(headers, self, pop_map=pops,
                                               initial_mapping=initial_mapping,
                                               initial_fixed_pop_id=initial_fixed,
                                               initial_fixed_enabled=initial_enabled,
                                               pingone_attrs=self._get_pingone_attributes(),
                                               sample_row=(raw_rows[0] if raw_rows else None))
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
                    with open(self.config_file, 'w') as f:
                        json.dump(cfg, f, indent=4)
            except Exception:
                pass

            # convert rows into users via shared helper
            users = self._convert_rows_to_users(raw_rows, mapping, client, pops,
                                                fixed_pop_id, fixed_enabled)
            # hand off to common import logic
            self._perform_import_sequence(users, client, pops, fixed_pop_id, fixed_enabled)
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
            # Show attribute mapping dialog using a synthetic header list
            # derived from the first entry's keys (hyphens converted to dots)
            first_flat_keys = []
            first_sample = {}
            if entries:
                first = entries[0]
                for line in first.splitlines():
                    if not line or ':' not in line:
                        continue
                    key = line.split(':', 1)[0].strip()
                    val = line.split(':', 1)[1].strip()
                    if '-' in key and '.' not in key:
                        key = key.replace('-', '.')
                    first_flat_keys.append(key)
                    if key.lower() != 'dn' and key not in first_sample:
                        first_sample[key] = val
            # Create API client early to fetch populations for mapping UI
            client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
            pops = {}
            try:
                token = asyncio.run(client.get_token())
                if token:
                    pops = asyncio.run(client.get_populations())
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
            map_dialog = AttributeMappingDialog(
                first_flat_keys,
                self,
                pop_map=pops,
                initial_mapping=initial_mapping,
                initial_fixed_pop_id=initial_fixed,
                initial_fixed_enabled=initial_enabled,
                pingone_attrs=self._get_pingone_attributes(),
                sample_row=first_sample,
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
                    with open(self.config_file, 'w') as f:
                        json.dump(cfg, f, indent=4)
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
                    pops = asyncio.run(client.get_populations())
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
                        pops = asyncio.run(client.get_populations())
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
                    w.signals.status.connect(lambda msg: (self.status_label.setText(msg), self.statusBar().showMessage(msg)))

                    def on_done(res):
                        created = res.get('created', 0)
                        updated_on_retry = res.get('updated_on_retry', 0)
                        total = res.get('total', 0)
                        errors = res.get('errors', []) or []

                        def _on_updates_done(res2):
                            self.prog.hide()
                            updated = res2.get('updated', 0)
                            total_upd = res2.get('total', 0)
                            upd_errors = res2.get('errors', []) or []
                            result_msg = f"Created {created}/{total} users"
                            if updated_on_retry:
                                result_msg += f"; Updated on retry {updated_on_retry}"
                            result_msg += f"; Updated {updated}/{total_upd} users"
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
                            self.prog.setRange(0, len(update_pairs))
                            upd_w = BulkUpdateWorker(client, update_pairs)
                            upd_w.signals.progress.connect(lambda cur, tot: self.prog.setValue(cur))
                            upd_w.signals.finished.connect(_on_updates_done)
                            upd_w.signals.error.connect(lambda m: (self.prog.hide(), QtWidgets.QMessageBox.critical(self, "Update Error", m)))
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
                        self.prog.setRange(0, len(update_pairs))
                        upd_w = BulkUpdateWorker(client, update_pairs)
                        upd_w.signals.progress.connect(lambda cur, tot: self.prog.setValue(cur))

                        def _on_updates_done2(res):
                            self.prog.hide()
                            updated = res.get('updated', 0)
                            total_upd = res.get('total', 0)
                            upd_errors = res.get('errors', []) or []
                            result_msg = f"Updated {updated}/{total_upd} users"
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
                self.status_label.setText(msg)
                try:
                    self.statusBar().showMessage(msg)
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
            self.status_label.setText(msg)
            try:
                self.statusBar().showMessage(msg, 4000)
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
            with open(self.config_file, 'w') as f:
                json.dump(p, f, indent=4)
            if show_notification:
                msg = f"Column layout saved for profile '{name}'"
                self.status_label.setText(msg)
                try:
                    self.statusBar().showMessage(msg, 3000)
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
        # Only open editor when double-clicking the UUID or username columns
        if col_name in ('id', 'username'):
            self.u_table.selectRow(row)
            self.edit_user()
            return
        elif col_name == 'email':
            email = item.text()
            url = f"mailto:{email}"
            if QtWidgets.QMessageBox.question(self, "Open Email", f"Compose email to {email}?") == QtWidgets.QMessageBox.Yes:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))
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
        self.status_label.setText(msg)
        try:
            self.statusBar().showMessage(msg)
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
