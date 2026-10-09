"""Main window, tray status, and the lobby check loop."""

from __future__ import annotations

import queue
import sys
import time
from datetime import datetime

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFontMetrics,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from blacklist_detect import __version__
from blacklist_detect.capture import (
    CaptureUnavailable,
    capture_capability_message,
    capture_displays,
    capture_top_band,
    lock_foreground,
    virtual_origin,
)
from blacklist_detect.hotkey import GlobalHotkey, parse_hotkey
from blacklist_detect.logs import log, log_dir, on_uncaught, setup_logging
from blacklist_detect.match import NameLabel, fold, format_hit, match_label, seat_number, split_ellipsis
from blacklist_detect.model import Entry
from blacklist_detect.ocr_engine import OcrUnavailable, get_engine
from blacklist_detect.paths import instance_key
from blacklist_detect.pipeline import (
    CheckResult,
    Hit,
    NameSlot,
    band_signature,
    check_frames,
    check_image,
    glance_title,
    same_band,
)
from blacklist_detect.storage import Store, describe_entry, tag_text
from blacklist_detect.ui_dialogs import (
    SAMPLE_LOBBY,
    AddNameDialog,
    BatchAddDialog,
    GuideDialog,
    PictureResultDialog,
    TagCreateDialog,
    TagEditDialog,
    _confirm,
)
from blacklist_detect.ui_icons import pixmap as line_pixmap
from blacklist_detect.ui_kit import (
    ConfirmDialog,
    EmptyState,
    IconButton,
    SegmentedControl,
    SettingsSection,
    Switch,
    TabButton,
    Toast,
)
from blacklist_detect.ui_overlay import (
    _COVER_OUTSET,
    ClearMark,
    HitCard,
    LobbyPanel,
    _cover_radius,
    _pin_topmost,
    _play_hit_sound,
    native_to_logical,
)
from blacklist_detect.ui_theme import (
    APPEARANCES,
    BODY_PT,
    GAP,
    PAD,
    ROW_H,
    SMALL_PT,
    THEME,
    THEMES,
    _apply_theme,
    _caption_color,
    _menu_style,
    _page,
    _pointing,
    _window_style,
    accent_of,
    chinese_family,
    chinese_font,
    is_dark,
    record_font,
    ui_font,
    use_theme,
    wants_dark,
)
from blacklist_detect.ui_widgets import (
    DayFolderIcon,
    NewTagButton,
    TagPill,
    ThemeSwatch,
    _check_icon,
    _ColumnHeader,
    _DetailTip,
    _FlowHost,
    _icon,
    _local_moment,
    _PlainItemDelegate,
    _TagRow,
    _watch_mark,
    _zh_ago,
    _zh_clock,
    masked_name,
)
from blacklist_detect.watch import GLANCE_INTERVAL_MS, LobbyWatch

__all__ = [
    "AddNameDialog",
    "BatchAddDialog",
    "DayFolderIcon",
    "GuideDialog",
    "MainWindow",
    "PictureResultDialog",
    "SAMPLE_LOBBY",
    "TagCreateDialog",
    "TagEditDialog",
    "TagPill",
    "_COVER_OUTSET",
    "_apply_theme",
    "_cover_radius",
    "_icon",
    "_play_hit_sound",
    "_zh_clock",
    "chinese_font",
    "instance_key",
    "listen_for_instances",
    "masked_name",
    "native_to_logical",
    "notify_running_instance",
    "run_app",
]


def _claim_windows_app() -> None:
    """Tell Windows this is its own app, so the taskbar uses our icon instead of Python's."""
    if sys.platform != "win32":
        return
    import ctypes

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Local.BlackListDetect")


def run_app() -> int:
    log_path = setup_logging()
    log.info("Start %s, Python %s, %s", __version__, sys.version.split()[0], sys.platform)
    _claim_windows_app()
    app = QApplication(sys.argv)
    app.setApplicationName("黑名单检测")
    app.setApplicationVersion(__version__)
    key = instance_key()
    if notify_running_instance(key):
        log.info("Already running. Brought the open window forward.")
        return 0
    app.setWindowIcon(_icon())
    app.setFont(chinese_font())
    _apply_theme(app)
    try:
        window = MainWindow()
    except Exception as exc:
        log.critical("The window could not open", exc_info=True)
        from PySide6.QtWidgets import QMessageBox

        where = f"\n\n详情在 {log_path}" if log_path else ""
        QMessageBox.critical(None, "黑名单检测", f"程序没能打开：{exc}{where}")
        return 1
    window.instance_server = listen_for_instances(key, window._show_from_tray, window.quit_app)
    on_uncaught(window.report_uncaught)
    window.show()
    window.start_warmup()
    QTimer.singleShot(0, window.show_first_run_guide)
    code = app.exec()
    log.info("Exit %s", code)
    return code


def notify_running_instance(key: str) -> bool:
    """Ask a copy that is already open to show its window. False when none is open."""
    from PySide6.QtNetwork import QLocalSocket

    socket = QLocalSocket()
    socket.connectToServer(key)
    if not socket.waitForConnected(300):
        return False
    socket.write(b"show")
    socket.flush()
    socket.waitForBytesWritten(300)
    socket.disconnectFromServer()
    return True


def listen_for_instances(key: str, on_show, on_quit=None):  # noqa: ANN001
    """Answer a second copy of the app, or the local installer.

    "show" (or nothing) brings this window forward, because two copies would
    overwrite each other's files. "quit" closes the app so its files can be updated.
    """
    from PySide6.QtNetwork import QLocalServer

    QLocalServer.removeServer(key)
    server = QLocalServer()
    server.listen(key)

    def accept() -> None:
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            if not connection.bytesAvailable():
                connection.waitForReadyRead(300)
            message = bytes(connection.readAll()).strip()
            connection.disconnectFromServer()
            connection.deleteLater()
            if message == b"quit" and on_quit is not None:
                on_quit()
            else:
                on_show()

    server.newConnection.connect(accept)
    return server


def _qt_key_name(key: int) -> str | None:
    if Qt.Key_A <= key <= Qt.Key_Z or Qt.Key_0 <= key <= Qt.Key_9:
        return chr(key)
    if Qt.Key_F1 <= key <= Qt.Key_F12:
        return f"F{key - Qt.Key_F1 + 1}"
    return None


class CheckWorker(QThread):
    """Owns the OCR engine. Paddle is loaded on this thread and reused here."""

    done = Signal(object)
    placed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._queue: queue.Queue = queue.Queue()
        self.running_job = False

    def request(self, fn, kind: str = "check") -> bool:
        if self.running_job:
            return False
        self.running_job = True
        self._queue.put((kind, fn))
        if not self.isRunning():
            self.start()
        return True

    def run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            kind, fn = item
            try:
                self.done.emit((kind, "ok", fn()))
            except Exception as exc:
                self.done.emit((kind, "err", exc))

    def stop(self) -> None:
        self._queue.put(None)


class MainWindow(QMainWindow):
    uncaught = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.uncaught.connect(self._show_uncaught)
        self.setWindowTitle(f"黑名单检测 {__version__}")
        self.store = Store()
        use_theme(self.store.theme, self.store.appearance)
        self.setMinimumSize(900, 560)
        saved = self.store.window_size or (900, 560)
        self.resize(saved[0], saved[1])
        self.setWindowIcon(_icon())
        self.hotkey = GlobalHotkey(self.check_now)
        self.worker = CheckWorker()
        self.worker.done.connect(self._on_worker)
        self.worker.placed.connect(self._on_lobby_placed)
        self.watch = LobbyWatch()
        # 跟随系统 looks at Windows every few seconds; a registry read costs nothing.
        self._appearance_timer = QTimer(self)
        self._appearance_timer.setInterval(3000)
        self._appearance_timer.timeout.connect(self._follow_system)
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(GLANCE_INTERVAL_MS)
        self._watch_timer.timeout.connect(self._auto_tick)
        self._closing = False
        self.panel = LobbyPanel()
        self.hit_card = HitCard()
        self.clear_mark = ClearMark()
        self._panel_hide_timer = QTimer(self)
        self._panel_hide_timer.setSingleShot(True)
        self._panel_hide_timer.timeout.connect(self._hide_panel_after_title)
        self._live_check = False
        self._rescan_active = False
        self._history_hover = (-1, -1)
        self._closed_days: set[str] = set()
        self._day_hover = -1
        self._check_started: float | None = None
        self._release_foreground = False
        self._told_tray = False
        self._manual_check = False
        self._problem = ""
        self._told_problems: set[str] = set()
        self._glance_pause_until = 0.0
        self._warm_started: float | None = None
        self._picture_pending = ""
        self._picture_dialog = None
        # The last glance, kept by the worker thread to skip a screen that has not changed.
        self._last_band = None
        self._last_glance: bool | None = None
        self.instance_server = None
        self._status_kind = "idle"
        self._watch_tone = "idle"
        self._watch_full = "未开启"
        self._watch_tip = ""
        self._blacklist_sort: tuple[int, bool] | None = None
        self._blacklist_hover = -1
        self._build()
        self._apply_style()
        _caption_color(self)
        self._show_list()
        self._reload_history()
        self._restore_hotkey()
        if self.store.auto_capture:
            app = QApplication.instance()
            if app is not None and app.platformName() == "offscreen":
                self._watch_timer.setInterval(60_000)
            self._watch_timer.start()
        self._sync_watch_idle()
        notice = self.store.load_warning or capture_capability_message()
        if notice:
            self._set_result(notice, "hit", "error")

    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(PAD, PAD, PAD, PAD)
        outer.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.history_tab = self.tabs.addTab(self._history_page(), "记录")
        self.blacklist_tab = self.tabs.addTab(self._list_page(), "黑名单")
        self.tabs.addTab(self._settings_page(), "设置")
        self.tabs.tabBar().hide()
        self.tabs.currentChanged.connect(self._sync_tab_buttons)
        header = QWidget()
        header.setObjectName("tabHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(4)
        self._tab_buttons: list[TabButton] = []
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        for index in range(self.tabs.count()):
            button = TabButton(self.tabs.tabText(index))
            self._tab_group.addButton(button, index)
            self._tab_buttons.append(button)
            header_row.addWidget(button, 0, Qt.AlignBottom)
        self._tab_group.idClicked.connect(self.tabs.setCurrentIndex)
        header_row.addStretch(1)
        # The status says what the last check found; the switch beside it sets the mode.
        self.mode_cluster = QWidget()
        self.mode_cluster.setObjectName("modeCluster")
        cluster_row = QHBoxLayout(self.mode_cluster)
        cluster_row.setContentsMargins(0, 0, 0, 0)
        cluster_row.setSpacing(6)
        self.watch_mark = QLabel()
        self.watch_mark.setPixmap(_watch_mark(THEME["muted"]))
        self.watch_label = QLabel("未开启")
        self.watch_label.setObjectName("idle")
        self.watch_label.setMaximumWidth(200)
        self.watch_label.setFont(chinese_font(BODY_PT))
        cluster_row.addWidget(self.watch_label, 0, Qt.AlignVCenter)
        cluster_row.addWidget(self.watch_mark, 0, Qt.AlignVCenter)
        header_row.addWidget(self.mode_cluster, 0, Qt.AlignVCenter)
        divider = QFrame()
        divider.setObjectName("headerDivider")
        divider.setFixedSize(1, 16)
        header_row.addSpacing(GAP)
        header_row.addWidget(divider, 0, Qt.AlignVCenter)
        header_row.addSpacing(GAP)
        self.auto_switch = Switch(self.store.auto_capture, text="自动检查")
        self.auto_switch.toggled.connect(self._toggle_auto)
        header_row.addWidget(self.auto_switch, 0, Qt.AlignVCenter)
        self._sync_tab_buttons(self.tabs.currentIndex())
        outer.addWidget(header)
        outer.addWidget(self.tabs)
        self.toast = Toast(root)

        self.tray = None
        if QSystemTrayIcon_available():
            from PySide6.QtWidgets import QSystemTrayIcon

            self.tray = QSystemTrayIcon(_icon(), self)
            self.tray.setToolTip(f"黑名单检测 {__version__}")
            self.tray_menu = QMenu()
            self.tray_menu.setFont(chinese_font())
            self.tray_menu.setStyleSheet(_menu_style(chinese_family()))
            self.tray_menu.addAction("打开", self._show_from_tray)
            self.tray_menu.addAction("退出", self.close)
            self.tray.setContextMenu(self.tray_menu)
            self.tray.activated.connect(self._on_tray)
            self.tray.show()

    def _list_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        _page(layout)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.list_search = QLineEdit()
        self.list_search.setPlaceholderText("搜索名字、标签或原因")
        self.list_search.setClearButtonEnabled(True)
        self.list_search.setMaximumWidth(360)
        self.list_search.textChanged.connect(self._on_search_text)
        toolbar.addWidget(self.list_search, 1)
        toolbar.addStretch(1)
        batch = QPushButton("批量添加")
        batch.clicked.connect(self._add_many_by_dialog)
        add = QPushButton("添加")
        add.setObjectName("primary")
        add.clicked.connect(self._add_by_dialog)
        toolbar.addWidget(batch)
        toolbar.addWidget(add)
        # 分享 and 清空列表 are used now and then, so they wait under 更多 instead of beside 添加.
        self.more_button = IconButton("more", "更多")
        self.more_menu = QMenu(self)
        self.share_action = self.more_menu.addAction("分享", self._share_list)
        self.share_action.setToolTip("复制整个名单。朋友在「批量添加」里粘贴即可。")
        self.more_menu.addSeparator()
        self.clear_list_action = self.more_menu.addAction("清空列表", self._clear_list)
        self.more_button.clicked.connect(self._open_more_menu)
        toolbar.addWidget(self.more_button)
        self.blacklist_table = QTableWidget(0, 4)
        self.blacklist_table.setObjectName("blacklist")
        name_header = _ColumnHeader(self.blacklist_table)
        name_header.names_hidden = self.store.names_hidden
        name_header.on_eye = self._toggle_name_hiding
        self.blacklist_table.setHorizontalHeader(name_header)
        self.blacklist_table.setHorizontalHeaderLabels(["名字", "标签", "原因", "最后遇到"])
        for column in range(4):
            item = self.blacklist_table.horizontalHeaderItem(column)
            if item is not None:
                item.setToolTip("拖动换顺序，拖边缘改宽度")
        header = self.blacklist_table.horizontalHeader()
        header.setStretchLastSection(True)
        for column in range(4):
            header.setSectionResizeMode(column, header.ResizeMode.Interactive)
        header.setMinimumSectionSize(72)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionsClickable(True)
        header.setSectionsMovable(True)
        header.setHighlightSections(False)
        header.setSortIndicatorShown(False)
        header.sectionClicked.connect(self._sort_blacklist)
        header.sectionMoved.connect(self._save_column_order)
        header.sectionResized.connect(self._save_column_width)
        self._apply_column_widths()
        self._apply_column_order()
        self.blacklist_table.verticalHeader().setVisible(False)
        self.blacklist_table.verticalHeader().setDefaultSectionSize(ROW_H)
        self.blacklist_table.setSelectionMode(QTableWidget.SingleSelection)
        self.blacklist_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.blacklist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.blacklist_table.setShowGrid(False)
        self.blacklist_table.setAutoScroll(False)
        self.blacklist_table.setWordWrap(False)
        self.blacklist_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.blacklist_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.blacklist_table.setFocusPolicy(Qt.NoFocus)
        self.blacklist_table.setItemDelegate(_PlainItemDelegate(self.blacklist_table))
        self.blacklist_table.setMouseTracking(True)
        self.blacklist_table.viewport().setMouseTracking(True)
        self.blacklist_table.viewport().installEventFilter(self)
        self.blacklist_table.setCursor(Qt.PointingHandCursor)
        self.blacklist_table.cellEntered.connect(self._hover_blacklist_row)
        self.blacklist_table.cellClicked.connect(self._edit_row)
        self.blacklist_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.blacklist_table.customContextMenuRequested.connect(self._blacklist_menu)
        self.detail_tip = _DetailTip()
        self.detail_tip.installEventFilter(self)
        self._detail_tip_timer = QTimer(self)
        self._detail_tip_timer.setSingleShot(True)
        self._detail_tip_timer.setInterval(160)
        self._detail_tip_timer.timeout.connect(self._hide_detail_tip)
        self.list_empty = EmptyState("users", "还没有名字")
        self.list_hint = self.list_empty.title
        layout.addLayout(toolbar)
        layout.addWidget(self.blacklist_table, 1)
        layout.addWidget(self.list_empty, 1)
        return page

    def _history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        _page(layout)
        body = QHBoxLayout()
        body.setSpacing(GAP)
        side = QWidget()
        side.setFixedWidth(168)
        self.history_side = side
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(GAP)
        self.history_list = QListWidget()
        self.history_list.setObjectName("history")
        self.history_list.setFocusPolicy(Qt.NoFocus)
        self.history_list.setItemDelegate(_PlainItemDelegate(self.history_list))
        self.history_list.setCursor(Qt.PointingHandCursor)
        self.history_list.setMouseTracking(True)
        self.history_list.viewport().setMouseTracking(True)
        self.history_list.viewport().installEventFilter(self)
        self.history_list.currentRowChanged.connect(self._on_history_picked)
        self.history_list.itemClicked.connect(self._on_history_clicked)
        side_layout.addWidget(self.history_list, 1)
        self.clear_history_button = QPushButton("清空记录")
        self.clear_history_button.clicked.connect(self._ask_clear_history)
        side_layout.addWidget(self.clear_history_button)
        body.addWidget(side)
        record = QWidget()
        record.setObjectName("recordCard")
        record.setAttribute(Qt.WA_StyledBackground, True)
        self.record_card = record
        names = QVBoxLayout(record)
        # Inset by the border so the card's outline and rounded foot stay visible.
        names.setContentsMargins(1, 1, 1, 6)
        names.setSpacing(0)
        head_bar = QWidget()
        head_bar.setObjectName("tableHead")
        head_bar.setAttribute(Qt.WA_StyledBackground, True)
        head = QHBoxLayout(head_bar)
        head.setContentsMargins(16, 12, 16, 12)
        head.setSpacing(GAP)
        catalog = QLabel("模仿者游戏（12人狂欢场）")
        catalog.setFont(record_font())
        catalog.setStyleSheet(
            f'color: {THEME["text"]}; background: transparent; font-family: "{chinese_family()}"; font-size: {BODY_PT}pt;'
        )
        head.addWidget(catalog)
        head.addStretch(1)
        self.record_time = QLabel("")
        self.record_time.setObjectName("sub")
        head.addWidget(self.record_time)
        names.addWidget(head_bar)
        self.history_table = QTableWidget(0, 2)
        self.history_table.setObjectName("recordNames")
        self.history_table.horizontalHeader().setVisible(False)
        header = self.history_table.horizontalHeader()
        header.setStretchLastSection(True)
        for column in range(2):
            header.setSectionResizeMode(column, header.ResizeMode.Stretch)
        self.history_table.setCursor(Qt.PointingHandCursor)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.verticalHeader().setDefaultSectionSize(ROW_H + 4)
        self.history_table.setSelectionMode(QTableWidget.NoSelection)
        self.history_table.setFocusPolicy(Qt.NoFocus)
        self.history_table.setItemDelegate(_PlainItemDelegate(self.history_table))
        self.history_table.setShowGrid(False)
        self.history_table.setMouseTracking(True)
        self.history_table.viewport().setMouseTracking(True)
        self.history_table.viewport().installEventFilter(self)
        self.history_table.cellEntered.connect(self._hover_history_cell)
        self.history_table.cellClicked.connect(self._on_history_cell)
        self.history_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_table.customContextMenuRequested.connect(self._history_menu)
        names.addWidget(self.history_table, 1)
        body.addWidget(record, 1)
        self.history_empty = EmptyState("records", "还没有记录", "进入「推演成功」大厅时会自动检查，并记在这里。")
        self.history_hint = self.history_empty.title
        self.history_test_button = QPushButton("测试一下")
        self.history_test_button.setToolTip("用自带的大厅截图试一次识别，不用进游戏")
        self.history_test_button.setAutoDefault(False)
        self.history_test_button.clicked.connect(self.test_recognition)
        self.history_empty.add_action(self.history_test_button)
        body.addWidget(self.history_empty, 1)
        layout.addLayout(body, 1)
        return page

    def _settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        _page(layout)
        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("settingsBody")
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, GAP, GAP)
        column.setSpacing(GAP)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        metrics = QFontMetrics(chinese_font())
        name_width = metrics.horizontalAdvance("中" * 7) + 28
        slot = metrics.horizontalAdvance("手动检查") + 36
        label_width = metrics.horizontalAdvance("角色名称") + 8

        def section(title: str) -> SettingsSection:
            card = SettingsSection(title, label_width)
            card.setMaximumWidth(760)
            column.addWidget(card)
            return card

        general = section("常规")
        self.player_edit = QLineEdit(self.store.player_name)
        self.player_edit.setPlaceholderText("游戏里的名字")
        self.player_edit.editingFinished.connect(self._save_player_name)
        self.player_edit.setFixedWidth(name_width)
        general.add_row("角色名称", self.player_edit)

        check = section("检查")
        self.auto_mode = SegmentedControl(
            [("auto", "自动检查"), ("manual", "手动检查")], "auto" if self.store.auto_capture else "manual"
        )
        self.auto_on = self.auto_mode.buttons["auto"]
        self.auto_off = self.auto_mode.buttons["manual"]
        self.auto_mode.changed.connect(self._on_auto_mode)
        self.hotkey_edit = QLineEdit()
        self.hotkey_edit.setReadOnly(True)
        self.hotkey_edit.setPlaceholderText("无")
        self.hotkey_edit.setFixedWidth(slot)
        self.hotkey_edit.setCursor(Qt.PointingHandCursor)
        self.hotkey_edit.installEventFilter(self)
        check.add_row("方式", self.auto_mode, self.hotkey_edit)
        # Hotkey problems show right under the hotkey they are about.
        self.settings_label = QLabel("")
        self.settings_label.setObjectName("rowHint")
        self.settings_label.setWordWrap(True)
        self.settings_label.hide()
        check.add_widget(self.settings_label, separated=False, indent=True)
        self.test_button = QPushButton("测试一下")
        self.test_button.setToolTip("用自带的大厅截图试一次识别，不用进游戏")
        self.test_button.setAutoDefault(False)
        self.test_button.clicked.connect(self.test_recognition)
        self.picture_button = QPushButton("检查截图")
        self.picture_button.setToolTip("选一张大厅截图，看看里面有没有黑名单")
        self.picture_button.setAutoDefault(False)
        self.picture_button.clicked.connect(self.check_picture)
        check.add_row("识别", self.test_button, self.picture_button)
        self.sound_switch = Switch(self.store.hit_sound)
        self.sound_switch.setAccessibleName("提示音")
        self.sound_switch.toggled.connect(self._set_hit_sound)
        check.add_row("提示音", self.sound_switch, hint="发现黑名单时响一声")

        look = section("外观")
        self.appearance_control = SegmentedControl(
            [("light", "浅色"), ("dark", "深色"), ("system", "跟随系统")], self.store.appearance
        )
        self.appearance_buttons: dict[str, QPushButton] = self.appearance_control.buttons
        self.appearance_control.changed.connect(self._set_appearance)
        look.add_row("模式", self.appearance_control)
        swatch_host = QWidget()
        swatches = QHBoxLayout(swatch_host)
        swatches.setSpacing(8)
        swatches.setContentsMargins(0, 0, 0, 0)
        self.theme_buttons: dict[str, ThemeSwatch] = {}
        for name in THEMES:
            swatch = ThemeSwatch(name, THEMES[name]["accent"])
            swatch.chosen.connect(self._set_theme)
            self.theme_buttons[name] = swatch
            swatches.addWidget(swatch, 0, Qt.AlignVCenter)
        look.add_row("主题", swatch_host)

        tags = section("标签")
        tag_row = QWidget()
        tag_line = QHBoxLayout(tag_row)
        tag_line.setContentsMargins(0, 4, 0, 8)
        tag_line.setSpacing(GAP)
        tag_host = QWidget()
        self.tag_settings = QVBoxLayout(tag_host)
        self.tag_settings.setSpacing(0)
        self.tag_settings.setContentsMargins(0, 0, 0, 0)
        self._fill_tag_settings()
        tag_line.addWidget(tag_host, 1)
        recheck = QPushButton("按原因补标签")
        recheck.setObjectName("recheck")
        recheck.setFont(chinese_font(SMALL_PT))
        recheck.setAutoDefault(False)
        recheck.setCursor(Qt.PointingHandCursor)
        recheck.clicked.connect(self._recheck_tags)
        tag_line.addWidget(recheck, 0, Qt.AlignTop)
        tags.add_widget(tag_row, separated=False)

        data = section("数据")
        self.data_button = QPushButton("打开数据文件夹")
        self.data_button.setToolTip("名单、设置、每天的备份 backups 和日志 logs 都在这里")
        self.data_button.setAutoDefault(False)
        self.data_button.setCursor(Qt.PointingHandCursor)
        self.data_button.clicked.connect(self.open_data_folder)
        reset = QPushButton("清除数据且复原")
        reset.setObjectName("danger")
        reset.setFont(ui_font())
        self.reset_button = reset
        reset.setAutoDefault(False)
        reset.setCursor(Qt.PointingHandCursor)
        reset.clicked.connect(self._ask_reset)
        # The destructive one sits apart, at the far end of the row.
        control = data.add_row("控制", self.data_button)
        control.addWidget(reset, 0, Qt.AlignVCenter)

        about = section("关于")
        about.add_row("版本", QLabel(__version__))
        column.addStretch(1)
        return page

    def _fill_tag_settings(self) -> None:
        while self.tag_settings.count():
            item = self.tag_settings.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        host = _FlowHost(gap=6)
        for tag in self.store.tag_catalog():
            pill = TagPill(tag, clickable=True)
            pill.clicked.connect(self._edit_settings_tag)
            host.addWidget(pill)
        create = NewTagButton()
        create.clicked.connect(self._create_settings_tag)
        host.addWidget(create)
        self.tag_settings.addWidget(host)

    def _recheck_tags(self) -> None:
        self.store.recheck_tags()
        self._show_list()

    def _create_settings_tag(self) -> None:
        dialog = TagCreateDialog(self.store.tag_catalog(), parent=self)
        if dialog.exec() != QDialog.Accepted or not dialog.created:
            return
        if not self.store.add_custom_tag(dialog.created):
            return
        self.store.save_settings()
        self._fill_tag_settings()

    def _edit_settings_tag(self, tag: str) -> None:
        dialog = TagEditDialog(tag, self.store.tag_catalog(), parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        if dialog.deleted:
            if self.store.remove_custom_tag(tag):
                self._refresh_tag_views()
            return
        if dialog.renamed == tag:
            return
        if self.store.rename_tag(tag, dialog.renamed) == "renamed":
            self._refresh_tag_views()

    def _refresh_tag_views(self) -> None:
        self._fill_tag_settings()
        self._show_list()
        self._show_history_scan(self._selected_scan())

    def _remove_settings_tag(self, tag: str) -> None:
        names = [entry.name for entry in self.store.entries if tag in entry.tags]
        if not names:
            text = f"没有名字使用「{tag}」。确定删除？"
        else:
            shown = "、".join(names[:6])
            if len(names) > 6:
                shown += "等"
            text = f"{len(names)} 个名字使用「{tag}」：{shown}。确定删除？"
        if not _confirm(self, text):
            return
        if not self.store.remove_custom_tag(tag):
            return
        self._refresh_tag_views()

    def _set_settings_note(self, text: str) -> None:
        self.settings_label.setText(text)
        self.settings_label.setVisible(bool(text))

    def _ask_reset(self) -> None:
        if not _confirm(self, "清除数据且复原会清空角色名称、记录、黑名单和设置。确定清除？"):
            return
        self.store.reset()
        self.hotkey.clear()
        self.player_edit.setText("")
        self.hotkey_edit.clearFocus()
        self._show_hotkey()
        self._sync_hotkey_mode()
        self._set_settings_note("")
        self._sync_auto_controls()
        self.sound_switch.blockSignals(True)
        self.sound_switch.setChecked(self.store.hit_sound)
        self.sound_switch.blockSignals(False)
        if not self._watch_timer.isActive():
            self.watch = LobbyWatch()
            self._watch_timer.start()
        self._sync_watch_idle()
        use_theme(self.store.theme, self.store.appearance)
        self._mark_appearance_buttons()
        icon = _icon()
        self.setWindowIcon(icon)
        if self.tray is not None:
            self.tray.setIcon(icon)
        self._apply_style()
        _caption_color(self)
        self._apply_column_widths()
        self._apply_column_order()
        self._panel_hide_timer.stop()
        self.panel.hide()
        self.hit_card.hide()
        self.clear_mark.hide()
        self._reload_history()

    def _save_player_name(self) -> None:
        name = self.player_edit.text().strip()
        if name == self.store.player_name:
            return
        self.store.player_name = name
        self.store.save_settings()
        self._show_history_scan(self._selected_scan())

    def _is_my_name(self, shown: str) -> bool:
        mine = self.store.player_name
        if not mine or not shown:
            return False
        return bool(match_label(NameLabel(raw=shown, visible=shown, truncated=False), [Entry(mine)]))

    def _apply_style(self) -> None:
        _apply_theme()
        self.setFont(chinese_font())
        self.setStyleSheet(_window_style(chinese_family()))
        self.setFont(chinese_font())
        for button in getattr(self, "_tab_buttons", []):
            button.update()
        if hasattr(self, "auto_switch"):
            self.auto_switch.update()
        if getattr(self, "reset_button", None) is not None:
            self.reset_button.setFont(ui_font())
        _pointing(self)
        self._mark_theme_buttons()
        if hasattr(self, "tag_settings"):
            self._fill_tag_settings()
        if hasattr(self, "watch_label"):
            self._set_result(self._watch_full, self._watch_tone, self._status_kind, self._watch_tip)
        if hasattr(self, "detail_tip"):
            self.detail_tip.apply_theme()
        if hasattr(self, "list_empty"):
            self.list_empty.refresh()
            self.more_button.refresh()
        if hasattr(self, "history_empty"):
            self.history_empty.refresh()

    def _mark_theme_buttons(self) -> None:
        for name, swatch in self.theme_buttons.items():
            # Show each accent as it looks in the current 浅色/深色, not always the light one.
            swatch._color = accent_of(name)
            swatch.set_selected(name == self.store.theme)

    def _set_theme(self, name: str) -> None:
        if name not in THEMES or name == self.store.theme:
            self._mark_theme_buttons()
            return
        self.store.theme = name
        self.store.save_settings()
        self._restyle()

    def _set_appearance(self, appearance: str) -> None:
        if appearance not in APPEARANCES:
            return
        self.store.appearance = appearance
        self.store.save_settings()
        self._mark_appearance_buttons()
        if appearance == "system":
            self._appearance_timer.start()
        else:
            self._appearance_timer.stop()
        if wants_dark(appearance) != is_dark():
            self._restyle()

    def _follow_system(self) -> None:
        """跟随系统: switch when Windows switches between light and dark apps."""
        if self.store.appearance == "system" and wants_dark("system") != is_dark():
            self._restyle()

    def _mark_appearance_buttons(self) -> None:
        if hasattr(self, "appearance_control"):
            self.appearance_control.set_current(self.store.appearance)

    def _restyle(self) -> None:
        """Repaint every window after the accent color or 浅色/深色 changed."""
        use_theme(self.store.theme, self.store.appearance)
        icon = _icon()
        self.setWindowIcon(icon)
        if self.tray is not None:
            self.tray.setIcon(icon)
        self._apply_style()
        _caption_color(self)
        self._reload_history(max(0, self._selected_scan()))
        self._show_list()

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001
        if getattr(self, "_closing", False):
            # Child widgets are being torn down. Touching them now raises.
            return False
        edit = getattr(self, "hotkey_edit", None)
        if edit is not None and watched is edit:
            kind = event.type()
            if kind == QEvent.Type.FocusIn:
                if not self.store.auto_capture:
                    self._begin_hotkey()
            elif kind == QEvent.Type.FocusOut:
                self._end_hotkey()
            elif kind == QEvent.Type.KeyPress and event.key() not in (Qt.Key_Tab, Qt.Key_Backtab):
                if not self.store.auto_capture:
                    self._take_hotkey(event)
                return True
        table = getattr(self, "history_table", None)
        if table is not None and watched is table.viewport() and event.type() == QEvent.Type.Leave:
            self._clear_history_hover()
        history = getattr(self, "history_list", None)
        if history is not None and watched is history.viewport():
            if event.type() == QEvent.Type.Leave:
                self._hover_day_folder(-1)
            elif event.type() == QEvent.Type.MouseMove:
                self._hover_day_folder(history.indexAt(event.position().toPoint()).row())
        names = getattr(self, "blacklist_table", None)
        if names is not None and watched is names.viewport():
            if event.type() == QEvent.Type.Leave:
                self._clear_blacklist_hover()
                self._schedule_detail_tip_hide()
            elif event.type() == QEvent.Type.MouseMove:
                index = names.indexAt(event.position().toPoint())
                if index.isValid():
                    self._sync_detail_tip(index.row(), index.column())
            elif event.type() == QEvent.Type.Resize:
                self._fit_blacklist_columns()
        tip = getattr(self, "detail_tip", None)
        if tip is not None and watched is tip:
            if event.type() == QEvent.Type.Enter:
                self._detail_tip_timer.stop()
            elif event.type() == QEvent.Type.Leave:
                self._schedule_detail_tip_hide()
        if watched.property("scanRow") is not None:
            button = watched.findChild(QPushButton, "rowDelete")
            kind = event.type()
            if button is not None and kind == QEvent.Type.Enter:
                button.show()
            elif button is not None and kind == QEvent.Type.Leave:
                button.hide()
            elif kind == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
                scan = int(watched.property("scanRow"))
                for row in range(self.history_list.count()):
                    item = self.history_list.item(row)
                    if item.data(Qt.UserRole) == scan and not item.isHidden():
                        self.history_list.setCurrentRow(row)
                        break
        return super().eventFilter(watched, event)

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        _caption_color(self)
        self._remember_size()

    def _tag_cell(self, tags: tuple[str, ...] | list[str]) -> QWidget:
        return _TagRow(tags)

    def _list_cell(self, text: str, store_index: int | None = None) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setFont(chinese_font(BODY_PT))
        item.setForeground(QColor(THEME["text"]))
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        if store_index is not None:
            item.setData(Qt.UserRole, store_index)
        return item

    def _sort_stamp(self, entry: Entry, column: int) -> float | None:
        if column != 3:
            return None
        for scan in self.store.scans:
            for seat in scan.get("names", []):
                if seat.get("unclear") or not str(seat.get("name") or ""):
                    continue
                shown = str(seat["name"])
                if match_label(NameLabel(raw=shown, visible=shown, truncated=False), [entry]):
                    moment = _local_moment(str(scan.get("at", "")))
                    return None if moment is None else moment.timestamp()
        return None

    def _search_text(self) -> str:
        search = getattr(self, "list_search", None)
        return search.text().strip() if search is not None else ""

    def _ordered_entries(self) -> list[tuple[int, Entry]]:
        rows = list(enumerate(self.store.entries))
        query = self._search_text()
        if query:
            folded = fold(query)
            lowered = query.casefold()

            def hit(entry: Entry) -> bool:
                if folded and folded in fold(entry.name):
                    return True
                if any(lowered in tag.casefold() for tag in entry.tags):
                    return True
                return lowered in entry.reason.casefold()

            rows = [pair for pair in rows if hit(pair[1])]
        if self._blacklist_sort is None:
            return rows
        column, newest = self._blacklist_sort

        def key(pair: tuple[int, Entry]) -> tuple[bool, float, int]:
            index, entry = pair
            stamp = self._sort_stamp(entry, column)
            if stamp is None:
                return (True, 0.0, index)
            return (False, -stamp if newest else stamp, index)

        return sorted(rows, key=key)

    def _column_labels(self) -> list[str]:
        header = self.blacklist_table.horizontalHeader()
        return [
            self.blacklist_table.horizontalHeaderItem(header.logicalIndex(visual)).text()
            for visual in range(header.count())
        ]

    def _apply_column_widths(self) -> None:
        header = self.blacklist_table.horizontalHeader()
        widths = self.store.column_widths
        if len(widths) != header.count():
            return
        header.blockSignals(True)
        for logical, width in enumerate(widths):
            self.blacklist_table.setColumnWidth(logical, width)
        header.blockSignals(False)
        self._fit_blacklist_columns()

    def _fit_blacklist_columns(self, prefer: int | None = None) -> None:
        """Keep every column inside the list. Extra width comes out of the last column."""
        table = getattr(self, "blacklist_table", None)
        if table is None or getattr(self, "_fitting_columns", False):
            return
        header = table.horizontalHeader()
        available = table.viewport().width()
        count = header.count()
        minimum = header.minimumSectionSize()
        if count == 0 or available < minimum:
            return
        logicals = [header.logicalIndex(visual) for visual in range(count)]
        if prefer is None:
            saved = self.store.column_widths
            if len(saved) != count:
                saved = [header.sectionSize(index) for index in range(count)]
            sizes = [max(minimum, saved[logical]) for logical in logicals]
        else:
            sizes = [max(minimum, header.sectionSize(logical)) for logical in logicals]
        others = sizes[:-1]
        overflow = sum(others) + minimum - available
        if overflow > 0 and prefer is not None and prefer in logicals[:-1]:
            index = logicals.index(prefer)
            spare = others[index] - minimum
            cut = min(max(spare, 0), overflow)
            others[index] -= cut
            overflow -= cut
        if overflow > 0:
            for index in range(len(others) - 1, -1, -1):
                spare = others[index] - minimum
                if spare <= 0:
                    continue
                cut = min(spare, overflow)
                others[index] -= cut
                overflow -= cut
                if overflow <= 0:
                    break
        room = available - sum(others)
        if room < minimum:
            room = minimum
        target = [*others, max(minimum, room)]
        self._fitting_columns = True
        header.blockSignals(True)
        try:
            for logical, size in zip(logicals, target, strict=True):
                if header.sectionSize(logical) != size:
                    table.setColumnWidth(logical, size)
                visual = header.visualIndex(logical)
                if (
                    prefer is not None
                    and visual != count - 1
                    and 0 <= logical < len(self.store.column_widths)
                ):
                    self.store.column_widths[logical] = size
        finally:
            header.blockSignals(False)
            self._fitting_columns = False

    def _save_column_width(self, logical: int, _old: int, new: int) -> None:
        header = self.blacklist_table.horizontalHeader()
        if getattr(self, "_fitting_columns", False):
            return
        if header.visualIndex(logical) == header.count() - 1:
            return
        if not 0 <= logical < len(self.store.column_widths) or self.store.column_widths[logical] == new:
            return
        self.store.column_widths[logical] = new
        self._fit_blacklist_columns(prefer=logical)
        self.store.save_settings()

    def _apply_column_order(self) -> None:
        header = self.blacklist_table.horizontalHeader()
        order = self.store.column_order
        if sorted(order) != list(range(header.count())):
            return
        header.blockSignals(True)
        for visual, logical in enumerate(order):
            current = header.visualIndex(logical)
            if current != visual:
                header.moveSection(current, visual)
        header.blockSignals(False)
        self._fit_blacklist_columns()

    def _save_column_order(self, _logical: int = 0, _old: int = 0, _new: int = 0) -> None:
        header = self.blacklist_table.horizontalHeader()
        order = [header.logicalIndex(visual) for visual in range(header.count())]
        if order == self.store.column_order:
            return
        self.store.column_order = order
        self.store.save_settings()
        self._fit_blacklist_columns()

    def _sort_blacklist(self, column: int) -> None:
        if column != 3:
            return
        newest = self._blacklist_sort != (column, True)
        self._blacklist_sort = (column, newest)
        header = self.blacklist_table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(column, Qt.DescendingOrder if newest else Qt.AscendingOrder)
        self._show_list()

    def _last_met_all(self) -> dict[int, str]:
        """When each listed name was last seen, from one pass over the records (newest first)."""
        found: dict[int, str] = {}
        by_id = {id(entry): index for index, entry in enumerate(self.store.entries)}
        for scan in self.store.scans:
            for seat in scan.get("names", []):
                if seat.get("unclear") or not str(seat.get("name") or ""):
                    continue
                shown = str(seat["name"])
                for match in match_label(NameLabel(raw=shown, visible=shown, truncated=False), self.store.entries):
                    index = by_id.get(id(match.entry))
                    if index is not None and index not in found:
                        found[index] = _zh_ago(str(scan.get("at", "")))
            if len(found) == len(self.store.entries):
                break
        return found

    def _show_list(self) -> None:
        rows = self._ordered_entries()
        met = self._last_met_all()
        bar = self.blacklist_table.verticalScrollBar()
        position = bar.value()
        self.blacklist_table.setRowCount(len(rows))
        for row, (index, entry) in enumerate(rows):
            shown = masked_name(entry.name) if self.store.names_hidden else entry.name
            self.blacklist_table.setItem(row, 0, self._list_cell(shown, index))
            tags_item = self._list_cell(tag_text(entry))
            tags_item.setToolTip(tag_text(entry))
            self.blacklist_table.setItem(row, 1, tags_item)
            self.blacklist_table.setCellWidget(row, 1, self._tag_cell(entry.tags))
            detail = " ".join(entry.reason.split())
            self.blacklist_table.setItem(row, 2, self._list_cell(detail))
            self.blacklist_table.setItem(row, 3, self._list_cell(met.get(index, "")))
            self.blacklist_table.setRowHeight(row, ROW_H)
        self._blacklist_hover = -1
        self.blacklist_table.setCurrentCell(-1, -1)
        bar.setValue(position)
        self._hide_detail_tip()
        self._refresh_blacklist_tab()
        count = len(self.store.entries)
        self.list_search.setVisible(count > 0 or bool(self._search_text()))
        self.more_button.setVisible(count > 0)
        if count and rows:
            self.list_empty.hide()
            self.blacklist_table.setVisible(True)
        elif count:
            self.list_empty.set_icon("search")
            self.list_empty.set_text(f"没有找到「{self._search_text()}」")
            self.list_empty.show()
            self.blacklist_table.setVisible(False)
        else:
            self.list_empty.set_icon("users")
            self.list_empty.set_text("还没有名字")
            self.list_empty.show()
            self.blacklist_table.setVisible(False)

    def _reason_for_row(self, row: int) -> str:
        item = self.blacklist_table.item(row, 0)
        if item is None or item.data(Qt.UserRole) is None:
            return ""
        index = int(item.data(Qt.UserRole))
        if not 0 <= index < len(self.store.entries):
            return ""
        return self.store.entries[index].reason

    def _toggle_name_hiding(self, hidden: bool) -> None:
        self.store.names_hidden = bool(hidden)
        header = self.blacklist_table.horizontalHeader()
        if isinstance(header, _ColumnHeader):
            header.names_hidden = self.store.names_hidden
            header.viewport().update()
        self.store.save_settings()
        self._show_list()

    def _sync_detail_tip(self, row: int, column: int) -> None:
        text = self._reason_for_row(row) if column == 2 else ""
        if not text.strip():
            self._hide_detail_tip()
            return
        self._detail_tip_timer.stop()
        rect = self.blacklist_table.visualRect(self.blacklist_table.model().index(row, 2))
        anchor = self.blacklist_table.viewport().mapToGlobal(rect.bottomLeft())
        self.detail_tip.show_reason(text, anchor)

    def _schedule_detail_tip_hide(self) -> None:
        tip = getattr(self, "detail_tip", None)
        if tip is None or not tip.isVisible():
            return
        if tip.geometry().contains(QCursor.pos()):
            self._detail_tip_timer.stop()
            return
        self._detail_tip_timer.start()

    def _hide_detail_tip(self) -> None:
        tip = getattr(self, "detail_tip", None)
        if tip is None:
            return
        self._detail_tip_timer.stop()
        tip.hide()

    def _hover_blacklist_row(self, row: int, column: int = 0) -> None:
        if row >= 0:
            self._sync_detail_tip(row, column)
        if row < 0:
            return
        if row == self._blacklist_hover:
            return
        bar = self.blacklist_table.verticalScrollBar()
        position = bar.value()
        self._blacklist_hover = row
        self.blacklist_table.selectRow(row)
        bar.setValue(position)

    def _clear_blacklist_hover(self) -> None:
        bar = self.blacklist_table.verticalScrollBar()
        position = bar.value()
        self._blacklist_hover = -1
        self.blacklist_table.clearSelection()
        self.blacklist_table.setCurrentCell(-1, -1)
        bar.setValue(position)

    def _set_tab_count(self, index: int, count: int) -> None:
        if not 0 <= index < len(self._tab_buttons):
            return
        button = self._tab_buttons[index]
        button.set_count(count)
        self.tabs.setTabText(index, f"{button.name()}  {count}" if count else button.name())

    def _sync_tab_buttons(self, index: int) -> None:
        for button_index, button in enumerate(self._tab_buttons):
            button.setChecked(button_index == index)

    def _refresh_blacklist_tab(self) -> None:
        count = len(self.store.entries)
        self._set_tab_count(self.blacklist_tab, count)

    def _open_more_menu(self) -> None:
        button = self.more_button
        self.more_menu.popup(button.mapToGlobal(button.rect().bottomRight()) - QPoint(self.more_menu.sizeHint().width(), -4))

    def _clear_list(self) -> None:
        count = len(self.store.entries)
        if not count:
            return
        if ConfirmDialog.ask(self, "清空列表", f"名单里的 {count} 个名字会被删除。", "确认清空", danger=True):
            self._confirm_clear_list()

    def _confirm_clear_list(self) -> None:
        before = self.store.snapshot_entries()
        self.store.clear_entries()
        self._list_changed()
        self._say(f"已清空 {len(before)} 人", undo=lambda: self._put_back(before))

    def _list_changed(self) -> None:
        self._show_list()
        self._show_history_scan(self._selected_scan())

    def _put_back(self, entries: list[Entry]) -> None:
        self.store.restore_entries(entries)
        self._refresh_tag_views()
        self._say("已撤销")

    def _say(self, text: str, undo=None) -> None:  # noqa: ANN001
        """Report a change in a toast. 撤销 stays for eight seconds."""
        if undo is None:
            self.toast.show_message(text, ms=4000)
        else:
            self.toast.show_message(text, "撤销", undo, ms=8000)

    def _on_search_text(self, _text: str) -> None:
        self._show_list()

    def _blacklist_menu(self, pos) -> None:  # noqa: ANN001
        row = self.blacklist_table.rowAt(pos.y())
        item = self.blacklist_table.item(row, 0) if row >= 0 else None
        if item is None or item.data(Qt.UserRole) is None:
            return
        index = int(item.data(Qt.UserRole))
        menu = self._row_menu(index)
        menu.popup(self.blacklist_table.viewport().mapToGlobal(pos))

    def _row_menu(self, index: int) -> QMenu:
        return self._menu((("修改", ("edit", index)), ("复制名字", ("copy_entry", index)), None, ("删除", ("delete", index))))

    def _menu(self, items) -> QMenu:  # noqa: ANN001
        menu = QMenu(self)
        for item in items:
            if item is None:
                menu.addSeparator()
                continue
            text, data = item
            menu.addAction(text).setData(data)
        menu.triggered.connect(self._on_menu_action)
        menu.aboutToHide.connect(menu.deleteLater)
        return menu

    def _on_menu_action(self, action) -> None:  # noqa: ANN001
        data = action.data()
        if not isinstance(data, tuple) or not data:
            return
        kind, *args = data
        if kind == "edit":
            self._edit_entry(*args)
        elif kind == "copy_entry":
            self._copy_name(*args)
        elif kind == "delete":
            self._delete_entry(*args)
        elif kind == "seat":
            self._on_history_cell(*args)
        elif kind == "copy_text":
            self._copy_text(*args)

    def _copy_name(self, index: int) -> None:
        if 0 <= index < len(self.store.entries):
            self._copy_text(self.store.entries[index].name)

    def _delete_entry(self, index: int) -> None:
        if not 0 <= index < len(self.store.entries):
            return
        name = self.store.entries[index].name
        before = self.store.snapshot_entries()
        self.store.remove_at(index)
        self._list_changed()
        self._say(f"已删除「{name}」", undo=lambda: self._put_back(before))

    def _share_list(self) -> None:
        """Copy the whole list in the 批量添加 line format, so a friend can paste it."""
        from blacklist_detect.storage import share_text

        count = len(self.store.entries)
        if not count:
            return
        QApplication.clipboard().setText(share_text(self.store.entries))
        self._say(f"已复制 {count} 人。朋友在「批量添加」里粘贴即可。")

    def _add_by_dialog(self) -> None:
        dialog = AddNameDialog(catalog=self.store.tag_catalog(), parent=self, taken=self._taken_names())
        if dialog.exec() != QDialog.Accepted or dialog.deleted:
            return
        before = self.store.snapshot_entries()
        entry = self.store.add(dialog.name, dialog.detail, tags=dialog.tags)
        if entry is None:
            return
        self._list_changed()
        self._say(f"已添加「{entry.name}」", undo=lambda: self._put_back(before))

    def _add_many_by_dialog(self) -> None:
        dialog = BatchAddDialog(self.store.tag_catalog(), parent=self)
        if dialog.exec() != QDialog.Accepted or not dialog.names:
            return
        before = self.store.snapshot_entries()
        if dialog.annotated is None:
            added = self.store.add_names(dialog.names)
        else:
            added = self.store.add_annotated(dialog.annotated)
        skipped = len(dialog.names) - added
        if added == 0:
            self._say(f"这 {skipped} 个名字都已经在名单里")
            return
        # A shared list may bring tags this list has not seen. They now show in 设置.
        self._refresh_tag_views()
        text = f"已添加 {added} 人"
        if skipped:
            text += f"，{skipped} 个已在名单里没有重复添加"
        self._say(text, undo=lambda: self._put_back(before))

    def _taken_names(self, skip: int = -1) -> frozenset[str]:
        return frozenset(fold(entry.name) for index, entry in enumerate(self.store.entries) if index != skip)

    def _edit_row(self, row: int, _column: int = 0) -> None:
        item = self.blacklist_table.item(row, 0)
        if item is None or item.data(Qt.UserRole) is None:
            return
        self._edit_entry(int(item.data(Qt.UserRole)))

    def _edit_entry(self, index: int) -> None:
        if not 0 <= index < len(self.store.entries):
            return
        entry = self.store.entries[index]
        dialog = AddNameDialog(
            entry.name,
            entry.tags,
            entry.reason,
            title="修改",
            allow_delete=True,
            catalog=self.store.tag_catalog(),
            added_at=entry.added_at,
            parent=self,
            taken=self._taken_names(skip=index),
        )
        if dialog.exec() != QDialog.Accepted:
            return
        if dialog.deleted:
            self._delete_entry(index)
            return
        self.store.update_at(index, dialog.name, dialog.tags, dialog.detail)
        self._list_changed()

    def _reload_history(self, select: int = 0) -> None:
        self.history_list.blockSignals(True)
        self.history_list.clear()
        folders: list[tuple[str, list[tuple[int, str]]]] = []
        seen: dict[str, int] = {}
        for index, scan in enumerate(self.store.scans):
            day, clock = self._day_and_clock(str(scan.get("at", "")))
            key = day or clock
            if key not in seen:
                seen[key] = len(folders)
                folders.append((key, []))
            folders[seen[key]][1].append((index, clock))
        count = len(self.store.scans)
        for key, rows in folders:
            closed = key in self._closed_days
            self._add_day_folder(key, closed)
            for index, clock in rows:
                self._add_history_time(key, index, clock, closed)
        self.history_side.setVisible(count > 0)
        self.history_list.setVisible(count > 0)
        self.record_card.setVisible(count > 0)
        self.history_table.setVisible(count > 0)
        self.history_empty.setVisible(count == 0)
        self.clear_history_button.setVisible(count > 0)
        self._set_tab_count(self.history_tab, count)
        chosen = -1
        if count:
            chosen = max(0, min(select, count - 1))
            for list_row in range(self.history_list.count()):
                if self.history_list.item(list_row).data(Qt.UserRole) == chosen:
                    self.history_list.setCurrentRow(list_row)
                    break
        self.history_list.blockSignals(False)
        self._mark_selected_record()
        self._show_history_scan(chosen)
        self._show_list()

    def _add_day_folder(self, day: str, closed: bool) -> None:
        item = QListWidgetItem("")
        item.setData(Qt.UserRole, -1)
        item.setData(Qt.UserRole + 1, "day")
        item.setData(Qt.UserRole + 2, day)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item.setSizeHint(QSize(0, 30))
        wrap = QWidget()
        wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        wrap.setStyleSheet("background: transparent;")
        line = QHBoxLayout(wrap)
        line.setContentsMargins(0, 0, 8, 0)
        line.setSpacing(8)
        line.addWidget(DayFolderIcon(opened=not closed), 0, Qt.AlignVCenter)
        label = QLabel(day)
        label.setObjectName("dayFolder")
        label.setFont(record_font())
        label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        label.setStyleSheet(
            f'color: {THEME["text"]}; background: transparent; font-family: "{chinese_family()}"; font-size: {BODY_PT}pt; font-weight: 400;'
        )
        line.addWidget(label)
        self.history_list.addItem(item)
        self.history_list.setItemWidget(item, wrap)

    def _add_history_time(self, day: str, index: int, text: str, closed: bool) -> None:
        item = QListWidgetItem("")
        item.setData(Qt.UserRole, index)
        item.setData(Qt.UserRole + 1, "time")
        item.setData(Qt.UserRole + 2, day)
        item.setFont(record_font())
        item.setSizeHint(QSize(0, 30))
        self.history_list.addItem(item)
        item.setHidden(closed)
        wrap = QWidget()
        wrap.setProperty("scanRow", index)
        wrap.setStyleSheet("background: transparent;")
        wrap.installEventFilter(self)
        line = QHBoxLayout(wrap)
        line.setContentsMargins(24, 0, 4, 0)
        line.setSpacing(0)
        clock = QLabel(text)
        clock.setObjectName("recordTime")
        clock.setFont(record_font())
        clock.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        clock.setStyleSheet(
            f'color: {THEME["text"]}; background: transparent; font-family: "{chinese_family()}"; font-size: {BODY_PT}pt; font-weight: 400;'
        )
        line.addWidget(clock, 0, Qt.AlignVCenter)
        line.addStretch(1)
        remove = QPushButton("×")
        remove.setObjectName("rowDelete")
        remove.setFixedSize(22, 22)
        mark = chinese_font(BODY_PT)
        remove.setFont(mark)
        remove.setCursor(Qt.PointingHandCursor)
        remove.setFocusPolicy(Qt.NoFocus)
        remove.hide()
        remove.clicked.connect(lambda _checked=False, scan=index: self._delete_scan(scan))
        line.addWidget(remove, 0, Qt.AlignVCenter)
        self.history_list.setItemWidget(item, wrap)

    def _on_history_clicked(self, item: QListWidgetItem) -> None:
        if item.data(Qt.UserRole + 1) != "day":
            return
        day = str(item.data(Qt.UserRole + 2) or "")
        if day in self._closed_days:
            self._closed_days.discard(day)
        else:
            self._closed_days.add(day)
        self._sync_day_folders()

    def _sync_day_folders(self) -> None:
        self.history_list.blockSignals(True)
        selected = self._selected_scan()
        for row in range(self.history_list.count()):
            item = self.history_list.item(row)
            day = str(item.data(Qt.UserRole + 2) or "")
            closed = day in self._closed_days
            kind = item.data(Qt.UserRole + 1)
            if kind == "day":
                wrap = self.history_list.itemWidget(item)
                mark = wrap.findChild(DayFolderIcon, "dayMark") if wrap is not None else None
                if mark is not None:
                    mark.set_open(not closed)
            else:
                item.setHidden(closed)
        if selected >= 0:
            for row in range(self.history_list.count()):
                item = self.history_list.item(row)
                if item.data(Qt.UserRole) == selected and not item.isHidden():
                    self.history_list.setCurrentRow(row)
                    break
        self.history_list.blockSignals(False)

    def _hover_day_folder(self, row: int) -> None:
        if self._day_hover == row:
            return
        self._day_hover = row
        for index in range(self.history_list.count()):
            item = self.history_list.item(index)
            if item.data(Qt.UserRole + 1) != "day":
                continue
            wrap = self.history_list.itemWidget(item)
            mark = wrap.findChild(DayFolderIcon, "dayMark") if wrap is not None else None
            if mark is not None:
                mark.set_hovered(index == row)

    def _on_history_picked(self, list_row: int) -> None:
        index = self._scan_at(list_row)
        if index < 0:
            return
        self._show_history_scan(index)

    def _selected_scan(self) -> int:
        return self._scan_at(self.history_list.currentRow())

    def _scan_at(self, list_row: int) -> int:
        if list_row < 0:
            return -1
        item = self.history_list.item(list_row)
        if item is None:
            return -1
        value = item.data(Qt.UserRole)
        try:
            index = int(value)
        except (TypeError, ValueError):
            return -1
        if index < 0:
            return -1
        return index

    def _delete_scan(self, index: int) -> None:
        self.store.remove_scan(index)
        self._reload_history(index)

    def _delete_history(self) -> None:
        self._delete_scan(self._selected_scan())

    def _ask_clear_history(self) -> None:
        count = len(self.store.scans)
        if count and ConfirmDialog.ask(self, "清空记录", f"{count} 条记录会被删除。", "确认清空", danger=True):
            self._clear_history()

    def _clear_history(self) -> None:
        self.store.clear_scans()
        self._reload_history()

    def _day_and_clock(self, stamp: str) -> tuple[str, str]:
        try:
            moment = datetime.fromisoformat(stamp)
        except ValueError:
            return "", stamp
        return f"{moment.month}月{moment.day}日", _zh_clock(moment)

    def _show_history_scan(self, row: int) -> None:
        self._history_hover = (-1, -1)
        self._mark_selected_record()
        self.history_table.setRowCount(0)
        if row < 0 or row >= len(self.store.scans):
            self.record_time.setText("")
            return
        day, clock = self._day_and_clock(str(self.store.scans[row].get("at", "")))
        self.record_time.setText(f"{day} {clock}".strip())
        names = self.store.scans[row].get("names", [])
        self.history_table.setRowCount((len(names) + 1) // 2)
        for index, seat in enumerate(names):
            self._set_history_seat(index // 2, index % 2, seat)
            self.history_table.setRowHeight(index // 2, ROW_H + 4)

    def _mark_selected_record(self) -> None:
        for row in range(self.history_list.count()):
            item = self.history_list.item(row)
            if item.data(Qt.UserRole + 1) != "time":
                continue
            item.setFont(record_font())

    def _history_match(self, shown: str):
        label = NameLabel(raw=shown, visible=shown, truncated=False)
        found = match_label(label, list(self.store.entries))
        return found[0] if found else None

    def _set_history_seat(self, row: int, column: int, seat: dict) -> None:
        unclear = bool(seat.get("unclear")) or not str(seat.get("name") or "")
        shown = "未看清" if unclear else str(seat.get("name"))
        visible = "未知" if unclear else shown
        match = None if unclear else self._history_match(shown)
        stored = match.entry.name if match is not None else ""
        mine = not unclear and match is None and self._is_my_name(shown)
        if mine:
            action = "你"
        elif unclear or match is not None:
            action = ""
        else:
            action = "添加"
        # The name as read off the screen. A match shows the list's spelling beside it,
        # so a cut-off or near name that matched can be told apart from an exact one.
        title = shown
        if not unclear:
            title = split_ellipsis(title)[0] or title
        listed = stored if match is not None and fold(stored) != fold(title) else ""
        # Lobby order is not the player's number. Show the name until a later stage.
        label = title
        name_item = QTableWidgetItem(label)
        name_item.setData(Qt.UserRole, "" if unclear else title)
        name_item.setData(Qt.UserRole + 1, action)
        name_item.setData(Qt.UserRole + 2, stored)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        name_font = record_font()
        name_item.setFont(name_font)
        if unclear:
            tone = THEME["gray"]
            wash = ""
            hover = ""
        elif match is not None:
            tone = THEME["red"]
            wash = THEME["red_wash"]
            hover = THEME["red_hover"]
        elif self._is_my_name(shown):
            tone = THEME["green"]
            wash = THEME["green_wash"]
            hover = ""
        else:
            tone = THEME["text"]
            wash = ""
            hover = THEME["hover"]
        name_item.setForeground(QColor(tone))
        self.history_table.setItem(row, column, name_item)
        wrap = QWidget()
        wrap.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        wrap.setProperty("toneWash", wash)
        wrap.setProperty("toneHover", hover)
        wrap.setStyleSheet(self._history_wrap_style(wash))
        inset = QHBoxLayout(wrap)
        inset.setContentsMargins(6, 3, 6, 3)
        tile = QFrame()
        tile.setObjectName("seat")
        tile.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        inset.addWidget(tile)
        line = QHBoxLayout(tile)
        line.setContentsMargins(12, 0, 12, 0)
        line.setSpacing(8)
        if match is not None:
            # Red is not the only sign of a hit: the warning mark says it too.
            warn = QLabel()
            warn.setObjectName("seatWarn")
            warn.setPixmap(line_pixmap("warning", 16, THEME["red"]))
            warn.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            warn.setStyleSheet("background: transparent;")
            line.addWidget(warn)
        name_label = QLabel(visible if unclear else label)
        name_label.setFont(name_font)
        name_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        name_color = tone
        if unclear:
            missed = record_font()
            missed.setItalic(True)
            name_label.setFont(missed)
        name_label.setStyleSheet(
            f'color: {name_color}; background: transparent; font-family: "{chinese_family()}"; font-size: {BODY_PT}pt;'
            + (" font-style: italic;" if unclear else "")
        )
        line.addWidget(name_label)
        line.addStretch(1)
        if listed:
            listed_label = QLabel(f"名单：{listed}")
            listed_label.setObjectName("rowListed")
            listed_label.setFont(chinese_font(SMALL_PT))
            listed_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            listed_label.setStyleSheet(
                f'color: {THEME["red"]}; background: transparent; font-family: "{chinese_family()}";'
            )
            name_item.setToolTip(f"画面是「{title}」，黑名单里是「{listed}」")
            line.addWidget(listed_label, 0, Qt.AlignVCenter)
        if action:
            action_label = QLabel(action)
            action_label.setObjectName("rowAction")
            action_label.setFont(chinese_font())
            action_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            action_label.setFont(chinese_font(SMALL_PT))
            if action == "你":
                action_label.setStyleSheet(
                    f'color: {THEME["chip_text"]}; background: {THEME["chip_bg"]}; border: 1px solid {THEME["chip_bg"]}; border-radius: 9px;'
                    f' padding: 1px 8px; font-family: "{chinese_family()}"; font-size: {SMALL_PT}pt;'
                )
            else:
                accent = THEME["accent_line"] if is_dark() else THEME["accent"]
                action_label.setStyleSheet(
                    f'color: {accent}; background: {THEME["surface"]}; border: 1px solid {THEME["accent_line"]};'
                    f' border-radius: 6px; padding: 1px 10px; font-family: "{chinese_family()}"; font-size: {SMALL_PT}pt;'
                )
            if action == "添加":
                action_label.hide()
            line.addWidget(action_label, 0, Qt.AlignVCenter)
        self.history_table.setCellWidget(row, column, wrap)

    def _history_wrap_style(self, wash: str = "") -> str:
        return f"QFrame#seat {{ background: {wash or THEME['surface']}; border-radius: 6px; }}"

    def _history_cell_is_mine(self, row: int, column: int) -> bool:
        item = self.history_table.item(row, column)
        return item is not None and str(item.data(Qt.UserRole + 1) or "") == "你"

    def _history_cell_is_unclear(self, row: int, column: int) -> bool:
        item = self.history_table.item(row, column)
        return item is not None and item.text() == "未看清"

    def _hover_history_cell(self, row: int, column: int) -> None:
        if self._history_cell_is_mine(row, column) or self._history_cell_is_unclear(row, column):
            self._clear_history_hover()
            self.history_table.viewport().setCursor(Qt.ArrowCursor)
            return
        self.history_table.viewport().setCursor(Qt.PointingHandCursor)
        if self._history_hover == (row, column):
            return
        self._paint_history_hover(*self._history_hover, False)
        self._history_hover = (row, column)
        self._paint_history_hover(row, column, True)

    def _clear_history_hover(self) -> None:
        self._paint_history_hover(*self._history_hover, False)
        self._history_hover = (-1, -1)

    def _paint_history_hover(self, row: int, column: int, hot: bool) -> None:
        if row < 0 or column < 0:
            return
        item = self.history_table.item(row, column)
        wrap = self.history_table.cellWidget(row, column)
        if item is None or wrap is None:
            return
        if hot and str(item.data(Qt.UserRole + 1) or "") == "你":
            hot = False
        hover = str(wrap.property("toneHover") or "")
        wash = hover if hot and hover else str(wrap.property("toneWash") or "")
        wrap.setStyleSheet(self._history_wrap_style(wash))
        action_label = wrap.findChild(QLabel, "rowAction")
        if action_label is not None and action_label.text() == "添加":
            action_label.setVisible(hot)

    def _history_menu(self, pos) -> None:  # noqa: ANN001
        index = self.history_table.indexAt(pos)
        menu = self._seat_menu(index.row(), index.column()) if index.isValid() else None
        if menu is not None:
            menu.popup(self.history_table.viewport().mapToGlobal(pos))

    def _seat_menu(self, row: int, column: int) -> QMenu | None:
        item = self.history_table.item(row, column)
        shown = str(item.data(Qt.UserRole) or "") if item is not None else ""
        if not shown:
            return None
        action = str(item.data(Qt.UserRole + 1) or "")
        items = []
        if item.data(Qt.UserRole + 2):
            items.append(("修改", ("seat", row, column)))
        elif action == "添加":
            items.append(("添加", ("seat", row, column)))
        items.append(("复制名字", ("copy_text", shown)))
        return self._menu(items)

    def _copy_text(self, text: str) -> None:
        QApplication.clipboard().setText(text)
        self._say(f"已复制「{text}」")

    def _on_history_cell(self, row: int, column: int) -> None:
        item = self.history_table.item(row, column)
        if item is None:
            return
        shown = str(item.data(Qt.UserRole) or "")
        shown = split_ellipsis(shown)[0] or shown
        if not shown or str(item.data(Qt.UserRole + 1) or "") == "你":
            return
        stored = str(item.data(Qt.UserRole + 2) or "")
        if stored:
            for index, entry in enumerate(self.store.entries):
                if entry.name == stored:
                    self._edit_entry(index)
                    return
            return
        dialog = AddNameDialog(shown, title="添加", catalog=self.store.tag_catalog(), parent=self, taken=self._taken_names())
        if dialog.exec() != QDialog.Accepted or dialog.deleted:
            return
        if self.store.add(dialog.name, dialog.detail, tags=dialog.tags) is None:
            return
        self._show_list()
        self._show_history_scan(self._selected_scan())

    def _toggle_auto(self, checked: bool) -> None:
        self.store.auto_capture = bool(checked)
        self.store.save_settings()
        self._sync_auto_controls()
        if self.store.auto_capture:
            self.watch = LobbyWatch()
            self._watch_timer.start()
        else:
            if not self.panel.isVisible():
                self._watch_timer.stop()
        self._sync_hotkey_mode()
        if self._status_kind in ("idle", "watch"):
            self._sync_watch_idle()

    def _on_auto_mode(self, key: str) -> None:
        self._toggle_auto(key == "auto")

    def _sync_auto_controls(self) -> None:
        """The header switch and the 方式 choice both show the saved mode."""
        auto = self.store.auto_capture
        self.auto_mode.set_current("auto" if auto else "manual")
        if self.auto_switch.isChecked() != auto:
            self.auto_switch.blockSignals(True)
            self.auto_switch.setChecked(auto)
            self.auto_switch.blockSignals(False)

    def _begin_hotkey(self) -> None:
        self._set_settings_note("")
        self.hotkey.clear()
        self.hotkey_edit.clear()
        self.hotkey_edit.setPlaceholderText("按下热键")

    def _end_hotkey(self) -> None:
        self.hotkey_edit.setPlaceholderText("无")
        self._show_hotkey()
        self._sync_hotkey_mode()

    def _sync_hotkey_mode(self) -> None:
        """Auto check and the hotkey do not run together."""
        manual = not self.store.auto_capture
        self.hotkey_edit.setEnabled(manual)
        self.hotkey_edit.setCursor(Qt.PointingHandCursor if manual else Qt.ArrowCursor)
        if not manual:
            self.hotkey.clear()
            return
        spec = parse_hotkey(self.store.hotkey)
        if spec is not None and self.hotkey.active != spec.display:
            self.hotkey.apply(spec)

    def _take_hotkey(self, event) -> None:
        if event.isAutoRepeat():
            return
        if event.key() == Qt.Key_Escape:
            self.hotkey_edit.clearFocus()
            return
        if event.key() in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta):
            return
        key = _qt_key_name(event.key())
        if key is None:
            self._set_settings_note("请按字母、数字，或 F1 到 F12。")
            return
        modifiers = []
        flags = event.modifiers()
        if flags & Qt.ControlModifier:
            modifiers.append("Ctrl")
        if flags & Qt.AltModifier:
            modifiers.append("Alt")
        if flags & Qt.ShiftModifier:
            modifiers.append("Shift")
        if flags & Qt.MetaModifier:
            modifiers.append("Win")
        spec = parse_hotkey("+".join([*modifiers, key]))
        if spec is None:
            self._set_settings_note("这个组合不能用。")
            return
        registered = self.hotkey.apply(spec)
        self.store.hotkey = spec.display
        self.store.save_settings()
        self.hotkey_edit.setText(spec.display)
        if registered:
            self._set_settings_note("")
        elif sys.platform != "win32":
            self._set_settings_note("这台电脑不能用热键。")
        else:
            self.store.hotkey = ""
            self.store.save_settings()
            self.hotkey_edit.clear()
            self._set_settings_note("换一个热键。")
        self.hotkey_edit.clearFocus()
        if self._status_kind == "idle":
            self._sync_watch_idle()

    def _show_hotkey(self) -> None:
        spec = parse_hotkey(self.store.hotkey)
        if spec is None:
            self.hotkey_edit.clear()
            return
        self.hotkey_edit.setText(spec.display)

    def _restore_hotkey(self) -> None:
        self._show_hotkey()
        self._sync_hotkey_mode()

    def check_now(self) -> None:
        self._release_foreground = True
        self._rescan_active = False
        lock_foreground(True)
        if self._start(self._capture_job, live=True):
            self._manual_check = True
        elif self._status_kind == "loading":
            self._notify("识别模型还在加载", "请过几秒再按一次快捷键。")

    def start_warmup(self) -> None:
        """Load the OCR models now, so the first lobby check does not wait for them."""
        if not self.worker.request(get_engine().warmup, kind="warmup"):
            return
        self._warm_started = time.perf_counter()
        self._set_result("正在加载识别模型", "idle", "loading")

    def show_first_run_guide(self) -> None:
        """Once per PC: the app opened with no settings file yet."""
        if not self.store.first_run:
            return
        self.store.first_run = False
        self.store.save_settings()
        guide = GuideDialog(self)
        if guide.exec() == QDialog.Accepted and guide.wants_test:
            self.test_recognition()

    def test_recognition(self) -> None:
        """Read the bundled lobby picture, so a friend can see recognition work without the game."""
        self._run_picture(str(SAMPLE_LOBBY), "识别测试")

    def check_picture(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "选择大厅截图", "", "图片 (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self._run_picture(path, "截图检查")

    def _run_picture(self, path: str, title: str, tries: int = 0) -> None:
        if self._picture_pending and tries == 0:
            return
        entries = list(self.store.entries)
        # Hold the lobby glances back so this check gets the reader next.
        self._glance_pause_until = max(self._glance_pause_until, time.perf_counter() + 2.0)
        if self.worker.request(lambda: check_image(path, entries), kind="picture"):
            self._picture_pending = title
            self._sync_picture_buttons()
            return
        if tries == 0:
            self._picture_pending = title
            self._sync_picture_buttons()
        if tries < 300:
            # The reader is busy: a glance, a lobby check, or the first model load.
            QTimer.singleShot(100, lambda: self._run_picture(path, title, tries + 1))
            return
        self._picture_pending = ""
        self._sync_picture_buttons()
        self._picture_dialog = PictureResultDialog(title, error="识别一直在忙，请稍后再试。", parent=self)
        self._picture_dialog.open()

    def _sync_picture_buttons(self) -> None:
        busy = bool(self._picture_pending)
        for button in (self.test_button, self.picture_button, self.history_test_button):
            button.setEnabled(not busy)
        self.test_button.setText("正在识别" if busy else "测试一下")

    def _on_picture(self, status: str, value) -> None:  # noqa: ANN001
        title = self._picture_pending or "截图检查"
        self._picture_pending = ""
        self._sync_picture_buttons()
        if status != "ok":
            log.warning("Picture check failed: %s", value)
            self._picture_dialog = PictureResultDialog(title, error=str(value), parent=self)
        else:
            log.info("Picture check: lobby %s, %d on the list", value.header_found, len(value.hits))
            self._picture_dialog = PictureResultDialog(title, result=value, parent=self)
        self._picture_dialog.open()

    def _set_hit_sound(self, enabled: bool) -> None:
        self.store.hit_sound = bool(enabled)
        self.store.save_settings()
        if self.sound_switch.isChecked() != self.store.hit_sound:
            self.sound_switch.blockSignals(True)
            self.sound_switch.setChecked(self.store.hit_sound)
            self.sound_switch.blockSignals(False)
        if enabled:
            _play_hit_sound()

    def report_uncaught(self, text: str) -> None:
        """Any thread may call this. The window is updated on its own thread."""
        self.uncaught.emit(text)

    def _show_uncaught(self, text: str) -> None:
        tip = f"{text}\n\n日志：{log_dir(self.store.root) / 'app.log'}"
        self._set_result("程序出错了", "hit", "error", tip=tip)

    def _report_problem(self, problem) -> None:  # noqa: ANN001
        """Say what went wrong in the header and the tray. A check that silently stops is worse than an error."""
        if isinstance(problem, OcrUnavailable):
            label = "识别模型没有就绪"
        elif isinstance(problem, CaptureUnavailable):
            label = "无法读取屏幕"
        else:
            label = "检查出错"
        detail = str(problem).strip() or label
        if detail != self._problem:
            trace = (type(problem), problem, problem.__traceback__) if isinstance(problem, BaseException) else None
            expected = isinstance(problem, (OcrUnavailable, CaptureUnavailable))
            log.warning("%s: %s", label, detail, exc_info=None if expected else trace)
        if self._status_kind != "error" or detail != self._problem:
            tip = f"{detail}\n\n日志：{log_dir(self.store.root) / 'app.log'}"
            self._set_result(label, "hit", "error", tip=tip)
        self._problem = detail
        if label not in self._told_problems:
            self._told_problems.add(label)
            self._notify(label, detail[:200])

    def _clear_problem(self) -> None:
        if not self._problem:
            return
        self._problem = ""
        log.info("Checks work again.")
        if self._status_kind == "error":
            self._sync_watch_idle()

    def _notify(self, title: str, text: str, warning: bool = True) -> None:
        """A Windows notification from the tray icon. The window is usually hidden behind the game."""
        if self.tray is None or not self.tray.isVisible():
            return
        from PySide6.QtWidgets import QSystemTrayIcon

        icon = QSystemTrayIcon.MessageIcon.Warning if warning else QSystemTrayIcon.MessageIcon.Information
        self.tray.showMessage(title, text, icon, 5000)

    def _capture_job(self) -> CheckResult:
        frames = capture_displays()
        return check_frames(frames, list(self.store.entries), on_lobby=self.worker.placed.emit)

    def _glance_job(self) -> bool:
        """Runs on the worker thread. An unchanged screen keeps the last answer without reading it again."""
        band = capture_top_band()
        signature = band_signature(band)
        if self._last_glance is not None and same_band(self._last_band, signature):
            return self._last_glance
        found = glance_title(band)
        self._last_band = signature
        self._last_glance = found
        return found

    def _auto_tick(self) -> None:
        if self._closing:
            return
        if not self.store.auto_capture and not self.panel.isVisible():
            self._watch_timer.stop()
            return
        if time.perf_counter() < self._glance_pause_until:
            return
        self.worker.request(self._glance_job, kind="glance")

    def _start(self, fn, live: bool = False) -> bool:
        self._live_check = live
        quiet = self._rescan_active
        if live and self.panel.isVisible() and not quiet:
            self._panel_hide_timer.stop()
            self.panel.set_mode("checking", "请等待")
            self.hit_card.hide()
            self.clear_mark.hide()
        if not self.worker.request(fn):
            self._unlock_foreground()
            return False
        self._check_started = time.perf_counter()
        return True

    def _unlock_foreground(self) -> None:
        if not self._release_foreground:
            return
        self._release_foreground = False
        lock_foreground(False)

    def _on_worker(self, payload) -> None:
        job, status, value = payload
        self.worker.running_job = False
        if self._closing:
            return
        if job == "warmup":
            self._on_warmed(status, value)
            return
        if job == "glance":
            self._on_glanced(status, value)
            return
        if job == "picture":
            self._on_picture(status, value)
            return
        self._on_checked(status, value)

    def _on_warmed(self, status: str, value) -> None:
        if status != "ok":
            self._report_problem(value)
            return
        if self._warm_started is not None:
            log.info("OCR ready in %.1f s", time.perf_counter() - self._warm_started)
        if self._status_kind == "loading":
            self._sync_watch_idle()

    def _on_glanced(self, status: str, value) -> None:
        if status != "ok":
            self._report_problem(value)
            # Do not reload a missing model or retry a dead screen copy every 0.4 seconds.
            pause = 15.0 if isinstance(value, OcrUnavailable) else 5.0
            self._glance_pause_until = time.perf_counter() + pause
            return
        was_error = self._status_kind == "error"
        if self._problem:
            self._clear_problem()
        elif was_error:
            self._sync_watch_idle()
        if not value:
            if self.panel.isVisible():
                self._hide_panel_after_title()
        else:
            self._panel_hide_timer.stop()
        if not self.store.auto_capture:
            return
        now = time.perf_counter()
        if not self.watch.wants_check(bool(value), now):
            return
        self.watch.arm(now)
        self._rescan_active = False
        if not self._start(self._capture_job, live=True):
            self.watch.retry_after(now)

    def _note_watch(self, found: bool) -> None:
        if not self.store.auto_capture:
            return
        if found:
            self.watch.hold()
        else:
            self.watch.retry_after(time.perf_counter())

    def _on_checked(self, status: str, value) -> None:
        self._unlock_foreground()
        if self._closing:
            return
        rescan = self._rescan_active
        self._rescan_active = False
        elapsed = None
        if self._check_started is not None:
            elapsed = time.perf_counter() - self._check_started
            self._check_started = None
        manual = self._manual_check
        if status == "err":
            if not rescan and self._live_check and self._rescan_now():
                return
            self._manual_check = False
            self._report_problem(value)
            if self.store.auto_capture:
                self.watch.retry_after(time.perf_counter())
            self._hide_panel_after_title()
            return
        result: CheckResult = value
        if not result.header_found:
            if not rescan and self._live_check and self._rescan_now():
                return
            self._manual_check = False
            log.info("No lobby on screen: %s", result.message)
            if manual:
                self._notify("没有看到大厅", "按快捷键时，「推演成功」的画面要在屏幕上。")
            if self.store.auto_capture:
                self.watch.retry_after(time.perf_counter())
            self._hide_panel_after_title()
            return
        self._manual_check = False
        self._clear_problem()
        log.info(
            "Checked the lobby: %d on the list, %d unclear, %.2f s",
            len(result.hits),
            sum(1 for slot in result.names if slot.unclear),
            elapsed or 0.0,
        )
        self._note_watch(bool(result.header_found))
        if result.header_found and result.names:
            outcome = self.store.add_scan(
                [
                    {
                        "seat": seat_number(slot.index),
                        "name": "" if slot.unclear else slot.visible,
                        "unclear": slot.unclear,
                    }
                    for slot in result.names
                ],
                elapsed,
            )
            if outcome == "filled":
                self._apply_filled(result)
            self._reload_history()
        self._show_panel(result)
        if result.hits and self._live_check and self.store.hit_sound:
            _play_hit_sound()
        if self.store.save_debug_frames and result.preview_rgb is not None:
            self._save_debug(result)

    def _rescan_now(self) -> bool:
        if self._closing:
            return False
        self._rescan_active = True
        if self.store.auto_capture:
            self.watch.arm(time.perf_counter())
        if self._start(self._capture_job, live=True):
            return True
        self._rescan_active = False
        return False

    def _apply_filled(self, result: CheckResult) -> None:
        if not self.store.scans:
            return
        saved = {int(item["seat"]): item for item in self.store.scans[0]["names"]}
        slots: list[NameSlot] = []
        for slot in result.names:
            item = saved.get(seat_number(slot.index))
            if item is None or item.get("unclear") or not str(item.get("name") or ""):
                slots.append(slot)
                continue
            name = str(item["name"])
            slots.append(
                NameSlot(
                    index=slot.index,
                    box=slot.box,
                    raw=name,
                    visible=name,
                    truncated=name.endswith("..."),
                    confidence=slot.confidence,
                    unclear=False,
                )
            )
        result.names = slots
        hits: list[Hit] = []
        for slot in slots:
            if slot.unclear or not slot.visible:
                continue
            label = NameLabel(raw=slot.visible, visible=slot.visible, truncated=slot.truncated, unclear=False)
            for found in match_label(label, self.store.entries):
                note = describe_entry(found.entry)
                hits.append(
                    Hit(
                        index=slot.index,
                        read_text=slot.visible,
                        entry_name=found.entry.name,
                        note=note,
                        truncated=slot.truncated,
                        line=format_hit(slot.index, slot.visible, slot.truncated, found.entry.name, note),
                        tags=tuple(found.entry.tags),
                    )
                )
        result.hits = hits

    def _hide_panel_after_title(self) -> None:
        self._panel_hide_timer.stop()
        self.panel.hide()
        self.hit_card.hide()
        self.clear_mark.hide()
        if not self.store.auto_capture:
            self._watch_timer.stop()

    def _on_lobby_placed(self, box) -> None:
        if self._closing or not self._live_check:
            return
        # A finished cover stays put. A second pass must not turn it yellow again.
        if self.panel.isVisible() and self.panel.mode in ("clear", "hit"):
            return
        self._open_panel("checking", "请等待", box)
        self.hit_card.hide()
        self.clear_mark.hide()

    def _show_panel(self, result: CheckResult) -> None:
        if not self._live_check or not result.header_found:
            self._hide_panel_after_title()
            return
        if result.button_box is None:
            self._hide_panel_after_title()
            return
        if result.hits:
            self.clear_mark.hide()
            self._open_panel("hit", "", result.button_box)
            self._show_hit_card(result.hits)
            return
        self.hit_card.hide()
        text = "没有黑名单"
        unclear = sum(1 for slot in result.names if slot.unclear)
        if unclear:
            text += f"\n{unclear} 人没看清"
        self._open_panel("clear", text, result.button_box)
        self._show_clear_mark()

    def _open_panel(self, mode: str, text: str, box) -> None:
        self._panel_hide_timer.stop()
        if box is None:
            return
        self._show_panel_at(box, mode, text)
        if not self._watch_timer.isActive():
            self._watch_timer.start()

    def _show_panel_at(self, box, mode: str, text: str) -> None:
        origin_x, origin_y = virtual_origin()
        left, top, right, bottom = box
        x, y, ratio = native_to_logical(left + origin_x, top + origin_y)
        outset = _COVER_OUTSET
        self.panel.show_over(
            x - outset,
            y - outset,
            (right - left) / ratio + outset * 2,
            (bottom - top) / ratio + outset * 2,
            mode,
            text,
        )

    def _show_hit_card(self, hits: list[Hit]) -> None:
        people: list[tuple[str, tuple[str, ...]]] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for hit in hits:
            person = (hit.entry_name, tuple(hit.tags))
            if person in seen:
                continue
            seen.add(person)
            people.append(person)
        if not people:
            self.hit_card.hide()
            self.clear_mark.hide()
            return
        self.hit_card.set_people(people, self.panel.height())
        self._place_beside(self.hit_card)

    def _show_clear_mark(self) -> None:
        self.clear_mark.set_size(self.panel.height())
        self._place_beside(self.clear_mark)

    def _place_beside(self, widget: QWidget) -> None:
        gap = 12
        panel = self.panel
        x = panel.x() + panel.width() + gap
        y = panel.y() + (panel.height() - widget.height()) // 2
        screen = QApplication.screenAt(panel.pos()) or QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            if x + widget.width() > area.right() - 8:
                x = panel.x() - gap - widget.width()
            x = max(area.left() + 8, min(x, area.right() - widget.width() - 8))
            y = max(area.top() + 8, min(y, area.bottom() - widget.height() - 8))
        widget.move(int(x), int(y))
        widget.show()
        _pin_topmost(widget)

    def _sync_watch_idle(self) -> None:
        if self.store.auto_capture:
            self._set_result("自动检查中", "watchOn", "watch")
        else:
            self._set_result("手动检查", "watchOff", "idle")

    def _show_status_mark(self, pixmap: QPixmap) -> None:
        self.watch_mark.setText("")
        self.watch_mark.setObjectName("")
        self.watch_mark.setPixmap(pixmap)
        self.watch_mark.show()
        self.watch_mark.style().unpolish(self.watch_mark)
        self.watch_mark.style().polish(self.watch_mark)

    def _show_hotkey_mark(self) -> None:
        self.watch_mark.setPixmap(QPixmap())
        self.watch_mark.setObjectName("hotkey")
        self.watch_mark.setFont(chinese_font(BODY_PT))
        self.watch_mark.setText(f"[{self.store.hotkey}]")
        self.watch_mark.setVisible(bool(self.store.hotkey))
        self.watch_mark.style().unpolish(self.watch_mark)
        self.watch_mark.style().polish(self.watch_mark)

    def _set_result(self, text: str, tone: str = "status", kind: str = "result", tip: str = "") -> None:
        self._status_kind = kind
        self._watch_tone = tone
        self._watch_full = text
        self._watch_tip = tip
        colors = {
            "clear": THEME["green"],
            "hit": THEME["red"],
            "idle": THEME["muted"],
            "status": THEME["text"],
        }
        self.watch_label.setObjectName(tone)
        self.watch_label.setFont(chinese_font(BODY_PT))
        self.watch_label.setToolTip(tip or text)
        width = max(1, self.watch_label.maximumWidth())
        self.watch_label.setText(self.watch_label.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, width))
        self.watch_label.style().unpolish(self.watch_label)
        self.watch_label.style().polish(self.watch_label)
        if kind == "watch":
            self._show_status_mark(_check_icon())
        elif kind == "idle":
            self._show_hotkey_mark()
        else:
            self._show_status_mark(_watch_mark(colors.get(tone, THEME["muted"])))
        self._set_tray(text)

    def _remember_size(self) -> None:
        if not hasattr(self, "store"):
            return
        width, height = self.width(), self.height()
        if width < 900 or height < 560:
            return
        if self.store.window_size == (width, height):
            return
        self.store.window_size = (width, height)
        self.store.save_settings()

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._remember_size()

    def _save_debug(self, result: CheckResult) -> None:
        directory = self.store.root / "debug"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = directory / f"{stamp}.png"
        from PIL import Image

        image = Image.fromarray(result.preview_rgb)
        image.save(path)

    def _set_tray(self, text: str) -> None:
        if self.tray is not None:
            self.tray.setToolTip(text[:120])

    def open_data_folder(self) -> bool:
        """Show the folder with the list, settings, backups, and logs, for sending a log or restoring a backup."""
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        self.store.root.mkdir(parents=True, exist_ok=True)
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.root)))

    def quit_app(self) -> None:
        """Close for real, as 退出 in the tray menu does. The local installer asks for this before an update."""
        log.info("Asked to quit.")
        self.close()
        QApplication.quit()

    def _show_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray(self, reason) -> None:
        from PySide6.QtWidgets import QSystemTrayIcon

        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._show_from_tray()

    def closeEvent(self, event) -> None:  # noqa: ANN001
        if event.spontaneous() and self.tray is not None and self.tray.isVisible():
            # Keep checking from the tray. Without a tray icon there would be no way back, so X quits.
            event.ignore()
            self.hide()
            if not self._told_tray:
                self._told_tray = True
                self._notify("黑名单检测仍在运行", "它会继续检查大厅。在右下角的托盘图标上右键可以退出。", warning=False)
            return
        self._remember_size()
        self.hide()
        self._closing = True
        self._panel_hide_timer.stop()
        self._watch_timer.stop()
        if hasattr(self, "detail_tip"):
            self.detail_tip.close()
        self.panel.close()
        self.hit_card.close()
        self.clear_mark.close()
        self.hotkey.clear()
        self.worker.stop()
        # A check or a model load cannot be interrupted. Ending the thread under it crashes on exit.
        if not self.worker.wait(20_000):
            log.warning("The check thread was still running at exit.")
        if self.instance_server is not None:
            self.instance_server.close()
        if self.tray is not None:
            self.tray.hide()
        super().closeEvent(event)


def QSystemTrayIcon_available() -> bool:
    try:
        from PySide6.QtWidgets import QSystemTrayIcon

        return QSystemTrayIcon.isSystemTrayAvailable()
    except Exception:
        return False
