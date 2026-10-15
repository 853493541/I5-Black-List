"""嘉宾场景: the scenes, choosing one or a random one, their pictures and preview, and the 嘉宾 marks a
scene dresses or draws itself."""

import random
from dataclasses import replace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF, QRect, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from blacklist_detect import love_scenes  # noqa: E402
from blacklist_detect.love_scenes import KEYS, Stage, choose, sample_stage  # noqa: E402

# The scenes that draw the 嘉宾 marks as themes of their own.
THEMES = ("classic", "cyber", "neon", "angel", "equation", "fluffy", "claw")


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
    assert 4.0 <= love_scenes.load(key).DURATION <= 7.0
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
    # 命运红线, 雪纺, 缎带, 花雨, 纸鹤晚霞 and 蝶梦 are gone: a player who had one, or a key from another
    # version, gets 经典. 香槟 is gone too, and 天使 took its place. 经典 is the gold welcome now, and the
    # rose border that was 经典花边 is 玫瑰花边 (lace), second.
    assert KEYS == ("classic", "lace", "ice", "stars", "cyber", "neon", "angel", "equation", "fluffy", "claw")
    for gone in ("thread", "chiffon", "ribbon", "petals", "cranes", "butterfly", "disco"):
        assert choose(gone, "", rng) == "classic"
    assert choose("champagne", "", rng) == "angel"


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


def test_the_same_scene_played_again_is_not_made_again(qapp, monkeypatch):
    from blacklist_detect.ui_love import LoveBorder

    border = LoveBorder(random.Random(3))
    area = QApplication.primaryScreen().geometry()
    keep = QRect(area.center().x() - 150, area.bottom() - 120, 300, 80)
    module = love_scenes.load("stars")
    made: list[str] = []
    real = module.make
    monkeypatch.setattr(module, "make", lambda stage: made.append("stars") or real(stage))
    image = QImage(64, 36, QImage.Format_ARGB32_Premultiplied)

    def play() -> None:
        border.choice = "stars"
        border.play(area, keep, keep.center())
        painter = QPainter(image)
        border.paint_at(painter, 1.0, area.width(), area.height())
        painter.end()
        border.stop()

    # The 场景 hotkey pressed again: the same scene over the same place starts at once.
    play()
    play()
    assert made == ["stars"]
    # Elsewhere, or after another scene, it is made again; never more than two are kept.
    border.choice = "ice"
    border.play(area, keep)
    border.stop()
    assert border._made == {}
    play()
    assert made == ["stars", "stars"]
    for width in (800, 900, 1000):
        painter = QPainter(image)
        border.paint_at(painter, 1.0, width, 450)
        painter.end()
    border.choice = "stars"
    border.play(area, keep)
    border.stop()
    assert len(border._made) == 2


def test_noise_is_the_same_as_worked_out_per_pixel():
    import numpy as np

    from blacklist_detect.love_scenes.light import noise

    def per_pixel(width, height, scale, octaves, seed):  # noqa: ANN001, ANN202
        rnd = np.random.default_rng(seed)
        out = np.zeros((height, width), dtype=np.float32)
        total, amp = 0.0, 1.0
        for octave in range(octaves):
            cell = max(2.0, scale / (2 ** octave))
            grid = rnd.random((int(height / cell) + 3, int(width / cell) + 3), dtype=np.float32)
            ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
            fx, fy = xs / cell, ys / cell
            x0, y0 = fx.astype(int), fy.astype(int)
            sx, sy = fx - x0, fy - y0
            sx, sy = sx * sx * (3 - 2 * sx), sy * sy * (3 - 2 * sy)
            top = grid[y0, x0] * (1 - sx) + grid[y0, x0 + 1] * sx
            bottom = grid[y0 + 1, x0] * (1 - sx) + grid[y0 + 1, x0 + 1] * sx
            out += (top * (1 - sy) + bottom * sy) * amp
            total += amp
            amp *= 0.5
        return out / total

    # Every scene's fog, smoke and grain looks exactly as it did.
    for args in ((311, 177, 60.0, 4, 11), (90, 40, 34.0, 2, 101), (7, 3, 2.0, 2, 1), (200, 1, 3.0, 2, 4), (64, 64, 1.6, 3, 5)):
        assert np.array_equal(noise(*args), per_pixel(*args)), args


def test_every_scene_has_its_picture(qapp):
    from pathlib import Path

    from blacklist_detect.ui_guests import POSTERS, poster, thumbnail

    # build/theme_posters.py draws them; a scene added without one would show a blank thumbnail.
    assert {path.stem for path in Path(POSTERS).glob("*.jpg")} == set(KEYS)
    for key in KEYS:
        assert not poster(key).isNull(), key
    # One this version does not have shows what plays for it.
    assert poster("ribbon").cacheKey() == poster("classic").cacheKey()
    assert poster("champagne").cacheKey() == poster("angel").cacheKey()
    small = thumbnail("stars", 56)
    assert small.width() / small.devicePixelRatio() == 56


def test_the_border_settles_its_scene_before_it_plays(qapp):
    """The 嘉宾 marks are dressed for the scene before it starts: pick() settles 随机, play() keeps it."""
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
    from blacklist_detect.ui_overlay import LOOKS, ROSE_LOOK, LikeCard, love_look

    assert set(LOOKS) <= set(KEYS)
    assert len({love_look(key).card for key in KEYS}) == len(KEYS), "no two cards alike"
    assert love_look("random") is love_look("off") is love_look("chiffon") is love_look("butterfly") is love_look("classic")
    assert love_look("lace") is ROSE_LOOK
    assert love_look("champagne") is love_look("angel"), "天使 took 香槟's place"
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
    preview.show_scene("angel")
    assert preview._marks is not ice
    # One this version no longer has plays 经典, in its look.
    preview.show_scene("ribbon")
    assert preview.scene == "classic" and preview._marks is preview._marks_for("classic")
    preview.stop()


def test_a_theme_brings_its_own_look(qapp):
    from blacklist_detect.ui_overlay import LOOKS, LoveLook, love_look

    assert set(THEMES) == set(KEYS) - set(LOOKS)
    for key in THEMES:
        module = love_scenes.load(key)
        # The look comes from the scene's own LOOK, and says the scene draws the marks.
        look = love_look(key)
        assert look == replace(LoveLook(**module.LOOK), marks=key) and love_look(key) is look
    # The old scenes only color the marks; 无 and a module that is no scene get 经典's, which draws them.
    assert all(love_look(key).marks == "" for key in ("lace", "ice", "stars"))
    assert love_look("off").marks == love_look("draw").marks == "classic"


@pytest.mark.parametrize("key", THEMES)
def test_every_theme_draws_its_marks(qapp, key):
    from blacklist_detect.ui_love_pick import SampleMarks

    marks = SampleMarks(key)
    for t in (0.0, 0.7, 2.5):
        shots = marks.at(t)
        assert len(shots) == 3 and all(_drawn(pixmap.toImage()) for pixmap, _at in shots)
    marks.close()


@pytest.fixture
def theme(monkeypatch):  # noqa: ANN201
    """A scene that draws all the marks itself, each hook noting what it was given: 赛博's file,
    whatever is in it now, with these put in. Gives its look and the notes."""
    from blacklist_detect.ui_overlay import ROSE_LOOK

    module = love_scenes.load("cyber")
    calls: dict[str, list] = {"ring": [], "badge": [], "card": [], "lead": []}

    def ring(painter, cover, t):  # noqa: ANN001, ANN202
        calls["ring"].append((QRectF(cover), t))
        painter.fillRect(QRectF(cover.left() - 4, cover.top() - 4, 8, 8), QColor("#00ff00"))

    def badge(_painter, box, t):  # noqa: ANN001, ANN202
        calls["badge"].append((QRectF(box), t))

    def card(painter, rect, t):  # noqa: ANN001, ANN202
        calls["card"].append((QRectF(rect), t))
        painter.fillRect(rect, QColor("#0000ff"))

    def lead(size, index):  # noqa: ANN001, ANN202
        calls["lead"].append((size, index))
        if index:
            return None
        picture = QPixmap(round(size), round(size))
        picture.fill(QColor("#ff0000"))
        return picture

    hooks = {"ring": ring, "badge": badge, "card": card, "lead": lead}
    settings = {"CARD_TOP": 20, "CARD_PAD": (30, 10, 30, 10), "CARD_FONT": "Consolas", "MARKS_ANIMATED": True}
    for name, value in {**hooks, **settings}.items():
        monkeypatch.setattr(module, name, value, raising=False)
    return replace(ROSE_LOOK, marks="cyber"), calls


def test_a_scene_draws_the_ring_and_badge_itself(qapp, theme):
    from blacklist_detect.ui_overlay import _GLOW, ClearMark, LobbyPanel

    look, calls = theme
    panel = LobbyPanel()
    panel.setFixedSize(280, 98)
    panel.set_look(look)
    panel.set_mode("liked", "")
    panel.set_time(1.5)
    shot = panel.grab().toImage()
    assert calls["ring"] == [(QRectF(_GLOW, _GLOW, 280 - 2 * _GLOW, 98 - 2 * _GLOW), 1.5)]
    ratio = shot.devicePixelRatio()
    assert shot.pixelColor(round(_GLOW * ratio), round(_GLOW * ratio)) == QColor("#00ff00")
    # Shared with 黑名单 players, the ring is in the look's colors, as before.
    panel.set_mode("both", "")
    panel.grab()
    assert len(calls["ring"]) == 1
    # The badge need not be a heart: drawing nothing, it is nothing.
    mark = ClearMark()
    mark.set_size(80)
    mark.set_heart(True)
    mark.set_look(look)
    assert not _drawn(mark.grab().toImage())
    assert calls["badge"] == [(mark.badge(), 0.0)], "not showing, t is 0"
    # The green check is the app's own.
    mark.set_heart(False)
    assert _drawn(mark.grab().toImage()) and len(calls["badge"]) == 1
    for widget in (panel, mark):
        widget.deleteLater()


def test_a_scene_draws_the_card_and_the_names_stay_labels(qapp, theme):
    from blacklist_detect.ui_overlay import LikeCard, love_look

    look, calls = theme
    card = LikeCard()
    card.set_look(look)
    card.set_people([("心动小鹿", ()), ("心动星星", ())], 82)
    shot = card.grab().toImage()
    assert calls["card"] == [(QRectF(card.rect()), 0.0)]
    assert calls["lead"] == [(18.0, 0), (18.0, 1)], "asked for a lead before each name, at full size"
    # The names are labels in the look's ink, in the scene's face; only the first has a lead.
    names = card.findChildren(QLabel, "hitName")
    assert [name.text() for name in names] == ["心动小鹿", "心动星星"]
    assert all(look.ink in name.styleSheet() and "font-family" not in name.styleSheet() for name in names)
    assert names[0].font().families()[0] == "Consolas"
    assert len(card.findChildren(QLabel, "likeLead")) == 1 and not card.findChildren(QLabel, "likeFlower")
    # Room on top for the scene's ornament, its margins round the names, no knot and a clear body.
    assert card.layout().contentsMargins().top() == 20 and card.height() == card.body.height() + 20
    assert card.body.layout().contentsMargins().left() == 30
    assert card.knot.isHidden() and "QWidget#likeCard { background: transparent; border: none; }" in card.styleSheet()
    ratio = shot.devicePixelRatio()
    assert shot.pixelColor(round(4 * ratio), round(4 * ratio)) == QColor("#0000ff")
    # Back to a look that only colors it: as it always was.
    card.set_look(love_look("stars"))
    card.set_people([("心动小鹿", ())], 82)
    assert not card.knot.isHidden() and card.layout().contentsMargins().top() == LikeCard.top
    assert card.findChildren(QLabel, "likeFlower") and "{ background: transparent; border: none; }" not in card.styleSheet()
    assert 'font-family: "' in card.findChild(QLabel, "hitName").styleSheet()
    card.deleteLater()


def test_moving_marks_run_while_they_show(qapp, theme):
    from blacklist_detect.ui_overlay import ClearMark, LikeCard, LobbyPanel, love_look

    look, calls = theme
    panel, mark, card = LobbyPanel(), ClearMark(), LikeCard()
    mark.set_heart(True)
    panel.set_mode("liked", "")
    for widget in (panel, mark, card):
        widget.setAttribute(Qt.WA_DontShowOnScreen, True)
        widget.set_look(look)
        assert not widget._clock.running(), "not while hidden"
        widget.show()
        assert widget._clock.running()
        widget.hide()
        assert not widget._clock.running()
    # Held for a picture, it is that moment.
    card.set_time(2.25)
    card.grab()
    assert calls["card"][-1][1] == 2.25
    # A ring shared with 黑名单 players, or a look that does not move, does not tick.
    panel.set_mode("both", "")
    panel.show()
    assert not panel._clock.running()
    panel.hide()
    card.set_time(None)
    card.set_look(love_look("stars"))
    card.show()
    assert not card._clock.running()
    card.hide()
    for widget in (panel, mark, card):
        widget.deleteLater()


def test_the_preview_moves_marks_that_move(qapp, theme):
    from blacklist_detect.ui_love_pick import SampleMarks

    _look, calls = theme
    still = SampleMarks("stars")
    assert not still.moving and still.at(0.0) is still.at(1.0)
    still.close()
    moving = SampleMarks("cyber")
    moving.at(0.5)
    moving.at(1.0)
    assert moving.moving and [t for _rect, t in calls["card"]] == [0.5, 1.0]
    moving.close()
    assert moving.at(2.0), "closed, the last grab stays"


def test_the_stage_knows_where_the_names_are(qapp):
    """Where the check read the names, a scene gets them; else the lobby's layout places them."""
    stage = sample_stage()
    names = stage.names()
    assert len(names) == 12 and all(stage.gap.top() > name.bottom() for name in names)
    assert names[0].center().x() < names[5].center().x() and names[0].center().y() < names[6].center().y()
    seat = QRectF(10, 20, 30, 12)
    assert Stage(100, 60, QRectF(0, 50, 100, 10), seats=(seat,)).names() == (seat,)


def test_the_claw_rips_down_from_the_top(qapp):
    """演说家遇袭's slashes open from their top ends down: early in the strike only the top half shows."""
    from blacklist_detect.love_scenes import claw

    stage = sample_stage()
    u = stage.unit()
    centre = claw._landing(stage.width, stage.height, u)
    sprite = claw._slash_sprite(claw.LENGTH * u, claw.THICK * u, u)
    slashes = [claw._cleared(sprite, [sprite], claw._place(centre, offset, u), stage.gap, u) for offset, _delay in claw.SLASHES]

    def lit(age: float) -> tuple[int, int]:
        image = QImage(round(stage.width), round(stage.height), QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        claw._strike(painter, age, slashes, u)
        painter.end()
        shown = [y for x in range(0, image.width(), 5) for y in range(0, image.height(), 5) if image.pixelColor(x, y).alpha() > 100]
        return sum(y < centre.y() for y in shown), sum(y > centre.y() for y in shown)

    above, below = lit(claw.GROW * 0.1)
    assert above > 0 and below == 0
    above, below = lit(claw.SLASHES[-1][1] + claw.GROW)
    assert above > 0 and below > 0


@pytest.mark.parametrize("scale", [1.0, 2.0])
def test_the_conductors_badge_holds_his_role_icon(qapp, scale):
    """演说家遇袭's badge is the 指挥家's role icon from the game, centred inside the disc's rim, his
    baton's tip at its top left."""
    from blacklist_detect.love_scenes import claw

    side = 56.0
    _glow, role, tip = claw._role(side, scale)
    alpha = claw._rgba(role)[..., 3]
    ys, xs = (alpha > 128).nonzero()
    middle = role.width() / 2
    assert abs((xs.min() + xs.max() + 1) / 2 - middle) <= 1.5 and abs((ys.min() + ys.max() + 1) / 2 - middle) <= 1.5
    # All of it inside the rim, which starts at 0.4 of the side out from the middle.
    assert ((xs + 0.5 - middle) ** 2 + (ys + 0.5 - middle) ** 2).max() ** 0.5 <= side * scale * 0.4
    # Tall as the icon is: about two thirds as wide as it is high.
    assert 0.55 <= (xs.max() - xs.min()) / (ys.max() - ys.min()) <= 0.8
    x, y = round(middle + tip.x() * scale), round(middle + tip.y() * scale)
    assert tip.x() < 0 and tip.y() < 0 and alpha[y - 1 : y + 2, x - 1 : x + 2].max() > 100
