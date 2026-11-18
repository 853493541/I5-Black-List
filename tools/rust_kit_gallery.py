"""The Python kit drawn offscreen in the layout of the Rust KitGallery (rust/app/ui/kit/gallery.slint), for the
side-by-side shots in rust/app/shots/kit/. Made-up names only.

QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=1.5 APPDATA=<own folder> python tools/rust_kit_gallery.py <out dir>
writes python-light.png and python-dark.png (one half each, 800 x 900 logical pixels).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRect, Qt  # noqa: E402
from PySide6.QtGui import QPainter  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect import ui_icons, ui_kit, ui_theme, ui_widgets  # noqa: E402
from blacklist_detect.ui_theme import THEME  # noqa: E402


def button(text: str, name: str = "", enabled: bool = True) -> QPushButton:
    out = QPushButton(text)
    if name:
        out.setObjectName(name)
    out.setEnabled(enabled)
    return out


class Pills(QWidget):
    """Tags drawn the way list rows draw them: red, then 组合 blue, 我 green and +N."""

    def __init__(self, tags: list[tuple[str, str]]) -> None:
        super().__init__()
        self.tags = tags
        self.setFixedSize(60 * len(tags), 30)

    def paintEvent(self, _event) -> None:  # noqa: ANN001, N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        face = ui_widgets._pill_face()
        painter.setFont(face)
        x = 0
        for text, tone in self.tags:
            size = ui_widgets._pill_size(text, painter.fontMetrics())
            rect = QRect(x, (self.height() - size.height()) // 2, size.width(), size.height())
            wash, ink = {"blue": (THEME["blue_wash"], THEME["blue"]), "green": (THEME["green_wash"], THEME["green"])}.get(
                tone, ("", "")
            )
            ui_widgets._draw_pill(painter, rect, text, tone != "off", ui_widgets.TagPill._pad, wash, ink)
            x += size.width() + 6
        painter.end()


def row(*widgets: QWidget) -> QHBoxLayout:
    line = QHBoxLayout()
    line.setSpacing(8)
    for widget in widgets:
        line.addWidget(widget)
    line.addStretch(1)
    return line


def half() -> QWidget:
    page = QWidget()
    page.setObjectName("root")
    page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    page.setStyleSheet(ui_theme._window_style(ui_theme.chinese_family()))
    page.resize(800, 900)
    column = QVBoxLayout(page)
    column.setContentsMargins(24, 24, 24, 24)
    column.setSpacing(12)
    icons = QHBoxLayout()
    icons.setSpacing(8)
    for name in ui_icons.DRAWINGS:
        label = QLabel()
        label.setPixmap(ui_icons.pixmap(name, 16, THEME["muted"]))
        icons.addWidget(label)
    icons.addStretch(1)
    column.addLayout(icons)
    edit = ui_kit.IconButton("edit", "编辑")
    column.addLayout(row(button("保存", "primary"), button("取消"), button("删除", "danger"), button("不可用", enabled=False),
                         button("查看说明", "link"), ui_kit.IconButton("more", "更多"), edit))
    column.addLayout(row(ui_kit.Switch(True, text="直播模式"), ui_kit.Switch(False), _disabled(ui_kit.Switch(True)),
                         ui_kit.SegmentedControl([("basic", "基础模式"), ("full", "完整模式")], "full")))
    search = QLineEdit()
    search.setPlaceholderText("搜索")
    search.addAction(ui_icons.icon("search", 16), QLineEdit.ActionPosition.LeadingPosition)
    name = QLineEdit()
    name.setPlaceholderText("名字")
    column.addLayout(row(search, name, Pills([("挂机", "red"), ("组合", "blue"), ("我", "green"), ("+3", "off")])))
    grid = QGridLayout()
    grid.setSpacing(12)
    card = QFrame()
    card.setObjectName("settingsCard")
    rows = QVBoxLayout(card)
    rows.setContentsMargins(16, 4, 16, 4)
    rows.addWidget(ui_kit.SettingsRow("全局声音", None, ui_kit.ChoiceBox([("play", "播放"), ("mute", "静音")], "play")))
    rows.addWidget(ui_kit.SettingsRow("开机启动", "登录 Windows 后自动打开小工具", ui_kit.Switch(True)))
    last = ui_kit.SettingsRow("清空数据", "删除名单和设置", button("清空", "danger"))
    last.setObjectName("settingsRowLast")
    rows.addWidget(last)
    grid.addWidget(card, 0, 0)
    modal = ui_kit.Modal(page)
    body = modal.frame("添加黑名单")
    first = QLineEdit("示例坏人")
    reason = QLineEdit()
    reason.setPlaceholderText("原因（可不填）")
    body.addWidget(first)
    body.addWidget(reason)
    modal.footer(button("取消"), button("保存", "primary"), left=button("删除", "danger"))
    modal.card.setParent(page)
    modal.card.setFixedWidth(330)
    grid.addWidget(modal.card, 0, 1, 2, 1)
    empty = ui_kit.EmptyState("records", "还没有记录", "按下快捷键检查一次大厅，这里就会出现记录")
    empty.add_action(button("去检查"))
    empty.setFixedWidth(200)
    grid.addWidget(empty, 0, 2, 2, 1)
    column.addLayout(grid)
    toast = ui_kit.Toast(page)
    toast.show_message("已删除 示例坏人", "撤销", lambda: None, ms=60_000)
    toast._anim.stop()
    toast._fade.setOpacity(1.0)
    column.addStretch(1)
    return page


def _disabled(widget: QWidget) -> QWidget:
    widget.setEnabled(False)
    return widget


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    for mode in ("light", "dark"):
        ui_theme.use_theme("蓝色", mode)
        ui_theme._apply_theme(app)
        page = half()
        page.show()
        app.processEvents()
        page.grab().save(str(out / f"python-{mode}.png"))
        page.close()
    print(out)


if __name__ == "__main__":
    main()
