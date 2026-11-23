# DN Browser Search Scope Update - SUBTREE for Full Directory Browsing

## Change Made
Updated the DN browser to use **SUBTREE** search scope instead of ONELEVEL when browsing directory structure for group and user base DN selection.

## What This Means

### Before (ONELEVEL)
- Could only see direct children of each DN
- Had to expand multiple levels to drill down
- More clicks needed to navigate

### After (SUBTREE)
- Can see entire subtree under each DN
- Full directory structure visible
- Faster navigation to desired DN
- Size limit of 1000 entries prevents overwhelming results

## Technical Changes

**File:** `ui/group_transfer.py` - `_browse_ldap_dn()` function

**Change 1 - Proper Imports:**
```python
# Before
from api import ldap_utils
import ldap3

# After
from api import ldap_utils
import ldap3
from ldap3 import SUBTREE, LEVEL, BASE
```

**Change 2 - Root DSE Search (unchanged scope, improved constants):**
```python
conn.search("", "(objectClass=*)", search_scope=BASE, attributes=['*', '+'])
```

**Change 3 - Subtree Search (the main fix):**
```python
# Before
conn.search(dn, "(|(objectClass=*))", search_scope=ldap3.ONELEVEL, 
           attributes=['name', 'cn'])

# After
conn.search(dn, "(|(objectClass=*))", search_scope=SUBTREE, 
           attributes=['name', 'cn'], size_limit=1000)
```

## Benefits
✅ Users can see full directory structure under each node  
✅ Faster navigation to desired group/user base DNs  
✅ Better exploration of LDAP directory structure  
✅ Size limit (1000 entries) prevents performance issues  
✅ Works with all LDAP server types (AD, OpenLDAP, 389DS, etc.)  

## Performance Considerations

### Size Limit
- Set to 1000 entries per expansion
- Prevents overwhelming large subtrees
- If a subtree has >1000 entries, user can manually type DN or start from a more specific level

### Lazy Loading
- Only loads entries when user clicks to expand
- Background loads don't block UI
- Multiple connections opened as needed (acceptable for browsing operations)

### Memory
- Minimal impact (tree stores DN strings)
- Old placeholders removed when expanded
- Lazy loading keeps memory footprint low

## Search Scope Explanation

| Scope | Behavior | Use Case |
|-------|----------|----------|
| BASE | Only the specified DN | Root DSE queries only |
| LEVEL | Only direct children (1 level down) | Navigation hierarchy |
| SUBTREE | Entire tree under specified DN | Full directory exploration |

For base DN selection, SUBTREE is ideal because:
- Users want to see the full structure
- They need to find the right container for groups or users
- Subtree search helps them navigate to `CN=Users` or `OU=Users` containers

## Testing Checklist
- [x] Code compiles without errors
- [x] Import statements correct
- [x] Constants properly imported from ldap3
- [x] SUBTREE searches use correct constant
- [x] Size limit set to 1000
- [x] App starts successfully

## Next Steps
The browser is now ready for use with SUBTREE scope. When users expand directory nodes:
1. All entries under that node appear (up to 1000)
2. Each entry can be expanded to see its children
3. Full directory navigation becomes possible
4. Users can select any DN as group/user base DN

## Notes
- SUBTREE scope is more intensive than ONELEVEL
- Size limit prevents performance issues
- If directory is very large, manual DN entry still supported
- All LDAP servers support SUBTREE scope (it's standard LDAP)
