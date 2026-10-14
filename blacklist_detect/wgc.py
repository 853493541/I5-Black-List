"""Would Windows capture this window the way 直播姬's 窗口捕捉 does?

直播姬 (and OBS) capture a window with Windows.Graphics.Capture: IGraphicsCaptureItemInterop's
CreateForWindow. On a friend's Windows 10 that call refused 直播模式's window every time with
E_INVALIDARG (0x80070057), the answer Windows gives for a window that is not showing, while it took
the game's window beside it. The capture was in the scene and live, and stayed blank.

The same call says beforehand whether a window will be captured. It is asked from a process of its
own, as 直播姬 asks it:

    python -m blacklist_detect.wgc <hwnd> [<hwnd> ...]    prints each HRESULT on a line, 0x00000000 when
                                                         Windows would capture it
"""

from __future__ import annotations

import ctypes
import sys
import uuid
from pathlib import Path

ACCEPTED = 0
# What Windows answers for a window it will not capture (and for a hidden one).
REFUSED = 0x80070057


def _guid(text: str):  # noqa: ANN202
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]

    value = uuid.UUID(text)
    return GUID(value.time_low, value.time_mid, value.time_hi_version, (ctypes.c_ubyte * 8)(*value.bytes[8:]))


def answer(hwnd: int) -> int | None:
    """CreateForWindow's HRESULT for hwnd: ACCEPTED when Windows would capture it. None where there is
    no Windows.Graphics.Capture to ask (not Windows, or Windows 10 before 1903)."""
    if sys.platform != "win32":
        return None
    from ctypes import wintypes

    combase = ctypes.windll.combase
    combase.RoInitialize(1)
    name = "Windows.Graphics.Capture.GraphicsCaptureItem"
    handle = ctypes.c_void_p()
    combase.WindowsCreateString(ctypes.c_wchar_p(name), len(name), ctypes.byref(handle))
    interop = _guid("3628E81B-3CAC-4C60-B7F4-23CE0E0C3356")
    factory = ctypes.c_void_p()
    found = combase.RoGetActivationFactory(handle, ctypes.byref(interop), ctypes.byref(factory))
    combase.WindowsDeleteString(handle)
    if found != 0 or not factory:
        return None

    def method(pointer: ctypes.c_void_p, index: int, *types):  # noqa: ANN002, ANN202
        table = ctypes.cast(ctypes.cast(pointer, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
        return ctypes.WINFUNCTYPE(*types)(table[index])

    item_iid = _guid("79C3F95B-31F7-4EC2-A464-632EF5D30760")
    item = ctypes.c_void_p()
    create = method(factory, 3, ctypes.HRESULT, ctypes.c_void_p, wintypes.HWND, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
    try:
        create(factory, hwnd, ctypes.addressof(item_iid), ctypes.byref(item))
        result = ACCEPTED
    except OSError as error:
        result = (error.winerror or 0) & 0xFFFFFFFF
    if item:
        method(item, 2, ctypes.c_ulong, ctypes.c_void_p)(item)
    method(factory, 2, ctypes.c_ulong, ctypes.c_void_p)(factory)
    return result


def hide_taskbar_button(hwnd: int) -> bool:
    """Take a window's button off the taskbar (ITaskbarList.DeleteTab); its styles stay as they are.
    False where the taskbar could not be asked. Windows 11 still captures it then; Windows 10 does not
    (直播画面 in v0.9.5), so only the diagnosis does this, to a copy."""
    if sys.platform != "win32":
        return False
    from ctypes import wintypes

    ole32 = ctypes.windll.ole32
    taskbar = ctypes.c_void_p()
    clsid, iid = _guid("56FDF344-FD6D-11D0-958A-006097C9A090"), _guid("56FDF342-FD6D-11D0-958A-006097C9A090")
    if ole32.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(taskbar)) != 0 or not taskbar:
        return False
    table = ctypes.cast(ctypes.cast(taskbar, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
    ready = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(table[3])(taskbar) == 0  # HrInit
    gone = ready and ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, wintypes.HWND)(table[5])(taskbar, hwnd) == 0  # DeleteTab
    ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[2])(taskbar)  # Release
    return gone


def command(hwnd: int) -> tuple[str, list[str], str]:
    """Program, arguments and folder that ask it from a process of their own, with no console."""
    program = Path(sys.executable)
    quiet = program.with_name("pythonw.exe")
    return str(quiet if quiet.is_file() else program), ["-m", "blacklist_detect.wgc", str(hwnd)], str(Path(__file__).parent.parent)


def read(output: str) -> int | None:
    """The answer printed by the process: an HRESULT, or None."""
    text = output.strip()
    try:
        return int(text, 16)
    except ValueError:
        return None


def words(result: int | None) -> str:
    """The answer for the log."""
    if result is None:
        return "no Windows.Graphics.Capture to ask"
    return "captured" if result == ACCEPTED else f"refused (0x{result:08X})"


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        result = answer(int(argument))
        print("none" if result is None else f"0x{result:08X}")
