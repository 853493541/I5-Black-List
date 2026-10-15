"""风翻笔记 (love_scenes/notebook), a concept not yet in 设置: it plays through over the lobby and other
window shapes, keeps the button and the names clear, draws its pencil work sharp on its own, and
draws the 嘉宾 marks itself."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPointF, QRect, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from blacklist_detect import love_scenes  # noqa: E402
from blacklist_detect.love_scenes import Stage, sample_stage  # noqa: E402

# A moment in each part: the breeze, the riffle, the sweep, the sketches, the leaves, the gust, the end.
MOMENTS = (0.0, 0.3, 0.9, 1.4, 1.7, 2.2, 2.8, 3.5, 3.9, 4.3, 4.7, 5.0)


@pytest.fixture(scope="module")
def qapp():  # noqa: ANN201
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def scene(qapp):  # noqa: ANN001, ANN201
    stage = sample_stage()
    return stage, love_scenes.load("notebook").make(stage)


def _shot(stage: Stage, paint, t: float, sharp: bool | None = None) -> QImage:  # noqa: ANN001
    image = QImage(round(stage.width), round(stage.height), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    if sharp is None:
        paint(painter, t)
    elif sharp:
        paint.sharp(painter, t)
    else:
        paint(painter, t, sharp=False)
    painter.end()
    return image


def _most(image: QImage, rect: QRectF, step: int = 3) -> int:
    """The most opaque pixel in rect, looking at a grid of them."""
    box = rect.toRect()
    return max(image.pixelColor(x, y).alpha() for x in range(box.left(), box.right(), step) for y in range(box.top(), box.bottom(), step))


def test_it_plays_through_and_keeps_the_button_bare(scene):
    stage, paint = scene
    module = love_scenes.load("notebook")
    assert module.DURATION == 5.0
    middle = stage.gap.center().toPoint()
    button = QRect(middle.x() - 60, round(stage.gap.top() + 50), 120, 20)
    drawn = 0
    for t in MOMENTS:
        shot = _shot(stage, paint, t)
        drawn += _most(shot, QRectF(shot.rect()), 9) > 0
        assert _most(shot, QRectF(button), 4) < 40, t
        # Nothing at all in the gap but its very edge.
        assert _most(shot, stage.gap.adjusted(30, 30, -30, -30), 5) < 40, t
    assert drawn >= len(MOMENTS) - 2, "something shows while it plays"


def test_the_washes_stay_thin_over_the_names(scene):
    """Over a name, nothing translucent keeps more than about 12%."""
    stage, paint = scene
    for t in (1.2, 1.5, 1.8, 2.1, 2.7, 3.4, 3.6, 3.8, 4.0, 4.2):
        washes = _shot(stage, paint, t, sharp=False)
        for name in stage.names():
            assert _most(washes, name, 2) <= 0.14 * 255, (t, name)


def test_the_pencil_work_is_drawn_sharp_on_its_own(scene):
    """paint(sharp=False) draws only the washes; paint.sharp the line work, crisp on top."""
    stage, paint = scene
    whole = _shot(stage, paint, 2.8)
    washes = _shot(stage, paint, 2.8, sharp=False)
    lines = _shot(stage, paint, 2.8, sharp=True)
    assert whole != washes and whole != lines
    assert _most(lines, QRectF(lines.rect()), 5) > 200, "the leaves are solid paper"
    assert _most(_shot(stage, paint, 0.3, sharp=False), QRectF(washes.rect()), 9) > 60, "the breeze brings watercolour ribbons"


def test_it_fits_another_window_shape(qapp):
    """A windowed emulator is narrower and taller than the lobby the scene was drawn on."""
    stage = Stage(900, 640, QRectF(300, 540, 330, 100), badge=QPointF(600, 580))
    paint = love_scenes.load("notebook").make(stage)
    for t in (0.5, 1.5, 2.6, 3.7, 4.6):
        shot = _shot(stage, paint, t)
        assert _most(shot, QRectF(stage.gap.center().x() - 50, stage.gap.top() + 40, 100, 20), 4) < 40, t


def test_it_draws_the_marks_itself(qapp):
    from blacklist_detect.ui_love_pick import SampleMarks
    from blacklist_detect.ui_overlay import love_look

    module = love_scenes.load("notebook")
    assert love_look("notebook").marks == "notebook" and module.MARKS_ANIMATED
    marks = SampleMarks("notebook")
    assert marks.moving
    first = [pixmap.toImage() for pixmap, _at in marks.at(0.0)]
    later = [pixmap.toImage() for pixmap, _at in marks.at(0.25)]
    assert len(first) == 3 and all(_most(image, QRectF(image.rect()), 3) > 0 for image in first)
    assert any(a != b for a, b in zip(first, later, strict=True)), "the pencil lines boil"
    marks.close()
    lead = module.lead(18, 1)
    assert lead.devicePixelRatio() >= 2 and not lead.isNull()


def test_no_paper_rests_on_a_name(qapp):
    """A flying leaf crosses a name row straight and fast: looked at every 0.05 s, none lies over a
    name for more than 0.2 s."""
    import math

    from PySide6.QtGui import QPolygonF

    from blacklist_detect.love_scenes import notebook

    stage = sample_stage()
    plan = notebook._Plan(stage)
    tooth = notebook._Tooth(plan.u)
    leaves = notebook._leaves(plan, notebook._Book(plan, tooth), tooth)
    names = [QPolygonF(QRectF(name)) for name in stage.names()]
    for leaf in leaves:
        over = [0] * len(names)
        for step in range(round(notebook.DURATION / 0.05) + 1):
            tq = math.floor(step * 0.05 * notebook.TWOS) / notebook.TWOS
            paper = QPolygonF(leaf.corners(tq))
            for index, name in enumerate(names):
                over[index] = over[index] + 1 if len(paper) and paper.intersects(name) else 0
                assert over[index] * 0.05 <= 0.2 + 1e-6, (step * 0.05, stage.names()[index])
