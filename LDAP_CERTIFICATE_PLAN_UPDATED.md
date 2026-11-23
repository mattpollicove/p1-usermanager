# LDAP Certificate Management - Updated Comprehensive Plan

## Status: ✅ ASK & PLAN Phase Complete - Ready for BUILD

**Methodology**: Ask / Plan / Build  
**Feature**: LDAP TLS/SSL with Signed AND Unsigned Certificate Support  
**Date**: Current Session

---

## Requirement Summary

### Original Scope
- Support self-signed (unsigned) certificates with LDAP TLS/SSL

### Enhanced Scope (User Clarification)
- ✅ Support **SIGNED** certificates (from CAs - internal or external)
- ✅ Support **UNSIGNED** certificates (self-signed)
- ⚠️ **Warn on unsigned** - Show warning when using self-signed certificates
- 📊 **Show type in UI** - Distinguish between signed and unsigned in interface
- 📄 **Multi-format** - Support all common certificate formats (PEM, DER, PKCS#12)

---

## Architecture Overview

### Unified Certificate Manager (Enhanced)

The CertificateManager now handles full certificate analysis:

```
CertificateManager
│
├── detect_certificate_format()
│   ├── Identify PEM format
│   ├── Identify DER format
│   ├── Identify PKCS#12 format
│   └── Return format or error
│
├── detect_certificate_type()
│   ├── Load certificate
│   ├── Parse structure
│   ├── Check if self-signed or CA-signed
│   ├── Extract subject, issuer, validity
│   └── Generate warnings if needed
│
├── validate_certificate_for_ldap()
│   ├── Full validation pipeline
│   ├── Format detection
│   ├── Type detection
│   ├── Expiration check
│   └── Return validation result + cert_info
│
└── get_certificate_info() / get_certificate_warnings()
    ├── Return detailed certificate information
    └── Return warning messages for UI display
```

### Configuration Storage (Enhanced)

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
      "certificate_format": "PEM",          // NEW: Detected format
      "certificate_type": "signed",         // NEW: "signed" or "unsigned"
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

---

## 5-Phase Implementation Strategy

### Phase 1: Enhanced Certificate Manager

**File**: `api/certificate_manager.py` (NEW)  
**Scope**: ~150 lines

```python
import os
from pathlib import Path
from typing import Tuple, Dict, List, Optional
from datetime import datetime
from cryptography import x509
from cryptography.hazmat.backends import default_backend

class CertificateManager:
    """Unified certificate management for LDAP and Database connections."""
    
    @staticmethod
    def detect_certificate_format(cert_path: str) -> str:
        """
        Detect certificate file format.
        Returns: "PEM", "DER", "PKCS12", or raises error
        """
        # Try PEM first (text format)
        # Then DER (binary)
        # Then PKCS12 (.p12/.pfx)
    
    @staticmethod
    def detect_certificate_type(cert_path: str) -> Tuple[str, Dict]:
        """
        Analyze certificate to determine type and extract info.
        Returns: (format, cert_info_dict)
        
        cert_info_dict: {
            'format': 'PEM'|'DER'|'PKCS12',
            'subject': 'CN=Company CA, O=Company, C=US',
            'issuer': 'CN=Company Root CA, O=Company, C=US',
            'is_self_signed': False,
            'valid_from': datetime,
            'valid_until': datetime,
            'is_expired': False,
            'days_until_expiry': 365,
            'fingerprint_sha256': 'abc123...',
        }
        """
        cert = x509.load_pem_x509_certificate(
            Path(cert_path).read_bytes(),
            default_backend()
        )
        
        subject = cert.subject.rfc4514_string()
        issuer = cert.issuer.rfc4514_string()
        is_self_signed = subject == issuer
        
        return format_type, {
            'format': format_type,
            'subject': subject,
            'issuer': issuer,
            'is_self_signed': is_self_signed,
            'valid_from': cert.not_valid_before,
            'valid_until': cert.not_valid_after,
            'is_expired': datetime.now() > cert.not_valid_after,
            'days_until_expiry': (cert.not_valid_after - datetime.now()).days,
        }
    
    @staticmethod
    def get_certificate_warnings(cert_info: Dict) -> List[str]:
        """Generate warning messages for certificate."""
        warnings = []
        
        if cert_info.get('is_self_signed'):
            warnings.append("⚠️ Self-signed certificate")
            warnings.append("Not recommended for production use")
        
        if cert_info.get('is_expired'):
            warnings.append("✗ Certificate is EXPIRED")
        
        elif cert_info.get('days_until_expiry', 999) < 30:
            warnings.append(f"⚠️ Certificate expires in {cert_info['days_until_expiry']} days")
        
        return warnings
    
    @staticmethod
    def validate_certificate_for_ldap(cert_path: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Full validation pipeline for LDAP certificate.
        Returns: (is_valid, error_message, cert_info)
        """
        if not cert_path or not cert_path.strip():
            return True, "", None
        
        path = Path(cert_path)
        
        # Check file exists
        if not path.exists():
            return False, f"Certificate file not found: {cert_path}", None
        
        # Check file readable
        try:
            with open(path, 'rb') as f:
                cert_data = f.read()
        except Exception as e:
            return False, f"Cannot read certificate file: {str(e)}", None
        
        # Detect format
        try:
            format_type = CertificateManager.detect_certificate_format(cert_path)
        except Exception as e:
            return False, f"Unknown certificate format: {str(e)}", None
        
        # Detect type and extract info
        try:
            format_type, cert_info = CertificateManager.detect_certificate_type(cert_path)
        except Exception as e:
            return False, f"Cannot parse certificate: {str(e)}", None
        
        # Check expiration (warning, not error)
        if cert_info.get('is_expired'):
            return False, "Certificate is expired", cert_info
        
        return True, "", cert_info
    
    @staticmethod
    def certificate_to_config(cert_path: Optional[str]) -> Optional[str]:
        """Sanitize certificate path for storage in config."""
        if not cert_path:
            return None
        return str(Path(cert_path).resolve())
    
    @staticmethod
    def certificate_from_config(cert_path: Optional[str]) -> Optional[str]:
        """Restore certificate path from config with validation."""
        if not cert_path:
            return None
        
        path = Path(cert_path)
        if path.exists():
            return str(path)
        
        return None
```

### Phase 2: Enhanced LDAP Utilities

**File**: `api/ldap_utils.py`  
**Changes**: +40 lines

```python
# Add to imports
from api.certificate_manager import CertificateManager

def _connect(
    host: str,
    port: int,
    use_ssl: bool,
    bind_dn: str,
    password: str,
    start_tls: bool = False,
    timeout: int = 15,
    certificate: Optional[str] = None,        # NEW
    skip_cert_validation: bool = False,       # NEW
):
    """
    Connect to LDAP server with optional certificate validation.
    
    Args:
        certificate: Path to CA certificate file for self-signed certs
        skip_cert_validation: If True, skip certificate validation entirely
    """
    _require_ldap3()
    
    host, use_ssl, parsed_port = _normalize_host_and_ssl(host, use_ssl)
    if not host:
        raise ValueError("Host cannot be empty")
    
    explicit_port = int(port or 0)
    safe_port = int(parsed_port or 0) or explicit_port or (636 if use_ssl else 389)
    
    # NEW: Validate certificate if provided
    cert_to_use = None
    if certificate and use_ssl:
        is_valid, error, cert_info = CertificateManager.validate_certificate_for_ldap(certificate)
        if not is_valid:
            raise ValueError(f"Certificate validation failed: {error}")
        
        cert_to_use = certificate
        
        # Log certificate type for debugging
        cert_type = "self-signed" if cert_info.get('is_self_signed') else "signed"
        logger.info(f"Using {cert_type} certificate for LDAP: {cert_info.get('subject', 'unknown')}")
    
    server_kwargs = {
        'host': host,
        'port': safe_port,
        'use_ssl': bool(use_ssl),
        'get_info': ALL,
        'connect_timeout': max(3, int(timeout or 15)),
    }
    
    # NEW: Pass certificate to ldap3 if provided
    if cert_to_use:
        server_kwargs['ca_certs_file'] = cert_to_use
    
    # NEW: Handle skip validation
    if skip_cert_validation and use_ssl:
        # ldap3 uses get_info=ALL which validates by default
        # To skip, we need to handle this carefully
        server_kwargs['use_ssl_ctx'] = None  # Will use minimal validation
    
    server = ldap3.Server(**server_kwargs)
    conn = ldap3.Connection(server, user=bind_dn, password=password, auto_bind=True)
    
    if start_tls and not use_ssl:
        conn.start_tls()
    
    return conn
```

### Phase 3: Enhanced LDAP Connection Dialog

**File**: `ui/dialogs.py` - `LDAPConnectionDialog`  
**Changes**: +100 lines

```python
class LDAPConnectionDialog(QtWidgets.QDialog):
    def __init__(self, initial: dict = None, parent=None):
        super().__init__(parent)
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
        
        # NEW: Certificate info display
        self.cert_info_label = QtWidgets.QLabel("")
        self.cert_info_label.setWordWrap(True)
        self.cert_info_label.setStyleSheet("background-color: #f9f9f9; padding: 8px; border-radius: 4px; border: 1px solid #ddd;")
        self.cert_info_label.setVisible(False)
        
        # NEW: Skip validation option
        self.skip_cert_validation_cb = QtWidgets.QCheckBox("Skip certificate validation (not recommended)")
        self.skip_cert_validation_cb.setStyleSheet("color: #cc0000;")
        
        form.addRow("", self.use_cert_cb)
        form.addRow("", cert_row)
        form.addRow("", self.cert_info_label)  # NEW: Shows cert details
        form.addRow("", self.skip_cert_validation_cb)
        
        self._on_cert_toggle(False)  # Initial state
        
        # Pre-populate if editing
        if initial:
            cert_path = initial.get('certificate', '')
            if cert_path:
                self.use_cert_cb.setChecked(True)
                self.cert_path_edit.setText(cert_path)
                self._update_certificate_info_display(cert_path)  # NEW
            self.skip_cert_validation_cb.setChecked(
                bool(initial.get('skip_cert_validation', False))
            )
    
    def _on_cert_toggle(self, checked):
        """Enable/disable certificate controls"""
        self.cert_path_edit.setEnabled(checked)
        self.cert_browse_btn.setEnabled(checked)
        self.skip_cert_validation_cb.setEnabled(checked)
        
        if not checked:
            self.cert_info_label.setVisible(False)
    
    def _browse_certificate(self):
        """File picker for certificate"""
        cert_dir = None
        if hasattr(self.parent(), '_get_ldap_connection_dir'):
            cert_dir = self.parent()._get_ldap_connection_dir('certificate')
        
        file_dialog = QtWidgets.QFileDialog(
            self,
            "Select CA Certificate File",
            cert_dir or str(Path.home()),
            "Certificate Files (*.pem *.crt *.der *.cer *.p12 *.pfx);;All Files (*)"
        )
        file_dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        
        if file_dialog.exec():
            cert_path = file_dialog.selectedFiles()[0]
            self.cert_path_edit.setText(cert_path)
            self._update_certificate_info_display(cert_path)  # NEW
            
            # Save directory for next time
            if hasattr(self.parent(), '_save_ldap_connection_dirs'):
                self.parent()._save_ldap_connection_dirs(str(Path(cert_path).parent))
    
    def _update_certificate_info_display(self, cert_path: str):
        """Display detected certificate information"""
        if not cert_path or not cert_path.strip():
            self.cert_info_label.setVisible(False)
            return
        
        try:
            from api.certificate_manager import CertificateManager
            
            is_valid, error, cert_info = CertificateManager.validate_certificate_for_ldap(cert_path)
            
            if not is_valid:
                self.cert_info_label.setText(f"<b>⚠️ Error:</b> {error}")
                self.cert_info_label.setStyleSheet("background-color: #ffe6e6; padding: 8px; border-radius: 4px; border: 1px solid #ff0000;")
                self.cert_info_label.setVisible(True)
                return
            
            if not cert_info:
                self.cert_info_label.setVisible(False)
                return
            
            # Build info display
            format_type = cert_info.get('format', 'Unknown')
            subject = cert_info.get('subject', 'Unknown')
            issuer = cert_info.get('issuer', 'Unknown')
            is_self_signed = cert_info.get('is_self_signed', False)
            valid_until = cert_info.get('valid_until', 'Unknown')
            days_left = cert_info.get('days_until_expiry', 0)
            
            # Determine certificate type icon and style
            if is_self_signed:
                type_icon = "⚠️"
                type_text = "Self-Signed Certificate"
                bg_color = "#fff3cd"  # Yellow warning
                border_color = "#ffc107"
            else:
                type_icon = "✓"
                type_text = "CA-Signed Certificate"
                bg_color = "#d4edda"  # Green success
                border_color = "#28a745"
            
            info_html = f"""
            <b>{type_icon} {type_text}</b><br>
            <small>
            Format: {format_type}<br>
            Subject: {subject}<br>
            Issuer: {issuer}<br>
            Expires: {valid_until.strftime("%Y-%m-%d") if hasattr(valid_until, 'strftime') else valid_until}
            ({days_left} days remaining)<br>
            </small>
            """
            
            # Add warning for self-signed
            warnings = CertificateManager.get_certificate_warnings(cert_info)
            if warnings:
                info_html += "<br><small style='color: #856404;'>"
                for warning in warnings:
                    info_html += f"{warning}<br>"
                info_html += "</small>"
            
            self.cert_info_label.setText(info_html)
            self.cert_info_label.setStyleSheet(f"background-color: {bg_color}; padding: 8px; border-radius: 4px; border: 1px solid {border_color};")
            self.cert_info_label.setVisible(True)
        
        except Exception as e:
            self.cert_info_label.setText(f"<b>Error reading certificate:</b> {str(e)}")
            self.cert_info_label.setStyleSheet("background-color: #ffe6e6; padding: 8px; border-radius: 4px; border: 1px solid #ff0000;")
            self.cert_info_label.setVisible(True)
```

### Phase 4: Enhanced LDAP Connections Manager

**File**: `ui/dialogs.py` - `LDAPConnectionsManager`  
**Changes**: +30 lines

```python
class LDAPConnectionsManager(QtWidgets.QDialog):
    # Enhanced connection list to show certificate type
    
    def _populate_connections_list(self):
        """Enhanced to show certificate information"""
        self.connections_list.setColumnCount(4)  # Name, Host, Cert Status, Actions
        self.connections_list.setHorizontalHeaderLabels(
            ["Connection Name", "Host", "Certificate", ""]
        )
        
        # For each connection, show certificate status
        for name, conn in self.connections.items():
            cert_path = conn.get('certificate')
            cert_format = conn.get('certificate_format', '')
            cert_type = conn.get('certificate_type', '')
            
            if cert_path:
                if cert_type == 'signed':
                    cert_status = f"✓ {cert_format} Signed"
                elif cert_type == 'unsigned':
                    cert_status = f"⚠️ {cert_format} Self-Signed"
                else:
                    cert_status = f"📄 {cert_format} Certificate"
            else:
                cert_status = "✗ No Certificate"
            
            # Add to list
            # ... existing code ...
            # + display cert_status in column
```

### Phase 5: Enhanced Main Window Integration

**File**: `ui/main_window.py`  
**Changes**: +80 lines

```python
def _save_last_ldap_connection(self, connection_name: str, certificate: Optional[str] = None):
    """Save last LDAP connection + certificate with metadata"""
    conf = self.conf or {}
    meta = conf.setdefault('__meta__', {})
    meta['last_ldap_connection_name'] = connection_name
    
    # NEW: Save certificate with format and type
    if certificate:
        meta['last_ldap_certificate'] = certificate
        
        # Detect format and type
        try:
            from api.certificate_manager import CertificateManager
            
            is_valid, error, cert_info = CertificateManager.validate_certificate_for_ldap(certificate)
            if cert_info:
                meta['last_ldap_certificate_format'] = cert_info.get('format')
                meta['last_ldap_certificate_type'] = 'unsigned' if cert_info.get('is_self_signed') else 'signed'
        except:
            pass  # Silently fail, not critical


def _get_last_ldap_connection(self):
    """Get last LDAP connection + certificate (with validation and metadata)"""
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

---

## Certificate Format Support

### Supported Formats

| Format | Extensions | Type | Notes |
|--------|-----------|------|-------|
| **PEM** | .pem, .crt, .cer | Text | Most common, human-readable |
| **DER** | .der, .cer | Binary | Compact, raw binary format |
| **PKCS#12** | .p12, .pfx | Binary | Contains cert + optional key |
| **CRT** | .crt | Variable | Can be PEM or DER |

### Format Detection Algorithm

```
1. Try parsing as PEM
   ├── Look for -----BEGIN CERTIFICATE-----
   └── Load using cryptography.x509
2. If fails, try DER
   ├── Load binary data directly
   └── Parse as DER X.509
3. If fails, try PKCS#12
   ├── Load as .p12/.pfx
   └── Extract certificate
4. If all fail, return error
```

---

## Validation & Warning Rules

### Certificate Validation Matrix

| Scenario | Valid? | Action | Display | Warning |
|----------|--------|--------|---------|---------|
| **Signed CA Cert** | ✓ | Use | ✓ Signed | None |
| **Self-Signed Cert** | ✓ | Use | ⚠️ Self-Signed | Show warning |
| **Expired Cert** | ✗ | Reject | ✗ Expired | Show error |
| **Invalid Format** | ✗ | Reject | ✗ Invalid | Show error |
| **File Not Found** | ✗ | Reject | ✗ Missing | Show error |
| **No Certificate** | ✓ | Use system trust | ✗ None | None |
| **Skip Validation** | - | Skip all | ⚠️ Unsafe | Red warning |

---

## Security Considerations

| Aspect | Implementation |
|--------|----------------|
| **Password Storage** | Keyring only (never in config) ✓ |
| **Certificate Paths** | Stored in config (not secrets) ✓ |
| **Certificate Validation** | Full X.509 parsing and verification ✓ |
| **Signed vs Unsigned** | Automatically detected and displayed ✓ |
| **Expiration Checks** | Validated and warned before use ✓ |
| **User Warnings** | Clear UI warnings for self-signed certs ✓ |
| **Skip Validation** | Red warning text, discouraged ✓ |

---

## Testing Strategy

### Unit Tests

```python
# Certificate format detection
test_detect_pem_certificate()
test_detect_der_certificate()
test_detect_pkcs12_certificate()

# Certificate type detection
test_detect_signed_certificate()
test_detect_unsigned_certificate()
test_detect_expired_certificate()

# Certificate validation
test_validate_valid_certificate()
test_validate_expired_certificate()
test_validate_invalid_format()
test_validate_missing_file()

# LDAP connection
test_ldap_with_signed_certificate()
test_ldap_with_unsigned_certificate()
test_ldap_with_no_certificate()
test_ldap_skip_validation()

# Certificate memory
test_ldap_certificate_saved_on_connect()
test_ldap_certificate_restored_on_reopen()
test_ldap_certificate_format_detected()
test_ldap_certificate_type_detected()

# Warning generation
test_warning_for_unsigned_cert()
test_warning_for_expiring_cert()
test_no_warning_for_signed_cert()
```

### Manual Testing Checklist

- [ ] Load PEM certificate (signed)
- [ ] Load PEM certificate (self-signed)
- [ ] Load DER certificate
- [ ] Load PKCS#12 certificate (.p12/.pfx)
- [ ] Verify UI correctly identifies signed vs unsigned
- [ ] Verify warning shown for self-signed certs
- [ ] Verify no warning for CA-signed certs
- [ ] Verify certificate details displayed (subject, issuer, validity)
- [ ] Test LDAP connection with signed certificate
- [ ] Test LDAP connection with self-signed certificate
- [ ] Close and reopen app
- [ ] Verify certificate info persists
- [ ] Verify file picker opens to last used directory
- [ ] Test deleted certificate file shows graceful error
- [ ] Verify system trust store used when no cert specified
- [ ] Verify skip validation option works (and shows warning)
- [ ] Verify database connections still work unchanged

---

## Implementation Timeline

| Phase | File | Changes | Lines | Effort |
|-------|------|---------|-------|--------|
| 1 | api/certificate_manager.py | NEW: Full cert analysis | +150 | High |
| 2 | api/ldap_utils.py | Integrate CertificateManager | +40 | Medium |
| 3 | ui/dialogs.py | Enhanced dialog with cert info | +100 | High |
| 4 | ui/dialogs.py | Manager cert display | +30 | Low |
| 5 | ui/main_window.py | Save/restore cert metadata | +80 | Medium |
| **TOTAL** | | | **~400 lines** | **~2-3 hours** |

---

## Code Reuse with Database Feature

✓ **CertificateManager** - Shared between LDAP and Database  
✓ **File picker directory memory** - Same pattern  
✓ **Connection memory** - Similar structure  
✓ **Config storage** - Unified __meta__ approach  
✓ **Validation logic** - Consistent error handling  

---

## Backward Compatibility

✅ Existing LDAP connections work unchanged  
✅ Existing database connections work unchanged  
✅ New fields (certificate_format, certificate_type) are optional  
✅ No config migration required  
✅ No breaking changes to existing functionality  
✅ Graceful fallback if new fields missing  

---

## Success Criteria

After BUILD phase:

✅ LDAP connections support both signed and unsigned certificates  
✅ Certificates auto-detected and displayed in UI  
✅ Warnings shown for self-signed certificates  
✅ All common formats supported (PEM, DER, PKCS#12)  
✅ Certificate paths remembered across sessions  
✅ Graceful fallback for missing/deleted certificates  
✅ Full X.509 parsing and validation  
✅ All syntax validated and no import errors  
✅ All tests passing  
✅ Backward compatible with existing configs  
✅ No breaking changes to database feature  

---

## Summary of Enhanced Plan

**Scope**: Support signed AND unsigned LDAP certificates with TLS/SSL  
**Formats**: PEM, DER, PKCS#12, CRT (auto-detected)  
**Features**: Type detection, warning for unsigned, certificate info display  
**Code**: ~400 lines across 4 files  
**Complexity**: Medium (certificate parsing required)  
**Time**: 2-3 hours implementation  
**Testing**: Comprehensive unit + manual tests  
**Security**: Full validation with user warnings  

---

**Status**: ✅ ASK & PLAN complete - Ready for BUILD phase  
**Next Action**: Proceed with implementation or request adjustments

