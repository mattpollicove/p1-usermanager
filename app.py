"""Small app entrypoint that starts the Qt event loop and shows the main window.

Keeping the runner minimal makes it easy to import `run_app()` from tests
or other scripts without side-effects.
"""

import sys
import os
from pathlib import Path

# Suppress macOS Java Runtime warning that appears during ldap3 import
# The warning comes from system-level LDAP libraries and doesn't affect functionality
_stderr_backup = sys.stderr

class _SilentStderr:
    """Silently drops Java Runtime warning lines while passing through everything else."""
    def __init__(self):
        self.real_stderr = sys.stderr
        self.buffer = ""
    
    def write(self, s):
        self.buffer += s
        # Check for complete lines
        lines = self.buffer.split('\n')
        for line in lines[:-1]:  # All complete lines
            # Skip Java Runtime warning
            if "Unable to locate a Java" not in line and \
               "visit http://www.java.com" not in line and \
               "The operation couldn't be completed" not in line:
                self.real_stderr.write(line + '\n')
        self.buffer = lines[-1]  # Keep incomplete line in buffer
    
    def flush(self):
        if self.buffer.strip() and \
           "Unable to locate a Java" not in self.buffer and \
           "visit http://www.java.com" not in self.buffer and \
           "The operation couldn't be completed" not in self.buffer:
            self.real_stderr.write(self.buffer)
            self.buffer = ""
        self.real_stderr.flush()
    
    def __getattr__(self, name):
        return getattr(self.real_stderr, name)

sys.stderr = _SilentStderr()

# ensure SQLAlchemy is importable at startup; most database helpers rely on it
# this import is intentionally at the top so a missing dependency raises early
try:
    import sqlalchemy  # noqa: F401
except ModuleNotFoundError:
    # if someone runs the app without installing requirements, provide a clear
    # message rather than letting the first database operation crash.
    sys.stderr = _stderr_backup  # Restore stderr for error message
    raise

# Restore stderr after imports complete
sys.stderr = _stderr_backup

# Ensure project root is on sys.path when running app.py directly from the editor
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from PySide6 import QtWidgets
from ui.main_window import MainWindow
import api.client as api_client


def run_app():
    # Create the QApplication and show the main window; return the
    # application's exit status so callers can raise SystemExit.
    app = QtWidgets.QApplication([])
    app.setApplicationName("PingOne User Manager")
    app.setApplicationDisplayName("PingOne User Manager")
    window = MainWindow()
    # Ensure shared AsyncClient is closed when the application exits.
    app.aboutToQuit.connect(api_client.close_async_client)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_app())
