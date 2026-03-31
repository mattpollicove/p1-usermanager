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
- **Issue**: Database table metadata fetch failed with `(1046, 'No database selected')` when updating DB connections. Also, `'DBConnectionsManager' object has no attribute 'edit_btn'` error when opening connection manager.
- **Root Cause**: (1) Buttons in DBConnectionsManager were created after _populate() was called, so signal-triggered _update_button_state() tried to access buttons that didn't exist yet. (2) Database name validation was missing, allowing empty strings through; PyMySQL requires explicit database selection via URL or init command.
- **Solution**: (1) Reorder initialization to create buttons BEFORE calling _populate(). (2) Add database name validation in _make_url(), test_connection(), and get_table_names(). (3) Add init_command to MySQL URL to ensure database is selected. (4) Show error messages in _populate_tables() instead of silently failing.
- **Files Affected**: `ui/dialogs.py` (DBConnectionsManager init order ~L1240, _populate_tables error reporting ~L1100), `api/db_utils.py` (_make_url validation ~L47, test_connection validation ~L80, get_table_names validation ~L170)
- **Prevention**: (1) Create UI widgets before connecting signals to them. (2) Always validate required parameters upstream in API functions, not downstream. (3) Pass database constraints via connection string (init_command) rather than relying on separate USE statement. (4) Never silently catch exceptions in UI code; report them to the user.

- **Date**: 2026-03-31
- **Issue**: Database import failed with `pymysql.err.ProgrammingError: Incorrect table name 'people '` due to trailing whitespace in table names.
- **Root Cause**: Table names were read from combo boxes and user input without stripping whitespace, then passed to SQL queries which interpreted the space as part of the identifier.
- **Solution**: Strip whitespace from table names in three places: (1) `_quote_table_identifier()` in db_utils, (2) when populating table combos from database, (3) when accepting user input for table names.
- **Files Affected**: `api/db_utils.py` (_quote_table_identifier ~L41), `ui/dialogs.py` (_populate_tables ~L1108), `ui/main_window.py` (import_from_database_wizard ~L1357)
- **Prevention**: Always strip user input and database-sourced identifiers before using in SQL queries. Apply sanitization at both input and query execution layers.

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

