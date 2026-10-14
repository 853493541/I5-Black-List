"""wgc: would Windows capture a window the way 直播姬's 窗口捕捉 does?"""

import subprocess
import sys

import pytest

from blacklist_detect import wgc

windows = pytest.mark.skipif(sys.platform != "win32", reason="Windows.Graphics.Capture is Windows only")


def test_the_answer_is_read_back_from_the_process():
    assert wgc.read("0x00000000\n") == wgc.ACCEPTED
    assert wgc.read("0x80070057") == wgc.REFUSED
    assert wgc.read("none") is None and wgc.read("") is None
    assert wgc.words(wgc.ACCEPTED) == "captured"
    assert wgc.words(wgc.REFUSED) == "refused (0x80070057)"
    assert wgc.words(None) == "no Windows.Graphics.Capture to ask"


@windows
def test_a_hidden_window_is_refused_as_on_the_friends_windows_10_and_a_shown_one_is_taken():
    """E_INVALIDARG is what Windows answers for a window that is not showing: what a friend's
    Windows 10 answered for 直播模式's window off the screen."""
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtWidgets import QApplication, QWidget

    QApplication.instance() or QApplication([])
    if QApplication.platformName() != "windows":
        pytest.skip("Qt runs offscreen in this run (other tests set it): no real windows to ask about")
    right = max(screen.geometry().right() for screen in QApplication.screens())
    hidden = QWidget(None, Qt.FramelessWindowHint | Qt.Window)
    hidden.setGeometry(QRect(right + 64, 0, 320, 180))
    assert wgc.answer(int(hidden.winId())) == wgc.REFUSED
    shown = QWidget(None, Qt.FramelessWindowHint | Qt.Window | Qt.WindowTransparentForInput)
    shown.setAttribute(Qt.WA_ShowWithoutActivating, True)
    shown.setGeometry(QRect(right + 64, 0, 320, 180))
    shown.show()
    QApplication.processEvents()
    if sys.getwindowsversion().build >= 22000:
        assert wgc.answer(int(shown.winId())) == wgc.ACCEPTED
    # Asked from a process of its own, as 直播姬 asks it: the same answers.
    for widget in (hidden, shown):
        program, arguments, folder = wgc.command(int(widget.winId()))
        done = subprocess.run([program, *arguments], cwd=folder, capture_output=True, text=True, timeout=60, check=False)
        assert wgc.read(done.stdout) == wgc.answer(int(widget.winId())), done.stderr
    shown.hide()


def _tests(**answers):  # noqa: ANN003, ANN202
    """A diagnosis's tests, each refused unless answers says otherwise (name → HRESULT)."""
    from blacklist_detect.wgc_diagnose import BY_PYTHONW, QT, TASKBAR, WIN32, Test

    names = ["直播画面 itself", "control: the game window 直播姬 captures", TASKBAR]
    names += [name for name, *_rest in WIN32] + [name for name, _without in QT] + [BY_PYTHONW]
    return [Test(name, 1, there=answers.get(name, wgc.REFUSED)) for name in names]


def test_the_diagnosis_says_what_the_answers_point_at():
    from blacklist_detect.wgc_diagnose import QT, WIN32, verdict

    taken = wgc.ACCEPTED
    everything = {name: taken for name, *_rest in (*WIN32, *QT)}
    # The friend's case so far: the game's window taken, ours refused. Which property is it?
    found, fix = verdict(_tests(**{**everything, "control: the game window 直播姬 captures": taken, "Qt, like 直播画面": wgc.REFUSED,
                                   "Qt, like 直播画面, nothing drawn": wgc.REFUSED, "Qt, without no-focus": wgc.REFUSED,
                                   "Qt, without on-bottom": wgc.REFUSED, "Qt, without see-through background": wgc.REFUSED}))  # fmt: skip
    assert found.startswith("Without click-through Windows takes it") and fix == "click-through"
    # The see-through background: named, and not something the app can leave out by itself.
    found, fix = verdict(_tests(**{"control: the game window 直播姬 captures": taken, "plain window": taken, "titled window": taken,
                                   "Qt, without see-through background": taken, "Qt, plain window": taken}))  # fmt: skip
    assert found.startswith("Without see-through Windows takes it") and fix == ""
    # Not the window: no window this app makes is taken, by its own program or by pythonw.exe.
    found, fix = verdict(_tests(**{"control: the game window 直播姬 captures": taken}))
    assert "no window made by this app" in found and fix == ""
    # Only the app's own program: pythonw.exe's plain window is taken.
    found, fix = verdict(_tests(**{"control: the game window 直播姬 captures": taken, "plain window made by pythonw.exe": taken}))
    assert "it is about the app's program file" in found and fix == ""
    # Not the window either: even the game's window and the taskbar are refused when asked from here.
    found, _fix = verdict(_tests())
    assert "refuses even the control windows" in found
    # One control taken is enough to rule that out.
    found, _fix = verdict(_tests(**{"control: the taskbar (Explorer's)": taken}))
    assert "no window made by this app" in found
    # A fresh copy taken: the running window differs.
    found, _fix = verdict(_tests(**{**everything, "control: the game window 直播姬 captures": taken}))
    assert found.startswith("A fresh window like 直播画面 is taken")
    found, _fix = verdict(_tests(**{"直播画面 itself": taken}))
    assert found == "Windows takes 直播画面 now."
    assert verdict([])[0].startswith("Windows could not be asked")


@windows
def test_the_diagnosis_runs_in_a_process_of_its_own_and_reports_everything():
    """Here, on Windows 11, everything is taken; what matters is that every fact and test is there."""
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtWidgets import QApplication, QWidget

    from blacklist_detect import paths
    from blacklist_detect.wgc_diagnose import QT, WIN32, command

    QApplication.instance() or QApplication([])
    if QApplication.platformName() != "windows":
        pytest.skip("Qt runs offscreen in this run (other tests set it): no real windows to ask about")
    flags = Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnBottomHint | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput
    mirror = QWidget(None, flags)
    mirror.setAttribute(Qt.WA_TranslucentBackground, True)
    mirror.setAttribute(Qt.WA_ShowWithoutActivating, True)
    right = max(screen.geometry().right() for screen in QApplication.screens())
    mirror.setGeometry(QRect(right + 64, 0, 320, 180))
    mirror.show()
    QApplication.processEvents()
    program, arguments, folder = command(int(mirror.winId()), 0)
    done = subprocess.run([program, *arguments], cwd=folder, capture_output=True, timeout=120, check=False, env=paths.child_env())
    report = done.stdout.decode("utf-8")
    mirror.hide()
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    assert "fact: 直播画面: class Qt" in report and "extended 0x08080020 (TRANSPARENT|LAYERED|NOACTIVATE)" in report
    assert "fact: 直播画面: layered per pixel (UpdateLayeredWindow)" in report and "直播姬: " in report
    assert "fact: 直播画面: process " in report and "administrator" in report
    assert "fact: the windows below are made by " in report and "test: control: the taskbar (Explorer's): " in report
    for name in ("直播画面 itself", *(name for name, *_rest in WIN32), *(name for name, _without in QT), "plain window made by pythonw.exe"):
        assert f"test: {name}: " in report, name
    if sys.getwindowsversion().build >= 22000:
        assert "verdict: Windows takes 直播画面 now." in report
