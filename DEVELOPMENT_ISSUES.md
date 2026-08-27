<!-- markdownlint-disable -->

# Development Issues Log

## 2026-08-21 - Fix CSV Import Crash: AttributeMappingDialog Missing initial_mapping

### Problem

- CSV import could fail when opening the attribute mapping dialog with:
    - `'AttributeMappingDialog' object has no attribute 'initial_mapping'`

### Root Cause

- `AttributeMappingDialog._populate_table()` references `self.initial_mapping` when restoring saved mappings.
- In the dialog constructor, `initial_mapping` was accepted as a parameter but never assigned to an instance attribute.

### Final Resolution

- Initialized the missing attribute in `AttributeMappingDialog.__init__`:

```python
self.initial_mapping = dict(initial_mapping or {})
```

- This guarantees `_populate_table()` can safely read the mapping state on first render and during table rebuilds.

### Lessons Learned

- Any constructor parameter that is consumed by helper methods should be normalized and assigned during initialization to avoid runtime attribute errors.

## 2026-06-12 - Fix DB Import Rows Not Importing Due to Source Key Mismatch

### Problem

- Database import reported rows read successfully, but items still did not import.
- User payload conversion silently skipped mapped fields for some rows.

### Root Cause

- Wizard path rewrote DB row keys using dotted->underscore conversion before mapping.
- Mapping source keys from the dialog did not always match rewritten keys, especially with JDBC/JPype-origin keys.
- In `_convert_rows_to_users`, lookups depended on exact key match, causing values like `username` to be missed and rows to be skipped from create/update batches.

### Final Resolution

- In wizard import path, normalized row keys to Python strings only (no forced dotted->underscore rewrite).
- In `_convert_rows_to_users`, normalized each row to `row_str = {str(k): v ...}` and added fallback lookup for dotted/underscore variants.
- This preserves compatibility with legacy underscore schemas while keeping mapping resolution reliable.

### Lessons Learned

- Normalize key *types* at DB boundaries, but avoid mutating key *semantics* before applying explicit user mapping.
- For import mapping, robust source lookup should support known naming variants (`name.given` vs `name_given`).

## 2026-06-12 - Add DB Import Row Mapping Debug Counters in UI Status

### Problem

- Remaining data-specific failures were hard to isolate because import only reported final create/update totals.
- There was no direct visibility into how many DB rows were successfully mapped vs skipped before worker execution.

### Final Resolution

- Added conversion-time debug counters in `_convert_rows_to_users(...)`:
    - `total_rows`
    - `mapped_rows`
    - `skipped_rows`
    - `skip_reasons` aggregated by reason
    - `sampled_skips` first 10 skipped row summaries
- Added one-line status formatter `_format_import_mapping_debug_summary(...)`.
- Wired both DB import flows to display status messages immediately after conversion:
    - `Row mapping: total=..., mapped=..., skipped=... (reason: count; ...)`
    - Optional sampled skip line: `Sample skipped rows: Row X: reason | ...`

### Example Status Output

- `Row mapping: total=4, mapped=1, skipped=3 (blank username: 1; missing username: 1; no mapped attributes: 1)`

### Lessons Learned

- Conversion-stage diagnostics dramatically reduce time to identify mapping/data issues before API calls begin.

## 2026-06-12 - Fix Remaining Qt java.lang.String Conversion Errors in DB Table Lists

### Problem

- UI emitted repeated errors like:
    - `_pythonToCppCopy: Cannot copy-convert ... (java.lang.String) to C++`
- Errors appeared when table names from JDBC metadata were pushed into Qt controls.

### Root Cause

- Some DB table-name normalization paths used `.strip()` directly on JPype `java.lang.String` objects.
- Those values were then passed to Qt APIs (`addItems`, `QInputDialog.getItem`) without first coercing to Python `str`.

### Final Resolution

- Forced Python string coercion at these UI boundaries:
    - DB connection dialog table list population: `names = [str(name).strip() ...]`
    - Main window import/export table prompts: `table_names = [str(t).strip() ...]`
- This guarantees all Qt-bound list values are native Python strings.

### Lessons Learned

- Any JDBC/JPype value used in Qt widgets should be normalized with `str(...)` at the last mile before UI calls.

## 2026-06-12 - Fix False "No Users to Import" When Mapping Preview Shows Data

### Problem

- Import could show sample data in mapping dialog, but then abort with "No users to import.".
- This happened even when `username` appeared present in the preview table.

### Root Cause

- `_convert_rows_to_users(...)` used strict source-key lookups against streamed DB rows.
- Some drivers/sources changed key case or key style between sample metadata and streamed batches (for example `USERNAME` vs `username`, `name_given` vs `name.given`).
- Result: mapped values were not found, users were classified as skipped, and import list became empty.

### Final Resolution

- Added resilient source-key lookup in `_convert_rows_to_users(...)`:
    - Case-insensitive key matching
    - Dotted/underscore variant fallback
    - Consistent source token trimming
- Also normalize mapped target tokens with `.strip()` before assignment.

### Validation

- Offscreen runtime test with mixed key formats now maps users correctly:
    - `USERNAME` and `UserName` map to `username`
    - `name_given` maps to `name.given`
    - Missing usernames are still correctly reported as skipped

## 2026-06-12 - Ensure "No Users to Import" Always Shows Mapping Diagnostics

### Problem

- Status-bar diagnostics could be missed in some UI states, making root cause unclear when import aborted with "No users to import.".

### Final Resolution

- Extended `_perform_import_sequence(...)` to accept `debug_stats` and include diagnostics directly in the "No users to import." dialog.
- Added connection log writes for zero-user conversion outcomes:
    - summary line (`Row mapping: total=..., mapped=..., skipped=...`)
    - sampled skipped-row reasons
- Wired `debug_stats` through all import call sites that use `_convert_rows_to_users(...)`.

### Result

- Even if transient status labels are not visible, mapping diagnostics are now visible in modal dialog and persisted in `connection_errors.log`.

## 2026-06-12 - Fix All-Rows "missing username" from DB Key Format Variants

### Problem

- Import diagnostics showed:
    - `Row mapping: total=50, mapped=0, skipped=50 (missing username: 50)`
- Mapping UI looked correct, but streamed row keys did not match selected source key format.

### Final Resolution

- Hardened source-key matching in `_convert_rows_to_users(...)` with:
    - trimmed-key aliases (`" username "` -> `"username"`)
    - case-insensitive matching
    - tokenized matching ignoring non-alphanumeric separators (`[User Name]`, `user_name`, `USERNAME` all match `username`)
- Added extra no-users diagnostics (`username_key_samples`) to show observed row keys for first skipped rows.

### Validation

- Offscreen runtime test now maps usernames from keys like `[User Name]` and ` user_name ` successfully.

## 2026-06-12 - Auto-Derive Username for HR Tables Without Username Column

### Problem

- Diagnostic output showed mapped=0/skipped=50 with reason `missing username`.
- Observed row keys contained HR-style fields (`EmployeeID`, `LastName`, `FirstName`, etc.) but no explicit username column.

### Final Resolution

- Added username fallback derivation in `_convert_rows_to_users(...)` when mapped username is missing/blank.
- Fallback sources (in order) include common identity keys:
    - `username`, `userId`, `userPrincipalName`, `sAMAccountName`, `login`, `uid`, `employeeId`, `employeeNumber`, `mail`, `email`
- Added diagnostics:
    - `derived_username` count in row-mapping summary
    - sampled derived usernames in popup/log

### Validation

- Offscreen runtime test with keys like `EmployeeID` now maps users successfully and derives usernames (for example `1001`, `1002`).

## 2026-06-12 - Fix Custom Query Input Box Wider Than Screen

### Problem

- The custom SQL query input could open wider than the screen, especially with long single-line saved queries.

### Root Cause

- `QInputDialog.getMultiLineText(...)` sizing behavior can expand poorly with long unwrapped text content.

### Final Resolution

- Replaced direct `getMultiLineText` usage with a custom helper dialog:
    - `_prompt_bounded_multiline_text(...)`
    - Uses `QTextEdit` in `NoWrap` mode (horizontal scroll instead of window growth)
    - Clamps dialog size to available screen geometry and sets a maximum size
- Applied to both custom SQL query prompt and custom LDAP filter prompt.

### Result

- Query/filter input dialogs remain within screen bounds across long text inputs.

### Enhancement

- Added dialog size persistence so the custom query/filter input window reopens at the last user-resized size.
- Size is stored per active profile under profile `dialog_sizes` and restored on next open.
- Restored size is still clamped to current screen bounds for safety.

### Follow-up Fix

- The saved query/filter *selection* prompt still used `QInputDialog.getItem(...)`, which could expand wider than screen when options contained long one-line text.
- Replaced it with a bounded custom picker dialog that:
    - truncates displayed labels while preserving full selected value
    - stores/restores picker size per profile
    - clamps picker to screen bounds

## 2026-06-12 - Fix MySQL JDBC Setup Message Showing Raw CSS/Markdown

### Problem

- MySQL import connection failures could display raw text like `p, li { white-space: pre-wrap; }` and markdown markers instead of readable setup guidance.

### Root Cause

- The error/help path relied on `QMessageBox` rich-text rendering heuristics.
- Some message content arrived in a document/export-like format, which Qt displayed literally and poorly.

### Final Resolution

- Replaced `_show_copyable_message(...)` message-box rendering with a custom bounded dialog using:
    - `QTextBrowser` for rich help content
    - `QPlainTextEdit` for plain text
- Hardened `_format_driver_error(...)` to sanitize:
    - raw Qt CSS export fragments
    - markdown-style links
    - markdown emphasis markers

## 2026-07-23 - Fix Export DB NameError for remove_btn

### Problem

- Exporting to database could fail with a runtime error: `name 'remove_btn' is not defined`.

### Root Cause

- In the database connection picker UI (`_choose_db_connection`), the code connected `remove_btn.clicked` but never created or added `remove_btn` in that dialog block.

### Final Resolution

- Added the missing Remove button construction and inserted it into the action row:
    - `remove_btn = QtWidgets.QPushButton("Remove")`
    - `action_row.addWidget(remove_btn)`
- Existing remove-handler wiring now binds correctly and no NameError occurs.

### Lessons Learned

- When copying parallel dialog patterns (DB and LDAP), verify all action buttons are instantiated before signal connections to avoid runtime NameErrors.

## 2026-07-23 - Add Touch ID Support for Vault Password Prompts on macOS

### Problem

- On macOS, credential save/load could trigger a generic keyring "vault password" prompt instead of native Keychain auth.
- Users requested Touch ID support when this prompt appears.

### Root Cause

- Keyring backend selection could fall back to a non-macOS backend (for example encrypted-file/vault style backend), which does not use native Keychain Touch ID flows.

### Final Resolution

- Added keyring backend detection/metadata during startup.
- On macOS, the app now explicitly prefers the native `keyring.backends.macOS.Keyring` backend.
- Added runtime status fields:
    - `KEYRING_BACKEND_NAME`
    - `KEYRING_TOUCH_ID_SUPPORTED`
- Updated startup warning and About dialog to surface backend and Touch ID capability status.

### Lessons Learned

- On macOS, Touch ID support depends on using the native Keychain backend; backend introspection and explicit selection prevent silent fallback to vault-style prompts.

## 2026-07-23 - Fix 401 invalid_client When Secret Not Loaded From Keychain

### Problem

- Connect/Test could fail with `401 Unauthorized` and `invalid_client` even though profile credentials were previously saved.
- In these failures, users also reported no keychain password/Touch ID prompt.

### Root Cause

- Keyring reads used a single username format (`profile_name`), but existing saved secrets can exist under alternate naming (`profile_name_client_secret`).
- When lookup missed the stored secret, `cl_sec` remained blank and token calls were sent with an empty secret.

### Final Resolution

- Added keyring compatibility helpers to read/write/delete across both key formats:
    - raw profile name
    - suffixed profile name (`_client_secret`)
- Updated all keyring operations in profile save/load/manager/delete paths to use these helpers.
- Added a manual Connect/Test fallback: if secret field is blank, force keyring read before token request so macOS keychain auth (including Touch ID where available) can prompt.

### Lessons Learned

- Credential-store key naming must be stable and backward compatible; otherwise auth failures look like bad credentials instead of lookup mismatches.

## 2026-07-23 - Enforce Native macOS Keychain Path for Touch ID-Capable Prompts

### Problem

- Users could still see vault-password style prompts without Touch ID even after keyring-backend preference updates.

### Root Cause

- Python keyring backend selection can still vary by environment/config, and some backend paths do not use native macOS Keychain authentication UI.

### Final Resolution

- Added native macOS Keychain operations using the `security` CLI and routed secret read/write/delete helpers through this path first.
- Kept python-keyring as a compatibility fallback for non-macOS and edge cases.
- Updated startup/about diagnostics to reflect native Keychain CLI availability for Touch ID-capable prompts.

### Lessons Learned

- On macOS, direct Keychain access (`security`) is the most reliable way to avoid non-native vault prompts and preserve Touch ID-capable auth flows.

### Follow-up Hardening

- Observed that fallback reads could still hit non-native vault backends when native keychain had no stored item yet.
- Updated `_read_secret_from_keyring(...)` to return native-only results on macOS when `security` CLI is available (no fallback read).
- Added explicit Connect/Test guidance dialog when no native keychain secret exists, instructing user to enter secret and Save Profile once to seed native keychain.

## 2026-07-23 - Fix macOS Keychain Save Error -25244 During Profile Save

### Problem

- Saving profile secret could show: `Failed to save client secret to keyring: can't store password on keychain (-25244, 'unknown error')`.

### Root Cause

- After native keychain write attempt, code still executed secondary python-keyring write calls.
- In some local keychain/backend states, fallback write path throws `-25244` even when native write is the intended storage path.

### Final Resolution

- Added canonical keyring username helper (`_preferred_keyring_username`) for stable writes.
- Changed native macOS write helper to return `(ok, error_message)`.
- Updated `_write_secret_to_keyring(...)` logic:
    - On macOS with native keychain available, return immediately after successful native write.
    - Only attempt fallback backend write if native write fails.
    - Surface combined native/fallback error context when both fail.

### Lessons Learned

- On macOS, once native Keychain write succeeds, avoid redundant backend writes that can emit false-negative failures.

## 2026-07-23 - Add Explicit Touch ID Prompt for Interactive Secret Retrieval

### Problem

- Users still reported no Touch ID prompt during Connect/Test secret retrieval, despite native keychain routing.

### Root Cause

- Native keychain access alone does not guarantee a visible biometric prompt in all local keychain/backend states.
- Explicit biometric challenge via macOS LocalAuthentication was not being invoked before secret retrieval.

### Final Resolution

- Added optional LocalAuthentication integration (`pyobjc-framework-LocalAuthentication`) with runtime capability detection.
- Added `_request_touch_id_auth(...)` and wired interactive Connect/Test secret reads to require biometric/device-owner auth before keychain lookup.
- Added About/status visibility for LocalAuthentication availability and startup warning when LocalAuthentication support is missing.
- Added macOS-only dependency marker in `requirements.txt`.

### Lessons Learned

- For deterministic Touch ID UX, trigger LocalAuthentication explicitly in interactive flows rather than relying only on backend keychain prompt behavior.
- URLs remain clickable and `pip install ...` commands remain readable.

## 2026-06-12 - Prevent Repeated profiles.json Truncation (JSONDecodeError)

### Problem

- App intermittently failed on startup/profile load with:
    - `JSONDecodeError: Expecting property name enclosed in double quotes: line 292 column 35`
- [profiles.json](profiles.json) was observed truncated again at:
    - `"db_import_mapping": {`

### Root Cause

- Config was being written with direct `open(..., 'w')` + `json.dump(...)` across many code paths.
- If app/process was interrupted during write, file could be left partially written, resulting in invalid JSON.

### Final Resolution

- Repaired [profiles.json](profiles.json) tail to valid JSON structure.
- Added atomic config persistence in [ui/main_window.py](ui/main_window.py):
    - New helper `self._write_config(data)` writes to a temp file, `fsync`s, then `os.replace(...)`.
- Replaced all direct config writes in `MainWindow` (`open(self.config_file, 'w')`) with `self._write_config(...)`.

### Lessons Learned

- Critical app config should always use atomic writes to prevent corruption on interruption/crash.
- EOF truncation is a strong signal of non-atomic write paths.

## 2026-06-12 - Fix Qt _pythonToCppCopy Error During MSSQL Import Mapping

### Problem

- MSSQL connection succeeded, but import mapping UI failed with:
    - `_pythonToCppCopy: Cannot copy-convert ... (java.lang.String) to C++`
- Symptom appeared when opening/using database mapping controls after reading JDBC metadata.

### Root Cause

- `DatabaseMappingDialog` accepted raw JDBC/JPype values (`java.lang.String`) for:
    - `table_cols`
    - `pingone_attrs`
    - `sample_row` keys
- Those values were passed to Qt APIs such as `QComboBox.addItems()` / `setCurrentText()`, which require native Python `str` values in PySide6 bindings.

### Final Resolution

- Normalized all dialog UI-bound names to Python strings in [ui/dialogs.py](ui/dialogs.py):
    - `self.table_cols = [str(c) for c in (table_cols or [])]`
    - `self.pingone_attrs = [str(a) for a in (pingone_attrs or [])]`
    - `self.sample_row = {str(k): v for k, v in (sample_row or {}).items()}`
- Kept the rest of import mapping logic unchanged.

### Lessons Learned

- Any values originating from JDBC metadata should be converted at UI boundaries before being sent into Qt widgets.
- Centralizing conversion in dialog initialization is safer than ad-hoc conversions at each widget call site.

## 2026-06-12 - Fix Truncated profiles.json Causing JSONDecodeError

### Problem

- App failed while loading JSON config with:
    - `JSONDecodeError: Expecting property name enclosed in double quotes: line 292 column 35`
- Failure occurred during `json.load()` on profile configuration.

### Root Cause

- [profiles.json](profiles.json) was truncated mid-object at:
    - `"db_import_mapping": {`
- Missing closing content for the `mssql` connection section and final closing braces for the root document.

### Final Resolution

- Repaired [profiles.json](profiles.json) by completing the truncated section with safe defaults:
    - `"db_import_mapping": {}`
    - `"db_import_mappings_by_query": {}`
    - `"db_export_mapping": {}`
- Added missing closing braces for `mssql`, `db_connections`, and root JSON object.
- Validated with `python -c` JSON parse check and workspace error scan.

### Lessons Learned

- Partial writes to config files can leave JSON structurally invalid and block app startup paths.
- On load failures with precise line/column, inspect the file tail first; truncation at EOF is a common cause.
- Consider future hardening: write config atomically via temp file + rename.

## 2026-06-12 - Fix QTableWidgetItem Constructor Calls with Java String Objects

### Problem

- PySide6 `QTableWidgetItem.__init__()` raised type error: called with `java.lang.String` instead of Python `str`
- Error occurred when displaying database import mappings with data from JDBC queries
- Multiple UI code paths instantiate `QTableWidgetItem` with column names and attribute values from database sources

### Root Cause

- JDBC column discovery and sample data processing return Java String objects in lists and dictionaries
- PySide6's `QTableWidgetItem` constructor is strict about types—it requires Python `str`, not Java String objects
- The following code paths were affected:
  - `dialogs.py:369,371`: Creating table items from attribute key/value pairs from JDBC
  - `dialogs.py:2502`: Creating items from database column names
  - `dialogs.py:2516`: Creating items from column values  
  - `dialogs.py:2552`: Creating items from attribute names
  - `dialogs.py:3019`: Creating items from attribute names in LDF/CSV preview

### Final Resolution

Added `str()` conversion around all variables passed to `QTableWidgetItem()` constructor when sourced from JDBC operations:
1. `dialogs.py:369`: `str(key)` instead of `key`
2. `dialogs.py:371`: `str(value)` instead of `value`
3. `dialogs.py:2502`: `str(col)` in f-string display name
4. `dialogs.py:2516`: `str(val)` instead of `val`
5. `dialogs.py:2552`: `str(attr)` instead of `attr`
6. `dialogs.py:3019`: `str(attr)` instead of `attr`

### Before/After Snippets

#### Before (dialogs.py:369)
```python
for row, (key, value) in enumerate(all_attrs):
    key_item = QtWidgets.QTableWidgetItem(key)  # Crashes if key is Java String
    value_item = QtWidgets.QTableWidgetItem(value)  # Crashes if value is Java String
```

#### After (dialogs.py:369)
```python
for row, (key, value) in enumerate(all_attrs):
    key_item = QtWidgets.QTableWidgetItem(str(key))  # Safe
    value_item = QtWidgets.QTableWidgetItem(str(value))  # Safe
```

#### Before (dialogs.py:2502)
```python
display_name = f"{col} ({phone_type})" if is_phone and phone_type else col
src_item = QtWidgets.QTableWidgetItem(display_name)  # col is Java String
```

#### After (dialogs.py:2502)
```python
display_name = f"{str(col)} ({phone_type})" if is_phone and phone_type else str(col)
src_item = QtWidgets.QTableWidgetItem(display_name)  # Safe
```

### Lessons Learned

- PySide6 widget constructors require Python native types, not JPype/Java equivalents
- Always convert JDBC-sourced strings to Python `str` before passing to widget constructors
- This pattern applies to all Qt widgets that expect string arguments (QTableWidgetItem, QLabel, QLineEdit, etc.)
- Pattern: `str(variable_from_jdbc)` before constructing any PySide6 widget with it

## 2026-06-12 - Fix Java String .lower() Calls in Database Import Flows

### Problem

- Database column mapping dialog crashed with: `'java.lang.string' object has no attribute 'lower'`
- Occurred in `_expand_phone_numbers()` and LDAP/database entry processing
- Multiple `.lower()` calls on variables that could be Java String objects from JDBC queries

### Root Cause

- JDBC database queries return Python lists with Java String objects as column names and dictionary keys
- Several code paths called `.lower()` directly on these Java strings without converting to Python strings first:
  - `dialogs.py:2583`: `col.lower() == 'phonenumbers'`
  - `main_window.py:3100`: `k.lower() != 'dn'` in LDAP attributes discovery
  - `main_window.py:3173`: `rdn_attr.lower()` in RDN aliases lookup  
  - `main_window.py:7070`: `key.lower()` in entry attribute processing

### Final Resolution

Added defensive `str()` conversion before all `.lower()` calls on variables from JDBC sources:
1. `dialogs.py:2583`: `str(col).lower()` instead of `col.lower()`
2. `main_window.py:3100`: `str(k).lower()` instead of `k.lower()`
3. `main_window.py:3173`: `str(rdn_attr).lower()` instead of `rdn_attr.lower()`
4. `main_window.py:7070`: `str(key).lower()` instead of `key.lower()`

### Before/After Snippets

#### Before (dialogs.py)
```python
def _expand_phone_numbers(self, table_cols: List[str], sample_row: Optional[dict]):
    for col in table_cols:
        if col.lower() == 'phonenumbers':  # Crashes if col is Java String
```

#### After (dialogs.py)
```python
def _expand_phone_numbers(self, table_cols: List[str], sample_row: Optional[dict]):
    for col in table_cols:
        if str(col).lower() == 'phonenumbers':  # Safe for Java strings
```

#### Before (main_window.py:3100)
```python
ldap_attrs = sorted(set(ldap_attrs).union({k for k in sample_entry.keys() if k and k.lower() != 'dn'}))
```

#### After (main_window.py:3100)
```python
ldap_attrs = sorted(set(ldap_attrs).union({k for k in sample_entry.keys() if k and str(k).lower() != 'dn'}))
```

### Lessons Learned

- All string method calls (`.lower()`, `.strip()`, `.startswith()`) on variables from JDBC data paths must use defensive `str()` conversion
- Pattern: When iterating over dict keys from JDBC sources, assume they might be Java objects
- Check both database column lists and dictionary keys from JDBC query results
- Test database import flows with tables that have non-standard column names (all uppercase, mixed case, special chars)

## 2026-06-12 - Fix Java String Object Error in User Import Error Handling

### Problem

- User import worker crashed with: `'java.lang.string' object has no attribute 'lower'`
- This occurred when processing HTTPStatusError responses (409 conflicts) from PingOne during bulk import.

### Root Cause

- Line 816 in `workers.py` had a typo: `cont = str(e)` instead of `err_text = str(e)`
- This caused the subsequent call to `self._is_existing_user_error(err_text)` to use an undefined/stale `err_text` variable from an outer scope
- If that variable held a Java String object from a prior JDBC operation, the `.lower()` call in `_is_existing_user_error()` would fail

### Final Resolution

1. Fixed typo: changed `cont = str(e)` → `err_text = str(e)` on line 816
2. Added defensive `str()` conversion in `_is_existing_user_error()` method to handle any Java objects gracefully

### Before/After Snippets

#### Before

```python
# Line 816: typo causes undefined err_text
except Exception as retry_err:
    err_msg = f"User {username or uname}: Rate limit retry failed: {retry_err}"
    errors.append(err_msg)
    if api_client.API_LOGGING_ENABLED:
        api_client.api_logger.error(err_msg)
cont = str(e)  # BUG: typo, should be err_text
if self._is_existing_user_error(err_text):  # Uses stale/undefined err_text

def _is_existing_user_error(self, err_text: str) -> bool:
    txt = (err_text or "").lower()  # Fails if err_text is Java String
```

#### After

```python
# Line 816: fixed typo
except Exception as retry_err:
    err_msg = f"User {username or uname}: Rate limit retry failed: {retry_err}"
    errors.append(err_msg)
    if api_client.API_LOGGING_ENABLED:
        api_client.api_logger.error(err_msg)
err_text = str(e)  # Fixed: correct variable name
if self._is_existing_user_error(err_text):  # Now has correct err_text

def _is_existing_user_error(self, err_text: str) -> bool:
    txt = str(err_text or "").lower()  # Defensive: converts Java objects to Python strings
```

### Lessons Learned

- Typos in error handling paths can silently propagate to cause cryptic downstream errors
- Always add defensive `str()` conversions when calling string methods on objects that might be JPype Java types
- Error handling code paths should be tested with rate limit scenarios to catch variable name issues

## 2026-06-12 - Suppress Repeated macOS Java Runtime Console Messages

### Problem

- App/terminal still showed repeated macOS runtime text:
    - "Unable to locate a Java Runtime."
- This appeared even after user-facing Java setup guidance was added.

### Root Cause

- `_raw_connect()` still invoked `jpype.getDefaultJVMPath()` without a quiet macOS precheck.
- That path can emit OS-level Java discovery messages before Python exception handling runs.

### Final Resolution

- Added `_ensure_java_home_macos_quiet()` helper in `api/db_utils.py`.
- Reused this helper in both startup preflight (`get_java_runtime_status`) and JDBC connect path (`_raw_connect`) to short-circuit before JPype JVM path discovery when Java is missing.

### Before/After Snippets

#### Before

```python
jpype.startJVM(
        jpype.getDefaultJVMPath(),
        "--enable-native-access=ALL-UNNAMED",
        classpath=[self._jar_path],
)
```

#### After

```python
if not _ensure_java_home_macos_quiet():
        raise RuntimeError(_get_java_runtime_error_details())
```

### Lessons Learned

- Quiet dependency checks should be shared across startup and runtime call paths to prevent repeated OS-level noise and inconsistent behavior.

## 2026-06-12 - Add Startup Java/JDBC Preflight Warning

### Problem

- Java/JDBC setup problems were only discovered when running a database action.
- Users requested a warning once at launch when Java is missing or undiscoverable.

### Root Cause

- There was no startup preflight check for Java runtime discovery.

### Final Resolution

- Added `get_java_runtime_status()` to `api/db_utils.py` for non-invasive JVM-path discovery.
- Added `_show_java_startup_warning()` in `ui/main_window.py` and invoked it during window initialization.
- Warning uses non-modal status messaging to avoid startup modal side effects.

### Before/After Snippets

#### Before

```python
self._show_keyring_startup_warning()
```

#### After

```python
self._show_keyring_startup_warning()
self._show_java_startup_warning()
```

### Lessons Learned

- Dependency preflight checks at startup reduce time-to-diagnosis and avoid deferred runtime failures.

## 2026-06-12 - macOS java_home Lookup Failure During JDBC Connect

### Problem

- Database operations surfaced: `Command '['/usr/libexec/java_home']' returned non-zero exit status 1.`

### Root Cause

- JPype/JDBC JVM discovery failed when no usable JDK was discoverable via macOS `java_home`.
- The bootstrap exception path was treated as best-effort and the raw discovery failure later leaked through connection handling.

### Final Resolution

- Added explicit detection for `java_home` discovery failures in `api/db_utils.py`.
- Added a user-facing runtime error with concrete remediation steps (`brew install openjdk`, set `JAVA_HOME`, restart app) instead of exposing raw subprocess exception text.

### Before/After Snippets

#### Before

```python
except Exception:
    # Best effort only
    pass
```

#### After

```python
except Exception as exc:
    jvm_bootstrap_error = str(exc)

...

if _is_java_home_discovery_error(msg) or _is_java_home_discovery_error(jvm_bootstrap_error):
    raise RuntimeError(_get_java_runtime_error_details()) from exc
```

### Lessons Learned

- JVM bootstrap failures should be normalized into actionable setup guidance early, especially on macOS where `java_home` discovery is common.

## 2026-06-12 - macOS Keychain Read Could Freeze Profile Loading

### Problem

- Selecting a profile could hang the UI while reading the client secret from keyring.
- Stack trace showed blocking inside macOS keychain lookup (`SecItemCopyMatching`) during `load_selected_profile()`.

### Root Cause

- `keyring.get_password(...)` was called synchronously on the main Qt UI thread.
- When macOS keychain access blocked (prompt/wait), the UI event loop stalled.

### Attempted Solutions

- Confirmed existing cache and read-attempt guards reduced repeated prompts but did not prevent first-read blocking.
- Verified startup auto-connect path to avoid introducing a regression when secret loading becomes asynchronous.

### Final Resolution

- Moved keyring secret reads to a background daemon thread via `_start_secret_read()`.
- Added in-flight read tracking (`self._secret_read_inflight`) to avoid duplicate concurrent reads.
- Added `secret_read_completed` Qt signal to safely apply loaded secrets on the UI thread.
- Updated startup auto-connect to wait briefly for secret-read completion using `_connect_when_secret_ready(...)` before attempting token retrieval.

### Before/After Snippets

#### Before

```python
secret = keyring.get_password("pingone_usermanager", name) or ""
self._cache_secret(name, secret)
```

#### After

```python
secret = ""
self._start_secret_read(name)

# background thread -> UI signal callback
self.secret_read_completed.emit(profile_name, secret)
```

### Lessons Learned

- Secure-store calls must not run on the UI thread in desktop apps; even reliable backends can block unpredictably.
- Async credential loading should include in-flight coordination and startup retry logic to preserve expected auto-connect behavior.

## 2026-06-11 - Startup Runtime Warnings (JPype Native Access + macOS modalSession)

### Problem

- App startup output included Java warning from JPype/native access and macOS modal warning:
    - `Use --enable-native-access=ALL-UNNAMED...`
    - `modalSession has been exited prematurely...`
- Startup also printed development debug lines for menu creation.

### Root Cause

- JVM was started without explicit native-access opt-in on modern JDKs.
- Startup auto-connect failure showed a modal `QMessageBox` during launch path, which can cause Cocoa modal-session warnings.
- Debug `print(...)` statements were left in `init_ui()`.

### Final Resolution

- Added `_ensure_jdk_native_access_option()` in `api/db_utils.py` and invoked it before first JDBC connect.
- Explicitly start JPype JVM with `--enable-native-access=ALL-UNNAMED` in `api/db_utils.py` when JVM is not already running (reliable for embedded JNI startup).
- Changed startup auto-connect call to `connect_only(interactive=False)` so launch failures update status without modal popup.
- Kept manual connect behavior unchanged (`interactive=True`) so explicit user actions still show modal errors.
- Removed Settings/Help menu debug `print(...)` lines.

### Before/After Snippets

#### Before

```python
QtCore.QTimer.singleShot(250, self.connect_only)
...
QtWidgets.QMessageBox.critical(self, "Connect", "Auth Failed. Check credentials.")
```

#### After

```python
QtCore.QTimer.singleShot(250, lambda: self.connect_only(interactive=False))
...
if interactive:
        QtWidgets.QMessageBox.critical(self, "Connect", "Auth Failed. Check credentials.")
```

### Lessons Learned

- Startup/background validation paths should avoid modal dialogs; reserve blocking UI for direct user-triggered actions.

## 2026-06-11 - MSSQL TLS Failure With Legacy Encrypt Mode Values

### Problem

- MSSQL connections failed with: `"encrypt" property is set to "true" ... (unexpected_message)`.
- Some saved connections still used legacy truthy encrypt values and were treated as strict TLS.

### Root Cause

- `_normalize_encrypt_mode()` mapped truthy values like `true/yes/1` to `on`.
- For servers/endpoints that do not complete TLS handshake, strict mode prevented fallback and surfaced the SQLServerException.

### Final Resolution

- Updated encryption normalization in `api/db_utils.py` so legacy boolean/truthy values map to `auto` (secure-first with fallback).
- Kept explicit strict behavior for `on|required|strict` only.

### Before/After Snippets

#### Before

```python
if raw in ('on', 'true', 'yes', '1', 'required'):
    return 'on'
```

#### After

```python
if isinstance(encrypt_mode, bool):
    return 'auto' if encrypt_mode else 'off'
if raw in ('on', 'required', 'strict'):
    return 'on'
if raw in ('true', 'yes', '1', 'enabled'):
    return 'auto'
```

### Lessons Learned

- Migrations from implicit flags to explicit security modes need compatibility mapping to avoid unexpected strictness.

## 2026-06-11 - Keychain Prompt Repeated On Every Profile Change

### Problem
- Profile switching could still trigger a macOS keychain authentication prompt repeatedly in the same app session.

### Root Cause
- Secret reads only used in-memory cache hits to skip keyring access.
- When a keyring read failed/was denied for a profile, that profile was not marked as attempted, so switching back retried `keyring.get_password(...)` and prompted again.

### Final Resolution
- Added session-level tracking for keyring read attempts (`self._secret_read_attempted`).
- Updated `load_selected_profile()` to attempt keyring read at most once per profile key variant per session.
- Kept cache/delete behavior coherent by clearing attempt markers when a profile secret cache is cleared.

### Before/After Snippets

#### Before
```python
if cached_secret is None:
    secret = keyring.get_password("pingone_usermanager", name) or ""
    self._cache_secret(name, secret)
```

#### After
```python
if cached_secret is None:
    if self._was_secret_read_attempted(name):
        secret = ""
    else:
        try:
            secret = keyring.get_password("pingone_usermanager", name) or ""
            self._cache_secret(name, secret)
        finally:
            self._mark_secret_read_attempted(name)
```

### Lessons Learned
- Preventing repeated secure-store prompts requires caching both successful reads and failed/denied attempts.

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
- The database connection dialog tooltip did not match the approved two-option MSSQL setup guidance.

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
- The app mixed JDBC and non-JDBC database paths (pymysql/pymssql), and Oracle was not supported.
- Documentation and prerequisites did not consistently reflect a JDBC-only model across supported databases.

### Root Cause
- Database engine creation in `api/db_utils.py` had fallback paths for Python DBAPI drivers.
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
    raise ImportError("pymssql not installed")
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

## 2026-06-11 - Duplicate Keychain Prompt Still Occurred On Profile Switch

### Problem
- Switching profiles could still trigger two macOS Keychain prompts even after the startup duplicate-load fix.

### Root Cause
- The profile selector was connected through the generic overloaded `currentIndexChanged` signal on `QComboBox`, which could invoke `load_selected_profile()` more than once.
- Two profile-manager flows also did `setCurrentIndex(...)` and then manually called `load_selected_profile()` again.

### Final Resolution
- Bound the profile selector to `currentIndexChanged[int]` explicitly.
- Removed redundant `load_selected_profile()` calls immediately after `setCurrentIndex(...)` in profile-manager code paths.

### Before/After Snippets

#### Before
```python
self.profile_list.currentIndexChanged.connect(self.load_selected_profile)
```

#### After
```python
self.profile_list.currentIndexChanged[int].connect(self.load_selected_profile)
```

### Lessons Learned
- When Qt widgets expose overloaded signals, bind the specific overload needed or side effects may fire more than once.

## 2026-06-11 - JDBC Class Not Found Error Diagnostics

### Problem
- Database connection failures showed `Class com.microsoft.sqlserver.jdbc.SQLServerDriver is not found` without clearly identifying the jar path being used.

### Root Cause
- Driver path handling passed the raw path through without explicit path resolution checks.
- Class-not-found exceptions from jaydebeapi did not include actionable context in app-facing errors.

### Final Resolution
- Added `_resolve_driver_jar_path()` to resolve relative paths against current working directory and project root and fail fast with checked paths.
- Enhanced JDBC connect exception handling to emit explicit class + jar-path diagnostics for class-not-found cases.

### Before/After Snippets

#### Before
```python
return jaydebeapi.connect(self._driver_class, self._jdbc_url, [self._user, self._password], self._jar_path)
```

#### After
```python
try:
    return jaydebeapi.connect(...)
except Exception as exc:
    if "Class" in str(exc) and "is not found" in str(exc):
        raise RuntimeError(
            f"JDBC driver class '{self._driver_class}' was not found using jar '{self._jar_path}'. ..."
        ) from exc
```

### Lessons Learned
- JDBC errors should always include both expected driver class and effective jar path to speed up root-cause diagnosis.

## 2026-06-11 - MSSQL JDBC Class Not Found Despite Correct Jar Path

### Problem
- User selected the correct MSSQL jar path, but connection still failed with `Class com.microsoft.sqlserver.jdbc.SQLServerDriver is not found`.

### Root Cause
- The JVM can already be running in the app process from an earlier JDBC operation. In that case, the active classpath may not include the newly selected vendor jar unless explicitly added.

### Final Resolution
- In `_JDBCEngine._raw_connect()`, add best-effort `jpype.addClassPath(self._jar_path)` when `jpype.isJVMStarted()` is true before calling `jaydebeapi.connect(...)`.

### Before/After Snippets

#### Before
```python
return jaydebeapi.connect(self._driver_class, self._jdbc_url, [self._user, self._password], self._jar_path)
```

#### After
```python
if jpype.isJVMStarted():
    jpype.addClassPath(self._jar_path)
return jaydebeapi.connect(...)
```

### Lessons Learned
- With JPype/jaydebeapi, JVM lifecycle and classpath state are process-wide; switching DB drivers needs explicit classpath management.

## 2026-06-11 - MSSQL JDBC SSL Handshake Failure (unexpected_message)

### Problem
- MSSQL JDBC connect failed with:
  `"encrypt" property is set to "true" ... could not establish a secure connection ... (unexpected_message)`.

### Root Cause
- JDBC URL for MSSQL enforced `encrypt=true` by default. Some SQL Server endpoints/listeners in the field do not complete TLS negotiation as expected.

### Final Resolution
- Added targeted fallback for MSSQL: if TLS handshake error is detected, retry once with `encrypt=false`.
- Kept primary behavior unchanged (`encrypt=true;trustServerCertificate=true`) for secure-first compatibility.

### Before/After Snippets

#### Before
```python
url = "...;encrypt=true;trustServerCertificate=true"
return connect(url)
```

#### After
```python
try:
    return connect(secure_url)
except Exception as exc:
    if is_ssl_handshake_error(exc):
        return connect(insecure_url)
    raise
```

### Lessons Learned
- For broad SQL Server compatibility, secure-by-default plus explicit fallback provides better resilience than a single hardcoded encryption mode.

## 2026-06-11 - MSSQL Encrypt Mode Needed User-Controlled TLS Behavior

### Problem
- Connection attempts still failed against some SQL Server endpoints with SSL handshake errors.
- Existing behavior only used an internal fallback, but users needed explicit control per saved connection.

### Root Cause
- Encryption behavior was hardcoded in JDBC URL assembly and not configurable from the UI/profile.
- DB utility call paths from import/export/metadata operations did not carry encryption preference.

### Final Resolution
- Added **Encrypt Mode** in `DatabaseConnectionDialog` with values `Auto`, `On`, and `Off`.
- Persisted `encrypt_mode` in saved DB connection definitions.
- Extended `api/db_utils.py` engine and all public helpers to accept `encrypt_mode` and apply MSSQL URL policy:
    - `On`: `encrypt=true;trustServerCertificate=true` (no fallback)
    - `Off`: `encrypt=false`
    - `Auto`: secure-first with one fallback retry to `encrypt=false` on recognized TLS handshake failures
- Propagated `encrypt_mode` through all `ui/main_window.py` db_utils call sites.

### Before/After Snippets

#### Before
```python
self._jdbc_url = "...;encrypt=true;trustServerCertificate=true"
ok, err = db_utils.test_connection(..., conn.get('driver'))
```

#### After
```python
mode = _normalize_encrypt_mode(encrypt_mode)
if mode == 'off':
        self._jdbc_url = "...;encrypt=false"
ok, err = db_utils.test_connection(..., conn.get('driver'), encrypt_mode=conn.get('encrypt_mode'))
```

### Lessons Learned
- Transport/security toggles that impact connectivity must be explicit per connection profile, not implicit in backend-only fallback logic.

## 2026-07-27 - macOS Keychain ACL Updated to Allow All Applications (Reduce Password Prompts)

### Problem
- Users received Touch ID prompts and separate Keychain password prompts when reading saved client secrets.
- Per-application Keychain ACL checks could trigger additional authorization prompts in some launch paths.

### Root Cause
- Keychain items were saved without explicit "allow all applications" ACL.
- Existing item ACL behavior could require a separate Keychain authorization step depending on requesting executable context.

### Final Resolution
- Updated native macOS keychain write path to include `-A` on `security add-generic-password`.
- Kept `-U` so existing items are updated in place when profile secrets are re-saved.
- Added `KEYCHAIN_ALLOW_ALL_APPS = True` to make behavior explicit in code.

### Before/After Snippets

#### Before
```python
["security", "add-generic-password", "-U", "-s", KEYRING_SERVICE, "-a", username, "-w", secret or ""]
```

#### After
```python
cmd = ["security", "add-generic-password", "-U"]
if KEYCHAIN_ALLOW_ALL_APPS:
    cmd.append("-A")
cmd.extend(["-s", KEYRING_SERVICE, "-a", username, "-w", secret or ""])
```

### Lessons Learned
- macOS Keychain ACL behavior can differ by calling executable even when the item/service is the same.
- `-A` can reduce prompt friction but broadens access scope; use only when this tradeoff is acceptable.
