"""Read the reference lobby. Needs the local PaddleOCR Chinese model."""

from pathlib import Path

import pytest

from blacklist_detect.model import Entry
from blacklist_detect.pipeline import check_image

# CI has no Paddle and no models. The release build runs this check on the bundled runtime instead.
pytest.importorskip("paddleocr", reason="PaddleOCR is not installed")

FIXTURE = Path(__file__).parent / "fixtures" / "reference-lobby.png"

# Visible text, and whether the card hides the rest with an ellipsis.
# Slot 3 and slot 9 are what this model reads off the pixels. The plan's
# labels for those two cards are 罪玥吉尔曼 and gifdsd; see the assertions.
EXPECTED = [
    ("无害虎皮...", True),
    ("栀盏灯下", False),
    ("霁玥吉尔曼", False),
    ("小猫爆锤...", True),
    ("穷不知", False),
    ("祈光君", False),
    ("谁想救人", False),
    ("坎贝尔又...", True),
    ("gffdsd", False),
    ("EluElu", False),
    ("玩的很菜了", False),
    ("不屑讨好谁", False),
]


def test_reference_lobby_names():
    assert FIXTURE.is_file(), f"missing fixture {FIXTURE}"
    entries = [
        Entry("霁玥吉尔曼", reason="在这张图上"),
        Entry("罪玥吉尔曼"),
        Entry("gifdsd"),
        Entry("gffdsd"),
        Entry("无害虎皮猫"),
        Entry("雾玥吉尔曼"),
        Entry("准备就绪"),
    ]
    result = check_image(FIXTURE, entries)
    read = [(slot.visible, slot.truncated, slot.raw, round(slot.confidence, 3), slot.unclear) for slot in result.names]
    assert result.header_found, result.message
    assert result.countdown_seconds == 10, result.message
    assert result.ready_count == 11
    assert [(slot.visible, slot.truncated) for slot in result.names] == EXPECTED, read
    # The printed third name is not rewritten toward 罪 or 雾.
    assert result.names[2].visible == "霁玥吉尔曼"
    assert result.names[2].raw.startswith("霁玥吉尔曼")
    assert "雾" not in result.names[2].visible
    assert "罪" not in result.names[2].visible
    # The printed Latin name keeps the second letter the model sees.
    assert result.names[8].visible == "gffdsd"
    assert result.names[9].visible == "EluElu"
    assert result.names[10].visible == "玩的很菜了"
    matched = [hit.entry_name for hit in result.hits]
    assert "霁玥吉尔曼" in matched
    assert "gffdsd" in matched
    assert "无害虎皮猫" in matched
    assert "罪玥吉尔曼" not in matched
    assert "gifdsd" not in matched
    assert "雾玥吉尔曼" not in matched
    assert "准备就绪" not in matched


# The bundled sample is the reference lobby with every player's name replaced by a made-up one:
# the app ships no real player's name.
SAMPLE_NAMES = ["小林同学", "白日梦想家", "路过的猫", "一只团子", "夏天的风", "心动小鹿",
                "晚风吹过", "摸鱼大师", "示例坏人", "心动星星", "柠檬汽水", "棉花糖"]  # fmt: skip


def test_the_bundled_sample_reads_its_made_up_names():
    from blacklist_detect.ui import SAMPLE_LOBBY

    assert SAMPLE_LOBBY.is_file()
    result = check_image(SAMPLE_LOBBY, [])
    assert result.header_found
    assert [(slot.visible, slot.truncated, slot.unclear) for slot in result.names] == [(name, False, False) for name in SAMPLE_NAMES]


def test_the_glance_sees_the_title_in_the_reference_band():
    from blacklist_detect.pipeline import glance_title, load_rgb

    rgb = load_rgb(FIXTURE)
    assert glance_title(rgb[: int(rgb.shape[0] * 0.4)]) is True
    assert glance_title(rgb[int(rgb.shape[0] * 0.5) :]) is False


@pytest.mark.parametrize("shrink", [1, 2, 4])
def test_a_lobby_in_a_small_window_on_a_big_screen_is_found(shrink):
    """An emulator's window on a 4K screen: the screen is shrunk to find text, so the lines under the
    title are read again from the full copy. Found down to a quarter of the screen's width."""
    import numpy as np
    from PIL import Image

    from blacklist_detect.pipeline import check_rgb
    from blacklist_detect.ui import SAMPLE_LOBBY

    lobby = Image.open(SAMPLE_LOBBY).convert("RGB")
    if shrink > 1:
        lobby = lobby.reduce(shrink)
    screen = Image.new("RGB", (3840, 2160), (40, 44, 52))
    screen.paste(lobby, ((3840 - lobby.width) // 2, (2160 - lobby.height) // 2))
    result = check_rgb(np.asarray(screen), [])
    assert result.header_found, result.message
    assert result.countdown_seconds == 10 and result.ready_count == 11
    read = [slot.visible for slot in result.names]
    assert sum(1 for got, want in zip(read, SAMPLE_NAMES, strict=True) if got == want) >= 11, read
    # The whole game screen round it, 16:9: the sample is a crop of a lobby, so it lies inside.
    left, top = (3840 - lobby.width) // 2, (2160 - lobby.height) // 2
    g_left, g_top, g_right, g_bottom = result.game_box
    assert abs((g_right - g_left) / (g_bottom - g_top) - 16 / 9) < 0.01
    assert g_left <= left and g_top <= top and g_right >= left + lobby.width and g_bottom >= top + lobby.height


def test_the_same_lobby_again_is_read_where_it_was_and_a_moved_one_is_searched_for():
    """After a lobby is found, the next check reads its header where it was and skips the search;
    the names are cut where the search put them, so they read the same. A moved window is searched for."""
    import numpy as np
    from PIL import Image

    from blacklist_detect.ocr_engine import get_engine
    from blacklist_detect.pipeline import check_rgb
    from blacklist_detect.ui import SAMPLE_LOBBY

    engine = get_engine()
    engine.lobby_spot = None
    lobby = Image.open(SAMPLE_LOBBY).convert("RGB").reduce(2)

    def screen(x: int, y: int) -> np.ndarray:
        canvas = Image.new("RGB", (3840, 2160), (40, 44, 52))
        canvas.paste(lobby, (x, y))
        return np.asarray(canvas)

    here = screen(900, 500)
    first = check_rgb(here, [])
    assert first.header_found and "spot" not in first.timings
    again = check_rgb(here, [])
    assert again.header_found and again.timings.get("spot") == 1.0
    assert [s.visible for s in again.names] == [s.visible for s in first.names]
    assert (again.button_box, again.ready_count, again.countdown_seconds) == (first.button_box, 11, 10)
    # The window moved: the remembered spot no longer shows the title, so the lobby is searched for.
    moved = check_rgb(screen(1500, 300), [])
    assert moved.header_found and "spot" not in moved.timings
    assert moved.button_box != first.button_box
    engine.lobby_spot = None
