"""Reusable Qt dialogs used by the PingOne UserManager UI.

Contains small, focused dialogs for editing user fields, selecting
table columns, and viewing/editing JSON payloads.
"""

import json
import copy
import sys
import re
import platform
import html
from pathlib import Path
from typing import List, Optional, Dict

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


def apply_screen_relative_size(
    dialog: QtWidgets.QDialog,
    min_w: int,
    min_h: int,
    default_w: int,
    default_h: int,
    max_w_ratio: float = 0.72,
    max_h_ratio: float = 0.70,
):
    """Apply min/default sizing while capping footprint to screen-relative bounds."""
    screen = dialog.screen() or QtWidgets.QApplication.primaryScreen()
    if not screen:
        dialog.setMinimumSize(min_w, min_h)
        dialog.resize(default_w, default_h)
        return

    geom = screen.availableGeometry()
    max_w = max(min_w, int(geom.width() * max_w_ratio))
    max_h = max(min_h, int(geom.height() * max_h_ratio))
    target_w = max(min_w, min(default_w, max_w))
    target_h = max(min_h, min(default_h, max_h))

    dialog.setMinimumSize(min_w, min_h)
    dialog.resize(target_w, target_h)


def ensure_dialog_caption_fit(dialog: QtWidgets.QDialog):
    """Adjust dialog width so title/short labels are not cramped."""
    try:
        dialog.adjustSize()
        fm = dialog.fontMetrics()
        title_w = fm.horizontalAdvance(dialog.windowTitle() or "") + scale_size(120)

        # Include short, single-line labels that act like captions in forms.
        caption_w = 0
        for lbl in dialog.findChildren(QtWidgets.QLabel):
            text = (lbl.text() or "").replace('&', '').strip()
            if not text or '\n' in text or len(text) > 48:
                continue
            caption_w = max(caption_w, fm.horizontalAdvance(text))

        target_w = max(
            dialog.minimumWidth(),
            dialog.width(),
            title_w,
            caption_w + scale_size(380),
        )

        screen = dialog.screen() or QtWidgets.QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            max_w = int(geom.width() * 0.86)
            target_w = min(target_w, max_w)

        dialog.setMinimumWidth(target_w)
        dialog.resize(target_w, max(dialog.height(), dialog.minimumHeight()))
    except Exception:
        pass


def apply_combo_typeahead(combo: QtWidgets.QComboBox, options: List[str]):
    """Attach case-insensitive contains-based type-ahead completion to a combo."""
    if not combo.isEditable():
        return
    uniq = sorted({str(o) for o in (options or []) if str(o).strip()})
    completer = QtWidgets.QCompleter(uniq, combo)
    completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
    completer.setFilterMode(QtCore.Qt.MatchContains)
    combo.setCompleter(completer)


class _ClearNoneComboFilter(QtCore.QObject):
    """Clear editable combo text when interacting with a '<None>' placeholder."""

    def __init__(self, combo: QtWidgets.QComboBox):
        super().__init__(combo)
        self.combo = combo
        self.clearing = False

    def eventFilter(self, watched, event):
        # Clear <None> on focus/click
        if event.type() in (QtCore.QEvent.FocusIn, QtCore.QEvent.MouseButtonPress):
            if (self.combo.currentText() or "").strip().lower() == "<none>":
                self.clearing = True
                self.combo.setCurrentIndex(-1)
                self.combo.setEditText("")
                self.clearing = False
        # Clear <None> when user starts typing
        elif event.type() == QtCore.QEvent.KeyPress and not self.clearing:
            if (self.combo.currentText() or "").strip().lower() == "<none>":
                key = event.key()
                text = event.text() or ""
                # Allow printable characters to auto-clear
                if (key >= QtCore.Qt.Key_A and key <= QtCore.Qt.Key_Z) or \
                   (key >= QtCore.Qt.Key_0 and key <= QtCore.Qt.Key_9) or \
                   key in (QtCore.Qt.Key_Period, QtCore.Qt.Key_Underscore, QtCore.Qt.Key_Minus, QtCore.Qt.Key_Space) or \
                   text.isprintable():
                    self.clearing = True
                    self.combo.setCurrentIndex(-1)
                    self.combo.setEditText("")
                    self.clearing = False
        return False


def clear_none_on_interact(combo: QtWidgets.QComboBox):
    """Make '<None>' placeholders disappear when user clicks/focuses the editor."""
    if not combo.isEditable():
        return
    line_edit = combo.lineEdit()
    if not line_edit:
        return
    filt = _ClearNoneComboFilter(combo)
    combo.installEventFilter(filt)
    line_edit.installEventFilter(filt)
    combo._clear_none_filter = filt


class _MappingTableKeyFilter(QtCore.QObject):
    """Handle Enter (move down) and Tab (autocomplete) in mapping tables."""

    def __init__(self, table: QtWidgets.QTableWidget, mapping_col: int = 2):
        super().__init__(table)
        self.table = table
        self.mapping_col = mapping_col

    def _apply_top_completion(self, row: int, column: int) -> bool:
        combo = self.table.cellWidget(row, column)
        if not isinstance(combo, QtWidgets.QComboBox) or not combo.isEditable():
            return False

        completer = combo.completer()
        if not completer:
            return False

        model = completer.completionModel()
        if model is None:
            return False

        idx = model.index(0, 0)
        if not idx.isValid():
            return False

        text = model.data(idx)
        if not text:
            return False

        combo.setEditText(str(text))
        return True

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            if key == QtCore.Qt.Key_Return or key == QtCore.Qt.Key_Enter:
                current_col = self.table.currentColumn()
                current = self.table.currentRow()
                if current >= 0 and current_col == self.mapping_col:
                    self._apply_top_completion(current, current_col)
                # Move focus to same column in next row
                if current >= 0 and current < self.table.rowCount() - 1:
                    self.table.setCurrentCell(current + 1, self.mapping_col)
                return True
            elif key == QtCore.Qt.Key_Tab:
                current = self.table.currentColumn()
                row = self.table.currentRow()
                if row >= 0 and current == self.mapping_col:
                    self._apply_top_completion(row, current)
                    return True
        return False


def apply_mapping_table_keys(table: QtWidgets.QTableWidget, mapping_col: int = 2):
    """Install key event filter for Enter/Tab navigation in mapping columns."""
    filt = _MappingTableKeyFilter(table, mapping_col)
    table.installEventFilter(filt)
    table._key_filter = filt


class _MappingComboKeyFilter(QtCore.QObject):
    """Handle Enter/Tab directly on editable mapping combo editors."""

    def __init__(self, table: QtWidgets.QTableWidget, combo: QtWidgets.QComboBox, mapping_col: int):
        super().__init__(combo)
        self.table = table
        self.combo = combo
        self.mapping_col = mapping_col

    def _find_combo_row(self) -> int:
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, self.mapping_col) is self.combo:
                return row
        return -1

    def _apply_top_completion(self) -> bool:
        completer = self.combo.completer()
        if not completer:
            return False
        model = completer.completionModel()
        if model is None:
            return False
        idx = model.index(0, 0)
        if not idx.isValid():
            return False
        text = model.data(idx)
        if not text:
            return False
        self.combo.setEditText(str(text))
        return True

    def eventFilter(self, watched, event):
        if event.type() != QtCore.QEvent.KeyPress:
            return False

        key = event.key()
        if key not in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter, QtCore.Qt.Key_Tab):
            return False

        row = self._find_combo_row()
        if row < 0:
            return False

        self._apply_top_completion()

        if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter) and row < self.table.rowCount() - 1:
            self.table.setCurrentCell(row + 1, self.mapping_col)

        return True


def apply_mapping_combo_keys(table: QtWidgets.QTableWidget, combo: QtWidgets.QComboBox, mapping_col: int):
    """Install Enter/Tab completion handling on an editable mapping combo."""
    if not combo.isEditable() or not combo.lineEdit():
        return
    filt = _MappingComboKeyFilter(table, combo, mapping_col)
    combo.installEventFilter(filt)
    combo.lineEdit().installEventFilter(filt)
    combo._mapping_key_filter = filt


class EditUserDialog(QtWidgets.QDialog):
    """Dialog for editing user information."""
    def __init__(self, user_data, pop_map, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit User")
        self.setModal(True)
        
        # Set minimum size based on DPI
        dpi_scale = get_dpi_scale()
        self.setMinimumSize(scale_size(450, dpi_scale), scale_size(500, dpi_scale))
        
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # Editable fields section
        layout = QtWidgets.QFormLayout()
        
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
        
        main_layout.addLayout(layout)
        
        # Show all populated attributes section in a clean table-like view
        all_attrs = self._get_all_populated_attributes(user_data)
        if all_attrs:
            separator = QtWidgets.QLabel("All User Attributes:")
            separator.setStyleSheet("font-weight: bold; margin-top: 10px;")
            main_layout.addWidget(separator)

            attrs_table = QtWidgets.QTableWidget(len(all_attrs), 2)
            attrs_table.setHorizontalHeaderLabels(["Attribute", "Value"])
            attrs_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            attrs_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            attrs_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            attrs_table.setAlternatingRowColors(True)
            attrs_table.verticalHeader().setVisible(False)
            attrs_table.horizontalHeader().setStretchLastSection(True)
            attrs_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            attrs_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
            attrs_table.setWordWrap(False)
            attrs_table.setMaximumHeight(220)

            for row, (key, value) in enumerate(all_attrs):
                key_item = QtWidgets.QTableWidgetItem(str(key))
                key_item.setFlags(key_item.flags() & ~QtCore.Qt.ItemIsEditable)
                value_item = QtWidgets.QTableWidgetItem(str(value))
                value_item.setFlags(value_item.flags() & ~QtCore.Qt.ItemIsEditable)
                attrs_table.setItem(row, 0, key_item)
                attrs_table.setItem(row, 1, value_item)

            main_layout.addWidget(attrs_table)
        
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
        main_layout.addWidget(buttons)
        
        self.user_data = user_data
        self.pop_map = pop_map
        ensure_dialog_caption_fit(self)
    
    def _get_all_populated_attributes(self, user_data):
        """Return populated attributes as (key, value) rows for display.

        Results are sorted alphabetically by the flattened attribute key.
        Attributes whose values look like HTTP links or JSON objects/arrays
        are excluded to keep the view clean.
        """
        _LINK_PREFIXES = ('http://', 'https://', '{', '[')

        def _is_link_or_json(text: str) -> bool:
            t = text.strip().lower()
            return any(t.startswith(p.lower()) for p in _LINK_PREFIXES)

        def format_dict(d, prefix=""):
            result = []
            for key, value in sorted(d.items()):
                full_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    if value:
                        result.extend(format_dict(value, full_key))
                elif isinstance(value, list):
                    if value:
                        for i, item in enumerate(value):
                            item_key = f"{full_key}[{i}]"
                            if isinstance(item, dict):
                                result.extend(format_dict(item, item_key))
                            elif item is not None and item != "":
                                s = str(item)
                                if not _is_link_or_json(s):
                                    result.append((item_key, s))
                elif value is not None and value != "":
                    s = str(value)
                    if not _is_link_or_json(s):
                        result.append((full_key, s))
            return result

        raw = format_dict(user_data)
        # Guarantee global alphabetical order by flattened key name.
        return sorted(raw, key=lambda t: t[0].lower())
    
    def get_data(self):
        """Return the updated user data from the dialog."""
        # Start from existing user data so a PUT update preserves
        # populated attributes that are not editable in this dialog.
        data = copy.deepcopy(self.user_data) if isinstance(self.user_data, dict) else {}

        pop_name = self.population.currentText()
        pop_id = next((k for k, v in self.pop_map.items() if v == pop_name), '')

        data["username"] = self.username.text()
        data["email"] = self.email.text()
        data["name"] = {
            "given": self.first_name.text(),
            "family": self.last_name.text(),
        }
        data["population"] = {"id": pop_id}

        if self.phone.text():
            data["phoneNumbers"] = [{"number": self.phone.text(), "type": "mobile"}]
        else:
            data.pop("phoneNumbers", None)

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
        else:
            data.pop("address", None)
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
        ensure_dialog_caption_fit(self)
    
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
        ensure_dialog_caption_fit(self)
    
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
        ensure_dialog_caption_fit(self)

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
    """CSV/LDIF mapping dialog aligned with the database mapping experience.

    Presents a table-first mapper with source columns, sample values, and a
    target PingOne attribute combo. Returns
    ``(mapping, fixed_population_id, fixed_enabled, remember_mapping)``.
    """

    def __init__(
        self,
        headers,
        parent=None,
        pop_map: dict = None,
        initial_mapping: dict = None,
        initial_fixed_pop_id: str = None,
        initial_fixed_enabled=None,
        pingone_attrs: Optional[List[str]] = None,
        sample_row: Optional[dict] = None,
        client=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("CSV Mapping")
        self.setModal(True)

        dpi_scale = get_dpi_scale()
        apply_screen_relative_size(
            self,
            scale_size(760, dpi_scale),
            scale_size(360, dpi_scale),
            scale_size(900, dpi_scale),
            scale_size(540, dpi_scale),
            max_w_ratio=0.76,
            max_h_ratio=0.68,
        )

        layout = QtWidgets.QVBoxLayout(self)
        direction_label = QtWidgets.QLabel("File column -> PingOne attribute")
        direction_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(direction_label)

        self.headers = list(headers or [])
        self.pop_map = pop_map or {}
        self.initial_mapping = dict(initial_mapping or {})
        self.sample_row = sample_row or {}
        self.client = client
        self.initial_fixed_pop_id = initial_fixed_pop_id

        base_attrs = [
            'username', 'email', 'name.given', 'name.middle', 'name.family',
            'population.id', 'population.name', 'enabled',
            'phoneNumbers.mobile', 'phoneNumbers.work', 'phoneNumbers.home',
            'employeeType', 'type',
            'address.streetAddress', 'address.locality', 'address.region',
            'address.postalCode', 'address.countryCode', 'address.country',
            'title', 'department', 'organization', 'id',
        ]
        self.pingone_attrs = sorted({*(pingone_attrs or []), *base_attrs})

        # Auto-filter checkbox for link attributes
        self.auto_filter_links_cb = QtWidgets.QCheckBox("Auto-remove link attributes (URLs, JSON objects)")
        self.auto_filter_links_cb.setChecked(True)
        self.auto_filter_links_cb.setToolTip("Automatically filter out columns containing http://, https://, or starting with {")
        self.auto_filter_links_cb.stateChanged.connect(self._rebuild_table)
        layout.addWidget(self.auto_filter_links_cb)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Column Name", "Sample Value", "PingOne Attribute"])
        # Enable multi-row selection
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        
        self._populate_table()

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)

        apply_mapping_table_keys(self.table, mapping_col=2)
        layout.addWidget(self.table)

        row_actions = QtWidgets.QHBoxLayout()
        add_row_btn = QtWidgets.QPushButton("Add Row")
        add_row_btn.setToolTip("Add a manual mapping row")
        add_row_btn.clicked.connect(self._add_manual_row)
        del_row_btn = QtWidgets.QPushButton("Delete Row")
        del_row_btn.setToolTip("Delete selected mapping row(s)")
        del_row_btn.clicked.connect(self._delete_selected_rows)
        row_actions.addWidget(add_row_btn)
        row_actions.addWidget(del_row_btn)
        row_actions.addStretch()
        layout.addLayout(row_actions)

        options_group = QtWidgets.QGroupBox("Import Options")
        options_form = QtWidgets.QFormLayout(options_group)

        # Population combo with refresh button
        pop_layout = QtWidgets.QHBoxLayout()
        self.population_fixed = QtWidgets.QComboBox()
        self.population_fixed.addItem("<Use mapped CSV column>", None)
        for name, pid in sorted(self.pop_map.items(), key=lambda x: x[0].lower()):
            self.population_fixed.addItem(f"{name} ({pid})", pid)
        if initial_fixed_pop_id:
            idx = self.population_fixed.findData(initial_fixed_pop_id)
            if idx != -1:
                self.population_fixed.setCurrentIndex(idx)
        pop_layout.addWidget(self.population_fixed)
        
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.setToolTip("Query PingOne for updated population list")
        refresh_btn.clicked.connect(self._refresh_populations)
        # Only enable if client is available
        refresh_btn.setEnabled(self.client is not None)
        pop_layout.addWidget(refresh_btn)
        
        options_form.addRow("Fixed population:", pop_layout)

        self.enabled_field = QtWidgets.QComboBox()
        self.enabled_field.addItem("<Use mapped CSV column>", None)
        self.enabled_field.addItem("<Fixed: true>", True)
        self.enabled_field.addItem("<Fixed: false>", False)
        if initial_fixed_enabled is True:
            idx = self.enabled_field.findData(True)
            if idx != -1:
                self.enabled_field.setCurrentIndex(idx)
        elif initial_fixed_enabled is False:
            idx = self.enabled_field.findData(False)
            if idx != -1:
                self.enabled_field.setCurrentIndex(idx)

        options_form.addRow("Fixed population:", self.population_fixed)
        options_form.addRow("Fixed enabled:", self.enabled_field)
        layout.addWidget(options_group)

        self.remember_cb = QtWidgets.QCheckBox("Remember mapping for this profile")
        self.remember_cb.setChecked(False)
        layout.addWidget(self.remember_cb)

        note = QtWidgets.QLabel("Note: ID values are system-generated and ignored during import.")
        note.setWordWrap(True)
        note.setStyleSheet('color: #555; font-style: italic;')
        layout.addWidget(note)

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
        ensure_dialog_caption_fit(self)

    def _normalize_mapping_token(self, value: str) -> str:
        token = str(value or '').strip().lower()
        return ''.join(ch for ch in token if ch.isalnum())

    def _suggest_pingone_attr(self, source_name: str) -> str:
        """Suggest a target attribute using exact token matching and aliases."""
        source = str(source_name or '').strip()
        normalized_source = self._normalize_mapping_token(source)
        if not normalized_source:
            return ''

        alias_map = {
            'firstname': 'name.given',
            'givenname': 'name.given',
            'middlename': 'name.middle',
            'middleinitial': 'name.middle',
            'lastname': 'name.family',
            'familyname': 'name.family',
            'uid': 'username',
            'mobilenumber': 'phoneNumbers.mobile',
            'worknumber': 'phoneNumbers.work',
            'homenumber': 'phoneNumbers.home',
            'mobilephone': 'phoneNumbers.mobile',
            'workphone': 'phoneNumbers.work',
            'homephone': 'phoneNumbers.home',
            'employeetype': 'employeeType',
            'employmenttype': 'employeeType',
            'street': 'address.streetAddress',
            'streetaddress': 'address.streetAddress',
            'addressline1': 'address.streetAddress',
            'city': 'address.locality',
            'state': 'address.region',
            'province': 'address.region',
            'region': 'address.region',
            'postalcode': 'address.postalCode',
            'zipcode': 'address.postalCode',
            'zip': 'address.postalCode',
            'country': 'address.countryCode',
            'population': 'population.id',
        }
        if normalized_source in alias_map:
            candidate = alias_map[normalized_source]
            candidate_norm = self._normalize_mapping_token(candidate)
            for attr in self.pingone_attrs:
                if self._normalize_mapping_token(attr) == candidate_norm:
                    return attr
            return candidate

        for attr in self.pingone_attrs:
            if self._normalize_mapping_token(attr) == normalized_source:
                return attr
        return ''

    def _refresh_populations(self):
        """Query PingOne for updated population list and refresh the combo box."""
        if not self.client:
            QtWidgets.QMessageBox.warning(
                self, 
                "Refresh Populations", 
                "No API client available. Cannot refresh populations."
            )
            return
        
        try:
            # Get current selection to try to restore it
            current_pop_id = self.population_fixed.currentData()
            
            # Show wait cursor
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
            
            # Query PingOne for updated populations
            import asyncio
            token = asyncio.run(self.client.get_token())
            if token:
                new_pops, _ = asyncio.run(self.client.get_populations())
                self.pop_map = new_pops or {}
                
                # Rebuild the combo box
                self.population_fixed.clear()
                self.population_fixed.addItem("<Use mapped CSV column>", None)
                for name, pid in sorted(self.pop_map.items(), key=lambda x: x[0].lower()):
                    self.population_fixed.addItem(f"{name} ({pid})", pid)
                
                # Try to restore previous selection
                if current_pop_id:
                    idx = self.population_fixed.findData(current_pop_id)
                    if idx != -1:
                        self.population_fixed.setCurrentIndex(idx)
                    else:
                        # Previous selection no longer exists, try to restore from initial
                        if self.initial_fixed_pop_id:
                            idx = self.population_fixed.findData(self.initial_fixed_pop_id)
                            if idx != -1:
                                self.population_fixed.setCurrentIndex(idx)
                
                QtWidgets.QMessageBox.information(
                    self,
                    "Refresh Populations",
                    f"Successfully refreshed population list. Found {len(self.pop_map)} population(s)."
                )
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Refresh Populations",
                    "Failed to authenticate with PingOne. Please check your credentials."
                )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Refresh Populations",
                f"Failed to refresh populations: {str(e)}"
            )
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def get_mapping(self):
        mapping = {}
        for row in range(self.table.rowCount()):
            src_item = self.table.item(row, 0)
            combo = self.table.cellWidget(row, 2)
            if not src_item or combo is None:
                continue
            src = src_item.text().strip()
            dst = combo.currentText().strip()
            if src and dst and dst != "<None>":
                mapping[src] = dst

        fixed_pop_id = self.population_fixed.currentData()
        fixed_enabled = self.enabled_field.currentData()
        remember = bool(self.remember_cb.isChecked())
        return mapping, fixed_pop_id, fixed_enabled, remember

    def _add_manual_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(""))
        self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(""))
        combo = QtWidgets.QComboBox()
        combo.setEditable(True)
        combo.addItem("<None>")
        combo.addItems(self.pingone_attrs)
        combo.setPlaceholderText("Select or type attribute name")
        apply_combo_typeahead(combo, self.pingone_attrs)
        clear_none_on_interact(combo)
        apply_mapping_combo_keys(self.table, combo, 2)
        self.table.setCellWidget(row, 2, combo)

    def _should_filter_column(self, col_name: str, sample_value: str = '') -> bool:
        """Check if a column should be filtered out based on link content."""
        if not self.auto_filter_links_cb.isChecked():
            return False
        
        # Check column name
        col_lower = str(col_name).lower()
        if col_lower.startswith('_links') or col_lower.startswith('_embedded'):
            return True
        
        # Check sample value for URLs or JSON
        val_str = str(sample_value).strip()
        if val_str.startswith('http://') or val_str.startswith('https://') or val_str.startswith('{'):
            return True
        
        return False

    def _rebuild_table(self):
        """Rebuild table when filter state changes."""
        self._populate_table()

    def _populate_table(self):
        """Populate the mapping table with headers and combos."""
        # Store current mapping before rebuilding
        current_mapping = {}
        for row in range(self.table.rowCount()):
            col_item = self.table.item(row, 0)
            combo = self.table.cellWidget(row, 2)
            if col_item and isinstance(combo, QtWidgets.QComboBox):
                current_mapping[col_item.text()] = combo.currentText()
        
        # Filter headers if needed
        headers_to_show = []
        for hdr in self.headers:
            val = self.sample_row.get(hdr, "") if isinstance(self.sample_row, dict) else ""
            if isinstance(val, (dict, list)):
                try:
                    val = json.dumps(val)
                except Exception:
                    val = str(val)
            if not self._should_filter_column(hdr, str(val)):
                headers_to_show.append(hdr)
        
        self.table.setRowCount(len(headers_to_show))
        
        for i, hdr in enumerate(headers_to_show):
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(hdr))

            val = self.sample_row.get(hdr, "") if isinstance(self.sample_row, dict) else ""
            if isinstance(val, (dict, list)):
                try:
                    val = json.dumps(val)
                except Exception:
                    val = str(val)
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(val) if val is not None else ""))

            combo = QtWidgets.QComboBox()
            combo.setEditable(True)
            combo.addItem("<None>")
            combo.addItems(self.pingone_attrs)
            combo.setPlaceholderText("Select or type attribute name")
            apply_combo_typeahead(combo, self.pingone_attrs)
            clear_none_on_interact(combo)
            apply_mapping_combo_keys(self.table, combo, 2)

            # Restore or apply mapping
            if hdr in current_mapping:
                combo.setCurrentText(current_mapping[hdr])
            elif self.initial_mapping and isinstance(self.initial_mapping, dict):
                mapped = self.initial_mapping.get(hdr)
                if mapped:
                    idx = combo.findText(mapped)
                    if idx != -1:
                        combo.setCurrentIndex(idx)
                    else:
                        combo.setEditText(str(mapped))
            else:
                suggested = self._suggest_pingone_attr(hdr)
                if suggested:
                    idx = combo.findText(suggested)
                    if idx != -1:
                        combo.setCurrentIndex(idx)
                    else:
                        combo.setEditText(suggested)

            self.table.setCellWidget(i, 2, combo)

    def _delete_selected_rows(self):
        rows = sorted({idx.row() for idx in self.table.selectionModel().selectedRows()}, reverse=True)
        if not rows and self.table.currentRow() >= 0:
            rows = [self.table.currentRow()]
        for row in rows:
            self.table.removeRow(row)


# -- database connection/dialog classes -------------------------------------------------

class DatabaseConnectionDialog(QtWidgets.QDialog):
    """Dialog for creating or editing a database connection definition.

    Fields include connection name, type (MSSQL, MySQL, Oracle), host/port/db,
    credentials, and JDBC driver path. Provides a "Test
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
        # MySQL is the default entry
        self.type_combo.addItems(["MySQL", "MSSQL", "Oracle"])
        self.encrypt_combo = QtWidgets.QComboBox()
        self.encrypt_combo.addItems(["Auto", "On", "Off"])
        self.encrypt_combo.setToolTip(
            "MSSQL only:\n"
            "- Auto: Try TLS first, then retry without encryption if handshake fails\n"
            "- On: Require TLS\n"
            "- Off: Disable TLS"
        )
        self.host_edit = QtWidgets.QLineEdit()
        self.host_edit.setPlaceholderText("hostname or IP")
        self.host_edit.setToolTip("Database server host")
        self.port_edit = QtWidgets.QLineEdit()
        self.port_edit.setValidator(QtGui.QIntValidator(1, 65535))
        self.port_edit.setPlaceholderText("port number")
        self.port_edit.setToolTip("TCP port for the database service")
        self.db_combo = QtWidgets.QComboBox()
        self.db_combo.setEditable(True)
        self.db_combo.lineEdit().setPlaceholderText("database name")
        self.db_combo.setToolTip("Name of the target database")
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
        # path to JDBC .jar file for the selected DB type
        self.driver_combo = QtWidgets.QComboBox()
        self.driver_combo.setEditable(True)
        self.driver_combo.setPlaceholderText("JDBC .jar path")
        self.driver_combo.setToolTip(
            "JDBC-only support:\n"
            "- MSSQL: mssql-jdbc-*.jar\n"
            "- MySQL: mysql-connector-j-*.jar\n"
            "- Oracle: ojdbc*.jar\n"
            "Python prerequisite: pip install jaydebeapi JPype1"
        )
        # label to display the currently selected driver for clarity
        self.driver_label = QtWidgets.QLabel("")
        self.driver_combo.currentTextChanged.connect(self._update_driver_label)
        # populate with sensible defaults (will be refreshed on type change)
        self._set_driver_options()

        # update port field whenever type changes
        self.type_combo.currentTextChanged.connect(self._update_port_default)
        # refresh driver name suggestions when type changes
        self.type_combo.currentTextChanged.connect(self._set_driver_options)
        # refresh encrypt-mode availability when type changes
        self.type_combo.currentTextChanged.connect(self._update_encrypt_mode_state)
        # update JDBC string when type changes
        self.type_combo.currentTextChanged.connect(self._update_jdbc_string)
        self.encrypt_combo.currentTextChanged.connect(self._update_jdbc_string)
        # update JDBC string when host/db/port change
        self.host_edit.textChanged.connect(self._update_jdbc_string)
        self.port_edit.textChanged.connect(self._update_jdbc_string)
        self.db_combo.currentTextChanged.connect(self._update_jdbc_string)
        drv_layout = QtWidgets.QHBoxLayout()
        drv_layout.addWidget(self.driver_combo, 1)
        browse_drv_btn = QtWidgets.QPushButton("Browse…")
        browse_drv_btn.setToolTip("Browse for a JDBC .jar file")
        browse_drv_btn.clicked.connect(self._browse_jar)
        drv_layout.addWidget(browse_drv_btn)

        form.addRow("Name:", self.name_edit)
        form.addRow("Type:", self.type_combo)
        form.addRow("Encrypt Mode:", self.encrypt_combo)
        form.addRow("Host:", self.host_edit)
        form.addRow("Port:", self.port_edit)
        db_row = QtWidgets.QHBoxLayout()
        db_row.addWidget(self.db_combo, 1)
        self.db_fetch_btn = QtWidgets.QPushButton("Fetch Databases")
        self.db_fetch_btn.setToolTip("Fetch available databases from the server (requires SHOW DATABASES privilege)")
        self.db_fetch_btn.clicked.connect(self._populate_databases)
        db_row.addWidget(self.db_fetch_btn)
        form.addRow("Database:", db_row)
        # table selector will be populated after a successful connection test
        self.table_combo = QtWidgets.QComboBox()
        self.table_combo.setEditable(True)
        self.table_combo.lineEdit().setPlaceholderText("(run Test Connection to populate)")
        self.table_combo.setEnabled(False)
        table_row = QtWidgets.QHBoxLayout()
        table_row.addWidget(self.table_combo, 1)
        self.table_refresh_btn = QtWidgets.QPushButton("Refresh Tables")
        self.table_refresh_btn.setToolTip("Refresh table list from server")
        self.table_refresh_btn.clicked.connect(self._populate_tables)
        table_row.addWidget(self.table_refresh_btn)
        form.addRow("Table:", table_row)
        form.addRow("User:", self.user_edit)
        pw_row = QtWidgets.QHBoxLayout()
        pw_row.addWidget(self.pw_edit, 1)
        self.show_pw_btn = QtWidgets.QPushButton("Show")
        self.show_pw_btn.setCheckable(True)
        self.show_pw_btn.setToolTip("Show or hide password")
        self.show_pw_btn.toggled.connect(self._toggle_password_visibility)
        pw_row.addWidget(self.show_pw_btn)
        form.addRow("Password:", pw_row)
        form.addRow("Driver:", drv_layout)
        # show the selected driver name below the driver field
        form.addRow("", self.driver_label)
        # readonly JDBC URL preview placed at the bottom so it stretches
        form.addRow("JDBC URL:", self.jdbc_edit)

        layout.addLayout(form)

        # initialize port based on current type (combo default may already be set)
        self._update_port_default()
        self._update_encrypt_mode_state()
        # ensure JDBC string is populated as well
        self._update_jdbc_string()

        action_row = QtWidgets.QHBoxLayout()
        test_btn = QtWidgets.QPushButton("Test Connection")
        test_btn.clicked.connect(self._on_test)
        new_btn = QtWidgets.QPushButton("New Connection")
        new_btn.setToolTip("Clear fields so you can enter a new database connection")
        new_btn.clicked.connect(self._new_connection)
        action_row.addWidget(test_btn)
        action_row.addWidget(new_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        # status label shows progress/result of connection test
        self.status_label = QtWidgets.QLabel("")
        layout.addWidget(self.status_label)

        # sample data display (shown after successful test with table selected)
        self.sample_label = QtWidgets.QLabel("")
        self.sample_label.setWordWrap(True)
        self.sample_label.setStyleSheet("background-color: #f0f0f0; padding: 8px; border-radius: 4px; font-family: Monaco; font-size: 10px;")
        self.sample_label.setVisible(False)
        layout.addWidget(self.sample_label)

        # allow user to choose whether this connection should be saved
        self.save_cb = QtWidgets.QCheckBox("Save this connection")
        self.save_cb.setChecked(True)
        layout.addWidget(self.save_cb)

        # button layout with OK, Cancel, and Use This Connection
        btn_layout = QtWidgets.QHBoxLayout()
        use_btn = QtWidgets.QPushButton("Use This Connection")
        use_btn.setToolTip("Use this connection and close the dialog")
        use_btn.clicked.connect(self._on_use)
        self.use_btn = use_btn
        
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        
        btn_layout.addWidget(use_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(btns)
        layout.addLayout(btn_layout)

        if initial:
            self.name_edit.setText(initial.get('name', ''))
            initial_type = initial.get('type', 'MySQL')
            if initial_type == 'MariaDB/MySQL':
                initial_type = 'MySQL'
            self.type_combo.setCurrentText(initial_type)
            self.host_edit.setText(initial.get('host', ''))
            self.port_edit.setText(str(initial.get('port', '')))
            self.db_combo.setCurrentText(initial.get('database', ''))
            self.user_edit.setText(initial.get('user', ''))
            self.pw_edit.setText(initial.get('password', ''))
            self.driver_combo.setCurrentText(initial.get('driver', ''))
            self.encrypt_combo.setCurrentText(str(initial.get('encrypt_mode', 'Auto')).title())
            # do not prefill the table combo when editing; user must test
            # the connection in order to refresh and choose a table
            # rebuild JDBC string from loaded values
            self._update_encrypt_mode_state()
            self._update_jdbc_string()
            # if editing an existing connection, focus name field for convenience
            self.name_edit.setFocus()
        ensure_dialog_caption_fit(self)

    # browsing is no longer required since driver is entered via combo
    # kept for historical reference but not used
    def _browse_driver(self):
        pass

    def _browse_jar(self):
        """Open a file dialog to select a JDBC .jar file."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select JDBC .jar File",
            "",
            "JDBC Driver (*.jar);;All Files (*)",
        )
        if path:
            self.driver_combo.setCurrentText(path)
            self._update_driver_label(path)

    def _validate_and_accept(self):
        """Ensure required fields are present before closing dialog."""
        name = self.name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Invalid Name", "Connection name cannot be empty.")
            self.name_edit.setFocus()
            return
        host = self.host_edit.text().strip()
        db = self.db_combo.currentText().strip()
        if not host or not db:
            QtWidgets.QMessageBox.warning(self, "Missing Details", "Host and database name are required.")
            if not host:
                self.host_edit.setFocus()
            else:
                self.db_combo.setFocus()
            return
        # everything seems fine
        self.accept()

    def _update_port_default(self):
        # called when the type combo changes
        typ = self.type_combo.currentText()
        if typ == "MySQL":
            default = "3306"
        elif typ == "Oracle":
            default = "1521"
        else:
            default = "1433"
        if not self.port_edit.text():
            self.port_edit.setText(default)
        # also refresh JDBC url whenever port default changes
        self._update_jdbc_string()

    def _update_driver_label(self, text: str):
        """Update the helper label to show the currently selected driver."""
        if text:
            self.driver_label.setText(f"Selected driver: {text}")
        else:
            self.driver_label.setText("")

    def _set_driver_options(self):
        """Populate the driver combo with sensible defaults for the selected DB.

        The combo is always editable so the user may enter an absolute path,
        while the dropdown offers typical JDBC jar filenames as guidance.

        After repopulating we update the display label as well.
        """
        typ = self.type_combo.currentText()
        self.driver_combo.clear()
        if typ == "MySQL":
            self.driver_combo.addItems([
                "drivers/mysql/mysql-connector-j-9.0.0.jar",
                "drivers/mysql/mysql-connector-j-8.4.0.jar",
            ])
        elif typ == "Oracle":
            self.driver_combo.addItems([
                "drivers/oracle/ojdbc11.jar",
                "drivers/oracle/ojdbc8.jar",
            ])
        else:
            self.driver_combo.addItems([
                "drivers/mssql/mssql-jdbc-12.6.1.jre11.jar",
                "drivers/mssql/mssql-jdbc-12.6.1.jre8.jar",
            ])
        # update label after changing options
        if hasattr(self, 'driver_label'):
            self._update_driver_label(self.driver_combo.currentText())

    def _update_encrypt_mode_state(self):
        """Enable encrypt mode controls only for MSSQL connections."""
        is_mssql = self.type_combo.currentText() == "MSSQL"
        self.encrypt_combo.setEnabled(is_mssql)

    def _update_jdbc_string(self):
        """Build a JDBC connection string from the current fields.

        The string is shown in the read‑only ``jdbc_edit`` so the user can
        copy it or verify the syntax.  It updates whenever the type, host,
        port or database fields change.
        """
        typ = self.type_combo.currentText()
        host = self.host_edit.text().strip()
        if typ == "MySQL":
            fallback_port = "3306"
        elif typ == "Oracle":
            fallback_port = "1521"
        else:
            fallback_port = "1433"
        port = self.port_edit.text().strip() or fallback_port
        db = self.db_combo.currentText().strip()
        url = ""
        if host and db:
            if typ == "MySQL":
                url = f"jdbc:mysql://{host}:{port}/{db}"
            elif typ == "Oracle":
                url = f"jdbc:oracle:thin:@//{host}:{port}/{db}"
            else:
                mode = self.encrypt_combo.currentText()
                if mode == "Off":
                    suffix = ";encrypt=false"
                else:
                    suffix = ";encrypt=true;trustServerCertificate=true"
                url = f"jdbc:sqlserver://{host}:{port};databaseName={db}{suffix}"
        self.jdbc_edit.setText(url)

    def _populate_tables(self):
        # attempt to list tables and fill combo - called after a successful test
        try:
            from api import db_utils
        except ModuleNotFoundError:
            # if sqlalchemy isn't installed there's nothing to do
            return

        try:
            db_name = self.db_combo.currentText().strip()
            if not db_name:
                self.status_label.setText("Database name is required to list tables.")
                return
            
            names = db_utils.get_table_names(
                self.type_combo.currentText(),
                self.host_edit.text(),
                int(self.port_edit.text() or 0),
                db_name,
                self.user_edit.text(),
                self.pw_edit.text(),
                self.driver_combo.currentText() or None,
                self.encrypt_combo.currentText(),
            )
            # Strip whitespace and coerce to Python str to prevent Qt/JPype conversion errors
            names = [str(name).strip() for name in names if str(name).strip()]
            self.table_combo.clear()
            self.table_combo.addItems(names)
            self.table_combo.setEnabled(bool(names))
            if names:
                self.status_label.setText(f"Found {len(names)} table(s).")
            else:
                self.status_label.setText("No tables found.")
        except Exception as e:
            # Show error so user can debug
            self.status_label.setText(f"Failed to read table metadata: {e}")
            self.table_combo.clear()
            self.table_combo.setEnabled(False)

    def _on_test(self):
        # show busy cursor and status while testing
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        self.status_label.setText("Testing connection...")
        self.sample_label.setVisible(False)
        QtWidgets.QApplication.processEvents()
        try:
            from api import db_utils
        except ModuleNotFoundError:
            self._show_copyable_message(
                "Missing Dependency",
                "SQLAlchemy is not installed. Please install the requirements and restart (e.g. pip install -r requirements.txt).",
                icon=QtWidgets.QMessageBox.Critical,
            )
            QtWidgets.QApplication.restoreOverrideCursor()
            self.status_label.setText("Dependency missing.")
            return

        port = int(self.port_edit.text() or 0)
        ok, err = db_utils.test_connection(
            self.type_combo.currentText(),
            self.host_edit.text(),
            port,
            self.db_combo.currentText(),
            self.user_edit.text(),
            self.pw_edit.text(),
            self.driver_combo.currentText() or None,
            self.encrypt_combo.currentText(),
        )
        QtWidgets.QApplication.restoreOverrideCursor()
        if ok:
            self.status_label.setText("Connection successful.")
            self._populate_tables()
            # If a table is selected, fetch and display the first record
            self._show_sample_data(db_utils)
        else:
            self.status_label.setText("Connection failed.")
            # clear any previous table list so the user must retest
            self.table_combo.clear()
            self.table_combo.setEnabled(False)
            # show detailed error so user can debug
            msg = "Failed to connect to database."
            if err:
                # Check if this is a missing driver error
                if "pip install" in err and "jaydebeapi" in err:
                    # Format as HTML with clickable links for better readability
                    msg = self._format_driver_error(err)
                else:
                    msg += f"\n\nError details:\n{err}"
            
            # Use a message box that supports HTML/links if it's a driver error
            if "https://" in msg:
                self._show_copyable_message(
                    "Missing Database Driver",
                    msg,
                    icon=QtWidgets.QMessageBox.Critical,
                    rich_text=True,
                )
            else:
                self._show_copyable_message(
                    "Test Connection",
                    msg,
                    icon=QtWidgets.QMessageBox.Critical,
                )

    def _show_sample_data(self, db_utils):
        """Fetch and display the first record from the selected table."""
        if not self.table_combo.currentText():
            self.sample_label.setVisible(False)
            return
        
        try:
            sample = db_utils.get_table_sample(
                self.type_combo.currentText(),
                self.host_edit.text(),
                int(self.port_edit.text() or 0),
                self.db_combo.currentText(),
                self.user_edit.text(),
                self.pw_edit.text(),
                self.table_combo.currentText(),
                self.driver_combo.currentText() or None,
                self.encrypt_combo.currentText(),
            )
            if sample:
                # Format the sample row in horizontal layout
                parts = ["<b>First Record:</b>"]
                for key, value in sample.items():
                    parts.append(f"<b>{key}:</b> {value}")
                self.sample_label.setText(" | ".join(parts))
                self.sample_label.setVisible(True)
            else:
                self.sample_label.setText("<i>Table is empty.</i>")
                self.sample_label.setVisible(True)
        except Exception as e:
            self.sample_label.setText(f"<i>Could not fetch sample: {str(e)}</i>")
            self.sample_label.setVisible(True)

    def _format_driver_error(self, error_msg: str) -> str:
        """Convert driver/setup guidance into safe HTML for display."""
        raw = str(error_msg or '').strip()
        # Strip Qt/RichText export CSS noise if a rich text fragment was passed back.
        raw = re.sub(r'^\s*p,\s*li\s*\{[^\n]*\}\s*', '', raw, flags=re.IGNORECASE)
        raw = re.sub(r'^\s*hr\s*\{[^\n]*\}\s*', '', raw, flags=re.IGNORECASE)
        raw = re.sub(r'^\s*li\.unchecked::marker\s*\{[^\n]*\}\s*', '', raw, flags=re.IGNORECASE)
        raw = re.sub(r'^\s*li\.checked::marker\s*\{[^\n]*\}\s*', '', raw, flags=re.IGNORECASE)
        # Convert markdown-style links to plain URLs before HTML escaping/linking.
        raw = re.sub(r'\[([^\]]+?)\]\((https?://[^\s)]+)\)', r'\2', raw)
        # Remove markdown emphasis markers.
        raw = raw.replace('**', '')

        html_msg = html.escape(raw).replace('\n', '<br>')
        # Highlight pip install commands
        html_msg = re.sub(
            r'(pip install [^\n<]+)',
            r'<code style="background-color: #f0f0f0; padding: 2px 4px;">\1</code>',
            html_msg
        )
        # Create clickable links for URLs
        html_msg = re.sub(
            r'(https://[^<\s\n]+)',
            r'<a href="\1" style="color: #0066cc; text-decoration: underline;">\1</a>',
            html_msg
        )
        return html_msg

    def _show_copyable_message(
        self,
        title: str,
        message: str,
        *,
        icon=QtWidgets.QMessageBox.Critical,
        rich_text: bool = False,
    ):
        """Show a selectable/clickable message dialog without Qt auto-format surprises."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setModal(True)

        layout = QtWidgets.QVBoxLayout(dlg)

        header = QtWidgets.QHBoxLayout()
        icon_label = QtWidgets.QLabel()
        pixmap = self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxCritical).pixmap(32, 32)
        if icon == QtWidgets.QMessageBox.Warning:
            pixmap = self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxWarning).pixmap(32, 32)
        elif icon == QtWidgets.QMessageBox.Information:
            pixmap = self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation).pixmap(32, 32)
        icon_label.setPixmap(pixmap)
        header.addWidget(icon_label, 0, QtCore.Qt.AlignTop)

        body_container = QtWidgets.QVBoxLayout()
        if rich_text:
            viewer = QtWidgets.QTextBrowser(dlg)
            viewer.setOpenExternalLinks(True)
            viewer.setHtml(self._format_driver_error(message))
        else:
            viewer = QtWidgets.QPlainTextEdit(dlg)
            viewer.setPlainText(str(message or ''))
        viewer.setReadOnly(True)
        body_container.addWidget(viewer)
        header.addLayout(body_container, 1)
        layout.addLayout(header)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok, parent=dlg)
        btns.accepted.connect(dlg.accept)
        layout.addWidget(btns)

        try:
            screen = dlg.screen() or QtWidgets.QApplication.primaryScreen()
            geom = screen.availableGeometry() if screen else QtCore.QRect(0, 0, 1280, 800)
            dlg.resize(min(900, int(geom.width() * 0.7)), min(520, int(geom.height() * 0.6)))
        except Exception:
            dlg.resize(820, 480)
        dlg.exec()

    def _on_use(self):
        """Accept the dialog and mark that this connection should be used immediately."""
        # Validate required fields
        if not self.name_edit.text().strip():
            QtWidgets.QMessageBox.warning(self, "Invalid Name", "Connection name cannot be empty.")
            self.name_edit.setFocus()
            return
        if not self.host_edit.text().strip() or not self.db_combo.currentText().strip():
            QtWidgets.QMessageBox.warning(self, "Missing Details", "Host and database name are required.")
            return
        # Mark that we should use this connection
        self.use_connection = True
        self.accept()

    def get_connection_data(self) -> dict:
        data = {
            'name': self.name_edit.text().strip(),
            'type': self.type_combo.currentText(),
            'host': self.host_edit.text().strip(),
            'port': int(self.port_edit.text() or 0),
            'database': self.db_combo.currentText().strip(),
            'user': self.user_edit.text().strip(),
            'password': self.pw_edit.text(),
            'driver': self.driver_combo.currentText().strip(),
            'encrypt_mode': self.encrypt_combo.currentText().strip().lower(),
            'save': bool(self.save_cb.isChecked()),
            'use': getattr(self, 'use_connection', False),
        }
        # include table if user selected one
        if self.table_combo.count() and self.table_combo.currentText():
            data['table'] = self.table_combo.currentText()
        return data

    def _populate_databases(self):
        """Fetch available databases from the server and populate db_combo.

        Requires the user to have SHOW DATABASES (MySQL) or VIEW ANY DATABASE
        (MSSQL) privilege. Oracle discovery is not supported in this flow.
        If the privilege is missing, shows an informational
        dialog so the user knows to enter the name manually.
        """
        try:
            from api import db_utils
        except ModuleNotFoundError:
            return

        host = self.host_edit.text().strip()
        user = self.user_edit.text().strip()
        typ = self.type_combo.currentText()
        if typ == "Oracle":
            QtWidgets.QMessageBox.information(
                self,
                "Oracle",
                "Oracle service-name discovery is not supported here. Enter the service name manually.",
            )
            return
        if not host or not user:
            QtWidgets.QMessageBox.warning(
                self,
                "Missing Details",
                "Enter the host and user name before fetching databases."
            )
            return

        port = int(self.port_edit.text() or 0)
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            names = db_utils.get_database_names(
                self.type_combo.currentText(),
                host,
                port,
                user,
                self.pw_edit.text(),
                self.driver_combo.currentText() or None,
                self.encrypt_combo.currentText(),
            )
            current = self.db_combo.currentText()
            self.db_combo.clear()
            self.db_combo.addItems(names)
            if current:
                self.db_combo.setCurrentText(current)
            msg = f"Found {len(names)} database(s)." if names else "No databases found."
            self.status_label.setText(msg)
        except PermissionError as e:
            self._show_copyable_message(
                "Insufficient Permissions",
                f"{e}\n\nYou can still type the database name directly in the field.",
                icon=QtWidgets.QMessageBox.Information,
            )
        except Exception as e:
            self._show_copyable_message(
                "Could Not Fetch Databases",
                f"Failed to retrieve database list:\n\n{e}",
                icon=QtWidgets.QMessageBox.Warning,
            )
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _toggle_password_visibility(self, checked: bool):
        """Toggle password field between hidden and visible."""
        if checked:
            self.pw_edit.setEchoMode(QtWidgets.QLineEdit.Normal)
            self.show_pw_btn.setText("Hide")
        else:
            self.pw_edit.setEchoMode(QtWidgets.QLineEdit.Password)
            self.show_pw_btn.setText("Show")

    def _new_connection(self):
        """Reset fields to defaults so user can define a new DB connection."""
        self.name_edit.clear()
        self.type_combo.setCurrentText("MySQL")
        self.host_edit.clear()
        self.port_edit.clear()
        self.db_combo.clearEditText()
        self.table_combo.clear()
        self.table_combo.setEnabled(False)
        self.user_edit.clear()
        self.pw_edit.clear()
        self.driver_combo.setCurrentIndex(0)
        self.encrypt_combo.setCurrentText("Auto")
        self.save_cb.setChecked(True)
        self.status_label.setText("")
        self.sample_label.setVisible(False)
        self.show_pw_btn.setChecked(False)
        self._update_port_default()
        self._update_jdbc_string()
        self.name_edit.setFocus()


class DBConnectionsManager(QtWidgets.QDialog):
    """List, create, edit, and delete saved database connections."""
    def __init__(self, connections: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Database Connections")
        self.setModal(True)
        dpi = get_dpi_scale()
        self.setMinimumSize(scale_size(600, dpi), scale_size(400, dpi))
        layout = QtWidgets.QVBoxLayout(self)
        
        # Create buttons FIRST so they exist when signals are unblocked
        self.add_btn = QtWidgets.QPushButton("Add")
        self.add_btn.setToolTip("Create a new connection profile")
        self.edit_btn = QtWidgets.QPushButton("Edit")
        self.edit_btn.setToolTip("Modify the selected connection")
        self.del_btn = QtWidgets.QPushButton("Delete")
        self.del_btn.setToolTip("Remove the selected connection")
        
        # Initialize deleted set before populating list (used by _populate)
        self.deleted = set()  # Track items marked for deletion
        
        # ensure Enter triggers edit when a connection is selected
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.itemActivated.connect(self.edit)
        self.list_widget.itemSelectionChanged.connect(self._update_button_state)
        self._populate(connections)
        layout.addWidget(self.list_widget)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.add_btn); btn_layout.addWidget(self.edit_btn); btn_layout.addWidget(self.del_btn);
        layout.addLayout(btn_layout)

        self.add_btn.clicked.connect(self.add)
        self.edit_btn.clicked.connect(self.edit)
        self.del_btn.clicked.connect(self.delete)
        # make Add the default button so Enter adds when no selection
        self.add_btn.setDefault(True)
        
        # If no connections, set focus to Add button
        if not connections:
            self.add_btn.setFocus()
            
        # Update button state based on selection
        self._update_button_state()

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self.connections = connections
        self.result = connections.copy()
        ensure_dialog_caption_fit(self)
    
    def _update_button_state(self):
        """Enable/disable edit and delete buttons based on selection."""
        has_selection = self.list_widget.currentItem() is not None
        self.edit_btn.setEnabled(has_selection)
        self.del_btn.setEnabled(has_selection)
        
        # Update delete button text based on whether selected item is marked for deletion
        if has_selection:
            item = self.list_widget.currentItem()
            if item and item.text() in self.deleted:
                self.del_btn.setText("Undelete")
                self.del_btn.setToolTip("Restore this connection (cancel deletion)")
            else:
                self.del_btn.setText("Delete")
                self.del_btn.setToolTip("Mark this connection for deletion")
        else:
            self.del_btn.setText("Delete")
            self.del_btn.setToolTip("Mark this connection for deletion")

    def _populate(self, connections):
        """Repopulate the list widget, blocking signals during update to avoid spurious state changes."""
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for name in sorted(connections.keys()):
            item = QtWidgets.QListWidgetItem(name)
            if name in self.deleted:
                # Mark deleted items visually
                font = item.font()
                font.setStrikeOut(True)
                item.setFont(font)
                item.setForeground(QtGui.QColor("#999999"))
                item.setToolTip("This connection will be deleted when the dialog is closed")
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)
        # Focus on most recent entry (last in sorted list) or Add button if empty
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(self.list_widget.count() - 1)
            self.list_widget.setFocus()
        # Update button state after unblocking signals
        self._update_button_state()

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
        if name in self.deleted:
            # Undelete if already marked for deletion
            self.deleted.remove(name)
            self._populate(self.result)
        else:
            # Mark for deletion
            if QtWidgets.QMessageBox.question(self, "Delete", f"Delete connection '{name}'?") == QtWidgets.QMessageBox.Yes:
                self.deleted.add(name)
                self._populate(self.result)

    def get_connections(self) -> dict:
        # Process deletions when dialog is closed
        for name in self.deleted:
            if name in self.result:
                del self.result[name]
        return self.result


class LDAPConnectionDialog(QtWidgets.QDialog):
    """Dialog for creating or editing an LDAP connection definition."""

    def __init__(self, initial: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LDAP Connection")
        self.setModal(True)
        dpi = get_dpi_scale()
        self.setMinimumSize(scale_size(520, dpi), scale_size(430, dpi))

        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

        self.name_edit = QtWidgets.QLineEdit()
        self.host_edit = QtWidgets.QLineEdit()
        self.host_edit.setPlaceholderText("ldap.example.com")
        self.host_edit.setToolTip("Host or URI, e.g. ldap.example.com, ldap://ldap.example.com:1389, or ldaps://ldap.example.com:1636")
        self.port_edit = QtWidgets.QLineEdit()
        self.port_edit.setValidator(QtGui.QIntValidator(1, 65535))
        self.port_edit.setPlaceholderText("389")
        self.port_edit.setToolTip("Any LDAP port is supported, e.g. 389, 636, 1389, 1636")

        self.use_ssl_cb = QtWidgets.QCheckBox("Use SSL (LDAPS)")
        self.start_tls_cb = QtWidgets.QCheckBox("Use StartTLS")
        self.auto_create_parents_cb = QtWidgets.QCheckBox("Auto-create missing parent containers")
        self.auto_create_parents_cb.setToolTip("When enabled, export can create missing OU/DC parent containers before adding user entries.")

        self.base_dn_edit = QtWidgets.QLineEdit()
        self.base_dn_edit.setPlaceholderText("ou=People,dc=example,dc=com")
        self.bind_dn_edit = QtWidgets.QLineEdit()
        self.bind_dn_edit.setPlaceholderText("cn=admin,dc=example,dc=com")

        self.pw_edit = QtWidgets.QLineEdit()
        self.pw_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.show_pw_btn = QtWidgets.QPushButton("Show")
        self.show_pw_btn.setCheckable(True)
        self.show_pw_btn.toggled.connect(self._toggle_password_visibility)
        pw_row = QtWidgets.QHBoxLayout()
        pw_row.addWidget(self.pw_edit, 1)
        pw_row.addWidget(self.show_pw_btn)

        self.filter_edit = QtWidgets.QLineEdit()
        self.filter_edit.setPlaceholderText("(objectClass=person)")
        self.rdn_attr_edit = QtWidgets.QLineEdit()
        self.rdn_attr_edit.setPlaceholderText("uid")
        self.timeout_edit = QtWidgets.QLineEdit()
        self.timeout_edit.setValidator(QtGui.QIntValidator(3, 120))
        self.timeout_edit.setPlaceholderText("30")
        self.timeout_edit.setToolTip("LDAP connect timeout in seconds (3-120)")

        form.addRow("Name:", self.name_edit)
        form.addRow("Host:", self.host_edit)
        form.addRow("Port:", self.port_edit)
        form.addRow("", self.use_ssl_cb)
        form.addRow("", self.start_tls_cb)
        form.addRow("", self.auto_create_parents_cb)
        form.addRow("Base DN:", self.base_dn_edit)
        form.addRow("Bind DN:", self.bind_dn_edit)
        form.addRow("Password:", pw_row)
        form.addRow("Search Filter:", self.filter_edit)
        form.addRow("RDN Attribute:", self.rdn_attr_edit)
        form.addRow("Timeout (sec):", self.timeout_edit)
        layout.addLayout(form)

        self.sample_label = QtWidgets.QLabel("")
        self.sample_label.setWordWrap(True)
        self.sample_label.setStyleSheet("background-color: #f0f0f0; padding: 8px; border-radius: 4px;")
        self.sample_label.setVisible(False)
        layout.addWidget(self.sample_label)

        self.status_label = QtWidgets.QLabel("")
        layout.addWidget(self.status_label)

        action_row = QtWidgets.QHBoxLayout()
        test_btn = QtWidgets.QPushButton("Test Connection")
        test_btn.clicked.connect(self._on_test)
        new_btn = QtWidgets.QPushButton("New Connection")
        new_btn.setToolTip("Clear fields so you can enter a new LDAP connection")
        new_btn.clicked.connect(self._new_connection)
        action_row.addWidget(test_btn)
        action_row.addWidget(new_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.save_cb = QtWidgets.QCheckBox("Save this connection")
        self.save_cb.setChecked(True)
        layout.addWidget(self.save_cb)

        btn_layout = QtWidgets.QHBoxLayout()
        use_btn = QtWidgets.QPushButton("Use This Connection")
        use_btn.clicked.connect(self._on_use)
        self.use_btn = use_btn

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self._validate_and_accept)
        btns.rejected.connect(self.reject)

        btn_layout.addWidget(use_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(btns)
        layout.addLayout(btn_layout)

        self.use_ssl_cb.toggled.connect(self._sync_port_with_tls)

        if initial:
            self.name_edit.setText(initial.get('name', ''))
            self.host_edit.setText(initial.get('host', ''))
            self.port_edit.setText(str(initial.get('port', '')))
            self.use_ssl_cb.setChecked(bool(initial.get('use_ssl', False)))
            self.start_tls_cb.setChecked(bool(initial.get('start_tls', False)))
            self.auto_create_parents_cb.setChecked(bool(initial.get('auto_create_parents', True)))
            self.base_dn_edit.setText(initial.get('base_dn', ''))
            self.bind_dn_edit.setText(initial.get('bind_dn', ''))
            self.pw_edit.setText(initial.get('password', ''))
            self.filter_edit.setText(initial.get('search_filter', '(objectClass=person)'))
            self.rdn_attr_edit.setText(initial.get('rdn_attribute', 'uid'))
            self.timeout_edit.setText(str(initial.get('timeout', 30)))
        else:
            self.auto_create_parents_cb.setChecked(True)

        if not self.port_edit.text().strip():
            self._sync_port_with_tls()
        if not self.filter_edit.text().strip():
            self.filter_edit.setText('(objectClass=person)')
        if not self.rdn_attr_edit.text().strip():
            self.rdn_attr_edit.setText('uid')
        if not self.timeout_edit.text().strip():
            self.timeout_edit.setText('30')
        ensure_dialog_caption_fit(self)

    def _new_connection(self):
        """Reset fields to defaults so user can define a new LDAP connection."""
        self.name_edit.clear()
        self.host_edit.clear()
        self.port_edit.clear()
        self.use_ssl_cb.setChecked(False)
        self.start_tls_cb.setChecked(False)
        self.auto_create_parents_cb.setChecked(True)
        self.base_dn_edit.clear()
        self.bind_dn_edit.clear()
        self.pw_edit.clear()
        self.filter_edit.setText('(objectClass=person)')
        self.rdn_attr_edit.setText('uid')
        self.timeout_edit.setText('30')
        self.sample_label.setVisible(False)
        self.status_label.setText('')
        self.save_cb.setChecked(True)
        self._sync_port_with_tls()
        self.name_edit.setFocus()

    def _toggle_password_visibility(self, checked: bool):
        if checked:
            self.pw_edit.setEchoMode(QtWidgets.QLineEdit.Normal)
            self.show_pw_btn.setText("Hide")
        else:
            self.pw_edit.setEchoMode(QtWidgets.QLineEdit.Password)
            self.show_pw_btn.setText("Show")

    def _sync_port_with_tls(self):
        if self.port_edit.text().strip():
            return
        self.port_edit.setText("636" if self.use_ssl_cb.isChecked() else "389")

    def _validate_and_accept(self):
        if not self.name_edit.text().strip():
            QtWidgets.QMessageBox.warning(self, "Invalid Name", "Connection name cannot be empty.")
            self.name_edit.setFocus()
            return
        if not self.host_edit.text().strip() or not self.base_dn_edit.text().strip() or not self.bind_dn_edit.text().strip():
            QtWidgets.QMessageBox.warning(self, "Missing Details", "Host, Base DN, and Bind DN are required.")
            return
        self.accept()

    def _on_test(self):
        try:
            from api import ldap_utils
        except ModuleNotFoundError:
            QtWidgets.QMessageBox.critical(
                self,
                "Missing Dependency",
                "ldap3 is not installed. Please install requirements and restart (e.g. `pip install -r requirements.txt`)."
            )
            self.status_label.setText("Dependency missing.")
            return

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        self.status_label.setText("Testing connection...")
        QtWidgets.QApplication.processEvents()
        timeout = int(self.timeout_edit.text() or 30)
        ok, err = ldap_utils.test_connection(
            self.host_edit.text().strip(),
            int(self.port_edit.text() or 0),
            bool(self.use_ssl_cb.isChecked()),
            self.bind_dn_edit.text().strip(),
            self.pw_edit.text(),
            self.base_dn_edit.text().strip(),
            bool(self.start_tls_cb.isChecked()),
            timeout=timeout,
        )
        QtWidgets.QApplication.restoreOverrideCursor()

        if not ok:
            self.status_label.setText("Connection failed.")
            msg = "Failed to connect to LDAP directory."
            if err:
                msg += f"\n\nError details:\n{err}"
            QtWidgets.QMessageBox.critical(self, "Test Connection", msg)
            self.sample_label.setVisible(False)
            return

        self.status_label.setText("Connection successful.")
        try:
            sample = ldap_utils.get_entry_sample(
                self.host_edit.text().strip(),
                int(self.port_edit.text() or 0),
                bool(self.use_ssl_cb.isChecked()),
                self.bind_dn_edit.text().strip(),
                self.pw_edit.text(),
                self.base_dn_edit.text().strip(),
                self.filter_edit.text().strip() or "(objectClass=person)",
                bool(self.start_tls_cb.isChecked()),
                timeout=timeout,
            )
            if sample:
                fields = []
                for key in sorted(sample.keys())[:6]:
                    fields.append(f"{key}={sample[key]}")
                self.sample_label.setText("Sample entry: " + " | ".join(fields))
                self.sample_label.setVisible(True)
            else:
                self.sample_label.setText("Connected, but no matching entries found.")
                self.sample_label.setVisible(True)
        except Exception as exc:
            self.sample_label.setText(f"Connected, but sample read failed: {exc}")
            self.sample_label.setVisible(True)

    def _on_use(self):
        self._validate_and_accept()
        if self.result() == QtWidgets.QDialog.Accepted:
            self.use_connection = True

    def get_connection_data(self) -> dict:
        return {
            'name': self.name_edit.text().strip(),
            'host': self.host_edit.text().strip(),
            'port': int(self.port_edit.text() or 0),
            'use_ssl': bool(self.use_ssl_cb.isChecked()),
            'start_tls': bool(self.start_tls_cb.isChecked()),
            'auto_create_parents': bool(self.auto_create_parents_cb.isChecked()),
            'base_dn': self.base_dn_edit.text().strip(),
            'bind_dn': self.bind_dn_edit.text().strip(),
            'password': self.pw_edit.text(),
            'search_filter': (self.filter_edit.text().strip() or '(objectClass=person)'),
            'rdn_attribute': (self.rdn_attr_edit.text().strip() or 'uid'),
            'timeout': int(self.timeout_edit.text() or 30),
            'save': bool(self.save_cb.isChecked()),
            'use': getattr(self, 'use_connection', False),
        }


class LDAPConnectionsManager(QtWidgets.QDialog):
    """List, create, edit, and delete saved LDAP connections."""

    def __init__(self, connections: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage LDAP Connections")
        self.setModal(True)
        dpi = get_dpi_scale()
        self.setMinimumSize(scale_size(600, dpi), scale_size(400, dpi))
        self.connections = connections
        self.result = connections.copy()

        layout = QtWidgets.QVBoxLayout(self)
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.itemActivated.connect(self.edit)
        self.list_widget.itemSelectionChanged.connect(self._update_button_state)
        layout.addWidget(self.list_widget)

        btn_row = QtWidgets.QHBoxLayout()
        self.add_btn = QtWidgets.QPushButton("Add")
        self.edit_btn = QtWidgets.QPushButton("Edit")
        self.del_btn = QtWidgets.QPushButton("Delete")
        self.add_btn.clicked.connect(self.add)
        self.edit_btn.clicked.connect(self.edit)
        self.del_btn.clicked.connect(self.delete)
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.del_btn)
        layout.addLayout(btn_row)

        close_btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        close_btns.rejected.connect(self.reject)
        layout.addWidget(close_btns)

        self.deleted = set()  # Track items marked for deletion
        self._populate(self.result)
        ensure_dialog_caption_fit(self)

    def _populate(self, connections: dict):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for name in sorted(connections.keys()):
            item = QtWidgets.QListWidgetItem(name)
            if name in self.deleted:
                # Mark deleted items visually
                font = item.font()
                font.setStrikeOut(True)
                item.setFont(font)
                item.setForeground(QtGui.QColor("#999999"))
                item.setToolTip("This connection will be deleted when the dialog is closed")
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(self.list_widget.count() - 1)
        self._update_button_state()

    def _update_button_state(self):
        has_selection = self.list_widget.currentItem() is not None
        self.edit_btn.setEnabled(has_selection)
        self.del_btn.setEnabled(has_selection)
        
        # Update delete button text based on whether selected item is marked for deletion
        if has_selection:
            item = self.list_widget.currentItem()
            if item and item.text() in self.deleted:
                self.del_btn.setText("Undelete")
                self.del_btn.setToolTip("Restore this connection (cancel deletion)")
            else:
                self.del_btn.setText("Delete")
                self.del_btn.setToolTip("Mark this connection for deletion")
        else:
            self.del_btn.setText("Delete")
            self.del_btn.setToolTip("Mark this connection for deletion")

    def add(self):
        dlg = LDAPConnectionDialog(parent=self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            data = dlg.get_connection_data()
            if not data.get('save', True):
                return
            name = data.get('name')
            if name:
                if name in self.result:
                    resp = QtWidgets.QMessageBox.question(
                        self,
                        "Replace Connection",
                        f"A connection named '{name}' already exists. Replace it?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
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
        dlg = LDAPConnectionDialog(initial=self.result.get(name, {}), parent=self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            data = dlg.get_connection_data()
            if not data.get('save', True):
                if name in self.result:
                    del self.result[name]
                    self._populate(self.result)
                return
            new_name = data.get('name')
            if new_name and new_name != name:
                del self.result[name]
            self.result[new_name] = data
            self._populate(self.result)

    def delete(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        name = item.text()
        if name in self.deleted:
            # Undelete if already marked for deletion
            self.deleted.remove(name)
            self._populate(self.result)
        else:
            # Mark for deletion
            if QtWidgets.QMessageBox.question(self, "Delete", f"Delete connection '{name}'?") == QtWidgets.QMessageBox.Yes:
                self.deleted.add(name)
                self._populate(self.result)

    def get_connections(self) -> dict:
        # Process deletions when dialog is closed
        for name in self.deleted:
            if name in self.result:
                del self.result[name]
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
    def __init__(self, table_cols: List[str], pingone_attrs: List[str], direction: str = 'import', sample_row: Optional[dict] = None, initial_mapping: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Database Mapping")
        self.setModal(True)
        dpi = get_dpi_scale()
        apply_screen_relative_size(
            self,
            scale_size(760, dpi),
            scale_size(360, dpi),
            scale_size(880, dpi),
            scale_size(500, dpi),
            max_w_ratio=0.76,
            max_h_ratio=0.64,
        )
        self.direction = direction
        # JDBC result metadata can contain JPype Java string objects;
        # normalize all UI-bound names to Python str for Qt compatibility.
        self.table_cols = [str(c) for c in (table_cols or [])]
        self.pingone_attrs = [str(a) for a in (pingone_attrs or [])]
        self.sample_row = {str(k): v for k, v in (sample_row or {}).items()}
        self.initial_mapping = dict(initial_mapping or {})

        layout = QtWidgets.QVBoxLayout(self)
        direction_label = QtWidgets.QLabel(
            "Database column -> PingOne attribute"
            if direction == 'import'
            else "PingOne attribute -> Database column"
        )
        direction_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(direction_label)

        # Auto-filter checkbox for link attributes
        self.auto_filter_links_cb = QtWidgets.QCheckBox("Auto-remove link attributes (URLs, JSON objects)")
        self.auto_filter_links_cb.setChecked(True)
        self.auto_filter_links_cb.setToolTip("Automatically filter out columns containing http://, https://, or starting with {")
        self.auto_filter_links_cb.stateChanged.connect(self._rebuild_rows)
        layout.addWidget(self.auto_filter_links_cb)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(3)
        # Enable multi-row selection
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        
        if direction == 'import':
            headers = ["Column Name", "Sample Value", "PingOne Attribute"]
        else:
            headers = ["PingOne Attribute", "Example Value", "Target Column"]
        self.table.setHorizontalHeaderLabels(headers)

        if direction == 'import':
            self._build_import_rows()
        else:
            self._build_export_rows()

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        
        # Install key event handling for Enter/Tab navigation
        apply_mapping_table_keys(self.table, mapping_col=2)

        # If a saved mapping exists for this connection, prefill combos.
        self._apply_initial_mapping()

        layout.addWidget(self.table)

        row_actions = QtWidgets.QHBoxLayout()
        add_row_btn = QtWidgets.QPushButton("Add Row")
        add_row_btn.setToolTip("Add a manual mapping row")
        add_row_btn.clicked.connect(self._add_manual_row)
        del_row_btn = QtWidgets.QPushButton("Delete Row")
        del_row_btn.setToolTip("Delete selected mapping row(s)")
        del_row_btn.clicked.connect(self._delete_selected_rows)
        row_actions.addWidget(add_row_btn)
        row_actions.addWidget(del_row_btn)
        row_actions.addStretch()
        layout.addLayout(row_actions)

        self.remember_cb = QtWidgets.QCheckBox("Save mapping in DB connection settings")
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
        ensure_dialog_caption_fit(self)

    def _normalize_mapping_token(self, value: str) -> str:
        token = str(value or '').strip().lower()
        return ''.join(ch for ch in token if ch.isalnum())

    def _suggest_pingone_attr(self, column_name: str, phone_type: str = '') -> str:
        """Suggest the best PingOne attribute for a database import column."""
        if phone_type:
            typed = f"phoneNumbers.{phone_type}"
            if typed in self.pingone_attrs:
                return typed

        normalized_source = self._normalize_mapping_token(column_name)
        if not normalized_source:
            return ''

        alias_map = {
            'firstname': 'name.given',
            'givenname': 'name.given',
            'middlename': 'name.middle',
            'middleinitial': 'name.middle',
            'lastname': 'name.family',
            'familyname': 'name.family',
            'uid': 'username',
            'employeetype': 'employeeType',
            'employmenttype': 'employeeType',
            'street': 'address.streetAddress',
            'streetaddress': 'address.streetAddress',
            'addressline1': 'address.streetAddress',
            'city': 'address.locality',
            'state': 'address.region',
            'province': 'address.region',
            'region': 'address.region',
            'postalcode': 'address.postalCode',
            'zipcode': 'address.postalCode',
            'zip': 'address.postalCode',
            'country': 'address.countryCode',
            'population': 'population.id',
        }
        if normalized_source in alias_map:
            candidate = alias_map[normalized_source]
            candidate_norm = self._normalize_mapping_token(candidate)
            for attr in self.pingone_attrs:
                if self._normalize_mapping_token(attr) == candidate_norm:
                    return attr
            return candidate

        for attr in self.pingone_attrs:
            if self._normalize_mapping_token(attr) == normalized_source:
                return attr
        return ''

    def _suggest_db_column(self, pingone_attr: str) -> str:
        """Suggest the best database column for a PingOne export attribute."""
        normalized_attr = self._normalize_mapping_token(pingone_attr)
        if not normalized_attr:
            return ''

        for col in self.table_cols:
            if self._normalize_mapping_token(col) == normalized_attr:
                return col
        return ''

    def _should_filter_column(self, col_name: str, sample_value: str = '') -> bool:
        """Check if a column should be filtered out based on link content."""
        if not self.auto_filter_links_cb.isChecked():
            return False
        
        # Check column name
        col_lower = str(col_name).lower()
        if col_lower.startswith('_links') or col_lower.startswith('_embedded'):
            return True
        
        # Check sample value for URLs or JSON
        val_str = str(sample_value).strip()
        if val_str.startswith('http://') or val_str.startswith('https://') or val_str.startswith('{'):
            return True
        
        return False

    def _rebuild_rows(self):
        """Rebuild table rows when filter state changes."""
        if self.direction == 'import':
            self._build_import_rows()
        else:
            self._build_export_rows()

    def _build_import_rows(self):
        # If sample_row has phoneNumbers with multiple types, expand them for clarity.
        expanded_cols = self._expand_phone_numbers(self.table_cols, self.sample_row)
        
        # Filter out link attributes if enabled
        if self.auto_filter_links_cb.isChecked():
            filtered_cols = []
            for col_info in expanded_cols:
                col = col_info['name']
                sample_val = ''
                if col in self.sample_row:
                    sample_val = str(self.sample_row[col])
                if not self._should_filter_column(col, sample_val):
                    filtered_cols.append(col_info)
            expanded_cols = filtered_cols
        
        self.table.setRowCount(len(expanded_cols))
        for i, col_info in enumerate(expanded_cols):
            col = col_info['name']
            is_phone = col_info.get('is_phone', False)
            phone_type = col_info.get('phone_type', '')
            source_key = f"{col}::{phone_type}" if is_phone and phone_type else col
            display_name = f"{str(col)} ({phone_type})" if is_phone and phone_type else str(col)

            src_item = QtWidgets.QTableWidgetItem(display_name)
            src_item.setData(QtCore.Qt.UserRole, source_key)
            self.table.setItem(i, 0, src_item)

            val = ''
            if col in self.sample_row:
                val = str(self.sample_row[col])
                if is_phone and phone_type:
                    phones = self.sample_row.get(col, [])
                    if isinstance(phones, list):
                        for phone_obj in phones:
                            if isinstance(phone_obj, dict) and phone_obj.get('type') == phone_type:
                                val = phone_obj.get('number', '')
                                break
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(val) if val else ''))

            combo = QtWidgets.QComboBox()
            combo.setEditable(True)
            combo.addItem("<None>")
            if is_phone and phone_type:
                combo.addItem(f"phoneNumbers.{phone_type}")
            combo.addItems(self.pingone_attrs)
            combo.setPlaceholderText("Select or type attribute name")
            apply_combo_typeahead(combo, self.pingone_attrs)
            clear_none_on_interact(combo)
            suggested = self._suggest_pingone_attr(col, phone_type)
            if suggested:
                combo.setCurrentText(suggested)
            apply_mapping_combo_keys(self.table, combo, 2)
            self.table.setCellWidget(i, 2, combo)

    def _build_export_rows(self):
        attrs = self.pingone_attrs or self.table_cols
        
        # Filter out link attributes if enabled
        if self.auto_filter_links_cb.isChecked():
            filtered_attrs = []
            for attr in attrs:
                sample_val = self.sample_row.get(attr, '')
                if isinstance(sample_val, (dict, list)):
                    try:
                        sample_val = json.dumps(sample_val)
                    except Exception:
                        sample_val = str(sample_val)
                if not self._should_filter_column(attr, str(sample_val)):
                    filtered_attrs.append(attr)
            attrs = filtered_attrs
        
        self.table.setRowCount(len(attrs))
        for i, attr in enumerate(attrs):
            left_item = QtWidgets.QTableWidgetItem(str(attr))
            left_item.setData(QtCore.Qt.UserRole, attr)
            self.table.setItem(i, 0, left_item)

            val = self.sample_row.get(attr, '')
            if isinstance(val, (dict, list)):
                try:
                    val = json.dumps(val)
                except Exception:
                    val = str(val)
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(val) if val is not None else ''))

            combo = QtWidgets.QComboBox()
            combo.setEditable(True)
            combo.addItem("<None>")
            combo.addItems(self.table_cols)
            suggested = self._suggest_db_column(attr)
            if suggested:
                combo.setCurrentText(suggested)
            else:
                combo.setEditText(attr)
            combo.setPlaceholderText("Select or type target column")
            apply_combo_typeahead(combo, list(self.table_cols) + [attr])
            clear_none_on_interact(combo)
            apply_mapping_combo_keys(self.table, combo, 2)
            self.table.setCellWidget(i, 2, combo)
    
    def _expand_phone_numbers(self, table_cols: List[str], sample_row: Optional[dict]) -> List[dict]:
        """Expand phoneNumbers column to show individual phone types if present."""
        expanded = []
        for col in table_cols:
            if str(col).lower() == 'phonenumbers' and sample_row and col in sample_row:
                phones = sample_row.get(col, [])
                if isinstance(phones, list) and phones:
                    # Expand each phone with its type
                    phone_types_seen = set()
                    for phone_obj in phones:
                        if isinstance(phone_obj, dict):
                            phone_type = phone_obj.get('type', 'unknown')
                            if phone_type not in phone_types_seen:
                                phone_types_seen.add(phone_type)
                                expanded.append({
                                    'name': col,
                                    'is_phone': True,
                                    'phone_type': phone_type
                                })
                    if expanded and expanded[-1].get('name') == col:
                        continue  # Already added phone entries
                expanded.append({'name': col, 'is_phone': False})
            else:
                expanded.append({'name': col, 'is_phone': False})
        return expanded

    def _add_manual_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(""))
        self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(""))

        combo = QtWidgets.QComboBox()
        combo.setEditable(True)
        combo.addItem("<None>")
        if self.direction == 'import':
            combo.addItems(self.pingone_attrs)
            combo.setPlaceholderText("Select or type attribute name")
            apply_combo_typeahead(combo, self.pingone_attrs)
        else:
            combo.addItems(self.table_cols)
            combo.setPlaceholderText("Select or type target column")
            apply_combo_typeahead(combo, self.table_cols)
        clear_none_on_interact(combo)
        apply_mapping_combo_keys(self.table, combo, 2)
        self.table.setCellWidget(row, 2, combo)

    def _delete_selected_rows(self):
        rows = sorted({idx.row() for idx in self.table.selectionModel().selectedRows()}, reverse=True)
        if not rows and self.table.currentRow() >= 0:
            rows = [self.table.currentRow()]
        for row in rows:
            self.table.removeRow(row)

    def _apply_initial_mapping(self):
        if not self.initial_mapping:
            return
        for row in range(self.table.rowCount()):
            left_item = self.table.item(row, 0)
            combo = self.table.cellWidget(row, 2)
            if not left_item or not isinstance(combo, QtWidgets.QComboBox):
                continue
            left = left_item.data(QtCore.Qt.UserRole) or left_item.text()
            if left in self.initial_mapping:
                combo.setCurrentText(str(self.initial_mapping[left]))

    def get_mapping(self) -> dict:
        result = {}
        for row in range(self.table.rowCount()):
            left_item = self.table.item(row, 0)
            if left_item:
                left = left_item.data(QtCore.Qt.UserRole) or left_item.text()
                combo: QtWidgets.QComboBox = self.table.cellWidget(row, 2)
                tgt = combo.currentText()
                if tgt and tgt != "<None>":
                    result[left] = tgt
        return result

    def remember_mapping(self) -> bool:
        return bool(self.remember_cb.isChecked())


class LDAPMappingDialog(DatabaseMappingDialog):
    """Mapping dialog for LDAP directory attributes and PingOne attributes.

    Mirrors DatabaseMappingDialog but uses LDAP-specific labels and terminology.

    - ``'import'``: LDAP attributes -> PingOne attributes
    - ``'export'``: PingOne attributes -> LDAP attributes
    """

    # Well-known PingOne attribute -> canonical LDAP attribute name mapping.
    # Used so the dialog auto-suggests correct LDAP names (e.g. `mail` not `email`).
    _PINGONE_TO_LDAP: Dict[str, str] = {
        'email': 'mail',
        'username': 'cn',
        'name.formatted': 'cn',
        'name.given': 'givenName',
        'name.family': 'sn',
        'name.middle': 'initials',
        'phoneNumbers.work': 'telephoneNumber',
        'phoneNumbers.mobile': 'mobile',
        'phoneNumbers.home': 'homePhone',
        'address.streetAddress': 'street',
        'address.locality': 'l',
        'address.region': 'st',
        'address.postalCode': 'postalCode',
        'address.countryCode': 'c',
        'title': 'title',
        'department': 'departmentNumber',
        'organization': 'o',
        'description': 'description',
    }

    # Reverse map: canonical LDAP -> PingOne attribute, with extra common aliases.
    _LDAP_TO_PINGONE: Dict[str, str] = {
        'mail': 'email',
        'uid': 'username',
        'cn': 'name.formatted',
        'givenname': 'name.given',
        'sn': 'name.family',
        'surname': 'name.family',
        'initials': 'name.middle',
        'telephonenumber': 'phoneNumbers.work',
        'mobile': 'phoneNumbers.mobile',
        'homephone': 'phoneNumbers.home',
        'street': 'address.streetAddress',
        'l': 'address.locality',
        'st': 'address.region',
        'postalcode': 'address.postalCode',
        'c': 'address.countryCode',
        'title': 'title',
        'departmentnumber': 'department',
        'o': 'organization',
        'description': 'description',
    }

    def _suggest_db_column(self, pingone_attr: str) -> str:
        """Suggest the LDAP attribute name for a PingOne export attribute."""
        norm = self._normalize_mapping_token(pingone_attr)
        for p_attr, ldap_name in self._PINGONE_TO_LDAP.items():
            if self._normalize_mapping_token(p_attr) == norm:
                # Prefer the known LDAP attr if the server advertised it.
                for col in self.table_cols:
                    if self._normalize_mapping_token(col) == self._normalize_mapping_token(ldap_name):
                        return col
                # Still return the correct LDAP name as a free-text suggestion.
                return ldap_name
        return super()._suggest_db_column(pingone_attr)

    def _suggest_pingone_attr(self, ldap_attr: str, phone_type: str = '') -> str:
        """Suggest the PingOne attribute name for an LDAP import attribute."""
        if phone_type:
            return super()._suggest_pingone_attr(ldap_attr, phone_type)
        norm = self._normalize_mapping_token(ldap_attr)
        for l_attr, p_attr in self._LDAP_TO_PINGONE.items():
            if self._normalize_mapping_token(l_attr) == norm:
                for pa in self.pingone_attrs:
                    if self._normalize_mapping_token(pa) == self._normalize_mapping_token(p_attr):
                        return pa
                return p_attr
        return super()._suggest_pingone_attr(ldap_attr, phone_type)

    def __init__(self, ldap_attrs: List[str], pingone_attrs: List[str], direction: str = 'import', sample_row: Optional[dict] = None, initial_mapping: Optional[dict] = None, parent=None):
        super().__init__(ldap_attrs, pingone_attrs, direction=direction, sample_row=sample_row, initial_mapping=initial_mapping, parent=parent)
        self.setWindowTitle("LDAP Mapping")

        layout = self.layout()
        # Replace the direction label (always first widget in the layout)
        old_label = layout.itemAt(0).widget()
        if isinstance(old_label, QtWidgets.QLabel):
            old_label.setText(
                "LDAP attribute \u2192 PingOne attribute"
                if direction == 'import'
                else "PingOne attribute \u2192 LDAP attribute"
            )

        # Replace column headers
        if direction == 'import':
            self.table.setHorizontalHeaderLabels(["LDAP Attribute", "Sample Value", "PingOne Attribute"])
        else:
            self.table.setHorizontalHeaderLabels(["PingOne Attribute", "Example Value", "Target LDAP Attribute"])

        # Replace the remember checkbox text
        self.remember_cb.setText("Save mapping in LDAP connection settings")

        ensure_dialog_caption_fit(self)


class _ReorderableTableWidget(QtWidgets.QTableWidget):
    """QTableWidget with row-level drag-and-drop reordering.

    Works alongside the Move Up / Move Down buttons in ExportOptionsDialog.
    Check-states and all column data are preserved across drops.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)

    def dropEvent(self, event):
        if event.source() is not self:
            event.ignore()
            return

        src_row = self.currentRow()
        if src_row < 0:
            event.ignore()
            return

        # Derive target row from the drop position.
        try:
            pos = event.position().toPoint()
        except AttributeError:
            pos = event.pos()
        index = self.indexAt(pos)
        drop_row = index.row() if index.isValid() else self.rowCount() - 1

        if drop_row < 0 or drop_row == src_row:
            event.ignore()
            return

        cols = self.columnCount()
        row_data = [self.takeItem(src_row, col) for col in range(cols)]

        self.removeRow(src_row)
        # Adjust target index after removal when dragging downward.
        if src_row < drop_row:
            drop_row -= 1

        self.insertRow(drop_row)
        for col, item in enumerate(row_data):
            if item is None:
                item = QtWidgets.QTableWidgetItem('')
            self.setItem(drop_row, col, item)

        self.selectRow(drop_row)
        event.accept()


class ExportOptionsDialog(QtWidgets.QDialog):
    """Dialog to choose export options: selected vs all rows, visible vs all columns, metadata fields, populations.

    Returns a dict:
    { 'rows': 'selected'|'all', 'only_visible_columns': bool, 'remember': bool,
      'required_populated_attributes': List[str], 'excluded_metadata': List[str],
      'selected_populations': List[str] }
    """
    def __init__(
        self,
        has_selection: bool,
        only_visible_default: bool = True,
        prefer_selected_default: bool = True,
        parent=None,
        populated_attributes: Optional[List[str]] = None,
        populated_attribute_samples: Optional[dict] = None,
        metadata_columns: Optional[List[str]] = None,
        excluded_metadata: Optional[List[str]] = None,
        populations: Optional[dict] = None,
        selected_populations: Optional[List[str]] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle('Export Options')
        self.setModal(True)
        layout = QtWidgets.QVBoxLayout(self)

        self.setMinimumSize(520, 260)
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
            note = QtWidgets.QLabel('No rows selected - "Export only selected rows" is disabled.')
            note.setStyleSheet('color: #666;')
            layout.addWidget(note)

        layout.addWidget(self.rb_sel)
        layout.addWidget(self.rb_all)

        self.only_visible_cb = QtWidgets.QCheckBox('Export only visible columns')
        self.only_visible_cb.setChecked(bool(only_visible_default))
        layout.addWidget(self.only_visible_cb)

        # Metadata fields section
        metadata_cols = [str(m) for m in (metadata_columns or []) if str(m)]
        excluded_set = set(str(e) for e in (excluded_metadata or []))
        
        if metadata_cols:
            self.metadata_group = QtWidgets.QGroupBox('Metadata Fields')
            self.metadata_group.setCheckable(False)
            metadata_layout = QtWidgets.QVBoxLayout(self.metadata_group)
            
            metadata_note = QtWidgets.QLabel(
                'Metadata fields are API-specific (_embedded, _links, etc.). '
                'Uncheck fields to exclude them from export.'
            )
            metadata_note.setWordWrap(True)
            metadata_note.setStyleSheet('color: #666; font-size: 10pt;')
            metadata_layout.addWidget(metadata_note)
            
            # Create scrollable list for metadata fields
            scroll_area = QtWidgets.QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setMaximumHeight(120)
            scroll_widget = QtWidgets.QWidget()
            scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)
            scroll_layout.setContentsMargins(5, 5, 5, 5)
            
            self.metadata_checkboxes = {}
            for metadata_field in metadata_cols:
                cb = QtWidgets.QCheckBox(metadata_field)
                # By default, metadata is excluded (unchecked)
                cb.setChecked(metadata_field not in excluded_set)
                self.metadata_checkboxes[metadata_field] = cb
                scroll_layout.addWidget(cb)
            
            scroll_layout.addStretch()
            scroll_area.setWidget(scroll_widget)
            metadata_layout.addWidget(scroll_area)
            
            # Select All / Deselect All buttons
            metadata_buttons = QtWidgets.QHBoxLayout()
            select_all_metadata_btn = QtWidgets.QPushButton('Select All')
            deselect_all_metadata_btn = QtWidgets.QPushButton('Deselect All')
            select_all_metadata_btn.clicked.connect(self._select_all_metadata)
            deselect_all_metadata_btn.clicked.connect(self._deselect_all_metadata)
            metadata_buttons.addWidget(select_all_metadata_btn)
            metadata_buttons.addWidget(deselect_all_metadata_btn)
            metadata_buttons.addStretch()
            metadata_layout.addLayout(metadata_buttons)
            
            layout.addWidget(self.metadata_group)
        else:
            self.metadata_checkboxes = {}

        # Population filter section
        pop_dict = populations or {}
        selected_pop_ids = set(selected_populations or [])
        
        if pop_dict:
            self.population_filter_group = QtWidgets.QGroupBox('Filter by Population (optional)')
            self.population_filter_group.setCheckable(True)
            self.population_filter_group.setChecked(bool(selected_pop_ids))
            pop_layout = QtWidgets.QVBoxLayout(self.population_filter_group)
            
            pop_note = QtWidgets.QLabel(
                'Select specific populations to export. Leave all unchecked to export from all populations.'
            )
            pop_note.setWordWrap(True)
            pop_note.setStyleSheet('color: #666; font-size: 10pt;')
            pop_layout.addWidget(pop_note)
            
            # Create scrollable list for populations
            pop_scroll_area = QtWidgets.QScrollArea()
            pop_scroll_area.setWidgetResizable(True)
            pop_scroll_area.setMaximumHeight(120)
            pop_scroll_widget = QtWidgets.QWidget()
            pop_scroll_layout = QtWidgets.QVBoxLayout(pop_scroll_widget)
            pop_scroll_layout.setContentsMargins(5, 5, 5, 5)
            
            self.population_checkboxes = {}
            # Sort populations by name for better UX
            for pop_name, pop_id in sorted(pop_dict.items(), key=lambda x: x[0].lower()):
                cb = QtWidgets.QCheckBox(f"{pop_name} ({pop_id})")
                cb.setChecked(pop_id in selected_pop_ids or len(selected_pop_ids) == 0)
                self.population_checkboxes[pop_id] = cb
                pop_scroll_layout.addWidget(cb)
            
            pop_scroll_layout.addStretch()
            pop_scroll_area.setWidget(pop_scroll_widget)
            pop_layout.addWidget(pop_scroll_area)
            
            # Select All / Deselect All buttons
            pop_buttons = QtWidgets.QHBoxLayout()
            select_all_pop_btn = QtWidgets.QPushButton('Select All')
            deselect_all_pop_btn = QtWidgets.QPushButton('Deselect All')
            select_all_pop_btn.clicked.connect(self._select_all_populations)
            deselect_all_pop_btn.clicked.connect(self._deselect_all_populations)
            pop_buttons.addWidget(select_all_pop_btn)
            pop_buttons.addWidget(deselect_all_pop_btn)
            pop_buttons.addStretch()
            pop_layout.addLayout(pop_buttons)
            
            layout.addWidget(self.population_filter_group)
        else:
            self.population_checkboxes = {}
            self.population_filter_group = None

        self.attr_filter_group = QtWidgets.QGroupBox('Filter by populated attributes (optional)')
        self.attr_filter_group.setCheckable(True)
        self.attr_filter_group.setChecked(False)
        group_layout = QtWidgets.QVBoxLayout(self.attr_filter_group)

        note = QtWidgets.QLabel(
            'Enable and check attributes below. Their top-to-bottom order controls filter order.'
        )
        note.setWordWrap(True)
        note.setStyleSheet('color: #666;')
        group_layout.addWidget(note)

        attrs = [str(a) for a in (populated_attributes or []) if str(a)]
        samples = populated_attribute_samples or {}

        self.attr_table = _ReorderableTableWidget(len(attrs), 3)
        self.attr_table.setHorizontalHeaderLabels(['Include', 'Attribute', 'Sample Value'])
        self.attr_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.attr_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.attr_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.attr_table.setAlternatingRowColors(True)
        self.attr_table.verticalHeader().setVisible(False)
        self.attr_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.attr_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.attr_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.attr_table.setMinimumHeight(170)
        self.attr_table.setToolTip('Drag rows to reorder, or use Move Up / Move Down')

        for row, attr in enumerate(attrs):
            check_item = QtWidgets.QTableWidgetItem('')
            check_item.setFlags(
                QtCore.Qt.ItemIsEnabled |
                QtCore.Qt.ItemIsSelectable |
                QtCore.Qt.ItemIsUserCheckable
            )
            check_item.setCheckState(QtCore.Qt.Unchecked)
            self.attr_table.setItem(row, 0, check_item)

            attr_item = QtWidgets.QTableWidgetItem(str(attr))
            attr_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            self.attr_table.setItem(row, 1, attr_item)

            sample_text = str(samples.get(attr, '')) if samples.get(attr, '') is not None else ''
            sample_item = QtWidgets.QTableWidgetItem(sample_text)
            sample_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            self.attr_table.setItem(row, 2, sample_item)

        if self.attr_table.rowCount() > 0:
            self.attr_table.selectRow(0)

        group_layout.addWidget(self.attr_table)

        controls = QtWidgets.QHBoxLayout()
        self.select_all_btn = QtWidgets.QPushButton('Select All')
        self.select_all_btn.clicked.connect(self._select_all_attributes)
        controls.addWidget(self.select_all_btn)

        self.clear_all_btn = QtWidgets.QPushButton('Clear All')
        self.clear_all_btn.clicked.connect(self._clear_all_attributes)
        controls.addWidget(self.clear_all_btn)

        controls.addStretch(1)

        self.move_up_btn = QtWidgets.QPushButton('Move Up')
        self.move_up_btn.clicked.connect(lambda: self._move_selected_attribute_row(-1))
        controls.addWidget(self.move_up_btn)

        self.move_down_btn = QtWidgets.QPushButton('Move Down')
        self.move_down_btn.clicked.connect(lambda: self._move_selected_attribute_row(1))
        controls.addWidget(self.move_down_btn)

        group_layout.addLayout(controls)

        if self.attr_table.rowCount() == 0:
            self.attr_filter_group.setEnabled(False)
            self.attr_filter_group.setTitle('Filter by populated attributes (none available)')
            self.select_all_btn.setEnabled(False)
            self.clear_all_btn.setEnabled(False)
            self.move_up_btn.setEnabled(False)
            self.move_down_btn.setEnabled(False)

        layout.addWidget(self.attr_filter_group)

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
        ensure_dialog_caption_fit(self)

    def _selected_attr_row(self) -> int:
        row = self.attr_table.currentRow()
        if row >= 0:
            return row
        selected = self.attr_table.selectionModel().selectedRows()
        if selected:
            return selected[0].row()
        return -1

    def _select_all_attributes(self):
        for row in range(self.attr_table.rowCount()):
            item = self.attr_table.item(row, 0)
            if item:
                item.setCheckState(QtCore.Qt.Checked)

    def _clear_all_attributes(self):
        for row in range(self.attr_table.rowCount()):
            item = self.attr_table.item(row, 0)
            if item:
                item.setCheckState(QtCore.Qt.Unchecked)

    def _select_all_metadata(self):
        """Check all metadata field checkboxes."""
        for cb in self.metadata_checkboxes.values():
            cb.setChecked(True)

    def _deselect_all_metadata(self):
        """Uncheck all metadata field checkboxes."""
        for cb in self.metadata_checkboxes.values():
            cb.setChecked(False)

    def _select_all_populations(self):
        """Check all population checkboxes."""
        for cb in self.population_checkboxes.values():
            cb.setChecked(True)

    def _deselect_all_populations(self):
        """Uncheck all population checkboxes."""
        for cb in self.population_checkboxes.values():
            cb.setChecked(False)

    def _move_selected_attribute_row(self, delta: int):
        row = self._selected_attr_row()
        if row < 0:
            return
        target = row + int(delta)
        if target < 0 or target >= self.attr_table.rowCount() or target == row:
            return

        values = []
        for col in range(self.attr_table.columnCount()):
            item = self.attr_table.takeItem(row, col)
            if not item:
                item = QtWidgets.QTableWidgetItem('')
            values.append(item)

        self.attr_table.removeRow(row)
        self.attr_table.insertRow(target)
        for col, item in enumerate(values):
            self.attr_table.setItem(target, col, item)
        self.attr_table.selectRow(target)

    def get_options(self) -> dict:
        rows = 'selected' if self.rb_sel.isChecked() and self.rb_sel.isEnabled() else 'all'
        required_populated_attributes = []
        if self.attr_filter_group.isEnabled() and self.attr_filter_group.isChecked():
            for row in range(self.attr_table.rowCount()):
                include_item = self.attr_table.item(row, 0)
                attr_item = self.attr_table.item(row, 1)
                if not include_item or not attr_item:
                    continue
                if include_item.checkState() == QtCore.Qt.Checked:
                    attr = attr_item.text().strip()
                    if attr:
                        required_populated_attributes.append(attr)
        
        # Collect excluded metadata fields (those that are unchecked)
        excluded_metadata = []
        for field, cb in self.metadata_checkboxes.items():
            if not cb.isChecked():
                excluded_metadata.append(field)
        
        # Collect selected populations (if filter is enabled and checked)
        selected_populations = []
        if self.population_filter_group and self.population_filter_group.isEnabled() and self.population_filter_group.isChecked():
            for pop_id, cb in self.population_checkboxes.items():
                if cb.isChecked():
                    selected_populations.append(pop_id)
        
        return {
            'rows': rows,
            'only_visible_columns': bool(self.only_visible_cb.isChecked()),
            'remember': bool(self.remember_cb.isChecked()),
            'required_populated_attributes': required_populated_attributes,
            'excluded_metadata': excluded_metadata,
            'selected_populations': selected_populations,
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
        ensure_dialog_caption_fit(self)
    
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
        ensure_dialog_caption_fit(self)
    
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


class ImportWizardDialog(QtWidgets.QDialog):
    """Wizard-style dialog for import with back/forward navigation and radio buttons."""
    
    def __init__(
        self,
        parent=None,
        db_connections: dict = None,
        ldap_connections: dict = None,
        manage_db_callback=None,
        manage_ldap_callback=None,
        last_method: str = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Import Data - Wizard")
        self.setModal(True)
        self.setMinimumSize(500, 300)
        
        self.db_connections = db_connections or {}
        self.ldap_connections = ldap_connections or {}
        self.manage_db_callback = manage_db_callback
        self.manage_ldap_callback = manage_ldap_callback
        self.last_method = last_method or 'csv'
        self.current_step = 0
        self.selected_connection = None
        self.result = {}
        self._new_ldap_option = "<Create New LDAP Connection...>"
        self._new_db_option = "<Create New Database Connection...>"
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Title
        title = QtWidgets.QLabel("Select Import Source")
        title_font = title.font()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        layout.addSpacing(10)
        
        # Content area
        self.content_layout = QtWidgets.QVBoxLayout()
        layout.addLayout(self.content_layout)
        
        layout.addSpacing(10)
        
        # Navigation buttons
        nav_layout = QtWidgets.QHBoxLayout()
        self.back_btn = QtWidgets.QPushButton("Back")
        self.back_btn.clicked.connect(self.go_back)
        self.back_btn.setEnabled(False)
        nav_layout.addWidget(self.back_btn)
        
        nav_layout.addStretch()
        
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        nav_layout.addWidget(cancel_btn)
        
        self.next_btn = QtWidgets.QPushButton("Next")
        self.next_btn.clicked.connect(self.go_next)
        nav_layout.addWidget(self.next_btn)
        
        layout.addLayout(nav_layout)
        
        self.show_step(0)
        ensure_dialog_caption_fit(self)
    
    def show_step(self, step: int):
        """Show the appropriate step of the wizard."""
        # Clear content layout safely (widgets, nested layouts, spacers).
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
                continue
            nested = item.layout()
            if nested is not None:
                while nested.count():
                    nitem = nested.takeAt(0)
                    nw = nitem.widget()
                    if nw is not None:
                        nw.deleteLater()
        
        if step == 0:
            self.show_import_type_selection()
        elif step == 1:
            self.show_connection_selection()
        elif step == 2:
            self.show_query_mode_selection()
        
        self.current_step = step
        self.next_btn.setEnabled(True)
        self.back_btn.setEnabled(step > 0)
        self.next_btn.setText("Next" if step < 2 else "Finish")
    
    def show_import_type_selection(self):
        """Step 0: Select import type (CSV, LDIF, Database, LDAP)."""
        label = QtWidgets.QLabel("Select Import Format:")
        self.content_layout.addWidget(label)
        
        self.rb_csv = QtWidgets.QRadioButton("CSV File")
        self.rb_ldif = QtWidgets.QRadioButton("LDIF File")
        self.rb_db = QtWidgets.QRadioButton("Database")
        self.rb_ldap = QtWidgets.QRadioButton("LDAP Directory")
        # pre-select the last used method
        {
            'csv': self.rb_csv,
            'ldif': self.rb_ldif,
            'db': self.rb_db,
            'ldap': self.rb_ldap,
        }.get(self.last_method, self.rb_csv).setChecked(True)
        
        self.content_layout.addWidget(self.rb_csv)
        self.content_layout.addWidget(self.rb_ldif)
        self.content_layout.addWidget(self.rb_db)
        self.content_layout.addWidget(self.rb_ldap)
        self.content_layout.addStretch()
    
    def show_connection_selection(self):
        """Step 1: Select source connection (DB or LDAP)."""
        source_type = self.result.get('source_type')
        if source_type == 'ldap':
            label = QtWidgets.QLabel("Select LDAP Connection:")
            source_connections = self.ldap_connections
        else:
            label = QtWidgets.QLabel("Select Database Connection:")
            source_connections = self.db_connections
        self.content_layout.addWidget(label)
        
        self.conn_combo = QtWidgets.QComboBox()
        if source_connections:
            if source_type == 'ldap':
                self.conn_combo.addItem(self._new_ldap_option)
            else:
                self.conn_combo.addItem(self._new_db_option)
            self.conn_combo.addItems(list(source_connections.keys()))
        else:
            self.conn_combo.addItem("(No connections available)")
            self.next_btn.setEnabled(False)
        
        self.content_layout.addWidget(self.conn_combo)
        
        # Add Manage button for existing connections
        if source_connections:
            manage_btn = QtWidgets.QPushButton("Manage Connections...")
            if source_type == 'ldap':
                manage_btn.clicked.connect(self._manage_ldap_connections)
            else:
                manage_btn.clicked.connect(self._manage_db_connections)
            self.content_layout.addWidget(manage_btn)

        if not source_connections:
            if source_type == 'ldap':
                note = QtWidgets.QLabel("No LDAP connections found. Use LDAP connection management to add one.")
            else:
                note = QtWidgets.QLabel("No database connections found. Use DB connection management to add one.")
            note.setWordWrap(True)
            note.setStyleSheet("color: #666;")
            self.content_layout.addWidget(note)

            if source_type == 'ldap':
                manage_btn = QtWidgets.QPushButton("Manage LDAP Connections...")
                manage_btn.clicked.connect(self._manage_ldap_connections)
            else:
                manage_btn = QtWidgets.QPushButton("Manage DB Connections...")
                manage_btn.clicked.connect(self._manage_db_connections)
            self.content_layout.addWidget(manage_btn)

        self.content_layout.addStretch()

    def _manage_db_connections(self):
        """Open DB connection manager and refresh wizard connection list."""
        if callable(self.manage_db_callback):
            try:
                self.manage_db_callback()
            except Exception:
                pass
        self._reload_connections_from_parent()
        self.show_step(1)

    def _manage_ldap_connections(self):
        """Open LDAP connection manager and refresh wizard connection list."""
        if callable(self.manage_ldap_callback):
            try:
                self.manage_ldap_callback()
            except Exception:
                pass
        self._reload_connections_from_parent()
        self.show_step(1)

    def _reload_connections_from_parent(self):
        """Refresh local connection snapshots after manager dialogs close."""
        p = self.parent()
        if p is None or not hasattr(p, '_read_config'):
            return
        try:
            cfg = p._read_config()
            self.db_connections = cfg.get('db_connections', {})
            self.ldap_connections = cfg.get('ldap_connections', {})
        except Exception:
            pass
    
    def _create_new_db_connection(self):
        """Open DB connection dialog to create a new connection and refresh the list."""
        p = self.parent()
        if p is None or not hasattr(p, '_create_new_db_connection'):
            return
        try:
            new_conn_name = p._create_new_db_connection()
            if new_conn_name:
                # Reload connections and refresh the step
                self._reload_connections_from_parent()
                self.show_step(1)
                # Set the newly created connection as selected
                idx = self.conn_combo.findText(new_conn_name)
                if idx >= 0:
                    self.conn_combo.setCurrentIndex(idx)
        except Exception:
            pass
    
    def show_query_mode_selection(self):
        """Step 2: Select DB table/query mode or skip for LDAP."""
        if self.result.get('source_type') == 'ldap':
            label = QtWidgets.QLabel("LDAP import is ready.")
            self.content_layout.addWidget(label)
            self.content_layout.addStretch()
            return

        label = QtWidgets.QLabel("Select Import Source:")
        self.content_layout.addWidget(label)
        
        self.rb_table = QtWidgets.QRadioButton("Import from Table")
        self.rb_custom = QtWidgets.QRadioButton("Import from Custom Query")
        self.rb_table.setChecked(True)
        
        self.content_layout.addWidget(self.rb_table)
        self.content_layout.addWidget(self.rb_custom)
        self.content_layout.addStretch()
    
    def go_next(self):
        """Move to next step or finish."""
        if self.current_step == 0:
            # Determine source type and update result
            if self.rb_csv.isChecked():
                self.result['source_type'] = 'csv'
                self.accept()
            elif self.rb_ldif.isChecked():
                self.result['source_type'] = 'ldif'
                self.accept()
            elif self.rb_db.isChecked():
                self.result['source_type'] = 'db'
                self.show_step(1)
            elif self.rb_ldap.isChecked():
                self.result['source_type'] = 'ldap'
                self.show_step(1)
        elif self.current_step == 1:
            self.selected_connection = self.conn_combo.currentText()
            if self.result.get('source_type') == 'ldap' and self.selected_connection == self._new_ldap_option:
                self._manage_ldap_connections()
                return
            if self.result.get('source_type') == 'db' and self.selected_connection == self._new_db_option:
                self._create_new_db_connection()
                return
            if not self.selected_connection or self.selected_connection == "(No connections available)":
                QtWidgets.QMessageBox.warning(self, "No Connection", "Please select a valid connection.")
                return
            self.result['connection_name'] = self.selected_connection
            self.show_step(2)
        elif self.current_step == 2:
            if self.result.get('source_type') == 'db':
                query_mode = 'custom' if self.rb_custom.isChecked() else 'table'
                self.result['query_mode'] = query_mode
            self.accept()
    
    def go_back(self):
        """Move to previous step."""
        if self.current_step > 0:
            self.show_step(self.current_step - 1)
    
    def get_result(self) -> dict:
        """Return the import source selection result."""
        return self.result
