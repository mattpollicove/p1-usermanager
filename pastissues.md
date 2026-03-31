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
- **Issue**: Column order/layout could be lost after a user refresh.
- **Root Cause**: Column move persistence used an inverted visual/logical index mapping, and refresh did not explicitly capture current visual order before rebuilding.
- **Solution**: Added `_capture_current_column_layout()` to persist visual order and widths, invoked before refresh and on column move. Fixed order capture by using `header.logicalIndex(visual_idx)`.
- **Files Affected**: `ui/main_window.py` (`refresh_users`, `on_column_moved`, new layout capture helper)
- **Prevention**: For table-layout persistence, always derive order from visual index -> logical index mapping and persist just before table rebuild operations.

- **Date**: 2026-03-31
- **Issue**: DB import prompted to save queries even when already saved, and query mappings were not consistently tied to saved queries. Import mapping lists could miss custom PingOne attributes.
- **Root Cause**: Query save prompt lacked dedupe logic; mapping persistence was generic rather than query-specific; PingOne attributes were sourced from static schema-only lists.
- **Solution**: (1) Skip save prompt when query already exists and mark it as saved. (2) Persist query-specific import mappings under `db_import_mappings_by_query` and auto-apply when that query is reused. (3) Refresh import mapping attributes from live PingOne user data to include custom attributes.
- **Files Affected**: `ui/main_window.py`
- **Prevention**: Couple reusable query workflows to query-keyed mapping settings and refresh dynamic attribute sources from live API data before mapping dialogs.

- **Date**: 2026-03-31
- **Issue**: DB import/export required re-entering custom queries and mapping choices each time.
- **Root Cause**: Query text and DB mapping selections were not persisted with each saved DB connection.
- **Solution**: Added reusable DB-connection settings storage for `saved_custom_queries`, `last_custom_query`, `db_import_mapping`, and `db_export_mapping`; mapping dialogs now support prefill + "save mapping" option.
- **Files Affected**: `ui/main_window.py` (query prompt + connection settings persistence), `ui/dialogs.py` (DatabaseMappingDialog prefill + remember checkbox)
- **Prevention**: Treat DB connection definitions as reusable workflow profiles that include query and mapping preferences, not just host credentials.

- **Date**: 2026-03-31
- **Issue**: After import, additional mapped attributes were not visible in the User Management grid unless manually added in column selection.
- **Root Cause**: Import completion refreshed data but did not merge newly imported attribute keys into `selected_columns`.
- **Solution**: Added `_include_import_attributes_in_grid()` and invoked it on import completion paths before `refresh_users()`, automatically appending newly imported attribute columns and persisting layout.
- **Files Affected**: `ui/main_window.py` (import completion handlers, new helper, help text)
- **Prevention**: When import payload schemas can vary, merge discovered attribute keys into visible grid columns on successful import.

- **Date**: 2026-03-31
- **Issue**: Imports could fail when a record already existed, even though update behavior was expected.
- **Root Cause**: Bulk create failures for duplicate users were treated as terminal errors instead of retrying as updates.
- **Solution**: Added create->update retry logic in `BulkCreateWorker`: detect duplicate/conflict errors, resolve existing `username -> id`, and retry with `update_user`. Import summaries now report "Updated on retry" counts.
- **Files Affected**: `workers.py` (`BulkCreateWorker`), `ui/main_window.py` (import result summaries)
- **Prevention**: For bulk import flows, handle create conflicts as idempotent upsert behavior when a stable identity key (username) is available.

- **Date**: 2026-03-31
- **Issue**: "Hide Links" checkbox appeared to do nothing in User Management grid.
- **Root Cause**: Column filtering only checked column names, but the problematic link-like data was in column values.
- **Solution**: Extended `_should_hide_column()` to hide columns when either the column name or the first non-empty displayed value starts with `{` or `http`, and trigger table refresh on toggle.
- **Files Affected**: `ui/main_window.py` (column visibility filter + toggle behavior)
- **Prevention**: When adding view filters, validate both metadata (column names) and rendered data patterns so toggles visibly affect the grid.

- **Date**: 2026-03-31
- **Issue**: Runtime errors could surface from `_poll_api_events()` while the main window was closing.
- **Root Cause**: The API event timer could still fire during shutdown and attempt to read or update UI widgets while the window teardown was in progress.
- **Solution**: Added a `_closing` guard, stopped `api_timer` in `closeEvent()`, and made `_poll_api_events()` return early during application shutdown or before required widgets are available.
- **Files Affected**: `ui/main_window.py` (`closeEvent`, `_poll_api_events`, window initialization)
- **Prevention**: Stop active timers during window shutdown and guard timer callbacks against partially-destroyed UI state.

- **Date**: 2026-03-31
- **Issue**: Database table metadata fetch failed with `(1046, 'No database selected')` when updating DB connections. Also, `'DBConnectionsManager' object has no attribute 'edit_btn'` error when opening connection manager.
- **Root Cause**: Buttons in DBConnectionsManager were created after `_populate()` was called, causing signal-triggered `_update_button_state()` to access buttons that didn't exist yet. Database name validation was missing, allowing empty strings through; PyMySQL requires explicit database selection.
- **Solution**: Reorder initialization to create buttons before calling `_populate()`. Add database name validation in `_make_url()`, `test_connection()`, and `get_table_names()`. Add `init_command` to MySQL URL. Show error messages in `_populate_tables()` instead of silently failing.
- **Files Affected**: `ui/dialogs.py` (DBConnectionsManager init order ~L1240, _populate_tables error reporting ~L1100), `api/db_utils.py` (_make_url validation ~L47, test_connection validation ~L80, get_table_names validation ~L170)
- **Prevention**: Create UI widgets before connecting signals. Validate required parameters upstream in API functions. Pass database constraints via connection string rather than relying on separate USE statement. Never silently catch exceptions in UI code.

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
