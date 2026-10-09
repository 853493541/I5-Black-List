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


def test_the_bundled_sample_reads_like_the_reference():
    from blacklist_detect.ui import SAMPLE_LOBBY

    assert SAMPLE_LOBBY.is_file()
    result = check_image(SAMPLE_LOBBY, [])
    assert result.header_found
    assert [(slot.visible, slot.truncated) for slot in result.names] == EXPECTED
