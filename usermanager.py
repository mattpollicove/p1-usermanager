import sys
from pathlib import Path

# Ensure project root is on sys.path when executed directly from the editor
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app import run_app

# Thin compatibility entrypoint preserved for users/scripts that run
# `python usermanager.py`. The heavy lifting lives in `app.py` and the
# UI/module packages created during the refactor.



if __name__ == "__main__":
    raise SystemExit(run_app())