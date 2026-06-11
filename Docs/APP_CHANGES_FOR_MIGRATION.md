# Application Changes for Migration

This document captures modifications to the application that also need to be
mirrored on other platforms (Windows, Linux, mobile clients, etc.) whenever
such changes are made. Each entry should include:

- **Date**: YYYY-MM-DD
- **Files changed**: list of paths
- **Platforms affected**: Windows, Linux, both, or others
- **Description**: what was changed (old -> new, include code snippets if helpful)
- **Notes**: any platform-specific considerations or remaining work

---

- **Date**: 2026-04-14
- **Files changed**: app.py
- **Platforms affected**: macOS, Windows, Linux
- **Description**: Set explicit Qt application naming at startup so native app/menu labels use the product name instead of the Python interpreter name.
  - Old:
    - `app = QtWidgets.QApplication([])`
  - New:
    - `app = QtWidgets.QApplication([])`
    - `app.setApplicationName("PingOne User Manager")`
    - `app.setApplicationDisplayName("PingOne User Manager")`
- **Notes**: On macOS this updates the menu-bar app title for script runs. Packaged app bundles should still define bundle metadata (`CFBundleName` / `CFBundleDisplayName`) for full consistency.

- **Date**: 2026-04-14
- **Files changed**: ui/main_window.py
- **Platforms affected**: macOS, Windows, Linux
- **Description**: Restored a dedicated Preferences entry that opens a Settings window, and kept Configuration Help only in the Help menu.
  - Old:
    - Configuration Help had been assigned the application-preferences shortcut/path.
    - Preference actions were exposed directly in a Preferences menu.
  - New:
    - `Preferences...` opens the dedicated settings dialog.
    - `Configuration Help` remains in the Help menu only.
    - Runtime preference controls live in the settings dialog instead of a separate Preferences menu.
- **Notes**: On macOS, `Preferences...` should use the application menu role. Other platforms will show the same dialog from the File menu unless later moved into a platform-specific menu layout.

- **Date**: 2026-06-11
- **Files changed**: INSTALL.md, README.md
- **Platforms affected**: macOS, Windows, Linux
- **Description**: Documented JDBC driver filesystem layout, vendor jar filenames, vendor download URLs, and local runtime setup details for JDBC database connectivity.
  - Old:
    - JDBC support was documented at a high level with vendor URLs only.
  - New:
    - Recommended repo layout:
      - `drivers/mssql/mssql-jdbc-13.4.0.jre11.jar`
      - `drivers/mysql/mysql-connector-j-9.0.0.jar`
      - `drivers/oracle/ojdbc11.jar`
    - Added macOS `JAVA_HOME` shell configuration example.
    - Added local verification commands for Java, JPype, and JDBC jar loading.
- **Notes**: The `JAVA_HOME` example is macOS/Homebrew-specific. Windows and Linux packaging or setup guides may need platform-native equivalents if local JVM discovery differs there.
