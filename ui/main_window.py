import json
from pathlib import Path
from datetime import datetime
import asyncio
import functools
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
from workers import UserFetchWorker, BulkDeleteWorker, UserUpdateWorker, BulkCreateWorker
from ui.dialogs import EditUserDialog, ColumnSelectDialog, JSONViewDialog, AttributeMappingDialog

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

APP_NAME = "UserManager"
APP_VERSION = "0.52"


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

4. Click "Save Profile" to persist the credentials and settings.

5. Click "Connect & Sync" to authenticate and fetch users from PingOne.

Profile Settings:
- Credentials (Env ID, Client ID, Secret) are saved per-profile.
- Column selection and order are saved per-profile.
- Import/export preferences are saved per-profile when "Remember" is checked.
- The last active profile can auto-connect on startup (see Settings menu).

Status Bar:
- Shows live API call summaries when "Show API calls in status bar" is enabled.
- Displays connection status and recent operation results.
- API call logging can be toggled from the Settings menu.

See the User Management help for information about working with users.
"""

HELP_USER = """
User Management Tab Help:

Viewing Users:
- The table displays users with selected columns (UUID, username, name, etc.).
- Click "Refresh" to reload users from PingOne.
- Use "Columns" to select which attributes to display.
- Column selection and order are saved per-profile.

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
- Usernames are normalized (whitespace trimmed, case-insensitive comparison).
- If a username already exists on the server, the import updates that user instead of creating a duplicate.
- Local JSON Schema validation is performed if jsonschema is installed and user_schema.json exists.

Exporting Users:
- Click "Export CSV" or "Export LDIF" to save users.
- Choose to export all users or selected rows only.
- Choose to export all columns or only visible columns.
- Check "Remember these choices" to save export preferences per-profile.

Deleting Users:
- Select one or more rows and click "Delete Selected" or use the context menu.
- A confirmation dialog will appear before deletion.
- Progress is shown for bulk deletions.

Logs Menu:
- "Show Log Files" displays connection and API logs in a dialog.
- "Reset Log" clears an individual log file.
- "Clear All Logs" empties all log files at once.
- "Archive Logs" creates a timestamped .zip archive of all logs, with optional rotation (truncate originals after archiving).
"""


class MainWindow(QtWidgets.QMainWindow):
    """Main application window for UserManager.

    Responsibilities:
    - Build and manage the configuration and user-management tabs
    - Start background workers and update UI when they complete
    - Provide helper methods for dialogs to trigger API updates
    - Surface connection logs and toggle API logging at runtime
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - v{APP_VERSION}")
        
        # Set DPI-aware minimum window size
        try:
            screen = QtWidgets.QApplication.primaryScreen()
            if screen:
                dpi_scale = screen.devicePixelRatio()
                min_width = int(1200 * max(1.0, dpi_scale * 0.8))
                min_height = int(800 * max(1.0, dpi_scale * 0.8))
                self.setMinimumSize(min_width, min_height)
            else:
                self.setMinimumSize(1200, 800)
        except Exception:
            self.setMinimumSize(1200, 800)
        
        self.threadpool = QtCore.QThreadPool()
        self.config_file, self.users_cache, self.pop_map = Path("profiles.json"), [], {}
        self.columns = []
        # Default column order: UUID first, then username, first name,
        # last name, and population. This matches the requested default
        # and ensures the UUID is always visible as the left-most column.
        self.default_columns = ['id', 'username', 'name.given', 'name.family', 'population.name']
        self.selected_columns = self.default_columns.copy()
        self.all_columns = set()
        self.json_editing_enabled = False
        self.use_friendly_names = True
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

    def init_ui(self):
        # Build the main UI widgets and wire actions to slots.
        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Menu Bar
        menubar = self.menuBar()
        # On macOS, use the native menu bar
        if IS_MACOS:
            menubar.setNativeMenuBar(True)
        
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
        # Credentials logging settings
        self.enable_credentials_logging_action = settings_menu.addAction("Enable Credentials Logging")
        self.enable_credentials_logging_action.setCheckable(True)
        self.enable_credentials_logging_action.setChecked(True)
        self.enable_credentials_logging_action.triggered.connect(self.toggle_credentials_logging)
        self.credentials_log_level_action = settings_menu.addAction("Credentials Log Level...")
        self.credentials_log_level_action.triggered.connect(self.set_credentials_log_level)
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

        # Separate Logs submenu for quick actions (reset, clear, archive)
        logs_menu = menubar.addMenu("Logs")
        self.logs_show_action = logs_menu.addAction("Show Log Files...")
        self.logs_show_action.triggered.connect(self.show_log_files)
        self.logs_reset_api = logs_menu.addAction("Reset API Calls Log")
        self.logs_reset_api.triggered.connect(lambda: self.reset_log_file(getattr(api_client, 'LOG_FILE', Path('api_calls.log'))))
        self.logs_reset_conn = logs_menu.addAction("Reset Connection Log")
        self.logs_reset_conn.triggered.connect(lambda: self.reset_log_file(getattr(api_client, 'CONNECTION_LOG', Path('connection_errors.log'))))
        self.logs_reset_creds = logs_menu.addAction("Reset Credentials Log")
        self.logs_reset_creds.triggered.connect(lambda: self.reset_log_file(getattr(api_client, 'CREDENTIALS_LOG', Path('credentials.log'))))
        logs_menu.addSeparator()
        self.logs_clear_all = logs_menu.addAction("Clear All Logs")
        self.logs_clear_all.triggered.connect(self.clear_all_logs)
        self.logs_archive = logs_menu.addAction("Archive Logs...")
        self.logs_archive.triggered.connect(self.archive_logs)
        
        # File menu for quit action (standard on all platforms)
        file_menu = menubar.addMenu("File")
        quit_action = file_menu.addAction("Quit")
        quit_action.triggered.connect(self.close)
        quit_action.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_Q))
        quit_action.setToolTip(f"Quit application ({'Cmd' if IS_MACOS else 'Ctrl'}+Q)")
        if IS_MACOS:
            # On macOS, the quit action should have the QuitRole to appear in app menu
            quit_action.setMenuRole(QtGui.QAction.MenuRole.QuitRole)
        
        help_menu = menubar.addMenu("Help")
        config_help_action = help_menu.addAction("Configuration Help")
        config_help_action.triggered.connect(self.show_config_help)
        user_help_action = help_menu.addAction("User Management Help")
        user_help_action.triggered.connect(self.show_user_help)
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

        btn_save = QtWidgets.QPushButton("Save Profile")
        btn_save.clicked.connect(self.save_current_profile)
        btn_save.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_P))
        btn_save.setToolTip(f"Save profile ({'Cmd' if IS_MACOS else 'Ctrl'}+P)")
        
        btn_sync = QtWidgets.QPushButton("Connect")
        btn_sync.clicked.connect(self.connect_only)
        btn_sync.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_N))
        btn_sync.setToolTip(f"Connect to PingOne ({'Cmd' if IS_MACOS else 'Ctrl'}+N)")
        
        btn_test = QtWidgets.QPushButton("Test Credentials")
        btn_test.clicked.connect(self.test_credentials)
        btn_test.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_T))
        btn_test.setToolTip(f"Test credentials ({'Cmd' if IS_MACOS else 'Ctrl'}+T)")
        
        btn_delete = QtWidgets.QPushButton("Delete Profile")
        btn_delete.clicked.connect(self.delete_current_profile)
        # Swap Test Credentials and Save Profile positions per request
        cred_form.addRow("Env ID:", self.env_id); cred_form.addRow("Client ID:", self.cl_id)
        cred_form.addRow("Secret:", secret_widget); cred_form.addRow(btn_test); cred_form.addRow(btn_save); cred_form.addRow(btn_sync); cred_form.addRow(btn_delete)
        # Button to view connection log
        self._view_conn_log_btn = QtWidgets.QPushButton("View Connection Log")
        self._view_conn_log_btn.clicked.connect(self.view_connection_log)
        cred_form.addRow(self._view_conn_log_btn)
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
        btn_reload = QtWidgets.QPushButton("🔄 Refresh"); btn_reload.clicked.connect(self.refresh_users)
        btn_reload.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_R))
        btn_reload.setToolTip(f"Refresh user list ({'Cmd' if IS_MACOS else 'Ctrl'}+R)")
        
        btn_del = QtWidgets.QPushButton("🗑 Delete Selected")
        btn_del.setStyleSheet("background-color: #d9534f; color: white;")
        btn_del.clicked.connect(self.delete_selected_users)
        # Delete key works on Windows/Linux, Backspace on macOS is more common
        if IS_MACOS:
            btn_del.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Backspace))
            btn_del.setToolTip("Delete selected users (Backspace)")
        else:
            btn_del.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Delete))
            btn_del.setToolTip("Delete selected users (Delete)")
        
        self.search_bar = QtWidgets.QLineEdit(); self.search_bar.setPlaceholderText("Filter...")
        self.search_bar.textChanged.connect(self.filter_table)
        # Create a shortcut to focus the search bar (QLineEdit doesn't have setShortcut method)
        search_shortcut = QtGui.QShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_L), self)
        search_shortcut.activated.connect(self.search_bar.setFocus)
        self.search_bar.setToolTip(f"Focus filter field ({'Cmd' if IS_MACOS else 'Ctrl'}+L)")
        
        toolbar.addWidget(btn_reload); toolbar.addWidget(btn_del); toolbar.addWidget(self.search_bar)
        btn_import_csv = QtWidgets.QPushButton("Import CSV")
        btn_import_csv.clicked.connect(self.import_from_csv)
        btn_import_csv.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_I))
        btn_import_csv.setToolTip(f"Import from CSV ({'Cmd' if IS_MACOS else 'Ctrl'}+I)")
        
        btn_import_ldif = QtWidgets.QPushButton("Import LDIF")
        btn_import_ldif.clicked.connect(self.import_from_ldif)
        btn_import_ldif.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_Shift | QtCore.Qt.Key.Key_I))
        btn_import_ldif.setToolTip(f"Import from LDIF ({'Cmd' if IS_MACOS else 'Ctrl'}+Shift+I)")
        
        btn_export_csv = QtWidgets.QPushButton("Export CSV")
        btn_export_csv.clicked.connect(self.export_to_csv)
        btn_export_csv.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_E))
        btn_export_csv.setToolTip(f"Export to CSV ({'Cmd' if IS_MACOS else 'Ctrl'}+E)")
        
        btn_export_ldif = QtWidgets.QPushButton("Export LDIF")
        btn_export_ldif.clicked.connect(self.export_to_ldif)
        btn_export_ldif.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_Shift | QtCore.Qt.Key.Key_E))
        btn_export_ldif.setToolTip(f"Export to LDIF ({'Cmd' if IS_MACOS else 'Ctrl'}+Shift+E)")
        
        toolbar.addWidget(btn_import_csv); toolbar.addWidget(btn_import_ldif)
        toolbar.addWidget(btn_export_csv); toolbar.addWidget(btn_export_ldif)
        btn_columns = QtWidgets.QPushButton("Columns")
        btn_columns.clicked.connect(self.select_columns)
        btn_columns.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_K))
        btn_columns.setToolTip(f"Select columns ({'Cmd' if IS_MACOS else 'Ctrl'}+K)")
        
        toolbar.addWidget(btn_columns)
        btn_save_layout = QtWidgets.QPushButton("Save Layout")
        btn_save_layout.clicked.connect(self.save_columns_to_config)
        btn_save_layout.setShortcut(QtGui.QKeySequence(SHORTCUT_MODIFIER | QtCore.Qt.Key.Key_S))
        btn_save_layout.setToolTip(f"Save column layout ({'Cmd' if IS_MACOS else 'Ctrl'}+S)")
        
        toolbar.addWidget(btn_save_layout)
        
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
        user_lay.addWidget(self.status_label)
        user_lay.addWidget(self.api_calls_label)
        sb = QtWidgets.QStatusBar()
        self.setStatusBar(sb)
        # Mirror initial status and add API calls label as a permanent widget
        try:
            self.statusBar().showMessage(self.status_label.text())
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

    # --- Profile Methods ---
    def _read_config(self):
        if self.config_file.exists():
            with open(self.config_file, 'r') as f: return json.load(f)
        return {}

    def load_profiles_from_disk(self):
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
        except Exception:
            pass
        if self.profile_list.count() > 0:
            # If auto-connect is enabled and there is a last working profile, select it
            try:
                meta = cfg.get('__meta__', {})
                last = meta.get('last_working_profile')
                if last and last in profile_names and self.auto_connect_cb.isChecked():
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
            self.cl_sec.setText(keyring.get_password("PingOneUM", name) or "")
            self.selected_columns = p[name].get("columns", self.default_columns.copy())
            self.column_widths = p[name].get("column_widths", {})
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
                msg = f"Profile loaded: {name}"
                self.status_label.setText(msg)
                try:
                    self.statusBar().showMessage(msg)
                except Exception:
                    pass
            except Exception:
                pass

    def save_current_profile(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "Save Profile", "Name:")
        if ok and name:
            p = self._read_config(); p[name] = {"env_id": self.env_id.text(), "cl_id": self.cl_id.text()}
            p[name]["columns"] = self.selected_columns
            p[name]["column_widths"] = self.column_widths
            # Save per-profile UI options
            p[name]['status_show_api_calls'] = bool(getattr(self, 'show_api_calls_cb', QtWidgets.QCheckBox()).isChecked())
            with open(self.config_file, 'w') as f: json.dump(p, f, indent=4)
            keyring.set_password("PingOneUM", name, self.cl_sec.text()); self.load_profiles_from_disk()

    def save_app_settings(self):
        """Persist app-level settings (auto-connect) to config file under __meta__."""
        try:
            cfg = self._read_config()
            meta = cfg.get('__meta__', {})
            meta['auto_connect_last'] = bool(self.auto_connect_cb.isChecked())
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
            with open(self.config_file, 'w') as f:
                json.dump(cfg, f, indent=4)
        except Exception:
            pass

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
        # Create an API client using current UI credentials and start the
        # UserFetchWorker in the shared threadpool so the UI stays responsive.
        client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
        self.prog.show(); self.prog.setRange(0, 0)
        worker = UserFetchWorker(client)
        worker.signals.finished.connect(self.on_fetch_success)
        worker.signals.error.connect(self.on_connection_error)
        QtCore.QThreadPool.globalInstance().start(worker)

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
                    keyring.delete_password("PingOneUM", name)
                except Exception:
                    pass
                self.load_profiles_from_disk()
                self.status_label.setText(f"Deleted profile {name}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Delete Profile", f"Failed to delete profile: {e}")
        else:
            QtWidgets.QMessageBox.information(self, "Delete Profile", "Profile not found.")

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
        # Discover all available columns from the fetched users.
        self.columns = [c for c in self.selected_columns if c in self.all_columns]

        # Append any newly discovered columns to the end of the
        # selected list. This preserves the order of existing columns
        # and places new attributes at the end by default.
        for col in self.all_columns:
            if col not in self.selected_columns:
                self.selected_columns.append(col)

        # Build the final displayed columns by keeping selected order
        # but filtering out any columns that aren't present in this dataset.
        self.columns = [c for c in self.selected_columns if c in self.all_columns]
        # Persist the (possibly extended) selected order to the profile.
        self.save_columns_to_config()
        self.u_table.setColumnCount(len(self.columns))
        self.u_table.setHorizontalHeaderLabels(self._get_column_labels())
        
        self.u_table.setRowCount(0)
        for u in self.users_cache:
            r = self.u_table.rowCount(); self.u_table.insertRow(r)
            for c, col in enumerate(self.columns):
                value = self._get_value(u, col)
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setData(QtCore.Qt.UserRole, value)
                self.u_table.setItem(r, c, item)
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
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        lvl, ok = QtWidgets.QInputDialog.getItem(self, "Credentials Log Level", "Level:", levels, 1, False)
        if ok and lvl:
            try:
                api_client.set_credentials_log_level(lvl)
                self.status_label.setText(f"Credentials log level set to {lvl}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Logging", f"Failed to set log level: {e}")

    def show_log_files(self):
        """Display a small dialog listing the log files and allow opening them."""
        logs = [
            ("API Calls Log", getattr(api_client, 'LOG_FILE', Path('api_calls.log'))),
            ("Connection Log", getattr(api_client, 'CONNECTION_LOG', Path('connection_errors.log'))),
            ("Credentials Log", getattr(api_client, 'CREDENTIALS_LOG', Path('credentials.log'))),
        ]
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Log Files")
        lay = QtWidgets.QVBoxLayout(dlg)
        for label, p in logs:
            try:
                pth = p.resolve()
            except Exception:
                pth = p
            row = QtWidgets.QHBoxLayout()
            lbl = QtWidgets.QLabel(f"{label}:")
            val = QtWidgets.QLineEdit(str(pth))
            val.setReadOnly(True)
            btn = QtWidgets.QPushButton("Open")
            def _open(path):
                try:
                    QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))
                except Exception:
                    pass
            btn.clicked.connect(functools.partial(_open, pth))
            reset_btn = QtWidgets.QPushButton("Reset")
            def _reset(path):
                try:
                    if QtWidgets.QMessageBox.question(self, "Reset Log", f"Truncate {path}? This cannot be undone.") != QtWidgets.QMessageBox.Yes:
                        return
                    with open(path, 'w', encoding='utf-8'):
                        pass
                    QtWidgets.QMessageBox.information(self, "Reset Log", f"Truncated {path}")
                except Exception as e:
                    QtWidgets.QMessageBox.warning(self, "Reset Log", f"Failed to truncate {path}: {e}")
            reset_btn.clicked.connect(functools.partial(_reset, pth))
            row.addWidget(lbl); row.addWidget(val); row.addWidget(btn)
            row.addWidget(reset_btn)
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
        save_btn = QtWidgets.QPushButton("Save...")
        close_btn = QtWidgets.QPushButton("Close")
        btn_row.addWidget(start_btn); btn_row.addWidget(stop_btn); btn_row.addWidget(save_btn); btn_row.addStretch(); btn_row.addWidget(close_btn)
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

        start_btn.clicked.connect(start)
        stop_btn.clicked.connect(stop)
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
        """Attempt to obtain a token using provided credentials and report result."""
        client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
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
            QtWidgets.QMessageBox.critical(self, "Test Credentials", "Auth Failed. Check credentials.")
            try:
                api_client.credential_logger.error(f"Test credentials failed: env={client.env_id}, client_id={client.client_id}")
            except Exception:
                pass
            self.status_label.setText("Credentials invalid")
            try:
                self.statusBar().showMessage("Credentials invalid")
            except Exception:
                pass

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

    def show_config_help(self):
        QtWidgets.QMessageBox.information(self, "Configuration Help", HELP_CONFIG)

    def show_user_help(self):
        QtWidgets.QMessageBox.information(self, "User Management Help", HELP_USER)

    def show_full_help(self):
        """Show comprehensive help covering all UI options and configuration."""
        combined = f"{HELP_CONFIG}\n\n{HELP_USER}"
        QtWidgets.QMessageBox.information(self, "Full Help & Options", combined)

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
        QtWidgets.QMessageBox.information(self, "Tabs Overview", tabs_text)

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
        dialog = ColumnSelectDialog(self.all_columns, self.selected_columns, self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            self.selected_columns = dialog.get_selected()
            self.save_columns_to_config()
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
        try:
            import csv as _csv
            users = []
            with open(path, 'r', encoding='utf-8') as f:
                reader = _csv.DictReader(f)
                headers = reader.fieldnames or []
                # Create a client early so we can fetch populations for the mapping UI
                client = api_client.PingOneClient(self.env_id.text(), self.cl_id.text(), self.cl_sec.text())
                pops = {}
                try:
                    token = asyncio.run(client.get_token())
                    if token:
                        pops = asyncio.run(client.get_populations())
                except Exception:
                    token = None
                # Show attribute mapping dialog (passes population map and any saved mappings for this profile)
                initial_mapping = None
                initial_fixed = None
                prof_name = self.profile_list.currentText()
                try:
                    cfg = self._read_config()
                    if prof_name and prof_name in cfg:
                        initial_mapping = cfg[prof_name].get('mappings')
                        initial_fixed = cfg[prof_name].get('fixed_population_id')
                except Exception:
                    initial_mapping = None
                    initial_fixed = None
                initial_enabled = None
                try:
                    if prof_name and prof_name in cfg:
                        initial_enabled = cfg[prof_name].get('fixed_enabled')
                except Exception:
                    initial_enabled = None
                map_dialog = AttributeMappingDialog(headers, self, pop_map=pops, initial_mapping=initial_mapping, initial_fixed_pop_id=initial_fixed, initial_fixed_enabled=initial_enabled)
                if map_dialog.exec() != QtWidgets.QDialog.Accepted:
                    return
                mapping, fixed_pop_id, fixed_enabled, remember = map_dialog.get_mapping()
                # Persist mapping into the active profile only if user chose to remember it
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
                for row in reader:
                    # Apply mapping to keys and build nested object
                    flat = {}
                    for k, v in row.items():
                        if v is None or v == '':
                            continue
                        target = mapping.get(k, k)
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
                            # skip any id column provided in CSV — system generated
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
            if not users:
                QtWidgets.QMessageBox.information(self, "Import", "No users found in CSV.")
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
            # Refresh existing usernames from the server to avoid stale cache
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
                    # update existing user
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
            def on_done(res):
                self.prog.hide()
                created = res.get('created', 0)
                total = res.get('total', 0)
                errors = res.get('errors', []) or []
                if created == 0 and errors:
                    dlg = QtWidgets.QDialog(self)
                    dlg.setWindowTitle("Import Result")
                    lay = QtWidgets.QVBoxLayout(dlg)
                    lab = QtWidgets.QLabel(f"Created {created}/{total} users. No users were created.")
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
                    QtWidgets.QMessageBox.information(self, "Import Complete", f"Created {created}/{total} users")
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
        try:
            users = []
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            entries = [e.strip() for e in content.split('\n\n') if e.strip()]
            # Show attribute mapping dialog using a synthetic header list
            # derived from the first entry's keys (hyphens converted to dots)
            first_flat_keys = []
            if entries:
                first = entries[0]
                for line in first.splitlines():
                    if not line or ':' not in line:
                        continue
                    key = line.split(':', 1)[0].strip()
                    if '-' in key and '.' not in key:
                        key = key.replace('-', '.')
                    first_flat_keys.append(key)
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
            map_dialog = AttributeMappingDialog(first_flat_keys, self, pop_map=pops, initial_mapping=initial_mapping, initial_fixed_pop_id=initial_fixed, initial_fixed_enabled=initial_enabled)
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

                    def on_done(res):
                        created = res.get('created', 0)
                        total = res.get('total', 0)
                        errors = res.get('errors', []) or []

                        def _on_updates_done(res2):
                            self.prog.hide()
                            updated = res2.get('updated', 0)
                            total_upd = res2.get('total', 0)
                            upd_errors = res2.get('errors', []) or []
                            result_msg = f"Created {created}/{total} users; Updated {updated}/{total_upd} users"
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

    def save_columns_to_config(self):
        """Save the selected columns to the current profile's configuration."""
        name = self.profile_list.currentText()
        if not name:
            return
        p = self._read_config()
        if name in p:
            p[name]["columns"] = self.selected_columns
            with open(self.config_file, 'w') as f:
                json.dump(p, f, indent=4)

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
        self.columns = [c for c in self.selected_columns if c in self.all_columns]
        self.selected_columns = self.columns.copy()
        self.save_columns_to_config()
        self.u_table.setColumnCount(len(self.columns))
        self.u_table.setHorizontalHeaderLabels(self._get_column_labels())
        self.u_table.setRowCount(0)
        for u in self.users_cache:
            r = self.u_table.rowCount()
            self.u_table.insertRow(r)
            for c, col in enumerate(self.columns):
                value = self._get_value(u, col)
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setData(QtCore.Qt.UserRole, value)
                self.u_table.setItem(r, c, item)
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
        self.selected_columns = [self.columns[self.u_table.horizontalHeader().visualIndex(i)] for i in range(len(self.columns))]
        self.save_columns_to_config()
        msg = "Column order updated"
        self.status_label.setText(msg)
        try:
            self.statusBar().showMessage(msg)
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
