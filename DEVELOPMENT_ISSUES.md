# Development Issues Log

## 2026-06-11 - Duplicate Keychain Prompts On Startup/Profile Switch

### Problem
- macOS Keychain was prompting twice during startup auto-connect.
- Switching profiles/environments could trigger repeated keychain prompts in the same app session.

### Root Cause
- In auto-connect flow, profile selection triggered `load_selected_profile()` via `currentIndexChanged`, and the code also called `load_selected_profile()` manually right after.
- That caused duplicate `keyring.get_password()` calls.
- Profile switches always read from keyring even if the same secret had already been read during the current session.

### Attempted Solutions
- Confirmed all `keyring.get_password`, `keyring.set_password`, and `keyring.delete_password` call paths in `ui/main_window.py`.
- Traced startup flow in `load_profiles_from_disk()` and validated duplicate loader invocation.

### Final Resolution
- Updated auto-connect branch to block combo-box signals while setting profile index, then perform exactly one explicit `load_selected_profile()`.
- Added in-memory per-session secret cache (`self._secret_cache`) to avoid repeated keychain reads for already-loaded profiles.
- Kept cache coherent by updating it on secret saves and clearing entries on profile deletion.

### Before/After Snippets

#### Before (duplicate load path)
```python
self.profile_list.setCurrentIndex(idx)
try:
    self.load_selected_profile()
except Exception:
    pass
```

#### After (single load path)
```python
self.profile_list.blockSignals(True)
self.profile_list.setCurrentIndex(idx)
self.profile_list.blockSignals(False)
self.load_selected_profile()
```

#### Added cache use in profile load
```python
if name in self._secret_cache:
    secret = self._secret_cache.get(name) or ""
else:
    secret = keyring.get_password("pingone_usermanager", name) or ""
    self._secret_cache[name] = secret
self.cl_sec.setText(secret)
```

### Lessons Learned
- Signal-connected UI handlers and manual calls must be audited together to prevent duplicate side effects.
- Keychain/keyring access should be minimized in interactive desktop apps to reduce repeated unlock prompts.

## 2026-06-11 - User Management Not Refreshing After Configuration Switch

### Problem
- Switching to another profile/configuration did not automatically refresh user data when entering the User Management tab.

### Root Cause
- There was no tab change handler to detect entry into User Management and no "pending refresh" state tied to profile switches.

### Final Resolution
- Added `on_main_tab_changed()` and connected it to `self.tabs.currentChanged`.
- Added `_pending_user_tab_refresh` state, set to `True` when the active profile changes in `load_selected_profile()`.
- When the User Management tab is selected and the flag is set, `refresh_users()` runs and the flag is reset.

### Before/After Snippets

#### Before
```python
self.tabs.addTab(env_tab, "Configuration"); self.tabs.addTab(user_tab, "User Management")
```

#### After
```python
self.tabs.addTab(env_tab, "Configuration"); self.tabs.addTab(user_tab, "User Management")
self.tabs.currentChanged.connect(self.on_main_tab_changed)

def on_main_tab_changed(self, index):
    if self.tabs.tabText(index) == "User Management" and self._pending_user_tab_refresh:
        self._pending_user_tab_refresh = False
        self.refresh_users()
```

### Lessons Learned
- Profile-switch workflows should explicitly mark data stale and refresh on context entry points (like tab activation).

## 2026-06-11 - MSSQL Guidance In UI Tooltip Not Aligned

### Problem
- The database connection dialog tooltip used generic JDBC/ODBC wording and did not match the approved two-option MSSQL setup guidance.

### Root Cause
- UI tooltip text in the DB connection dialog was older than the runtime error and install-document guidance.

### Final Resolution
- Updated the `driver_combo` tooltip in `ui/dialogs.py` to mirror:
    - Option 1: JDBC (`pip install jaydebeapi JPype1`, set Driver Path to `.jar`)
    - Option 2: `pymssql` (`pip install pymssql`)
- Kept MariaDB/MySQL note unchanged.

### Before/After Snippets

#### Before
```python
"MSSQL JDBC: Browse to select a mssql-jdbc .jar file (recommended).\n"
"MSSQL ODBC: type or select an ODBC driver name (e.g. ODBC Driver 18 for SQL Server).\n"
```

#### After
```python
"MSSQL OPTION 1 (recommended): set Driver Path to a mssql-jdbc .jar file.\n"
"Install: pip install jaydebeapi JPype1\n"
"MSSQL OPTION 2: install pymssql (pure Python, no system drivers).\n"
"Install: pip install pymssql\n"
```

### Lessons Learned
- Keep runtime errors, install docs, and UI helper text synchronized to avoid conflicting setup instructions.

## 2026-06-11 - Enforce JDBC-Only DB Support (MSSQL/MySQL/Oracle)

### Problem
- The app mixed JDBC and non-JDBC database paths (pymysql/pymssql/pyodbc), and Oracle was not supported.
- Documentation and prerequisites did not consistently reflect a JDBC-only model across supported databases.

### Root Cause
- Database engine creation in `api/db_utils.py` had fallback paths for Python DBAPI/ODBC drivers.
- DB dialog defaults/tooltips and docs were written for MSSQL + MariaDB/MySQL mixed driver modes.

### Final Resolution
- Refactored DB engine path to JDBC-only in `api/db_utils.py` for `MSSQL`, `MySQL`, and `Oracle`.
- Added Oracle JDBC support (`oracle.jdbc.OracleDriver`, `jdbc:oracle:thin:@//host:port/service`).
- Updated inspector SQL for MSSQL/MySQL/Oracle metadata queries.
- Updated DB dialog type selector, defaults, JDBC URL preview, and helper text in `ui/dialogs.py`.
- Updated in-app help text in `ui/main_window.py` and docs in `README.md`, `INSTALL.md`, and `requirements.txt`.

### Before/After Snippets

#### Before (mixed DBAPI fallback)
```python
try:
    import pymssql
    return f"mssql+pymssql://..."
except ImportError:
    import pyodbc
    return f"mssql+pyodbc://..."
```

#### After (JDBC-only)
```python
if not _is_jdbc_jar(driver_path):
    raise ImportError(_get_mssql_driver_error())
return _JDBCEngine(db_kind, host, port, db_name, user, password, driver_path)
```

### Lessons Learned
- Mixing transport layers (JDBC + non-JDBC) creates drift in UI behavior, backend logic, and install docs.
- A single connectivity model is easier to support and document across multiple databases.

## 2026-06-11 - Requirements And Documentation Alignment For JDBC-Only Policy

### Problem
- Active documentation needed to be fully aligned with the JDBC-only database policy and dependency set.

### Root Cause
- Some docs had already been updated, but the development spec and changelog lacked explicit JDBC-only language and prerequisites summary.

### Final Resolution
- Confirmed `requirements.txt` includes JDBC bridge dependencies only for DB connectivity (`jaydebeapi`, `JPype1`) and removed non-JDBC DB drivers.
- Updated active documentation (`README.md`, `INSTALL.md`, `DEVELOPMENT_SPEC.md`, `CHANGELOG.md`, `DEVELOPMENT_RULES.md`) to consistently state JDBC-only support for MSSQL/MySQL/Oracle.

### Before/After Snippets

#### Before
```markdown
## [Unreleased]
```

#### After
```markdown
## [Unreleased]

### Changed
- Database connectivity is now JDBC-only for MSSQL, MySQL, and Oracle.
```

### Lessons Learned
- Keep requirements and documentation updates in the same change cycle whenever database policy changes.
