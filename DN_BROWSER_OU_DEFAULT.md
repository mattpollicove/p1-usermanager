# DN Browser OU Filter - Default Changed to Enabled

## Change Made
Updated the "Show only Organizational Units" checkbox in the DN browser to be **checked by default** instead of unchecked.

## Before
- Checkbox started unchecked
- Users saw full directory structure (all object types)
- Had to manually check the box to filter to OUs only

## After
- Checkbox starts **checked** ✓
- Users see only Organizational Units by default
- Much cleaner starting view
- Users can uncheck if they need to see all object types

## Why This Makes Sense

When selecting group and user base DNs, OUs are almost always what users need:
- Groups are typically in `OU=Groups`
- Users are typically in `OU=Users`
- OUs are the standard organizational containers

Showing only OUs by default:
- ✅ Cleaner, less cluttered interface
- ✅ Faster to find the right container
- ✅ More intuitive for most use cases
- ✅ Reduces scrolling through irrelevant objects
- ✅ Advanced users can still uncheck if needed

## Usage

### Opening DN Browser (New Default Behavior)
1. Click "Browse..." next to Group base DN
2. DN browser opens with OU-only view active ✓
3. See only OUs like `OU=Groups`, `OU=Users`, etc.
4. Navigate and select the desired OU
5. If you need to see other object types, uncheck the box

### Example Directory View
```
DC=pollicove,DC=net
├── OU=Accounting
├── OU=Finance
└── OU=IT
```

Clean and focused! No clutter from containers, domains, or other objects.

## Technical Details

**File Modified:** `ui/group_transfer.py`

**Change:**
```python
# Before
ou_only_cb.setChecked(False)

# After
ou_only_cb.setChecked(True)
```

**Impact:**
- Single line change
- Affects initial state only (users can toggle)
- No behavior change, just default state
- Backward compatible (users can uncheck if needed)

## Edge Cases

### If directory has no OUs
- Empty tree shown
- User can uncheck to see all objects
- Or manually enter DN

### If base DN itself is in a container
- Still shown (it's the root of the subtree)
- Fully functional

### Advanced Users
- Can uncheck at any time to see full structure
- Filter state applies during the session
- Resets to checked when reopening browser

## Testing
- [x] Checkbox starts checked
- [x] Tree shows only OUs on initial expand
- [x] Unchecking shows all objects
- [x] Rechecking filters back to OUs
- [x] Works for both Group and User DN selection

## Files Modified
- `ui/group_transfer.py` - Line 84: `setChecked(True)` instead of `setChecked(False)`

## Next Time User Opens Browser
They'll see a focused, clean view showing only Organizational Units, making it much easier to select the correct group/user base DN.
