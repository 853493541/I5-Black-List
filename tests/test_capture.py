import sys

import pytest

from blacklist_detect.capture import (
    TITLE_BAND_FRACTION,
    CaptureUnavailable,
    capture_capability_message,
    capture_displays,
    capture_top_band,
)


def test_missing_display_api_is_reported():
    message = capture_capability_message()
    if sys.platform == "win32":
        assert message == "" or "选择图片" in message
        return
    assert "选择图片" in message
    with pytest.raises(CaptureUnavailable) as raised:
        capture_displays()
    assert "选择图片" in str(raised.value)


def test_top_band_is_the_upper_part_of_the_desktop():
    if sys.platform != "win32":
        with pytest.raises(CaptureUnavailable):
            capture_top_band()
        return
    full = capture_displays()[0]
    band = capture_top_band()
    assert band.shape[1] == full.shape[1]
    assert band.shape[0] == max(1, int(round(full.shape[0] * TITLE_BAND_FRACTION)))
