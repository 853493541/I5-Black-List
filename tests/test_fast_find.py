"""Finding the lobby without reading the whole screen: the title from the tallest lines, then only the
lines under it; read again sharp from the full copy when the screen was shrunk too far to read them."""

import numpy as np

from blacklist_detect import pipeline
from blacklist_detect.layout import COUNTDOWN_BOX, MODE_BOX, TITLE_BOX
from blacklist_detect.model import OcrLine


def _line(text, frac, width, height):  # noqa: ANN001, ANN202
    left, top, right, bottom = frac
    return OcrLine(text, 0.99, (left * width, top * height, right * width, bottom * height))


class _Engine:
    """Answers read_lobby_lines with the given lines, and counts the full reads."""

    def __init__(self, quick, full=(), crop=()) -> None:  # noqa: ANN001
        self.quick, self.full, self.crop = quick, list(full), list(crop)
        self.full_reads = 0
        self.crops: list[tuple[int, int]] = []

    def read_lobby_lines(self, _bgr):  # noqa: ANN001, ANN202
        return self.quick

    def read_bgr(self, bgr):  # noqa: ANN001, ANN202
        if bgr.shape[:2] == (720, 1280):
            # The whole screen, shrunk to 1280 wide.
            self.full_reads += 1
            return self.full
        self.crops.append(bgr.shape[:2])
        return self.crop


def _header(width, height):  # noqa: ANN001, ANN202
    return [
        _line("推演成功", TITLE_BOX, width, height),
        _line("模仿者狂欢（12人狂欢）", MODE_BOX, width, height),
        _line("倒计时10秒", COUNTDOWN_BOX, width, height),
    ]


def test_the_lobby_is_found_from_the_lines_under_its_title_alone():
    rgb = np.zeros((720, 1280, 3), dtype=np.uint8)
    engine = _Engine(_header(1280, 720))
    anchor, _lines = pipeline._locate(engine, rgb)
    assert anchor.found and engine.full_reads == 0, "the rest of the screen is never read"


def test_no_title_among_the_tallest_lines_means_no_lobby_at_once():
    rgb = np.zeros((720, 1280, 3), dtype=np.uint8)
    engine = _Engine([])
    anchor, _lines = pipeline._locate(engine, rgb)
    assert not anchor.found and engine.full_reads == 0


def test_lines_too_small_on_a_shrunk_screen_are_read_again_sharp():
    # A 3840 wide screen is shrunk to 1280 to find text: the title is read, the countdown is not.
    rgb = np.zeros((2160, 3840, 3), dtype=np.uint8)
    title = _line("推演成功", TITLE_BOX, 1280, 720)
    engine = _Engine([title, _line("倒计", COUNTDOWN_BOX, 1280, 720)])
    # Read sharp from the full copy, the crop's lines come back in its own coordinates.
    full = _header(3840, 2160)
    left, top = int((title.box[0] + title.box[2]) / 2 * 3 - 1.4 * (title.box[2] - title.box[0]) * 3), int(title.box[1] * 3 - 0.4 * (title.box[3] - title.box[1]) * 3)
    engine.crop = [OcrLine(line.text, line.confidence, (line.box[0] - left, line.box[1] - top, line.box[2] - left, line.box[3] - top)) for line in full]
    anchor, _lines = pipeline._locate(engine, rgb)
    assert anchor.found and anchor.countdown_seconds == 10
    assert len(engine.crops) == 1 and engine.full_reads == 0
    height, width = engine.crops[0]
    assert width * height < 0.6 * 3840 * 2160, "only the part under the title, at full size"
    assert abs(anchor.title_box[0] - full[0].box[0]) < 2
