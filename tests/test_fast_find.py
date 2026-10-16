"""Finding the lobby without reading the whole screen: the title from the tallest lines, then only the
lines under it; read again sharp from the full copy when the screen was shrunk too far to read them."""

import numpy as np

from blacklist_detect import pipeline
from blacklist_detect.layout import COUNTDOWN_BOX, MODE_BOX, REF_READY_DY, TITLE_BOX, find_anchor, ready_strip
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


def test_no_title_among_the_tallest_lines_is_still_searched_for_fully():
    # Bigger text than the game's title elsewhere on the screen must not hide a lobby.
    rgb = np.zeros((720, 1280, 3), dtype=np.uint8)
    engine = _Engine([], full=_header(1280, 720))
    anchor, _lines = pipeline._locate(engine, rgb)
    assert anchor.found and engine.full_reads == 1
    # And with no lobby at all, the answer is no.
    engine = _Engine([])
    anchor, _lines = pipeline._locate(engine, rgb)
    assert not anchor.found and engine.full_reads == 1


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
    # The second crop is the strip where 准备就绪 must be, since it did not come back either.
    assert len(engine.crops) == 2 and engine.full_reads == 0
    height, width = engine.crops[0]
    assert width * height < 0.6 * 3840 * 2160, "only the part under the title, at full size"
    assert abs(anchor.title_box[0] - full[0].box[0]) < 2


def test_a_lobby_found_without_its_ready_line_reads_it_again_where_it_must_be():
    # A game window on a 4K screen: the header was read shrunk, 准备就绪 was not among its lines.
    rgb = np.zeros((2160, 3840, 3), dtype=np.uint8)
    engine = _Engine(_header(1280, 720))
    first = find_anchor(_header(3840, 2160), 3840, 2160)
    strip = ready_strip(first)
    middle = (first.title_box[1] + first.title_box[3]) / 2 + REF_READY_DY * first.scale * 0.99
    left, top = int(strip[0]), int(strip[1])
    engine.crop = [OcrLine("准备就绪：11/12", 0.99, (400.0, middle - 20 - top, 700.0, middle + 20 - top))]
    anchor, lines = pipeline._locate(engine, rgb)
    assert anchor.found and anchor.ready_count == 11
    assert abs(anchor.scale / first.scale - 0.99) < 1e-6, "sized from 准备就绪, not from the countdown"
    assert any(line.box[0] == 400.0 + left for line in lines), "the line is placed on the whole screen"
    height, width = engine.crops[0]
    assert len(engine.crops) == 1 and width * height < 0.15 * 3840 * 2160, "only the strip, at full size"
    # A read that has 准备就绪 already reads nothing more.
    ready = OcrLine("准备就绪：11/12", 0.99, tuple(value / 3 for value in lines[-1].box))
    engine = _Engine([*_header(1280, 720), ready])
    anchor, _lines = pipeline._locate(engine, rgb)
    assert anchor.found and anchor.ready_count == 11 and engine.crops == [] and engine.full_reads == 0
