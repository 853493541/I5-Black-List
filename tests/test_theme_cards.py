"""特效 cards: every scene has its picture, a gallery picks one at a time, and the 嘉宾 dialogs play the
picked one."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from blacklist_detect import love_scenes


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_every_scene_has_its_picture():
    from blacklist_detect.ui_theme_cards import POSTERS

    # build/theme_posters.py draws them; a scene added without one would show the bare lobby.
    assert {path.stem for path in Path(POSTERS).glob("*.jpg")} == set(love_scenes.KEYS)


def test_a_gallery_picks_one_card_at_a_time(qapp):
    from blacklist_detect.ui_theme_cards import ThemeGallery, poster

    items = [*love_scenes.SCENES, ("random", "随机"), ("off", "无")]
    picked: list[str] = []
    gallery = ThemeGallery(items, "stars", 780)
    gallery.picked.connect(picked.append)
    assert list(gallery.buttons) == [key for key, _name in items] and gallery.value() == "stars"
    gallery.buttons["cyber"].click()
    assert gallery.value() == "cyber" and picked == ["cyber"]
    assert sum(card.isChecked() for card in gallery.buttons.values()) == 1
    # Six to a row, all the same size, 无 in red.
    cards = list(gallery.buttons.values())
    assert len({card.size().toTuple() for card in cards}) == 1 and cards[0].width() * 6 <= 780
    assert gallery.buttons["off"].property("off") is True and gallery.buttons["off"].text() == "无"
    # Every card draws, 随机 and 无 with pictures of their own.
    for card in cards:
        assert not card.grab().isNull()
    assert not poster("random").isNull() and not poster("off").isNull()
    # A saved choice this version does not have starts on the first card.
    assert ThemeGallery(items, "ribbon", 780).value() == "classic"


def test_a_guests_default_card_shows_what_effects_plays(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from blacklist_detect.ui_likes import LikeDialog

    dialog = LikeDialog(default_scene="random")
    card = dialog.theme_row.buttons[""]
    assert card.text() == "默认" and card.label == "默认 · 随机" and card.isChecked()
    assert dialog.preview.choice == "random" and dialog.preview.caption().startswith("默认 · 随机 · ")
    dialog.theme_row.buttons["claw"].click()
    assert dialog.preview.caption() == "遇袭"
    dialog.reject()
