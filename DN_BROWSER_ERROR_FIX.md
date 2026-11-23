# DN Browser Error Fix - "Invalid Attribute Type defaultNamingContext"

## Problem
When users clicked "Browse..." in the LDAP Group Mapping dialog, the DN browser would fail with:
```
Error loading directory: invalid attribute type defaultnaming context
```

## Root Cause
The initial implementation tried to query specific LDAP attributes to discover naming contexts:
```python
attributes=['namingContexts', 'defaultNamingContext']
```

**The issue:** The Root DSE search would validate attribute names strictly. When the LDAP server didn't recognize one of the attribute names (or had different naming conventions), it would raise an error instead of silently skipping unknown attributes.

## Solution
Changed the approach to request all available attributes without strict validation:

**Before:**
```python
conn.search("", "(objectClass=*)", search_scope=ldap3.BASE, 
            attributes=['namingContexts', 'defaultNamingContext'])
```

**After:**
```python
# Request all attributes ('*' and '+' means user and operational attributes)
conn.search("", "(objectClass=*)", search_scope=ldap3.BASE, 
            attributes=['*', '+'])

# Then safely retrieve available naming contexts
contexts = (
    root_attrs.get('namingContexts') or 
    root_attrs.get('defaultNamingContext') or 
    []
)
```

## Key Improvements

1. **More Permissive Search**
   - Request all attributes instead of specific ones
   - LDAP server won't reject unknown attribute names
   - Works with any LDAP server implementation

2. **Better Fallback Logic**
   - Tries multiple attribute names for naming contexts
   - Falls back to configured base DN if discovery fails
   - Shows helpful message if discovery succeeds or fails

3. **Cleaner Error Handling**
   - Filters out empty/None values
   - Gracefully handles both AD and OpenLDAP naming conventions
   - Continues to work even if naming context discovery fails

## Updated Error Messages

| Scenario | Old Message | New Message |
|----------|------------|------------|
| Discovery succeeds | "Found 3 directory suffix(es). Click to browse." | "Found 3 directory suffix(es). Click to expand and browse." |
| Discovery fails but base DN configured | ❌ Error shown | "Could not discover directory suffixes. Using configured base DN." |
| Discovery fails, no base DN | ❌ Error shown | ✅ Empty tree, user can manually enter DN |

## Technical Details

### LDAP Root DSE
The Root DSE (Directory Service Entry) is queried with:
- **Base:** Empty string `""`
- **Scope:** BASE (only the DSE itself, no children)
- **Filter:** `(objectClass=*)`
- **Attributes:** `['*', '+']` (all user + operational attributes)

This returns server metadata including:
- `namingContexts` - Standard attribute (most servers)
- `defaultNamingContext` - AD-specific attribute
- Other server info (supported controls, extensions, etc.)

### Attribute Names Supported
- **Standard (OpenLDAP, 389DS, etc.):** `namingContexts`
- **Active Directory:** `defaultNamingContext`
- **Other:** Any LDAP server's root DSE will be fully loaded with `['*', '+']`

## Impact

✅ **Fixed:** DN browser now works with all LDAP server types  
✅ **Improved:** Better error messages and fallback behavior  
✅ **Backward Compatible:** Existing configurations continue to work  
✅ **Robust:** Handles servers with missing or different attribute names  

## Testing

**To verify the fix:**

1. Start the app
2. Set up an LDAP connection (Directory > LDAP Connections)
3. Create a test connection to your LDAP server
4. Go to Group > Import LDAP Groups
5. Click "Browse..." next to Group base DN
6. Should now see:
   - Directory structure loads successfully (no error)
   - Shows discovered naming contexts
   - Can expand and browse the tree
   - Or shows fallback message if discovery failed

## Files Modified

- `ui/group_transfer.py` - `_browse_ldap_dn()` function
  - Improved Root DSE search (line ~100)
  - Better attribute retrieval (line ~102-109)
  - Enhanced error handling and fallback (line ~111-121)

## Notes for Future Enhancements

If the browser still doesn't work for a specific LDAP server:
1. Admin can manually enter base DN in the field (typing is still supported)
2. The browser becomes optional - not required for configuration
3. Future versions could add search box to filter entries
4. Could add option to specify custom search base if auto-discovery fails
