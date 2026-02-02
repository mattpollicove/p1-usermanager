# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [v0.6] - 2026-02-02
### Added
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
