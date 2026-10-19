"""A frozen window leaves where it froze: its stack in crash.log, and when it stopped in app.log."""

import logging
import time

import pytest

from blacklist_detect import logs


class _Lines(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


@pytest.fixture
def said():  # noqa: ANN201
    handler = _Lines()
    logs.log.addHandler(handler)
    level = logs.log.level
    logs.log.setLevel(logging.INFO)
    yield handler.lines
    logs.log.removeHandler(handler)
    logs.log.setLevel(level)


def _blocks_the_main_thread() -> None:
    time.sleep(2.0)


def test_a_main_thread_that_stops_answering_leaves_its_stack(tmp_path, said):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    with open(tmp_path / "crash.log", "w", encoding="utf-8") as crash:
        dog = logs.watch_main_thread(period=0.2, dump_after=1.0, quiet_after=0.8, crash_file=crash)
        try:
            loop = QEventLoop()
            QTimer.singleShot(300, _blocks_the_main_thread)
            QTimer.singleShot(3000, loop.quit)
            loop.exec()
        finally:
            dog.stop()
            dog.timer.stop()
    text = (tmp_path / "crash.log").read_text(encoding="utf-8")
    assert "Timeout" in text and "_blocks_the_main_thread" in text
    assert [line for line in said if "not answering" in line] and [line for line in said if "answering again" in line]


def test_a_pc_that_slept_is_no_freeze(said):
    now = [100.0]
    dog = logs.Watchdog(period=2.0, quiet_after=10.0, asleep_after=20.0, clock=lambda: now[0])

    def tick(seconds: float) -> None:
        now[0] += seconds
        dog.tick()

    dog.beat()
    tick(2.0)
    # An hour asleep: neither thread ran, and on waking the beat is long ago.
    tick(3600.0)
    tick(2.0)
    tick(2.0)
    assert said == []
    # A real freeze: the watch keeps ticking, the main thread does not beat. Said once.
    for _ in range(8):
        tick(2.0)
    assert len(said) == 1 and said[0].startswith("Main thread not answering for 1")
    dog.beat()
    tick(2.0)
    assert len(said) == 2 and said[1] == "Main thread answering again after 20 s."


def test_the_tray_says_it_is_alive_only_while_hidden(said):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    hidden = [False]
    timer = logs.tray_heartbeat(None, lambda: hidden[0], every_ms=50)
    loop = QEventLoop()
    QTimer.singleShot(200, loop.quit)
    loop.exec()
    assert "Tray: alive." not in said
    hidden[0] = True
    QTimer.singleShot(200, loop.quit)
    loop.exec()
    timer.stop()
    assert "Tray: alive." in said
