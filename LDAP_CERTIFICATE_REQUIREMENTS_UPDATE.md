# LDAP Certificate Management - Requirements Update

## Status: ✅ ASK Phase Complete - Plan Requires Update

**Date**: Current Session  
**Change**: Expanded certificate support scope

---

## Original Requirement
- Support self-signed (unsigned) certificates with LDAP TLS/SSL

## Updated Requirement (User Clarification)
- Support **BOTH** signed AND unsigned certificates with LDAP TLS/SSL

---

## ASK Phase - User Responses Captured

| Question | Response |
|----------|----------|
| **Validation Approach** | ⚠️ **Warn on unsigned** |
| **UI Display** | ✓ **Show certificate type in UI** |
| **File Formats** | 📄 **All common formats** |

### Interpreted Requirements

1. ✅ Support signed certificates (from CAs - internal or external)
2. ✅ Support unsigned/self-signed certificates
3. ⚠️ Warn users when using unsigned certificates (not recommended for production)
4. 📊 UI should display/indicate certificate type (signed vs unsigned)
5. 📄 Support common certificate formats:
   - PEM (.pem, .crt, .cer)
   - DER (.der, .cer)
   - PKCS#12 (.p12, .pfx)
   - Possibly others

---

## Updated Architecture

### Certificate Type Detection

```
CertificateManager
├── detect_certificate_type(cert_path)
│   ├── Load certificate file
│   ├── Parse certificate structure
│   ├── Determine if signed or unsigned
│   └── Identify certificate format
│
├── validate_certificate_signature()
│   ├── Check if certificate is self-signed
│   ├── Check certificate expiration
│   └── Verify signature chain (if signed)
│
└── get_certificate_warnings(cert_type)
    ├── Empty warnings for signed certs
    └── "⚠️ Self-signed certificate" for unsigned
```

### Enhanced Validation Logic

```python
class CertificateInfo:
    path: str
    format: str              # "PEM", "DER", "PKCS12", etc.
    is_signed: bool          # True if signed by CA, False if self-signed
    subject: str             # Certificate subject (CN=...)
    issuer: str              # Certificate issuer (CN=...)
    not_before: datetime     # Certificate valid from
    not_after: datetime      # Certificate valid until
    warnings: List[str]      # Validation warnings (empty for signed)
```

---

## Configuration Changes

### Enhanced LDAP Connection Storage

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
      "certificate_format": "PEM",                     // NEW
      "certificate_type": "signed",                    // NEW (signed/unsigned)
      "skip_cert_validation": false,
      "bind_dn": "cn=admin,dc=company,dc=com",
      "base_dn": "ou=people,dc=company,dc=com",
      "search_filter": "(objectClass=person)",
      "rdn_attribute": "uid",
      "timeout": 30,
      "auto_create_parents": true
    }
  }
}
```

---

## UI Enhancements

### Certificate File Picker Dialog

After user selects a certificate file:

```
┌─ Certificate Selected ──────────────────┐
│                                         │
│ 📄 File: company-ca.pem                │
│ 📋 Format: PEM                          │
│ 🔏 Type: ✓ Signed Certificate           │
│    Subject: CN=Company CA               │
│    Issuer: CN=Company Root CA           │
│    Valid: Jan 1, 2024 - Dec 31, 2026    │
│                                         │
│ [Browse] [Clear]                        │
└─────────────────────────────────────────┘

vs.

┌─ Certificate Selected ──────────────────┐
│                                         │
│ 📄 File: self-signed.pem                │
│ 📋 Format: PEM                          │
│ ⚠️  Type: Self-Signed Certificate        │
│    Subject: CN=LDAP Server              │
│    Issuer: CN=LDAP Server (self-signed) │
│    Valid: Jan 1, 2024 - Dec 31, 2025    │
│                                         │
│ [Browse] [Clear]                        │
│ ⚠️  Warning: Self-signed certs are not   │
│    recommended for production use.      │
└─────────────────────────────────────────┘
```

### Connection List Display

Enhanced certificate column:

```
Connection Name     | Host            | Cert Status
─────────────────────────────────────────────────────
my-ldap-prod        | ldap.prod.com   | ✓ Signed CA Cert
my-ldap-dev         | ldap.dev.com    | ⚠️ Self-Signed
my-ldap-test        | ldap.test.com   | ✗ No Certificate
```

---

## Implementation Changes (Updated)

### Phase 1: Enhanced Certificate Manager

**Changes to api/certificate_manager.py**:

```python
class CertificateManager:
    @staticmethod
    def detect_certificate_format(cert_path: str) -> str:
        """Detect certificate format (PEM, DER, PKCS12, etc.)"""
        # Try to load as PEM, DER, PKCS12
        # Return format or raise error
    
    @staticmethod
    def detect_certificate_type(cert_path: str) -> Tuple[bool, dict]:
        """
        Analyze certificate and determine if signed or self-signed.
        Returns: (is_self_signed, cert_info)
        
        cert_info dict contains:
        - format: "PEM", "DER", "PKCS12"
        - subject: certificate subject
        - issuer: certificate issuer
        - not_before: valid from date
        - not_after: valid until date
        - is_signed: bool (True if signed by CA)
        - warnings: list of warning strings
        """
    
    @staticmethod
    def get_certificate_warnings(cert_info: dict) -> List[str]:
        """Return list of warnings for certificate"""
        warnings = []
        if cert_info.get('is_self_signed'):
            warnings.append("⚠️ Self-signed certificate detected")
            warnings.append("Not recommended for production use")
        # Add more warnings as needed
        return warnings
    
    @staticmethod
    def validate_certificate_for_ldap(cert_path: str) -> Tuple[bool, str, dict]:
        """
        Validate certificate for LDAP use.
        Returns: (is_valid, error_message, cert_info)
        """
```

### Phase 2: Enhanced LDAP Utilities

**Changes to api/ldap_utils.py**:

```python
def _connect(
    host: str,
    port: int,
    use_ssl: bool,
    bind_dn: str,
    password: str,
    start_tls: bool = False,
    timeout: int = 15,
    certificate: Optional[str] = None,
    skip_cert_validation: bool = False,
):
    """
    Enhanced with certificate detection.
    Will detect if certificate is signed or unsigned
    and pass appropriate parameters to ldap3.
    """
    if certificate:
        is_valid, error, cert_info = CertificateManager.validate_certificate_for_ldap(certificate)
        if not is_valid:
            raise ValueError(f"Certificate validation failed: {error}")
        
        # Pass certificate to ldap3.Server
        # Log whether using signed or unsigned certificate
```

### Phase 3: Enhanced LDAP Connection Dialog

**Changes to ui/dialogs.py - LDAPConnectionDialog**:

```python
class LDAPConnectionDialog(QtWidgets.QDialog):
    def _browse_certificate(self):
        """Enhanced file picker with certificate info display"""
        # After file selection, show certificate details
        # Display certificate type, format, validity period
        # Show warnings if self-signed
    
    def _update_certificate_info_display(self, cert_path: str):
        """Display detected certificate information"""
        # NEW: Show certificate details in UI
        # Detect format, type, subject, issuer, validity
        # Display warnings if self-signed
```

### Phase 4: Enhanced LDAP Connections Manager

**Changes to ui/dialogs.py - LDAPConnectionsManager**:

```python
class LDAPConnectionsManager(QtWidgets.QDialog):
    # Enhanced to show certificate type in connection list
    # Display "✓ Signed", "⚠️ Self-Signed", or "✗ No Cert"
    # Show certificate info on hover or in details
```

### Phase 5: Enhanced Main Window Integration

**Changes to ui/main_window.py**:

```python
def _save_last_ldap_connection(self, connection_name: str, certificate: Optional[str] = None):
    """Enhanced to save certificate format and type"""
    # Detect and save certificate_format
    # Detect and save certificate_type (signed/unsigned)

def _get_last_ldap_connection(self):
    """Enhanced to restore and validate certificate"""
    # Return certificate info including type and warnings
```

---

## Certificate Format Support

### Common Formats to Support

| Format | Extensions | Notes |
|--------|-----------|-------|
| **PEM** | .pem, .crt, .cer | Text-based, most common |
| **DER** | .der, .cer | Binary format |
| **PKCS#12** | .p12, .pfx | Contains cert + key |
| **CRT** | .crt | X.509 certificate |

### Implementation Approach

```python
def load_certificate(cert_path: str):
    """
    Try to load certificate in multiple formats.
    
    1. Try PEM format
    2. Try DER format
    3. Try PKCS#12 format
    4. If all fail, return error
    """
```

---

## Validation Rules (Updated)

### LDAP Connection Certificate Scenarios

| Scenario | Validation | Action | Warning |
|----------|-----------|--------|---------|
| **SSL + Signed CA Cert** | ✓ Valid | Use for validation | None |
| **SSL + Self-Signed Cert** | ✓ Valid | Use for validation | ⚠️ Show warning |
| **SSL + Expired Cert** | ✗ Invalid | Reject | ✗ Show error |
| **SSL + Invalid Format** | ✗ Invalid | Reject | ✗ Show error |
| **SSL + No Certificate** | - | Use system trust store | None |
| **SSL + Skip Validation** | - | Skip all validation | ⚠️ Show red warning |

---

## Security Considerations (Updated)

| Aspect | Approach |
|--------|----------|
| **Signed Certificates** | Fully validated, no warnings |
| **Unsigned Certificates** | Valid but show warning (not production recommended) |
| **Certificate Expiration** | Check and warn before expiry |
| **Format Validation** | Support all common formats safely |
| **User Guidance** | Clear UI indicators (✓, ⚠️, ✗) |

---

## Testing Strategy (Updated)

### Unit Tests

```python
def test_detect_pem_certificate():
    """Test PEM format detection"""

def test_detect_der_certificate():
    """Test DER format detection"""

def test_detect_pkcs12_certificate():
    """Test PKCS#12 format detection"""

def test_detect_signed_certificate():
    """Test detection of CA-signed certificate"""

def test_detect_self_signed_certificate():
    """Test detection of self-signed certificate"""

def test_certificate_expiration_check():
    """Test certificate expiration detection"""

def test_ldap_connection_with_signed_cert():
    """Test LDAP connection with signed certificate"""

def test_ldap_connection_with_unsigned_cert():
    """Test LDAP connection with self-signed certificate"""

def test_certificate_warnings_generation():
    """Test warning message generation"""
```

### Manual Testing Checklist

- [ ] Load PEM certificate (signed)
- [ ] Load PEM certificate (self-signed)
- [ ] Load DER certificate
- [ ] Load PKCS#12 certificate
- [ ] Verify UI shows certificate type correctly
- [ ] Verify warning shown for self-signed certs
- [ ] Verify no warning shown for signed certs
- [ ] Test LDAP connection with signed certificate
- [ ] Test LDAP connection with self-signed certificate
- [ ] Verify certificate info persists across sessions
- [ ] Verify system trust store used when no cert specified

---

## Implementation Impact

### Code Changes Summary

| Phase | File | Changes | Lines |
|-------|------|---------|-------|
| 1 | api/certificate_manager.py | Enhanced with format/type detection | +150 |
| 2 | api/ldap_utils.py | Enhanced with cert info logging | +40 |
| 3 | ui/dialogs.py (LDAPConnectionDialog) | Add cert info display | +100 |
| 4 | ui/dialogs.py (Manager) | Show cert type in list | +30 |
| 5 | ui/main_window.py | Save/restore cert type/format | +80 |
| **TOTAL** | | | **~400 lines** |

**Previous estimate**: ~290 lines  
**Updated estimate**: ~400 lines (110 additional for format/type detection)

---

## Backward Compatibility (Updated)

✅ Existing LDAP connections work unchanged  
✅ Existing database connections work unchanged  
✅ New certificate_format field is optional  
✅ New certificate_type field is optional  
✅ No config migration required  
✅ No breaking changes  

---

## Summary of Changes from Original Plan

| Aspect | Original | Updated |
|--------|----------|---------|
| **Certificate Types** | Unsigned only | Signed + Unsigned |
| **Format Support** | PEM assumed | Auto-detect (PEM, DER, PKCS12, etc.) |
| **Validation** | File exists check | Full certificate analysis |
| **UI Display** | Simple file path | Certificate details + type indicator |
| **Warnings** | None | ⚠️ for self-signed certificates |
| **Code Changes** | ~290 lines | ~400 lines |
| **Complexity** | Simple | Medium |

---

## Next Steps

1. **User Confirmation**: Confirm updated plan addresses all requirements
2. **UPDATE Phase**: Update LDAP_CERTIFICATE_MANAGEMENT_PLAN.md with these changes
3. **BUILD Phase**: Implement enhanced certificate manager and LDAP support
4. **TESTING**: Verify all formats and certificate types work correctly

---

**Status**: ✅ ASK phase complete with enhanced requirements  
**Next**: PLAN phase update to incorporate signed/unsigned certificate support

