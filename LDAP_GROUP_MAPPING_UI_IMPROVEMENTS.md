# LDAP Group Mapping UI Improvements

## Overview
Enhanced the LDAP Group Mapping dialog with a graphical DN browser and improved filter editing experience.

## Changes Made

### 1. **Graphical DN Browser**
- Added a new `_browse_ldap_dn()` function that provides an interactive directory tree browser
- Users can now **click "Browse..."** buttons next to both "Group base DN" and "User base DN" fields
- The browser:
  - Automatically discovers all naming contexts (directory suffixes) from the LDAP server
  - Displays an expandable tree of the directory structure
  - Allows users to explore and select any DN without manual typing
  - Handles errors gracefully if the server doesn't provide naming context info

### 2. **Multi-Line Filter Editing**
- **User filter** field changed from single-line `QLineEdit` to multi-line `QPlainTextEdit`
- Improved height to show full filter text without horizontal scrolling
- Placeholder text shows example: `(&(objectClass=user)(!(objectClass=computer)))`
- Makes complex LDAP filters much easier to read and edit

### 3. **Improved Dialog Layout**
- Increased dialog size from default to 700x650 pixels
- Added scroll area for the form to handle varying content
- Better spacing and organization:
  - Schema selection at top (compact)
  - Base DN selections with browse buttons (1 row each with inline buttons)
  - Other configuration fields follow naturally
  - Buttons at bottom

### 4. **Better UX**
- Schema dropdown shows helpful info about which profiles are available (filtering read-only export profiles appropriately)
- Browse buttons have fixed width to keep layout clean
- Loading indicator shows when directory structure is being fetched
- Status label provides feedback about directory discovery
- Expandable tree with lazy loading prevents slow UI for large directories

## Code Changes

### File: `ui/group_transfer.py`

**New Function: `_browse_ldap_dn()`**
```python
def _browse_ldap_dn(parent, config, title="Select DN"):
    """Browse and select an LDAP DN from the directory tree."""
```
- ~90 lines of new code
- Creates a modal dialog with tree widget
- Fetches naming contexts from LDAP server root DSE
- Implements lazy-loading expansion of tree nodes
- Returns selected DN or None if cancelled

**Updated Function: `ldap_mapping()`**
- Changed from simple `QFormLayout` to more sophisticated layout:
  - Horizontal layout for schema selection
  - Scroll area with form layout inside
  - Browse buttons next to DN fields
  - `QPlainTextEdit` for user filter instead of `QLineEdit`
- Added connected functions for browse button actions
- Properly reads plain text from `user_filter.toPlainText()`

## Technical Details

### DN Browser Implementation
1. Connects to LDAP server using existing credentials from config
2. Queries root DSE (empty string base) with BASE scope to get naming contexts
3. Creates tree items for each naming context with placeholder children
4. When user expands a tree node, runs async search at ONELEVEL scope
5. Dynamically populates child entries with their DNs
6. Each level gets placeholders so deeper levels can be explored

### Error Handling
- Gracefully handles missing naming context attributes
- Falls back to configured base DN if discovery fails
- Silently handles expand errors (shows as empty node)
- Main dialog still functions even if browser encounters errors

### Performance
- Lazy loading prevents loading entire directory tree upfront
- Only loads one level at a time as user expands
- Large directories stay responsive
- Background loading doesn't block UI

## Usage Example

### For AD (Active Directory)
1. Select "Active Directory" schema
2. Click "Browse..." for Group base DN → Select `CN=Groups,DC=example,DC=com`
3. Click "Browse..." for User base DN → Select `CN=Users,DC=example,DC=com`
4. User filter auto-fills: `(&(objectClass=user)(!(objectClass=computer)))`

### For LDAP (OpenLDAP, 389DS)
1. Select "POSIX Groups (memberUid)" schema
2. Click "Browse..." for Group base DN → Select `ou=groups,dc=example,dc=com`
3. Click "Browse..." for User base DN → Select `ou=users,dc=example,dc=com`
4. User filter auto-fills: `(objectClass=person)`

## Benefits
✅ No more manual DN typing—just browse and select  
✅ Full filter text visible without scrolling  
✅ Better error messages if DN structure is unexpected  
✅ More professional, discoverable UI  
✅ Reduced user errors from typos in DNs  
✅ Self-documenting: users can see the actual directory structure  

## Testing Checklist
- [ ] Launch group import/export workflow
- [ ] Test DN browser with your LDAP server
  - [ ] Can expand naming contexts
  - [ ] Can see sub-DNs
  - [ ] Selection returns correct DN
- [ ] Test that schema selection still auto-fills correctly
- [ ] Test multi-line user filter
  - [ ] Can edit multi-line filters
  - [ ] Newlines preserved in filter text
- [ ] Cancel dialog works as expected
- [ ] Invalid credentials show proper error (from earlier fix)

## Notes
- The DN browser uses the same connection credentials as the LDAP configuration
- If the server denies visibility of certain parts of the tree, those areas won't be browsable
- Lazy loading means large trees stay responsive even with thousands of entries
- The browser is read-only (doesn't modify anything on the server)
