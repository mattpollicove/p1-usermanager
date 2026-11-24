"""Version management for PingOne User Manager."""

from pathlib import Path


def get_version_file() -> Path:
    """Get path to version.txt file."""
    return Path(__file__).parent.parent / "version.txt"


def read_version() -> str:
    """Read current version from version.txt file.
    
    Returns:
        Version string (e.g., "0.840")
    """
    version_file = get_version_file()
    if version_file.exists():
        try:
            return version_file.read_text().strip()
        except Exception:
            return "0.840"
    return "0.840"


def bump_version() -> str:
    """Increment version by 0.001 and save to file.
    
    Returns:
        New version string
    """
    current = read_version()
    
    try:
        # Parse current version as float
        version_num = float(current)
        # Increment by 0.001
        new_version_num = version_num + 0.001
        # Round to 3 decimal places to avoid floating point errors
        new_version_num = round(new_version_num, 3)
        new_version = str(new_version_num)
    except (ValueError, TypeError):
        # If parsing fails, reset to 0.841
        new_version = "0.841"
    
    # Write new version to file
    version_file = get_version_file()
    version_file.write_text(new_version + "\n")
    
    return new_version


def get_version_string() -> str:
    """Get formatted version string for display.
    
    Returns:
        Formatted string like "v0.840"
    """
    return f"v{read_version()}"
