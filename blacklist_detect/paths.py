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


def instance_key() -> str:
    """One name per Windows user, so a second copy (or the local installer) can find the first.

    On Windows, Qt's QLocalServer serves it as a named pipe of the same name.
    """
    import getpass
    import hashlib

    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    return "BlackListDetect-" + hashlib.sha1(user.encode("utf-8")).hexdigest()[:12]


def message_running_copy(message: bytes, key: str | None = None) -> bool:
    """Send b"show" or b"quit" to the copy that is open. False when none is open.

    Plain file I/O on the named pipe, so the local installer needs no Qt.
    """
    if sys.platform != "win32":
        return False
    pipe = "\\\\.\\pipe\\" + (key or instance_key())
    try:
        with open(pipe, "wb", buffering=0) as handle:
            handle.write(message)
    except OSError:
        return False
    return True
