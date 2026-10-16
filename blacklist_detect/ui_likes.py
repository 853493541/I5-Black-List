"""嘉宾: players worth meeting again, the other side of 黑名单.

A 嘉宾 player has a name, a 昵称, a 原因 and their 场景; no 标签. When a lobby has one, the app shows
the 昵称, or the full name when there is none, and greets them with one of their 场景 (any when none is
ticked; none on 不放). The list is in the player's order, newest first until they drag a row elsewhere;
when 嘉宾 with different 场景 meet in a lobby the higher one decides, unless a 组合 of theirs is all
there (guests.lobby_choice). A player is on one list at a time: a 黑名单 name is refused here, and putting
a 嘉宾 name on 黑名单 asks to move it.

The page is laid out like 黑名单 with a 场景 column for 标签: search, 添加 (添加嘉宾 or 添加组合), and
under 更多, 复制名单 and 清空嘉宾列表. On top is the 我 row, green: the player's own name and the 场景
they asked for themselves. The 组合 come next, each a row tagged 组合 with its 嘉宾 and its 场景; under
them the 嘉宾, whose rows drag into another order. 嘉宾场景 itself, on or
off, and its music are in 设置.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QStyle,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect import love_scenes
from blacklist_detect.guests import members
from blacklist_detect.match import clean_stored_name, fold, last_seen
from blacklist_detect.model import ANY_SCENE, Combo, Entry, Scenes
from blacklist_detect.ui_dialogs import (
    _danger,
    _field,
    _frame,
    _primary,
    _say_error,
)
from blacklist_detect.ui_guests import ComboDialog, ThemeField, scenes_said
from blacklist_detect.ui_icons import icon as line_icon
from blacklist_detect.ui_kit import ConfirmDialog, EmptyState, IconButton, Modal
from blacklist_detect.ui_theme import ROW_H, THEME, _page, _pointing, chinese_font
from blacklist_detect.ui_widgets import (
    NEVER_MET,
    TagPill,
    _draw_pill,
    _mark_menu_item,
    _pill_face,
    _pill_size,
    _PlainItemDelegate,
    _row_divider,
    _zh_ago,
)

# Columns of the list.
NAME, NICKNAME, THEME_COLUMN, REASON, MET = range(5)
# On a 组合 row's cells: its place in store.combos; on its 名字, its 嘉宾 as members() gives them.
COMBO_ROLE = Qt.UserRole + 1
PEOPLE_ROLE = Qt.UserRole + 2
# On each cell of the 我 row: the player's own name, empty when they have not given it.
ME_ROLE = Qt.UserRole + 3
# The tag before a 组合's 嘉宾, and why 添加组合 cannot be picked yet.
COMBO_TAG = "组合"
# The tag before the player's own name on the 我 row, and what it says before there is one.
ME_TAG = "我"
NO_NAME = "点右上角填写游戏名"
TOO_FEW = "先添加至少两位嘉宾"


def combos_met(combos: list[Combo], likes: list[Entry], scans: list[dict]) -> dict[int, str]:
    """When all of each 组合's 嘉宾 were last in one record, by its place in combos. Records are newest
    first, so the first record that holds them all is the latest. Seats are matched against every
    嘉宾, as the lobby check does, so a seat that is another 嘉宾 is not taken for one of a 组合's;
    a 嘉宾 since taken off the list is matched by name beside them."""
    taken = {fold(like.name) for like in likes}
    gone = {fold(name): Entry(name) for combo in combos for name in combo.names if fold(name) not in taken}
    people = [*likes, *gone.values()]
    keys = [fold(person.name) for person in people]
    wanted = [{fold(name) for name in combo.names} for combo in combos]
    found: dict[int, str] = {}
    for scan in scans:
        if len(found) == len(combos):
            break
        here = {keys[index] for index in last_seen(people, [scan])[0]}
        for number, names in enumerate(wanted):
            if number not in found and names <= here:
                found[number] = str(scan.get("at", ""))
    return found


def _paint_tagged(painter: QPainter, rect: QRect, font: QFont, tag_text: str, colors: tuple[str, str], parts: list[tuple[str, str, bool]]) -> None:
    """A tag, drawn as 黑名单 draws its tags but in the THEME colors (wash, ink) given, then words, each
    (text, the THEME color of its ink, struck out or not); cut with … where they run past the cell."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    face = _pill_face()
    painter.setFont(face)
    size = _pill_size(tag_text, QFontMetrics(face))
    tag = QRect(rect.left(), rect.top() + (rect.height() - size.height()) // 2, size.width(), size.height())
    _draw_pill(painter, tag, tag_text, True, TagPill._pad, THEME[colors[0]], THEME[colors[1]])
    x, limit = tag.right() + 1 + 6, rect.right()
    for text, ink, struck in parts:
        face = QFont(font)
        face.setStrikeOut(struck)
        metrics = QFontMetrics(face)
        painter.setFont(face)
        painter.setPen(QColor(THEME[ink]))
        wide = metrics.horizontalAdvance(text)
        if x + wide > limit:
            room = max(0, limit - x)
            painter.drawText(QRect(x, rect.top(), room, rect.height()), Qt.AlignLeft | Qt.AlignVCenter, metrics.elidedText(text, Qt.ElideRight, room))
            break
        painter.drawText(QRect(x, rect.top(), wide + 1, rect.height()), Qt.AlignLeft | Qt.AlignVCenter, text)
        x += wide
    painter.restore()


def _paint_combo_name(painter: QPainter, rect: QRect, font: QFont, people: list[tuple[str, bool]]) -> None:
    """A 组合's 名字: the blue 组合 tag, then its 嘉宾 joined by +, one since taken off the list struck
    out in gray."""
    parts: list[tuple[str, str, bool]] = []
    for index, (name, present) in enumerate(people):
        if index:
            parts.append((" + ", "text", False))
        parts.append((name, "text" if present else "muted", not present))
    _paint_tagged(painter, rect, font, COMBO_TAG, ("blue_wash", "blue"), parts)


def _paint_me_name(painter: QPainter, rect: QRect, font: QFont, name: str) -> None:
    """The 我 row's 名字: the green 我 tag, then the player's own name, or where to fill it in. The row is
    green_wash already, so the tag is a chip of the card's own color to stand out on it."""
    _paint_tagged(painter, rect, font, ME_TAG, ("surface", "green"), [(name, "text", False) if name else (NO_NAME, "muted", False)])


class _GuestDelegate(_PlainItemDelegate):
    """The list's cells: a 组合 row's 名字 painted with its tag and its 嘉宾, the 我 row on green."""

    def paint(self, painter, option, index) -> None:  # noqa: ANN001
        people = index.data(PEOPLE_ROLE)
        me = index.data(ME_ROLE)
        if not people and me is None:
            super().paint(painter, option, index)
            return
        view = self.parent()
        drawn = QStyleOptionViewItem(option)
        self.initStyleOption(drawn, index)
        drawn.state = drawn.state & ~QStyle.State_HasFocus
        drawn.text = ""
        if me is None:
            view.style().drawControl(QStyle.CE_ItemViewItem, drawn, painter, view)
        else:
            painter.fillRect(option.rect, QColor(THEME["green_hover" if option.state & QStyle.State_Selected else "green_wash"]))
        # Where the cell's words would start, so the tag lines up with the 嘉宾 names under it.
        words = view.style().subElementRect(QStyle.SE_ItemViewItemText, drawn, view)
        if people:
            _paint_combo_name(painter, words, drawn.font, people)
        elif index.column() == NAME:
            _paint_me_name(painter, words, drawn.font, me)
        elif text := str(index.data() or ""):
            # Inset as the style insets a cell's words, so they line up with the column's.
            margin = view.style().pixelMetric(QStyle.PM_FocusFrameHMargin, None, view) + 1
            words.adjust(margin, 0, -margin, 0)
            painter.save()
            painter.setFont(drawn.font)
            painter.setPen(QColor(THEME["text"]))
            shown = QFontMetrics(drawn.font).elidedText(text, Qt.ElideRight, words.width())
            painter.drawText(words, Qt.AlignLeft | Qt.AlignVCenter, shown)
            painter.restore()
        _row_divider(painter, option.rect)


class _GuestTable(QTableWidget):
    """The 嘉宾 list, whose 嘉宾 rows can be dragged into another order. moved(row, to) says which row
    went where, as shown; the page moves the 嘉宾 and redraws, so the table moves nothing itself.
    The first `fixed` rows are the 我 row and the 组合: they don't drag, and nothing is dropped among them."""

    moved = Signal(int, int)

    def __init__(self) -> None:
        super().__init__(0, 5)
        self.fixed = 0
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)

    def _drop_row(self, event) -> int:  # noqa: ANN001
        under = self.indexAt(event.position().toPoint())
        return under.row() if under.isValid() else self.rowCount() - 1

    def dragMoveEvent(self, event) -> None:  # noqa: ANN001
        if self._drop_row(event) < self.fixed:
            event.ignore()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: ANN001
        row = self.currentRow()
        to = self._drop_row(event)
        # The table keeps its rows; the page redraws them in the new order.
        event.setDropAction(Qt.IgnoreAction)
        event.accept()
        if row >= self.fixed and to >= self.fixed and row != to:
            self.moved.emit(row, to)


class LikeDialog(Modal):
    """One 嘉宾 player: 名字, a 昵称 to show for them, the 场景 that greet them, and why."""

    def __init__(
        self,
        name: str = "",
        nickname: str = "",
        reason: str = "",
        allow_delete: bool = False,
        scenes: Scenes = ANY_SCENE,
        music=None,  # noqa: ANN001
        taken: frozenset[str] | set[str] = frozenset(),
        blacklisted: frozenset[str] | set[str] = frozenset(),
        parent=None,  # noqa: ANN001
    ) -> None:
        super().__init__(parent)
        # Folded names already on 嘉宾. Saving one of them again would make a second row.
        self.taken = frozenset(taken)
        # Folded names on 黑名单: a player is on one list, and 黑名单 is not moved to 嘉宾.
        self.blacklisted = frozenset(blacklisted)
        self.name = name
        self.nickname = nickname
        self.detail = reason
        self.scenes = scenes
        self.deleted = False
        layout = _frame(self, "编辑嘉宾" if allow_delete else "添加嘉宾")
        self.card.setFixedWidth(520)
        self.name_edit = QLineEdit(name)
        self.name_error = _field(layout, "名字", self.name_edit)
        self.name_edit.textChanged.connect(self._clear_name_error)
        self.nickname_edit = QLineEdit(nickname)
        self.nickname_edit.setPlaceholderText("遇到时显示的名字")
        _field(layout, "昵称", self.nickname_edit)
        self.detail_edit = QPlainTextEdit()
        self.detail_edit.setPlainText(reason)
        self.detail_edit.setTabChangesFocus(True)
        self.detail_edit.setFixedHeight(self.fontMetrics().lineSpacing() * 2 + 18)
        _field(layout, "原因", self.detail_edit)
        self.theme_field = ThemeField(scenes, name, music)
        _field(layout, "场景", self.theme_field)
        remove = _danger("删除", self._delete) if allow_delete else None
        self.footer(_primary("保存" if allow_delete else "添加", self._accept), left=remove)
        self.name_edit.returnPressed.connect(self._accept)
        self.nickname_edit.returnPressed.connect(self._accept)
        self._before = (name, nickname, reason, self.theme_field.value())
        _pointing(self)

    def _clear_name_error(self, _text: str) -> None:
        _say_error(self.name_error, "")

    def has_changes(self) -> bool:
        now = (self.name_edit.text(), self.nickname_edit.text(), self.detail_edit.toPlainText(), self.theme_field.value())
        return now != self._before

    def _accept(self) -> None:
        key = fold(clean_stored_name(self.name_edit.text()))
        if not self.name_edit.text().strip():
            problem = "请填写名字"
        elif not key:
            problem = "名字里要有文字或数字"
        elif key in self.taken:
            problem = "已经是嘉宾了"
        elif key in self.blacklisted:
            problem = "已经在黑名单里了"
        else:
            problem = ""
        if problem:
            _say_error(self.name_error, problem)
            return
        self.name = self.name_edit.text()
        self.nickname = self.nickname_edit.text()
        self.detail = self.detail_edit.toPlainText()
        self.scenes = self.theme_field.value()
        self.deleted = False
        self.accept()

    def _delete(self) -> None:
        self.deleted = True
        self.accept()


def share_likes(likes: list[Entry]) -> str:
    """嘉宾 as 名字（原因）, one per line: the shape 批量导入 reads. A 昵称 is one's own; it stays."""
    return "\n".join(f"{like.name}（{like.reason}）" if like.reason else like.name for like in likes)


class LikesPage(QWidget):
    """The 嘉宾 page. It changes only the store; changed() tells the window to redraw the rest."""

    changed = Signal()

    def __init__(self, store, say, parent: QWidget | None = None, music=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.store = store
        self._say = say
        # The scenes' music, for ▶ on a 嘉宾's or a 组合's 场景.
        self.music = music
        self._met_cache: tuple | None = None
        outer = QVBoxLayout(self)
        _page(outer)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索")
        self.search.setAccessibleName("搜索名字、昵称或原因")
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(360)
        self.search_icon = self.search.addAction(line_icon("search", 16, THEME["muted"]), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self.refresh)
        toolbar.addWidget(self.search, 1)
        toolbar.addStretch(1)
        self.add_button = QPushButton("添加")
        self.add_button.setObjectName("primary")
        self.add_button.clicked.connect(self._open_add)
        self.toolbar_buttons = (self.add_button,)
        toolbar.addWidget(self.add_button)
        # 添加: a 嘉宾, or a 组合 of them, who all in one lobby get 场景 of their own.
        self.add_menu = QMenu(self)
        self.add_menu.setToolTipsVisible(True)
        self.add_like_action = self.add_menu.addAction("添加嘉宾", self.add_one)
        _mark_menu_item(self.add_like_action, "heart")
        self.add_combo_action = self.add_menu.addAction("添加组合", self.add_combo)
        _mark_menu_item(self.add_combo_action, "users")
        self.more_button = IconButton("more", "更多")
        self.more_menu = QMenu(self)
        self.copy_action = self.more_menu.addAction("复制名单", self.copy_list)
        _mark_menu_item(self.copy_action, "copy")
        self.more_menu.addSeparator()
        self.clear_action = self.more_menu.addAction("清空嘉宾列表", self.clear)
        _mark_menu_item(self.clear_action, "delete")
        self.more_button.clicked.connect(self._open_more)
        toolbar.addWidget(self.more_button)
        outer.addLayout(toolbar)
        self.table = _GuestTable()
        self.table.moved.connect(self._moved)
        self.table.setObjectName("likes")
        self.table.setAccessibleName("嘉宾列表")
        self.table.setHorizontalHeaderLabels(["名字", "昵称", "场景", "原因", "最近遇到"])
        head = self.table.horizontalHeader()
        head.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        head.setHighlightSections(False)
        # 场景 as wide as the longest scene name or word for several and the cell's padding: 毛茸茸保护协会
        # is never cut.
        metrics = QFontMetrics(chinese_font())
        words = [name for _key, name in love_scenes.SCENES] + ["随机", "不放", f"{len(love_scenes.SCENES)}个场景"]
        theme_width = max(110, max(metrics.horizontalAdvance(word) for word in words) + 2 * 12 + 16)
        for column, width in ((NAME, 200), (NICKNAME, 140), (THEME_COLUMN, theme_width), (MET, 120)):
            head.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(column, width)
        head.setSectionResizeMode(REASON, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(ROW_H)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setItemDelegate(_GuestDelegate(self.table))
        self.table.setCursor(Qt.PointingHandCursor)
        self.table.cellClicked.connect(self._edit_row)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._row_menu)
        self.table.installEventFilter(self)
        outer.addWidget(self.table, 1)
        self.empty = EmptyState("heart", "嘉宾列表还是空的")
        self.empty_add_button = self.empty.add_action(QPushButton("添加"))
        self.empty_add_button.setObjectName("primary")
        self.empty_add_button.clicked.connect(self._open_add)
        outer.addWidget(self.empty, 1)
        self.refresh()

    # The list -----------------------------------------------------------------------------

    def _met(self) -> tuple[dict[int, str], dict[int, str]]:
        """最近遇到 of each 嘉宾 and of each 组合, by their places in the store."""
        likes, combos, scans = self.store.likes, self.store.combos, self.store.scans
        key = (
            tuple(like.name for like in likes),
            tuple(combos),
            tuple((str(s.get("at", "")), len(s.get("names", []))) for s in scans),
            id(scans),
        )
        if self._met_cache is None or self._met_cache[0] != key:
            self._met_cache = (key, (last_seen(likes, scans)[0], combos_met(combos, likes, scans)))
        return self._met_cache[1]

    def _shown_rows(self) -> list[int]:
        query = self.search.text().strip()
        folded = fold(query)
        rows = []
        for index in range(len(self.store.likes) - 1, -1, -1):
            like = self.store.likes[index]
            text = f"{like.nickname} {like.reason}"
            if query and folded not in fold(like.name) and query not in text:
                continue
            rows.append(index)
        return rows

    def _shows_me(self) -> bool:
        """The 我 row: on top once the list has anyone, while nothing is searched for or the search is in
        the player's own name."""
        if not self.store.likes and not self.store.combos:
            return False
        query = fold(self.search.text().strip())
        return not query or query in fold(self.store.player_name)

    def _me_row(self) -> None:
        """The 我 row: the player's own name (or where to fill it in) under 名字 and on across 昵称, and
        the 场景 they asked for themselves. It neither drags nor takes a drop, and has no 编辑 or 删除."""
        name = self.store.player_name
        self.table.setSpan(0, NAME, 1, 2)
        for column, text in enumerate((name or NO_NAME, "", scenes_said(self.store.me), "", "")):
            item = QTableWidgetItem(text)
            item.setData(ME_ROLE, name)
            item.setFlags(item.flags() & ~Qt.ItemIsDragEnabled & ~Qt.ItemIsDropEnabled)
            if column == NAME:
                item.setToolTip(f"{ME_TAG}：{name}" if name else NO_NAME)
            self.table.setItem(0, column, item)

    def _shown_combos(self) -> list[int]:
        """The 组合 in their order, filtered by the search: any of their 嘉宾's name or 昵称."""
        query = self.search.text().strip()
        if not query:
            return list(range(len(self.store.combos)))
        folded = fold(query)
        nicknames = {fold(like.name): like.nickname for like in self.store.likes}
        return [
            number
            for number, combo in enumerate(self.store.combos)
            if any(folded in fold(name) or query in nicknames.get(fold(name), "") for name in combo.names)
        ]

    def _combo_row(self, row: int, number: int, met: dict[int, str]) -> None:
        """A 组合's row: the 组合 tag and its 嘉宾 under 名字 and on across 昵称, which a 组合 has none of,
        its 场景, and when they were last all met."""
        combo = self.store.combos[number]
        self.table.setSpan(row, NAME, 1, 2)
        people = members(combo, self.store.likes)
        who = " + ".join(name for name, _present in people)
        cells = (who, "", scenes_said(combo.scenes), "", _zh_ago(met[number]) if number in met else NEVER_MET)
        for column, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setData(COMBO_ROLE, number)
            # A 组合 keeps its place at the top: it neither drags nor takes a drop.
            item.setFlags(item.flags() & ~Qt.ItemIsDragEnabled & ~Qt.ItemIsDropEnabled)
            if column == NAME:
                item.setData(PEOPLE_ROLE, people)
                item.setToolTip(f"{COMBO_TAG}：{who}")
            if column == MET:
                item.setForeground(QColor(THEME["muted"]))
            self.table.setItem(row, column, item)

    def refresh(self) -> None:
        """Redraw from the store: the 我 row on top, the 组合 under it, then the 嘉宾 in the list's order
        (the last saved on top), filtered by the search. 嘉宾 rows drag into another order while nothing
        is searched for."""
        count = len(self.store.likes)
        me = int(self._shows_me())
        combos = self._shown_combos()
        rows = self._shown_rows()
        met, combo_met = self._met()
        table = self.table
        table.clearSpans()
        table.setRowCount(me + len(combos) + len(rows))
        table.fixed = me + len(combos)
        if me:
            self._me_row()
        for row, number in enumerate(combos, me):
            self._combo_row(row, number, combo_met)
        for row, index in enumerate(rows, me + len(combos)):
            like = self.store.likes[index]
            cells = (like.name, like.nickname, scenes_said(like.scenes), like.reason, _zh_ago(met[index]) if index in met else NEVER_MET)
            for column, text in enumerate(cells):
                item = QTableWidgetItem(" ".join(text.split()) if column == REASON else text)
                item.setData(Qt.UserRole, index)
                if column == REASON and text:
                    item.setToolTip(text)
                if column in (NICKNAME, MET):
                    item.setForeground(QColor(THEME["rose"] if column == NICKNAME else THEME["muted"]))
                table.setItem(row, column, item)
        has_any = count > 0 or bool(self.store.combos)
        shown = bool(me or combos or rows)
        for widget in (*self.toolbar_buttons, self.search):
            widget.setVisible(has_any or (widget is self.search and bool(self.search.text())))
        # 复制名单 and 清空嘉宾列表 are for 嘉宾: with 组合 alone they would have nothing to do.
        self.more_button.setVisible(count > 0)
        if has_any and not shown:
            self.empty.set_icon("search")
            self.empty.set_text(f"没有找到「{self.search.text().strip()}」")
        else:
            self.empty.set_icon("heart")
            self.empty.set_text("嘉宾列表还是空的")
        self.empty_add_button.setVisible(not has_any)
        table.setVisible(shown)
        self.empty.setVisible(not shown)
        # Only the whole list has an order to change.
        table.setDragEnabled(not self.search.text().strip() and len(rows) > 1)

    def _index_at(self, row: int) -> int:
        """The 嘉宾 a row shows, by its place in the store; -1 for the 我 row, a 组合's row or none."""
        item = self.table.item(row, NAME)
        return int(item.data(Qt.UserRole)) if item is not None and item.data(Qt.UserRole) is not None else -1

    def _combo_at(self, row: int) -> int:
        """The 组合 a row shows, by its place in the store; -1 for the 我 row, a 嘉宾's row or none."""
        item = self.table.item(row, NAME)
        return int(item.data(COMBO_ROLE)) if item is not None and item.data(COMBO_ROLE) is not None else -1

    def _is_me(self, row: int) -> bool:
        item = self.table.item(row, NAME)
        return item is not None and item.data(ME_ROLE) is not None

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001
        if watched is self.table and event.type() == QEvent.Type.KeyPress:
            row = self.table.currentRow()
            if self._is_me(row) and event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.edit_me()
                return True
            index, number = self._index_at(row), self._combo_at(row)
            edit, delete = (self.edit, self.delete) if index >= 0 else (self.edit_combo, self.delete_combo)
            if max(index, number) >= 0 and event.key() in (Qt.Key_Return, Qt.Key_Enter):
                edit(max(index, number))
                return True
            if max(index, number) >= 0 and event.key() == Qt.Key_Delete:
                delete(max(index, number))
                return True
        return super().eventFilter(watched, event)

    # Actions ------------------------------------------------------------------------------

    def _taken(self, skip: int = -1) -> frozenset[str]:
        return frozenset(fold(like.name) for index, like in enumerate(self.store.likes) if index != skip)

    def _blacklisted(self) -> frozenset[str]:
        return frozenset(fold(entry.name) for entry in self.store.entries)

    def add_one(self, name: str = "") -> None:
        dialog = LikeDialog(
            name if isinstance(name, str) else "",
            music=self.music,
            taken=self._taken(),
            blacklisted=self._blacklisted(),
            parent=self.window(),
        )
        if dialog.exec() != QDialog.Accepted or dialog.deleted:
            return
        before = (self.store.snapshot_likes(), self.store.snapshot_entries())
        like = self.store.add_like(dialog.name, dialog.nickname, dialog.detail, dialog.scenes)
        if like is None:
            return
        self._done(f"「{like.shown()}」加进嘉宾了", before)

    def edit(self, index: int) -> None:
        if not 0 <= index < len(self.store.likes):
            return
        like = self.store.likes[index]
        dialog = LikeDialog(
            like.name, like.nickname, like.reason, allow_delete=True,
            scenes=like.scenes, music=self.music,
            taken=self._taken(skip=index),
            blacklisted=self._blacklisted(), parent=self.window(),
        )
        if dialog.exec() != QDialog.Accepted:
            return
        if dialog.deleted:
            self.delete(index)
            return
        self.store.update_like(index, dialog.name, dialog.nickname, dialog.detail, dialog.scenes)
        self._met_cache = None
        self.refresh()
        self.changed.emit()

    def edit_me(self) -> None:
        """The 我 row clicked: it has no 编辑嘉宾. The 场景 the player asks for themselves will be chosen
        here."""

    def _edit_row(self, row: int, _column: int = 0) -> None:
        number = self._combo_at(row)
        if self._is_me(row):
            self.edit_me()
        elif number >= 0:
            self.edit_combo(number)
        else:
            self.edit(self._index_at(row))

    def _combo_editor(self, combo: Combo | None = None) -> ComboDialog:
        return ComboDialog(self.store.likes, combo, parent=self.window(), music=self.music)

    def add_combo(self, _checked: bool = False) -> None:
        """添加组合: two or more 嘉宾 and the 场景 that greet them all in one lobby."""
        if len(self.store.likes) < 2:
            self._say(TOO_FEW)
            return
        dialog = self._combo_editor()
        if dialog.exec() != QDialog.Accepted or dialog.combo is None:
            return
        self.store.set_combos([*self.store.combos, dialog.combo])
        self.refresh()
        self.changed.emit()

    def edit_combo(self, number: int) -> None:
        if not 0 <= number < len(self.store.combos):
            return
        dialog = self._combo_editor(self.store.combos[number])
        if dialog.exec() != QDialog.Accepted:
            return
        if dialog.deleted:
            self.delete_combo(number)
            return
        combos = list(self.store.combos)
        combos[number] = dialog.combo
        self.store.set_combos(combos)
        self.refresh()
        self.changed.emit()

    def delete_combo(self, number: int) -> None:
        if not 0 <= number < len(self.store.combos):
            return
        before = list(self.store.combos)
        who = " + ".join(name for name, _present in members(before[number], self.store.likes))
        self.store.set_combos(before[:number] + before[number + 1 :])
        self.refresh()
        self.changed.emit()
        self._say(f"已删除组合「{who}」", undo=lambda: self._combos_back(before))

    def _combos_back(self, before: list[Combo]) -> None:
        self.store.set_combos(before)
        self.refresh()
        self.changed.emit()
        self._say("已撤销")

    def _moved(self, row: int, to: int) -> None:
        """A row dragged to another place: the 嘉宾 there now decides before the ones below it."""
        index, target = self._index_at(row), self._index_at(to)
        if index >= 0 and target >= 0 and self.store.move_like(index, target):
            self.refresh()
            self.table.selectRow(to)

    def to_top(self, index: int) -> None:
        """置顶: this 嘉宾 first, deciding before every other."""
        if self.store.move_like(index, len(self.store.likes) - 1):
            self.refresh()

    def delete(self, index: int) -> None:
        if not 0 <= index < len(self.store.likes):
            return
        name = self.store.likes[index].shown()
        before = (self.store.snapshot_likes(), self.store.snapshot_entries())
        self.store.remove_like(index)
        self._done(f"已删除「{name}」", before)

    def copy_list(self) -> None:
        count = len(self.store.likes)
        if not count:
            return
        QApplication.clipboard().setText(share_likes(self.store.likes))
        self._say(f"已复制 {count} 人")

    def clear(self) -> None:
        count = len(self.store.likes)
        if not count or not ConfirmDialog.ask(self.window(), "清空嘉宾", f"将删除 {count} 位嘉宾，确定清空吗？", "清空", danger=True):
            return
        before = (self.store.snapshot_likes(), self.store.snapshot_entries())
        self.store.clear_likes()
        self._done(f"已清空 {count} 人", before)

    def _done(self, text: str, before) -> None:  # noqa: ANN001
        """After a change: redraw, tell the window, and offer 撤销."""
        self._met_cache = None
        self.refresh()
        self.changed.emit()
        self._say(text, undo=lambda: self._put_back(before))

    def _put_back(self, before) -> None:  # noqa: ANN001
        likes, entries = before
        self.store.restore_likes(likes)
        if [entry.name for entry in entries] != [entry.name for entry in self.store.entries]:
            self.store.restore_entries(entries)
        self._met_cache = None
        self.refresh()
        self.changed.emit()
        self._say("已撤销")

    def _open_more(self) -> None:
        button = self.more_button
        self.more_menu.popup(button.mapToGlobal(button.rect().bottomRight()) - QPoint(self.more_menu.sizeHint().width(), -4))

    def _ready_add_menu(self) -> None:
        """添加组合 waits for two 嘉宾 to pick from, and says so."""
        enough = len(self.store.likes) >= 2
        self.add_combo_action.setEnabled(enough)
        self.add_combo_action.setToolTip("" if enough else TOO_FEW)

    def _open_add(self) -> None:
        """添加, in the toolbar or on the empty list: 添加嘉宾 or 添加组合, under the button."""
        button = self.empty_add_button if self.add_button.isHidden() else self.add_button
        self._ready_add_menu()
        self.add_menu.popup(button.mapToGlobal(button.rect().bottomLeft()) + QPoint(0, 4))

    def _row_menu(self, pos) -> None:  # noqa: ANN001
        row = self.table.rowAt(pos.y())
        index, number = self._index_at(row), self._combo_at(row)
        if number >= 0:
            items = (("编辑", "combo_edit", number), (None, None, -1), ("删除", "combo_delete", number))
        elif index >= 0:
            top = index == len(self.store.likes) - 1
            items = (
                ("编辑", "edit", index),
                ("复制名字", "copy", index),
                *(() if top else (("置顶", "top", index),)),
                (None, None, -1),
                ("删除", "delete", index),
            )
        else:
            return
        menu = QMenu(self)
        for text, kind, place in items:
            if text is None:
                menu.addSeparator()
                continue
            action = menu.addAction(text)
            action.setData((kind, place))
            _mark_menu_item(action)
        menu.triggered.connect(self._on_menu)
        menu.aboutToHide.connect(menu.deleteLater)
        menu.popup(self.table.viewport().mapToGlobal(pos))

    def _on_menu(self, action) -> None:  # noqa: ANN001
        kind, index = action.data()
        {
            "edit": self.edit,
            "copy": self._copy,
            "top": self.to_top,
            "delete": self.delete,
            "combo_edit": self.edit_combo,
            "combo_delete": self.delete_combo,
        }[kind](index)

    def _copy(self, index: int) -> None:
        if 0 <= index < len(self.store.likes):
            QApplication.clipboard().setText(self.store.likes[index].name)
            self._say(f"已复制「{self.store.likes[index].name}」")

    def restyle(self) -> None:
        """After a theme change: icons in the new colors, the list redrawn."""
        self.more_button.refresh()
        self.empty.refresh()
        self.search_icon.setIcon(line_icon("search", 16, THEME["muted"]))
        for action in (self.copy_action, self.clear_action, self.add_like_action, self.add_combo_action):
            _mark_menu_item(action, str(action.property("icon_name") or ""))
        self.refresh()


__all__ = ["LikeDialog", "LikesPage", "share_likes"]
