"""开机自动启动: start with Windows, quietly, in the tray.

Windows runs whatever is listed under the user's Run key at sign-in. The entry
points at the 黑名单检测.exe this copy was started from, with --background, so
the app comes up in the tray instead of opening its window over the desktop.
Only the current user's key is touched; nothing needs administrator rights.
"""

from __future__ import annotations

import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "BlackListDetect"
EXE_NAME = "黑名单检测.exe"
BACKGROUND = "--background"


def launcher() -> Path | None:
    """The 黑名单检测.exe beside this copy of the app, or None when run from source."""
    exe = Path(__file__).resolve().parent.parent / EXE_NAME
    return exe if exe.is_file() else None


def available() -> bool:
    return sys.platform == "win32" and launcher() is not None


def command() -> str:
    exe = launcher()
    return f'"{exe}" {BACKGROUND}' if exe is not None else ""


def _read() -> str:
    if sys.platform != "win32":
        return ""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, VALUE_NAME)
            return str(value)
    except OSError:
        return ""


def is_enabled() -> bool:
    return bool(_read())


def set_enabled(enabled: bool) -> bool:
    """Add or remove the Run entry. Returns False when it could not be changed."""
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                text = command()
                if not text:
                    return False
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, text)
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def refresh() -> None:
    """After the app moved or was reinstalled elsewhere, point an existing entry at this copy."""
    current = _read()
    if current and available() and current != command():
        set_enabled(True)
