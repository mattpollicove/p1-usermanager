"""Shared LDAP DN browsing utilities for dialogs."""

import logging
from typing import Dict, Tuple

from PySide6 import QtCore, QtGui, QtWidgets
from ldap3 import BASE, SUBTREE

logger = logging.getLogger(__name__)


def _extract_rdn(dn):
    """Extract the RDN (first component) from a DN string.
    
    For example, 'cn=Users,dc=example,dc=net' returns 'Users'.
    """
    if not dn:
        return ''
    parts = dn.split(',')
    if not parts:
        return ''
    first_part = parts[0].strip()
    if '=' not in first_part:
        return ''
    return first_part.split('=', 1)[1].strip()


def _extract_ou_names(dn):
    """Extract all OU values from a DN.
    
    For example, 'cn=Users,ou=Groups,ou=Company,dc=example,dc=net' returns ['Groups', 'Company'].
    """
    if not dn:
        return []
    ous = []
    for part in dn.split(','):
        part = part.strip()
        if part.lower().startswith('ou='):
            value = part.split('=', 1)[1].strip()
            ous.append(value)
    return ous


def _match_search_term(dn, search_term):
    """Check if DN matches search term with RDN prioritization.
    
    Returns priority score: 0 = no match, 1 = OU match, 2 = RDN match
    """
    if not search_term:
        return 2, _extract_rdn(dn)
    
    search_lower = search_term.lower()
    
    # Check RDN (highest priority)
    rdn = _extract_rdn(dn)
    if search_lower in rdn.lower():
        return 2, rdn
    
    # Check OUs (second priority)
    ous = _extract_ou_names(dn)
    for ou in ous:
        if search_lower in ou.lower():
            return 1, ou
    
    return 0, ''


def _get_domain_partition(contexts):
    """Determine the domain partition from naming contexts.
    
    Prefers contexts with 'dc=com' or 'dc=' patterns over others.
    """
    if not contexts:
        return None
    
    # Prefer contexts with 'dc=' (domain component)
    domain_contexts = [c for c in contexts if 'dc=' in c.lower()]
    if domain_contexts:
        return domain_contexts[0]
    
    return contexts[0] if contexts else None


def browse_ldap_dn(parent, config: Dict, title: str = "Select DN") -> str:
    """Browse and select an LDAP DN from the directory tree with optional OU filtering.
    
    Args:
        parent: Parent widget for dialog
        config: Dictionary with LDAP connection details (host, port, use_ssl, bind_dn, password, etc.)
        title: Dialog title
        
    Returns:
        Selected DN string, or empty string if cancelled
    """
    from api import ldap_utils
    
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
    
    # Search field for progressive entry filtering
    search_layout = QtWidgets.QHBoxLayout()
    search_input = QtWidgets.QLineEdit()
    search_input.setPlaceholderText("Type to search (RDN, then OUs)...")
    search_input.setMaximumHeight(32)
    search_clear_btn = QtWidgets.QPushButton("Clear")
    search_clear_btn.setMaximumWidth(60)
    search_layout.addWidget(search_input, 1)
    search_layout.addWidget(search_clear_btn)
    layout.addLayout(search_layout)
    
    # Tree widget for directory structure
    tree = QtWidgets.QTreeWidget()
    tree.setHeaderLabel("Directory Structure")
    tree.setAnimated(True)
    layout.addWidget(tree)
    
    info_label = QtWidgets.QLabel("Loading directory structure...")
    info_label.setStyleSheet("color: gray; font-size: 11px;")
    layout.addWidget(info_label)
    
    # Dialog buttons
    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.StandardButton.Ok |
        QtWidgets.QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    
    domain_partition = None
    
    try:
        with ldap_utils._connect(
            config.get('host', ''),
            int(config.get('port') or 389),
            bool(config.get('use_ssl', False)),
            config.get('bind_dn', ''),
            config.get('password', ''),
            bool(config.get('start_tls', False)),
            certificate=config.get('certificate'),
            skip_cert_validation=config.get('skip_cert_validation', False),
        ) as conn:
            # Get root DSE to find available naming contexts
            conn.search("", "(objectClass=*)", search_scope=BASE, attributes=['*', '+'])
            if conn.entries:
                root_attrs = conn.entries[0].entry_attributes_as_dict
                contexts = (
                    root_attrs.get('namingContexts') or 
                    root_attrs.get('defaultNamingContext') or 
                    []
                )
                if not isinstance(contexts, list):
                    contexts = [contexts] if contexts else []
            else:
                contexts = [config.get('base_dn', '')] if config.get('base_dn') else []
            
            contexts = [c for c in contexts if c]
            
            if not contexts:
                info_label.setText("Could not discover directory suffixes. Using configured base DN.")
                if config.get('base_dn'):
                    contexts = [config.get('base_dn')]
            
            domain_partition = _get_domain_partition(contexts)
            
            # Create tree items for each naming context
            domain_partition_item = None
            for context in contexts:
                item = QtWidgets.QTreeWidgetItem(tree, [str(context)])
                item.setData(0, QtCore.Qt.ItemDataRole.UserRole, str(context))
                if context == domain_partition:
                    domain_partition_item = item
                QtWidgets.QTreeWidgetItem(item, ["Loading..."])
            
            if contexts:
                if domain_partition:
                    info_label.setText(f"Domain partition: {domain_partition}. Expand to browse.")
                else:
                    info_label.setText(f"Found {len(contexts)} directory suffix(es). Click to expand and browse.")
            
            if domain_partition_item:
                tree.expandItem(domain_partition_item)
                tree.setCurrentItem(domain_partition_item)
        
        def expand_item(item):
            """Load child entries when a tree item is expanded."""
            dn = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            if not dn:
                return
            
            item.takeChildren()
            
            try:
                with ldap_utils._connect(
                    config.get('host', ''),
                    int(config.get('port') or 389),
                    bool(config.get('use_ssl', False)),
                    config.get('bind_dn', ''),
                    config.get('password', ''),
                    bool(config.get('start_tls', False)),
                    certificate=config.get('certificate'),
                    skip_cert_validation=config.get('skip_cert_validation', False),
                ) as conn:
                    if ou_only_cb.isChecked():
                        search_filter = "(objectClass=organizationalUnit)"
                    else:
                        search_filter = "(|(objectClass=*))"
                    
                    conn.search(dn, search_filter, search_scope=SUBTREE, 
                               attributes=['name', 'cn', 'objectClass'], size_limit=1000)
                    children = sorted(conn.entries, key=lambda e: str(e.entry_dn))
                    for entry in children:
                        child_item = QtWidgets.QTreeWidgetItem(item, [str(entry.entry_dn)])
                        child_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, str(entry.entry_dn))
                        QtWidgets.QTreeWidgetItem(child_item, ["Loading..."])
            except Exception as e:
                error_str = str(e)
                if 'certificate' in error_str.lower() or 'ssl' in error_str.lower():
                    if hasattr(parent, 'handle_ldap_certificate_error'):
                        should_retry, cert_path = parent.handle_ldap_certificate_error(
                            config.get('host', ''),
                            int(config.get('port') or 389),
                            error_str,
                            config
                        )
                        if should_retry:
                            expand_item(item)
                        return
                logger.debug(f"Error expanding LDAP tree item: {e}")
        
        def on_filter_changed():
            """Refresh tree when filter checkbox is toggled."""
            for i in range(tree.topLevelItemCount()):
                top_item = tree.topLevelItem(i)
                tree.collapseItem(top_item)
                top_item.takeChildren()
                QtWidgets.QTreeWidgetItem(top_item, ["Loading..."])
        
        def _get_all_tree_items():
            """Recursively get all items in the tree."""
            items = []
            for i in range(tree.topLevelItemCount()):
                top_item = tree.topLevelItem(i)
                items.append(top_item)
                stack = [top_item]
                while stack:
                    current = stack.pop()
                    for j in range(current.childCount()):
                        child = current.child(j)
                        items.append(child)
                        stack.append(child)
            return items
        
        def _reset_tree_visibility():
            """Show all items and remove highlighting."""
            for item in _get_all_tree_items():
                item.setHidden(False)
                font = item.font(0)
                font.setBold(False)
                item.setFont(0, font)
                item.setBackground(0, QtGui.QBrush())
        
        def on_search_changed(text):
            """Handle progressive search input."""
            search_term = text.strip()
            
            if not search_term:
                _reset_tree_visibility()
                search_input.setStyleSheet("")
                return
            
            all_items = _get_all_tree_items()
            matches = []
            
            for item in all_items:
                dn = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                if not dn:
                    continue
                
                score, matched_text = _match_search_term(dn, search_term)
                if score > 0:
                    matches.append((score, dn, item, matched_text))
            
            if not matches:
                search_input.setStyleSheet("background-color: #ffe0e0;")
                _reset_tree_visibility()
                for item in all_items:
                    item.setHidden(True)
                return
            
            search_input.setStyleSheet("")
            matches.sort(key=lambda x: (-x[0], x[1]))
            
            # Build visible set and ancestry map
            visible_dns = {m[1] for m in matches}
            ancestry_map = {}
            for item in all_items:
                dn = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                if not dn:
                    continue
                parent_item = item.parent()
                if parent_item:
                    parent_dn = parent_item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                    if parent_dn:
                        if parent_dn not in ancestry_map:
                            ancestry_map[parent_dn] = set()
                        ancestry_map[parent_dn].add(dn)
            
            def add_ancestors(dn):
                parts = dn.split(',')
                while len(parts) > 1:
                    parts = parts[1:]
                    parent = ','.join(parts)
                    visible_dns.add(parent)
                    if parent in ancestry_map:
                        for child in ancestry_map[parent]:
                            add_ancestors(child)
            
            for dn in list(visible_dns):
                add_ancestors(dn)
            
            # Highlight and show items
            for item in all_items:
                dn = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                is_match = dn in {m[1] for m in matches}
                is_visible = dn in visible_dns
                
                item.setHidden(not is_visible)
                
                if is_match:
                    font = item.font(0)
                    font.setBold(True)
                    item.setFont(0, font)
                    item.setBackground(0, QtGui.QBrush(QtGui.QColor("#e8f5e9")))
                else:
                    font = item.font(0)
                    font.setBold(False)
                    item.setFont(0, font)
                    item.setBackground(0, QtGui.QBrush())
            
            # Expand ancestors of matches for visibility
            for item in all_items:
                dn = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
                if dn in {m[1] for m in matches}:
                    parent = item.parent()
                    while parent:
                        tree.expandItem(parent)
                        parent = parent.parent()
        
        # Connect signals
        tree.itemExpanded.connect(lambda item: expand_item(item))
        ou_only_cb.toggled.connect(on_filter_changed)
        search_input.textChanged.connect(on_search_changed)
        search_clear_btn.clicked.connect(lambda: search_input.clear())
    
    except Exception as e:
        logger.error(f"Error initializing LDAP browser: {e}")
        info_label.setText(f"Error: {e}")
    
    # Show dialog and return selected DN
    if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
        item = tree.currentItem()
        if item:
            return item.data(0, QtCore.Qt.ItemDataRole.UserRole) or ""
    
    return ""
