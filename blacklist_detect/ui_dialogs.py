"""Dialogs: add and edit names, batch import, picture results, the first-run guide and 直播模式's guide."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect.importing import ELSEWHERE, MERGE, ODD, SAME, ImportRow, TagSuggestion, plan_import
from blacklist_detect.match import clean_stored_name, fold, listed_tail, split_ellipsis
from blacklist_detect.names import APP_NAME
from blacklist_detect.pipeline import CheckResult
from blacklist_detect.ui_icons import pixmap as line_pixmap
from blacklist_detect.ui_kit import Modal
from blacklist_detect.ui_theme import (
    GAP,
    SMALL_PT,
    THEME,
    _pointing,
    chinese_family,
    seat_line,
)
from blacklist_detect.ui_widgets import (
    TagPill,
    _FlowHost,
    _zh_date,
    masked_name,
    paint_tag_row,
)


def _frame(dialog: Modal, title: str) -> QVBoxLayout:
    """Every dialog starts the same way: a card with its title and a × in one row."""
    return dialog.frame(title)


def _field(layout: QVBoxLayout, label: str, widget: QWidget, aside: QWidget | None = None) -> QLabel:
    """A label above its control, and a line under it for what is wrong with it.

    With no label, the control stands alone: in a dialog with one box, the title names it.
    """
    column = QVBoxLayout()
    column.setSpacing(6)
    if label or aside is not None:
        top = QHBoxLayout()
        top.setSpacing(8)
        name = QLabel(label)
        name.setObjectName("field")
        top.addWidget(name)
        top.addStretch(1)
        if aside is not None:
            top.addWidget(aside)
        column.addLayout(top)
    column.addWidget(widget)
    error = QLabel("")
    error.setObjectName("error")
    error.hide()
    column.addWidget(error)
    layout.addLayout(column)
    return error


def _footer(dialog: Modal, *right: QPushButton, left: QPushButton | None = None) -> None:
    """The main action on the right of the footer band; anything destructive stands apart on the left.

    There is no 取消: ×, Esc and a click outside the card close without saving.
    """
    dialog.footer(*right, left=left)


def _primary(text: str, on_click) -> QPushButton:  # noqa: ANN001
    button = QPushButton(text)
    button.setObjectName("primary")
    button.setAutoDefault(True)
    button.setDefault(True)
    button.clicked.connect(on_click)
    return button


def _danger(text: str, on_click) -> QPushButton:  # noqa: ANN001
    button = QPushButton(text)
    button.setObjectName("danger")
    button.setAutoDefault(False)
    button.setDefault(False)
    button.clicked.connect(on_click)
    return button


def _say_error(label: QLabel, text: str) -> None:
    label.setText(text)
    label.setVisible(bool(text))


def _confirm(parent, text: str, title: str = APP_NAME, confirm: str = "确定") -> bool:
    """Ask before something that cannot be taken back. 取消 is the default answer."""
    from blacklist_detect.ui_kit import ConfirmDialog

    return ConfirmDialog.ask(parent, title, text, confirm, danger=True)


class AddNameDialog(Modal):
    """One player. Click a tag to put it on this record, and click it again to take it off."""

    def __init__(
        self,
        name: str = "",
        tags: tuple[str, ...] = (),
        detail: str = "",
        title: str = "添加",
        allow_delete: bool = False,
        catalog: tuple[str, ...] = (),
        added_at: str = "",
        parent=None,
        taken: frozenset[str] | set[str] = frozenset(),
    ) -> None:
        super().__init__(parent)
        from blacklist_detect.storage import TAGS

        # Folded names already on the list. Saving one of them again would make a second row.
        self.taken = frozenset(taken)
        self.name = name
        self.tags: tuple[str, ...] = tuple(tags)
        self.detail = detail
        self.catalog = list(catalog or TAGS)
        self.picked = [tag for tag in self.catalog if tag in tags]
        self.picked.extend(tag for tag in tags if tag not in self.picked)
        self._tag_order = list(self.picked)
        self._tag_order.extend(tag for tag in self.catalog if tag not in self._tag_order)
        self.deleted = False
        layout = _frame(self, title)
        self.name_edit = QLineEdit(name)
        added_on = _zh_date(added_at)
        self.added_on = QLabel(added_on)
        self.added_on.setObjectName("sub")
        self.added_on.setVisible(bool(added_on))
        self.name_error = _field(layout, "名字", self.name_edit)
        self.name_edit.textChanged.connect(self._clear_name_error)
        self.tag_host = _FlowHost(gap=8)
        _field(layout, "标签", self.tag_host)
        self._refresh_tags()
        self.detail_edit = QPlainTextEdit()
        self.detail_edit.setPlainText(detail)
        self.detail_edit.setTabChangesFocus(True)
        self.detail_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.detail_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.detail_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.detail_edit.document().setDocumentMargin(0)
        self.detail_edit.setFixedHeight(QFontMetrics(self.font()).lineSpacing() * 3 + 18)
        _field(layout, "原因", self.detail_edit)
        remove = _danger("删除", self._delete) if allow_delete else None
        confirm = _primary("保存" if allow_delete else "添加", self._accept)
        # The destructive button stands apart on the left, away from 保存.
        _footer(self, confirm, left=remove)
        self.card.setMinimumWidth(440)
        self.name_edit.returnPressed.connect(self._accept)
        self._before = (name, tuple(self.picked), detail)
        _pointing(self)

    def _clear_name_error(self, _text: str) -> None:
        _say_error(self.name_error, "")

    def has_changes(self) -> bool:
        return (self.name_edit.text(), tuple(self.picked), self.detail_edit.toPlainText()) != self._before

    def _refresh_tags(self) -> None:
        self.tag_host.clear()
        for tag in self._tag_order:
            pill = TagPill(tag, clickable=True, active=tag in self.picked)
            pill.clicked.connect(self._toggle_tag)
            self.tag_host.addWidget(pill)
        self.tag_host.updateGeometry()
        self.tag_host.setVisible(bool(self._tag_order))

    def _toggle_tag(self, tag: str) -> None:
        if tag in self.picked:
            self._detach_tag(tag)
            return
        self._attach_tag(tag)

    def _attach_tag(self, tag: str | None = None) -> None:
        chosen = tag or ""
        if not chosen or chosen in self.picked or chosen not in self.catalog:
            return
        self.picked.append(chosen)
        self._paint_tag(chosen)

    def _detach_tag(self, tag: str) -> None:
        self.picked = [item for item in self.picked if item != tag]
        self._paint_tag(tag)

    def _paint_tag(self, tag: str) -> None:
        for pill in self.tag_host.widgets():
            if isinstance(pill, TagPill) and pill._text == tag:
                pill.set_active(tag in self.picked)
                return

    def _chosen(self) -> tuple[str, ...]:
        ordered = [tag for tag in self.catalog if tag in self.picked]
        ordered.extend(tag for tag in self.picked if tag not in ordered)
        return tuple(ordered)

    def _accept(self) -> None:
        key = fold(clean_stored_name(self.name_edit.text()))
        if not self.name_edit.text().strip():
            problem = "请填写名字"
        elif not key:
            problem = "名字里要有文字或数字"
        elif key in self.taken:
            problem = "已经在黑名单里了"
        else:
            problem = ""
        if problem:
            _say_error(self.name_error, problem)
            return
        _say_error(self.name_error, "")
        self.name = self.name_edit.text()
        self.tags = self._chosen()
        self.detail = self.detail_edit.toPlainText()
        self.deleted = False
        self.accept()

    def _delete(self) -> None:
        self.deleted = True
        self.accept()


class _PickDelegate(QStyledItemDelegate):
    """A preview row's first cell: a box like the app's own, then the name. Unchecked is grey."""

    BOX = 16

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: ANN001
        checked = bool(index.data(Qt.UserRole))
        rect = option.rect
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        box = QRectF(rect.left() + 8, rect.center().y() - self.BOX / 2 + 0.5, self.BOX, self.BOX)
        if checked:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(THEME["accent"]))
            painter.drawRoundedRect(box, 4, 4)
            painter.drawPixmap(box.adjusted(2, 2, -2, -2).toRect(), line_pixmap("check", 12, THEME["on_accent"]))
        else:
            painter.setPen(QPen(QColor(THEME["border"]), 1.2))
            painter.setBrush(QColor(THEME["surface"]))
            painter.drawRoundedRect(box.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
        text = QRect(round(box.right()) + 8, rect.top(), max(0, rect.right() - round(box.right()) - 12), rect.height())
        painter.setFont(option.font)
        painter.setPen(QColor(THEME["text"] if checked else THEME["muted"]))
        shown = QFontMetrics(option.font).elidedText(str(index.data() or ""), Qt.ElideRight, text.width())
        painter.drawText(text, Qt.AlignLeft | Qt.AlignVCenter, shown)
        painter.restore()


class _PreviewDelegate(QStyledItemDelegate):
    """The other preview cells: 标签 as the list's red pills, text in its own color, faded when unchecked."""

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: ANN001
        checked = bool(index.sibling(index.row(), 0).data(Qt.UserRole))
        painter.save()
        if not checked:
            painter.setOpacity(0.45)
        tags = index.data(Qt.UserRole + 3)
        if tags:
            paint_tag_row(painter, option.rect, tuple(tags))
        else:
            box = option.rect.adjusted(8, 0, -8, 0)
            painter.setFont(option.font)
            painter.setPen(QColor(index.data(Qt.UserRole + 4) or THEME["text"]))
            shown = QFontMetrics(option.font).elidedText(str(index.data() or ""), Qt.ElideRight, box.width())
            painter.drawText(box, Qt.AlignLeft | Qt.AlignVCenter, shown)
        painter.restore()


class BatchAddDialog(Modal):
    """Paste a list, see what each person does to the list, then import the ones left checked.

    Under the box, one row per person: 合并 when the name is on the list already (its new
    标签 and 原因 are added to it), 已在黑名单 when it brings nothing new, and 可能不是名字 for a
    line that is not a name, such as a title. Those two start unchecked. A click on a row,
    or Space, checks or unchecks it. The rows follow the text as it changes; a row
    unchecked by hand stays unchecked.
    """

    def __init__(self, catalog: tuple[str, ...] = (), entries=(), parent=None, likes: bool = False, elsewhere=()) -> None:  # noqa: ANN001
        super().__init__(parent)
        from blacklist_detect.storage import TAGS

        # Into 嘉宾 there are no 标签: the whole note is the 原因.
        self.likes = likes
        self.catalog = () if likes else (catalog or TAGS)
        self.entries = list(entries)
        self.elsewhere = list(elsewhere)
        here, there = ("嘉宾列表", "黑名单") if likes else ("黑名单", "嘉宾列表")
        self._status = {MERGE: "合并", SAME: f"已在{here}", ODD: "可能不是名字", ELSEWHERE: f"已在{there}"}
        self.rows: list[ImportRow] = []
        self.chosen: list[tuple[str, tuple[str, ...], str, int]] = []
        self._picked: dict[str, bool] = {}
        layout = _frame(self, "批量导入")
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("名字（原因），一行一个")
        self.edit.setAccessibleName("名单")
        self.edit.setFixedHeight(120)
        layout.addWidget(self.edit)
        self.preview = QTableWidget(0, 4)
        self.preview.setObjectName("importPreview")
        self.preview.setAccessibleName("导入预览")
        self.preview.setHorizontalHeaderLabels(["名字", "标签", "原因", ""])
        head = self.preview.horizontalHeader()
        head.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        head.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        head.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        head.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        head.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.preview.setColumnWidth(0, 160)
        self.preview.setColumnWidth(1, 110)
        self.preview.setColumnHidden(1, likes)
        self.preview.verticalHeader().setVisible(False)
        self.preview.verticalHeader().setDefaultSectionSize(30)
        self.preview.setSelectionMode(QTableWidget.NoSelection)
        self.preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview.setShowGrid(False)
        self.preview.setWordWrap(False)
        self.preview.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.preview.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.preview.setMinimumHeight(240)
        self.preview.setItemDelegateForColumn(0, _PickDelegate(self.preview))
        for column in (1, 2, 3):
            self.preview.setItemDelegateForColumn(column, _PreviewDelegate(self.preview))
        self.preview.setCursor(Qt.PointingHandCursor)
        self.preview.hide()
        self.preview.cellClicked.connect(self._toggle)
        self.preview.installEventFilter(self)
        layout.addWidget(self.preview)
        self.error = QLabel("")
        self.error.setObjectName("error")
        self.error.hide()
        layout.addWidget(self.error)
        self.import_button = _primary("导入", self._accept)
        self.import_button.setEnabled(False)
        _footer(self, self.import_button)
        self.card.setMinimumWidth(680)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._refresh)
        self.edit.textChanged.connect(self._timer.start)
        _pointing(self)

    def has_changes(self) -> bool:
        return bool(self.edit.toPlainText().strip())

    def _refresh(self) -> None:
        """Read the paste again and show who it brings."""
        self.rows = plan_import(self.edit.toPlainText(), self.entries, self.catalog, self.elsewhere)
        for row in self.rows:
            picked = self._picked.get(fold(row.name))
            if picked is not None:
                row.checked = picked
        table = self.preview
        table.setRowCount(len(self.rows))
        for index, row in enumerate(self.rows):
            name = QTableWidgetItem(row.name)
            name.setToolTip(row.name)
            reason = QTableWidgetItem(row.reason)
            reason.setToolTip(row.reason)
            status = QTableWidgetItem(self._status.get(row.status, ""))
            if row.status == MERGE and 0 <= row.target < len(self.entries):
                status.setToolTip(f"合并到「{self.entries[row.target].name}」")
            tags = QTableWidgetItem("")
            tags.setData(Qt.UserRole + 3, row.tags)
            tags.setToolTip("、".join(row.tags))
            status.setData(Qt.UserRole + 4, (THEME["accent_line"] if THEME.get("scheme") == "dark" else THEME["accent"]) if row.status == MERGE else THEME["muted"])
            for column, item in enumerate((name, tags, reason, status)):
                item.setFlags(Qt.ItemIsEnabled)
                table.setItem(index, column, item)
            self._paint_row(index)
        table.setVisible(bool(self.rows))
        typed = bool(self.edit.toPlainText().strip())
        _say_error(self.error, "没有读到名字" if typed and not self.rows else "")
        self._sync_button()

    def _paint_row(self, index: int) -> None:
        """Checked or not, for its box; the delegates fade the rest of an unchecked row."""
        self.preview.item(index, 0).setData(Qt.UserRole, self.rows[index].checked)

    def _toggle(self, index: int, _column: int = 0) -> None:
        if not 0 <= index < len(self.rows):
            return
        row = self.rows[index]
        row.checked = not row.checked
        self._picked[fold(row.name)] = row.checked
        self._paint_row(index)
        self.preview.viewport().update()
        self._sync_button()

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001
        if watched is self.preview and event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key_Space:
            self._toggle(self.preview.currentRow())
            return True
        return super().eventFilter(watched, event)

    def _sync_button(self) -> None:
        count = sum(1 for row in self.rows if row.checked)
        self.import_button.setEnabled(count > 0)
        self.import_button.setText(f"导入 {count} 人" if count else "导入")

    def _accept(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
            self._refresh()
        self.chosen = [
            (row.name, row.tags, row.reason, row.target if row.status in (MERGE, SAME) else -1)
            for row in self.rows
            if row.checked
        ]
        if self.chosen:
            self.accept()



class TagSuggestDialog(Modal):
    """批量导入's last step: the 标签 to add, then who will be added.

    The 标签 are phrases several 原因 share, as pills under 新标签 and 已有标签. All start on;
    a click cancels one, a second click brings it back. Under them, the people being added
    with the 标签 each will get and their 原因, their number beside 名字; six rows show and the rest scroll.
    导入 imports; 返回 goes back to the pasted text.
    """

    LIST_ROWS = 6

    def __init__(self, suggestions: list[TagSuggestion], rows: list[tuple[str, tuple[str, ...], str, int]], parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.suggestions = list(suggestions)
        self.rows = list(rows)
        self.went_back = False
        self.on = {suggestion.tag for suggestion in self.suggestions}
        layout = _frame(self, "确认导入")
        # 1. The 标签.
        tags = QWidget()
        column = QVBoxLayout(tags)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(10)
        hint = QLabel("点标签可以取消")
        hint.setObjectName("sub")
        hint.setWordWrap(True)
        column.addWidget(hint)
        self.pills: dict[str, TagPill] = {}
        for title, existing in (("新标签", False), ("已有标签", True)):
            group = [suggestion for suggestion in self.suggestions if suggestion.existing == existing]
            if not group:
                continue
            row = QHBoxLayout()
            row.setSpacing(12)
            kind = QLabel(title)
            kind.setObjectName("sub")
            kind.setFixedWidth(QFontMetrics(kind.font()).horizontalAdvance("已有标签") + 4)
            kind.setFixedHeight(TagPill("标签").sizeHint().height())
            row.addWidget(kind, 0, Qt.AlignTop)
            host = _FlowHost(gap=8)
            for suggestion in group:
                pill = TagPill(suggestion.tag, clickable=True, active=True)
                pill.clicked.connect(self._toggle_tag)
                host.addWidget(pill)
                self.pills[suggestion.tag] = pill
            row.addWidget(host, 1)
            column.addLayout(row)
        layout.addWidget(tags)
        # 2. Who will be added, how many beside 名字.
        table = QTableWidget(len(self.rows), 3)
        self.people = table
        table.setObjectName("importPreview")
        table.setAccessibleName("要添加的人")
        table.setHorizontalHeaderLabels([f"名字  {len(self.rows)}", "标签", "原因"])
        head = table.horizontalHeader()
        head.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        head.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        head.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        head.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(0, 150)
        table.setColumnWidth(1, 190)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(30)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setFocusPolicy(Qt.NoFocus)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # The rows paint as checked: everyone listed here is coming in.
        table.setItemDelegateForColumn(0, _PreviewDelegate(table))
        table.setItemDelegateForColumn(1, _PreviewDelegate(table))
        table.setItemDelegateForColumn(2, _PreviewDelegate(table))
        for index, (name, _tags, reason, _target) in enumerate(self.rows):
            who = QTableWidgetItem(name)
            who.setToolTip(name)
            who.setData(Qt.UserRole, True)
            gets = QTableWidgetItem("")
            why = QTableWidgetItem(reason)
            why.setToolTip(reason)
            why.setData(Qt.UserRole + 4, THEME["muted"])
            for column, item in enumerate((who, gets, why)):
                item.setFlags(Qt.ItemIsEnabled)
                table.setItem(index, column, item)
        shown = min(len(self.rows), self.LIST_ROWS)
        table.setFixedHeight(head.sizeHint().height() + 30 * shown + 2 * table.frameWidth() + 24)
        layout.addWidget(table)
        self._fill_tags()
        back = QPushButton("返回")
        back.setAutoDefault(False)
        back.clicked.connect(self._back)
        self.import_button = _primary("导入", self.accept)
        _footer(self, back, self.import_button)
        self.card.setMinimumWidth(680)
        _pointing(self)

    def picked(self) -> list[TagSuggestion]:
        return [suggestion for suggestion in self.suggestions if suggestion.tag in self.on]

    def _toggle_tag(self, tag: str) -> None:
        if tag in self.on:
            self.on.discard(tag)
        else:
            self.on.add(tag)
        self.pills[tag].set_active(tag in self.on)
        self._fill_tags()

    def _fill_tags(self) -> None:
        """Each person's 标签 in the list, with the ones still on."""
        from blacklist_detect.importing import with_tags

        for index, (_name, tags, _reason, _target) in enumerate(with_tags(self.rows, self.picked())):
            item = self.people.item(index, 1)
            item.setData(Qt.UserRole + 3, tuple(tags))
            item.setToolTip("、".join(tags))
        self.people.viewport().update()

    def _back(self) -> None:
        self.went_back = True
        self.reject()


SAMPLE_LOBBY = Path(__file__).resolve().parent / "assets" / "sample-lobby.jpg"


def _is_me(slot, me: str) -> bool:
    """Whether this seat is the player's own 游戏名. The same rule as 记录."""
    from blacklist_detect.match import NameLabel, match_label
    from blacklist_detect.model import Entry

    if slot.unclear or not me:
        return False
    shown = split_ellipsis(slot.visible)[0] or slot.visible
    return bool(match_label(NameLabel(raw=shown, visible=shown, truncated=False), [Entry(me)]))


def _liked(slot, likes):  # noqa: ANN001, ANN202
    """The 嘉宾 entry this seat is, or None. The same rule as the lobby check."""
    from blacklist_detect.match import NameLabel, match_label

    if slot.unclear or not likes:
        return None
    found = match_label(NameLabel(raw=slot.raw, visible=slot.visible, truncated=slot.truncated), list(likes))
    return found[0].entry if found else None


class PictureResultDialog(Modal):
    """What one picture check read: the twelve seats, blacklist matches in red, 嘉宾 in rose."""

    def __init__(  # noqa: ANN001
        self, title: str, result: CheckResult | None = None, error: str = "", parent=None, likes=(), hide_hits: bool = False, me: str = ""
    ) -> None:
        super().__init__(parent)
        layout = _frame(self, title)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.seats: list[QLabel] = []
        if error:
            self.summary.setText(f"检查失败：{error}")
        elif result is None or not result.header_found:
            reason = result.message if result is not None else ""
            self.summary.setText(f"{reason}\n请用「推演成功」大厅的完整截图".strip())
        else:
            # The seats say it: red ones are on the list, grey ones were not read.
            self.summary.hide()
            hits = {}
            for hit in result.hits:
                hits.setdefault(hit.index, hit)
            grid = QGridLayout()
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(8)
            for slot in result.names:
                tile = QWidget()
                tile.setObjectName("seatTile")
                tile.setAttribute(Qt.WA_StyledBackground, True)
                tile.setMinimumWidth(200)
                line = QHBoxLayout(tile)
                line.setContentsMargins(12, 8, 12, 8)
                line.setSpacing(8)
                cell = QLabel()
                base = f'font-family: "{chinese_family()}"; background: transparent;'
                wash = ""
                # Marks that go after the name, such as 我.
                after: list[QWidget] = []
                if slot.unclear:
                    cell.setText("未识别")
                    cell.setStyleSheet(base + f' color: {THEME["gray"]};')
                elif slot.index in hits:
                    hit = hits[slot.index]
                    shown = split_ellipsis(slot.visible)[0] or slot.visible
                    tail = listed_tail(shown, hit.entry_name)
                    if hide_hits:
                        # 直播模式: the dialog may be on stream; the name is masked.
                        cell.setText(masked_name(shown))
                    elif tail:
                        # Cut short by the game: the name once, in full as the list has it.
                        cell.setText(hit.entry_name)
                        cell.setToolTip(f"读到「{shown}」，是黑名单里的「{hit.entry_name}」")
                    else:
                        listed = "" if tail == "" else f"　黑名单：{hit.entry_name}"
                        cell.setText(shown + listed)
                    cell.setStyleSheet(base + f' color: {THEME["red"]};')
                    wash = THEME["red_wash"]
                    # Red is not the only sign of a hit: the warning mark says it too.
                    warn = QLabel()
                    warn.setObjectName("seatWarn")
                    warn.setPixmap(line_pixmap("warning", 16, THEME["red"]))
                    warn.setStyleSheet("background: transparent;")
                    line.addWidget(warn)
                elif (liked := _liked(slot, likes)) is not None:
                    shown = split_ellipsis(slot.visible)[0] or slot.visible
                    # 嘉宾 shows the 昵称, or the full name as the list has it.
                    cell.setText(liked.shown())
                    cell.setToolTip(f"读到「{shown}」，是嘉宾「{liked.name}」")
                    cell.setStyleSheet(base + f' color: {THEME["rose"]};')
                    wash = THEME["rose_wash"]
                    heart = QLabel()
                    heart.setObjectName("seatHeart")
                    heart.setPixmap(line_pixmap("heart", 16, THEME["rose"]))
                    heart.setStyleSheet("background: transparent;")
                    line.addWidget(heart)
                elif _is_me(slot, me):
                    # The player's own seat: green, with 我 after the name, as on 记录.
                    cell.setText(split_ellipsis(slot.visible)[0] or slot.visible)
                    cell.setStyleSheet(base + f' color: {THEME["green"]};')
                    wash = THEME["green_wash"]
                    mine = QLabel("我")
                    mine.setObjectName("seatMe")
                    mine.setStyleSheet(
                        f'color: {THEME["chip_text"]}; background: {THEME["chip_bg"]}; border: 1px solid {THEME["chip_bg"]};'
                        f' border-radius: 9px; padding: 1px 8px;'
                        f' font-family: "{chinese_family()}"; font-size: {SMALL_PT}pt;'
                    )
                    after.append(mine)
                else:
                    cell.setText(split_ellipsis(slot.visible)[0] or slot.visible)
                    cell.setStyleSheet(base + f' color: {THEME["text"]};')
                # As on 记录: white with a thin gray outline, filled only when the seat means something.
                line_color = wash or seat_line()
                tile.setStyleSheet(
                    f"QWidget#seatTile {{ background: {wash or THEME['surface']}; border: 1px solid {line_color}; border-radius: 6px; }}"
                )
                line.addWidget(cell, 1)
                for mark in after:
                    line.addWidget(mark, 0, Qt.AlignVCenter)
                grid.addWidget(tile, slot.index // 2, slot.index % 2)
                self.seats.append(cell)
            layout.addLayout(grid)
        close = _primary("关闭", self.accept)
        _footer(self, close)
        self.card.setMinimumWidth(480)
        _pointing(self)


# 使用声明: what the app is and is not, and who answers for using it.
DISCLAIMER = (
    "玩家自制的免费工具，和网易、第五人格官方无关。",
    "本工具会进行截图并且在工具内分析，然后展示结果，无注入游戏。",
    "使用第三方工具可能违反游戏用户协议，由此带来的任何后果（包括账号处罚）由使用者自行承担。",
)


class DisclaimerDialog(Modal):
    """使用声明. Before first use it asks: 同意 goes on, 不同意 closes the app. From 设置 it only shows."""

    def __init__(self, parent=None, asking: bool = True) -> None:
        super().__init__(parent)
        layout = _frame(self, "使用声明")
        self.points: list[QLabel] = []
        for number, text in enumerate(DISCLAIMER, 1):
            row = QHBoxLayout()
            row.setSpacing(8)
            mark = QLabel(f"{number}.")
            mark.setObjectName("rowHint")
            mark.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            row.addWidget(mark, 0, Qt.AlignTop)
            point = QLabel(text)
            point.setWordWrap(True)
            row.addWidget(point, 1)
            layout.addLayout(row)
            self.points.append(point)
        if asking:
            self.decline_button = QPushButton("不同意")
            self.decline_button.setAutoDefault(False)
            self.decline_button.clicked.connect(self.reject)
            self.agree_button = _primary("同意并继续", self.accept)
            _footer(self, self.decline_button, self.agree_button)
        else:
            _footer(self, _primary("知道了", self.accept))
        self.card.setMinimumWidth(520)
        _pointing(self)


class GuideDialog(Modal):
    """Shown once on a new PC: what to set up, how a check starts, and what it shows.

    how: how a check starts in the mode the app is in, such as 「在「推演成功」大厅按 Alt+1 检查」.
    """

    def __init__(self, parent=None, how: str = "在「推演成功」大厅按快捷键检查") -> None:  # noqa: ANN001
        super().__init__(parent)
        layout = _frame(self, f"欢迎使用{APP_NAME}")
        steps = (
            ("edit", "右上角填写游戏名称"),
            ("users", "在「黑名单」里加上不想遇到的人"),
            ("search", how),
            ("warning", "遇到黑名单会提醒你"),
        )
        accent = THEME["accent_line"] if THEME.get("scheme") == "dark" else THEME["accent"]
        self.steps: list[QLabel] = []
        for icon_name, text in steps:
            row = QHBoxLayout()
            row.setSpacing(GAP)
            tile = QLabel()
            tile.setObjectName("stepIcon")
            tile.setFixedSize(36, 36)
            tile.setAlignment(Qt.AlignCenter)
            tile.setPixmap(line_pixmap(icon_name, 20, accent))
            tile.setStyleSheet(f'background: {THEME["accent_wash"]}; border-radius: 8px;')
            row.addWidget(tile, 0, Qt.AlignTop)
            step = QLabel(text)
            step.setWordWrap(True)
            step.setMinimumHeight(36)
            step.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            row.addWidget(step, 1)
            layout.addLayout(row)
            self.steps.append(step)
        _footer(self, _primary("开始使用", self.accept))
        self.card.setMinimumWidth(460)
        _pointing(self)


# 直播模式's guide, one page of two rows: (picture in assets, title, words). What viewers see,
# side by side with what the player sees (both 完整模式, the same moment), then how to add it in 直播姬.
STREAM_GUIDE = (
    ("stream-diff-1.jpg", "观众看到什么", "观众看不到黑名单，能看到嘉宾"),
    ("stream-setup-2.png", "怎么设置", "在直播姬添加窗口捕捉"),
)
# 显示's guide: what the player sees in each mode.
DISPLAY_DIFF = (
    ("display-diff-1.jpg", "发现黑名单", "安全模式只在右下角提示，完整模式直接标在游戏上"),
    ("display-diff-2.jpg", "遇到嘉宾", "完整模式还有花边"),
)
GUIDE_PICTURES = Path(__file__).resolve().parent / "assets"
# Each picture fits in this box, in logical pixels; the files are made at twice the size.
PICTURE_BOX = (465, 150)
WORDS_WIDTH = 186


class _Pages(QWidget):
    """Pages, one shown at a time, as tall as the one shown. A QStackedWidget works out its
    height from every page, so a short page got the blank space of the longest."""

    def __init__(self) -> None:
        super().__init__()
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._pages: list[QWidget] = []
        self._current = 0

    def addWidget(self, page: QWidget) -> None:  # noqa: N802 - as QStackedWidget names it
        self._column.addWidget(page)
        page.setVisible(not self._pages)
        self._pages.append(page)

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802
        self._current = index
        for number, page in enumerate(self._pages):
            page.setVisible(number == index)

    def currentIndex(self) -> int:  # noqa: N802
        return self._current

    def count(self) -> int:
        return len(self._pages)

    def widget(self, index: int) -> QWidget:
        return self._pages[index]


class PictureGuideDialog(Modal):
    """A guide in pages of up to three rows, each row its words beside its picture.

    pages: (heading, rows), rows as (picture in assets, title, words). The last page's button says
    知道了; before it, the button names the next page.
    """

    def __init__(self, title: str, pages, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        layout = _frame(self, title)
        self.headings = [heading for heading, _rows in pages]
        self.page_label = QLabel()
        self.page_label.setObjectName("sub")
        # One page needs no heading: the title says it.
        self.page_label.setVisible(len(pages) > 1)
        layout.addWidget(self.page_label)
        self.pages = _Pages()
        self.pictures: list[QLabel] = []
        for _heading, rows in pages:
            page = QWidget()
            column = QVBoxLayout(page)
            column.setContentsMargins(0, 4, 0, 0)
            column.setSpacing(14)
            for name, row_title, words in rows:
                column.addLayout(self._row(name, row_title, words))
            column.addStretch(1)
            self.pages.addWidget(page)
        layout.addWidget(self.pages)
        self.back_button = QPushButton("上一步")
        self.back_button.setAutoDefault(False)
        self.back_button.clicked.connect(lambda: self.show_page(self.page - 1))
        self.next_button = _primary("知道了", self._next)
        _footer(self, self.back_button, self.next_button)
        _pointing(self)
        self.show_page(0)

    def _row(self, name: str, title: str, words: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(16)
        text = QVBoxLayout()
        text.setSpacing(4)
        heading = QLabel(title)
        heading.setStyleSheet("font-weight: 600;")
        text.addWidget(heading)
        body = QLabel(words)
        body.setObjectName("sub")
        body.setWordWrap(True)
        text.addWidget(body)
        text.addStretch(1)
        holder = QWidget()
        holder.setFixedWidth(WORDS_WIDTH)
        holder.setLayout(text)
        row.addWidget(holder, 0, Qt.AlignTop)
        picture = QLabel()
        picture.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        image = QPixmap(str(GUIDE_PICTURES / name))
        if not image.isNull():
            ratio = self.devicePixelRatioF()
            box_w, box_h = PICTURE_BOX
            scale = min(box_w / (image.width() / 2), box_h / (image.height() / 2), 1.0)
            size = (round(image.width() / 2 * scale), round(image.height() / 2 * scale))
            shown = image.scaled(round(size[0] * ratio), round(size[1] * ratio), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            shown.setDevicePixelRatio(ratio)
            picture.setPixmap(shown)
            picture.setFixedSize(*size)
            picture.setStyleSheet(f'border: 1px solid {THEME["border"]}; border-radius: 6px;')
        self.pictures.append(picture)
        row.addWidget(picture, 0, Qt.AlignTop)
        row.addStretch(1)
        return row

    def show_page(self, page: int) -> None:
        count = len(self.headings)
        self.page = max(0, min(page, count - 1))
        self.pages.setCurrentIndex(self.page)
        heading = self.headings[self.page]
        self.page_label.setText(f"{heading}（{self.page + 1}/{count}）" if count > 1 else heading)
        self.back_button.setVisible(self.page > 0)
        last = self.page == count - 1
        self.next_button.setText("知道了" if last else self.headings[self.page + 1])

    def _next(self) -> None:
        if self.page == len(self.headings) - 1:
            self.accept()
        else:
            self.show_page(self.page + 1)


class StreamGuideDialog(PictureGuideDialog):
    """直播模式: what viewers see, and how to add it in 直播姬."""

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__("直播模式", [("", STREAM_GUIDE)], parent)


class DisplayGuideDialog(PictureGuideDialog):
    """显示: 安全模式 and 完整模式 side by side."""

    def __init__(self, parent=None) -> None:  # noqa: ANN001
        super().__init__("显示", [("", DISPLAY_DIFF)], parent)




# The colors of 环境测试's bars, one per step, in STEPS order.
_STEP_COLORS = {"capture": "#8fa3bf", "glance": "#a58bff", "find": "#4f8fdc", "read": "#e58aa8"}


class _FlowBar(QWidget):
    """One way a check starts as a bar on a shared time scale: a part per step, its seconds under it."""

    def __init__(self, title: str, parts: list[tuple[str, str, float]], scale: float, parent=None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self.title = title
        self.parts = parts
        self.scale = max(scale, 0.1)
        self.setMinimumHeight(64)
        self.setMinimumWidth(420)

    def total(self) -> float:
        return sum(seconds for _key, _words, seconds in self.parts)

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        metrics = QFontMetrics(self.font())
        line = metrics.height()
        painter.setPen(QColor(THEME["text"]))
        painter.drawText(QRectF(0, 0, self.width(), line), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        painter.drawText(QRectF(0, 0, self.width(), line), Qt.AlignRight | Qt.AlignVCenter, f"{self.total():.1f} 秒")
        top = line + 6
        bar_h = 14.0
        x = 0.0
        width = self.width()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(THEME["surface_alt"]))
        painter.drawRoundedRect(QRectF(0, top, width, bar_h), 4, 4)
        labels = []
        for key, words, seconds in self.parts:
            span = width * seconds / self.scale
            if span <= 0:
                continue
            painter.setBrush(QColor(_STEP_COLORS.get(key, THEME["accent"])))
            painter.drawRoundedRect(QRectF(x, top, max(span, 2.0), bar_h), 3, 3)
            labels.append((x, f"{words} {seconds:.2f}"))
            x += span
        painter.setPen(QColor(THEME["muted"]))
        left = 0.0
        for at, text in labels:
            # Each part's seconds under it, never on top of the one before.
            spot = max(at, left)
            painter.drawText(QRectF(spot, top + bar_h + 4, metrics.horizontalAdvance(text) + 4, line), Qt.AlignLeft, text)
            left = spot + metrics.horizontalAdvance(text) + 12
        painter.end()


class FlowReportDialog(Modal):
    """环境测试's report: how long a check takes here, as two bars (手动检查 and 自动检查) split by step,
    then why, in plain words, and a way to send it."""

    def __init__(self, test, on_export, parent=None) -> None:  # noqa: ANN001
        from blacklist_detect.diagnostics import STEPS

        super().__init__(parent)
        layout = _frame(self, "环境测试")
        words = dict(STEPS)
        self.headline = QLabel(f"检查一次约 {test.hotkey_total():.1f} 秒，{test.verdict()}")
        self.headline.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.headline)
        hotkey = [(key, words[key], seconds) for key, seconds in test.hotkey().items()]
        auto = [("glance", words["glance"], test.glance), *((key, words[key], seconds) for key, seconds in test.auto.items())]
        scale = max(test.hotkey_total(), test.auto_total())
        self.bars = [_FlowBar("手动检查（快捷键）", hotkey, scale), _FlowBar("自动检查", auto, scale)]
        for bar in self.bars:
            layout.addWidget(bar)
        facts = [f"识别用 {'显卡' if test.device.startswith('gpu') else 'CPU'}", f"屏幕 {test.size[0]}×{test.size[1]}"]
        if test.cpu_busy is not None:
            facts.append(f"CPU {test.cpu_busy:.0f}%（本工具 {test.cpu_own or 0:.0f}%）")
        facts.append(f"示例名字读对 {test.right}/12")
        self.facts = QLabel(" · ".join(facts))
        self.facts.setObjectName("sub")
        self.facts.setWordWrap(True)
        self.facts.setVisible(bool(test.causes()) or test.right < 12)
        layout.addWidget(self.facts)
        self.causes = QLabel("\n".join(f"· {cause}" for cause in test.causes()))
        self.causes.setWordWrap(True)
        self.causes.setVisible(bool(test.causes()))
        layout.addWidget(self.causes)
        self.export_button = QPushButton("导出日志")
        self.export_button.setAutoDefault(False)
        self.export_button.clicked.connect(on_export)
        _footer(self, self.export_button, _primary("知道了", self.accept))
        self.card.setMinimumWidth(500)
        _pointing(self)
