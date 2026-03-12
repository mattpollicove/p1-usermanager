"""Reusable Qt dialogs used by the PingOne UserManager UI.

Contains small, focused dialogs for editing user fields, selecting
table columns, and viewing/editing JSON payloads.
"""

import json
import sys
import platform
from pathlib import Path

# Add project root to sys.path when running this file directly so
# `from ui.dialogs` and other absolute imports resolve in editor-run mode.
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from PySide6 import QtWidgets, QtCore, QtGui

# Platform detection for cross-platform UI optimization
IS_MACOS = platform.system() == 'Darwin'
IS_WINDOWS = platform.system() == 'Windows'
IS_LINUX = platform.system() == 'Linux'


def get_dpi_scale():
    """Get the current DPI scale factor for sizing dialogs appropriately."""
    try:
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            return screen.devicePixelRatio()
    except Exception:
        pass
    return 1.0


def scale_size(base_size, dpi_scale=None):
    """Scale a size value based on DPI, ensuring minimum readability."""
    if dpi_scale is None:
        dpi_scale = get_dpi_scale()
    return int(base_size * max(1.0, dpi_scale * 0.8))


class EditUserDialog(QtWidgets.QDialog):
    """Dialog for editing user information."""
    def __init__(self, user_data, pop_map, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit User")
        self.setModal(True)
        
        # Set minimum size based on DPI
        dpi_scale = get_dpi_scale()
        self.setMinimumSize(scale_size(450, dpi_scale), scale_size(400, dpi_scale))
        
        layout = QtWidgets.QFormLayout(self)
        
        self.username = QtWidgets.QLineEdit(user_data.get('username', ''))
        self.username.setPlaceholderText("e.g. jsmith")
        self.username.setToolTip("Unique username used in PingOne")
        self.email = QtWidgets.QLineEdit(user_data.get('email', ''))
        self.email.setPlaceholderText("user@example.com")
        self.email.setToolTip("Primary email address")
        self.first_name = QtWidgets.QLineEdit(user_data.get('name', {}).get('given', ''))
        self.first_name.setPlaceholderText("First name")
        self.last_name = QtWidgets.QLineEdit(user_data.get('name', {}).get('family', ''))
        self.last_name.setPlaceholderText("Last name")
        self.phone = QtWidgets.QLineEdit()
        self.phone.setPlaceholderText("Optional mobile number")
        phones = user_data.get('phoneNumbers', [])
        if phones:
            self.phone.setText(phones[0].get('number', ''))
        self.street = QtWidgets.QLineEdit(user_data.get('address', {}).get('streetAddress', ''))
        self.street.setPlaceholderText("Street address")
        self.city = QtWidgets.QLineEdit(user_data.get('address', {}).get('locality', ''))
        self.city.setPlaceholderText("City")
        self.state = QtWidgets.QLineEdit(user_data.get('address', {}).get('region', ''))
        self.state.setPlaceholderText("State or region")
        self.zip = QtWidgets.QLineEdit(user_data.get('address', {}).get('postalCode', ''))
        self.zip.setPlaceholderText("ZIP/postal code")
        self.country = QtWidgets.QLineEdit(user_data.get('address', {}).get('country', ''))
        self.country.setPlaceholderText("Country")
        self.population = QtWidgets.QComboBox()
        self.population.addItems(list(pop_map.values()))
        current_pop_id = user_data.get('population', {}).get('id', '')
        current_pop_name = pop_map.get(current_pop_id, '')
        self.population.setCurrentText(current_pop_name)
        self.population.setEnabled(False)  # Population not modifiable
        
        layout.addRow("Username:", self.username)
        layout.addRow("Email:", self.email)
        layout.addRow("First Name:", self.first_name)
        layout.addRow("Last Name:", self.last_name)
        layout.addRow("Phone:", self.phone)
        layout.addRow("Street Address:", self.street)
        layout.addRow("City:", self.city)
        layout.addRow("State/Region:", self.state)
        layout.addRow("ZIP/Postal Code:", self.zip)
        layout.addRow("Country:", self.country)
        layout.addRow("Population:", self.population)
        
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        # default/escape roles for keyboard accessibility
        ok_btn = buttons.button(QtWidgets.QDialogButtonBox.Ok)
        if ok_btn:
            ok_btn.setDefault(True)
        cancel_btn = buttons.button(QtWidgets.QDialogButtonBox.Cancel)
        if cancel_btn:
            cancel_btn.setAutoDefault(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.user_data = user_data
        self.pop_map = pop_map
    
    def get_data(self):
        """Return the updated user data from the dialog."""
        # Build a minimal user update payload containing only fields that
        # the UI allows editing. This keeps updates concise and reduces
        # risk of accidentally overwriting unrelated attributes.
        pop_name = self.population.currentText()
        pop_id = next((k for k, v in self.pop_map.items() if v == pop_name), '')
        data = {
            "username": self.username.text(),
            "email": self.email.text(),
            "name": {"given": self.first_name.text(), "family": self.last_name.text()},
            "population": {"id": pop_id}
        }
        if self.phone.text():
            data["phoneNumbers"] = [{"number": self.phone.text(), "type": "mobile"}]
        address = {}
        if self.street.text():
            address["streetAddress"] = self.street.text()
        if self.city.text():
            address["locality"] = self.city.text()
        if self.state.text():
            address["region"] = self.state.text()
        if self.zip.text():
            address["postalCode"] = self.zip.text()
        if self.country.text():
            address["country"] = self.country.text()
        if address:
            data["address"] = address
        return data


class ColumnSelectDialog(QtWidgets.QDialog):
    """Dialog for selecting which columns to display in the user table."""
    def __init__(self, all_columns, selected, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Columns")
        self.setModal(True)
        self.parent_window = parent
        self.defaults_applied = False  # Track if user clicked Reset to Defaults
        
        # Set minimum size based on DPI
        dpi_scale = get_dpi_scale()
        self.setMinimumSize(scale_size(400, dpi_scale), scale_size(300, dpi_scale))
        
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # Columns checkboxes
        columns_layout = QtWidgets.QHBoxLayout()
        self.checkboxes = {}
        sorted_cols = sorted(all_columns)
        mid = len(sorted_cols) // 2
        
        for col_list in [sorted_cols[:mid], sorted_cols[mid:]]:
            col_layout = QtWidgets.QVBoxLayout()
            for col in col_list:
                cb = QtWidgets.QCheckBox(col)
                cb.setChecked(col in selected)
                if col == 'id':
                    cb.setEnabled(False)
                col_layout.addWidget(cb)
                self.checkboxes[col] = cb
            col_layout.addStretch()
            columns_layout.addLayout(col_layout)
        
        main_layout.addLayout(columns_layout)
        
        # Buttons
        buttons_layout = QtWidgets.QHBoxLayout()
        
        select_all_btn = QtWidgets.QPushButton("Select All")
        select_all_btn.setToolTip("Check every column")
        select_all_btn.clicked.connect(self.select_all)
        buttons_layout.addWidget(select_all_btn)
        
        clear_all_btn = QtWidgets.QPushButton("Clear All")
        clear_all_btn.setToolTip("Uncheck every column except ID")
        clear_all_btn.clicked.connect(self.clear_all)
        buttons_layout.addWidget(clear_all_btn)
        
        reset_btn = QtWidgets.QPushButton("Reset to Defaults")
        reset_btn.setToolTip("Restore the application's recommended column set")
        reset_btn.clicked.connect(self.reset_to_defaults)
        buttons_layout.addWidget(reset_btn)
        
        buttons_layout.addStretch()
        
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        ok_btn = button_box.button(QtWidgets.QDialogButtonBox.Ok)
        if ok_btn:
            ok_btn.setDefault(True)
        cancel_btn = button_box.button(QtWidgets.QDialogButtonBox.Cancel)
        if cancel_btn:
            cancel_btn.setAutoDefault(False)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        buttons_layout.addWidget(button_box)
        
        main_layout.addLayout(buttons_layout)
    
    def get_selected(self):
        """Return the list of selected column names."""
        # If defaults were applied, return them in the correct order
        if self.defaults_applied and self.parent_window and hasattr(self.parent_window, 'default_columns'):
            default_columns = self.parent_window.default_columns
            # Return defaults first, then any additional selected columns
            selected = [col for col in default_columns if self.checkboxes.get(col, QtWidgets.QCheckBox()).isChecked()]
            # Add any non-default columns that are selected
            for col, cb in self.checkboxes.items():
                if cb.isChecked() and col not in default_columns:
                    selected.append(col)
            return selected
        
        return [col for col, cb in self.checkboxes.items() if cb.isChecked()]
    
    def reset_to_defaults(self):
        """Reset checkboxes to default columns."""
        # Get default columns from parent window
        default_columns = ['id', 'name.given', 'name.family', 'email', 'population.name']
        if self.parent_window and hasattr(self.parent_window, 'default_columns'):
            default_columns = self.parent_window.default_columns
        
        # Mark that defaults were applied
        self.defaults_applied = True
        
        # Update checkboxes
        for col, cb in self.checkboxes.items():
            if col == 'id':
                continue  # Always checked and disabled
            cb.setChecked(col in default_columns)
    
    def select_all(self):
        """Select all column checkboxes."""
        self.defaults_applied = False  # Clear defaults flag since this is a custom selection
        for col, cb in self.checkboxes.items():
            cb.setChecked(True)
    
    def clear_all(self):
        """Clear all column checkboxes except the required 'id' column."""
        self.defaults_applied = False  # Clear defaults flag since this is a custom selection
        for col, cb in self.checkboxes.items():
            if col == 'id':
                continue  # ID is always required and disabled
            cb.setChecked(False)


class JSONViewDialog(QtWidgets.QDialog):
    """Dialog for viewing and optionally editing JSON content."""
    def __init__(self, data, editable, parent, user_id, col_name):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("JSON Content")
        self.user_id = user_id
        self.col_name = col_name
        self.parent = parent
        
        # Set minimum size based on DPI
        dpi_scale = get_dpi_scale()
        self.setMinimumSize(scale_size(600, dpi_scale), scale_size(400, dpi_scale))
        
        layout = QtWidgets.QVBoxLayout(self)
        self.text = QtWidgets.QTextEdit()
        self.text.setPlainText(json.dumps(data, indent=2))
        if not editable:
            self.text.setReadOnly(True)
        layout.addWidget(self.text)
        buttons = QtWidgets.QHBoxLayout()
        if editable:
            save_btn = QtWidgets.QPushButton("Save")
            save_btn.setDefault(True)
            save_btn.clicked.connect(self.save_changes)
            buttons.addWidget(save_btn)
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)
    
    def save_changes(self):
        """Save the edited JSON back to the user data."""
        # Validate selection before attempting to save edits back to the
        # user's record via the main window helper.
        if not self.user_id:
            QtWidgets.QMessageBox.warning(self, "Error", "No user selected for saving.")
            return
        try:
            new_data = json.loads(self.text.toPlainText())
            self.parent.update_user_field(self.user_id, self.col_name, new_data)
            QtWidgets.QMessageBox.information(self, "Saved", "JSON updated successfully.")
        except json.JSONDecodeError:
            QtWidgets.QMessageBox.warning(self, "Error", "Invalid JSON format.")


class TextViewDialog(QtWidgets.QDialog):
    """Dialog to display (and optionally edit/save) plain text or blob content.

    If `editable` is True and `user_id` + `col_name` are provided, the Save
    button will call `parent.update_user_field(user_id, col_name, new_text)`.
    """
    def __init__(self, text: str, title: str = "Content", parent=None, editable: bool = False, user_id: str = None, col_name: str = None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle(title)
        
        # Set minimum size based on DPI
        dpi_scale = get_dpi_scale()
        self.setMinimumSize(scale_size(600, dpi_scale), scale_size(400, dpi_scale))
        
        layout = QtWidgets.QVBoxLayout(self)
        self.text = QtWidgets.QTextEdit()
        self.text.setReadOnly(not bool(editable))
        self.text.setPlainText(text or '')
        layout.addWidget(self.text)
        btns = QtWidgets.QDialogButtonBox()
        if editable:
            save_btn = QtWidgets.QPushButton("Save")
            save_btn.setDefault(True)
            save_btn.clicked.connect(self._on_save)
            btns.addButton(save_btn, QtWidgets.QDialogButtonBox.ActionRole)
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btns.addButton(close_btn, QtWidgets.QDialogButtonBox.RejectRole)
        layout.addWidget(btns)
        self._editable = bool(editable)
        self._user_id = user_id
        self._col_name = col_name
        self._parent = parent

    def _on_save(self):
        """Save edited text back to the user field via parent.update_user_field."""
        if not self._editable:
            return
        new_text = self.text.toPlainText()
        # If parent exposes update_user_field, call it
        try:
            if self._parent and hasattr(self._parent, 'update_user_field') and self._user_id and self._col_name:
                # Attempt to preserve JSON if the content looks like JSON
                import json as _json
                out = new_text
                try:
                    parsed = _json.loads(new_text)
                    out = parsed
                except Exception:
                    out = new_text
                self._parent.update_user_field(self._user_id, self._col_name, out)
                QtWidgets.QMessageBox.information(self, "Saved", "Changes saved.")
                self.accept()
                return
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save Failed", str(e))
            return
        # Fallback: just close
        self.accept()


class AttributeMappingDialog(QtWidgets.QDialog):
    """Dialog to review and edit mapping from file headers to API attribute names.

    Presents a small form for required fields (username, email, given/family names,
    and population selection) followed by a two-column table: the original file
    header (read-only) and an editable mapped attribute (defaulting to a
    suggested mapping). Returns a tuple `(mapping_dict, fixed_population_id)` where
    `fixed_population_id` is a population id chosen from the dropdown or `None`.
    """
    def __init__(self, headers, parent=None, pop_map: dict = None, initial_mapping: dict = None, initial_fixed_pop_id: str = None, initial_fixed_enabled=None):
        super().__init__(parent)
        self.setWindowTitle("Attribute Mapping")
        self.setModal(True)
        
        # Set minimum size based on DPI
        dpi_scale = get_dpi_scale()
        self.setMinimumSize(scale_size(700, dpi_scale), scale_size(500, dpi_scale))
        
        layout = QtWidgets.QVBoxLayout(self)

        # Keep a local copy of headers for dropdowns
        self.headers = list(headers or [])
        # population map: name -> id
        self.pop_map = pop_map or {}
        # persist initial fixed population id for use during mapping retrieval
        self.initial_fixed_pop_id = initial_fixed_pop_id

        # Top form for required / commonly-used attributes so users can
        # explicitly choose which file header maps to them.
        form = QtWidgets.QFormLayout()
        self.username_field = QtWidgets.QComboBox()
        self.email_field = QtWidgets.QComboBox()
        self.given_field = QtWidgets.QComboBox()
        self.family_field = QtWidgets.QComboBox()
        # population source: choose CSV field or select fixed population
        self.population_field = QtWidgets.QComboBox()
        self.population_fixed = QtWidgets.QComboBox()
        # enabled mapping: allow mapping from CSV header or fixed True/False
        self.enabled_field = QtWidgets.QComboBox()

        # Helper to populate header-selection combos (allow empty selection)
        def _populate_hdr_combo(cb: QtWidgets.QComboBox, default_suggest: str = None):
            cb.addItem("<None>")
            for h in self.headers:
                cb.addItem(h)
            # Try to auto-select a suggested header if present
            if default_suggest:
                for i in range(cb.count()):
                    if cb.itemText(i).lower() == default_suggest.lower():
                        cb.setCurrentIndex(i)
                        break

        _populate_hdr_combo(self.username_field, 'username')
        _populate_hdr_combo(self.email_field, 'email')
        _populate_hdr_combo(self.given_field, 'first name')
        _populate_hdr_combo(self.family_field, 'last name')
        _populate_hdr_combo(self.population_field, 'population')
        # populate enabled_field: only fixed true/false options per request
        self.enabled_field.addItem("<None>", None)
        self.enabled_field.addItem("<Fixed: true>", True)
        self.enabled_field.addItem("<Fixed: false>", False)
        # If an initial fixed enabled value was provided, pre-select it
        try:
            if initial_fixed_enabled is True:
                idx = self.enabled_field.findData(True)
                if idx != -1:
                    self.enabled_field.setCurrentIndex(idx)
            elif initial_fixed_enabled is False:
                idx = self.enabled_field.findData(False)
                if idx != -1:
                    self.enabled_field.setCurrentIndex(idx)
        except Exception:
            pass

        # If an initial mapping was provided, pre-select choices where possible
        try:
            if initial_mapping and isinstance(initial_mapping, dict):
                def _select_header_for(target_attr, combo):
                    for hdr, mapped in initial_mapping.items():
                        if mapped == target_attr:
                            idx = combo.findText(hdr)
                            if idx != -1:
                                combo.setCurrentIndex(idx)
                                return
                _select_header_for('username', self.username_field)
                _select_header_for('email', self.email_field)
                _select_header_for('name.given', self.given_field)
                _select_header_for('name.family', self.family_field)
                # population may have been stored as population.id mapping
                _select_header_for('population.id', self.population_field)
                # initial_fixed_enabled handled above; ignore header-mapped enabled values
        except Exception:
            pass

        # Populate population_fixed dropdown with a default <Use CSV Field> option
        self.population_fixed.addItem("<Use CSV Field>")
        for name, pid in sorted(self.pop_map.items(), key=lambda x: x[0].lower()):
            self.population_fixed.addItem(f"{name} ({pid})", pid)

        form.addRow("Username field:", self.username_field)
        form.addRow("Email field:", self.email_field)
        form.addRow("Given name field:", self.given_field)
        form.addRow("Family name field:", self.family_field)
        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.population_field)
        hbox.addWidget(self.population_fixed)
        form.addRow("Population:", hbox)
        form.addRow("Enabled field:", self.enabled_field)
        layout.addLayout(form)
        # Note about ID columns: show them but they are system-generated
        note = QtWidgets.QLabel("Note: any 'ID' column is system-generated and read-only; ID values will be shown but ignored during import.")
        note.setWordWrap(True)
        note.setStyleSheet('color: #555; font-style: italic;')


# -- database connection/dialog classes -------------------------------------------------

class DatabaseConnectionDialog(QtWidgets.QDialog):
    """Dialog for creating or editing a database connection definition.

    Fields include connection name, type (MSSQL or MariaDB), host/port/db,
    credentials, and optional JDBC/ODBC driver path.  Provides a "Test
    Connection" button that calls :func:`api.db_utils.test_connection`.

    The ``get_connection_data`` method returns a dict suitable for storing in
    the config under ``db_connections``.
    """
    def __init__(self, initial: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Database Connection")
        self.setModal(True)
        dpi = get_dpi_scale()
        self.setMinimumSize(scale_size(500, dpi), scale_size(400, dpi))


        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

        self.name_edit = QtWidgets.QLineEdit()
        self.type_combo = QtWidgets.QComboBox()
        # make MySQL/Maria the default entry
        self.type_combo.addItems(["MariaDB/MySQL", "MSSQL"])
        self.host_edit = QtWidgets.QLineEdit()
        self.host_edit.setPlaceholderText("hostname or IP")
        self.host_edit.setToolTip("Database server host")
        self.port_edit = QtWidgets.QLineEdit()
        self.port_edit.setValidator(QtGui.QIntValidator(1, 65535))
        self.port_edit.setPlaceholderText("port number")
        self.port_edit.setToolTip("TCP port for the database service")
        self.db_edit = QtWidgets.QLineEdit()
        self.db_edit.setPlaceholderText("database name")
        self.db_edit.setToolTip("Name of the target database")
        # add JDBC URL display field before any signals use it
        self.jdbc_edit = QtWidgets.QLineEdit()
        self.jdbc_edit.setReadOnly(True)
        self.jdbc_edit.setPlaceholderText("jdbc URL will appear here")
        # make the preview wide so long URLs are easier to read/copy
        self.jdbc_edit.setMinimumWidth(400)
        self.jdbc_edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        self.user_edit = QtWidgets.QLineEdit()
        self.user_edit.setPlaceholderText("username")
        self.user_edit.setToolTip("Database user account")
        self.pw_edit = QtWidgets.QLineEdit()
        self.pw_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.pw_edit.setPlaceholderText("password")
        # driver name (for pyodbc) or JDBC/ODBC path
        self.driver_combo = QtWidgets.QComboBox()
        self.driver_combo.setEditable(True)
        self.driver_combo.setPlaceholderText("driver name or path")
        self.driver_combo.setToolTip("Select or type a driver name (e.g. ODBC Driver 18 for SQL Server) or specify a path to a JDBC/ODBC driver library")
        # populate with sensible defaults (will be refreshed on type change)
        self._set_driver_options()

        # update port field whenever type changes
        self.type_combo.currentTextChanged.connect(self._update_port_default)
        # refresh driver name suggestions when type changes
        self.type_combo.currentTextChanged.connect(self._set_driver_options)
        # update JDBC string when type changes
        self.type_combo.currentTextChanged.connect(self._update_jdbc_string)
        # update JDBC string when host/db/port change
        self.host_edit.textChanged.connect(self._update_jdbc_string)
        self.port_edit.textChanged.connect(self._update_jdbc_string)
        self.db_edit.textChanged.connect(self._update_jdbc_string)
        drv_layout = QtWidgets.QHBoxLayout()
        drv_layout.addWidget(self.driver_combo)

        form.addRow("Name:", self.name_edit)
        form.addRow("Type:", self.type_combo)
        form.addRow("Host:", self.host_edit)
        form.addRow("Port:", self.port_edit)
        form.addRow("Database:", self.db_edit)
        # table selector will be populated after a successful connection test
        self.table_combo = QtWidgets.QComboBox()
        self.table_combo.setEnabled(False)
        form.addRow("Table:", self.table_combo)
        form.addRow("User:", self.user_edit)
        form.addRow("Password:", self.pw_edit)
        form.addRow("Driver:", drv_layout)
        # readonly JDBC URL preview placed at the bottom so it stretches
        form.addRow("JDBC URL:", self.jdbc_edit)

        layout.addLayout(form)

        # initialize port based on current type (combo default may already be set)
        self._update_port_default()
        # ensure JDBC string is populated as well
        self._update_jdbc_string()

        test_btn = QtWidgets.QPushButton("Test Connection")
        test_btn.clicked.connect(self._on_test)
        layout.addWidget(test_btn)

        # status label shows progress/result of connection test
        self.status_label = QtWidgets.QLabel("")
        layout.addWidget(self.status_label)

        # allow user to choose whether this connection should be saved
        self.save_cb = QtWidgets.QCheckBox("Save this connection")
        self.save_cb.setChecked(True)
        layout.addWidget(self.save_cb)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        if initial:
            self.name_edit.setText(initial.get('name', ''))
            self.type_combo.setCurrentText(initial.get('type', 'MariaDB/MySQL'))
            self.host_edit.setText(initial.get('host', ''))
            self.port_edit.setText(str(initial.get('port', '')))
            self.db_edit.setText(initial.get('database', ''))
            self.user_edit.setText(initial.get('user', ''))
            self.pw_edit.setText(initial.get('password', ''))
            self.driver_combo.setCurrentText(initial.get('driver', ''))
            # do not prefill the table combo when editing; user must test
            # the connection in order to refresh and choose a table
            # rebuild JDBC string from loaded values
            self._update_jdbc_string()
            # if editing an existing connection, focus name field for convenience
            self.name_edit.setFocus()

    # browsing is no longer required since driver is entered via combo
    # kept for historical reference but not used
    def _browse_driver(self):
        pass

    def _validate_and_accept(self):
        """Ensure required fields are present before closing dialog."""
        name = self.name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Invalid Name", "Connection name cannot be empty.")
            self.name_edit.setFocus()
            return
        host = self.host_edit.text().strip()
        db = self.db_edit.text().strip()
        if not host or not db:
            QtWidgets.QMessageBox.warning(self, "Missing Details", "Host and database name are required.")
            if not host:
                self.host_edit.setFocus()
            else:
                self.db_edit.setFocus()
            return
        # everything seems fine
        self.accept()

    def _update_port_default(self):
        # called when the type combo changes
        typ = self.type_combo.currentText()
        if typ == "MariaDB/MySQL":
            default = "3306"
        else:
            default = "1433"
        if not self.port_edit.text():
            self.port_edit.setText(default)
        # also refresh JDBC url whenever port default changes
        self._update_jdbc_string()

    def _set_driver_options(self):
        """Populate the driver combo with sensible defaults for the selected DB.

        The combo is always editable so the user may enter a custom string or
        a path, but providing a dropdown helps when picking a recent ODBC
        driver name for SQL Server.
        """
        typ = self.type_combo.currentText()
        self.driver_combo.clear()
        if typ == "MariaDB/MySQL":
            # MySQL doesn't actually use the driver string in our URL, but
            # having some common ODBC names may help users who configure
            # pyodbc manually.
            self.driver_combo.addItems([
                "MySQL ODBC 8.0 Driver",
                "MySQL ODBC 8.0 Unicode Driver",
            ])
        else:
            # SQL Server: recent ODBC drivers
            self.driver_combo.addItems([
                "ODBC Driver 18 for SQL Server",
                "ODBC Driver 17 for SQL Server",
                "ODBC Driver 13 for SQL Server",
            ])

    def _update_jdbc_string(self):
        """Build a JDBC connection string from the current fields.

        The string is shown in the read‑only ``jdbc_edit`` so the user can
        copy it or verify the syntax.  It updates whenever the type, host,
        port or database fields change.
        """
        typ = self.type_combo.currentText()
        host = self.host_edit.text().strip()
        port = self.port_edit.text().strip() or ("3306" if typ == "MariaDB/MySQL" else "1433")
        db = self.db_edit.text().strip()
        url = ""
        if host and db:
            if typ == "MariaDB/MySQL":
                url = f"jdbc:mysql://{host}:{port}/{db}"
            else:
                # MSSQL style
                url = f"jdbc:sqlserver://{host}:{port};databaseName={db}"
        self.jdbc_edit.setText(url)

    def _populate_tables(self):
        # attempt to list tables and fill combo - called after a successful test
        try:
            from api import db_utils
        except ModuleNotFoundError:
            # if sqlalchemy isn't installed there's nothing to do
            return

        try:
            names = db_utils.get_table_names(
                self.type_combo.currentText(),
                self.host_edit.text(),
                int(self.port_edit.text() or 0),
                self.db_edit.text(),
                self.user_edit.text(),
                self.pw_edit.text(),
                self.driver_combo.currentText() or None,
            )
            self.table_combo.clear()
            self.table_combo.addItems(names)
            self.table_combo.setEnabled(bool(names))
            if names:
                self.status_label.setText(f"Found {len(names)} table(s).")
            else:
                self.status_label.setText("No tables found.")
        except Exception:
            # silently ignore; tables remain as-is
            pass

    def _on_test(self):
        # show busy cursor and status while testing
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        self.status_label.setText("Testing connection...")
        QtWidgets.QApplication.processEvents()
        try:
            from api import db_utils
        except ModuleNotFoundError:
            QtWidgets.QMessageBox.critical(
                self,
                "Missing Dependency",
                "SQLAlchemy is not installed. Please install the requirements and restart (e.g. `pip install -r requirements.txt`)."
            )
            QtWidgets.QApplication.restoreOverrideCursor()
            self.status_label.setText("Dependency missing.")
            return

        port = int(self.port_edit.text() or 0)
        ok = db_utils.test_connection(
            self.type_combo.currentText(),
            self.host_edit.text(),
            port,
            self.db_edit.text(),
            self.user_edit.text(),
            self.pw_edit.text(),
            self.driver_combo.currentText() or None
        )
        QtWidgets.QApplication.restoreOverrideCursor()
        if ok:
            self.status_label.setText("Connection successful.")
            self._populate_tables()
        else:
            self.status_label.setText("Connection failed.")
            # clear any previous table list so the user must retest
            self.table_combo.clear()
            self.table_combo.setEnabled(False)
            QtWidgets.QMessageBox.critical(self, "Test Connection", "Failed to connect. Check credentials and driver.")

    def get_connection_data(self) -> dict:
        data = {
            'name': self.name_edit.text().strip(),
            'type': self.type_combo.currentText(),
            'host': self.host_edit.text().strip(),
            'port': int(self.port_edit.text() or 0),
            'database': self.db_edit.text().strip(),
            'user': self.user_edit.text().strip(),
            'password': self.pw_edit.text(),
            'driver': self.driver_combo.currentText().strip(),
            'save': bool(self.save_cb.isChecked()),
        }
        # include table if user selected one
        if self.table_combo.count() and self.table_combo.currentText():
            data['table'] = self.table_combo.currentText()
        return data


class DBConnectionsManager(QtWidgets.QDialog):
    """List, create, edit, and delete saved database connections."""
    def __init__(self, connections: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Database Connections")
        self.setModal(True)
        dpi = get_dpi_scale()
        self.setMinimumSize(scale_size(600, dpi), scale_size(400, dpi))
        layout = QtWidgets.QVBoxLayout(self)
        # ensure Enter triggers edit when a connection is selected
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.itemActivated.connect(self.edit)

        self.list_widget = QtWidgets.QListWidget()
        self._populate(connections)
        layout.addWidget(self.list_widget)

        btn_layout = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("Add")
        add_btn.setToolTip("Create a new connection profile")
        edit_btn = QtWidgets.QPushButton("Edit")
        edit_btn.setToolTip("Modify the selected connection")
        del_btn = QtWidgets.QPushButton("Delete")
        del_btn.setToolTip("Remove the selected connection")
        btn_layout.addWidget(add_btn); btn_layout.addWidget(edit_btn); btn_layout.addWidget(del_btn);
        layout.addLayout(btn_layout)

        add_btn.clicked.connect(self.add)
        edit_btn.clicked.connect(self.edit)
        del_btn.clicked.connect(self.delete)
        # make Add the default button so Enter adds when no selection
        add_btn.setDefault(True)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self.connections = connections
        self.result = connections.copy()

    def _populate(self, connections):
        self.list_widget.clear()
        for name in sorted(connections.keys()):
            self.list_widget.addItem(name)

    def add(self):
        dlg = DatabaseConnectionDialog(parent=self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            data = dlg.get_connection_data()
            # save flag allows dialog users to request a non-persistent test
            if not data.get('save', True):
                # simply return without adding/updating profile
                return
            name = data.get('name')
            if name:
                if name in self.result:
                    resp = QtWidgets.QMessageBox.question(
                        self, "Replace Connection",
                        f"A connection named '{name}' already exists. Replace it?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                    )
                    if resp != QtWidgets.QMessageBox.Yes:
                        return
                self.result[name] = data
                self._populate(self.result)

    def edit(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        name = item.text()
        data = self.result.get(name, {})
        dlg = DatabaseConnectionDialog(initial=data, parent=self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            new_data = dlg.get_connection_data()
            # if user unchecks save while editing, remove the connection
            if not new_data.get('save', True):
                if name in self.result:
                    del self.result[name]
                    self._populate(self.result)
                return
            new_name = new_data.get('name')
            # handle rename
            if new_name and new_name != name:
                del self.result[name]
            self.result[new_name] = new_data
            self._populate(self.result)

    def delete(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        name = item.text()
        if QtWidgets.QMessageBox.question(self, "Delete", f"Delete connection '{name}'?") == QtWidgets.QMessageBox.Yes:
            del self.result[name]
            self._populate(self.result)

    def get_connections(self) -> dict:
        return self.result


class DatabaseMappingDialog(QtWidgets.QDialog):
    """Mapping dialog for database table columns and PingOne attributes.

    The behaviour differs depending on ``direction``:
    - ``'import'``: columns -> PingOne attributes
    - ``'export'``: PingOne attributes -> columns

    ``pingone_attrs`` should be a list of available PingOne attribute names.
    ``table_cols`` is a list of column names read from the database.
    Optionally, ``sample_row`` may provide a dict of a single row for preview
    values (used only in import direction).
    """
    def __init__(self, table_cols: List[str], pingone_attrs: List[str], direction: str = 'import', sample_row: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Database Mapping")
        self.setModal(True)
        dpi = get_dpi_scale()
        self.setMinimumSize(scale_size(800, dpi), scale_size(600, dpi))

        layout = QtWidgets.QVBoxLayout(self)
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(3)
        if direction == 'import':
            headers = ["Column Name", "Sample Value", "PingOne Attribute"]
        else:
            headers = ["PingOne Attribute", "Example Value", "Target Column"]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(table_cols))

        for i, col in enumerate(table_cols):
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(col))
            # sample value
            val = ''
            if sample_row and col in sample_row:
                val = str(sample_row[col])
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(val))
            combo = QtWidgets.QComboBox()
            combo.addItem("<None>")
            for attr in pingone_attrs:
                combo.addItem(attr)
            self.table.setCellWidget(i, 2, combo)

        layout.addWidget(self.table)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        ok_btn = btns.button(QtWidgets.QDialogButtonBox.Ok)
        if ok_btn:
            ok_btn.setDefault(True)
        cancel_btn = btns.button(QtWidgets.QDialogButtonBox.Cancel)
        if cancel_btn:
            cancel_btn.setAutoDefault(False)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_mapping(self) -> dict:
        result = {}
        for row in range(self.table.rowCount()):
            left = self.table.item(row, 0).text()
            combo: QtWidgets.QComboBox = self.table.cellWidget(row, 2)
            tgt = combo.currentText()
            if tgt and tgt != "<None>":
                result[left] = tgt
        return result



class ExportOptionsDialog(QtWidgets.QDialog):
    """Dialog to choose export options: selected vs all rows, visible vs all columns.

    Returns a dict: { 'rows': 'selected'|'all', 'only_visible_columns': bool, 'remember': bool }
    """
    def __init__(self, has_selection: bool, only_visible_default: bool = True, prefer_selected_default: bool = True, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Export Options')
        self.setModal(True)
        layout = QtWidgets.QVBoxLayout(self)

        self.setMinimumSize(420, 180)
        self.row_group = QtWidgets.QButtonGroup(self)
        self.rb_sel = QtWidgets.QRadioButton('Export only selected rows')
        self.rb_all = QtWidgets.QRadioButton('Export all rows')
        self.row_group.addButton(self.rb_sel)
        self.row_group.addButton(self.rb_all)
        if has_selection:
            if prefer_selected_default:
                self.rb_sel.setChecked(True)
            else:
                self.rb_all.setChecked(True)
        else:
            self.rb_sel.setEnabled(False)
            self.rb_all.setChecked(True)

        if not has_selection:
            note = QtWidgets.QLabel('No rows selected — "Export only selected rows" is disabled.')
            note.setStyleSheet('color: #666;')
            layout.addWidget(note)

        layout.addWidget(self.rb_sel)
        layout.addWidget(self.rb_all)

        self.only_visible_cb = QtWidgets.QCheckBox('Export only visible columns')
        self.only_visible_cb.setChecked(bool(only_visible_default))
        layout.addWidget(self.only_visible_cb)

        self.remember_cb = QtWidgets.QCheckBox('Remember these choices for this profile')
        self.remember_cb.setChecked(False)
        layout.addWidget(self.remember_cb)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        ok_btn = btns.button(QtWidgets.QDialogButtonBox.Ok)
        if ok_btn:
            ok_btn.setDefault(True)
        cancel_btn = btns.button(QtWidgets.QDialogButtonBox.Cancel)
        if cancel_btn:
            cancel_btn.setAutoDefault(False)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_options(self) -> dict:
        rows = 'selected' if self.rb_sel.isChecked() and self.rb_sel.isEnabled() else 'all'
        return {
            'rows': rows,
            'only_visible_columns': bool(self.only_visible_cb.isChecked()),
            'remember': bool(self.remember_cb.isChecked())
        }


class NewProfileDialog(QtWidgets.QDialog):
    """Dialog for creating a new profile with connection details."""
    
    def __init__(self, existing_profiles: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Create New Profile')
        self.setModal(True)
        self.existing_profiles = existing_profiles
        
        # Set dialog size
        dpi_scale = get_dpi_scale()
        self.setMinimumSize(scale_size(600, dpi_scale), scale_size(350, dpi_scale))
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Info label
        info = QtWidgets.QLabel(
            "Create a new profile by entering a name and connection details.\n"
            "Connection details are optional and can be configured later."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Form for profile details
        form = QtWidgets.QFormLayout()
        
        # Profile name - make it wide enough for reasonable names
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Production, Development")
        self.name_edit.setMinimumWidth(scale_size(400, dpi_scale))
        form.addRow("Profile Name*:", self.name_edit)
        
        form.addRow(QtWidgets.QLabel(""))  # Spacer
        
        # Connection details header
        conn_label = QtWidgets.QLabel("Connection Details (Optional):")
        font = conn_label.font()
        font.setBold(True)
        conn_label.setFont(font)
        form.addRow(conn_label)
        
        # Environment ID - match profile manager sizing
        self.env_id_edit = QtWidgets.QLineEdit()
        self.env_id_edit.setPlaceholderText("Environment ID (UUID)")
        self.env_id_edit.setToolTip("PingOne environment identifier")
        self.env_id_edit.setMaxLength(40)
        self.env_id_edit.setMinimumWidth(scale_size(400, dpi_scale))
        form.addRow("Environment ID:", self.env_id_edit)
        
        # Client ID - match profile manager sizing
        self.client_id_edit = QtWidgets.QLineEdit()
        self.client_id_edit.setPlaceholderText("Client ID (UUID)")
        self.client_id_edit.setMaxLength(40)
        self.client_id_edit.setMinimumWidth(scale_size(400, dpi_scale))
        form.addRow("Client ID:", self.client_id_edit)
        
        # Client Secret with show/hide toggle - ensure proper alignment
        secret_layout = QtWidgets.QHBoxLayout()
        secret_layout.setContentsMargins(0, 0, 0, 0)
        secret_layout.setSpacing(5)
        
        self.client_secret_edit = QtWidgets.QLineEdit()
        self.client_secret_edit.setPlaceholderText("Client Secret")
        self.client_secret_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.client_secret_edit.setMaxLength(100)
        self.client_secret_edit.setMinimumWidth(scale_size(330, dpi_scale))
        secret_layout.addWidget(self.client_secret_edit)
        
        self.show_secret_btn = QtWidgets.QPushButton("Show")
        self.show_secret_btn.setCheckable(True)
        self.show_secret_btn.setFixedWidth(scale_size(65, dpi_scale))
        self.show_secret_btn.toggled.connect(self._toggle_secret_visibility)
        secret_layout.addWidget(self.show_secret_btn)
        
        secret_widget = QtWidgets.QWidget()
        secret_widget.setLayout(secret_layout)
        form.addRow("Client Secret:", secret_widget)
        
        layout.addLayout(form)
        
        # Note about partial configuration
        note = QtWidgets.QLabel(
            "Note: You can leave connection details empty and configure them later "
            "in the Configuration tab."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #666; font-size: 10pt;")
        layout.addWidget(note)
        
        # Buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        ok_btn = button_box.button(QtWidgets.QDialogButtonBox.Ok)
        if ok_btn:
            ok_btn.setDefault(True)
        cancel_btn = button_box.button(QtWidgets.QDialogButtonBox.Cancel)
        if cancel_btn:
            cancel_btn.setAutoDefault(False)
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Focus on name field
        self.name_edit.setFocus()
    
    def _toggle_secret_visibility(self, checked):
        """Toggle client secret visibility."""
        if checked:
            self.client_secret_edit.setEchoMode(QtWidgets.QLineEdit.Normal)
            self.show_secret_btn.setText("Hide")
        else:
            self.client_secret_edit.setEchoMode(QtWidgets.QLineEdit.Password)
            self.show_secret_btn.setText("Show")
    
    def validate_and_accept(self):
        """Validate inputs before accepting."""
        name = self.name_edit.text().strip()
        
        # Validate profile name
        if not name:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid Name",
                "Profile name cannot be empty."
            )
            self.name_edit.setFocus()
            return
        
        if name == '__meta__':
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid Name",
                "Profile name '__meta__' is reserved."
            )
            self.name_edit.setFocus()
            return
        
        if name in self.existing_profiles:
            QtWidgets.QMessageBox.warning(
                self,
                "Profile Exists",
                f"A profile named '{name}' already exists.\nPlease choose a different name."
            )
            self.name_edit.setFocus()
            return
        
        # If any connection detail is provided, validate that we have at least env_id and client_id
        env_id = self.env_id_edit.text().strip()
        client_id = self.client_id_edit.text().strip()
        secret = self.client_secret_edit.text().strip()
        
        # Partial validation: if any field is filled, recommend filling all
        filled_fields = sum([bool(env_id), bool(client_id), bool(secret)])
        if 0 < filled_fields < 3:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Incomplete Credentials",
                "You have only partially filled the connection details.\n\n"
                "For a complete configuration, all three fields (Environment ID, Client ID, and Client Secret) are needed.\n\n"
                "Do you want to continue anyway?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return
        
        self.accept()
    
    def get_profile_data(self):
        """Return the profile data as a tuple: (name, env_id, client_id, secret)."""
        return (
            self.name_edit.text().strip(),
            self.env_id_edit.text().strip(),
            self.client_id_edit.text().strip(),
            self.client_secret_edit.text().strip()
        )


class ProfileManagerDialog(QtWidgets.QDialog):
    """Dialog to view, select, and delete profiles.
    
    Provides a list view of all saved profiles with their environment IDs,
    allowing users to see all configurations at a glance and delete unwanted ones.
    """
    def __init__(self, profiles_dict: dict, current_profile: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Manage Profiles')
        self.setModal(True)
        self.profiles_dict = profiles_dict
        self.current_profile = current_profile
        self.deleted_profiles = []
        self.new_profile_name = None
        self.new_profile_credentials = None  # Will hold (env_id, cl_id, secret) if provided
        self.auto_connect_requested = False  # Track if user wants to auto-connect to new profile
        self.connection_callback = None  # Callback to trigger connection test
        
        # Set reasonable dialog size based on DPI
        dpi_scale = get_dpi_scale()
        self.setMinimumSize(scale_size(700, dpi_scale), scale_size(500, dpi_scale))
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Info label
        info_label = QtWidgets.QLabel(
            "Select profiles to view details, create a new profile, or delete profiles. The current active profile is highlighted."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # List widget for profiles
        self.profile_list = QtWidgets.QListWidget()
        self.profile_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.profile_list.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.profile_list)
        
        # Details area
        details_group = QtWidgets.QGroupBox("Profile Details")
        details_layout = QtWidgets.QFormLayout(details_group)
        
        # Environment ID field - wider to display full UUID
        self.detail_env_id = QtWidgets.QLineEdit()
        self.detail_env_id.setReadOnly(True)
        self.detail_env_id.setMinimumWidth(scale_size(400, dpi_scale))
        
        # Client ID field - wider to display full UUID
        self.detail_client_id = QtWidgets.QLineEdit()
        self.detail_client_id.setReadOnly(True)
        self.detail_client_id.setMinimumWidth(scale_size(400, dpi_scale))
        
        # Columns display - use QTextEdit with scrollbar for dynamic content
        self.detail_columns = QtWidgets.QTextEdit()
        self.detail_columns.setReadOnly(True)
        self.detail_columns.setMaximumHeight(scale_size(80, dpi_scale))
        self.detail_columns.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.detail_columns.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        
        details_layout.addRow("Environment ID:", self.detail_env_id)
        details_layout.addRow("Client ID:", self.detail_client_id)
        details_layout.addRow("Custom Columns:", self.detail_columns)
        layout.addWidget(details_group)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        new_profile_btn = QtWidgets.QPushButton("New Profile...")
        new_profile_btn.clicked.connect(self.create_new_profile)
        button_layout.addWidget(new_profile_btn)
        
        self.delete_btn = QtWidgets.QPushButton("Delete Selected Profile")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self.delete_selected)
        button_layout.addWidget(self.delete_btn)
        button_layout.addStretch()
        
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Populate the list
        self.populate_profiles()
    
    def populate_profiles(self):
        """Populate the profile list widget with all available profiles."""
        self.profile_list.clear()
        # Filter out __meta__ key
        profile_names = [k for k in self.profiles_dict.keys() if k != '__meta__']
        
        for name in sorted(profile_names):
            item = QtWidgets.QListWidgetItem(name)
            # Highlight current profile
            if name == self.current_profile:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setText(f"{name} (active)")
            self.profile_list.addItem(item)
        
        # Select the first item if available
        if self.profile_list.count() > 0:
            self.profile_list.setCurrentRow(0)
    
    def on_selection_changed(self):
        """Update details when selection changes."""
        selected_items = self.profile_list.selectedItems()
        if not selected_items:
            self.delete_btn.setEnabled(False)
            self.clear_details()
            return
        
        item = selected_items[0]
        profile_name = item.text().replace(" (active)", "")
        
        self.delete_btn.setEnabled(True)
        self.show_profile_details(profile_name)
    
    def show_profile_details(self, profile_name: str):
        """Display details for the selected profile."""
        profile = self.profiles_dict.get(profile_name, {})
        
        self.detail_env_id.setText(profile.get('env_id', 'N/A'))
        self.detail_client_id.setText(profile.get('cl_id', 'N/A'))
        
        columns = profile.get('columns', [])
        if columns:
            col_count = len(columns)
            # Display all columns, wrapped to multiple lines
            col_text = ', '.join(columns)
            self.detail_columns.setPlainText(f"{col_count} columns:\n{col_text}")
        else:
            self.detail_columns.setPlainText("Default columns")
    
    def clear_details(self):
        """Clear the details area."""
        self.detail_env_id.clear()
        self.detail_client_id.clear()
        self.detail_columns.clear()
    
    def delete_selected(self):
        """Delete the selected profile after confirmation."""
        selected_items = self.profile_list.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        profile_name = item.text().replace(" (active)", "")
        
        # Prevent deleting the current active profile
        if profile_name == self.current_profile:
            QtWidgets.QMessageBox.warning(
                self,
                "Cannot Delete Active Profile",
                f"Profile '{profile_name}' is currently active. Please switch to a different profile before deleting it."
            )
            return
        
        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete Profile",
            f"Are you sure you want to delete profile '{profile_name}'?\n\nThis will remove saved credentials and settings.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            # Remove from dict and track for cleanup
            if profile_name in self.profiles_dict:
                del self.profiles_dict[profile_name]
                self.deleted_profiles.append(profile_name)
            
            # Remove from list widget
            row = self.profile_list.currentRow()
            self.profile_list.takeItem(row)
            
            # Clear details
            self.clear_details()
            
            # Update status
            if self.profile_list.count() == 0:
                QtWidgets.QMessageBox.information(
                    self,
                    "No Profiles",
                    "All profiles have been deleted. You can create a new profile in the Configuration tab."
                )
    
    def create_new_profile(self):
        """Prompt user to create a new profile with connection details."""
        # Get list of existing profile names
        existing_profiles = [k for k in self.profiles_dict.keys() if k != '__meta__']
        
        # Show the new profile dialog
        dialog = NewProfileDialog(existing_profiles, self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        
        # Get the profile data
        profile_name, env_id, client_id, secret = dialog.get_profile_data()
        
        # Create new profile with provided details
        self.profiles_dict[profile_name] = {
            'env_id': env_id,
            'cl_id': client_id,
            'columns': []
        }
        self.new_profile_name = profile_name
        
        # Store credentials if provided (secret will be saved to keyring by main window)
        if secret:
            self.new_profile_credentials = (env_id, client_id, secret)
        
        # Refresh the list and select new profile
        self.populate_profiles()
        
        # Find and select the new profile
        for i in range(self.profile_list.count()):
            item = self.profile_list.item(i)
            if item.text() == profile_name:
                self.profile_list.setCurrentRow(i)
                break
        
        # Show success message and offer to connect if credentials are complete
        if env_id and client_id and secret:
            msg = f"Profile '{profile_name}' has been created with connection details.\n\nWould you like to test the connection now?"
            reply = QtWidgets.QMessageBox.question(
                self,
                "Profile Created",
                msg,
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.Yes
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.auto_connect_requested = True
                # Trigger the connection test if callback is available
                if self.connection_callback:
                    QtCore.QTimer.singleShot(100, self.test_new_profile_connection)
        elif env_id or client_id:
            msg = f"Profile '{profile_name}' has been created.\n\nComplete the configuration in the Configuration tab."
            QtWidgets.QMessageBox.information(
                self,
                "Profile Created",
                msg
            )
        else:
            msg = f"Profile '{profile_name}' has been created.\n\nConfigure connection details in the Configuration tab."
            QtWidgets.QMessageBox.information(
                self,
                "Profile Created",
                msg
            )
    
    def get_deleted_profiles(self) -> list:
        """Return the list of profile names that were deleted."""
        return self.deleted_profiles
    
    def get_new_profile_name(self) -> str:
        """Return the name of a newly created profile, if any."""
        return self.new_profile_name
    
    def get_new_profile_credentials(self) -> tuple:
        """Return credentials for newly created profile: (env_id, client_id, secret) or None."""
        return self.new_profile_credentials
    
    def should_auto_connect(self) -> bool:
        """Return True if user requested to auto-connect to the new profile."""
        return self.auto_connect_requested
    
    def set_connection_callback(self, callback):
        """Set callback function to test connection."""
        self.connection_callback = callback
    
    def test_new_profile_connection(self):
        """Test connection to newly created profile."""
        if self.connection_callback:
            success = self.connection_callback()
            if success:
                # Close the dialog after successful connection
                QtWidgets.QMessageBox.information(
                    self,
                    "Connection Successful",
                    f"Successfully connected to profile '{self.new_profile_name}'.\n\nYou can now manage users in the Users tab."
                )
                self.accept()  # Close the dialog
