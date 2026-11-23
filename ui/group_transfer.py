"""Dialogs and background tasks for the separate group migration workflow."""

import asyncio
import csv

import httpx
from PySide6 import QtCore, QtWidgets

from api.client import PingOneClient
from api.group_transfer import apply_import, export_pingone, preflight, read_csv, write_csv
from api.pingone_groups import PingOneGroups
from ui.background import background


def review(window, title, heading, lines, action=None):
    dialog = QtWidgets.QDialog(window)
    dialog.setWindowTitle(title)
    dialog.resize(780, 480)
    layout = QtWidgets.QVBoxLayout(dialog)
    label = QtWidgets.QLabel(heading)
    label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    layout.addWidget(label)
    text = QtWidgets.QPlainTextEdit("\n".join(lines))
    text.setReadOnly(True)
    layout.addWidget(text)
    buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    if action:
        button = buttons.addButton(action, QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        button.setAutoDefault(False)
        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Close).setDefault(True)
        buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)
    return dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted


def replacement_selection(window, data):
    if not data.groups:
        return frozenset()
    dialog = QtWidgets.QDialog(window)
    dialog.setWindowTitle("Optional: Replace Direct Memberships")
    layout = QtWidgets.QVBoxLayout(dialog)
    hint = QtWidgets.QLabel(
        "Leave all groups unchecked for an additive import. For checked existing groups, "
        "the source is the complete list of direct users. A checked group with no source "
        "members removes all its direct users. Nesting and inherited memberships are not replaced."
    )
    hint.setWordWrap(True)
    layout.addWidget(hint)
    groups = QtWidgets.QListWidget()
    for key, group in sorted(data.groups.items()):
        item = QtWidgets.QListWidgetItem(f"{group.name} [{group.scope or 'selected scope'}; {key}]")
        item.setData(QtCore.Qt.ItemDataRole.UserRole, key)
        item.setCheckState(QtCore.Qt.CheckState.Unchecked)
        groups.addItem(item)
    layout.addWidget(groups)
    buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok
                                        | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return None
    return frozenset(groups.item(i).data(QtCore.Qt.ItemDataRole.UserRole)
                     for i in range(groups.count())
                     if groups.item(i).checkState() == QtCore.Qt.CheckState.Checked)


def _browse_ldap_dn(parent, config, title="Select DN"):
    """Browse and select an LDAP DN from the directory tree with optional OU filtering."""
    from api import ldap_utils
    import ldap3
    from ldap3 import SUBTREE, LEVEL, BASE
    
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(600, 450)
    layout = QtWidgets.QVBoxLayout(dialog)
    
    # Filter options
    filter_layout = QtWidgets.QHBoxLayout()
    ou_only_cb = QtWidgets.QCheckBox("Show only Organizational Units")
    ou_only_cb.setChecked(True)
    filter_layout.addWidget(ou_only_cb)
    filter_layout.addStretch()
    layout.addLayout(filter_layout)
    
    # Try to fetch available DNs from the LDAP server
    tree = QtWidgets.QTreeWidget()
    tree.setHeaderLabel("Directory Structure")
    tree.setAnimated(True)
    layout.addWidget(tree)
    
    info_label = QtWidgets.QLabel("Loading directory structure...")
    info_label.setStyleSheet("color: gray; font-size: 11px;")
    layout.addWidget(info_label)
    
    try:
        with ldap_utils._connect(
            config.get('host', ''),
            int(config.get('port') or 389),
            bool(config.get('use_ssl', False)),
            config.get('bind_dn', ''),
            config.get('password', ''),
            bool(config.get('start_tls', False))
        ) as conn:
            # Get root DSE to find available naming contexts
            # Use None for attributes to get all available, then filter
            conn.search("", "(objectClass=*)", search_scope=BASE, attributes=['*', '+'])
            if conn.entries:
                root_attrs = conn.entries[0].entry_attributes_as_dict
                # Try multiple attribute names for naming contexts
                contexts = (
                    root_attrs.get('namingContexts') or 
                    root_attrs.get('defaultNamingContext') or 
                    []
                )
                if not isinstance(contexts, list):
                    contexts = [contexts] if contexts else []
            else:
                contexts = [config.get('base_dn', '')] if config.get('base_dn') else []
            
            # Filter out empty strings
            contexts = [c for c in contexts if c]
            
            if not contexts:
                info_label.setText("Could not discover directory suffixes. Using configured base DN.")
                if config.get('base_dn'):
                    contexts = [config.get('base_dn')]
            
            # Create tree items for each naming context
            for context in contexts:
                item = QtWidgets.QTreeWidgetItem(tree, [str(context)])
                item.setData(0, QtCore.Qt.ItemDataRole.UserRole, str(context))
                # Add a placeholder child so the item appears expandable
                QtWidgets.QTreeWidgetItem(item, ["Loading..."])
            
            if contexts:
                info_label.setText(f"Found {len(contexts)} directory suffix(es). Click to expand and browse.")
        
        
        def expand_item(item):
            """Load child entries when a tree item is expanded."""
            dn = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if not dn:
                return
            
            # Clear placeholder
            item.takeChildren()
            
            try:
                with ldap_utils._connect(
                    config.get('host', ''),
                    int(config.get('port') or 389),
                    bool(config.get('use_ssl', False)),
                    config.get('bind_dn', ''),
                    config.get('password', ''),
                    bool(config.get('start_tls', False))
                ) as conn:
                    # Determine search filter based on checkbox
                    if ou_only_cb.isChecked():
                        # Only show Organizational Units
                        search_filter = "(objectClass=organizationalUnit)"
                    else:
                        # Show all objects
                        search_filter = "(|(objectClass=*))"
                    
                    # Search subtree to show full directory structure for selection
                    # Limit to DNs only (no attributes needed for display)
                    conn.search(dn, search_filter, search_scope=SUBTREE, 
                               attributes=['name', 'cn', 'objectClass'], size_limit=1000)
                    children = sorted(conn.entries, key=lambda e: str(e.entry_dn))
                    for entry in children:
                        child_item = QtWidgets.QTreeWidgetItem(item, [str(entry.entry_dn)])
                        child_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, str(entry.entry_dn))
                        # Add placeholder if this might have children
                        QtWidgets.QTreeWidgetItem(child_item, ["Loading..."])
            except Exception:
                pass
        
        def on_filter_changed():
            """Refresh tree when filter checkbox is toggled."""
            # Collapse and re-expand to refresh with new filter
            for i in range(tree.topLevelItemCount()):
                top_item = tree.topLevelItem(i)
                tree.collapseItem(top_item)
                # Clear children to force reload on next expand
                top_item.takeChildren()
                QtWidgets.QTreeWidgetItem(top_item, ["Loading..."])
        
        ou_only_cb.stateChanged.connect(on_filter_changed)
        tree.itemExpanded.connect(expand_item)
    except Exception as e:
        info_label.setText(f"Error loading directory: {e}")
    
    # Buttons
    buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok
                                        | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    
    if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return None
    
    selected = tree.currentItem()
    if selected:
        return selected.data(0, QtCore.Qt.ItemDataRole.UserRole)
    return None


def ldap_mapping(window, config, importing, profiles, mapping_class):
    dialog = QtWidgets.QDialog(window)
    dialog.setWindowTitle("LDAP Group Mapping")
    dialog.resize(700, 650)
    
    main_layout = QtWidgets.QVBoxLayout(dialog)
    
    # Schema selection
    schema_layout = QtWidgets.QHBoxLayout()
    schema_label = QtWidgets.QLabel("LDAP schema:")
    mode = QtWidgets.QComboBox()
    mode.addItems([label for label, (_, attr) in profiles.items() if importing or attr != "memberOf"])
    schema_layout.addWidget(schema_label)
    schema_layout.addWidget(mode)
    schema_layout.addStretch()
    main_layout.addLayout(schema_layout)
    
    # Scroll area for form
    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll_widget = QtWidgets.QWidget()
    form = QtWidgets.QFormLayout(scroll_widget)
    scroll.setWidget(scroll_widget)
    main_layout.addWidget(scroll)
    
    # Group base DN with browse button
    group_base_layout = QtWidgets.QHBoxLayout()
    group_base = QtWidgets.QLineEdit(config.get("base_dn", ""))
    group_base_btn = QtWidgets.QPushButton("Browse...")
    group_base_btn.setMaximumWidth(100)
    group_base_layout.addWidget(group_base)
    group_base_layout.addWidget(group_base_btn)
    form.addRow("Group base DN", group_base_layout)
    
    # User base DN with browse button
    user_base_layout = QtWidgets.QHBoxLayout()
    user_base = QtWidgets.QLineEdit(config.get("base_dn", ""))
    user_base_btn = QtWidgets.QPushButton("Browse...")
    user_base_btn.setMaximumWidth(100)
    user_base_layout.addWidget(user_base)
    user_base_layout.addWidget(user_base_btn)
    form.addRow("User base DN", user_base_layout)
    
    # Group class
    group_class = QtWidgets.QLineEdit()
    form.addRow("Group object class", group_class)
    
    # Additional group filter (single line is OK for this one)
    group_filter = QtWidgets.QLineEdit()
    form.addRow("Additional group filter", group_filter)
    
    # Username attribute
    username = QtWidgets.QLineEdit()
    form.addRow("User's username attribute", username)
    
    # User filter (multi-line)
    user_filter = QtWidgets.QPlainTextEdit()
    user_filter.setMaximumHeight(80)
    user_filter.setPlaceholderText("e.g., (&(objectClass=user)(!(objectClass=computer)))")
    form.addRow("User filter", user_filter)
    
    # Optional: gidNumber for POSIX
    gid = QtWidgets.QSpinBox()
    gid.setRange(0, 2**31 - 1)
    gid.setSpecialValueText("Not assigned")
    if not importing:
        form.addRow("Starting gidNumber for new POSIX groups", gid)
    
    def select(label):
        object_class, attr = profiles[label]
        group_class.setText(object_class or "group")
        group_class.setReadOnly(bool(object_class))
        ad = object_class == "group" or attr == "memberOf"
        username.setText("sAMAccountName" if ad else "uid")
        user_filter.setPlainText("(&(objectClass=user)(!(objectClass=computer)))" if ad else "(objectClass=person)")
        gid.setEnabled(attr == "memberUid")
    
    def browse_group():
        dn = _browse_ldap_dn(dialog, config, "Select Group Search Base DN")
        if dn:
            group_base.setText(dn)
    
    def browse_user():
        dn = _browse_ldap_dn(dialog, config, "Select User Search Base DN")
        if dn:
            user_base.setText(dn)
    
    group_base_btn.clicked.connect(browse_group)
    user_base_btn.clicked.connect(browse_user)
    mode.currentTextChanged.connect(select)
    select(mode.currentText())
    
    # Buttons
    buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok
                                        | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    main_layout.addWidget(buttons)
    
    if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
        return None
    
    mapping = mapping_class(group_base.text(), user_base.text(), group_class.text(),
                            profiles[mode.currentText()][1], username.text(), user_filter.toPlainText(),
                            group_filter.text(), gid.value())
    mapping.validate()
    return mapping


def run_transfer(window, importing, source):
    title = f"{'Import' if importing else 'Export'} Groups ({source})"
    try:
        env, app, secret = window.env_id.text(), window.cl_id.text(), window.cl_sec.text()
        if not (env and app and secret):
            raise ValueError("Select an authenticated PingOne profile first.")
        client = PingOneClient(env, app, secret)

        def ping(action):
            async def run():
                async with httpx.AsyncClient(timeout=30.0) as http:
                    return await action(PingOneGroups(client, http))
            return asyncio.run(run())

        if source == "LDAP":
            from api import ldap_groups

            name, connections = window._choose_ldap_connection("Select LDAP Group Directory")
            if not name:
                return
            config = dict(connections[name])
            mapping = ldap_mapping(window, config, importing, ldap_groups.PROFILES,
                                   ldap_groups.DirectoryMapping)
            if mapping is None:
                return

        if importing:
            if source == "CSV":
                path, _ = QtWidgets.QFileDialog.getOpenFileName(window, title, "", "CSV files (*.csv)")
                if not path:
                    return
                column, ok = QtWidgets.QInputDialog.getText(
                    window, title, "Optional existing CSV column with JSON arrays of usernames (blank for standard format):")
                if not ok:
                    return
                delimiter = ""
                if column.strip():
                    delimiter, ok = QtWidgets.QInputDialog.getText(
                        window, title, "Multi-value delimiter (blank for JSON; use backslash to escape the delimiter):")
                    if not ok:
                        return

                def load(_):
                    with open(path, newline="", encoding="utf-8-sig") as file:
                        return read_csv(file, column.strip() or "members", delimiter)
            else:
                def load(_):
                    with ldap_groups.connect(config) as conn:
                        groups, users = ldap_groups.directory_entries(conn, mapping)
                        return ldap_groups.from_directory(groups, users, mapping)
            data = background(window, title, load)
            scope = ""
            if any(not group.scope for group in data.groups.values()):
                populations = background(window, title, lambda _: ping(lambda api: api.populations()))
                choices = {"Choose a target scope...": "", "Environment-wide": "environment"}
                choices.update({f"{name} [{key}]": key for key, name in sorted(populations.items())})
                choice, ok = QtWidgets.QInputDialog.getItem(window, title, "Scope for groups without one:",
                                                             list(choices), editable=False)
                if not ok:
                    return
                scope = choices[choice]
                if not scope:
                    raise ValueError("Choose an explicit environment or population scope.")
            if source == "LDAP" and mapping.membership == "memberOf":
                # Backlinks are only available for the users returned by the source search.
                replacement = frozenset()
            else:
                replacement = replacement_selection(window, data)
            if replacement is None:
                return
            plan = background(window, title, lambda _: ping(
                lambda api: preflight(api, data, scope, replacement)))
            operations = list(plan.operations())
            preview = [plan.describe(item) for item in operations]
            if not operations:
                review(window, title, f"No changes needed in PingOne environment {env}.", [])
                return
            if not review(window, title, f"Target PingOne environment: {env}\n"
                          f"{len(plan.remove)} direct memberships will be removed. "
                          "The preview itself makes no changes.", preview,
                          "Apply including removals" if plan.remove else "Apply changes"):
                return

            async def write(api, progress):
                current = await preflight(api, data, scope, replacement)
                if current != plan:
                    # The user or group inventory may have changed since preview.
                    if (current.resolved != plan.resolved or current.create != plan.create
                            or [current.describe(op) for op in current.operations()] != preview):
                        raise ValueError("Target changed after preview. Run the import again to review the new plan.")
                return await apply_import(api, current, progress)

            completed, error = background(window, title, lambda progress: ping(lambda api: write(api, progress)))
        else:
            data = background(window, title, lambda _: ping(export_pingone))
            if source == "CSV":
                path, _ = QtWidgets.QFileDialog.getSaveFileName(window, title, "groups.csv", "CSV files (*.csv)")
                if not path:
                    return
                with open(path, "w", newline="", encoding="utf-8") as file:
                    write_csv(file, data)
                QtWidgets.QMessageBox.information(window, title, f"Exported {len(data.groups)} groups to {path}.")
                return

            def ldap_preview(_):
                with ldap_groups.connect(config) as conn:
                    return ldap_groups.export_plan(conn, data, mapping)

            writes = background(window, title, ldap_preview)
            heading = (f"LDAP target: {config.get('host')} / {mapping.group_base}\n"
                       "Only direct memberships and explicit nesting are written. "
                       "New AD groups are global distribution groups.")
            if not writes:
                review(window, title, f"No LDAP changes needed.\n{heading}", [])
                return
            if not review(window, title, heading, [item.describe() for item in writes], "Apply LDAP changes"):
                return

            def ldap_write(progress):
                with ldap_groups.connect(config) as conn:
                    current = ldap_groups.export_plan(conn, data, mapping)
                    if writes != current:
                        raise ValueError("LDAP changed after preview. Run the export again to review the new plan.")
                    return ldap_groups.apply_export(conn, writes, mapping, progress)

            completed, error = background(window, title, ldap_write)
        review(window, title, error or f"Verified {len(completed)} changes.",
               [*(["Rerun to reread the target and skip changes that already succeeded.", ""] if error else []),
                *completed])
    except (ValueError, KeyError, OSError, RuntimeError, ImportError, csv.Error) as exc:
        QtWidgets.QMessageBox.critical(window, title, str(exc))
