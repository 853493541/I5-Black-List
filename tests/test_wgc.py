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
