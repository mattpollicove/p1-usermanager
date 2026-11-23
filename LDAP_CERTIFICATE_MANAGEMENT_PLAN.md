# LDAP Certificate Management Plan

## Overview

Add self-signed certificate support to LDAP connections using a unified, shared certificate handling approach. This plan ensures LDAP and Database connections use consistent certificate validation logic while respecting their different use patterns.

## User Requirement

- ✓ LDAP connections MUST support self-signed certificate files
- ✓ Connections will use EITHER database role (source/destination) OR LDAP (single)
- ✓ Both should use the SAME unified certificate handling code
- ✓ Implement NOW (not deferred)

## Current State Analysis

### LDAP Connections Today
```python
# Current ldap_utils.py _connect()
server = ldap3.Server(
    host=host,
    port=safe_port,
    use_ssl=bool(use_ssl),
    get_info=ALL,
    connect_timeout=max(3, int(timeout or 15)),
)
# No certificate parameter support
```

**Limitation**: Cannot specify custom CA certificate or skip validation

### Database Connections Today
```python
# Database has full certificate support:
# - Saves certificate path in profiles.json
# - Validates file exists
# - Passes to driver (MySQL, SQL Server, etc.)
# - Methods: _save_last_db_connection, _get_last_db_connection
```

### Shared Infrastructure
- Both use `profiles.json` for config storage
- Both have connection dialogs (LDAPConnectionDialog, DatabaseConnectionDialog)
- Both have connection memory features
- Both use main_window.py for memory methods

## Architecture Decision: Unified Certificate Handling

### Strategy
Create a **unified certificate utility module** that both LDAP and Database use:

```
NEW: api/certificate_manager.py
├── Certificate validation and usage
├── File existence checking
├── Error handling and logging
└── Shared between LDAP and Database

MODIFY: api/ldap_utils.py
├── Accept optional certificate parameter
├── Use certificate_manager for validation
└── Pass to ldap3.Server()

MODIFY: ui/dialogs.py (LDAPConnectionDialog)
├── Add certificate file picker
├── Add "Skip Certificate Validation" checkbox
├── Save certificate path in connection

MODIFY: ui/main_window.py
├── Extend _get_last_ldap_connection() to restore cert
├── Extend _save_last_ldap_connection() to save cert
└── Add _get_ldap_connection_dir() for file picker defaults
```

## Implementation Details

### Phase 1: Unified Certificate Manager

Create `api/certificate_manager.py`:

```python
class CertificateManager:
    @staticmethod
    def validate_certificate_file(cert_path: str) -> Tuple[bool, Optional[str]]:
        """Check if certificate file exists and is readable.
        Returns: (is_valid, error_message)"""
        
    @staticmethod
    def get_certificate_for_ldap(cert_path: Optional[str]) -> Optional[str]:
        """Get validated certificate path for LDAP, None if invalid"""
        
    @staticmethod
    def get_certificate_for_database(cert_path: Optional[str], driver: str) -> Optional[str]:
        """Get validated certificate path for database (may need driver-specific handling)"""
        
    @staticmethod
    def certificate_to_config(cert_path: Optional[str]) -> Optional[str]:
        """Sanitize certificate path for storage in config"""
        
    @staticmethod
    def certificate_from_config(cert_path: Optional[str]) -> Optional[str]:
        """Restore certificate path from config with validation"""
```

### Phase 2: LDAP Utilities Enhancement

Modify `api/ldap_utils.py`:

```python
def _connect(
    host: str,
    port: int,
    use_ssl: bool,
    bind_dn: str,
    password: str,
    start_tls: bool = False,
    timeout: int = 15,
    certificate: Optional[str] = None,  # NEW
    skip_cert_validation: bool = False,  # NEW
) -> ldap3.Connection:
    """
    Connect to LDAP server.
    
    Args:
        certificate: Path to CA certificate file for self-signed certs
        skip_cert_validation: If True, skip certificate validation entirely
    """
    # Validate certificate if provided
    if certificate:
        certificate = CertificateManager.get_certificate_for_ldap(certificate)
    
    # Create server with certificate handling
    server_kwargs = {
        'host': host,
        'port': safe_port,
        'use_ssl': bool(use_ssl),
        'get_info': ALL,
        'connect_timeout': max(3, int(timeout or 15)),
    }
    
    if certificate:
        server_kwargs['ca_certs_file'] = certificate  # ldap3 parameter
    
    if skip_cert_validation:
        server_kwargs['ssl_version'] = ssl.PROTOCOL_TLS  # Allow any cert
        # Note: ldap3 uses 'get_info': ALL by default which may validate
        # We'll need to handle this carefully
    
    server = ldap3.Server(**server_kwargs)
    # ... rest of connection
```

### Phase 3: LDAPConnectionDialog Enhancement

Modify `ui/dialogs.py` LDAPConnectionDialog class:

```python
class LDAPConnectionDialog(QtWidgets.QDialog):
    def __init__(self, initial: dict = None, parent=None):
        # ... existing code ...
        
        # NEW: Certificate section
        self.use_cert_cb = QtWidgets.QCheckBox("Use Certificate File (for self-signed)")
        self.use_cert_cb.toggled.connect(self._on_cert_toggle)
        
        cert_row = QtWidgets.QHBoxLayout()
        self.cert_path_edit = QtWidgets.QLineEdit()
        self.cert_path_edit.setPlaceholderText("/path/to/ca-cert.pem")
        self.cert_browse_btn = QtWidgets.QPushButton("Browse")
        self.cert_browse_btn.clicked.connect(self._browse_certificate)
        cert_row.addWidget(self.cert_path_edit, 1)
        cert_row.addWidget(self.cert_browse_btn)
        
        # NEW: Skip validation option
        self.skip_cert_validation_cb = QtWidgets.QCheckBox("Skip certificate validation (not recommended)")
        self.skip_cert_validation_cb.setStyleSheet("color: #cc0000;")
        
        form.addRow("", self.use_cert_cb)
        form.addRow("", cert_row)
        form.addRow("", self.skip_cert_validation_cb)
        
        self._on_cert_toggle(False)  # Initial state
        
        # Pre-populate if editing
        if initial:
            cert_path = initial.get('certificate', '')
            if cert_path:
                self.use_cert_cb.setChecked(True)
                self.cert_path_edit.setText(cert_path)
            self.skip_cert_validation_cb.setChecked(
                bool(initial.get('skip_cert_validation', False))
            )
    
    def _on_cert_toggle(self, checked):
        """Enable/disable certificate controls"""
        self.cert_path_edit.setEnabled(checked)
        self.cert_browse_btn.setEnabled(checked)
    
    def _browse_certificate(self):
        """File picker for certificate"""
        cert_dir = self.parent()._get_ldap_connection_dir('certificate') if hasattr(self.parent(), '_get_ldap_connection_dir') else None
        
        file_dialog = QtWidgets.QFileDialog(
            self,
            "Select CA Certificate File",
            cert_dir or str(Path.home()),
            "Certificate Files (*.pem *.crt *.der *.cer);;All Files (*)"
        )
        file_dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        
        if file_dialog.exec():
            cert_path = file_dialog.selectedFiles()[0]
            self.cert_path_edit.setText(cert_path)
            # Save directory for next time
            if hasattr(self.parent(), '_save_ldap_connection_dirs'):
                self.parent()._save_ldap_connection_dirs(str(Path(cert_path).parent))
```

### Phase 4: LDAPConnectionsManager Enhancement

Modify `ui/dialogs.py` LDAPConnectionsManager to show certificate info:

```python
class LDAPConnectionsManager(QtWidgets.QDialog):
    # Show saved certificate path in connection list
    # Allow editing/removing certificate from existing connections
```

### Phase 5: Main Window Integration

Modify `ui/main_window.py`:

```python
def _save_last_ldap_connection(self, connection_name: str, certificate: Optional[str] = None):
    """Save last LDAP connection + optional certificate"""
    # Existing code saves connection_name
    # NEW: Also save certificate path
    
    conf = self.conf or {}
    meta = conf.setdefault('__meta__', {})
    meta['last_ldap_connection_name'] = connection_name
    
    # NEW: Save certificate path
    if certificate:
        meta['last_ldap_certificate'] = certificate

def _get_last_ldap_connection(self):
    """Get last LDAP connection + certificate"""
    conf = self.conf or {}
    meta = conf.get('__meta__', {})
    name = meta.get('last_ldap_connection_name')
    cert = meta.get('last_ldap_certificate')
    
    # Validate certificate file exists
    if cert and cert.strip():
        cert_path = Path(cert)
        if not cert_path.exists():
            cert = None
    
    return name, cert

def _save_ldap_connection_dirs(self, cert_dir: Optional[str] = None):
    """Save LDAP file picker directory defaults"""
    conf = self.conf or {}
    meta = conf.setdefault('__meta__', {})
    dirs = meta.setdefault('last_ldap_connection_dirs', {})
    
    if cert_dir:
        dirs['certificate'] = cert_dir

def _get_ldap_connection_dir(self, dir_type: str = 'certificate') -> Optional[str]:
    """Get saved LDAP file picker directory"""
    conf = self.conf or {}
    meta = conf.get('__meta__', {})
    dirs = meta.get('last_ldap_connection_dirs', {})
    
    if dir_type in dirs:
        path_str = dirs[dir_type]
        if path_str and Path(path_str).exists():
            return path_str
    
    return None
```

## Configuration Structure

### LDAP Connection Storage (profiles.json)

```json
{
  "connections": {
    "my-ldap-prod": {
      "name": "my-ldap-prod",
      "host": "ldap.company.com",
      "port": 636,
      "use_ssl": true,
      "start_tls": false,
      "certificate": "/Users/user/certs/company-ca.pem",
      "skip_cert_validation": false,
      "bind_dn": "cn=admin,dc=company,dc=com",
      "base_dn": "ou=people,dc=company,dc=com",
      "search_filter": "(objectClass=person)",
      "rdn_attribute": "uid",
      "timeout": 30,
      "auto_create_parents": true
    }
  },
  "__meta__": {
    "last_ldap_connection_name": "my-ldap-prod",
    "last_ldap_certificate": "/Users/user/certs/company-ca.pem",
    "last_ldap_connection_dirs": {
      "certificate": "/Users/user/certs"
    }
  }
}
```

## Certificate Handling Rules

### For LDAP Connections

| Scenario | Action |
|----------|--------|
| SSL/TLS enabled + certificate specified | Use provided certificate for validation |
| SSL/TLS enabled + no certificate | Use system trust store |
| SSL/TLS enabled + skip validation checked | Skip certificate validation (⚠️ risky) |
| Non-SSL connection | Ignore certificate settings |

### For Database Connections

| Scenario | Action |
|----------|--------|
| Encrypt enabled + certificate specified | Use provided certificate for validation |
| Encrypt enabled + no certificate | Use system trust store |
| Non-encrypted connection | Ignore certificate settings |

## Security Considerations

1. **Passwords**: Never stored in config (use keyring) ✓
2. **Certificate Paths**: Stored in config (file paths are not secrets)
3. **Skip Validation**: Flagged as risky in UI (red text warning)
4. **File Validation**: Check certificate file exists before using
5. **User Warning**: Clear UI warning when skipping validation

## Testing Strategy

### Unit Tests (test_ldap_wizard.py)

```python
def test_ldap_connection_with_certificate():
    """Test LDAP connection with self-signed certificate"""
    
def test_ldap_connection_skip_validation():
    """Test LDAP connection with validation skipped"""
    
def test_ldap_certificate_file_validation():
    """Test that invalid certificate paths are rejected"""
    
def test_ldap_certificate_memory():
    """Test that certificate path is remembered across sessions"""
```

### Manual Testing Checklist

- [ ] Create LDAP connection with self-signed certificate
- [ ] Test connection succeeds with certificate
- [ ] Test connection fails without certificate
- [ ] Test skip validation option works
- [ ] Close app and reopen
- [ ] Verify certificate path is restored
- [ ] Test file picker opens to last used directory
- [ ] Test that deleted certificate file shows graceful error
- [ ] Test connection still works with dialog empty (uses system trust)
- [ ] Verify database connections still work unchanged

## Implementation Phases

| Phase | Task | Files | Lines |
|-------|------|-------|-------|
| 1 | Create certificate_manager.py | api/certificate_manager.py | ~100 |
| 2 | Enhance ldap_utils.py | api/ldap_utils.py | ~30 |
| 3 | Enhance LDAPConnectionDialog | ui/dialogs.py | ~80 |
| 4 | Enhance LDAPConnectionsManager | ui/dialogs.py | ~20 |
| 5 | Enhance main_window.py | ui/main_window.py | ~60 |
| **Total** | | | **~290 lines** |

## Code Reuse Opportunities

1. **Certificate validation**: Share CertificateManager between LDAP and Database
2. **Connection memory**: Similar pattern to database memory, adapted for LDAP
3. **File picker**: Reuse directory tracking in both connection types
4. **UI patterns**: Both dialogs follow same checkbox/file picker pattern

## Backward Compatibility

- ✓ Existing LDAP connections work unchanged (certificate optional)
- ✓ Existing database connections work unchanged
- ✓ No config migration needed (new keys are optional)
- ✓ Existing UI still works (new controls hidden unless enabled)

## Deliverables

1. ✓ Unified certificate manager
2. ✓ Enhanced LDAP utilities with certificate support
3. ✓ Enhanced LDAP connection dialog with certificate UI
4. ✓ Enhanced LDAP connections manager
5. ✓ Enhanced main window with certificate memory
6. ✓ Documentation and testing guide
7. ✓ Implementation notes

## Success Criteria

✅ LDAP connections can use self-signed certificates  
✅ Database connections continue working unchanged  
✅ Both use same certificate validation code  
✅ Certificate path is remembered across sessions  
✅ Graceful fallback if certificate file missing  
✅ All tests pass  
✅ Backward compatible with existing configs  

---

**Status**: Ready for BUILD phase  
**Next Step**: User confirms plan is good to implement
