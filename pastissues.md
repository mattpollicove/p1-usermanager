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

_None at this time._

### Resolved

- **Date**: 2026-04-15
- **Issue**: Database export failed with `pymysql.err.OperationalError: (1054, "Unknown column 'lifecycle_status' in 'INSERT INTO'")`. Export tried to insert data into columns that didn't exist in the target table.
- **Root Cause**: The `create_table_if_not_exists` function only creates tables if they don't exist, but doesn't add missing columns to existing tables. When a saved mapping includes columns not present in the current table schema, or when exporting to a table created with fewer columns, the INSERT fails.
- **Solution**: Added `add_missing_columns()` function to `db_utils.py` that detects and adds missing columns to existing tables using ALTER TABLE statements. The export flow now: (1) creates table if needed, (2) adds any missing columns to existing table, (3) inserts data. Users see a status bar notification showing which columns were added.
- **Files Affected**: `api/db_utils.py` (new add_missing_columns function), `ui/main_window.py` (export_to_database method)
- **Prevention**: When exporting to databases, always ensure the target table schema matches the mapping. Auto-add missing columns with ALTER TABLE before INSERT operations. Add checklist item: "Database exports auto-add missing columns to existing tables."
- **Status**: RESOLVED (2026-04-15)

- **Date**: 2026-04-15
- **Issue**: Database export failed with `pymysql.err.OperationalError: (1054, "Unknown column 'account.canAuthenticate' in 'INSERT INTO'")`. Dotted column names like `account.canAuthenticate`, `identityProvider.type` were being used in SQL INSERT statements.
- **Root Cause**: Column name sanitization (converting dots to underscores) only ran when creating new tables (`if not cols` block). When exporting to existing tables, the mapping used dotted names directly in SQL statements, which are invalid SQL identifiers.
- **Solution**: Moved column sanitization logic outside the `if not cols` conditional so it always runs for both new and existing tables. Now all target column names are sanitized via `_sanitize_db_column_name()` before being used in SQL statements.
- **Files Affected**: `ui/main_window.py` (export_to_database method)
- **Prevention**: Always sanitize database column names for SQL compatibility regardless of whether the table is new or existing. Add checklist item: "Database export column names sanitized for SQL (dots → underscores)."
- **Status**: RESOLVED (2026-04-15)

- **Date**: 2026-04-15
- **Issue**: Database export failed with `pymysql.err.OperationalError: (1054, "Unknown column '_embedded' in 'INSERT INTO'")`. Metadata fields (`_embedded`, `_links.*`, etc.) were being included in database exports causing SQL errors.
- **Root Cause**: Database exports bypassed the ExportOptionsDialog (which filters metadata) and went directly to DatabaseMappingDialog. Existing table columns could contain metadata fields from previous exports. Saved mappings could also contain metadata field references. Metadata was present in four places: (1) existing table columns, (2) post-migration table columns, (3) initial saved mappings, (4) final mapping after dialog confirmation.
- **Solution**: Added comprehensive metadata filtering at all four points: (1) Filter existing table columns immediately after fetching, (2) Filter columns after migration completes, (3) Filter saved initial_mapping before passing to dialog, (4) Final safeguard filter on effective_mapping after user confirms. Also filtered PingOne attributes list to exclude metadata before populating mapping dialog choices.
- **Files Affected**: `ui/main_window.py` (export_to_database method with four filtering checkpoints)
- **Prevention**: When exporting to external systems (databases, LDAP, etc.), always filter API metadata fields (`_embedded`, `_links`) from both source attributes and target columns at every stage: initial column lists, saved mappings, and final effective mappings. Add checklist item: "Metadata fields filtered from external exports."
- **Status**: RESOLVED (2026-04-15)

- **Date**: 2026-04-06
- **Issue**: LDAP import failed with PingOne `400 INVALID_DATA` — `employeeNumber must be a STRING object` / `address.postalCode must be a STRING object`.
- **Root Cause**: Two conversion points produced numeric payloads: (1) `_normalize_attr_value` in `ldap_utils.py` could return raw non-string scalars from LDAP values. (2) `_unflatten_user` attempted `json.loads()` on _all_ strings; scalar strings like `"75038"` were parsed to integer `75038`, reintroducing numeric types for fields like `address.postalCode`.
- **Solution**: (1) Fixed `_normalize_attr_value` to always return strings for scalar values (plus bytes → UTF-8 decode). (2) Hardened `_unflatten_user` to JSON-parse only structured values (`{...}` / `[...]`), never plain scalar strings. (3) Added recursive import-time coercion that converts numeric scalars to strings across nested payloads before validation/API calls.
- **Files Affected**: `api/ldap_utils.py` (`_normalize_attr_value`), `ui/main_window.py` (`_convert_rows_to_users`)
- **Prevention**: Add to LDAP/DB import checklist: scalar PingOne fields (e.g. `employeeNumber`, `address.postalCode`) must be strings. Never run JSON parsing on plain scalar strings in unflattening logic. Always coerce numeric scalars to strings recursively before validation/send. Test with LDAP directories that emit integer-syntax attributes.
- **Status**: RESOLVED (2026-04-06)

- **Date**: 2026-04-06
- **Issue**: Phone number mapping in DatabaseMappingDialog could lose type distinctions (mobile/work/home) if not explicitly mapped.
- **Root Cause**: Risk that mapping might default to generic `phoneNumbers` instead of `phoneNumbers.mobile/work/home`, causing imported phone data to lose type classification.
- **Solution**: Audited `_expand_phone_numbers` (dialogs.py ~L2103), `_build_import_rows` (dialogs.py ~L2031), `get_mapping` (dialogs.py ~L2169), and DB-row-to-user conversion (main_window.py ~L3490). All correctly use `::` encoding for phone source keys and `phoneNumbers.<type>` targets. Phone types are preserved end-to-end.
- **Files Affected**: `ui/dialogs.py`, `ui/main_window.py`
- **Prevention**: Always prefer explicit typed phone attributes (`phoneNumbers.mobile/work/home`) in import mappings. Verify that `source_key` in `_build_import_rows` stores `col::type` for phone rows, and that `get_mapping()` reads back the `UserRole` data (not display text) when collecting results.
- **Status**: RESOLVED (code verified correct 2026-04-06)

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
