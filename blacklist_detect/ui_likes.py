"""心动: players worth meeting again, the other side of 黑名单.

A 心动 player has a name, a 昵称, and a 原因; no 标签. When a lobby has one, the app shows
the 昵称, or the full name when there is none. A player is on one list at a time: putting a
黑名单 name on 心动, or the other way round, asks to move it.

The page is laid out like 黑名单 without the 标签 column: search, 批量导入, 添加, and under
更多, 复制名单 and 清空心动列表.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect.match import clean_stored_name, fold, last_seen
from blacklist_detect.model import Entry
from blacklist_detect.ui_dialogs import (
    BatchAddDialog,
    _danger,
    _field,
    _footer,
    _frame,
    _primary,
    _say_error,
)
from blacklist_detect.ui_icons import icon as line_icon
from blacklist_detect.ui_kit import ConfirmDialog, EmptyState, IconButton, Modal
from blacklist_detect.ui_theme import ROW_H, THEME, _page, _pointing
from blacklist_detect.ui_widgets import _mark_menu_item, _PlainItemDelegate, _zh_ago, _zh_date

# Columns of the list.
NAME, NICKNAME, REASON, MET = range(4)


class LikeDialog(Modal):
    """One 心动 player: 名字, a 昵称 to show for them, and why."""

    def __init__(
        self,
        name: str = "",
        nickname: str = "",
        reason: str = "",
        title: str = "添加",
        allow_delete: bool = False,
        added_at: str = "",
        taken: frozenset[str] | set[str] = frozenset(),
        parent=None,  # noqa: ANN001
    ) -> None:
        super().__init__(parent)
        # Folded names already on 心动. Saving one of them again would make a second row.
        self.taken = frozenset(taken)
        self.name = name
        self.nickname = nickname
        self.detail = reason
        self.deleted = False
        layout = _frame(self, title)
        self.name_edit = QLineEdit(name)
        added_on = _zh_date(added_at)
        self.added_on = QLabel(added_on)
        self.added_on.setObjectName("sub")
        self.added_on.setVisible(bool(added_on))
        self.name_error = _field(layout, "名字", self.name_edit, aside=self.added_on if added_on else None)
        self.name_edit.textChanged.connect(self._clear_name_error)
        self.nickname_edit = QLineEdit(nickname)
        self.nickname_edit.setPlaceholderText("遇到时显示的名字")
        _field(layout, "昵称", self.nickname_edit)
        self.detail_edit = QPlainTextEdit()
        self.detail_edit.setPlainText(reason)
        self.detail_edit.setTabChangesFocus(True)
        self.detail_edit.setFixedHeight(self.fontMetrics().lineSpacing() * 3 + 18)
        _field(layout, "原因", self.detail_edit)
        remove = _danger("删除", self._delete) if allow_delete else None
        _footer(self, _primary("保存" if allow_delete else "添加", self._accept), left=remove)
        self.card.setMinimumWidth(440)
        self.name_edit.returnPressed.connect(self._accept)
        self.nickname_edit.returnPressed.connect(self._accept)
        self._before = (name, nickname, reason)
        _pointing(self)

    def _clear_name_error(self, _text: str) -> None:
        _say_error(self.name_error, "")

    def has_changes(self) -> bool:
        return (self.name_edit.text(), self.nickname_edit.text(), self.detail_edit.toPlainText()) != self._before

    def _accept(self) -> None:
        key = fold(clean_stored_name(self.name_edit.text()))
        if not self.name_edit.text().strip():
            problem = "请填写名字"
        elif not key:
            problem = "名字需包含文字或数字"
        elif key in self.taken:
            problem = "心动列表里已经有这个名字"
        else:
            problem = ""
        if problem:
            _say_error(self.name_error, problem)
            return
        self.name = self.name_edit.text()
        self.nickname = self.nickname_edit.text()
        self.detail = self.detail_edit.toPlainText()
        self.deleted = False
        self.accept()

    def _delete(self) -> None:
        self.deleted = True
        self.accept()


def share_likes(likes: list[Entry]) -> str:
    """心动 as 名字（原因）, one per line: the shape 批量导入 reads. A 昵称 is one's own; it stays."""
    return "\n".join(f"{like.name}（{like.reason}）" if like.reason else like.name for like in likes)


class LikesPage(QWidget):
    """The 心动 page. It changes only the store; changed() tells the window to redraw the rest."""

    changed = Signal()

    def __init__(self, store, say, parent: QWidget | None = None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.store = store
        self._say = say
        self._met_cache: tuple | None = None
        outer = QVBoxLayout(self)
        _page(outer)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索名字、昵称或原因")
        self.search.setAccessibleName("搜索名字、昵称或原因")
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(360)
        self.search_icon = self.search.addAction(line_icon("search", 16, THEME["muted"]), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self.refresh)
        toolbar.addWidget(self.search, 1)
        toolbar.addStretch(1)
        batch = QPushButton("批量导入")
        batch.clicked.connect(self.import_many)
        add = QPushButton("添加")
        add.setObjectName("primary")
        add.clicked.connect(self.add_one)
        self.toolbar_buttons = (batch, add)
        toolbar.addWidget(batch)
        toolbar.addWidget(add)
        self.more_button = IconButton("more", "更多")
        self.more_menu = QMenu(self)
        self.copy_action = self.more_menu.addAction("复制名单", self.copy_list)
        _mark_menu_item(self.copy_action, "copy")
        self.more_menu.addSeparator()
        self.clear_action = self.more_menu.addAction("清空心动列表", self.clear)
        _mark_menu_item(self.clear_action, "delete")
        self.more_button.clicked.connect(self._open_more)
        toolbar.addWidget(self.more_button)
        outer.addLayout(toolbar)
        self.table = QTableWidget(0, 4)
        self.table.setObjectName("likes")
        self.table.setAccessibleName("心动列表")
        self.table.setHorizontalHeaderLabels(["名字", "昵称", "原因", "最近遇到"])
        head = self.table.horizontalHeader()
        head.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        head.setHighlightSections(False)
        for column, width in ((NAME, 200), (NICKNAME, 160), (MET, 120)):
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
        self.table.setItemDelegate(_PlainItemDelegate(self.table))
        self.table.setCursor(Qt.PointingHandCursor)
        self.table.cellClicked.connect(self._edit_row)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._row_menu)
        self.table.installEventFilter(self)
        outer.addWidget(self.table, 1)
        self.empty = EmptyState("heart", "心动列表还是空的", "把想再一起玩的玩家加到这里。")
        self.empty_batch_button = self.empty.add_action(QPushButton("批量导入"))
        self.empty_batch_button.clicked.connect(self.import_many)
        self.empty_add_button = self.empty.add_action(QPushButton("添加"))
        self.empty_add_button.setObjectName("primary")
        self.empty_add_button.clicked.connect(self.add_one)
        outer.addWidget(self.empty, 1)
        self.refresh()

    # The list -----------------------------------------------------------------------------

    def _met(self) -> dict[int, str]:
        likes, scans = self.store.likes, self.store.scans
        key = (tuple(like.name for like in likes), tuple((str(s.get("at", "")), len(s.get("names", []))) for s in scans), id(scans))
        if self._met_cache is None or self._met_cache[0] != key:
            self._met_cache = (key, last_seen(likes, scans)[0])
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

    def refresh(self) -> None:
        """Redraw from the store: newest first, filtered by the search."""
        count = len(self.store.likes)
        rows = self._shown_rows()
        met = self._met()
        table = self.table
        table.setRowCount(len(rows))
        for row, index in enumerate(rows):
            like = self.store.likes[index]
            cells = (like.name, like.nickname, like.reason, _zh_ago(met[index]) if index in met else "")
            for column, text in enumerate(cells):
                item = QTableWidgetItem(" ".join(text.split()) if column == REASON else text)
                item.setData(Qt.UserRole, index)
                if column == REASON and text:
                    item.setToolTip(text)
                if column in (NICKNAME, MET):
                    item.setForeground(QColor(THEME["rose"] if column == NICKNAME else THEME["muted"]))
                table.setItem(row, column, item)
        has_any = count > 0
        for widget in (*self.toolbar_buttons, self.more_button, self.search):
            widget.setVisible(has_any or (widget is self.search and bool(self.search.text())))
        if has_any and not rows:
            self.empty.set_icon("search")
            self.empty.set_text(f"没有找到「{self.search.text().strip()}」")
        else:
            self.empty.set_icon("heart")
            self.empty.set_text("心动列表还是空的", "把想再一起玩的玩家加到这里。")
        self.empty_batch_button.setVisible(not has_any)
        self.empty_add_button.setVisible(not has_any)
        table.setVisible(bool(rows))
        self.empty.setVisible(not rows)

    def _index_at(self, row: int) -> int:
        item = self.table.item(row, NAME)
        return int(item.data(Qt.UserRole)) if item is not None and item.data(Qt.UserRole) is not None else -1

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001
        if watched is self.table and event.type() == QEvent.Type.KeyPress:
            index = self._index_at(self.table.currentRow())
            if index >= 0 and event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.edit(index)
                return True
            if index >= 0 and event.key() == Qt.Key_Delete:
                self.delete(index)
                return True
        return super().eventFilter(watched, event)

    # Actions ------------------------------------------------------------------------------

    def _taken(self, skip: int = -1) -> frozenset[str]:
        return frozenset(fold(like.name) for index, like in enumerate(self.store.likes) if index != skip)

    def take_from_blacklist(self, name: str) -> bool:
        """A name on 黑名单 moves here only when asked. True when it is not there, or was moved."""
        index = self.store.entry_index(name)
        if index < 0:
            return True
        listed = self.store.entries[index].name
        if not ConfirmDialog.ask(self.window(), "移到心动列表", f"「{listed}」在黑名单中，要移到心动列表吗？", "移到心动列表"):
            return False
        self.store.remove_at(index)
        return True

    def add_one(self, name: str = "") -> None:
        dialog = LikeDialog(name if isinstance(name, str) else "", taken=self._taken(), parent=self.window())
        if dialog.exec() != QDialog.Accepted or dialog.deleted:
            return
        # Taken before a move off 黑名单, so 撤销 puts the name back there too.
        before = (self.store.snapshot_likes(), self.store.snapshot_entries())
        if not self.take_from_blacklist(dialog.name):
            return
        like = self.store.add_like(dialog.name, dialog.nickname, dialog.detail)
        if like is None:
            return
        self._done(f"已将「{like.shown()}」加入心动列表", before)

    def edit(self, index: int) -> None:
        if not 0 <= index < len(self.store.likes):
            return
        like = self.store.likes[index]
        dialog = LikeDialog(
            like.name, like.nickname, like.reason, title="编辑", allow_delete=True,
            added_at=like.added_at, taken=self._taken(skip=index), parent=self.window(),
        )
        if dialog.exec() != QDialog.Accepted:
            return
        if dialog.deleted:
            self.delete(index)
            return
        self.store.update_like(index, dialog.name, dialog.nickname, dialog.detail)
        self._met_cache = None
        self.refresh()
        self.changed.emit()

    def _edit_row(self, row: int, _column: int = 0) -> None:
        self.edit(self._index_at(row))

    def delete(self, index: int) -> None:
        if not 0 <= index < len(self.store.likes):
            return
        name = self.store.likes[index].shown()
        before = (self.store.snapshot_likes(), self.store.snapshot_entries())
        self.store.remove_like(index)
        self._done(f"已删除「{name}」", before)

    def import_many(self) -> None:
        dialog = BatchAddDialog(entries=self.store.likes, parent=self.window(), likes=True, elsewhere=self.store.entries)
        if dialog.exec() != QDialog.Accepted or not dialog.chosen:
            return
        before = (self.store.snapshot_likes(), self.store.snapshot_entries())
        added, merged = self.store.import_likes(dialog.chosen)
        if not added and not merged:
            self._say("这些玩家都已在心动列表中")
            return
        parts = [f"已添加 {added} 人"] if added else []
        if merged:
            parts.append(f"合并 {merged} 人")
        self._done("，".join(parts), before)

    def copy_list(self) -> None:
        count = len(self.store.likes)
        if not count:
            return
        QApplication.clipboard().setText(share_likes(self.store.likes))
        self._say(f"已复制 {count} 人，好友可在「心动」页的「批量导入」中粘贴")

    def clear(self) -> None:
        count = len(self.store.likes)
        if not count or not ConfirmDialog.ask(self.window(), "清空心动列表", f"将删除心动列表中的 {count} 人，确定清空吗？", "清空", danger=True):
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

    def _row_menu(self, pos) -> None:  # noqa: ANN001
        index = self._index_at(self.table.rowAt(pos.y()))
        if index < 0:
            return
        menu = QMenu(self)
        for text, kind in (("编辑", "edit"), ("复制名字", "copy"), (None, None), ("删除", "delete")):
            if text is None:
                menu.addSeparator()
                continue
            action = menu.addAction(text)
            action.setData((kind, index))
            _mark_menu_item(action)
        menu.triggered.connect(self._on_menu)
        menu.aboutToHide.connect(menu.deleteLater)
        menu.popup(self.table.viewport().mapToGlobal(pos))

    def _on_menu(self, action) -> None:  # noqa: ANN001
        kind, index = action.data()
        {"edit": self.edit, "copy": self._copy, "delete": self.delete}[kind](index)

    def _copy(self, index: int) -> None:
        if 0 <= index < len(self.store.likes):
            QApplication.clipboard().setText(self.store.likes[index].name)
            self._say(f"已复制「{self.store.likes[index].name}」")

    def restyle(self) -> None:
        """After a theme change: icons in the new colors, the list redrawn."""
        self.more_button.refresh()
        self.empty.refresh()
        self.search_icon.setIcon(line_icon("search", 16, THEME["muted"]))
        for action in (self.copy_action, self.clear_action):
            _mark_menu_item(action, str(action.property("icon_name") or ""))
        self.refresh()


__all__ = ["LikeDialog", "LikesPage", "share_likes"]
