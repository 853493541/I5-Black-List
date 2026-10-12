"""What the app is called, and what its files are called.

The app was 黑名单检测 until v0.4.2. A folder unzipped before then keeps its old file names
when it updates itself (an older copy only accepts update files under the names it knows), so
everything that looks for the launcher or the app's process takes either name, new first.
"""

from __future__ import annotations

from pathlib import Path

APP_NAME = "模仿者小工具"
# The launcher a friend double-clicks, beside runtime\ and blacklist_detect\.
LAUNCHERS = ("模仿者小工具.exe", "黑名单检测.exe")
# The app's own process in runtime\: pythonw.exe with the app's name and icon.
PROCESSES = ("模仿者小工具.exe", "I5黑名单.exe")


def launcher_in(root: Path) -> Path | None:
    """The launcher in this folder, under whichever name it has."""
    for name in LAUNCHERS:
        if (root / name).is_file():
            return root / name
    return None
