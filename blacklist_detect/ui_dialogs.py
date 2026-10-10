"""Dialogs: add and edit names, batch add, tags, picture results, and the first-run guide."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QFontMetrics,
)
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect.match import clean_stored_name, fold, split_ellipsis
from blacklist_detect.pipeline import CheckResult
from blacklist_detect.ui_icons import pixmap as line_pixmap
from blacklist_detect.ui_theme import (
    DIALOG_PAD,
    GAP,
    THEME,
    TITLE_PT,
    _caption_color,
    _dialog_style,
    _pointing,
    chinese_family,
    chinese_font,
)
from blacklist_detect.ui_widgets import (
    TagPill,
    _FlowHost,
    _zh_date,
)


def _cancel_button(dialog: QDialog) -> QPushButton:
    """Close without saving. Esc does the same."""
    cancel = QPushButton("取消")
    cancel.setAutoDefault(False)
    cancel.setDefault(False)
    cancel.clicked.connect(dialog.reject)
    return cancel


def _frame(dialog: QDialog, title: str) -> QVBoxLayout:
    """Every dialog starts the same way: the theme, and its title as a heading inside it."""
    dialog.setWindowTitle(title)
    dialog.setFont(chinese_font())
    dialog.setStyleSheet(_dialog_style(chinese_family()))
    _caption_color(dialog)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(DIALOG_PAD, DIALOG_PAD - 4, DIALOG_PAD, DIALOG_PAD)
    layout.setSpacing(GAP)
    heading = QLabel(title)
    heading.setObjectName("dialogTitle")
    heading.setFont(chinese_font(TITLE_PT))
    layout.addWidget(heading)
    dialog.heading = heading
    return layout


def _field(layout: QVBoxLayout, label: str, widget: QWidget, aside: QWidget | None = None) -> QLabel:
    """A label above its control, and a line under it for what is wrong with it."""
    column = QVBoxLayout()
    column.setSpacing(6)
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


def _footer(layout: QVBoxLayout, *right: QPushButton, left: QPushButton | None = None) -> None:
    """取消 and the main action on the right; anything destructive stands apart on the left."""
    layout.addSpacing(8)
    row = QHBoxLayout()
    row.setSpacing(8)
    if left is not None:
        row.addWidget(left)
    row.addStretch(1)
    for button in right:
        row.addWidget(button)
    layout.addLayout(row)


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


def _confirm(parent, text: str, title: str = "黑名单检测", confirm: str = "确定") -> bool:
    """Ask before something that cannot be taken back. 取消 is the default answer."""
    from blacklist_detect.ui_kit import ConfirmDialog

    return ConfirmDialog.ask(parent, title, text, confirm, danger=True)


class TagEditDialog(QDialog):
    """Rename one tag, or delete it from the list and from every name."""

    def __init__(self, tag: str, catalog: tuple[str, ...], parent=None) -> None:
        super().__init__(parent)
        self.original = tag
        self.catalog = catalog
        self.renamed = tag
        self.deleted = False
        layout = _frame(self, "修改标签")
        self.name_edit = QLineEdit(tag)
        self.error = _field(layout, "标签", self.name_edit)
        self.name_edit.textChanged.connect(self._clear_error)
        # The destructive button stands apart on the left, away from 保存.
        _footer(layout, _cancel_button(self), _primary("保存", self._accept), left=_danger("删除", self._delete))
        self.setMinimumWidth(380)
        self.name_edit.returnPressed.connect(self._accept)
        _pointing(self)

    def _clear_error(self, *_args) -> None:
        _say_error(self.error, "")

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)

    def _accept(self) -> None:
        from blacklist_detect.storage import clean_tag

        renamed = clean_tag(self.name_edit.text())
        if not renamed:
            _say_error(self.error, "请填写标签")
            return
        if renamed != self.original and renamed in self.catalog:
            _say_error(self.error, "已有这个标签")
            return
        _say_error(self.error, "")
        self.renamed = renamed
        self.deleted = False
        self.accept()

    def _delete(self) -> None:
        self.deleted = True
        self.accept()


class TagCreateDialog(QDialog):
    """Name a tag that is not in the list yet."""

    def __init__(self, catalog: tuple[str, ...], parent=None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.created = ""
        layout = _frame(self, "新标签")
        self.name_edit = QLineEdit()
        self.error = _field(layout, "标签", self.name_edit)
        self.name_edit.textChanged.connect(self._clear_error)
        _footer(layout, _cancel_button(self), _primary("添加", self._accept))
        self.setMinimumWidth(380)
        self.name_edit.returnPressed.connect(self._accept)
        _pointing(self)

    def _clear_error(self, *_args) -> None:
        _say_error(self.error, "")

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)

    def _accept(self) -> None:
        from blacklist_detect.storage import clean_tag

        tag = clean_tag(self.name_edit.text())
        if not tag:
            _say_error(self.error, "请填写标签")
            return
        if tag in self.catalog:
            _say_error(self.error, "已有这个标签")
            return
        _say_error(self.error, "")
        self.created = tag
        self.accept()


class AddNameDialog(QDialog):
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
        self.name_error = _field(layout, "名字", self.name_edit, aside=self.added_on if added_on else None)
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
        _field(layout, "详情", self.detail_edit)
        remove = _danger("删除", self._delete) if allow_delete else None
        confirm = _primary("保存" if allow_delete else "添加", self._accept)
        # The destructive button stands apart on the left, away from 保存.
        _footer(layout, _cancel_button(self), confirm, left=remove)
        self.setMinimumWidth(440)
        self.name_edit.returnPressed.connect(self._accept)
        _pointing(self)

    def _clear_name_error(self, _text: str) -> None:
        _say_error(self.name_error, "")

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)

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
            problem = "黑名单里已经有这个名字"
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


class BatchAddDialog(QDialog):
    """Many names from one paste. Spaces separate names, or each person is 名字（说明）."""

    def __init__(self, catalog: tuple[str, ...] = (), parent=None) -> None:
        super().__init__(parent)
        from blacklist_detect.storage import TAGS

        self.names: list[str] = []
        self.annotated: list[tuple[str, tuple[str, ...], str]] | None = None
        self.catalog = catalog or TAGS
        layout = _frame(self, "批量添加")
        hint = QLabel(
            "可以这样粘贴：\n"
            "· 一行一个：名字，炸房，贴脸，原因\n"
            "· 名字（说明），说明里的标签会自动选上\n"
            "· 只有名字，用空格或换行隔开\n"
            "· 朋友用「分享」复制的名单"
        )
        hint.setObjectName("sub")
        layout.addWidget(hint)
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("把名字粘在这里")
        self.edit.setMinimumHeight(180)
        layout.addWidget(self.edit)
        self.error = QLabel("")
        self.error.setObjectName("error")
        self.error.hide()
        layout.addWidget(self.error)
        self.edit.textChanged.connect(self._clear_error)
        _footer(layout, _cancel_button(self), _primary("添加", self._accept))
        self.setMinimumWidth(460)
        _pointing(self)

    def _clear_error(self, *_args) -> None:
        _say_error(self.error, "")

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)

    def _accept(self) -> None:
        from blacklist_detect.storage import annotated_from_block, is_shared, names_from_block, parse_blacklist, parse_shared

        text = self.edit.toPlainText()
        if is_shared(text):
            # A list copied with 分享 in this app. Its tags come with it.
            self.annotated = parse_shared(text)
            self.names = [name for name, _tags, _reason in self.annotated]
            if not self.names:
                _say_error(self.error, "没有名字")
                return
            self.accept()
            return
        self.annotated = annotated_from_block(text, self.catalog)
        if self.annotated is None and ("," in text or "，" in text):
            self.annotated = parse_blacklist(text, self.catalog) or None
        if self.annotated is None:
            self.names = names_from_block(text)
        else:
            self.names = [name for name, _tags, _reason in self.annotated]
        if not self.names:
            _say_error(self.error, "没有名字")
            return
        self.accept()


SAMPLE_LOBBY = Path(__file__).resolve().parent / "assets" / "sample-lobby.jpg"


class PictureResultDialog(QDialog):
    """What one picture check read: the twelve seats, with blacklist matches in red."""

    def __init__(self, title: str, result: CheckResult | None = None, error: str = "", parent=None) -> None:
        super().__init__(parent)
        layout = _frame(self, title)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.seats: list[QLabel] = []
        if error:
            self.summary.setText(f"没能检查：{error}")
        elif result is None or not result.header_found:
            reason = result.message if result is not None else ""
            self.summary.setText(f"{reason}\n截图里要有「推演成功」大厅的画面。".strip())
        else:
            if result.hits:
                head = f"{len(result.hits)} 人在黑名单里"
            else:
                head = "这间大厅里没有黑名单"
            unclear = sum(1 for slot in result.names if slot.unclear)
            if unclear:
                head += f"，{unclear} 人没看清"
            self.summary.setText(head)
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
                wash = THEME["surface"]
                if slot.unclear:
                    cell.setText("未看清")
                    cell.setStyleSheet(base + f' color: {THEME["gray"]}; font-style: italic;')
                elif slot.index in hits:
                    hit = hits[slot.index]
                    shown = split_ellipsis(slot.visible)[0] or slot.visible
                    listed = "" if fold(hit.entry_name) == fold(shown) else f"　名单：{hit.entry_name}"
                    cell.setText(shown + listed)
                    cell.setStyleSheet(base + f' color: {THEME["red"]};')
                    wash = THEME["red_wash"]
                    # Red is not the only sign of a hit: the warning mark says it too.
                    warn = QLabel()
                    warn.setObjectName("seatWarn")
                    warn.setPixmap(line_pixmap("warning", 16, THEME["red"]))
                    warn.setStyleSheet("background: transparent;")
                    line.addWidget(warn)
                else:
                    cell.setText(split_ellipsis(slot.visible)[0] or slot.visible)
                    cell.setStyleSheet(base + f' color: {THEME["text"]};')
                tile.setStyleSheet(f"QWidget#seatTile {{ background: {wash}; border-radius: 6px; }}")
                line.addWidget(cell, 1)
                grid.addWidget(tile, slot.index // 2, slot.index % 2)
                self.seats.append(cell)
            layout.addLayout(grid)
        close = _primary("关闭", self.accept)
        _footer(layout, close)
        self.setMinimumWidth(480)
        _pointing(self)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)


class GuideDialog(QDialog):
    """Shown once on a new PC: what the app does and the three things to set up."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = _frame(self, "欢迎使用黑名单检测")
        intro = QLabel("进入「推演成功」大厅时，它会读出十二个名字，并标出黑名单里的人。只读屏幕，不碰游戏。")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        layout.addSpacing(4)
        steps = (
            ("edit", "1. 在「黑名单」里填上你的角色名称，记录里会标出你自己。"),
            ("users", "2. 在「黑名单」里添加名字，或用「批量添加」粘贴朋友分享的名单。"),
            ("check", "3. 进游戏就好。有黑名单的人时，「准备案件还原」按钮会被标红，旁边列出名字。"),
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
        _footer(layout, _primary("开始使用", self.accept))
        self.setMinimumWidth(600)
        _pointing(self)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)
