# ASK / PLAN Phase: LDAP Self-Signed Certificate Management

## Status: ✅ PLAN PHASE COMPLETE - READY FOR BUILD

**Methodology**: Ask / Plan / Build  
**Feature**: LDAP Self-Signed Certificate Management  
**Date**: Current Session

---

## ASK Phase - Requirements Clarified

### User Form Response

| Question | Answer |
|----------|--------|
| **Should LDAP connections support self-signed certificate files?** | ✅ **YES, add now** |
| **What's your LDAP SSL scenario?** | Connections will use ONLY ONE OR THE OTHER (LDAP OR Database, not both simultaneously) |
| **Should LDAP and Database use the SAME certificate handling code?** | ✅ **YES, unify** |

### Interpreted Requirements

1. ✅ LDAP connections **MUST** support self-signed certificate files
2. ✅ Users will choose **EITHER** LDAP **OR** Database, not both at same time
3. ✅ Both should use the **SAME unified certificate handling code**
4. ✅ This is a **priority feature** (implement NOW, not deferred)

---

## PLAN Phase - Comprehensive Architecture Defined

### Key Decision: Unified Certificate Manager

Instead of duplicating certificate logic, create a **shared component** that both LDAP and Database use:

```
api/certificate_manager.py
├── Unified certificate validation
├── File existence checking
├── Used by LDAP connections
├── Used by Database connections
└── Ensures consistency
```

### 5-Phase Implementation Strategy

| Phase | Component | Changes | Lines |
|-------|-----------|---------|-------|
| 1 | Certificate Manager | NEW: api/certificate_manager.py | ~100 |
| 2 | LDAP Utilities | MODIFY: api/ldap_utils.py | +30 |
| 3 | LDAP Dialog | MODIFY: ui/dialogs.py (LDAPConnectionDialog) | +80 |
| 4 | LDAP Connections Mgr | MODIFY: ui/dialogs.py (Manager) | +20 |
| 5 | Main Window | MODIFY: ui/main_window.py | +60 |
| **TOTAL** | | | **~290 lines** |

### Architecture Diagram

```
User Interface
├── LDAPConnectionDialog (enhanced)
│   ├── Certificate checkbox
│   ├── Certificate file picker
│   └── Skip validation option
│
├── LDAPConnectionsManager (enhanced)
│   └── Show certificate path in list
│
└── DatabaseConnectionDialog (unchanged)
    └── Already has certificate support

Configuration Storage
└── profiles.json
    ├── LDAP connections → certificate field
    ├── Database connections → certificate field
    └── __meta__ → last_ldap_certificate + dirs

Certificate Management
└── api/certificate_manager.py (NEW - SHARED)
    ├── validate_certificate_file()
    ├── get_certificate_for_ldap()
    ├── get_certificate_for_database()
    └── Used by both LDAP and Database

Connection Logic
├── api/ldap_utils.py (enhanced)
│   └── _connect() accepts certificate + skip_validation
│
└── api/db_utils.py (unchanged)
    └── Already handles certificates
```

---

## Configuration Structure

### LDAP Connection (Enhanced)

```json
{
  "connections": {
    "my-ldap-prod": {
      "name": "my-ldap-prod",
      "host": "ldap.company.com",
      "port": 636,
      "use_ssl": true,
      "start_tls": false,
      "certificate": "/Users/user/certs/company-ca.pem",    // NEW
      "skip_cert_validation": false,                        // NEW
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

### Memory Storage (Enhanced)

```json
{
  "__meta__": {
    "last_ldap_connection_name": "my-ldap-prod",
    "last_ldap_certificate": "/Users/user/certs/company-ca.pem",    // NEW
    "last_ldap_connection_dirs": {                                   // NEW
      "certificate": "/Users/user/certs"
    }
  }
}
```

---

## Certificate Handling Rules

### LDAP Connection Scenarios

| Scenario | Behavior |
|----------|----------|
| **SSL/TLS ON + Certificate specified** | Use provided certificate for validation |
| **SSL/TLS ON + No certificate** | Use system trust store (default) |
| **SSL/TLS ON + Skip validation checked** | ⚠️ Skip validation (risky - warn user) |
| **SSL/TLS OFF** | Ignore certificate settings |

### Database Connection Scenarios (Unchanged)

| Scenario | Behavior |
|----------|----------|
| **Encrypt ON + Certificate specified** | Use provided certificate for validation |
| **Encrypt ON + No certificate** | Use system trust store (default) |
| **No encrypt** | Ignore certificate settings |

---

## Security Considerations

| Aspect | Approach |
|--------|----------|
| **Passwords** | Never stored in config (use keyring) ✓ |
| **Certificate Paths** | Stored in config (paths are not secrets) ✓ |
| **Skip Validation** | Flagged as risky in red text warning |
| **File Validation** | Checked before use (must exist) |
| **User Warning** | Clear UI warning when skipping validation |

---

## Backward Compatibility

✅ Existing LDAP connections work unchanged (certificate fields optional)  
✅ Existing database connections work unchanged  
✅ New fields are optional in profiles.json  
✅ No config migration required  
✅ No breaking changes to existing functionality  

---

## Code Reuse with Database Feature

This plan maximizes sharing with the existing database feature:

| Component | Reused/Shared |
|-----------|---------------|
| Certificate validation | ✓ Shared CertificateManager |
| File picker directory memory | ✓ Same pattern as database |
| Connection memory | ✓ Similar pattern adapted for LDAP |
| Config storage (__meta__) | ✓ Same structure and location |
| Validation logic | ✓ Unified and consistent |

**Result**: DRY principle applied - no duplicate certificate code

---

## Implementation Details

### Phase 1: Unified Certificate Manager

```python
# NEW: api/certificate_manager.py

class CertificateManager:
    @staticmethod
    def validate_certificate_file(cert_path: str) -> Tuple[bool, Optional[str]]:
        """Check if certificate file exists and is readable.
        Returns: (is_valid, error_message)"""
    
    @staticmethod
    def get_certificate_for_ldap(cert_path: Optional[str]) -> Optional[str]:
        """Get validated certificate path for LDAP"""
    
    @staticmethod
    def get_certificate_for_database(cert_path: Optional[str], driver: str) -> Optional[str]:
        """Get validated certificate path for database"""
```

### Phase 2: LDAP Utilities Enhancement

```python
# MODIFY: api/ldap_utils.py

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
    # Validate certificate if provided
    # Pass to ldap3.Server() with certificate parameter
    # Handle skip_cert_validation if requested
```

### Phase 3: LDAP Connection Dialog Enhancement

```python
# MODIFY: ui/dialogs.py - LDAPConnectionDialog

# Add certificate section to dialog:
├── "Use Certificate File (for self-signed)" checkbox
├── Certificate path text input + Browse button
└── "Skip certificate validation (not recommended)" checkbox (red text)

# Add methods:
├── _on_cert_toggle() - Enable/disable certificate controls
└── _browse_certificate() - File picker for certificate
```

### Phase 4: LDAP Connections Manager Enhancement

```python
# MODIFY: ui/dialogs.py - LDAPConnectionsManager

# Display certificate path in connection list
# Allow editing/removing certificate from saved connections
```

### Phase 5: Main Window Integration

```python
# MODIFY: ui/main_window.py

def _save_last_ldap_connection(self, connection_name: str, certificate: Optional[str] = None):
    """Save last LDAP connection + certificate"""

def _get_last_ldap_connection(self):
    """Get last LDAP connection + certificate (with validation)"""

def _save_ldap_connection_dirs(self, cert_dir: Optional[str] = None):
    """Save LDAP file picker directory defaults"""

def _get_ldap_connection_dir(self, dir_type: str = 'certificate') -> Optional[str]:
    """Get saved LDAP file picker directory"""
```

---

## Testing Strategy

### Unit Tests (test_ldap_wizard.py additions)

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
- [ ] Test deleted certificate file shows graceful error
- [ ] Test connection still works with dialog empty
- [ ] Verify database connections still work unchanged

---

## Success Criteria

After BUILD phase, all of these must be true:

✅ LDAP connections can use self-signed certificate files  
✅ Database connections continue working unchanged  
✅ Both use same CertificateManager code  
✅ Certificate path remembered across sessions  
✅ Graceful fallback if certificate file missing  
✅ All syntax validated  
✅ All imports working  
✅ All tests passing  
✅ Backward compatible with existing configs  
✅ No breaking changes  

---

## Deliverables Summary

| Deliverable | Status | File |
|-------------|--------|------|
| ASK Phase | ✅ Complete | Form responses captured |
| PLAN Phase | ✅ Complete | LDAP_CERTIFICATE_MANAGEMENT_PLAN.md |
| ASK/PLAN Summary | ✅ Complete | ASK_PLAN_LDAP_CERTIFICATES.md (this file) |
| BUILD Phase | ⏳ Ready | Awaiting user confirmation |

---

## Next Steps

1. **User Review**: Confirm plan is good and addresses all requirements
2. **BUILD Phase**: Implement all 5 phases with full code and tests
3. **Verification**: Run all tests and validate functionality
4. **Documentation**: Create implementation details and user guide
5. **Commit**: Commit to repository with descriptive message

---

## Questions or Concerns?

Refer to detailed plan: **LDAP_CERTIFICATE_MANAGEMENT_PLAN.md**

It includes:
- Complete implementation details for each phase
- Configuration structure examples
- Security considerations
- Code reuse opportunities
- Testing strategy

---

**ASK PHASE**: ✅ COMPLETE - Requirements understood  
**PLAN PHASE**: ✅ COMPLETE - Architecture designed  
**STATUS**: Ready for BUILD phase  
**NEXT ACTION**: User confirms, then proceed with implementation

