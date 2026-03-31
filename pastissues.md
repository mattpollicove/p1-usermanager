# Past Issues & Lessons Learned

This file tracks issues that have been encountered and resolved. When making code updates, review this list to ensure the same problems do not recur.

## Issue Template
- **Date**: YYYY-MM-DD
- **Issue**: Description of the problem
- **Root Cause**: What caused it
- **Solution**: How it was fixed
- **Files Affected**: Which files were involved
- **Prevention**: How to avoid this in future updates

---

## Issues

### Current (Active/Pending)

- **Date**: TBD
- **Issue**: Phone number mapping in DatabaseMappingDialog may lose type distinctions (mobile/work/home) if not explicitly mapped.
- **Root Cause**: If mapping defaults to generic 'phoneNumbers' instead of 'phoneNumbers.mobile/work/home', imported phone data loses type classification.
- **Solution**: Ensure phone columns are mapped to explicit typed targets like `phoneNumbers.mobile` rather than untyped `phoneNumbers`.
- **Files Affected**: `ui/dialogs.py` (DatabaseMappingDialog class, _expand_phone_numbers method ~L1546)
- **Prevention**: Always prefer explicit typed phone attributes in import mappings.
- **Status**: PENDING AUDIT (already has phone type expansion logic but needs verification)

### Resolved

- **Date**: 2026-03-31
- **Issue**: DBConnectionsManager broke itemSelectionChanged/itemActivated signals when repopulating the QListWidget after editing.
- **Root Cause**: Calling `clear()` triggered `itemSelectionChanged` before items were re-added, causing spurious state changes and button state confusion.
- **Solution**: Modified `_populate()` to block signals during clear/repopulate, then manually trigger `_update_button_state()` after unblocking.
- **Files Affected**: `ui/dialogs.py` (DBConnectionsManager._populate method ~L1290)
- **Prevention**: Always block signals on widgets during bulk operations (clear/repopulate), then unblock and manually update dependent state.

- **Date**: 2026-03-31
- **Issue**: Status bar "Last source" context was incomplete—CSV/LDIF exports did not update the status bar with file information.
- **Root Cause**: `_set_last_data_source()` was called in import handlers but not in corresponding export handlers (`export_to_csv()`, `export_to_ldif()`).
- **Solution**: Added `_set_last_data_source()` calls after successful CSV and LDIF exports to maintain consistent context.
- **Files Affected**: `ui/main_window.py` (export_to_csv ~L3201, export_to_ldif ~L3299)
- **Prevention**: When adding bulk data operations (import/export), always call context-update methods in all branches to keep UI state coherent.

- **Date**: 2026-03-31
- **Issue**: PingOne Console URL was being over-normalized, stripping query parameters and fragments. User entered `https://console.pingone.com/?env=429f5783-0f16-432f-b726-88223c380ab0#/overviewDashboard` but it was saved as just `https://console.pingone.com`.
- **Root Cause**: Normalization logic was extracting only scheme, host, and port, discarding path, query, and fragment. The design assumed only a base URL would be stored.
- **Solution**: Modified `_normalize_pingone_console_url()` to preserve the full URL as entered. Updated `open_pingone_console()` and `update_pingone_console_env_label()` to detect when URL already has query params/fragment and use it as-is instead of appending env params.
- **Files Affected**: `ui/main_window.py`
- **Prevention**: When storing user-configurable URLs, preserve them fully. Detect when a URL already has query/fragment and don't duplicate params.

