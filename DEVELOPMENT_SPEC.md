# PingOne UserManager - Development Specification

**Version:** 0.6  
**Last Updated:** February 3, 2026  
**Status:** Active Development

---

## 1. Executive Summary

PingOne UserManager is a cross-platform desktop application for managing PingOne identity environments. Built with Python and Qt (PySide6), it provides IT administrators with a robust GUI for user management, bulk operations, and environment configuration across multiple profiles.

### Core Purpose
- Simplify PingOne user administration through a native desktop interface
- Enable bulk operations (create, update, delete) with visual feedback
- Support multiple environment profiles with secure credential storage
- Provide flexible data import/export capabilities (CSV, LDIF)

### Target Users
- IT administrators managing PingOne environments
- DevOps teams working across Dev/Staging/Production environments
- Identity management professionals requiring bulk user operations

---

## 2. Architecture Overview

### 2.1 Application Structure

```
p1-usermanager/
├── app.py                    # Application entry point
├── api/
│   ├── __init__.py
│   └── client.py            # HTTP client, token management, logging
├── ui/
│   ├── __init__.py
│   ├── main_window.py       # Main application window (2968 lines)
│   ├── dialogs.py           # Reusable dialog components (1263 lines)
│   └── themes.py            # Theme management (light/dark modes)
├── workers.py               # Background worker tasks (QRunnable)
├── profiles.json            # Profile configurations storage
├── user_schema.json         # JSON schema for user validation
├── requirements.txt         # Python dependencies
├── README.md                # User documentation
├── CHANGELOG.md             # Version history
└── DEVELOPMENT_RULES.md     # Development guidelines
```

### 2.2 Technology Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **GUI Framework** | PySide6 (Qt for Python) | 6.x | Cross-platform native UI |
| **HTTP Client** | httpx | Latest | Async HTTP operations |
| **Credential Storage** | keyring | Latest | OS-native secure storage |
| **Language** | Python | 3.9+ | Application logic |
| **Threading** | QThreadPool + QRunnable | Qt built-in | Non-blocking operations |
| **Async Runtime** | asyncio | Python stdlib | Async HTTP operations |

### 2.3 Design Patterns

#### Non-Blocking Worker Pattern
- All API calls execute in background threads via `QRunnable` workers
- UI remains responsive during network operations
- Workers emit Qt signals (`finished`, `progress`, `error`) to update UI
- Dedicated thread pool manages concurrent operations

#### Signal-Slot Architecture
- Qt's signal-slot mechanism handles UI updates
- Loose coupling between workers and UI components
- Type-safe event handling with `QtCore.Signal`

#### Separation of Concerns
- **api/client.py**: HTTP communication, authentication, logging
- **workers.py**: Background task execution, API calls
- **ui/main_window.py**: UI layout, event handling, state management
- **ui/dialogs.py**: Reusable modal dialogs
- **ui/themes.py**: Theme/appearance management

---

## 3. Core Components

### 3.1 Application Entry Point (app.py)

**Purpose:** Minimal entry point that bootstraps the Qt application

**Responsibilities:**
- Create `QApplication` instance
- Instantiate `MainWindow`
- Register cleanup handlers (`app.aboutToQuit`)
- Return application exit code

**Key Code:**
```python
def run_app():
    app = QtWidgets.QApplication([])
    window = MainWindow()
    app.aboutToQuit.connect(api_client.close_async_client)
    window.show()
    return app.exec()
```

### 3.2 API Client (api/client.py)

**Purpose:** Centralized HTTP client for PingOne API interactions

**Key Features:**
- **Token Management**: Caches OAuth2 tokens with expiration tracking
- **Connection Logging**: Writes API calls to `connection_errors.log`
- **Credential Logging**: Tracks auth events in `credentials.log` (no secrets)
- **API Call Logging**: Optional detailed logging to `api_calls.log`
- **Live Capture**: In-memory event capture for UI display

**Main Class:**
```python
class PingOneClient:
    def __init__(self, env_id, client_id, client_secret):
        self.env_id = env_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.token_expiry = None
        self.base_url = f"https://api.pingone.com/v1/environments/{env_id}"
```

**Critical Methods:**
- `get_token()`: Obtains/refreshes OAuth2 access token
- `get_users()`: Fetches paginated user list
- `update_user()`: PATCH request to modify user attributes
- `delete_user()`: DELETE request to remove user
- `create_user()`: POST request to create new user

**Logging Configuration:**
- `API_LOGGING_ENABLED`: Global toggle for detailed API logging
- `CREDENTIALS_LOGGING_ENABLED`: Toggle for auth event logging
- `LIVE_CAPTURE_ENABLED`: Toggle for in-memory event capture

### 3.3 Background Workers (workers.py)

**Purpose:** Execute API operations in background threads without blocking UI

**Base Pattern:**
```python
class WorkerSignals(QtCore.QObject):
    finished = QtCore.Signal(dict)
    progress = QtCore.Signal(int, int)
    error = QtCore.Signal(str)

class SomeWorker(QtCore.QRunnable):
    def __init__(self, client, params):
        super().__init__()
        self.client = client
        self.signals = WorkerSignals()
    
    @QtCore.Slot()
    def run(self):
        asyncio.run(self.execute())
    
    async def execute(self):
        # Perform async HTTP operations
        # Emit signals to update UI
```

**Worker Classes:**

| Worker | Purpose | Signals Emitted |
|--------|---------|----------------|
| `UserFetchWorker` | Fetch all users + populations | `finished(users, pop_map)` |
| `BulkDeleteWorker` | Delete multiple users | `progress(current, total)`, `finished` |
| `UserUpdateWorker` | Update single user | `finished`, `error` |
| `BulkCreateWorker` | Create/update users from import | `progress`, `finished` |

### 3.4 Main Window (ui/main_window.py)

**Purpose:** Primary application window containing all UI components

**Key Attributes:**
```python
APP_VERSION = "0.6"
self.threadpool = QtCore.QThreadPool()
self.users_cache = []           # Current user list
self.pop_map = {}               # Population ID -> Name mapping
self.selected_columns = [...]   # Active columns for table
self.default_columns = ['id', 'name.given', 'name.family', 'email', 'population.name']
self.theme_manager = ThemeManager()
```

**UI Sections:**

1. **Menu Bar**
   - File: New Profile, Manage Profiles, Exit
   - Settings: Dark Mode, Select Columns, Revert to Defaults, Toggle API Logging
   - Logs: Show Logs, Reset Log, Clear All, Archive Logs
   - Help: Configuration Help, User Management Help, About

2. **Configuration Tab**
   - Profile selector dropdown
   - Environment ID, Client ID, Client Secret fields
   - Save Profile, Connect & Sync, Test Connection buttons

3. **User Management Tab**
   - Toolbar: Refresh, Import CSV/LDIF, Export CSV/LDIF, Columns, Delete Selected
   - User table (QTableWidget) with sortable columns
   - Status bar: Profile name, API call counter, operation status

**Critical Methods:**
- `load_selected_profile()`: Loads profile from `profiles.json`
- `save_profile()`: Persists profile configuration (credentials to keyring)
- `connect_and_sync()`: Initiates connection and user fetch
- `refresh_table()`: Reloads user data from cache, optimized with `setRowCount()`
- `on_fetch_success()`: Handles worker completion, populates table
- `delete_selected_users()`: Bulk delete with confirmation dialog
- `save_columns_to_config()`: Persists column selection per-profile

**Performance Optimizations:**
- Disable sorting during bulk table updates: `setSortingEnabled(False)`
- Use `setRowCount()` for bulk row allocation instead of `insertRow()` in loop
- Create list copies when loading profile to avoid shared references
- Batch table updates to reduce paint events

### 3.5 Dialogs (ui/dialogs.py)

**Purpose:** Reusable modal dialogs for specific tasks

**Dialog Classes:**

| Dialog | Purpose | Key Features |
|--------|---------|--------------|
| `EditUserDialog` | Edit single user attributes | Form layout with validation |
| `ColumnSelectDialog` | Select table columns | Checkboxes, Select All, Clear All, Reset to Defaults |
| `JSONViewDialog` | View/edit JSON attributes | Syntax highlighting, formatted display |
| `TextViewDialog` | View log file contents | Read-only text display |
| `AttributeMappingDialog` | Map CSV/LDIF to PingOne attributes | Dropdown mapping, remember preferences |
| `ExportOptionsDialog` | Configure export options | All/selected users, all/visible columns |
| `NewProfileDialog` | Create new profile | Credential entry, show/hide secret toggle |
| `ProfileManagerDialog` | Manage saved profiles | List profiles, delete, create new, test connection |

**Design Principles:**
- DPI-aware sizing with `scale_size()` helper
- Platform detection for cross-platform optimization
- Parent window reference for callbacks
- Modal dialogs with accept/reject buttons

### 3.6 Theme Manager (ui/themes.py)

**Purpose:** Manage application themes (light/dark modes)

**Features:**
- Light theme: System default palette
- Dark theme: Custom palette with #353535 base color
- Theme persistence in `profiles.json` (__meta__ section)
- Per-theme button styling for visual consistency

**Usage:**
```python
theme_manager = ThemeManager()
theme_manager.set_theme(ThemeManager.DARK, qapp_instance)
current = theme_manager.get_current_theme()  # "light" or "dark"
```

---

## 4. Data Management

### 4.1 Profile Storage (profiles.json)

**Structure:**
```json
{
  "profile_name": {
    "env_id": "environment-uuid",
    "client_id": "client-uuid",
    "columns": ["id", "username", "email", ...],
    "column_widths": {"id": 100, "username": 150, ...},
    "import_mapping": {"Header": "pingone.attribute"},
    "export_preferences": {
      "scope": "all|selected",
      "columns": "all|visible",
      "remember": true
    }
  },
  "__meta__": {
    "theme": "light|dark",
    "last_working_profile": "profile_name",
    "auto_connect_last": true|false
  }
}
```

**Key Points:**
- Client secrets stored in OS keyring, NOT in profiles.json
- Column configurations are per-profile (isolated)
- Import/export preferences saved per-profile when "Remember" checked
- Metadata section for global app settings

### 4.2 Credential Storage (keyring)

**Security Model:**
- Service name: `"pingone_usermanager"`
- Username: `"{profile_name}_client_secret"`
- Value: Encrypted client secret

**Platform Backends:**
- macOS: Keychain
- Windows: Credential Manager
- Linux: Secret Service (GNOME Keyring, KWallet)

**Usage:**
```python
import keyring
keyring.set_password("pingone_usermanager", f"{profile}_client_secret", secret)
secret = keyring.get_password("pingone_usermanager", f"{profile}_client_secret")
keyring.delete_password("pingone_usermanager", f"{profile}_client_secret")
```

### 4.3 User Data Cache

**In-Memory Storage:**
- `self.users_cache`: List of user dictionaries from API
- `self.pop_map`: Dictionary mapping population IDs to names
- Updated on each fetch/sync operation
- Table displays subset based on `selected_columns`

**Data Flow:**
1. Worker fetches users from API
2. Worker emits `finished` signal with user data
3. `on_fetch_success()` updates cache and refreshes table
4. Table displays cached data filtered by selected columns

---

## 5. Feature Specifications

### 5.1 Multi-Profile Management

**Requirements:**
- Support unlimited named profiles
- Each profile stores independent configuration
- Prevent deletion of active profile
- Visual profile switcher in configuration tab

**Implementation:**
- Dropdown in config tab populates from `profiles.json` keys
- Profile change triggers `load_selected_profile()`
- Profile Manager dialog shows all profiles with metadata
- Delete button removes profile from JSON and keyring

**User Flows:**

*Create New Profile:*
1. File → Manage Profiles → New Profile
2. Enter profile name and credentials
3. Optional: Test connection before saving
4. Profile saved to `profiles.json`, secret to keyring

*Switch Profile:*
1. Select profile from dropdown in config tab
2. Credentials and settings auto-load
3. Click "Connect & Sync" to fetch users

*Delete Profile:*
1. File → Manage Profiles
2. Select profile (not active)
3. Click Delete → Confirm
4. Profile removed from JSON and keyring

### 5.2 Column Management

**Default Columns:**
- UUID (`id`)
- First Name (`name.given`)
- Last Name (`name.family`)
- Email (`email`)
- Population (`population.name`)

**Features:**
- Per-profile column selection
- Persistent column widths per-profile
- Select All, Clear All, Reset to Defaults buttons
- Columns displayed in default order when defaults applied

**Implementation:**
```python
# Default columns defined in MainWindow.__init__
self.default_columns = ['id', 'name.given', 'name.family', 'email', 'population.name']

# Saved per-profile in profiles.json
profile_config["columns"] = list(self.selected_columns)

# Loaded with list copy to avoid shared references
self.selected_columns = list(config.get('columns', self.default_columns))
```

**User Flows:**

*Select Columns:*
1. Settings → Select Columns (Cmd/Ctrl+K)
2. Check/uncheck desired columns
3. Optional: Select All, Clear All, Reset to Defaults
4. Click OK
5. Columns saved to profile, table refreshes

*Revert to Defaults:*
1. Settings → Revert to Default Columns
2. Table resets to default 5 columns
3. Selection saved to profile

### 5.3 User Import (CSV/LDIF)

**Supported Formats:**
- CSV with header row
- LDIF (RFC 2849)

**Required Fields:**
- `username`
- `email`
- `name.given` (first name)
- `name.family` (last name)

**Optional Fields:**
- Address fields (street, city, state, zip, country)
- Phone numbers
- Population assignment

**Import Process:**
1. Click "Import CSV" or "Import LDIF"
2. Select file via file picker
3. Mapping dialog appears:
   - Map file headers to PingOne attributes
   - Set population for all users
   - Toggle "enabled" status
   - Optional: Remember mapping for profile
4. Validation (if `jsonschema` installed)
5. Background worker creates/updates users
6. Progress dialog shows status
7. Results dialog shows success/failure counts

**Duplicate Handling:**
- Username comparison is case-insensitive and trimmed
- Existing users are updated (PATCH) instead of created (POST)
- Prevents duplicate user creation

**Validation:**
- Local JSON schema validation (optional)
- Server-side validation on create/update
- Error messages surfaced to user

### 5.4 User Export (CSV/LDIF)

**Export Options:**
- Scope: All users or selected rows only
- Columns: All columns or visible columns only
- Remember preferences per-profile

**Export Process:**
1. Click "Export CSV" or "Export LDIF"
2. Options dialog appears (if not remembered)
3. Select file save location
4. Export executes synchronously
5. Success message with file path

**CSV Format:**
- Header row with column names
- Nested attributes flattened (e.g., `name.given`)
- UTF-8 encoding

**LDIF Format:**
- RFC 2849 compliant
- DN: `cn={username}, ou=users`
- Common attributes mapped to LDAP schema
- Base64 encoding for non-ASCII values

### 5.5 Bulk Operations

**Delete:**
- Select multiple rows (Ctrl+Click, Shift+Click, Cmd+A)
- Click "Delete Selected" or right-click context menu
- Confirmation dialog with count
- Progress dialog during deletion
- BulkDeleteWorker handles sequential deletes

**Create:**
- Import CSV/LDIF (see User Import)
- BulkCreateWorker handles batched creates
- Progress updates in real-time

**Update:**
- Future enhancement (not yet implemented)
- Would use BulkUpdateWorker pattern

### 5.6 Dark Mode

**Implementation:**
- ThemeManager class with light/dark palettes
- Toggle via Settings → Dark Mode (Cmd+D / Ctrl+D)
- Theme persisted in `profiles.json` (__meta__.theme)
- Applied on startup if saved

**Color Scheme (Dark):**
- Background: #353535 (dark gray)
- Base: #232323 (darker gray for input fields)
- Text: #FFFFFF (white)
- Highlight: #2A82DA (blue)
- Disabled: #7F7F7F (medium gray)

**User Flow:**
1. Settings → Dark Mode (or Cmd+D / Ctrl+D)
2. Theme switches immediately
3. Preference saved to profiles.json
4. Applied automatically on next launch

---

## 6. API Integration

### 6.1 PingOne API Endpoints

| Operation | Method | Endpoint | Purpose |
|-----------|--------|----------|---------|
| **Auth** | POST | `/token` | Obtain OAuth2 access token |
| **Populations** | GET | `/environments/{envId}/populations` | List populations |
| **Users** | GET | `/environments/{envId}/users` | List users (paginated) |
| **User Detail** | GET | `/environments/{envId}/users/{userId}` | Get single user |
| **Create User** | POST | `/environments/{envId}/users` | Create new user |
| **Update User** | PATCH | `/environments/{envId}/users/{userId}` | Update user attributes |
| **Delete User** | DELETE | `/environments/{envId}/users/{userId}` | Delete user |

### 6.2 Authentication Flow

```
1. Client sends POST to /as/token.oauth2
   - grant_type: client_credentials
   - client_id: {client_id}
   - client_secret: {client_secret}

2. Server responds with:
   - access_token: {jwt_token}
   - expires_in: 3600 (seconds)
   - token_type: "Bearer"

3. Client caches token and expiry timestamp
4. Subsequent requests include header:
   - Authorization: Bearer {access_token}

5. Token refresh when expired:
   - Check if current time >= token_expiry
   - If expired, repeat step 1
```

### 6.3 Pagination

**Pattern:**
```json
{
  "_embedded": {
    "users": [ ... ]
  },
  "_links": {
    "next": {
      "href": "https://api.pingone.com/v1/environments/{envId}/users?limit=100&cursor={cursor}"
    }
  }
}
```

**Implementation:**
```python
all_users = []
url = f"{base_url}/users"
while url:
    resp = await session.get(url, headers=headers)
    data = resp.json()
    all_users.extend(data.get("_embedded", {}).get("users", []))
    url = data.get("_links", {}).get("next", {}).get("href")
```

### 6.4 Error Handling

**HTTP Status Codes:**
- 200: Success
- 201: Created
- 204: No Content (delete success)
- 400: Bad Request (validation error)
- 401: Unauthorized (invalid token)
- 403: Forbidden (insufficient permissions)
- 404: Not Found (user doesn't exist)
- 429: Too Many Requests (rate limit)
- 500: Internal Server Error

**Error Propagation:**
1. Worker catches exceptions during API calls
2. Worker emits `error` signal with message
3. MainWindow displays error dialog to user
4. Error logged to `connection_errors.log`

---

## 7. User Interface Guidelines

### 7.1 Platform Compatibility

**Supported Platforms:**
- macOS 10.14+
- Windows 10+
- Linux (Ubuntu 20.04+, Fedora 34+)

**Platform Detection:**
```python
IS_MACOS = platform.system() == 'Darwin'
IS_WINDOWS = platform.system() == 'Windows'
IS_LINUX = platform.system() == 'Linux'

SHORTCUT_MODIFIER = QtCore.Qt.KeyboardModifier.MetaModifier if IS_MACOS else QtCore.Qt.KeyboardModifier.ControlModifier
```

### 7.2 DPI Awareness

**Scaling Strategy:**
```python
def get_dpi_scale():
    screen = QtWidgets.QApplication.primaryScreen()
    return screen.devicePixelRatio() if screen else 1.0

def scale_size(base_size, dpi_scale=None):
    if dpi_scale is None:
        dpi_scale = get_dpi_scale()
    return int(base_size * max(1.0, dpi_scale * 0.8))
```

**Window Sizing:**
- Initial size: 75% of screen dimensions
- Minimum size: 800x600 (scaled by DPI)
- Window centered on screen
- Dialogs sized proportionally to screen DPI

### 7.3 Keyboard Shortcuts

| Action | macOS | Windows/Linux |
|--------|-------|---------------|
| **Dark Mode** | Cmd+D | Ctrl+D |
| **Select Columns** | Cmd+K | Ctrl+K |
| **Refresh** | Cmd+R | Ctrl+R |
| **Select All** | Cmd+A | Ctrl+A |
| **Delete** | Cmd+Delete | Delete |
| **Manage Profiles** | Cmd+Shift+M | Ctrl+Shift+M |
| **Quit** | Cmd+Q | Ctrl+Q |

### 7.4 Accessibility

**Current State:**
- Standard Qt accessibility via QAccessible
- Keyboard navigation for all controls
- Tab order follows logical flow
- Focus indicators visible

**Future Enhancements:**
- Screen reader labels for all controls
- High contrast mode support
- Configurable font sizes
- ARIA labels for complex widgets

---

## 8. Logging and Debugging

### 8.1 Log Files

| File | Purpose | Content |
|------|---------|---------|
| `api_calls.log` | Detailed API logging | Request/response details when enabled |
| `connection_errors.log` | Connection events | Auth attempts, API call summaries |
| `credentials.log` | Auth events | Token requests/responses (no secrets) |

### 8.2 Logging Controls

**Runtime Toggles:**
- Settings → Show API calls in status bar
- Enables `api_client.API_LOGGING_ENABLED`
- Shows call counter in status bar
- Writes detailed logs to `api_calls.log`

**Log Management:**
- Logs → Show Log Files: View logs in dialog
- Logs → Reset Log: Clear single log file
- Logs → Clear All Logs: Empty all log files
- Logs → Archive Logs: Create timestamped ZIP archive

### 8.3 Live Capture

**Purpose:** In-memory event capture for UI display

**API:**
```python
api_client.enable_live_capture(True)
events = api_client.get_and_clear_live_events()
# Returns: ["2026-02-03T12:34:56Z GET /users - 200"]
```

**Usage:**
- Profile Manager connection testing
- Real-time debugging without file I/O

---

## 9. Testing Strategy

### 9.1 Manual Testing

**Test Scenarios:**

1. **Profile Management**
   - Create profile with valid credentials
   - Create profile with invalid credentials
   - Switch between profiles
   - Delete profile
   - Attempt to delete active profile (should fail)

2. **User Operations**
   - Fetch users (small dataset < 100)
   - Fetch users (large dataset > 1000)
   - Edit single user
   - Delete single user
   - Bulk delete (10, 100, 1000 users)

3. **Import/Export**
   - Import CSV with valid data
   - Import CSV with invalid data
   - Import LDIF with valid data
   - Export CSV (all users, all columns)
   - Export CSV (selected users, visible columns)
   - Export LDIF

4. **Column Management**
   - Select columns
   - Revert to defaults
   - Resize columns (widths persist)
   - Switch profile (columns reset to profile config)

5. **Theme Management**
   - Toggle dark mode
   - Restart app (theme persists)
   - Switch profile (theme persists across profiles)

### 9.2 Automated Testing

**Future Implementation:**
- Unit tests for api_client functions
- Integration tests for worker completion
- UI tests with pytest-qt
- Mock API responses for deterministic tests

**Proposed Structure:**
```
tests/
├── unit/
│   ├── test_api_client.py
│   ├── test_workers.py
│   └── test_dialogs.py
├── integration/
│   ├── test_profile_management.py
│   ├── test_user_operations.py
│   └── test_import_export.py
└── fixtures/
    ├── sample_users.json
    ├── sample_profiles.json
    └── mock_responses.py
```

---

## 10. Performance Considerations

### 10.1 Optimizations

**Table Population:**
- Disable sorting during bulk updates: `setSortingEnabled(False)`
- Use `setRowCount(len(users))` instead of `insertRow()` in loop
- Batch table updates to reduce paint events
- Re-enable sorting after population complete

**Memory Management:**
- Create list copies when loading profiles: `list(config.get('columns'))`
- Avoid shared references between profiles
- Clear cache on profile switch

**Network Operations:**
- Async HTTP with httpx
- Connection pooling via AsyncClient
- Timeout configuration (10 seconds default)
- Pagination for large datasets

### 10.2 Scalability Limits

**Current Tested Limits:**
- Users: 10,000+ (tested with pagination)
- Profiles: Unlimited (JSON file storage)
- Columns: 50+ (all user attributes)
- Bulk Delete: 1000+ users

**Known Bottlenecks:**
- Table rendering with > 5000 rows (Qt limitation)
- Bulk operations without progress feedback
- Synchronous export operations

**Future Improvements:**
- Virtual scrolling for large datasets
- Async export with progress dialog
- Database backend for user cache (SQLite)
- Incremental table updates instead of full refresh

---

## 11. Security Considerations

### 11.1 Credential Handling

**Best Practices:**
- Client secrets stored in OS keyring (encrypted)
- Secrets never logged to files
- Secrets masked in UI (password field)
- Secrets cleared from memory after use

**Vulnerabilities:**
- Profiles.json readable by user (contains env_id, client_id)
- No encryption for profiles.json
- Access tokens cached in memory

**Recommendations:**
- Add profile encryption option
- Implement token rotation
- Add session timeout
- Support SSO/SAML authentication

### 11.2 Data Privacy

**Current State:**
- User data cached in memory (plain text)
- No data encryption at rest
- Export files unencrypted
- Logs may contain user identifiers (UUIDs)

**Recommendations:**
- Add export encryption option
- Implement data anonymization for logs
- Add GDPR compliance features (data export/delete)

---

## 12. Dependencies

### 12.1 Core Dependencies

```
pyside6       # Qt bindings for Python
httpx         # Async HTTP client
keyring       # OS credential storage
```

### 12.2 Optional Dependencies

```
jsonschema    # JSON schema validation for imports
```

### 12.3 Development Dependencies (Future)

```
pytest        # Testing framework
pytest-qt     # Qt testing utilities
black         # Code formatting
pylint        # Code linting
mypy          # Static type checking
```

---

## 13. Build and Distribution

### 13.1 Current Distribution

**Manual Installation:**
1. Clone repository
2. Create virtual environment
3. Install dependencies via pip
4. Run `python app.py`

### 13.2 Future Distribution Options

**Standalone Executables:**
- **PyInstaller**: Bundle Python + dependencies into single executable
- **cx_Freeze**: Cross-platform freezing tool
- **Nuitka**: Python-to-C compiler for native executables

**Platform-Specific Packaging:**
- macOS: .app bundle, .dmg installer
- Windows: .exe installer (NSIS, Inno Setup)
- Linux: .deb, .rpm, AppImage, Snap, Flatpak

**Build Configuration (PyInstaller example):**
```python
# app.spec
a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('user_schema.json', '.'),
        ('README.md', '.'),
    ],
    hiddenimports=['keyring.backends'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='UserManager',
    icon='icon.ico',
    debug=False,
    strip=False,
    upx=True,
    console=False,
)
# macOS
app = BUNDLE(exe, name='UserManager.app', icon='icon.icns')
```

---

## 14. Version History

### v0.6 (February 2, 2026)
- Added dark mode with persistence
- Profile Manager with CRUD operations
- Per-profile column configurations
- Column dialog enhancements (Select All, Clear All, Reset)
- Performance optimizations for table operations
- Status bar shows profile name and notifications
- Comprehensive documentation updates

### v0.5 (Prior Releases)
- Multi-profile support
- CSV/LDIF import/export
- Bulk operations
- Attribute mapping dialog
- JSON schema validation

### v0.1 - v0.4
- Initial development
- Basic CRUD operations
- PingOne API integration

---

## 15. Future Enhancements

### 15.1 Planned Features

**Short-term (Next Release):**
- [ ] Automated testing suite
- [ ] User search/filter functionality
- [ ] Column sorting persistence
- [ ] Undo/redo for user edits
- [ ] Export format templates

**Medium-term (Next 3 Months):**
- [ ] Role-based access control
- [ ] Audit log viewer
- [ ] Scheduled sync operations
- [ ] Multi-environment comparison view
- [ ] Batch update operations

**Long-term (6+ Months):**
- [ ] Plugin architecture
- [ ] Custom attribute definitions
- [ ] Workflow automation
- [ ] Reporting dashboard
- [ ] Web interface option

### 15.2 Known Issues

1. **Table Performance**: Rendering slows with > 5000 users
   - **Workaround**: Use filters/search to reduce visible rows
   - **Fix**: Implement virtual scrolling

2. **Export Blocking**: Large exports freeze UI
   - **Workaround**: Export smaller subsets
   - **Fix**: Make export async with progress dialog

3. **Import Errors**: Unclear error messages for validation failures
   - **Workaround**: Check logs for details
   - **Fix**: Improve error messages, add line numbers

4. **Profile Switching**: Table doesn't clear when switching profiles
   - **Workaround**: Click Refresh after switching
   - **Fix**: Auto-clear table on profile change

---

## 16. Development Workflow

### 16.1 Code Style

**Python Style Guide:**
- Follow PEP 8
- Line length: 120 characters
- Docstrings: Google style
- Type hints: Encouraged for public APIs

**Qt/UI Conventions:**
- Widget names: `camelCase` (Qt convention)
- Signal names: `snake_case` (Python convention)
- Slot methods: Prefix with `on_` (e.g., `on_button_clicked`)

### 16.2 Git Workflow

**Branch Strategy:**
- `main`: Stable releases
- `develop`: Active development
- `feature/*`: Feature branches
- `bugfix/*`: Bug fix branches

**Commit Messages:**
```
type(scope): Short description

Longer description if needed

Fixes #123
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### 16.3 Release Process

1. Update version in `ui/main_window.py` (`APP_VERSION`)
2. Update version in `README.md`
3. Add entry to `CHANGELOG.md`
4. Update `DEVELOPMENT_RULES.md` if needed
5. Tag release: `git tag v0.X.Y`
6. Build distributables (if applicable)
7. Create GitHub release with notes

---

## 17. API Reference

### 17.1 Main Window Public API

```python
class MainWindow(QtWidgets.QMainWindow):
    def load_selected_profile() -> None:
        """Load profile from dropdown, populate UI fields."""
    
    def save_profile() -> None:
        """Save current profile to JSON, secret to keyring."""
    
    def connect_and_sync() -> None:
        """Authenticate and fetch users from PingOne."""
    
    def refresh_table() -> None:
        """Repopulate table from users_cache."""
    
    def delete_selected_users() -> None:
        """Delete selected rows with confirmation."""
    
    def save_columns_to_config(show_notification: bool = False) -> None:
        """Persist selected_columns to profile config."""
```

### 17.2 API Client Public API

```python
class PingOneClient:
    async def get_token() -> Optional[str]:
        """Obtain or refresh OAuth2 access token."""
    
    async def get_users() -> List[dict]:
        """Fetch all users with pagination."""
    
    async def update_user(user_id: str, data: dict) -> dict:
        """PATCH user with delta attributes."""
    
    async def delete_user(user_id: str) -> bool:
        """DELETE user by ID."""
    
    async def create_user(data: dict) -> dict:
        """POST new user."""
```

### 17.3 Worker Signals API

```python
class WorkerSignals(QtCore.QObject):
    finished = QtCore.Signal(dict)        # {"users": [...], "pop_map": {...}}
    progress = QtCore.Signal(int, int)    # (current, total)
    error = QtCore.Signal(str)            # "Error message"
```

---

## 18. Glossary

| Term | Definition |
|------|------------|
| **Environment** | PingOne tenant/workspace containing users and populations |
| **Population** | User group within an environment |
| **Profile** | Saved configuration for a PingOne environment |
| **Worker** | Background thread task (QRunnable) |
| **Delta Patch** | HTTP PATCH with only changed attributes |
| **Keyring** | OS-native secure credential storage |
| **DPI** | Dots Per Inch - screen resolution metric |
| **LDIF** | LDAP Data Interchange Format (RFC 2849) |
| **UUID** | Universally Unique Identifier (user ID) |

---

## 19. Contact and Support

**Repository:** https://github.com/mattpollicove/p1-usermanager  
**Issues:** Use GitHub Issues for bug reports and feature requests  
**Discussions:** Use GitHub Discussions for questions and community support  

**Maintainer:** Matt Pollicove  
**License:** See LICENSE file

---

## 20. Appendix

### A. Sample User Schema

See `user_schema.json` in repository root for complete JSON schema.

### B. Sample Profiles Configuration

```json
{
  "Development": {
    "env_id": "12345678-1234-1234-1234-123456789abc",
    "client_id": "abcdef12-3456-7890-abcd-ef1234567890",
    "columns": ["id", "username", "email", "name.given", "name.family"],
    "column_widths": {"id": 250, "username": 150, "email": 200}
  },
  "Production": {
    "env_id": "87654321-4321-4321-4321-210987654321",
    "client_id": "fedcba09-8765-4321-fedc-ba0987654321",
    "columns": ["id", "email", "name.given", "name.family", "population.name"],
    "column_widths": {"id": 250, "email": 200}
  },
  "__meta__": {
    "theme": "dark",
    "last_working_profile": "Development",
    "auto_connect_last": true
  }
}
```

### C. Environment Variables

Currently not used. Future consideration for configuration:
- `PINGONE_ENV_ID`
- `PINGONE_CLIENT_ID`
- `PINGONE_CLIENT_SECRET`
- `PINGONE_LOG_LEVEL`

### D. File Locations

**Configuration:**
- Profiles: `./profiles.json` (current directory)
- User schema: `./user_schema.json`

**Logs:**
- API calls: `./api_calls.log`
- Connection: `./connection_errors.log`
- Credentials: `./credentials.log`

**Exports:**
- User-specified via file picker
- Default: Current directory

---

**End of Development Specification**
