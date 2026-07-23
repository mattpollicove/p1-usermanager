# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed
- Bumped application version to `0.82`.
- Database connectivity is now JDBC-only for MSSQL, MySQL, and Oracle.
- Removed non-JDBC fallback guidance from active docs and UI guidance.

### Added
- Oracle support in database connection configuration and JDBC URL preview.
- Explicit prerequisites documentation for JDBC bridge (`jaydebeapi`, `JPype1`) and vendor JDBC jars.
- MSSQL Encrypt Mode selector (`Auto` / `On` / `Off`) in DB connection dialog, wired through all JDBC operations.

### Documentation
- Updated `README.md`, `INSTALL.md`, `DEVELOPMENT_SPEC.md`, and `DEVELOPMENT_RULES.md` to reflect JDBC-only database policy.
- Updated `requirements.txt` comments/dependencies to match JDBC-only database support.
- Added MSSQL Encrypt Mode guidance to `README.md` and `INSTALL.md`.

## [0.8] - 2026-04-14
### Added
- Bumped application version to `0.8`.
- Import/export mapping now includes middle name, employee type, address targets, and custom PingOne attributes discovered from live tenant data.
- In-app help text now explicitly documents new mapping aliases and fields for CSV/LDIF/DB/LDAP workflows.

## [0.79] - 2026-04-10
### Added
- Bumped application version to `0.79`.
- User-management troubleshooting improvements: dedicated `USER_MGMT_EDIT_*` logging, filtered log viewer, modeless log windows, and live API capture refresh/event counters.
- User update success notifications with per-profile mute preference and a Settings toggle to re-enable them.

### Changed
- Edit User and User Management updates now sanitize PUT payloads, preserve nested attributes correctly, and avoid sending read-only PingOne fields.
- User Management columns now default to UUID, first name, last name, email, phone, work telephone, title, and population, while hiding link/JSON reference columns by default.
- PingOne work email maps to `mail` and work telephone maps to `workTelephone` in User Management.
- API capture and log viewers now open as separate non-modal windows that can stay open while the app continues running.

### Fixed
- Email cells in User Management now open the Edit User dialog for editing instead of performing no action.
- Keyring backend failures on macOS no longer crash startup; the app falls back gracefully and shows a status-bar warning when secure secret storage is unavailable.

## [0.75] - 2026-04-07
### Added
- Bumped application version to `0.75`.
- LDAP import: coerce numeric scalar values (e.g. `employeeNumber`, `address.postalCode`) to strings so PingOne does not reject them with `400 INVALID_DATA`.
- Import normalization: `_unflatten_user` no longer JSON-parses plain scalar strings, preventing numeric strings being recast to integers; added recursive `_coerce_numeric_scalars_to_strings` sweep before every import API call.
- Export filter: `ExportOptionsDialog` now includes an optional "Filter by populated attributes" section; selecting attributes limits the export to users where all chosen attributes are populated (CSV, LDIF, and LDAP Directory exports).
- LDAP export: PingOne-internal system fields (`id`, `createdAt`, `updatedAt`, etc.) are excluded from the mapping dialog and from built LDAP entries; LDAP target attribute literally named `id` is also blocked.
- Import/Export method memory: last used import method (CSV / LDIF / DB / LDAP) and last used export method are persisted per-profile and pre-selected on next open.
- Fixed corrupted import in `app.py` (stray `/ ` prefix on `from ui.main_window import MainWindow`).
- Pre-change checklist added to `DEVELOPMENT_RULES.md` with guards derived from all past issues.
### Previous (0.71)
- New "New Connection" toolbar button: clears environment ID, client ID, and client secret fields and prompts user to save after entering values.
- Ability to skip automatic connection attempts when loading profiles from disk to avoid spurious "Auth Failed" messages.
- Improved connection testing and error reporting when validating credentials (shows detailed error message).
- Database import/export functionality:
  - Toolbar buttons for importing from and exporting to a database table.
  - `DatabaseConnectionDialog`, `DBConnectionsManager`, and `DatabaseMappingDialog` for managing connections and mapping between PingOne attributes and database columns.
  - SQLAlchemy-based helpers in `api/db_utils.py` to test connections, fetch table schemas, and sample rows.
  - Support for MySQL/MariaDB and SQL Server drivers via `pymysql` and `pymssql`.
  - Prompted users to save connection profiles on first use.
  - Database connection dialog now:
    * defaults to MariaDB/MySQL and automatically fills port numbers (3306/1433) when type is changed.
    * shows a status line and uses a busy cursor while testing connections.
    * can list and remember a target table via a drop‑down populated after successful test.
    * builds and displays a JDBC connection string in real time as host/port/db/type are entered.
  - Fix: database connection dialog now validates required fields (name, host, database) and warns when adding a duplicate-name profile.
  - Fix: avoid AttributeError by initializing host/port/db widgets before setting placeholders/tooltips.
  - Fix: ensure `jdbc_edit` is created before use and visible in the form.
  - **Handle missing SQLAlchemy gracefully** in the connection dialog; test button shows
    an explicit error if the dependency is missing instead of crashing.  Import
    and export operations now include the same check and message.
- **Check SQLAlchemy on startup** by importing it in `app.py` so the program
    fails fast with a clear error if the requirement isn’t installed.

- **Save connection option**: A "Save this connection" checkbox lets users
    test or use credentials without persisting them.  Unchecking it in the
    connections manager will prevent creation or delete an existing entry.
- **Fix manager persistence**: DB connections are now written to the config
    file whenever the manager dialog closes.  Previously the value returned by
    `exec()` was mistakenly checked for `QDialog.Accepted`, which never
    occurred with a Close-only dialog, so profiles were never saved.
- **Show selected driver name**: Connection dialog now displays the currently
    chosen driver string below the driver field, helping users verify what will
    be sent to the backend during connection tests.
- **Improved connection error reporting**: When a test fails, the actual
    exception message is now displayed (e.g., driver not found, network
    unreachable, authentication failed) instead of a generic "check credentials
    and driver" message.  This makes debugging connection issues much easier.
- **Fix database type recognition**: Connection tests now correctly handle the
    combo box display values "MariaDB/MySQL" and "MSSQL" instead of requiring
    shorthand like "mysql" or "sqlserver".  Users can now test connections
    without errors about unsupported database types.
  - **Reorder and resize JDBC URL field** to the bottom of the form and widen
    it for improved readability.
  - **Table selector starts empty** and will only be populated after a *successful*
    connection test; any previous list is cleared on failure.
- Dark Mode: Toggle between light and dark themes via Settings menu (Cmd/Ctrl+D).
  - Theme preference is persisted in profiles.json and restored on startup.
  - Dark mode applies a comfortable color scheme optimized for low-light environments.
  - Delete button styling adapts to the selected theme.
- Profile Manager: View and manage all saved profiles from File → Manage Profiles (Cmd/Ctrl+Shift+M).
  - See a list of all profiles with their environment IDs, client IDs, and column counts.
  - Delete unwanted profiles directly from the manager dialog.
  - Active profile is highlighted and protected from deletion.
  - Streamlined profile cleanup with batch deletion support.
  - **New Profile creation with credentials**: Create new profiles and optionally enter connection details (Environment ID, Client ID, Client Secret) directly in the Profile Manager.
  - Client Secret field includes show/hide toggle for security.
  - Credentials are optional - can create profiles and configure later.
  - Partial credential validation warns if only some fields are filled.
  - New profiles are automatically selected and loaded in the Configuration tab.
  - **Connection test from Profile Manager**: When a profile is created with complete credentials, the application offers to test the connection immediately. Profile Manager window remains open during the test and only closes after successful connection.
  - **All input fields properly sized**: Profile name, Environment ID, Client ID, and Client Secret fields are all sized to comfortably display full values (matching Profile Manager field dimensions).
  - **Optimized layout alignment**: Client Secret field and label are properly aligned with zero-margin layout and consistent spacing.
  - **Enhanced details display**: Environment and Client ID fields are wider to show full UUIDs.
  - **Scrollable columns list**: All columns are displayed in a scrollable text area (auto-scrolls when > 3 lines).
- **Default columns updated**: When establishing a new connection, the default columns are now: UUID, First Name, Last Name, Email, and Population (in that order).
- **Column selection enhancements**: 
  - Column selection dialog includes "Select All", "Clear All", and "Reset to Defaults" buttons.
  - Column configurations are saved per-profile, allowing different layouts for different environments.
  - Refresh operations now respect saved column configurations instead of auto-discovering new columns.
- **Status bar improvements**:
  - Active profile name is displayed on the status bar for easy reference.
  - Column layout save operations show confirmation notifications.
  - Persistent profile indicator remains visible across all operations.

### Changed
- Menu bar reorganization: File menu is now first (standard convention), followed by Settings, Logs, and Help.

### Fixed
- Column configuration isolation: Fixed bug where column settings were shared between profiles due to list reference issues. Each profile now maintains independent column configurations.
- Column order preservation: Fixed issue where "Reset to Defaults" button wasn't preserving the correct default column order.

## [v0.52] - 2026-01-29
### Added
- Cross-platform UI optimizations for Windows, macOS, and Linux:
  - Platform-aware keyboard shortcuts (Cmd on macOS, Ctrl on Windows/Linux) for all major actions.
  - Refresh: Cmd/Ctrl+R, Delete: Delete/Backspace, Save Layout: Cmd/Ctrl+S, Import CSV: Cmd/Ctrl+I, Export CSV: Cmd/Ctrl+E, Columns: Cmd/Ctrl+K, Quit: Cmd/Ctrl+Q.
  - DPI-aware dialog sizing for high-resolution displays.
  - Native menu bar support on macOS with proper Quit action placement.
  - Platform-specific file dialog behavior (native on macOS/Windows, Qt on Linux).
  - Tooltips showing keyboard shortcuts for all major buttons.

### Changed
- Main window and all dialogs now scale appropriately based on display DPI.
- File dialogs (Import/Export/Archive) use platform-appropriate native dialogs.
- Menu bar behavior adapted for each platform (native on macOS, integrated on Windows/Linux).

### Improved
- Better usability across different operating systems and screen resolutions.
- Consistent keyboard navigation and shortcuts across platforms.
- Enhanced accessibility with tooltips and platform-native UI elements.

## [v0.51] - 2026-01-28
### Added
- Logs menu with Show/Reset/Clear/Archive actions and optional log rotation.
- `DEVELOPMENT_RULES.md` with rule to update help docs when changing UI or behavior.
- Developer reminders added to UI help code (`ui/main_window.py`, `ui/dialogs.py`) and README.

### Changed
- CSV/LDIF import: usernames normalized; importer now updates existing users instead of creating duplicates when usernames match.
- Removed server-side dry-run validation from import flow; local JSON Schema validation may be used when available.
- Import mapping dialog: `enabled` field is a dropdown; mapping persistence per-profile only when "Remember mapping for this profile" is checked.
- Single-click selects rows; double-click required to edit `id`/`username` fields.
- Fixed stray mapping issue that produced empty-string keys; payloads are cleaned before sending.
- Bumped application version to `0.51`.

### Fixed
- Resolved syntax errors introduced during refactors.
- Added guards and diagnostics to prevent UNIQUENESS_VIOLATION caused by malformed payloads.


[Unreleased]: https://example.com/compare/v0.50...v0.51
