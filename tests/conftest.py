"""Shared test setup.

PySide6 6.12 crashes when a window is destroyed at the wrong moment: by a garbage
collection that happens to run inside a later test's Qt call, or after QApplication
is gone while Python shuts down. The app has one window that lives until it quits,
so it never meets this; a test run makes and drops dozens. So the windows each test
makes are kept until the run ends, and the run then exits without tearing Qt down.
"""

import contextlib
import os
import sys

import pytest

_windows: list = []
_status = {"code": 0}


@pytest.fixture(autouse=True)
def _no_open_questions(monkeypatch):
    """A question nobody answers would wait forever. A test that means to ask answers it itself."""
    try:
        from blacklist_detect.ui_kit import ConfirmDialog
    except ImportError:
        yield
        return

    def unanswered(dialog):  # noqa: ANN001, ANN202
        raise AssertionError(f"A question was asked and not answered: {dialog.windowTitle() or dialog.body.text()}")

    monkeypatch.setattr(ConfirmDialog, "exec", unanswered)
    # 直播模式's guide only shows how; it is noted, not waited on.
    from blacklist_detect.ui_dialogs import StreamGuideDialog

    StreamGuideDialog.shown = []
    monkeypatch.setattr(StreamGuideDialog, "exec", lambda dialog: StreamGuideDialog.shown.append(dialog) or 0)
    yield


@pytest.fixture(autouse=True)
def _no_game_window(monkeypatch):
    """Whatever windows this PC has open are not a game: the border and glow take the whole screen
    unless a test puts a game window under the button itself."""
    try:
        from blacklist_detect import ui
    except ImportError:
        yield
        return
    monkeypatch.setattr(ui, "window_rect_at", lambda _x, _y, _order=(), innermost=True: None)
    # Nor is any game in exclusive full screen.
    monkeypatch.setattr(ui, "exclusive_fullscreen", lambda: False)
    yield


@pytest.fixture(autouse=True)
def _no_capture_question(monkeypatch):
    """直播模式's window does not ask Windows whether it would capture it, nor why not: each starts a
    process. A test that means to ask calls the real StreamMirror.ask_windows or diagnose itself."""
    try:
        from blacklist_detect.ui_stream import StreamMirror
    except ImportError:
        yield
        return
    monkeypatch.setattr(StreamMirror, "ask_windows", lambda _mirror: None)
    monkeypatch.setattr(StreamMirror, "diagnose", lambda _mirror: None)
    # Nor does it read this PC's 直播姬 scene file: a test that means to gives one of its own.
    from blacklist_detect import livehime_layout

    real = livehime_layout.collection_path
    monkeypatch.setattr(livehime_layout, "collection_path", lambda root=None: None if root is None else real(root))
    yield


@pytest.fixture(autouse=True)
def _no_global_hotkeys(monkeypatch):
    """No test window takes a hotkey from Windows: the app on this PC may hold it, and a key pressed
    while the tests run must not reach them. Each one taken is noted in registered (id, modifiers, key)."""
    from blacklist_detect import hotkey

    registered: list[tuple[int, int, int]] = []
    monkeypatch.setattr(hotkey, "_register", lambda ident, modifiers, vk: registered.append((ident, modifiers, vk)) or True)
    monkeypatch.setattr(hotkey, "_unregister", lambda _ident: None)
    monkeypatch.setattr(hotkey, "registered", registered, raising=False)
    yield


class StartupRegistry:
    """The Run key 开机启动 writes, in memory. values: what it holds, by name."""

    HKEY_CURRENT_USER = "HKCU"
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self):
        self.values: dict[str, str] = {}

    def OpenKey(self, root, path):  # noqa: N802
        return contextlib.nullcontext()

    def CreateKeyEx(self, root, path, reserved, access):  # noqa: N802
        return contextlib.nullcontext()

    def QueryValueEx(self, key, name):  # noqa: N802
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], self.REG_SZ

    def SetValueEx(self, key, name, reserved, kind, value):  # noqa: N802
        self.values[name] = value

    def DeleteValue(self, key, name):  # noqa: N802
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


@pytest.fixture(autouse=True)
def _no_startup_entry(monkeypatch):
    """No test reads or changes the player's own 开机启动 entry: 清空数据 in a test turns off one in
    memory. A test that means to look at it uses autostart._registry()."""
    from blacklist_detect import autostart

    fake = StartupRegistry()
    monkeypatch.setattr(autostart, "_registry", lambda: fake)
    yield


@pytest.fixture(autouse=True)
def _keep_windows():
    yield
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        return
    app = QApplication.instance()
    if app is not None:
        _windows.extend(app.topLevelWidgets())


def pytest_sessionfinish(session, exitstatus):
    _status["code"] = int(exitstatus)


def pytest_unconfigure(config):
    # Results are reported by now. Skip the teardown of the Qt objects above. On Windows
    # even os._exit runs Qt's DLL shutdown, which trips over them, so end the process outright.
    if not _windows:
        return
    sys.stdout.flush()
    sys.stderr.flush()
    code = _status["code"]
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.TerminateProcess.argtypes = (ctypes.c_void_p, ctypes.c_uint)
        kernel32.TerminateProcess(kernel32.GetCurrentProcess(), code)
    os._exit(code)
