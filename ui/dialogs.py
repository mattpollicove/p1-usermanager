"""Reusable Qt dialogs used by the UserManager UI.

Contains small, focused dialogs for editing user fields, selecting
table columns, and viewing/editing JSON payloads.
"""

import json
import sys
from pathlib import Path

# Add project root to sys.path when running this file directly so
# `from ui.dialogs` and other absolute imports resolve in editor-run mode.
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from PySide6 import QtWidgets, QtCore, QtGui


class EditUserDialog(QtWidgets.QDialog):
    """Dialog for editing user information."""
    def __init__(self, user_data, pop_map, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit User")
        self.setModal(True)
        layout = QtWidgets.QFormLayout(self)
        
        self.username = QtWidgets.QLineEdit(user_data.get('username', ''))
        self.email = QtWidgets.QLineEdit(user_data.get('email', ''))
        self.first_name = QtWidgets.QLineEdit(user_data.get('name', {}).get('given', ''))
        self.last_name = QtWidgets.QLineEdit(user_data.get('name', {}).get('family', ''))
        self.phone = QtWidgets.QLineEdit()
        phones = user_data.get('phoneNumbers', [])
        if phones:
            self.phone.setText(phones[0].get('number', ''))
        self.street = QtWidgets.QLineEdit(user_data.get('address', {}).get('streetAddress', ''))
        self.city = QtWidgets.QLineEdit(user_data.get('address', {}).get('locality', ''))
        self.state = QtWidgets.QLineEdit(user_data.get('address', {}).get('region', ''))
        self.zip = QtWidgets.QLineEdit(user_data.get('address', {}).get('postalCode', ''))
        self.country = QtWidgets.QLineEdit(user_data.get('address', {}).get('country', ''))
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
        layout = QtWidgets.QHBoxLayout(self)
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
            layout.addLayout(col_layout)
        
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_selected(self):
        """Return the list of selected column names."""
        return [col for col, cb in self.checkboxes.items() if cb.isChecked()]


class JSONViewDialog(QtWidgets.QDialog):
    """Dialog for viewing and optionally editing JSON content."""
    def __init__(self, data, editable, parent, user_id, col_name):
        super().__init__(parent)
        self.setWindowTitle("JSON Content")
        self.user_id = user_id
        self.col_name = col_name
        self.parent = parent
        layout = QtWidgets.QVBoxLayout(self)
        self.text = QtWidgets.QTextEdit()
        self.text.setPlainText(json.dumps(data, indent=2))
        if not editable:
            self.text.setReadOnly(True)
        layout.addWidget(self.text)
        buttons = QtWidgets.QHBoxLayout()
        if editable:
            save_btn = QtWidgets.QPushButton("Save")
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
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(600, 400)
        layout = QtWidgets.QVBoxLayout(self)
        self.text = QtWidgets.QTextEdit()
        self.text.setReadOnly(not bool(editable))
        self.text.setPlainText(text or '')
        layout.addWidget(self.text)
        btns = QtWidgets.QDialogButtonBox()
        if editable:
            save_btn = QtWidgets.QPushButton("Save")
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
        layout.addWidget(note)

        # Table of all headers with suggested mappings (editable)
        # Add a third column which shows the mapping "type" (id/name) compactly
        self.table = QtWidgets.QTableWidget(len(self.headers), 3)
        self.table.setHorizontalHeaderLabels(["File Header", "Mapped Attribute", "Type"])
        self.table.horizontalHeader().setStretchLastSection(True)

        def _suggest_attr(hdr: str) -> str:
            if not hdr:
                return hdr
            s = hdr.strip()
            low = s.lower()
            # Common explicit mappings
            commons = {
                'first name': 'name.given', 'first_name': 'name.given', 'firstname': 'name.given', 'given': 'name.given',
                'last name': 'name.family', 'last_name': 'name.family', 'lastname': 'name.family', 'family': 'name.family',
                'email': 'email', 'e-mail': 'email',
                'username': 'username', 'user name': 'username', 'user': 'username',
                'phone': 'phoneNumbers', 'phone number': 'phoneNumbers', 'phone_number': 'phoneNumbers', 'phonenumber': 'phoneNumbers',
                'population': 'population.id', 'population.name': 'population.id',
                'id': 'id', 'uuid': 'id',
                'street': 'address.street', 'address.street': 'address.street',
                'city': 'address.city', 'state': 'address.region', 'zip': 'address.postalCode', 'postalcode': 'address.postalCode', 'country': 'address.country'
            }
            if low in commons:
                return commons[low]
            # Try dot-notation heuristics
            key = low.replace(' ', '.').replace('_', '.')
            if key in ('first', 'given'):
                return 'name.given'
            if key in ('last', 'family', 'surname'):
                return 'name.family'
            if key.startswith('name.'):
                return key
            return key

        def _make_type_icon(kind: str) -> QtGui.QPixmap:
            """Return a small circular pixmap for the given kind ('id'|'name')."""
            pix = QtGui.QPixmap(14, 14)
            pix.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(pix)
            try:
                painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
                if kind == 'id':
                    color = QtGui.QColor('#d9534f')
                elif kind == 'name':
                    color = QtGui.QColor('#007bff')
                else:
                    color = QtGui.QColor('#cccccc')
                brush = QtGui.QBrush(color)
                painter.setBrush(brush)
                pen = QtGui.QPen(QtCore.Qt.transparent)
                painter.setPen(pen)
                painter.drawEllipse(1, 1, 12, 12)
            finally:
                painter.end()
            return pix

        for r, h in enumerate(self.headers):
            item_h = QtWidgets.QTableWidgetItem(h)
            item_h.setFlags(item_h.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(r, 0, item_h)
            suggested = _suggest_attr(h)
            # If an explicit initial mapping exists for this header use it
            mapped_val = None
            try:
                if initial_mapping and h in initial_mapping:
                    mapped_val = initial_mapping.get(h)
            except Exception:
                mapped_val = None
            item_m = QtWidgets.QTableWidgetItem(mapped_val if mapped_val is not None else suggested)
            # If this header is mapped to the system `id`, mark it read-only and clarify tooltip
            try:
                mapped_target = mapped_val if mapped_val is not None else suggested
                if mapped_target == 'id':
                    item_m.setFlags(item_m.flags() & ~QtCore.Qt.ItemIsEditable)
                    item_m.setToolTip('System-generated ID (read-only) — values will be ignored on import')
                    type_item = QtWidgets.QTableWidgetItem()
                    type_item.setFlags(type_item.flags() & ~QtCore.Qt.ItemIsEditable)
                    type_item.setIcon(QtGui.QIcon(_make_type_icon('id')))
                    type_item.setToolTip('population.id (read-only)')
                    self.table.setItem(r, 2, type_item)
                else:
                    item_m.setToolTip('Suggested mapping; edit if needed')
                    # If the suggested mapping is population.name or population.id, show icon type
                    if mapped_target.startswith('population'):
                        kind = 'id' if mapped_target.endswith('.id') else 'name'
                        type_item = QtWidgets.QTableWidgetItem()
                        type_item.setFlags(type_item.flags() & ~QtCore.Qt.ItemIsEditable)
                        type_item.setIcon(QtGui.QIcon(_make_type_icon(kind)))
                        type_item.setToolTip(f'population.{kind}')
                        self.table.setItem(r, 2, type_item)
            except Exception:
                item_m.setToolTip('Suggested mapping; edit if needed')
            self.table.setItem(r, 1, item_m)
            # ensure Type column has an item for rows without population mapping
            if not self.table.item(r, 2):
                empty = QtWidgets.QTableWidgetItem('')
                empty.setFlags(empty.flags() & ~QtCore.Qt.ItemIsEditable)
                self.table.setItem(r, 2, empty)
        # Improve column sizing: left column content-sized, mapping column stretches, type column content-sized
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        # Add tooltip to Type column header explaining the icons
        try:
            hi = self.table.horizontalHeaderItem(2)
            if hi:
                hi.setToolTip('Icon indicates whether the population mapping will pass an id or a name (population.id / population.name)')
        except Exception:
            pass
        # Add a subtle bottom border to header row for visual separation
        try:
            self.table.horizontalHeader().setStyleSheet('QHeaderView::section { border-bottom: 1px solid #999; padding: 4px; }')
        except Exception:
            pass
        layout.addWidget(self.table)

        # Update Type column when the mapping cell is edited by the user
        self._suppress_item_changed = False
        self.table.itemChanged.connect(self._on_table_item_changed)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        # Option to remember/save this mapping for the active profile
        self.remember_cb = QtWidgets.QCheckBox('Remember mapping for this profile')
        # Default to checked when an initial mapping was provided for this profile
        try:
            self.remember_cb.setChecked(bool(initial_mapping))
        except Exception:
            self.remember_cb.setChecked(False)
        layout.addWidget(self.remember_cb)
        layout.addWidget(buttons)

    def _validate_mappings(self, mapping: dict) -> (bool, str):
        """Validate mapping rules. Returns (True, '') if valid, otherwise (False, message).

        Rule: any mapping that begins with 'population' must be exactly
        'population.id' or 'population.name'. This prevents accidental
        arbitrary population attributes from being passed through import.
        """
        for hdr, mapped in mapping.items():
            if not mapped:
                continue
            low = mapped.strip()
            if low.startswith('population'):
                if low not in ('population.id', 'population.name'):
                    return False, f"Invalid mapping for '{hdr}': '{mapped}'. Population mappings must be 'population.id' or 'population.name'."
        return True, ''

    def _on_accept(self):
        # Build a tentative mapping and validate before accepting.
        mapping, fixed_pop_id, fixed_enabled, _remember = self.get_mapping()
        ok, msg = self._validate_mappings(mapping)
        if not ok:
            # Show a small resizable dialog with an inline help link to README
            # Reminder: When changing mapping behavior or UI text, also update
            # the README and `show_*_help` strings so users see accurate help.
            # See DEVELOPMENT_RULES.md for the project rule about help docs.
            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle('Invalid Mapping')
            lay = QtWidgets.QVBoxLayout(dlg)
            lab = QtWidgets.QLabel(msg + "\nSee the <a href='file://" + str((Path(__file__).resolve().parent.parent / 'README.md').resolve()) + "'>README</a> for mapping help.")
            lab.setOpenExternalLinks(True)
            lab.setWordWrap(True)
            lay.addWidget(lab)
            btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
            btns.accepted.connect(dlg.accept)
            lay.addWidget(btns)
            try:
                dlg.resize(700, 200)
            except Exception:
                pass
            dlg.exec()
            return
        # All good — accept the dialog
        self.accept()

    def _on_table_item_changed(self, item: QtWidgets.QTableWidgetItem):
        # Keep updates idempotent and avoid recursion when programmatically changing items
        if self._suppress_item_changed:
            return
        try:
            row = item.row()
            col = item.column()
            # Only react to changes in the Mapped Attribute column
            if col != 1:
                return
            text = item.text().strip()
            # Determine type for population mappings
            if text.startswith('population'):
                kind = 'id' if text.endswith('.id') else 'name' if text.endswith('.name') else ''
            else:
                kind = ''
            self._suppress_item_changed = True
            try:
                type_item = self.table.item(row, 2)
                if not type_item:
                    type_item = QtWidgets.QTableWidgetItem('')
                    self.table.setItem(row, 2, type_item)
                # set icon for kind or clear icon
                if kind:
                    type_item.setIcon(QtGui.QIcon(_make_type_icon(kind)))
                    type_item.setToolTip(f'population.{kind}')
                else:
                    type_item.setIcon(QtGui.QIcon())
                    type_item.setToolTip('')
            finally:
                self._suppress_item_changed = False
        except Exception:
            pass

    def get_mapping(self):
        """Return a tuple `(mapping_dict, fixed_population_id)`.

        The mapping dict maps file-header -> attribute name. If the user
        selected a fixed population in the dropdown, `fixed_population_id`
        will be that id (string). If the user chose to use the CSV field
        for population, `fixed_population_id` will be None and the mapping
        should contain the header -> population.id or population.name entry as appropriate.
        """
        mapping = {}
        # First, incorporate selections from the required fields (if any)
        def _apply_field(cb: QtWidgets.QComboBox, target_attr: str):
            if cb.currentText() and cb.currentText() != '<None>':
                mapping[cb.currentText()] = target_attr

        _apply_field(self.username_field, 'username')
        _apply_field(self.email_field, 'email')
        _apply_field(self.given_field, 'name.given')
        _apply_field(self.family_field, 'name.family')

        # population: if a CSV header was chosen, map that header to population.id
        if self.population_field.currentText() and self.population_field.currentText() != '<None>':
            mapping[self.population_field.currentText()] = 'population.id'

        # Table entries override/augment the above
        for r in range(self.table.rowCount()):
            header = self.table.item(r, 0).text()
            mapped = self.table.item(r, 1).text().strip()
            if mapped:
                mapping[header] = mapped

        # Determine fixed population id (if chosen)
        fixed_pop_id = None
        if self.population_fixed.currentIndex() > 0:
            fixed_pop_id = self.population_fixed.currentData()

        # Determine fixed enabled value or mapping
        fixed_enabled = None
        try:
            en_data = self.enabled_field.currentData()
            en_text = self.enabled_field.currentText()
            if isinstance(en_data, bool):
                fixed_enabled = bool(en_data)
            else:
                if en_text and en_text != '<None>':
                    # a header was chosen to map to enabled
                    mapping[en_text] = 'enabled'
        except Exception:
            fixed_enabled = None

        # If an initial fixed population id was provided, prefer that when
        # nothing was chosen in the fixed dropdown by the user.
        try:
            if not fixed_pop_id and getattr(self, 'initial_fixed_pop_id', None):
                # find the index that has this data
                for i in range(self.population_fixed.count()):
                    if self.population_fixed.itemData(i) == self.initial_fixed_pop_id:
                        self.population_fixed.setCurrentIndex(i)
                        fixed_pop_id = self.initial_fixed_pop_id
                        break
        except Exception:
            pass

        # Resize dialog sensibly based on available screen space so mappings
        # and mapped attributes are visible without manual resizing.
        try:
            screen = QtWidgets.QApplication.primaryScreen()
            geom = screen.availableGeometry()
            w = max(800, int(geom.width() * 0.6))
            h = max(400, int(geom.height() * 0.5))
            # Keep some margins from screen edges
            w = min(w, geom.width() - 120)
            h = min(h, geom.height() - 120)
            self.resize(w, h)
        except Exception:
            try:
                self.resize(900, 500)
            except Exception:
                pass

        return mapping, fixed_pop_id, fixed_enabled, bool(getattr(self, 'remember_cb', QtWidgets.QCheckBox()).isChecked())


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
