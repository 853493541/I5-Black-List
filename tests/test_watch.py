"""The lobby title starts one check, then waits until it leaves."""

import numpy as np

from blacklist_detect.model import OcrLine
from blacklist_detect.pipeline import glance_title
from blacklist_detect.watch import LobbyWatch


class _Reader:
    def __init__(self, text: str) -> None:
        self.text = text

    def read_bgr(self, _image):
        return [OcrLine(self.text, 0.99, (0.0, 0.0, 10.0, 10.0))]


def test_glance_sees_only_the_match_found_title():
    image = np.zeros((48, 96, 3), dtype=np.uint8)
    assert glance_title(image, engine=_Reader("推演成功")) is True
    assert glance_title(image, engine=_Reader("准备就绪 0/12")) is False


def test_watch_checks_once_while_the_title_stays():
    watch = LobbyWatch(cooldown=1.0)
    assert watch.wants_check(False, 0.0) is False
    assert watch.wants_check(True, 1.0) is True
    watch.arm(1.0)
    assert watch.wants_check(True, 1.2) is False
    watch.hold()
    assert watch.wants_check(True, 5.0) is False
    assert watch.wants_check(False, 6.0) is False
    assert watch.wants_check(True, 6.4) is False
    assert watch.wants_check(False, 8.0) is False
    assert watch.wants_check(False, 9.0) is False
    assert watch.wants_check(True, 9.1) is True


def test_watch_retries_when_the_title_is_not_the_lobby_yet():
    watch = LobbyWatch(cooldown=1.0)
    assert watch.wants_check(True, 0.0) is True
    watch.arm(0.0)
    watch.retry_after(0.2)
    assert watch.wants_check(True, 0.5) is False
    assert watch.wants_check(True, 1.2) is True
