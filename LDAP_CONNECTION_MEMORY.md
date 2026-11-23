# LDAP Connection Memory Feature

## Overview

The PingOne User Manager app now automatically remembers the last successfully used LDAP connection. When you open the LDAP connection selector dialog, the app will pre-select your previously used connection, saving you from having to select it again each time you use the app.

## How It Works

### Storage Mechanism

- **Location**: The connection name is stored in `profiles.json` under `__meta__.last_ldap_connection`
- **Scope**: Each profile maintains its own last-used connection (independent memory per profile)
- **Persistence**: Automatically saved to disk - no manual configuration needed

### When Connections Are Remembered

The app saves a connection as "last used" in these scenarios:

1. **Dialog Selection** - User selects a connection and clicks OK in the connection selector dialog
2. **Successful Test** - User clicks "Test Connection" and the test succeeds
3. **New Connection** - User creates a new LDAP connection in the dialog
4. **First Connection** - User creates the first LDAP connection ever

### Connection Selection Priority

When opening the LDAP connection dialog, the app:

1. Checks if a last-used connection was saved
2. Verifies the connection still exists (hasn't been deleted)
3. If valid, pre-selects it in the dropdown
4. If invalid or missing, falls back to the first available connection
5. If no connections exist, prompts to create one

## User Experience

### Before (Old Behavior)
1. User opens app
2. Needs LDAP feature? Click menu
3. Select LDAP Connection dialog opens
4. First connection is always pre-selected by default
5. Must manually select desired connection
6. Close app
7. Restart app
8. Need LDAP again? Repeat steps 2-5

### After (New Behavior)
1. User opens app
2. Needs LDAP feature? Click menu
3. Select LDAP Connection dialog opens
4. **Last used connection is already pre-selected** ✓
5. Can click OK immediately (or select different one)
6. Close app
7. Restart app
8. Need LDAP again? Same connection still pre-selected ✓

## Technical Details

### Implementation

**New Methods in `main_window.py`:**

```python
def _save_last_ldap_connection(self, connection_name: str):
    """Save the last successfully used LDAP connection name to config."""
    # Stores connection name in profiles.json __meta__ section
    
def _get_last_ldap_connection(self):
    """Get the last successfully used LDAP connection name, if any."""
    # Retrieves connection name, validates it still exists
```

**Modified Methods:**

- `_choose_ldap_connection()` - Now checks for and pre-selects last connection
- Updated in 4 locations where connections are selected/confirmed

### Error Handling

The implementation gracefully handles edge cases:

- **Deleted Connections**: If the last-used connection was deleted, falls back to first available
- **Connection Rename**: If a connection is renamed, the app falls back to first available
- **No Connections**: If all connections are deleted, prompts user to create one
- **Missing Config**: If `__meta__` section doesn't exist, creates it automatically

### Profile Isolation

Connection memory is per-profile:
- Profile "Production" might remember "prod-ldap"
- Profile "Testing" might remember "test-ldap"
- Switching profiles automatically switches remembered connection

## Configuration File Structure

```json
{
    "__meta__": {
        "last_working_profile": "myprofile",
        "last_ldap_connection": "my-ldap-server",
        "auto_connect_last": true,
        ...other metadata...
    },
    "myprofile": {
        "env_id": "...",
        "ldap_connections": {
            "my-ldap-server": {
                "host": "ldap.example.com",
                "port": 389,
                ...
            },
            ...
        },
        ...
    }
}
```

## Benefits

✅ **Faster Workflow** - Don't re-select connection every session
✅ **Automatic** - No configuration needed, works out of the box
✅ **Smart Defaults** - App learns from your behavior
✅ **Per-Profile** - Each profile maintains independent memory
✅ **Safe** - Only stores connection names, not credentials
✅ **Robust** - Gracefully handles deleted/missing connections
✅ **Non-Intrusive** - Doesn't change existing config structure, uses __meta__ section

## Testing

### Test Case 1: Basic Memory
1. Create LDAP connection "test-conn"
2. Close and reopen app
3. Open LDAP connection dialog
4. **Expected**: "test-conn" is pre-selected

### Test Case 2: Persistent Across App Restarts
1. Use connection "ldap-prod"
2. Close app completely
3. Wait a moment
4. Reopen app
5. Try LDAP feature
6. **Expected**: "ldap-prod" still pre-selected

### Test Case 3: Different Profiles
1. Create Profile A and select connection "ldap-a"
2. Create Profile B and select connection "ldap-b"
3. Switch to Profile A
4. **Expected**: "ldap-a" is pre-selected
5. Switch to Profile B
6. **Expected**: "ldap-b" is pre-selected

### Test Case 4: Handle Deletion
1. Use connection "temp-ldap"
2. Delete "temp-ldap" via Manage LDAP Connections
3. Close and reopen app
4. Open LDAP connection dialog
5. **Expected**: App doesn't crash, falls back to another connection

### Test Case 5: Successful Test Saves Connection
1. Open LDAP connection dialog
2. Select "new-conn"
3. Click "Test Connection"
4. Test succeeds
5. Close dialog
6. Close and reopen app
7. **Expected**: "new-conn" is now pre-selected

## Troubleshooting

### Connection Not Being Remembered

**Symptom**: Last-used connection isn't pre-selected

**Solutions**:
- Ensure app was closed cleanly (not force-quit)
- Check that `profiles.json` is writable
- Verify `__meta__` section exists in `profiles.json`
- Try testing the connection instead of just selecting it

### Wrong Connection Pre-selected

**Symptom**: Different connection is pre-selected

**Solutions**:
- Delete the connection you don't want from "Manage LDAP Connections"
- Use the desired connection and test it (test saves it as last-used)
- Close and reopen app

### Profile-Specific Memory Not Working

**Symptom**: Connection memory carries over between profiles

**Solutions**:
- This is not a bug - memory is global by design
- Each profile can have its own LDAP connections defined
- When switching profiles, the app shows connections for that profile
- The last-used connection name persists across profiles

## Migration Notes

For existing users upgrading to this version:

- **No action required** - Feature works automatically
- **First time**: First available connection will be pre-selected (as before)
- **After first use**: Your preferred connection will be remembered
- **Config compatibility**: Existing `profiles.json` files work unchanged

## See Also

- [Group Management](./GROUP_MANAGEMENT.md)
- [LDAP Configuration](./LDAP_CONFIGURATION.md)
- [Database Connections](./DATABASE_CONNECTIONS.md)
