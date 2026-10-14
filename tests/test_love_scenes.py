"""心动特效: the eight scenes, choosing one or a random one, and the picker with its preview."""

import random

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF, QRect, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

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
    stage = Stage(900, 640, QRectF(300, 540, 330, 100), badge=QPointF(600, 580))
    _frames(stage, key)


def test_choosing_one_random_or_none():
    rng = random.Random(5)
    assert choose("off", "", rng) == ""
    assert choose("ice", "ice", rng) == "ice"
    picks = []
    last = ""
    for _ in range(80):
        last = choose("random", last, rng)
        picks.append(last)
    assert set(picks) == set(KEYS)
    assert all(a != b for a, b in zip(picks, picks[1:], strict=False))
    # 命运红线 and 雪纺 are gone: a player who had one, or a key from another version, gets 经典花边.
    assert "thread" not in KEYS and "chiffon" not in KEYS and len(KEYS) == 8
    assert choose("thread", "", rng) == "classic" and choose("chiffon", "", rng) == "classic"
    assert choose("disco", "", rng) == "classic"


def test_the_border_plays_the_choice_and_nothing_when_off(qapp):
    from blacklist_detect.ui_love import LoveBorder

    border = LoveBorder(random.Random(3))
    area = QApplication.primaryScreen().geometry()
    keep = QRect(area.center().x() - 150, area.bottom() - 120, 300, 80)
    border.choice = "off"
    assert border.play(area, keep, keep.center()) is False
    assert not border.playing()
    border.choice = "stars"
    assert border.play(area, keep, keep.center()) is True
    assert border.scene == "stars" and border.playing() and border.duration() == love_scenes.load("stars").DURATION
    # The heart comes in on the screen; the scene gets it in its own window.
    assert border._badge == QPointF(keep.center() - area.topLeft())
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
    # 心动人数: three choices that go together, 2人 and 2人以上 on to begin with.
    assert [box.text() for box in dialog.count_boxes.values()] == ["1人", "2人", "2人以上"]
    assert [box.isChecked() for box in dialog.count_boxes.values()] == [False, True, True]
    dialog.count_boxes[1].click()
    assert store.love_counts == (1, 2, 3) and Store(store.root).love_counts == (1, 2, 3)
    dialog.count_boxes[2].click()
    dialog.count_boxes[3].click()
    assert store.love_counts == (1,) and Store(store.root).love_counts == (1,)
    # The last one stays on: 无 turns the effect off.
    dialog.count_boxes[1].click()
    assert dialog.count_boxes[1].isChecked() and store.love_counts == (1,)
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


def test_the_border_settles_its_scene_before_it_plays(qapp):
    """The 心动 marks are dressed for the scene before it starts: pick() settles 随机, play() keeps it."""
    from blacklist_detect.ui_love import LoveBorder

    border = LoveBorder(random.Random(8))
    area = QApplication.primaryScreen().geometry()
    keep = QRect(area.center().x() - 150, area.bottom() - 120, 300, 80)
    border.choice = "random"
    for _ in range(6):
        picked = border.pick()
        assert border.pick() == picked, "asked again, the same scene"
        assert border.play(area, keep) is True and border.scene == picked
        border.stop()
    # A choice changed after the pick is what plays.
    border.choice = "ice"
    border.pick()
    border.choice = "stars"
    assert border.pick() == "stars"
    border.choice = "off"
    assert border.pick() == "" and border.play(area, keep) is False


def test_every_scene_dresses_the_marks_its_own_way(qapp):
    from blacklist_detect.ui_overlay import CLASSIC_LOOK, LOOKS, LikeCard, love_look

    assert set(LOOKS) == set(KEYS)
    assert len({look.card for look in LOOKS.values()}) == len(LOOKS), "no two cards alike"
    assert love_look("random") is love_look("off") is love_look("chiffon") is CLASSIC_LOOK
    card = LikeCard()
    card.set_look(love_look("stars"))
    card.set_people([("心动小鹿", ())], 90)
    assert "#f8e7b4" in card.findChild(QLabel, "hitName").styleSheet()
    assert "#2e2758" in card.styleSheet() and card.fade._bottom == "#1b1838"
    card.deleteLater()


def test_the_preview_shows_each_scenes_marks(qapp):
    from blacklist_detect.ui_love_pick import ScenePreview

    preview = ScenePreview()
    preview.show_scene("ice")
    ice = preview._marks
    preview.show_scene("champagne")
    assert preview._marks is not ice
    preview.show_scene("off")
    assert preview._marks is preview._marks_for("classic")
    preview.stop()
