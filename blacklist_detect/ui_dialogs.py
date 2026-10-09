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
from blacklist_detect.ui_theme import (
    DIALOG_PAD,
    GAP,
    THEME,
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


def _confirm(parent, text: str) -> bool:
    box = QDialog(parent)
    box.setWindowTitle("黑名单检测")
    box.setFont(chinese_font())
    box.setStyleSheet(_dialog_style(chinese_family()))
    _caption_color(box)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(DIALOG_PAD, DIALOG_PAD, DIALOG_PAD, DIALOG_PAD)
    layout.setSpacing(GAP)
    message = QLabel(text)
    message.setWordWrap(True)
    layout.addWidget(message)
    buttons = QHBoxLayout()
    buttons.addStretch(1)
    yes = QPushButton("确定")
    yes.setObjectName("primary")
    yes.setAutoDefault(True)
    yes.setDefault(True)
    yes.clicked.connect(box.accept)
    buttons.addWidget(_cancel_button(box))
    buttons.addWidget(yes)
    layout.addLayout(buttons)
    box.setMinimumWidth(360)
    _pointing(box)
    return box.exec() == QDialog.Accepted


class TagEditDialog(QDialog):
    """Rename one tag, or delete it from the list and from every name."""

    def __init__(self, tag: str, catalog: tuple[str, ...], parent=None) -> None:
        super().__init__(parent)
        self.original = tag
        self.catalog = catalog
        self.renamed = tag
        self.deleted = False
        self.setWindowTitle("修改标签")
        self.setFont(chinese_font())
        self.setStyleSheet(_dialog_style(chinese_family()))
        _caption_color(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(DIALOG_PAD, DIALOG_PAD, DIALOG_PAD, DIALOG_PAD)
        layout.setSpacing(GAP)
        label = QLabel("标签")
        label.setObjectName("field")
        layout.addWidget(label)
        self.name_edit = QLineEdit(tag)
        layout.addWidget(self.name_edit)
        self.error = QLabel("")
        self.error.setObjectName("error")
        layout.addWidget(self.error)
        self.name_edit.textChanged.connect(lambda _text: self.error.setText(""))
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        remove = QPushButton("删除")
        remove.setObjectName("danger")
        remove.setAutoDefault(False)
        remove.setDefault(False)
        remove.clicked.connect(self._delete)
        # The destructive button stands apart on the left, away from 保存.
        buttons.addWidget(remove)
        buttons.addStretch(1)
        save = QPushButton("保存")
        save.setObjectName("primary")
        save.setAutoDefault(True)
        save.setDefault(True)
        save.clicked.connect(self._accept)
        buttons.addWidget(_cancel_button(self))
        buttons.addWidget(save)
        layout.addLayout(buttons)
        self.setMinimumWidth(360)
        self.name_edit.returnPressed.connect(self._accept)
        _pointing(self)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)

    def _accept(self) -> None:
        from blacklist_detect.storage import clean_tag

        renamed = clean_tag(self.name_edit.text())
        if not renamed:
            self.error.setText("请填写标签")
            return
        if renamed != self.original and renamed in self.catalog:
            self.error.setText("已有这个标签")
            return
        self.error.setText("")
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
        self.setWindowTitle("新标签")
        self.setFont(chinese_font())
        self.setStyleSheet(_dialog_style(chinese_family()))
        _caption_color(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(DIALOG_PAD, DIALOG_PAD, DIALOG_PAD, DIALOG_PAD)
        layout.setSpacing(GAP)
        label = QLabel("标签")
        label.setObjectName("field")
        layout.addWidget(label)
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)
        self.error = QLabel("")
        self.error.setObjectName("error")
        layout.addWidget(self.error)
        self.name_edit.textChanged.connect(lambda _text: self.error.setText(""))
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        buttons.addStretch(1)
        add = QPushButton("添加")
        add.setObjectName("primary")
        add.setAutoDefault(True)
        add.setDefault(True)
        add.clicked.connect(self._accept)
        buttons.addWidget(_cancel_button(self))
        buttons.addWidget(add)
        layout.addLayout(buttons)
        self.setMinimumWidth(360)
        self.name_edit.returnPressed.connect(self._accept)
        _pointing(self)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)

    def _accept(self) -> None:
        from blacklist_detect.storage import clean_tag

        tag = clean_tag(self.name_edit.text())
        if not tag:
            self.error.setText("请填写标签")
            return
        if tag in self.catalog:
            self.error.setText("已有这个标签")
            return
        self.error.setText("")
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

        self.setWindowTitle(title)
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
        self.setFont(chinese_font())
        self.setStyleSheet(_dialog_style(chinese_family()))
        _caption_color(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(DIALOG_PAD, DIALOG_PAD, DIALOG_PAD, DIALOG_PAD)
        layout.setSpacing(10)
        label_width = QFontMetrics(chinese_font()).horizontalAdvance("名字") + 8

        def add_field(title: str, widget: QWidget) -> None:
            row = QHBoxLayout()
            row.setSpacing(12)
            label = QLabel(title)
            label.setObjectName("field")
            label.setFixedWidth(label_width)
            row.addWidget(label, 0, Qt.AlignVCenter)
            row.addWidget(widget, 1)
            layout.addLayout(row)

        self.name_edit = QLineEdit(name)
        added_on = _zh_date(added_at)
        if added_on:
            name_row = QHBoxLayout()
            name_row.setSpacing(12)
            name_label = QLabel("名字")
            name_label.setObjectName("field")
            name_label.setFixedWidth(label_width)
            name_row.addWidget(name_label, 0, Qt.AlignVCenter)
            name_row.addWidget(self.name_edit, 1)
            self.added_on = QLabel(added_on)
            self.added_on.setObjectName("sub")
            self.added_on.setFixedWidth(QFontMetrics(chinese_font()).horizontalAdvance(added_on) + 2)
            name_row.addWidget(self.added_on, 0, Qt.AlignVCenter)
            layout.addLayout(name_row)
        else:
            add_field("名字", self.name_edit)
        self.name_error = QLabel("")
        self.name_error.setObjectName("error")
        self.name_error.hide()
        layout.addWidget(self.name_error)
        self.name_edit.textChanged.connect(self._clear_name_error)
        tag_row = QHBoxLayout()
        tag_row.setSpacing(12)
        tag_label = QLabel("标签")
        tag_label.setObjectName("field")
        tag_label.setFixedWidth(label_width)
        tag_row.addWidget(tag_label, 0, Qt.AlignVCenter)
        self.tag_host = _FlowHost(gap=8)
        tag_row.addWidget(self.tag_host, 1)
        layout.addLayout(tag_row)
        self._refresh_tags()
        self.detail_edit = QPlainTextEdit()
        self.detail_edit.setPlainText(detail)
        self.detail_edit.setTabChangesFocus(True)
        self.detail_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.detail_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.detail_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.detail_edit.document().setDocumentMargin(0)
        self.detail_edit.setFixedHeight(QFontMetrics(self.font()).lineSpacing() * 3 + 18)
        detail_row = QHBoxLayout()
        detail_row.setSpacing(12)
        detail_label = QLabel("详情")
        detail_label.setObjectName("field")
        detail_label.setFixedWidth(label_width)
        detail_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        detail_label.setContentsMargins(0, 8, 0, 0)
        detail_row.addWidget(detail_label, 0, Qt.AlignTop)
        detail_row.addWidget(self.detail_edit, 1)
        layout.addLayout(detail_row)
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        remove = None
        if allow_delete:
            remove = QPushButton("删除")
            remove.setObjectName("danger")
            remove.setAutoDefault(False)
            remove.setDefault(False)
            remove.clicked.connect(self._delete)
            # The destructive button stands apart on the left, away from 保存.
            buttons.addWidget(remove)
        buttons.addStretch(1)
        confirm = QPushButton("保存" if allow_delete else "添加")
        confirm.setObjectName("primary")
        confirm.setAutoDefault(True)
        confirm.setDefault(True)
        confirm.clicked.connect(self._accept)
        buttons.addWidget(_cancel_button(self))
        buttons.addWidget(confirm)
        layout.addLayout(buttons)
        self.setMinimumWidth(420)
        self.name_edit.returnPressed.connect(self._accept)
        _pointing(self)

    def _clear_name_error(self, _text: str) -> None:
        self.name_error.setText("")
        self.name_error.hide()

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
            self.name_error.setText(problem)
            self.name_error.show()
            return
        self.name_error.setText("")
        self.name_error.hide()
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

        self.setWindowTitle("批量添加")
        self.names: list[str] = []
        self.annotated: list[tuple[str, tuple[str, ...], str]] | None = None
        self.catalog = catalog or TAGS
        self.setFont(chinese_font())
        self.setStyleSheet(_dialog_style(chinese_family()))
        _caption_color(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(DIALOG_PAD, DIALOG_PAD, DIALOG_PAD, DIALOG_PAD)
        layout.setSpacing(GAP)
        hint = QLabel(
            "可以这样粘贴：\n"
            "· 一行一个：名字，炸房，贴脸，原因\n"
            "· 名字（说明），说明里的标签会自动选上\n"
            "· 只有名字，用空格或换行隔开\n"
            "· 朋友用「分享」复制的名单"
        )
        hint.setObjectName("field")
        layout.addWidget(hint)
        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("把名字粘在这里")
        self.edit.setMinimumHeight(180)
        layout.addWidget(self.edit)
        self.error = QLabel("")
        self.error.setObjectName("error")
        layout.addWidget(self.error)
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        buttons.addStretch(1)
        confirm = QPushButton("添加")
        confirm.setObjectName("primary")
        confirm.setAutoDefault(True)
        confirm.setDefault(True)
        confirm.clicked.connect(self._accept)
        buttons.addWidget(_cancel_button(self))
        buttons.addWidget(confirm)
        layout.addLayout(buttons)
        self.setMinimumWidth(420)
        _pointing(self)

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
                self.error.setText("没有名字")
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
            self.error.setText("没有名字")
            return
        self.accept()


SAMPLE_LOBBY = Path(__file__).resolve().parent / "assets" / "sample-lobby.jpg"


class PictureResultDialog(QDialog):
    """What one picture check read: the twelve seats, with blacklist matches in red."""

    def __init__(self, title: str, result: CheckResult | None = None, error: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFont(chinese_font())
        self.setStyleSheet(_dialog_style(chinese_family()))
        _caption_color(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(DIALOG_PAD, DIALOG_PAD, DIALOG_PAD, DIALOG_PAD)
        layout.setSpacing(GAP)
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
                cell = QLabel()
                cell.setMinimumWidth(200)
                base = f'font-family: "{chinese_family()}"; border-radius: 8px; padding: 8px 12px;'
                if slot.unclear:
                    cell.setText("未看清")
                    cell.setStyleSheet(base + f' color: {THEME["gray"]}; background: {THEME["surface"]}; font-style: italic;')
                elif slot.index in hits:
                    hit = hits[slot.index]
                    shown = split_ellipsis(slot.visible)[0] or slot.visible
                    listed = "" if fold(hit.entry_name) == fold(shown) else f"　名单：{hit.entry_name}"
                    cell.setText(shown + listed)
                    cell.setStyleSheet(base + f' color: {THEME["red"]}; background: {THEME["red_wash"]};')
                else:
                    cell.setText(split_ellipsis(slot.visible)[0] or slot.visible)
                    cell.setStyleSheet(base + f' color: {THEME["text"]}; background: {THEME["surface"]};')
                grid.addWidget(cell, slot.index // 2, slot.index % 2)
                self.seats.append(cell)
            layout.addLayout(grid)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close = QPushButton("关闭")
        close.setObjectName("primary")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self.setMinimumWidth(460)
        _pointing(self)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)


class GuideDialog(QDialog):
    """Shown once on a new PC: what the app does and the three things to set up."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.wants_test = False
        self.setWindowTitle("欢迎使用黑名单检测")
        self.setFont(chinese_font())
        self.setStyleSheet(_dialog_style(chinese_family()))
        _caption_color(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(DIALOG_PAD, DIALOG_PAD, DIALOG_PAD, DIALOG_PAD)
        layout.setSpacing(GAP)
        intro = QLabel("进入「推演成功」大厅时，它会读出十二个名字，并标出黑名单里的人。只读屏幕，不碰游戏。")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        steps = (
            "1. 在「设置」里填上你的角色名称，记录里会标出你自己。",
            "2. 在「黑名单」里添加名字，或用「批量添加」粘贴朋友分享的名单。",
            "3. 进游戏就好。有黑名单的人时，「准备案件还原」按钮会被标红，旁边列出名字。",
        )
        for text in steps:
            step = QLabel(text)
            step.setObjectName("sub")
            step.setWordWrap(True)
            layout.addWidget(step)
        buttons = QHBoxLayout()
        buttons.setSpacing(GAP)
        buttons.addStretch(1)
        test = QPushButton("测试一下")
        test.setAutoDefault(False)
        test.setToolTip("用自带的大厅截图试一次识别")
        test.clicked.connect(self._test)
        buttons.addWidget(test)
        start = QPushButton("开始使用")
        start.setObjectName("primary")
        start.setDefault(True)
        start.clicked.connect(self.accept)
        buttons.addWidget(start)
        layout.addLayout(buttons)
        self.setMinimumWidth(600)
        _pointing(self)

    def _test(self) -> None:
        self.wants_test = True
        self.accept()

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)
