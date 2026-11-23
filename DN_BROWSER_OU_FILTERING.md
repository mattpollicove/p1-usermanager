# DN Browser OU Filtering Feature

## Overview
Added a "Show only Organizational Units" checkbox to the DN browser dialog, allowing users to filter the directory display to show only OUs and hide other object types.

## Feature Details

### Checkbox Location
- Appears at the top of the DN browser dialog
- Labeled: "Show only Organizational Units"
- Unchecked by default (shows all objects)

### Functionality

#### When Unchecked (Default)
```
Search Filter: (|(objectClass=*))
Result: Shows ALL objects in the directory
  - Organizational Units (OUs)
  - Containers (CN=)
  - Domains (DC=)
  - Custom objects
  - Everything else
```

#### When Checked
```
Search Filter: (objectClass=organizationalUnit)
Result: Shows ONLY Organizational Units
  - OU objects only
  - Cleaner, simpler view
  - Easier navigation to group/user containers
```

## Usage Scenario

### Finding Groups Base DN (Example)
1. Click "Browse..." next to Group base DN
2. DN browser opens showing full directory structure
3. Check "Show only Organizational Units"
4. Tree now displays only OUs (e.g., `OU=Groups,DC=pollicove,DC=net`)
5. Navigate to `OU=Groups` or similar
6. Click to select as base DN

### Finding Users Base DN (Example)
1. Click "Browse..." next to User base DN
2. DN browser opens
3. Check "Show only Organizational Units"
4. Tree shows only OUs (e.g., `OU=Users,DC=pollicove,DC=net`)
5. Navigate to the users container
6. Click to select as base DN

## Technical Implementation

### File Modified
- `ui/group_transfer.py` - `_browse_ldap_dn()` function

### Code Changes

**1. Added Filter Checkbox (Lines ~84-90)**
```python
# Filter options
filter_layout = QtWidgets.QHBoxLayout()
ou_only_cb = QtWidgets.QCheckBox("Show only Organizational Units")
ou_only_cb.setChecked(False)
filter_layout.addWidget(ou_only_cb)
filter_layout.addStretch()
layout.addLayout(filter_layout)
```

**2. Dynamic Search Filter (Lines ~148-154)**
```python
# Determine search filter based on checkbox
if ou_only_cb.isChecked():
    # Only show Organizational Units
    search_filter = "(objectClass=organizationalUnit)"
else:
    # Show all objects
    search_filter = "(|(objectClass=*))"

conn.search(dn, search_filter, search_scope=SUBTREE, ...)
```

**3. Filter Change Handler (Lines ~156-165)**
```python
def on_filter_changed():
    """Refresh tree when filter checkbox is toggled."""
    # Collapse and re-expand to refresh with new filter
    for i in range(tree.topLevelItemCount()):
        top_item = tree.topLevelItem(i)
        tree.collapseItem(top_item)
        # Clear children to force reload on next expand
        top_item.takeChildren()
        QtWidgets.QTreeWidgetItem(top_item, ["Loading..."])

ou_only_cb.stateChanged.connect(on_filter_changed)
```

## Benefits

✅ **Cleaner UI** - Shows only relevant containers when checked  
✅ **Faster Navigation** - Fewer items to scroll through  
✅ **Flexible** - Can toggle between filtered and unfiltered views  
✅ **Standard** - Uses standard LDAP `organizationalUnit` objectClass  
✅ **Non-Destructive** - Just a display filter, doesn't modify anything  

## Behavior Details

### Default Behavior
- Checkbox starts **unchecked**
- Shows full directory structure
- Users can see all object types
- Useful for learning directory layout

### Filtered Behavior
- When **checked**, shows only OUs
- Significantly reduces clutter
- Makes it easier to identify group/user containers
- Faster to navigate to desired location

### Real-time Updates
- Toggling the checkbox immediately refreshes the tree
- All expanded items collapse and reload with new filter
- No dialog close/reopen needed
- Changes apply immediately on next expand

### Edge Cases
- **If no OUs exist:** Empty tree shown (expected)
- **If base DN is an OU:** Still shown (it's the root of subtree)
- **Large OU structures:** Still responsive (size limit 1000)
- **Multiple naming contexts:** Filter applies to all

## LDAP Schema Notes

### Organizational Unit Filter
```
objectClass=organizationalUnit
```
- Standard across all LDAP servers
- Active Directory: Uses `OU` prefix in DNs
- OpenLDAP/389DS: Uses `ou` RDN component

### Why OUs?
- OUs are the standard container for organizing directory objects
- Groups typically stored in `OU=Groups`
- Users typically stored in `OU=Users`
- Easiest way to identify relevant search bases

## Testing Checklist
- [x] Checkbox appears in dialog
- [x] Unchecked by default
- [x] "Show all objects" mode works (unchecked)
- [x] "Show only OUs" mode works (checked)
- [x] Toggling filter refreshes tree
- [x] Tree reloads with new filter on expand
- [x] Code compiles without errors
- [x] No performance issues with filter

## UI/UX Details

### Checkbox Styling
- Standard QCheckBox widget
- Located at top of dialog above tree
- Left-aligned with label
- Right side has stretch space for future controls

### Dialog Sizing
- Increased height to 450px (from 400px)
- Accommodates checkbox + tree + labels comfortably
- Resizable by user if needed

### Visual Feedback
- Checkbox clearly labeled
- Status updates when filter changes
- Tree collapses/reloads with new filter
- Loading indicators show during refresh

## Example Directory Structure

### Without Filter (All Objects)
```
DC=pollicove,DC=net
├── CN=Administrator
├── CN=Configuration
├── CN=DomainDnsZones
├── CN=ForestDnsZones
├── CN=Groups          ← objectClass=container
├── CN=Users           ← objectClass=container
├── OU=Accounting      ← objectClass=organizationalUnit
├── OU=Finance         ← objectClass=organizationalUnit
└── OU=IT              ← objectClass=organizationalUnit
```

### With Filter (Only OUs)
```
DC=pollicove,DC=net
├── OU=Accounting
├── OU=Finance
└── OU=IT
```

Much cleaner! 🎯

## Future Enhancement Possibilities

1. **Additional Filters:**
   - Show only Containers
   - Show only Groups
   - Show only Users
   - Custom filter expressions

2. **Search Functionality:**
   - Text search within filtered results
   - Quick navigation to container

3. **Multi-select:**
   - Select multiple base DNs
   - Combine multiple containers

4. **Favorites:**
   - Save frequently used DNs
   - Quick access to common locations

## Notes

- Filter only affects DISPLAY, not underlying data
- Original directory structure unchanged
- Filter state persists during session
- Checkbox unchecks if dialog is reopened (new instance)
- Works with all LDAP servers supporting standard schema
