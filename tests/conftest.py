"""Shared test setup.

PySide6 6.12 crashes when a window is destroyed at the wrong moment: by a garbage
collection that happens to run inside a later test's Qt call, or after QApplication
is gone while Python shuts down. The app has one window that lives until it quits,
so it never meets this; a test run makes and drops dozens. So the windows each test
makes are kept until the run ends, and the run then exits without tearing Qt down.
"""

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
