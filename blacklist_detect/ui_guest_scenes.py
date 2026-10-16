"""嘉宾场景: which 场景 each 嘉宾, 组合 and 我 is greeted with, all in one dialog.

On the left everyone as the 嘉宾 list has them: 我 on top, green, then the 组合 with their blue tag, then
the 嘉宾, each with its 场景 in a word or two (scenes_said) as edited so far. A click picks one, and the
right shows theirs: 随机 (any scene, the ticks kept under it but their boxes greyed), the scenes in three
columns each with its box (several ticked, one of them each time; none ticked, 不放), and the highlighted
one playing over the sample lobby, silent (ScenePreview); ▶ plays it again from its start. A name is
highlighted by a click on 随机 too. One whose ticked scenes this version all lacks shows as 随机, as the
list says it and as it plays.

Each one's edits are kept as another is picked, and saved together by 确定, only those that differ from
what it showed; 取消, × and Esc keep none.
"""

from __future__ import annotations

from math import ceil

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect.guests import members, ticked
from blacklist_detect.love_scenes import DESIGN
from blacklist_detect.model import Combo, Scenes
from blacklist_detect.ui_dialogs import _primary
from blacklist_detect.ui_guests import scenes_said
from blacklist_detect.ui_kit import Modal, _KeyboardRing
from blacklist_detect.ui_likes import _paint_combo_name, _paint_me_name
from blacklist_detect.ui_love_pick import SceneChoice, SceneList, ScenePreview, paint_box
from blacklist_detect.ui_theme import THEME, _pointing, chinese_font

# Who is edited: ("me", 0), ("combo", its place in store.combos) or ("like", its place in store.likes).
ME = ("me", 0)
# On each row of the list: who it is, what it says of their 场景, and for a 组合 its 嘉宾 as members() gives them.
WHO_ROLE = Qt.UserRole
SAID_ROLE = Qt.UserRole + 1
PEOPLE_ROLE = Qt.UserRole + 2


class _PersonDelegate(QStyledItemDelegate):
    """A row of the list: the name, 我's and a 组合's with their tags as on the 嘉宾 page, and its 场景 at
    the right. The 我 row is green; the one picked sits in a ringed band, as a highlighted scene does."""

    H = 36
    RADIUS = 8

    def __init__(self, parent: QWidget, player_name: str) -> None:
        super().__init__(parent)
        self.player_name = player_name

    def sizeHint(self, option, _index) -> QSize:  # noqa: ANN001, N802
        return QSize(option.rect.width(), self.H)

    def paint(self, painter, option, index) -> None:  # noqa: ANN001
        kind = index.data(WHO_ROLE)[0]
        picked = bool(option.state & QStyle.State_Selected)
        band = QRectF(option.rect).adjusted(1, 1, -1, -1)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        fill = "green_hover" if kind == "me" and picked else "green_wash" if kind == "me" else "selected" if picked else ""
        if not fill and option.state & QStyle.State_MouseOver:
            fill = "hover"
        if fill:
            painter.setPen(QPen(QColor(THEME["accent_line"]), 1.5) if picked else Qt.NoPen)
            painter.setBrush(QColor(THEME[fill]))
            painter.drawRoundedRect(band, self.RADIUS, self.RADIUS)
        font = chinese_font()
        metrics = QFontMetrics(font)
        said = str(index.data(SAID_ROLE))
        words = QRect(option.rect).adjusted(10, 0, -10, 0)
        painter.setFont(font)
        painter.setPen(QColor(THEME["muted"]))
        painter.drawText(words, Qt.AlignRight | Qt.AlignVCenter, said)
        name = words.adjusted(0, 0, -(metrics.horizontalAdvance(said) + 12), 0)
        if kind == "me":
            _paint_me_name(painter, name, font, self.player_name)
        elif kind == "combo":
            _paint_combo_name(painter, name, font, index.data(PEOPLE_ROLE))
        else:
            painter.setPen(QColor(THEME["text"]))
            painter.drawText(name, Qt.AlignLeft | Qt.AlignVCenter, metrics.elidedText(index.data(Qt.DisplayRole), Qt.ElideRight, name.width()))
        painter.restore()


class _RandomBox(_KeyboardRing, QCheckBox):
    """随机, its box drawn as the grid's boxes are (filled with a ✓ when ticked), not the app's checkbox."""

    BOX = SceneChoice.BOX
    PAD = 4
    GAP = 8

    def sizeHint(self) -> QSize:
        return QSize(self.PAD + self.BOX + self.GAP + QFontMetrics(self.font()).horizontalAdvance(self.text()) + self.PAD, 28)

    def hitButton(self, pos: QPoint) -> bool:  # noqa: N802
        return self.rect().contains(pos)

    def paintEvent(self, _event) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.underMouse():
            p.fillRect(self.rect(), QColor(THEME["hover"]))
        if self.show_ring():
            p.setPen(QPen(QColor(THEME["accent_line"]), 1.5, Qt.DashLine))
            p.drawRect(QRectF(self.rect()).adjusted(1, 1, -1, -1))
        paint_box(p, QRectF(self.PAD, (self.height() - self.BOX) / 2, self.BOX, self.BOX), self.isChecked())
        p.setFont(self.font())
        p.setPen(QColor(THEME["text"]))
        p.drawText(QRect(self.PAD + self.BOX + self.GAP, 0, self.width(), self.height()), Qt.AlignLeft | Qt.AlignVCenter, self.text())
        p.end()


class GuestScenesDialog(Modal):
    """嘉宾场景, opened on who (ME, ("combo", n) or ("like", i)). value(who) is someone's 场景 as edited so
    far; 确定 saves those that changed into the store."""

    W = 250
    # The grid: three names side by side, each whole, its box clear of it.
    GRID_W = 576
    PREVIEW_W = 448
    # Five rows of scenes (up to 15) and the preview at its full size share this height: with more scenes
    # the preview gets smaller rather than the dialog taller.
    ROOM = 5 * (SceneChoice.H + SceneList.GAP) + round(PREVIEW_W * DESIGN[1] / DESIGN[0])

    def __init__(self, store, who: tuple[str, int] = ME, parent: QWidget | None = None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.store = store
        # Each one's 场景 as edited, kept only while it differs from the store's.
        self.edits: dict[tuple[str, int], Scenes] = {}
        self.who = ME
        self._loading = False
        layout = self.frame("嘉宾场景")
        row = QHBoxLayout()
        row.setSpacing(20)
        self.people = QListWidget()
        self.people.setObjectName("guestScenePeople")
        self.people.setAccessibleName("嘉宾")
        self.people.setFixedWidth(self.W)
        self.people.setMouseTracking(True)
        self.people.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.people.setItemDelegate(_PersonDelegate(self.people, store.player_name))
        for person in self._everyone():
            item = QListWidgetItem(self._name(person))
            item.setData(WHO_ROLE, person)
            item.setData(SAID_ROLE, scenes_said(self.value(person)))
            if person[0] == "combo":
                item.setData(PEOPLE_ROLE, members(store.combos[person[1]], store.likes))
            self.people.addItem(item)
        self.people.currentRowChanged.connect(self._show_person)
        row.addWidget(self.people)
        side = QVBoxLayout()
        side.setSpacing(12)
        top = QHBoxLayout()
        top.setSpacing(12)
        self.random_box = _RandomBox("随机")
        self.random_box.setToolTip("每次随机放一个场景")
        self.random_box.toggled.connect(self._random_toggled)
        top.addWidget(self.random_box)
        self.hint = QLabel("都不勾：不放")
        self.hint.setObjectName("sub")
        top.addWidget(self.hint)
        top.addStretch(1)
        side.addLayout(top)
        self.scenes = SceneList(chosen=(), columns=3, width=self.GRID_W)
        self.scenes.picked.connect(self.show_scene)
        self.scenes.chose.connect(self._edited)
        self.buttons = self.scenes.buttons
        side.addWidget(self.scenes)
        room = self.ROOM - ceil(len(self.buttons) / 3) * (SceneChoice.H + SceneList.GAP)
        self.preview = ScenePreview(self, min(self.PREVIEW_W, int(room * DESIGN[0] / DESIGN[1])), play=self.replay)
        self.play_button = self.preview.play_button
        self.play_button.setToolTip("从头播放")
        side.addWidget(self.preview, 0, Qt.AlignHCenter)
        side.addStretch(1)
        row.addLayout(side)
        layout.addLayout(row)
        cancel = QPushButton("取消")
        cancel.setAutoDefault(False)
        cancel.clicked.connect(self.reject)
        self.ok_button = _primary("确定", self._accept)
        self.footer(cancel, self.ok_button)
        _pointing(self)
        self.key = self.scenes.key
        self.preview.show_scene(self.key)
        self.select(who)

    def _everyone(self) -> list[tuple[str, int]]:
        """我, the 组合 in their order, then the 嘉宾 as the list shows them (the last saved on top)."""
        combos = [("combo", number) for number in range(len(self.store.combos))]
        return [ME, *combos, *(("like", index) for index in range(len(self.store.likes) - 1, -1, -1))]

    def _name(self, who: tuple[str, int]) -> str:
        kind, place = who
        if kind == "me":
            return self.store.player_name
        if kind == "combo":
            return " + ".join(self.store.combos[place].names)
        return self.store.likes[place].name

    def _saved(self, who: tuple[str, int]) -> Scenes:
        kind, place = who
        if kind == "me":
            return self.store.me
        return (self.store.combos if kind == "combo" else self.store.likes)[place].scenes

    def _shown(self, who: tuple[str, int]) -> Scenes:
        """Someone's 场景 as the editor shows them unedited: as saved, but one whose ticked scenes this version
        all lacks is 随机, as the list says it and as it plays."""
        saved = self._saved(who)
        if saved.keys and not saved.random and not ticked(saved):
            return Scenes(saved.keys, random=True)
        return saved

    def value(self, who: tuple[str, int]) -> Scenes:
        """Someone's 场景 as edited so far."""
        return self.edits.get(who, self._shown(who))

    def has_changes(self) -> bool:
        return bool(self.edits)

    def select(self, who: tuple[str, int]) -> None:
        """Pick this one in the list, and show their 场景; one not there (a 组合 or 嘉宾 since gone) is 我."""
        rows = [self.people.item(row).data(WHO_ROLE) for row in range(self.people.count())]
        row = rows.index(tuple(who)) if tuple(who) in rows else 0
        self.people.setCurrentRow(row)
        self._show_person(row)

    def _show_person(self, row: int) -> None:
        if row < 0:
            return
        self.who = self.people.item(row).data(WHO_ROLE)
        scenes = self.value(self.who)
        self._loading = True
        self.random_box.setChecked(scenes.random)
        self.scenes.set_chosen(scenes.keys)
        self._loading = False
        self._show_random()
        # Their first ticked in the grid plays; with none, the one shown stays.
        first = self.scenes.chosen()
        if first and first[0] != self.key:
            self.show_scene(first[0])

    def _random_toggled(self, _on: bool) -> None:
        self._show_random()
        self._edited()

    def _show_random(self) -> None:
        """随机 greys the grid's boxes, their ticks kept, and hides 都不勾：不放, which it is not; the names
        still highlight and play."""
        on = self.random_box.isChecked()
        self.scenes.set_boxes_enabled(not on)
        self.hint.setHidden(on)

    def _edited(self) -> None:
        """A box ticked or unticked: this one's 场景 as they are now, kept until 确定 unless back as shown."""
        if self._loading:
            return
        scenes = Scenes(self.scenes.chosen(), random=self.random_box.isChecked())
        saved = self._shown(self.who)
        # The same ticks in another order are no change.
        if scenes.random == saved.random and set(scenes.keys) == set(ticked(saved)):
            self.edits.pop(self.who, None)
        else:
            self.edits[self.who] = scenes
        self.people.currentItem().setData(SAID_ROLE, scenes_said(scenes))

    def show_scene(self, key: str) -> None:
        """Highlight this scene and play it over the sample lobby, silent."""
        self.scenes.select(key)
        self.key = self.scenes.key
        self.preview.show_scene(self.key)

    def replay(self) -> None:
        """▶: the highlighted scene again from its start, silent still."""
        self.preview.show_scene(self.key)

    def save(self) -> None:
        """Into the store, only those that changed: 我, the 组合 together, each 嘉宾."""
        store = self.store
        combos = list(store.combos)
        for (kind, place), scenes in self.edits.items():
            if kind == "me":
                store.set_me(scenes)
            elif kind == "combo":
                combos[place] = Combo(combos[place].names, scenes)
            else:
                like = store.likes[place]
                store.update_like(place, like.name, like.nickname, like.reason, scenes)
        if combos != store.combos:
            store.set_combos(combos)

    def _accept(self) -> None:
        self.save()
        self.accept()

    def done(self, result: int) -> None:  # noqa: A003
        self.preview.stop()
        super().done(result)


__all__ = ["ME", "GuestScenesDialog"]
