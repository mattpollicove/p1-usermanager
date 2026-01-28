# Changelog

All notable changes to this project will be documented in this file.

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
