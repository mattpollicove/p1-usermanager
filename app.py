"""Small app entrypoint that starts the Qt event loop and shows the main window.

Keeping the runner minimal makes it easy to import `run_app()` from tests
or other scripts without side-effects.
"""

import sys
from pathlib import Path

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
    window = MainWindow()
    # Ensure shared AsyncClient is closed when the application exits.
    app.aboutToQuit.connect(api_client.close_async_client)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_app())
