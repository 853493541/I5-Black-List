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


def custom_sound_dir(root: Path | None = None) -> Path:
    """The player's own 场景 sounds, each converted once as it was added: in the app's folder (root, when
    the lists are kept elsewhere), apart from sounds/, whose quieter copies are dropped as new ones are made."""
    return (root or app_dir()) / "custom_sounds"


# OMP_NUM_THREADS as this copy found it when it started, before it dropped it (see __main__).
inherited_threads: str | None = None
# Set in this process for this process (the OCR's thread count, Intel OpenMP: its marker), wrong for a
# program it starts: inherited, Paddle's OMP_NUM_THREADS=1 left the OCR one core.
_NOT_INHERITED = ("OMP_NUM_THREADS",)
_NOT_INHERITED_PREFIX = "__KMP_REGISTERED_LIB_"


def ocr_threads(cores: int | None = None) -> str:
    """Threads the OCR reads names on: one per core, as Intel advises for oneDNN, 2 to 8. Unset, it took one per
    CPU: 12 on a 6-core laptop with hyperthreading, the whole CPU busy for a check and the game beside it slowed.
    Never 1, which read 5 times slower; past 8, a check beside a game got slower (docs/dev/research)."""
    return str(max(2, min(8, cores or physical_cores())))


def physical_cores() -> int:
    """Cores, not the CPUs Windows shows: a 6-core laptop with hyperthreading shows 12."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        size = wintypes.DWORD(0)
        get_info = ctypes.windll.kernel32.GetLogicalProcessorInformationEx
        get_info(0, None, ctypes.byref(size))  # 0: one record per core
        records = ctypes.create_string_buffer(size.value)
        if size.value and get_info(0, records, ctypes.byref(size)):
            count = offset = 0
            while offset < size.value:
                count += 1
                offset += int.from_bytes(records.raw[offset + 4:offset + 8], "little")  # each record's size
            return count
    return os.cpu_count() or 1


def child_env() -> dict[str, str]:
    """This process's environment for a program it starts, the next copy of the app above all."""
    return {
        key: value
        for key, value in os.environ.items()
        if key.upper() not in _NOT_INHERITED and not key.upper().startswith(_NOT_INHERITED_PREFIX)
    }


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
