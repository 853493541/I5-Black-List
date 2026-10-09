"""Header anchor. The countdown digit is read, not fixed at 10."""

from pathlib import Path

import numpy as np
from PIL import Image

from blacklist_detect.layout import (
    BUTTON_BOX,
    COUNTDOWN_BOX,
    MODE_BOX,
    NAME_BOXES,
    REF_H,
    REF_W,
    TITLE_BOX,
    find_anchor,
    snap_button_box,
)
from blacklist_detect.model import OcrLine


def _line(text: str, frac: tuple[float, float, float, float], width=REF_W, height=REF_H) -> OcrLine:
    left, top, right, bottom = frac
    return OcrLine(text, 0.99, (left * width, top * height, right * width, bottom * height))


def _header(seconds: str, extra: list[OcrLine] | None = None) -> list[OcrLine]:
    lines = [
        _line("推演成功", TITLE_BOX),
        _line("模仿者狂欢（12人狂欢）", MODE_BOX),
        _line(f"倒计时 {seconds} 秒", COUNTDOWN_BOX),
    ]
    if extra:
        lines.extend(extra)
    return lines


def test_countdown_digit_is_not_locked_to_ten():
    anchor = find_anchor(_header("4"), REF_W, REF_H)
    assert anchor.found
    assert anchor.countdown_seconds == 4
    assert len(anchor.name_boxes) == 12

    packed = find_anchor(
        [
            _line("推演成功", TITLE_BOX),
            _line("模仿者狂欢（12人狂欢）", MODE_BOX),
            _line("倒计时10秒", COUNTDOWN_BOX),
        ],
        REF_W,
        REF_H,
    )
    assert packed.found
    assert packed.countdown_seconds == 10


def test_name_strips_follow_a_moved_header():
    scale = 0.5
    offset_x, offset_y = 120.0, 80.0

    def place(frac):
        left = offset_x + scale * frac[0] * REF_W
        top = offset_y + scale * frac[1] * REF_H
        right = offset_x + scale * frac[2] * REF_W
        bottom = offset_y + scale * frac[3] * REF_H
        return (left, top, right, bottom)

    lines = [
        OcrLine("推演成功", 0.99, place(TITLE_BOX)),
        OcrLine("模仿者狂欢（12人狂欢）", 0.99, place(MODE_BOX)),
        OcrLine("倒计时 7 秒", 0.99, place(COUNTDOWN_BOX)),
    ]
    width, height = 2000, 1200
    anchor = find_anchor(lines, width, height)
    assert anchor.found
    assert anchor.countdown_seconds == 7
    expected = place(NAME_BOXES[2])
    got = anchor.name_boxes[2]
    for actual, wanted in zip(got, expected, strict=False):
        assert abs(actual - wanted) <= 1


def test_missing_mode_or_seconds_is_not_this_lobby():
    no_mode = find_anchor(
        [
            _line("推演成功", TITLE_BOX),
            _line("模仿者狂欢", MODE_BOX),
            _line("倒计时 9 秒", COUNTDOWN_BOX),
        ],
        REF_W,
        REF_H,
    )
    assert not no_mode.found

    no_digit = find_anchor(
        [
            _line("推演成功", TITLE_BOX),
            _line("模仿者狂欢（12人狂欢）", MODE_BOX),
            _line("倒计时 秒", COUNTDOWN_BOX),
        ],
        REF_W,
        REF_H,
    )
    assert not no_digit.found


def test_text_beside_the_title_does_not_move_the_names():
    title = _line("推演成功", TITLE_BOX)
    junk = OcrLine(
        "亚的纪念日",
        0.9,
        (title.box[2] + 40, title.box[1] + 50, title.box[2] + 360, title.box[1] + 110),
    )
    anchor = find_anchor(_header("10") + [junk], REF_W, REF_H)
    assert anchor.found
    assert anchor.countdown_seconds == 10
    expected_left = round(NAME_BOXES[0][0] * REF_W)
    assert abs(anchor.name_boxes[0][0] - expected_left) <= 2


def test_countdown_split_into_two_tokens_still_counts():
    left = (0.466, 0.253, 0.535, 0.296)
    right = (0.525, 0.253, 0.604, 0.296)
    lines = [
        _line("推演成功", TITLE_BOX),
        _line("模仿者狂欢（12人狂欢）", MODE_BOX),
        _line("倒计时", left),
        _line("3秒", right),
    ]
    anchor = find_anchor(lines, REF_W, REF_H)
    assert anchor.found
    assert anchor.countdown_seconds == 3


def test_restore_button_follows_the_header():
    anchor = find_anchor(_header("10"), REF_W, REF_H)
    assert anchor.button_box is not None
    left, top, right, bottom = anchor.button_box
    assert abs(left - round(BUTTON_BOX[0] * REF_W)) <= 2
    assert abs(top - round(BUTTON_BOX[1] * REF_H)) <= 2
    assert abs(right - round(BUTTON_BOX[2] * REF_W)) <= 2
    assert abs(bottom - round(BUTTON_BOX[3] * REF_H)) <= 2
    assert right > left and bottom > top


def test_button_box_snaps_onto_the_pale_control():
    image = np.asarray(Image.open(Path(__file__).parent / "fixtures" / "reference-lobby.png").convert("RGB"))
    guessed = (
        round(BUTTON_BOX[0] * REF_W),
        round(BUTTON_BOX[1] * REF_H),
        round(BUTTON_BOX[2] * REF_W),
        round(BUTTON_BOX[3] * REF_H),
    )
    shifted = (guessed[0] - 38, guessed[1] - 34, guessed[2] - 48, guessed[3] - 41)
    snapped = snap_button_box(image, shifted)
    assert snapped == snap_button_box(image, guessed)
    assert snapped is not None
    assert abs(snapped[0] - 1498) <= 2
    assert abs(snapped[1] - 1518) <= 2
    assert abs(snapped[2] - 2010) <= 2
    assert abs(snapped[3] - 1667) <= 2
    dark = np.zeros((200, 400, 3), dtype=np.uint8)
    assert snap_button_box(dark, (40, 40, 160, 90)) == (40, 40, 160, 90)


def test_ready_count_is_not_a_thirteenth_name():
    ready_box = (0.461, 0.837, 0.609, 0.878)
    anchor = find_anchor(_header("6", [_line("准备就绪：8/12", ready_box)]), REF_W, REF_H)
    assert anchor.found
    assert anchor.countdown_seconds == 6
    assert anchor.ready_count == 8
    assert len(anchor.name_boxes) == 12
