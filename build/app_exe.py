"""The app's own process: runtime\\I5黑名单.exe, a copy of the runtime's pythonw.exe with its own name and icon.

Task Manager lists a process by its exe's description, and pythonw.exe says "Python": the app
showed as one Python among others, and a tool that ends every pythonw.exe ended it too. The copy
runs exactly as pythonw.exe does, since the embedded Python finds its library by python312.dll
beside it, not by the exe's name.

    python build/app_exe.py <runtime folder>     make or refresh the exe there
"""

from __future__ import annotations

import ctypes
import shutil
import sys
from ctypes import wintypes
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP_NAME = "I5黑名单"
APP_EXE = f"{APP_NAME}.exe"
ICON = REPO / "blacklist_detect" / "assets" / "app.ico"

_RT_ICON = 3
_RT_GROUP_ICON = 14
_RT_VERSION = 16
# pythonw.exe keeps its version and icons under US English. Writing ours under the same
# language replaces them; under another, Windows could still show "Python".
_LANG = 1033


def _version_numbers(version: str) -> tuple[int, int, int, int]:
    parts = [int(part) for part in version.lstrip("v").split(".") if part.isdigit()]
    return tuple((parts + [0, 0, 0, 0])[:4])  # type: ignore[return-value]


def _version_info(version: str) -> bytes:
    from PyInstaller.utils.win32 import versioninfo as vi

    numbers = _version_numbers(version)
    text = ".".join(str(part) for part in numbers[:3])
    strings = [
        vi.StringStruct("FileDescription", APP_NAME),
        vi.StringStruct("ProductName", APP_NAME),
        vi.StringStruct("InternalName", APP_NAME),
        vi.StringStruct("OriginalFilename", APP_EXE),
        vi.StringStruct("FileVersion", text),
        vi.StringStruct("ProductVersion", text),
    ]
    info = vi.VSVersionInfo(
        ffi=vi.FixedFileInfo(filevers=numbers, prodvers=numbers, mask=0x3F, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
        kids=[
            vi.StringFileInfo([vi.StringTable("040904B0", strings)]),
            vi.VarFileInfo([vi.VarStruct("Translation", [_LANG, 1200])]),
        ],
    )
    return info.toRaw()


def _icon_ids(path: Path) -> list[int]:
    from PyInstaller.utils.win32 import winresource

    found = winresource.get_resources(str(path), types=[_RT_ICON])
    return sorted(found.get(_RT_ICON, {}))


def stamp(exe: Path, version: str, icon: Path = ICON) -> None:
    """Give an exe the app's name and icon in its resources."""
    from PyInstaller.utils.win32.icon import IconFile

    kernel32 = ctypes.windll.kernel32
    kernel32.BeginUpdateResourceW.argtypes = (wintypes.LPCWSTR, wintypes.BOOL)
    kernel32.BeginUpdateResourceW.restype = wintypes.HANDLE
    kernel32.UpdateResourceW.argtypes = (wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, wintypes.WORD, ctypes.c_void_p, wintypes.DWORD)
    kernel32.EndUpdateResourceW.argtypes = (wintypes.HANDLE, wintypes.BOOL)

    old_icons = _icon_ids(exe)
    art = IconFile(str(icon))
    handle = kernel32.BeginUpdateResourceW(str(exe), False)
    if not handle:
        raise OSError(f"cannot open {exe} to change its resources")

    def put(kind: int, name: int, data: bytes | None) -> None:
        buffer = ctypes.create_string_buffer(data) if data else None
        if not kernel32.UpdateResourceW(handle, kind, name, _LANG, buffer, len(data) if data else 0):
            raise OSError(f"cannot write resource {kind}/{name} in {exe}")

    try:
        put(_RT_VERSION, 1, _version_info(version))
        for number, image in enumerate(art.images, start=1):
            put(_RT_ICON, number, image)
        for number in old_icons:
            if number > len(art.images):
                put(_RT_ICON, number, None)
        put(_RT_GROUP_ICON, 1, art.grp_icon_dir() + art.grp_icondir_entries(1))
    except Exception:
        kernel32.EndUpdateResourceW(handle, True)
        raise
    if not kernel32.EndUpdateResourceW(handle, False):
        raise OSError(f"cannot save the resources of {exe}")


def make_app_exe(runtime: Path, version: str) -> Path:
    """runtime\\I5黑名单.exe from runtime\\pythonw.exe, refreshed when either changed."""
    source = runtime / "pythonw.exe"
    target = runtime / APP_EXE
    temporary = runtime / "app-exe.tmp"
    shutil.copy2(source, temporary)
    stamp(temporary, version)
    if target.is_file() and target.read_bytes() == temporary.read_bytes():
        temporary.unlink()
    else:
        temporary.replace(target)
    return target


def _version() -> str:
    sys.path.insert(0, str(REPO))
    from blacklist_detect import __version__

    return __version__


if __name__ == "__main__":
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "dist" / "黑名单检测" / "runtime"
    print(make_app_exe(folder, _version()))
