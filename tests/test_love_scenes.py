"""心动特效: the ten scenes, choosing one or a random one, and 设置's picker with its preview."""

import random

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from blacklist_detect import love_scenes  # noqa: E402
from blacklist_detect.love_scenes import KEYS, Stage, choose, sample_stage  # noqa: E402


@pytest.fixture(scope="module")
def qapp():  # noqa: ANN201
    return QApplication.instance() or QApplication([])


def _frames(stage: Stage, key: str) -> list[QImage]:
    module = love_scenes.load(key)
    paint = module.make(stage)
    shots = []
    for t in (0.0, 0.4, 1.0, 1.7, 2.6, 3.4, module.DURATION - 0.3, module.DURATION):
        image = QImage(round(stage.width), round(stage.height), QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        paint(painter, t)
        painter.end()
        shots.append(image)
    return shots


def _drawn(image: QImage) -> bool:
    """Whether anything at all was drawn, looking at a coarse grid of pixels."""
    return any(image.pixelColor(x, y).alpha() for x in range(0, image.width(), 7) for y in range(0, image.height(), 7))


@pytest.mark.parametrize("key", KEYS)
def test_every_scene_plays_through_and_keeps_the_button_bare(qapp, key):
    stage = sample_stage()
    shots = _frames(stage, key)
    assert 4.0 <= love_scenes.load(key).DURATION <= 5.5
    assert any(_drawn(shot) for shot in shots[1:-1]), "something shows while it plays"
    # The middle of 准备案件还原 stays as the game drew it, at every moment.
    middle = stage.gap.center().toPoint()
    button = QRect(middle.x() - 60, round(stage.gap.top() + 50), 120, 20)
    for shot in shots:
        assert all(shot.pixelColor(x, y).alpha() < 40 for x in range(button.left(), button.right(), 6) for y in (button.top(), button.bottom()))


@pytest.mark.parametrize("key", KEYS)
def test_every_scene_fits_another_window_shape(qapp, key):
    """A windowed emulator is narrower and taller than the lobby the scenes were drawn on."""
    stage = Stage(900, 640, QRectF(300, 540, 330, 100), badge=QPointF(600, 580), cards=(QPointF(700, 200), QPointF(450, 380), QPointF(200, 200)))
    _frames(stage, key)


def test_choosing_one_random_or_none():
    rng = random.Random(5)
    assert choose("off", "", 2, rng) == ""
    assert choose("ice", "ice", 2, rng) == "ice"
    picks = []
    last = ""
    for _ in range(80):
        last = choose("random", last, 2, rng)
        picks.append(last)
    assert set(picks) == set(KEYS)
    assert all(a != b for a, b in zip(picks, picks[1:], strict=False))
    # 命运红线 needs the 心动 cards: without them random skips it and a choice of it gets 经典.
    assert "thread" not in {choose("random", "", 0, rng) for _ in range(60)}
    assert choose("thread", "", 0, rng) == "classic"
    # A key from another version: random.
    assert choose("disco", "", 2, rng) in KEYS


def test_the_border_plays_the_choice_and_nothing_when_off(qapp):
    from blacklist_detect.ui_love import LoveBorder

    border = LoveBorder(random.Random(3))
    area = QApplication.primaryScreen().geometry()
    keep = QRect(area.center().x() - 150, area.bottom() - 120, 300, 80)
    cards = (QPoint(area.left() + 400, area.top() + 300), QPoint(area.left() + 900, area.top() + 500))
    border.choice = "off"
    assert border.play(area, keep, keep.center(), cards) is False
    assert not border.playing()
    border.choice = "thread"
    assert border.play(area, keep, keep.center(), cards) is True
    assert border.scene == "thread" and border.playing() and border.duration() == 5.0
    # The cards come in on the screen; the scene gets them in its own window.
    assert border._cards[0] == QPointF(cards[0] - area.topLeft())
    image = QImage(area.width() * 2, area.height() * 2, QImage.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(2.0)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    border.paint_at(painter, 2.0, area.width(), area.height())
    painter.end()
    border.stop()
    # A heavy scene on a sharp screen is drawn at one pixel per point and laid on.
    border.choice = "ice"
    border.play(area, keep)
    painter = QPainter(image)
    border.paint_at(painter, 2.0, area.width(), area.height())
    painter.end()
    assert any(buffer.devicePixelRatio() == 1.0 for buffer in border._buffers.values())
    border.stop()


def test_the_picker_saves_each_choice_and_previews_it(qapp, tmp_path, monkeypatch):
    from blacklist_detect.storage import Store
    from blacklist_detect.ui_love_pick import LoveEffectsDialog
    from blacklist_detect.ui_music import KEYS as TUNE_KEYS
    from blacklist_detect.ui_music import TUNES, WeddingMusic

    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    store = Store()
    played: list = []
    dialog = LoveEffectsDialog(store, WeddingMusic(play=played.append, rng=random.Random(1)))
    # The default first, then the others, 随机, and 无 last and in red.
    assert list(dialog.scene_buttons) == [*KEYS, "random", "off"] and KEYS[0] == "classic"
    assert list(dialog.music_buttons) == [*TUNE_KEYS, "random", "off"] and TUNE_KEYS[0] == "organ"
    assert dialog.scene_buttons["off"].text() == dialog.music_buttons["off"].text() == "无"
    assert dialog.scene_buttons["classic"].isChecked() and dialog.music_buttons["organ"].isChecked()
    assert dialog.scene_buttons["off"].property("off") is True and dialog.scene_buttons["random"].property("off") is False
    assert dialog.preview.scene == "classic"
    assert dialog.play_button.text() == "预览"
    dialog.scene_buttons["butterfly"].click()
    assert store.love_scene == "butterfly" and dialog.preview.scene == "butterfly"
    assert Store(store.root).love_scene == "butterfly"
    dialog.music_buttons["canon"].click()
    assert store.love_music == "canon" and played == [TUNES["canon"]]
    dialog.play_button.click()
    assert played[-1] == TUNES["canon"] and dialog.preview.scene == "butterfly"
    dialog.scene_buttons["off"].click()
    assert dialog.preview.scene == "" and store.love_scene == "off"
    # The preview draws the lobby whatever the choice.
    dialog.preview.grab()
    dialog.reject()
    assert played[-1] is None, "closing stops the music"
