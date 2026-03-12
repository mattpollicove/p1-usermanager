"""Compatibility entrypoint expected by README and VS Code launch configs.

This thin shim imports and runs `run_app()` from `app.py` so scripts
or IDE launch configurations that expect `usermanager.py` continue to work.
"""

from app import run_app


if __name__ == "__main__":
    raise SystemExit(run_app())
