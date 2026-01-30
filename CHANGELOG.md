# Changelog

All notable changes to this project will be documented in this file.

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
