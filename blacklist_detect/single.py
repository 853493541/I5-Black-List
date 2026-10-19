"""One copy of the app at a time, and no copy stuck open.

Two things say a copy is open. The named pipe (paths.instance_key) is how a copy answers: a new
start asks it to show its window and leaves. A Windows mutex of the same name is held for as long
as the process lives, so it says a copy exists even while that copy is still starting and not
answering yet, and only the first of two starts at once owns it.

A copy can be left open without a window, a tray icon or a pipe: it answers nobody, and it holds
the app's files, so the launcher will not lay an update over them and the update starts over at
every restart. A start that finds such a copy from its own folder writes a small dump of it
(logs/stuck-<pid>.dmp, its threads' stacks, for 导出日志) and ends it. Only processes whose
program is this folder's runtime are ever ended, never anything else on the PC.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

from blacklist_detect.logs import log_dir
from blacklist_detect.names import PROCESSES

log = logging.getLogger(__name__)

# The mutex, held until the process ends.
_held = None
ERROR_ALREADY_EXISTS = 183


def claim(key: str) -> bool:
    """Take the app's mutex. True when this is the only copy that holds it (the first to start)."""
    global _held
    if sys.platform != "win32":
        return True
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
    handle = kernel32.CreateMutexW(None, False, "Local\\" + key)
    first = ctypes.get_last_error() != ERROR_ALREADY_EXISTS
    if handle:
        _held = handle
    return first


def _processes() -> list[tuple[int, str]]:
    """Every process: its id and its program's file name, as Windows lists them."""
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class Entry(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(Entry))
    kernel32.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(Entry))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    snapshot = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if not snapshot or snapshot == wintypes.HANDLE(-1).value:
        return []
    found: list[tuple[int, str]] = []
    try:
        entry = Entry()
        entry.dwSize = ctypes.sizeof(Entry)
        more = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            found.append((entry.th32ProcessID, entry.szExeFile))
            more = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return found


def running(program: str) -> bool:
    """Whether a program by this file name is running, such as livehime.exe."""
    return any(name.lower() == program.lower() for _pid, name in _processes())


def copies_in(root: Path) -> list[int]:
    """Other processes running this folder's copy of the app (runtime\\模仿者小工具.exe)."""
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    wanted = {os.path.normcase(str((root / "runtime" / name).resolve())) for name in PROCESSES}
    names = {name.lower() for name in PROCESSES}
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    found: list[int] = []
    for pid, name in _processes():
        if pid == os.getpid() or name.lower() not in names:
            continue
        process = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not process:
            continue
        try:
            size = wintypes.DWORD(1024)
            buffer = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(size)):
                if os.path.normcase(buffer.value) in wanted:
                    found.append(pid)
        finally:
            kernel32.CloseHandle(process)
    return found


def end(pids: list[int]) -> list[int]:
    """End these processes. Returns the ones that were ended."""
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    ended = []
    for pid in pids:
        process = kernel32.OpenProcess(0x0001 | 0x00100000, False, pid)  # PROCESS_TERMINATE | SYNCHRONIZE
        if not process:
            continue
        try:
            if kernel32.TerminateProcess(process, 1):
                kernel32.WaitForSingleObject(process, 3000)
                ended.append(pid)
        finally:
            kernel32.CloseHandle(process)
    return ended


def settle(root: Path | None, first: bool, answers: Callable[[], bool], wait: float = 8.0) -> bool:
    """Before this copy opens its window: True when another copy answered (this one should leave).

    first is whether this start owns the mutex; answers() asks the pipe. A copy that holds the
    mutex but does not answer may still be starting, so it gets a few seconds. A copy from this
    folder that never answers is stuck, and is ended.
    """
    if answers():
        return True
    others = copies_in(root) if root is not None else []
    if first and not others:
        return False
    # Another copy exists: give it time to start answering.
    deadline = time.monotonic() + (wait if not first else 3.0)
    while time.monotonic() < deadline:
        time.sleep(0.25)
        if answers():
            return True
    stuck = copies_in(root) if root is not None else []
    if stuck:
        # Where it was stuck, for its log: each thread's stack, written before it is ended.
        dumps = []
        for pid in stuck:
            try:
                dumps.append(write_dump(pid, log_dir()).name)
            except Exception as error:  # noqa: BLE001 - a copy that cannot be looked at is still ended
                log.warning("Could not write a dump of the copy %s that does not answer: %s", pid, error)
        ended = end(stuck)
        log.warning("A copy was open but its pipe did not answer; wrote %s; ended it: %s", ", ".join(dumps) or "no dump", ended)
    return False


DUMPS_KEPT = 3


def write_dump(pid: int, folder: Path, keep: int = DUMPS_KEPT) -> Path:
    """A small minidump of a process (folder/stuck-<pid>.dmp): its threads and their stacks, none of
    its other memory. Only the newest keep dumps stay. Raises OSError when Windows will not write it."""
    if sys.platform != "win32":
        raise OSError("minidumps are written on Windows only")
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    dbghelp = ctypes.WinDLL("dbghelp", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    dbghelp.MiniDumpWriteDump.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    )  # fmt: skip
    dbghelp.MiniDumpWriteDump.restype = wintypes.BOOL
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"stuck-{pid}.dmp"
    process = kernel32.OpenProcess(0x0400 | 0x0010, False, pid)  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
    if not process:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        with open(target, "wb") as out:
            # MiniDumpNormal | MiniDumpWithThreadInfo: the stacks and each thread's times, no heap.
            if not dbghelp.MiniDumpWriteDump(process, pid, msvcrt.get_osfhandle(out.fileno()), 0x0000 | 0x1000, None, None, None):
                error = ctypes.WinError(ctypes.get_last_error())
                out.close()
                target.unlink(missing_ok=True)
                raise error
    finally:
        kernel32.CloseHandle(process)
    for old in sorted(folder.glob("stuck-*.dmp"), key=lambda path: path.stat().st_mtime)[:-keep]:
        old.unlink(missing_ok=True)
    return target


def exit_now(code: int) -> None:
    """End this process at once, without unloading its libraries: PySide6 can crash while it is
    unloaded after the app has closed, and a process stuck there holds the app's files."""
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.TerminateProcess.argtypes = (ctypes.c_void_p, ctypes.c_uint)
        kernel32.TerminateProcess(kernel32.GetCurrentProcess(), code)
    os._exit(code)
