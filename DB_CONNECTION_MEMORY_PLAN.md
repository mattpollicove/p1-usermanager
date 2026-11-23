# Database Connection Memory Feature - Ask/Plan Document

## ASK - Requirements Clarification ✅

**User Request**: "App should remember last successful ldap/db connections being used"

**Clarifications**:
1. **What to remember**: ALL connection parameters + certificate path
2. **Scope**: Both per-profile AND global defaults
3. **Style**: Customized for database workflows

## PLAN - Implementation Strategy

### Overview

Implement database connection memory that:
- Saves all connection parameters (host, port, type, user, database, driver, SSL settings, certificate)
- Pre-populates dialog fields when opening database connection dialog
- Supports role-based memory (default, source, destination connections)
- Integrates with existing keyring for password storage
- Provides graceful fallback if connection/certificate deleted

### Key Differences from LDAP Implementation

| Aspect | LDAP | Database |
|--------|------|----------|
| **Storage** | Connection name only | Full connection object |
| **Complexity** | Simple | Complex (many parameters) |
| **Credentials** | Simple name | Username + password (keyring) |
| **Additional Data** | None | Certificate path, driver path |
| **Roles** | Single default | Multiple (source, destination) |
| **Validation** | Name exists | Certificate file exists, fields valid |

### Architecture

```
User opens Database dialog
    ↓
Dialog calls _get_last_db_connection(role)
    ↓
App retrieves saved connection params from __meta__.last_db_connections[role]
    ↓
App validates (cert exists, required fields present)
    ↓
Dialog pre-populates fields with saved values
    ↓
User can:
  - Use saved values (click OK)
  - Modify values
  - Test connection
    ↓
On successful test/confirmation:
  _save_last_db_connection(role, params)
    ↓
Params saved to __meta__.last_db_connections[role]
```

### Configuration Structure

```json
{
    "__meta__": {
        "last_working_profile": "myprofile",
        "last_ldap_connection": "my-ldap",
        "last_db_connections": {
            "default": {
                "type": "MySQL",
                "host": "db.example.com",
                "port": 3306,
                "database": "mydb",
                "user": "dbuser",
                "driver": "/path/to/mysql-connector.jar",
                "encrypt_mode": "Auto",
                "certificate": "/path/to/cert.pem"
            },
            "source": { ... },
            "destination": { ... }
        },
        "last_db_connection_dirs": {
            "driver": "/Users/matthewpollicove/drivers",
            "certificate": "/Users/matthewpollicove/certs"
        }
    }
}
```

### Implementation Phases

#### Phase 1: Create Core Memory Methods (main_window.py)

**Location**: After LDAP memory methods (~line 2143)

Three new methods:
1. `_save_last_db_connection(role, connection_data)` - Store parameters
2. `_get_last_db_connection(role='default')` - Retrieve with validation
3. `_save_db_connection_dirs(role, driver_dir, cert_dir)` - Track file picker defaults

**Key Features**:
- Password NOT stored (uses keyring)
- Certificate path validated before use
- Role-based memory (default/source/destination)
- Fallback: specific role → default → None
- Silent exception handling

#### Phase 2: Update DatabaseConnectionDialog (ui/dialogs.py)

**Location**: DatabaseConnectionDialog class (~line 1100)

Modifications:
1. **__init__** (line ~1297)
   - After form setup, pre-populate with saved connection
   - Retrieve last connection from parent window
   - Set all fields if connection found

2. **_on_test** method
   - After successful test, save connection
   - Call `parent()._save_last_db_connection('default', params)`

3. **_on_use** method
   - Before accepting, save connection
   - Call `parent()._save_last_db_connection('default', params)`

4. **_browse_jar** / **Certificate picker**
   - Save directory for next time
   - Restore default directory when opening picker

#### Phase 3: Integration Points

**manage_db_connections()** (~line 2690)
- After user creates/edits connection, save as default

**Database mapping selection** (~line 2995+)
- Pre-populate with last used connection
- Support different roles if applicable

**Connection tests**
- Save successful connections
- Don't save failed tests

#### Phase 4: Validation Logic

Before applying saved connection:
```python
def _get_last_db_connection(role='default'):
    1. Retrieve from last_db_connections[role]
    2. If not found, try last_db_connections['default']
    3. If not found, return None
    4. Validate certificate exists (if specified)
    5. Validate host, port, type are present
    6. Return connection or None on validation failure
```

#### Phase 5: Fallback Hierarchy

When pre-populating dialog:
1. Use last connection for specific role (if exists)
2. Fall back to default role (if exists)
3. Fall back to first available in db_connections
4. Fall back to empty dialog with defaults

### Methods to Implement

#### `_save_last_db_connection(role, connection_data)`
```python
Args:
    role (str): 'default', 'source', or 'destination'
    connection_data (dict): Connection parameters from dialog

Returns:
    None

Side effects:
    - Saves to __meta__.last_db_connections[role]
    - Creates __meta__ if missing
    - Skips password (uses keyring)
    - Silently fails on exception
```

#### `_get_last_db_connection(role='default')`
```python
Args:
    role (str): 'default', 'source', or 'destination'

Returns:
    dict: Connection parameters or None

Validation:
    - Certificate file exists (if specified)
    - Required fields present (host, port, type)
    - Silently returns None on validation failure
```

#### `_save_db_connection_dirs(role, driver_dir, cert_dir)`
```python
Args:
    role (str): 'default', 'source', or 'destination'
    driver_dir (str): Directory for JDBC drivers
    cert_dir (str): Directory for certificates

Returns:
    None

Side effects:
    - Saves to __meta__.last_db_connection_dirs
    - Allows file pickers to open in last-used directory
```

### Integration Points in dialogs.py

#### DatabaseConnectionDialog.__init__ (line ~1297)
```python
# After form is created, before status label
if not initial:  # Only for new connections
    if hasattr(self.parent(), '_get_last_db_connection'):
        last = self.parent()._get_last_db_connection('default')
        if last:
            # Pre-populate all fields
            self.type_combo.setCurrentText(last.get('type', 'MySQL'))
            self.host_edit.setText(last.get('host', ''))
            # ... etc for all fields
```

#### DatabaseConnectionDialog._on_test (after successful test)
```python
# After successful connection:
if hasattr(self.parent(), '_save_last_db_connection'):
    self.parent()._save_last_db_connection('default', self.get_connection_data())
```

#### DatabaseConnectionDialog._on_use (before accept)
```python
# Before dialog.accept():
if hasattr(self.parent(), '_save_last_db_connection'):
    self.parent()._save_last_db_connection('default', self.get_connection_data())
```

### Edge Cases & Solutions

| Scenario | Expected Behavior |
|----------|-------------------|
| Certificate deleted | Don't restore; return None; user picks new cert |
| Connection deleted | Try role, default, first available, empty |
| Keyring unavailable | Still restore fields, password field empty |
| Config corrupted | Silent fail, return None, use defaults |
| Port not in config | Use type's default port |
| Driver path broken | Still restore, let user test/fix |

### Testing Strategy

**Test 1: Basic Save & Restore**
1. Create new DB connection with all parameters
2. Click "Test Connection" (succeeds)
3. Close dialog
4. Reopen DB connection dialog
5. ✓ All fields pre-populated with saved values

**Test 2: Certificate Handling**
1. Create connection with certificate
2. Close app
3. Delete certificate file
4. Reopen app and DB dialog
5. ✓ Falls back gracefully, certificate field empty

**Test 3: Role Separation**
1. Create connection "prod-db" as default role
2. Create connection "test-db" as source role
3. ✓ Each role remembers independently

**Test 4: Global vs Per-Profile**
1. Create Profile A, use connection "db-a"
2. Create Profile B, use connection "db-b"
3. Switch to Profile A
4. ✓ Connection "db-a" pre-selected
5. Switch to Profile B
6. ✓ Connection "db-b" pre-selected

**Test 5: Password Security**
1. Save connection with password
2. Close app
3. Inspect profiles.json
4. ✓ Password NOT in config file
5. ✓ Password retrieved from keyring on next use

### Dependencies

**No new dependencies required**:
- Uses existing config file infrastructure
- Uses existing keyring integration
- Uses existing PySide6 widgets
- Uses existing Path class (already imported)

### Success Criteria

✅ Saves all connection parameters (except password)
✅ Pre-populates dialog fields with saved values
✅ Validates certificate exists before using
✅ Supports role-based memory (default/source/destination)
✅ Falls back gracefully if data missing/invalid
✅ Works with existing keyring for passwords
✅ No breaking changes to existing functionality
✅ Per-profile independent memory
✅ Global defaults with profile overrides

### Risk Assessment

**Low Risk**:
- Uses existing config save infrastructure
- Silent exception handling (non-blocking)
- Graceful fallback if any validation fails
- No new external dependencies
- Backward compatible (new keys optional)
- Existing behavior unchanged if memory not used

## BUILD Phase

Ready to implement when you confirm:
1. ✅ Requirements clear (all parameters + certificate)
2. ✅ Scope clear (per-profile + global)
3. ✅ Architecture documented
4. ✅ Implementation strategy planned

**Next Step**: Proceed with implementation

---

## Related Documents

- [LDAP_CONNECTION_MEMORY.md](./LDAP_CONNECTION_MEMORY.md) - Similar LDAP feature
- [IMPLEMENTATION_NOTES_CONNECTION_MEMORY.md](./IMPLEMENTATION_NOTES_CONNECTION_MEMORY.md) - LDAP technical details
