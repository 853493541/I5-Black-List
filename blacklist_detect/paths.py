"""Where the blacklist and settings live on this PC."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def app_dir(platform: str | None = None, env: dict[str, str] | None = None) -> Path:
    """Windows: %APPDATA%\\BlackListDetect. Elsewhere: the XDG config dir."""
    system = platform or sys.platform
    values = env if env is not None else os.environ
    if system == "win32":
        base = values.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "BlackListDetect"
    base = values.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "BlackListDetect"
