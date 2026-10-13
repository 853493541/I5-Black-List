"""Main window, tray status, and the lobby check loop."""

from __future__ import annotations

import queue
import sys
import time
from datetime import datetime

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFontMetrics,
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

from blacklist_detect import __version__, autostart, single, updater
from blacklist_detect.capture import (
    CaptureUnavailable,
    allow_any_foreground,
    bring_to_front,
    capture_capability_message,
    capture_displays,
    capture_top_band,
    lock_foreground,
    virtual_origin,
)
from blacklist_detect.diagnostics import (
    SAMPLE_NAMES,
    CpuWindow,
    FlowTest,
    export_logs,
    machine_line,
    power_note,
    run_flow_test,
    screens_line,
    summary_text,
)
from blacklist_detect.game_area import exclusive_fullscreen, window_order, window_rect_at
from blacklist_detect.hotkey import GlobalHotkey, parse_hotkey
from blacklist_detect.importing import suggest_tags, with_tags
from blacklist_detect.logs import log, mark_closed, mark_running, on_uncaught, setup_logging
from blacklist_detect.match import (
    NameLabel,
    fold,
    format_hit,
    last_seen,
    listed_tail,
    match_label,
    seat_number,
    split_ellipsis,
)
from blacklist_detect.model import Entry
from blacklist_detect.names import APP_NAME
from blacklist_detect.ocr_engine import OcrUnavailable, get_engine, inference_device
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
from blacklist_detect.storage import Store, clean_tag, describe_entry, tag_text
from blacklist_detect.ui_alert import AlertGlow
from blacklist_detect.ui_dialogs import (
    SAMPLE_LOBBY,
    AddNameDialog,
    BatchAddDialog,
    DisclaimerDialog,
    DisplayGuideDialog,
    FlowReportDialog,
    GuideDialog,
    PictureResultDialog,
    StreamGuideDialog,
    TagSuggestDialog,
    _confirm,
)
from blacklist_detect.ui_header import CheckPanel, ProfileChip, StatusChip
from blacklist_detect.ui_icons import icon as line_icon
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
from blacklist_detect.ui_likes import LikesPage
from blacklist_detect.ui_love import LoveBorder
from blacklist_detect.ui_love_pick import LoveEffectsDialog
from blacklist_detect.ui_music import WeddingMusic
from blacklist_detect.ui_notice import CornerNotice
from blacklist_detect.ui_overlay import (
    _COVER_OUTSET,
    ClearMark,
    HitCard,
    LikeCard,
    LobbyPanel,
    _cover_radius,
    _pin_topmost,
    native_to_logical,
)
from blacklist_detect.ui_stream import StreamMirror
from blacklist_detect.ui_theme import (
    APPEARANCES,
    BODY_PT,
    CONTROL_H,
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
    seat_line,
    ui_font,
    use_theme,
    wants_dark,
)
from blacklist_detect.ui_update import Download, UpdateChecker, UpdateDialog, restart_into_update
from blacklist_detect.ui_widgets import (
    NEVER_MET,
    DayFolderIcon,
    TagListDelegate,
    TagPill,
    ThemeSwatch,
    _ColumnHeader,
    _DetailTip,
    _icon,
    _local_moment,
    _mark_menu_item,
    _PlainItemDelegate,
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
    "TagPill",
    "_COVER_OUTSET",
    "_apply_theme",
    "_cover_radius",
    "_icon",
    "_zh_clock",
    "chinese_font",
    "instance_key",
    "listen_for_instances",
    "masked_name",
    "native_to_logical",
    "notify_running_instance",
    "run_app",
]

# Said once before 完整模式 is turned on, and agreed to before it runs.
CONSENT = {
    "full": (
        "开启完整模式",
        "特效直接显示在游戏窗口，可能被游戏当成异常。",
        "开启完整模式",
        "保持安全模式",
    ),
}

# Updates are looked for once each time the app opens, just after the window is up. A new version
# found then is installed before the app is used.
UPDATE_FIRST_MS = 1_000

# 主题色, the accent picker in 设置 › 外观, is hidden for now. True brings the row back. While it is
# hidden every window wears the default accent; a choice saved before waits in the settings.
THEME_PICKER = False


def _claim_windows_app() -> None:
    """Tell Windows this is its own app, so the taskbar uses our icon instead of Python's."""
    if sys.platform != "win32":
        return
    import ctypes

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Local.BlackListDetect")


def run_app(background: bool = False) -> int:
    setup_logging()
    log.info("Start %s, Python %s, %s", __version__, sys.version.split()[0], sys.platform)
    _claim_windows_app()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    key = instance_key()
    # One copy: a copy that answers is shown and this one leaves; a copy from this folder that
    # never answers is stuck open, holding the files an update needs, and is ended.
    first = single.claim(key)
    if single.settle(updater.app_root(), first, lambda: notify_running_instance(key, show=not background)):
        log.info("Already running." if background else "Already running. Brought the open window forward.")
        return 0
    app.setWindowIcon(_icon())
    app.setFont(chinese_font())
    _apply_theme(app)
    try:
        window = MainWindow()
    except Exception:
        log.critical("The window could not open", exc_info=True)
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(None, APP_NAME, "打不开，重新解压一遍安装包")
        return 1
    try:
        log.info("Computer: %s; screens %s", machine_line(), screens_line())
    except Exception:  # noqa: BLE001 - the summary must never stop the app
        log.info("Computer: unknown")
    if mark_running():
        log.warning("The last run ended without closing: it was ended from outside (Task Manager, a tool, or a power loss).")
    window.instance_server = listen_for_instances(key, window._show_from_tray, window.quit_app)
    on_uncaught(window.report_uncaught)
    # Started with Windows: stay in the tray, unless a first open or an environment check needs the window.
    quiet = (
        background
        and window.tray is not None
        and not window.store.first_run
        and window.store.disclaimer_accepted
        and window.store.env_checked == __version__
    )
    if quiet:
        log.info("Started with Windows; staying in the tray.")
    else:
        window.show()
    autostart.refresh()
    window.start_warmup()
    QTimer.singleShot(0, window.begin)
    code = app.exec()
    log.info("Exit %s", code)
    mark_closed()
    return code


def notify_running_instance(key: str, show: bool = True) -> bool:
    """Ask a copy that is already open to show its window. False when none is open.

    With show=False it only checks: a start at sign-in should not pop an open window forward.
    """
    from PySide6.QtNetwork import QLocalSocket

    socket = QLocalSocket()
    socket.connectToServer(key)
    if not socket.waitForConnected(300):
        return False
    if show:
        # The user just started this copy, so it may take the front; it hands that to the open one.
        allow_any_foreground()
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



def _lobby_summary(kinds: list[str]) -> str:
    """A checked lobby in a few words, from each seat's kind (hit, like, unclear or ""):
    「2 名黑名单 · 1 名心动 · 1 人未识别」, or 「未发现黑名单」."""
    hits, likes, unclear = kinds.count("hit"), kinds.count("like"), kinds.count("unclear")
    parts = [f"{hits} 名黑名单"] if hits else ["未发现黑名单"]
    if likes:
        parts.append(f"{likes} 名心动")
    if unclear:
        parts.append(f"{unclear} 人未识别")
    return " · ".join(parts)

class MainWindow(QMainWindow):
    uncaught = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.uncaught.connect(self._show_uncaught)
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.store = Store()
        use_theme(self._theme(), self.store.appearance)
        self.setMinimumSize(900, 560)
        saved = self.store.window_size or (900, 560)
        self.resize(saved[0], saved[1])
        # Open where it was left. Qt's own record keeps the frame right and moves a window
        # back onto a screen when the one it was on is gone.
        if self.store.window_geometry:
            from PySide6.QtCore import QByteArray

            self.restoreGeometry(QByteArray.fromBase64(self.store.window_geometry.encode("ascii")))
        # Moving or resizing saves once the window stops, not on every step of a drag.
        self._geometry_timer = QTimer(self)
        self._geometry_timer.setSingleShot(True)
        self._geometry_timer.setInterval(600)
        self._geometry_timer.timeout.connect(self._remember_size)
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
        # 心动 players in the lobby, under the hit card or beside the check.
        self.like_card = LikeCard()
        self.clear_mark = ClearMark()
        # Two or more 心动 players and no 黑名单: a border of silk and flowers, once per lobby.
        self.love = LoveBorder()
        self._love_played = False
        # 心动音乐: the same lobby, in either 显示, also gets a few seconds of wedding music.
        self.music = WeddingMusic()
        # Which scene and which music: 心动 › 心动特效.
        self.love.choice = self.store.love_scene
        # 黑名单 players in the lobby: a red glow at the screen's edges while the result is up.
        self.alert = AlertGlow()
        # 安全模式: the result in messages at the bottom right of the screen instead of over the game.
        self.notice = CornerNotice()
        self._notice_screen = None
        # 直播模式: the marks, never a 黑名单 name, in a window a streaming app can capture.
        self.stream = StreamMirror(self)
        if all(self.store.stream_size):
            # The game's window size from the last check; where it is comes with the next one.
            self.stream.set_frame(QRect(0, 0, *self.store.stream_size))
        # The lobby's button, in desktop pixels: the game's window is the one under it, in the
        # order the windows were in at the screenshot.
        self._game_box = None
        self._game_windows: tuple[int, ...] = ()
        # New versions from GitHub: checked when the app opens and installed before it is used.
        self.updates = UpdateChecker(self)
        self.updates.found.connect(self._on_update_found)
        self.updates.latest.connect(self._on_update_latest)
        self.updates.failed.connect(self._on_update_failed)
        # 检查更新 was pressed: its answer shows beside it. The check at start answers only in the log.
        self._update_asked = False
        self._release: updater.Release | None = None
        self._updating = False
        if updater.app_root() is not None:
            QTimer.singleShot(UPDATE_FIRST_MS, self._check_updates)
            QTimer.singleShot(3000, self._confirm_update)
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
        self._manual_check = False
        # When the hotkey was pressed, to log how long its check took from the player's side.
        self._pressed_at: float | None = None
        # When the recognition last ran: a model idle for a while reads its first lobby slower.
        self._last_ocr_at: float | None = None
        self._cpu: CpuWindow | None = None
        self._problem = ""
        self._glance_pause_until = 0.0
        self._warm_started: float | None = None
        # loading, ready or failed, so the environment check knows where the models stand.
        self._warm_state = ""
        self._warm_error = ""
        self._env_waiting = False
        self.setup = None
        # The last 环境测试, for 导出日志; whether the one running ends in its report.
        self._flow_test: FlowTest | None = None
        self._env_report = False
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
        # The tag picked beside 黑名单 ("" for 全部), and a press on a tag's pencil waiting for its release.
        self._tag_filter = ""
        self._tag_press = ""
        self._build()
        self._add_shortcuts()
        # Opening a window, Qt gives its first tab the focus as if Tab were pressed, and the
        # tab would draw its keyboard ring. The page takes the focus instead; Tab still reaches the tabs.
        # Focusable before the style is applied, so it keeps the input method like the rest.
        self.centralWidget().setFocusPolicy(Qt.ClickFocus)
        self._apply_style()
        self._sync_overlay_target()
        if self.store.stream_mode:
            self.stream.enable(self.store.stream_mode)
        self.centralWidget().setFocus(Qt.FocusReason.OtherFocusReason)
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
        if self.store.load_warning:
            log.warning("At start: %s", self.store.load_warning)
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
        self.likes_page = LikesPage(self.store, self._say)
        self.likes_page.show_effects = self._show_love_effects
        self.likes_page.changed.connect(self._likes_changed)
        self.likes_tab = self.tabs.addTab(self.likes_page, "心动")
        self.settings_tab = self.tabs.addTab(self._settings_page(), "设置")
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
            button.setToolTip(f"Ctrl+{index + 1}")
            self._tab_group.addButton(button, index)
            self._tab_buttons.append(button)
            header_row.addWidget(button, 0, Qt.AlignBottom)
        self._tab_group.idClicked.connect(self.tabs.setCurrentIndex)
        header_row.addStretch(1)
        # The chips keep clear of the header's line, which only the tab underline touches.
        right = QWidget()
        right_row = QHBoxLayout(right)
        right_row.setContentsMargins(0, 0, 0, 4)
        right_row.setSpacing(0)
        # What checking is doing. A click opens the 检查 settings under it.
        self.status_chip = StatusChip()
        self.status_chip.clicked.connect(lambda: self.check_panel.toggle())
        right_row.addWidget(self.status_chip, 0, Qt.AlignVCenter)
        right_row.addSpacing(12)
        divider = QFrame()
        divider.setObjectName("headerDivider")
        divider.setFixedSize(1, 18)
        right_row.addWidget(divider, 0, Qt.AlignVCenter)
        right_row.addSpacing(8)
        # 角色名称 where an app shows whose it is. A click turns the chip into a box for the
        # name, in the same place: Enter or a click elsewhere keeps it, Esc puts it back.
        self.profile_chip = ProfileChip()
        self.profile_chip.set_name(self.store.player_name)
        self.profile_chip.clicked.connect(self._edit_player_name)
        right_row.addWidget(self.profile_chip, 0, Qt.AlignVCenter)
        self.player_edit = QLineEdit(self.store.player_name)
        self.player_edit.setObjectName("nameEdit")
        self.player_edit.setPlaceholderText("游戏名")
        self.player_edit.setAccessibleName("游戏名")
        self.player_edit.setFixedWidth(180)
        self.player_edit.hide()
        self.player_edit.installEventFilter(self)
        self.player_edit.returnPressed.connect(self._finish_player_name)
        right_row.addWidget(self.player_edit, 0, Qt.AlignVCenter)
        self._name_before = ""
        header_row.addWidget(right, 0, Qt.AlignBottom)
        self._sync_tab_buttons(self.tabs.currentIndex())
        outer.addWidget(header)
        self.check_panel.attach(root, self.status_chip)
        self.tabs.currentChanged.connect(lambda _index: self.check_panel.close_panel())
        outer.addWidget(self.tabs)
        self.toast = Toast(root)

        self.tray = None
        if QSystemTrayIcon_available():
            from PySide6.QtWidgets import QSystemTrayIcon

            self.tray = QSystemTrayIcon(_icon(), self)
            self.tray.setToolTip(f"{APP_NAME} {__version__}")
            self.tray_menu = QMenu()
            self.tray_menu.setFont(chinese_font())
            self.tray_menu.setStyleSheet(_menu_style(chinese_family()))
            self.tray_menu.addAction("显示主窗口", self._show_from_tray)
            self.tray_menu.addAction("退出", self.close)
            self.tray.setContextMenu(self.tray_menu)
            self.tray.activated.connect(self._on_tray)
            self.tray.show()

    def _list_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        _page(outer)
        body = QHBoxLayout()
        body.setSpacing(GAP)
        outer.addLayout(body, 1)
        body.addWidget(self._list_side())
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(GAP)
        body.addLayout(layout, 1)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.list_search = QLineEdit()
        self.list_search.setPlaceholderText("搜索名字、标签或原因")
        self.list_search.setClearButtonEnabled(True)
        self.list_search.setMaximumWidth(360)
        self.list_search.setAccessibleName("搜索名字、标签或原因")
        self.search_icon = self.list_search.addAction(
            line_icon("search", 16, THEME["muted"]), QLineEdit.ActionPosition.LeadingPosition
        )
        self.list_search.setToolTip("Ctrl+F")
        self.list_search.textChanged.connect(self._on_search_text)
        toolbar.addWidget(self.list_search, 1)
        toolbar.addStretch(1)
        batch = QPushButton("批量导入")
        batch.setToolTip("Ctrl+I")
        batch.clicked.connect(self._add_many_by_dialog)
        add = QPushButton("添加")
        add.setObjectName("primary")
        add.setToolTip("Ctrl+N")
        add.clicked.connect(self._add_by_dialog)
        self.toolbar_buttons = (batch, add)
        toolbar.addWidget(batch)
        toolbar.addWidget(add)
        # 复制名单, 按原因补标签 and 清空黑名单 are used now and then, so they wait under 更多 instead of
        # beside 添加.
        self.more_button = IconButton("more", "更多")
        self.more_menu = QMenu(self)
        self.share_action = self.more_menu.addAction("复制名单", self._share_list)
        _mark_menu_item(self.share_action, "copy")
        # Tags for what each 原因 already says, such as 场外 for 「场外说话」.
        self.recheck_action = self.more_menu.addAction("按原因补标签", self._recheck_tags)
        _mark_menu_item(self.recheck_action, "reload")
        self.more_menu.addSeparator()
        self.clear_list_action = self.more_menu.addAction("清空黑名单", self._clear_list)
        _mark_menu_item(self.clear_list_action, "delete")
        self.more_button.clicked.connect(self._open_more_menu)
        toolbar.addWidget(self.more_button)
        self.blacklist_table = QTableWidget(0, 4)
        self.blacklist_table.setObjectName("blacklist")
        name_header = _ColumnHeader(self.blacklist_table)
        name_header.names_hidden = self._names_hidden()
        name_header.locked = bool(self.store.stream_mode)
        name_header.on_eye = self._toggle_name_hiding
        self.blacklist_table.setHorizontalHeader(name_header)
        self.blacklist_table.setHorizontalHeaderLabels(["名字", "标签", "原因", "最近遇到"])
        header = self.blacklist_table.horizontalHeader()
        header.setStretchLastSection(False)
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
        self.blacklist_table.setFocusPolicy(Qt.StrongFocus)
        self.blacklist_table.setAccessibleName("黑名单")
        self.blacklist_table.installEventFilter(self)
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
        self.list_empty = EmptyState("users", "黑名单还是空的")
        self.list_hint = self.list_empty.title
        self.empty_batch_button = self.list_empty.add_action(QPushButton("批量导入"))
        self.empty_batch_button.clicked.connect(self._add_many_by_dialog)
        self.empty_add_button = self.list_empty.add_action(QPushButton("添加"))
        self.empty_add_button.setObjectName("primary")
        self.empty_add_button.clicked.connect(self._add_by_dialog)
        layout.addLayout(toolbar)
        layout.addWidget(self.blacklist_table, 1)
        layout.addWidget(self.list_empty, 1)
        return page

    def _list_side(self) -> QWidget:
        """标签 beside the list: each one picks which names the list shows, and 全部 shows them all."""
        side = QWidget()
        # As wide as the list of records on 记录, so the left column stays put between the pages.
        side.setFixedWidth(168)
        self.list_side = side
        column = QVBoxLayout(side)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(GAP)
        head_row = QWidget()
        head_row.setFixedHeight(CONTROL_H)
        head = QHBoxLayout(head_row)
        # The title lines up with the pills below it, which sit 12 px into their rows.
        head.setContentsMargins(TagListDelegate.INSET, 0, 0, 0)
        head.setSpacing(4)
        title = QLabel("标签")
        title.setObjectName("sideTitle")
        self.tag_title = title
        self.tag_head = head
        head.addWidget(title, 1, Qt.AlignVCenter)
        self.tag_add = IconButton("add", "新标签")
        self.tag_add.clicked.connect(self._create_tag)
        head.addWidget(self.tag_add, 0, Qt.AlignVCenter)
        # + turns the heading into a box for the new tag's name.
        self.tag_new_edit = QLineEdit()
        self.tag_new_edit.setObjectName("tagEdit")
        self.tag_new_edit.setPlaceholderText("新标签")
        self.tag_new_edit.setAccessibleName("新标签")
        self.tag_new_edit.hide()
        self.tag_new_edit.installEventFilter(self)
        self.tag_new_edit.returnPressed.connect(self._finish_tag_new)
        head.addWidget(self.tag_new_edit, 1)
        column.addWidget(head_row)
        self.tag_list = QListWidget()
        self.tag_list.setObjectName("tags")
        self.tag_list.setAccessibleName("标签")
        self.tag_list.setFocusPolicy(Qt.StrongFocus)
        self.tag_list.setItemDelegate(TagListDelegate(self.tag_list))
        self.tag_list.setProperty("hoverRow", -1)
        self.tag_list.setCursor(Qt.PointingHandCursor)
        self.tag_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tag_list.setMouseTracking(True)
        self.tag_list.viewport().setMouseTracking(True)
        self.tag_list.installEventFilter(self)
        self.tag_list.viewport().installEventFilter(self)
        self.tag_list.currentRowChanged.connect(self._on_tag_picked)
        self.tag_list.itemDoubleClicked.connect(self._on_tag_double_clicked)
        self.tag_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tag_list.customContextMenuRequested.connect(self._tag_menu)
        column.addWidget(self.tag_list, 1)
        # 编辑 turns a tag's row into a box with its name, over the row.
        self.tag_editor = QLineEdit(self.tag_list.viewport())
        self.tag_editor.setObjectName("tagEdit")
        self.tag_editor.setAccessibleName("标签")
        self.tag_editor.hide()
        self.tag_editor.installEventFilter(self)
        self.tag_editor.returnPressed.connect(self._finish_tag_edit)
        self._tag_editing = ""
        self._fill_tag_list()
        return side

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
        self.history_list.setFocusPolicy(Qt.StrongFocus)
        self.history_list.setAccessibleName("记录")
        self.history_list.installEventFilter(self)
        self.history_list.setItemDelegate(_PlainItemDelegate(self.history_list))
        self.history_list.setCursor(Qt.PointingHandCursor)
        self.history_list.setMouseTracking(True)
        self.history_list.viewport().setMouseTracking(True)
        self.history_list.viewport().installEventFilter(self)
        self.history_list.currentRowChanged.connect(self._on_history_picked)
        self.history_list.itemClicked.connect(self._on_history_clicked)
        side_layout.addWidget(self.history_list, 1)
        # A lobby from a picture, read the way a live check reads it.
        self.picture_button = QPushButton("用截图检查")
        self.picture_button.setObjectName("sideAction")
        self.picture_button.setFont(chinese_font(SMALL_PT))
        self.picture_button.setIcon(line_icon("picture", 14, THEME["muted"]))
        self.picture_button.setAutoDefault(False)
        self.picture_button.setCursor(Qt.PointingHandCursor)
        self.picture_button.clicked.connect(self.check_picture)
        side_layout.addWidget(self.picture_button)
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
        catalog = QLabel("模仿者狂欢（12人狂欢）")
        catalog.setObjectName("recordTitle")
        catalog.setFont(record_font())
        head.addWidget(catalog)
        head.addStretch(1)
        # What this lobby had. The time is in the list on the left already.
        self.record_summary = QLabel("")
        self.record_summary.setObjectName("sub")
        head.addWidget(self.record_summary)
        self.record_more = IconButton("more", "更多")
        self.record_menu = QMenu(self)
        self.delete_record_action = self.record_menu.addAction("删除", self._delete_history)
        _mark_menu_item(self.delete_record_action)
        self.record_menu.addSeparator()
        self.clear_history_action = self.record_menu.addAction("清空记录", self._ask_clear_history)
        _mark_menu_item(self.clear_history_action, "delete")
        self.record_more.clicked.connect(self._open_record_menu)
        head.addWidget(self.record_more)
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
        self.history_table.setFocusPolicy(Qt.StrongFocus)
        self.history_table.setAccessibleName("模仿者狂欢（12人狂欢）")
        self.history_table.installEventFilter(self)
        self.history_table.currentCellChanged.connect(self._on_seat_current)
        self.history_table.setItemDelegate(_PlainItemDelegate(self.history_table))
        self.history_table.setShowGrid(False)
        self.history_table.setMouseTracking(True)
        self.history_table.viewport().setMouseTracking(True)
        self.history_table.viewport().installEventFilter(self)
        self.history_table.cellEntered.connect(self._hover_history_cell)
        self.history_table.cellClicked.connect(self._on_history_cell)
        self.history_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_table.customContextMenuRequested.connect(self._history_menu)
        names.addWidget(self.history_table)
        self.record_column = QWidget()
        column = QVBoxLayout(self.record_column)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(record)
        column.addStretch(1)
        body.addWidget(self.record_column, 1)
        self.history_empty = EmptyState("records", "还没有记录", "进入「推演成功」大厅时自动检查")
        self.history_hint = self.history_empty.title
        self.picture_empty_button = self.history_empty.add_action(QPushButton("用截图检查"))
        self.picture_empty_button.clicked.connect(self.check_picture)
        body.addWidget(self.history_empty, 1)
        layout.addLayout(body, 1)
        return page

    def _settings_page(self) -> QWidget:
        """One card per row, like settings grouped with like, all on one screen:
        常规, 外观, then 帮助 at the foot, where starting over is out of the way.

        检查 (显示, 方式, 直播模式) opens from the status pill in the header, 角色名称 is in the
        header too, 标签 beside the list on 黑名单, and 心动特效 on 心动.
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        _page(layout)
        # Only a very large text size makes this scroll; at the smallest window it fits.
        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.settings_scroll = scroll
        body = QWidget()
        body.setObjectName("settingsBody")
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(GAP)
        # A readable width: on a wide window the rows do not stretch across the screen.
        holder = QWidget()
        holder.setMaximumWidth(760)
        cards = QVBoxLayout(holder)
        cards.setContentsMargins(0, 0, 0, 0)
        cards.setSpacing(18)
        column.addWidget(holder)
        column.addStretch(1)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        metrics = QFontMetrics(chinese_font())
        slot = metrics.horizontalAdvance("手动检查") + 28
        label_width = metrics.horizontalAdvance("关闭窗口时") + 8

        def section(title: str) -> SettingsSection:
            card = SettingsSection(title, label_width, compact=True)
            cards.addWidget(card)
            return card

        # 检查: how and when a lobby is checked, in a card that opens from the status pill.
        check = SettingsSection("检查", metrics.horizontalAdvance("直播模式") + 20)
        # 1 显示: 安全模式 shows the result in a corner box; 完整模式 draws it over the game.
        self.display_mode = SegmentedControl(
            [("safe", "安全模式"), ("full", "完整模式")], "safe" if self.store.safe_mode else "full"
        )
        self.display_mode.setAccessibleName("显示")
        self.safe_on = self.display_mode.buttons["safe"]
        self.full_on = self.display_mode.buttons["full"]
        self.display_mode.changed.connect(self._on_display_mode)
        # ⓘ: the two, side by side, in pictures.
        self.display_guide = IconButton("info", "显示说明")
        self.display_guide.clicked.connect(self._show_display_guide)
        check.add_row("显示", self.display_mode, self.display_guide)
        # 2 方式: 手动检查 waits for the hotkey; 自动检查 watches for the lobby, in 完整模式 only.
        # The default comes first, as in every choice here.
        self.auto_mode = SegmentedControl(
            [("manual", "手动检查"), ("auto", "自动检查")], "auto" if self.store.auto_capture else "manual"
        )
        self.auto_on = self.auto_mode.buttons["auto"]
        self.auto_off = self.auto_mode.buttons["manual"]
        self.auto_mode.changed.connect(self._on_auto_mode)
        self._sync_auto_controls()
        self.hotkey_edit = QLineEdit()
        self.hotkey_edit.setReadOnly(True)
        self.hotkey_edit.setPlaceholderText("无")
        # Room for the longest key there is, Ctrl+Shift+Alt+F12 aside: Ctrl+Alt+F12.
        self.hotkey_edit.setFixedWidth(max(slot, metrics.horizontalAdvance("Ctrl+Alt+F12") + 32))
        self.hotkey_edit.setCursor(Qt.PointingHandCursor)
        self.hotkey_edit.installEventFilter(self)
        self.hotkey_edit.setAccessibleName("快捷键")
        check.add_row("方式", self.auto_mode, self.hotkey_edit)
        # Hotkey problems show right under the hotkey they are about.
        self.settings_label = QLabel("")
        self.settings_label.setObjectName("rowHint")
        self.settings_label.setWordWrap(True)
        self.settings_label.hide()
        check.add_widget(self.settings_label, separated=False, indent=True)
        # 3 直播模式: a window for the streaming app, with the marks and never a 黑名单 name.
        self.stream_switch = Switch(bool(self.store.stream_mode))
        self.stream_switch.setAccessibleName("直播模式")
        self.stream_switch.toggled.connect(self._on_stream_switch)
        # ⓘ: what viewers see, and how to set it up in 直播姬, with screenshots.
        self.stream_guide = IconButton("info", "直播模式说明")
        self.stream_guide.clicked.connect(self._show_stream_guide)
        check.add_row("直播模式", self.stream_switch, self.stream_guide)
        # Put over the window under the pill once the header is built.
        self.check_panel = CheckPanel(check)

        # 常规: how the app starts and closes.
        general = section("常规")
        self.autostart_switch = Switch(autostart.is_enabled())
        self.autostart_switch.setAccessibleName("开机启动")
        self.autostart_switch.setEnabled(autostart.available())
        self.autostart_switch.toggled.connect(self._set_autostart)
        general.add_row("开机启动", self.autostart_switch)
        # Asked the way Chinese desktop apps ask it: what × does, with both answers in view.
        self.close_mode = SegmentedControl(
            [("tray", "最小化到托盘"), ("quit", "退出程序")], "tray" if self.store.close_to_tray else "quit"
        )
        self.close_mode.changed.connect(self._on_close_mode)
        general.add_row("关闭窗口时", self.close_mode)
        self.disclaimer_button = QPushButton("使用声明")
        self.disclaimer_button.setFont(ui_font())
        self.disclaimer_button.setAutoDefault(False)
        self.disclaimer_button.setCursor(Qt.PointingHandCursor)
        self.disclaimer_button.clicked.connect(self._show_disclaimer)

        # 外观: how the window looks.
        look = section("外观")
        self.appearance_control = SegmentedControl(
            [("light", "浅色"), ("dark", "深色"), ("system", "跟随系统")], self.store.appearance
        )
        self.appearance_buttons: dict[str, QPushButton] = self.appearance_control.buttons
        self.appearance_control.changed.connect(self._set_appearance)
        look.add_row("模式", self.appearance_control)
        self.theme_buttons: dict[str, ThemeSwatch] = {}
        if THEME_PICKER:
            swatch_host = QWidget()
            swatches = QHBoxLayout(swatch_host)
            swatches.setSpacing(8)
            swatches.setContentsMargins(0, 0, 0, 0)
            for name in THEMES:
                swatch = ThemeSwatch(name, THEMES[name]["accent"])
                swatch.chosen.connect(self._set_theme)
                self.theme_buttons[name] = swatch
                swatches.addWidget(swatch, 0, Qt.AlignVCenter)
            look.add_row("主题色", swatch_host)

        # 帮助: when something is wrong, what a friend can do and send. 环境测试 and its log share a row.
        helping = section("帮助")
        # 环境测试: the first open's test again, then a report of where a check's time goes.
        self.test_button = QPushButton("开始")
        self.test_button.setFont(ui_font())
        self.test_button.setAutoDefault(False)
        self.test_button.setCursor(Qt.PointingHandCursor)
        self.test_button.clicked.connect(lambda: self.start_environment_check(force=True))
        self.export_button = QPushButton("导出日志")
        self.export_button.setFont(ui_font())
        self.export_button.setAutoDefault(False)
        self.export_button.setCursor(Qt.PointingHandCursor)
        self.export_button.clicked.connect(self._export_logs)
        helping.add_row("环境测试", self.test_button, self.export_button)
        # 关于: this version, 检查更新 and 使用声明 in one row, so 设置 still fits on one screen.
        self.version_label = QLabel(__version__)
        self.update_button = QPushButton("检查更新")
        self.update_button.setFont(ui_font())
        self.update_button.setAutoDefault(False)
        self.update_button.setCursor(Qt.PointingHandCursor)
        self.update_button.clicked.connect(self._check_updates_now)
        # What 检查更新 found, in gray after the buttons.
        self.update_note = QLabel("")
        self.update_note.setObjectName("rowHint")
        helping.add_row("关于", self.version_label, self.update_button, self.disclaimer_button, self.update_note)
        # Starting over sits here too: one card fewer, so 设置 fits the window without scrolling.
        data = helping
        reset = QPushButton("清空数据")
        reset.setObjectName("danger")
        reset.setFont(ui_font())
        self.reset_button = reset
        reset.setAutoDefault(False)
        reset.setCursor(Qt.PointingHandCursor)
        reset.clicked.connect(self._ask_reset)
        data.add_row("重置", reset)
        return page

    def _fill_tag_list(self) -> None:
        """全部 and each tag, with how many names carry it. Rows are rebuilt only when the tags change."""
        view = getattr(self, "tag_list", None)
        if view is None:
            return
        catalog = self.store.tag_catalog()
        if self._tag_filter not in catalog:
            self._tag_filter = ""
        counts: dict[str, int] = {}
        for entry in self.store.entries:
            for tag in entry.tags:
                counts[tag] = counts.get(tag, 0) + 1
        rows = [("", len(self.store.entries)), *((tag, counts.get(tag, 0)) for tag in catalog)]
        view.blockSignals(True)
        if [self._tag_at(row) for row in range(view.count())] != [tag for tag, _count in rows]:
            view.clear()
            for tag, _count in rows:
                item = QListWidgetItem(tag or "全部")
                item.setData(Qt.UserRole, tag)
                view.addItem(item)
        for row, (tag, count) in enumerate(rows):
            view.item(row).setData(Qt.UserRole + 1, count)
            if tag == self._tag_filter and view.currentRow() != row:
                view.setCurrentRow(row)
        view.blockSignals(False)

    def _tag_at(self, row: int) -> str:
        item = self.tag_list.item(row) if row >= 0 else None
        return str(item.data(Qt.UserRole) or "") if item is not None else ""

    def _on_tag_picked(self, row: int) -> None:
        tag = self._tag_at(row)
        if tag == self._tag_filter:
            return
        self._tag_filter = tag
        self._show_list()

    def _on_tag_double_clicked(self, item: QListWidgetItem) -> None:
        tag = str(item.data(Qt.UserRole) or "")
        if tag:
            self._edit_tag(tag)

    def _hover_tag_row(self, row: int) -> None:
        if self.tag_list.property("hoverRow") == row:
            return
        self.tag_list.setProperty("hoverRow", row)
        self.tag_list.viewport().update()

    def _on_tag_pencil(self, event) -> bool:  # noqa: ANN001
        """A press and release on a tag's pencil opens 修改, the way a button would; the row is not picked."""
        if event.button() != Qt.LeftButton:
            return False
        pos = event.position().toPoint()
        row = self.tag_list.indexAt(pos).row()
        tag = self._tag_at(row)
        on_pencil = bool(tag) and TagListDelegate.edit_target(self.tag_list.visualItemRect(self.tag_list.item(row))).contains(pos)
        if event.type() == QEvent.Type.MouseButtonPress:
            self._tag_press = tag if on_pencil else ""
            return on_pencil
        pressed, self._tag_press = self._tag_press, ""
        if not pressed:
            return False
        if on_pencil and tag == pressed:
            self._edit_tag(tag)
        return True

    def _tag_menu(self, pos) -> None:  # noqa: ANN001
        tag = self._tag_at(self.tag_list.indexAt(pos).row())
        if not tag:
            return
        menu = self._menu((("编辑", ("tag_edit", tag)), None, ("删除", ("tag_delete", tag))))
        menu.popup(self.tag_list.viewport().mapToGlobal(pos))

    def _recheck_tags(self) -> None:
        self.store.recheck_tags()
        self._show_list()

    def _create_tag(self) -> None:
        """+ turns the 标签 heading into a box for a new tag's name."""
        self._finish_tag_edit()
        self.tag_title.hide()
        self.tag_add.hide()
        # The box fills the heading, its left edge where a renamed tag's box starts.
        self.tag_head.setContentsMargins(4, 0, 0, 0)
        self.tag_new_edit.clear()
        self.tag_new_edit.show()
        self.tag_new_edit.setFocus(Qt.MouseFocusReason)

    def _finish_tag_new(self, keep: bool = True) -> None:
        if self.tag_new_edit.isHidden():
            return
        tag = clean_tag(self.tag_new_edit.text()) if keep else ""
        self.tag_new_edit.hide()
        self.tag_head.setContentsMargins(TagListDelegate.INSET, 0, 0, 0)
        self.tag_title.show()
        self.tag_add.show()
        if not tag:
            return
        if tag in self.store.tag_catalog():
            self._say("标签已存在")
            return
        if self.store.add_custom_tag(tag):
            self.store.save_settings()
            self._fill_tag_list()

    def _edit_tag(self, tag: str) -> None:
        """The tag's row turns into a box with its name. Enter or a click elsewhere keeps it; Esc does not."""
        rows = [row for row in range(self.tag_list.count()) if tag and self._tag_at(row) == tag]
        if not rows:
            return
        self._finish_tag_new(keep=False)
        self._finish_tag_edit()
        self._tag_editing = tag
        rect = self.tag_list.visualItemRect(self.tag_list.item(rows[0]))
        self.tag_editor.setGeometry(rect.adjusted(4, 3, -4, -3))
        self.tag_editor.setText(tag)
        self.tag_editor.show()
        self.tag_editor.raise_()
        self.tag_editor.setFocus(Qt.MouseFocusReason)
        self.tag_editor.selectAll()

    def _finish_tag_edit(self, keep: bool = True) -> None:
        if self.tag_editor.isHidden():
            return
        tag, self._tag_editing = self._tag_editing, ""
        renamed = clean_tag(self.tag_editor.text()) if keep else ""
        self.tag_editor.hide()
        if not renamed or renamed == tag:
            return
        result = self.store.rename_tag(tag, renamed)
        if result == "taken":
            self._say("标签已存在")
        elif result == "renamed":
            if self._tag_filter == tag:
                self._tag_filter = renamed
            self._refresh_tag_views()

    def _refresh_tag_views(self) -> None:
        self._show_list()
        self._show_history_scan(self._selected_scan())

    def _remove_tag(self, tag: str) -> None:
        names = [entry.name for entry in self.store.entries if tag in entry.tags]
        if not names:
            text = f"确定删除标签「{tag}」吗？"
        else:
            shown = "、".join(names[:6])
            if len(names) > 6:
                shown += "等"
            text = f"「{tag}」{len(names)} 人正在使用，是否确定删除？"
        if not _confirm(self, text, "删除标签", "删除"):
            return
        if not self.store.remove_custom_tag(tag):
            return
        self._refresh_tag_views()

    def _set_settings_note(self, text: str) -> None:
        self.settings_label.setText(text)
        self.settings_label.setVisible(bool(text))

    def _ask_reset(self) -> None:
        if not _confirm(self, "清空数据后无法恢复，是否确定清空？", "清空数据", "清空"):
            return
        self.store.reset()
        self.hotkey.clear()
        self._tag_filter = ""
        self.player_edit.setText("")
        self.profile_chip.set_name("")
        self.hotkey_edit.clearFocus()
        self._show_hotkey()
        self._sync_hotkey_mode()
        self._set_settings_note("")
        self._sync_auto_controls()
        if autostart.is_enabled():
            autostart.set_enabled(False)
        self._sync_switch(self.autostart_switch, autostart.is_enabled())
        self.close_mode.set_current("tray" if self.store.close_to_tray else "quit")
        self.love.choice = self.store.love_scene
        self.display_mode.set_current("safe")
        self._sync_switch(self.stream_switch, False)
        self.notice.hide()
        if not self._watch_timer.isActive():
            self.watch = LobbyWatch()
            self._watch_timer.start()
        self._sync_watch_idle()
        use_theme(self._theme(), self.store.appearance)
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
        self.like_card.hide()
        self.clear_mark.hide()
        self.love.stop()
        self._love_played = False
        self.alert.stop()
        self.stream.enable("")
        self._sync_overlay_target()
        self._reload_history()
        self.likes_page.refresh()

    def _edit_player_name(self) -> None:
        """The chip becomes a box for the name, the same height and in the same place."""
        self._name_before = self.store.player_name
        self.player_edit.setText(self.store.player_name)
        self.player_edit.setFixedHeight(self.profile_chip.height())
        self.profile_chip.hide()
        self.player_edit.show()
        self.player_edit.setFocus(Qt.MouseFocusReason)
        self.player_edit.selectAll()

    def _finish_player_name(self, keep: bool = True) -> None:
        if self.player_edit.isHidden():
            return
        if not keep:
            self.player_edit.setText(self._name_before)
        self.player_edit.hide()
        self.profile_chip.show()
        self._save_player_name()

    def _save_player_name(self) -> None:
        name = self.player_edit.text().strip()
        self.profile_chip.set_name(name)
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
        if getattr(self, "reset_button", None) is not None:
            self.reset_button.setFont(ui_font())
        _pointing(self)
        self._mark_theme_buttons()
        if hasattr(self, "tag_list"):
            self.tag_add.refresh()
            self.tag_list.viewport().update()
        if hasattr(self, "picture_button"):
            self.picture_button.setIcon(line_icon("picture", 14, THEME["muted"]))
        if hasattr(self, "watch_label"):
            self._set_result(self._watch_full, self._watch_tone, self._status_kind, self._watch_tip)
        if hasattr(self, "profile_chip"):
            self.status_chip.update()
            self.profile_chip.update()
        if hasattr(self, "detail_tip"):
            self.detail_tip.apply_theme()
        if hasattr(self, "list_empty"):
            self.list_empty.refresh()
            self.more_button.refresh()
        if hasattr(self, "record_more"):
            self.record_more.refresh()
            for action in (*self.more_menu.actions(), *self.record_menu.actions()):
                _mark_menu_item(action, str(action.property("icon_name") or ""))
        if hasattr(self, "search_icon"):
            self.search_icon.setIcon(line_icon("search", 16, THEME["muted"]))
        if hasattr(self, "history_empty"):
            self.history_empty.refresh()
        if hasattr(self, "likes_page"):
            self.likes_page.restyle()

    def _theme(self) -> str:
        """The accent the windows wear: the one chosen in 主题色, or the default while it is hidden."""
        return self.store.theme if THEME_PICKER else "蓝色"

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
        use_theme(self._theme(), self.store.appearance)
        icon = _icon()
        self.setWindowIcon(icon)
        if self.tray is not None:
            self.tray.setIcon(icon)
        self._apply_style()
        _caption_color(self)
        if getattr(self, "tray_menu", None) is not None:
            # The tray menu has no parent window, so it does not get the window's new style.
            self.tray_menu.setStyleSheet(_menu_style(chinese_family()))
        self._reload_history(max(0, self._selected_scan()))
        self._show_list()

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001
        if getattr(self, "_closing", False):
            # Child widgets are being torn down. Touching them now raises.
            return False
        closers = {
            getattr(self, "player_edit", None): self._finish_player_name,
            getattr(self, "tag_editor", None): self._finish_tag_edit,
            getattr(self, "tag_new_edit", None): self._finish_tag_new,
        }
        finish = closers.get(watched) if watched is not None else None
        if finish is not None:
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key_Escape:
                finish(keep=False)
                return True
            if event.type() == QEvent.Type.FocusOut:
                finish()
        if event.type() == QEvent.Type.KeyPress and self._list_key(watched, event):
            return True
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
        tags = getattr(self, "tag_list", None)
        if tags is not None and watched is tags.viewport():
            kind = event.type()
            if kind == QEvent.Type.MouseMove:
                self._hover_tag_row(tags.indexAt(event.position().toPoint()).row())
            elif kind == QEvent.Type.Leave:
                self._hover_tag_row(-1)
            elif kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease) and self._on_tag_pencil(event):
                return True
        tip = getattr(self, "detail_tip", None)
        if tip is not None and watched is tip:
            if event.type() == QEvent.Type.Enter:
                self._detail_tip_timer.stop()
            elif event.type() == QEvent.Type.Leave:
                self._schedule_detail_tip_hide()
        if watched.property("scanRow") is not None:
            button = watched.findChild(QPushButton, "rowDelete")
            badge = [watched.findChild(QLabel, name) for name in ("recordHits", "recordHitCount")]
            kind = event.type()
            if button is not None and kind in (QEvent.Type.Enter, QEvent.Type.Leave):
                hovered = kind == QEvent.Type.Enter
                button.setVisible(hovered)
                for part in badge:
                    if part is not None:
                        part.setVisible(not hovered)
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
        self._remember_geometry_soon()

    def _list_cell(self, text: str, store_index: int | None = None, font=None, ink=None) -> QTableWidgetItem:  # noqa: ANN001
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setFont(font if font is not None else chinese_font(BODY_PT))
        item.setForeground(ink if ink is not None else QColor(THEME["text"]))
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        if store_index is not None:
            item.setData(Qt.UserRole, store_index)
        return item

    def _sort_stamp(self, index: int, column: int) -> float | None:
        if column != 3:
            return None
        stamp = self._last_met_stamps().get(index)
        moment = _local_moment(stamp) if stamp else None
        return None if moment is None else moment.timestamp()

    def _search_text(self) -> str:
        search = getattr(self, "list_search", None)
        return search.text().strip() if search is not None else ""

    def _ordered_entries(self) -> list[tuple[int, Entry]]:
        rows = list(enumerate(self.store.entries))
        if self._tag_filter:
            rows = [pair for pair in rows if self._tag_filter in pair[1].tags]
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
        if column == 0:
            # Chinese names in pinyin order, as a Chinese reader expects, then the rest.
            from functools import cmp_to_key

            from PySide6.QtCore import QCollator, QLocale

            collator = QCollator(QLocale(QLocale.Language.Chinese, QLocale.Country.China))
            collator.setNumericMode(True)
            ordered = sorted(rows, key=cmp_to_key(lambda a, b: collator.compare(a[1].name, b[1].name)))
            return ordered if newest else ordered[::-1]

        def key(pair: tuple[int, Entry]) -> tuple[bool, float, int]:
            index, _entry = pair
            stamp = self._sort_stamp(index, column)
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

    # 原因 takes whatever width is left, wherever it sits, so a wider window shows more
    # of the reason. The other columns keep the widths the user gave them.
    _FLEX_COLUMN = 2

    def _fit_blacklist_columns(self, prefer: int | None = None) -> None:
        """Keep every column inside the list. Extra width goes to, or comes out of, 原因."""
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
        saved = list(self.store.column_widths)
        if len(saved) != count:
            saved = [header.sectionSize(index) for index in range(count)]
        width = {
            logical: max(minimum, header.sectionSize(logical) if prefer is not None else saved[logical])
            for logical in logicals
        }
        flex = self._FLEX_COLUMN if self._FLEX_COLUMN in logicals else logicals[-1]
        if prefer == flex:
            # Dragging 原因's own edge moves that boundary: the column on its right gives or takes.
            visual = header.visualIndex(flex)
            prefer = None
            if visual + 1 < count:
                neighbour = logicals[visual + 1]
                rest = sum(size for logical, size in width.items() if logical not in (flex, neighbour))
                width[neighbour] = max(minimum, available - rest - width[flex])
                prefer = neighbour
        fixed = [logical for logical in logicals if logical != flex]
        overflow = sum(width[logical] for logical in fixed) + minimum - available
        order = list(reversed(fixed))
        if prefer in fixed:
            # The column being resized gives way first, so the others keep their size.
            order.remove(prefer)
            order.insert(0, prefer)
        for logical in order:
            if overflow <= 0:
                break
            cut = min(max(width[logical] - minimum, 0), overflow)
            width[logical] -= cut
            overflow -= cut
        width[flex] = max(minimum, available - sum(width[logical] for logical in fixed))
        self._fitting_columns = True
        header.blockSignals(True)
        try:
            for logical in logicals:
                if header.sectionSize(logical) != width[logical]:
                    table.setColumnWidth(logical, width[logical])
                if prefer is not None and logical != flex and 0 <= logical < len(self.store.column_widths):
                    self.store.column_widths[logical] = width[logical]
        finally:
            header.blockSignals(False)
            self._fitting_columns = False

    def _save_column_width(self, logical: int, _old: int, new: int) -> None:
        if getattr(self, "_fitting_columns", False):
            return
        if logical == self._FLEX_COLUMN:
            self._fit_blacklist_columns(prefer=logical)
            self.store.save_settings()
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
        if column not in (0, 3):
            return
        first = self._blacklist_sort != (column, True)
        self._blacklist_sort = (column, first)
        header = self.blacklist_table.horizontalHeader()
        header.setSortIndicatorShown(True)
        if column == 0:
            header.setSortIndicator(column, Qt.AscendingOrder if first else Qt.DescendingOrder)
        else:
            header.setSortIndicator(column, Qt.DescendingOrder if first else Qt.AscendingOrder)
        self._show_list()

    def _last_met_stamps(self) -> dict[int, str]:
        """When each listed name was last seen, as the record's time, from one pass (newest first).

        Kept until the list or the records change: a search letter or a theme change
        redraws the list, and matching every seat against a long list each time was slow.
        """
        entries = self.store.entries
        scans = self.store.scans
        key = (
            tuple(entry.name for entry in entries),
            tuple((str(scan.get("at", "")), tuple(str(seat.get("name") or "") for seat in scan.get("names", []))) for scan in scans),
        )
        cached = getattr(self, "_met_cache", None)
        if cached is not None and cached[0] == key:
            return cached[1]
        found, hits = last_seen(entries, scans)
        self._met_cache = (key, found, hits)
        return found

    def _scan_hit_counts(self) -> dict[int, int]:
        """How many seats in each record were on the list, from the same pass as 最后遇到."""
        self._last_met_stamps()
        return self._met_cache[2]

    def _last_met_all(self) -> dict[int, str]:
        """The same, as 刚刚 / 3小时前, worked out now so it stays current."""
        return {index: _zh_ago(stamp) for index, stamp in self._last_met_stamps().items()}

    def _show_list(self) -> None:
        # First, since a tag that is gone also drops out of the filter.
        self._fill_tag_list()
        rows = self._ordered_entries()
        met = self._last_met_all()
        table = self.blacklist_table
        bar = table.verticalScrollBar()
        position = bar.value()
        font = chinese_font(BODY_PT)
        ink = QColor(THEME["text"])
        table.setUpdatesEnabled(False)
        table.setRowCount(len(rows))
        for row, (index, entry) in enumerate(rows):
            shown = masked_name(entry.name) if self._names_hidden() else entry.name
            table.setItem(row, 0, self._list_cell(shown, index, font, ink))
            tags = tag_text(entry)
            tags_item = self._list_cell(tags, None, font, ink)
            tags_item.setToolTip(tags)
            # The table paints these as pills; a widget per row made a long list slow.
            tags_item.setData(Qt.UserRole + 3, tuple(entry.tags))
            table.setItem(row, 1, tags_item)
            detail = " ".join(entry.reason.split())
            table.setItem(row, 2, self._list_cell(detail, None, font, ink))
            # Never met: a dash, in gray, rather than an empty cell that looks unfinished.
            seen = met.get(index, "")
            table.setItem(row, 3, self._list_cell(seen or NEVER_MET, None, font, ink if seen else QColor(THEME["muted"])))
            table.setRowHeight(row, ROW_H)
        table.setUpdatesEnabled(True)
        self._blacklist_hover = -1
        self.blacklist_table.setCurrentCell(-1, -1)
        bar.setValue(position)
        self._hide_detail_tip()
        self._refresh_blacklist_tab()
        count = len(self.store.entries)
        self.list_search.setVisible(count > 0 or bool(self._search_text()))
        self.more_button.setVisible(count > 0)
        for button in self.toolbar_buttons:
            button.setVisible(count > 0)
        if count and rows:
            self.list_empty.hide()
            self.blacklist_table.setVisible(True)
        elif count:
            self.list_empty.set_icon("search")
            query = self._search_text()
            self.list_empty.set_text(f"没有找到「{query}」" if query else f"没有使用「{self._tag_filter}」标签的玩家")
            self.empty_add_button.hide()
            self.empty_batch_button.hide()
            self.list_empty.show()
            self.blacklist_table.setVisible(False)
        else:
            self.list_empty.set_icon("users")
            self.list_empty.set_text("黑名单还是空的")
            self.empty_add_button.show()
            self.empty_batch_button.show()
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

    def _names_hidden(self) -> bool:
        """黑名单's names masked: by the eye, or always while 直播模式 is on, the page may be on stream."""
        return self.store.names_hidden or bool(self.store.stream_mode)

    def _toggle_name_hiding(self, hidden: bool) -> None:
        self.store.names_hidden = bool(hidden)
        self.store.save_settings()
        self._sync_name_hiding()

    def _sync_name_hiding(self) -> None:
        header = self.blacklist_table.horizontalHeader()
        if isinstance(header, _ColumnHeader):
            header.names_hidden = self._names_hidden()
            header.locked = bool(self.store.stream_mode)
            header.viewport().update()
        self._show_list()
        # 记录 masks its 黑名单 seats in 直播模式 too.
        if hasattr(self, "history_table"):
            self._show_history_scan(self._selected_scan())

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
        if hasattr(self, "likes_tab"):
            self._set_tab_count(self.likes_tab, len(self.store.likes))

    def _likes_changed(self) -> None:
        """心动 changed, and a move may have taken a name off 黑名单: redraw both and the record."""
        self._refresh_tag_views()

    def _open_record_menu(self) -> None:
        button = self.record_more
        self.record_menu.popup(button.mapToGlobal(button.rect().bottomRight()) - QPoint(self.record_menu.sizeHint().width(), -4))

    def _open_more_menu(self) -> None:
        button = self.more_button
        self.more_menu.popup(button.mapToGlobal(button.rect().bottomRight()) - QPoint(self.more_menu.sizeHint().width(), -4))

    def _clear_list(self) -> None:
        count = len(self.store.entries)
        if not count:
            return
        if ConfirmDialog.ask(self, "清空黑名单", f"将删除 {count} 条黑名单，确定清空吗？", "清空", danger=True):
            self._confirm_clear_list()

    def _confirm_clear_list(self) -> None:
        before = self.store.snapshot_entries()
        self.store.clear_entries()
        self._list_changed()
        self._say(f"已清空 {len(before)} 人", undo=lambda: self._put_back(before))

    def _list_changed(self) -> None:
        self._show_list()
        self._show_history_scan(self._selected_scan())
        self.likes_page.refresh()

    def _put_back(self, entries: list[Entry], likes: list[Entry] | None = None) -> None:
        self.store.restore_entries(entries)
        if likes is not None:
            self.store.restore_likes(likes)
            self.likes_page.refresh()
        self._refresh_tag_views()
        self._say("已撤销")

    def _take_from_likes(self, name: str) -> bool:
        """A name on 心动 moves to 黑名单 only when asked. True when it is not there, or was moved."""
        index = self.store.like_index(name)
        if index < 0:
            return True
        listed = self.store.likes[index].name
        if not ConfirmDialog.ask(self, "移到黑名单", f"「{listed}」在心动列表中，要移到黑名单吗？", "移到黑名单"):
            return False
        self.store.remove_like(index)
        self.likes_page.refresh()
        return True

    def _say(self, text: str, undo=None) -> None:  # noqa: ANN001
        """Report a change in a toast. 撤销 stays for eight seconds."""
        if undo is None:
            self.toast.show_message(text, ms=4000)
        else:
            self.toast.show_message(text, "撤销", undo, ms=8000)

    def _list_key(self, watched, event) -> bool:  # noqa: ANN001
        """Enter opens what is current, Delete removes it, and Space or Enter folds a day."""
        key = event.key()
        enter = key in (Qt.Key_Return, Qt.Key_Enter)
        if watched is getattr(self, "blacklist_table", None):
            item = self.blacklist_table.item(self.blacklist_table.currentRow(), 0)
            if item is None or item.data(Qt.UserRole) is None:
                return False
            if enter:
                self._edit_entry(int(item.data(Qt.UserRole)))
                return True
            if key == Qt.Key_Delete:
                self._delete_entry(int(item.data(Qt.UserRole)))
                return True
        elif watched is getattr(self, "tag_list", None):
            tag = self._tag_at(self.tag_list.currentRow())
            if not tag:
                return False
            if enter or key == Qt.Key_F2:
                self._edit_tag(tag)
                return True
            if key == Qt.Key_Delete:
                self._remove_tag(tag)
                return True
        elif watched is getattr(self, "history_table", None):
            row, column = self.history_table.currentRow(), self.history_table.currentColumn()
            if enter and row >= 0 and column >= 0:
                self._on_history_cell(row, column)
                return True
        elif watched is getattr(self, "history_list", None):
            item = self.history_list.currentItem()
            if item is None:
                return False
            kind = item.data(Qt.UserRole + 1)
            if kind == "day" and (enter or key == Qt.Key_Space):
                self._on_history_clicked(item)
                return True
            if kind == "time" and key == Qt.Key_Delete:
                self._delete_scan(int(item.data(Qt.UserRole)))
                return True
        return False

    def _on_seat_current(self, row: int, column: int, *_previous) -> None:
        # Moving through the seats with the arrow keys lights them up the way the pointer does.
        if self.history_table.hasFocus() and row >= 0 and column >= 0:
            self._hover_history_cell(row, column)

    def _add_shortcuts(self) -> None:
        from PySide6.QtGui import QKeySequence, QShortcut

        self.shortcuts: dict[str, QShortcut] = {}
        for keys, slot in (
            ("Ctrl+1", self._show_records_page),
            ("Ctrl+2", self._show_blacklist_page),
            ("Ctrl+3", self._show_likes_page),
            ("Ctrl+4", self._show_settings_page),
            ("Ctrl+F", self._focus_search),
            ("Ctrl+N", self._add_by_dialog),
            ("Ctrl+I", self._add_many_by_dialog),
        ):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(slot)
            self.shortcuts[keys] = shortcut

    def _show_records_page(self) -> None:
        self.tabs.setCurrentIndex(self.history_tab)

    def _show_blacklist_page(self) -> None:
        self.tabs.setCurrentIndex(self.blacklist_tab)

    def _show_likes_page(self) -> None:
        self.tabs.setCurrentIndex(self.likes_tab)

    def _show_settings_page(self) -> None:
        self.tabs.setCurrentIndex(self.settings_tab)

    def _focus_search(self) -> None:
        self._show_blacklist_page()
        if not self.list_search.isHidden():
            self.list_search.setFocus(Qt.ShortcutFocusReason)
            self.list_search.selectAll()

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
        return self._menu((("编辑", ("edit", index)), ("复制名字", ("copy_entry", index)), None, ("删除", ("delete", index))))

    def _menu(self, items) -> QMenu:  # noqa: ANN001
        menu = QMenu(self)
        for item in items:
            if item is None:
                menu.addSeparator()
                continue
            text, data = item
            action = menu.addAction(text)
            action.setData(data)
            _mark_menu_item(action)
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
        elif kind == "like_seat":
            self.likes_page.add_one(split_ellipsis(args[0])[0] or args[0])
        elif kind == "copy_text":
            self._copy_text(*args)
        elif kind == "tag_edit":
            self._edit_tag(*args)
        elif kind == "tag_delete":
            self._remove_tag(*args)

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
        self._say(f"已复制 {count} 人")

    def _add_by_dialog(self) -> None:
        picked = (self._tag_filter,) if self._tag_filter else ()
        dialog = AddNameDialog(tags=picked, catalog=self.store.tag_catalog(), parent=self, taken=self._taken_names())
        if dialog.exec() != QDialog.Accepted or dialog.deleted:
            return
        before, likes = self.store.snapshot_entries(), self.store.snapshot_likes()
        if not self._take_from_likes(dialog.name):
            return
        entry = self.store.add(dialog.name, dialog.detail, tags=dialog.tags)
        if entry is None:
            return
        self._list_changed()
        self._say(f"已添加「{entry.name}」", undo=lambda: self._put_back(before, likes))

    def _add_many_by_dialog(self) -> None:
        """Paste, check the preview, then, when several 原因 share a phrase, confirm the 标签 to add."""
        dialog = BatchAddDialog(self.store.tag_catalog(), self.store.entries, parent=self, elsewhere=self.store.likes)
        while True:
            if dialog.exec() != QDialog.Accepted or not dialog.chosen:
                return
            rows = dialog.chosen
            suggestions = suggest_tags(rows, self.store.tag_catalog())
            if not suggestions:
                break
            confirm = TagSuggestDialog(suggestions, rows, parent=self)
            if confirm.exec() == QDialog.Accepted:
                rows = with_tags(rows, confirm.picked())
                break
            if not confirm.went_back:
                return
        before = self.store.snapshot_entries()
        added, merged = self.store.import_rows(rows)
        if not added and not merged:
            self._say("都已经在黑名单里了")
            return
        # A shared list may bring tags this list has not seen. They now show beside the list.
        self._refresh_tag_views()
        parts = [f"已添加 {added} 人"] if added else []
        if merged:
            parts.append(f"合并 {merged} 人")
        self._say("，".join(parts), undo=lambda: self._put_back(before))

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
            title="编辑",
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
        if hasattr(self, "likes_page"):
            self.likes_page.refresh()
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
        self.record_column.setVisible(count > 0)
        self.history_table.setVisible(count > 0)
        self.history_empty.setVisible(count == 0)
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
        hits = self._scan_hit_counts().get(index, 0)
        if hits:
            # A record with someone on the list can be found without opening each one.
            flag = QLabel()
            flag.setObjectName("recordHits")
            flag.setPixmap(line_pixmap("warning", 14, THEME["red"]))
            flag.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            flag.setStyleSheet("background: transparent;")
            count = QLabel(str(hits))
            count.setObjectName("recordHitCount")
            count.setFont(chinese_font(SMALL_PT))
            count.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            count.setStyleSheet(f'color: {THEME["red"]}; background: transparent;')
            line.addStretch(1)
            line.addWidget(flag, 0, Qt.AlignVCenter)
            line.addSpacing(3)
            line.addWidget(count, 0, Qt.AlignVCenter)
            line.addSpacing(6)
            wrap.setToolTip(f"{hits} 名黑名单玩家")
        else:
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
        if count and ConfirmDialog.ask(self, "清空记录", f"将删除 {count} 条记录，确定清空吗？", "清空", danger=True):
            self._clear_history()

    def _clear_history(self) -> None:
        self.store.clear_scans()
        self._reload_history()

    def _day_and_clock(self, stamp: str) -> tuple[str, str]:
        try:
            moment = datetime.fromisoformat(stamp)
        except ValueError:
            return "", stamp
        local = _local_moment(stamp) or moment
        today = datetime.now().astimezone().date()
        days = (today - local.date()).days
        if days == 0:
            day = "今天"
        elif days == 1:
            day = "昨天"
        else:
            day = f"{moment.month}月{moment.day}日"
        return day, _zh_clock(moment)

    def _show_history_scan(self, row: int) -> None:
        self._history_hover = (-1, -1)
        self._mark_selected_record()
        self.history_table.setRowCount(0)
        if row < 0 or row >= len(self.store.scans):
            self.record_summary.setText("")
            return
        names = self.store.scans[row].get("names", [])
        self.history_table.setRowCount((len(names) + 1) // 2)
        kinds = []
        for index, seat in enumerate(names):
            kinds.append(self._set_history_seat(index // 2, index % 2, seat))
            self.history_table.setRowHeight(index // 2, ROW_H + 4)
        self.record_summary.setText(_lobby_summary(kinds))
        self._fit_record_card()

    def _fit_record_card(self) -> None:
        """The table is exactly as tall as its rows, so the card ends with the last seat."""
        table = self.history_table
        rows = sum(table.rowHeight(row) for row in range(table.rowCount()))
        table.setFixedHeight(max(ROW_H + 4, rows) + 2 * table.frameWidth() + 6)

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

    def _history_like(self, shown: str) -> Entry | None:
        found = match_label(NameLabel(raw=shown, visible=shown, truncated=False), list(self.store.likes))
        return found[0].entry if found else None

    def _set_history_seat(self, row: int, column: int, seat: dict) -> str:
        """Fill one seat. Returns hit, like, unclear or "" for the lobby summary."""
        unclear = bool(seat.get("unclear")) or not str(seat.get("name") or "")
        shown = "未识别" if unclear else str(seat.get("name"))
        visible = "未识别" if unclear else shown
        match = None if unclear else self._history_match(shown)
        stored = match.entry.name if match is not None else ""
        like = None if unclear or match is not None else self._history_like(shown)
        mine = not unclear and match is None and like is None and self._is_my_name(shown)
        if mine:
            action = "我"
        elif unclear or match is not None or like is not None:
            action = ""
        else:
            action = "添加"
        # The name as read off the screen. A match shows the list's spelling beside it,
        # so a cut-off or near name that matched can be told apart from an exact one.
        title = shown
        if not unclear:
            title = split_ellipsis(title)[0] or title
        listed = stored if match is not None and fold(stored) != fold(title) else ""
        # A name the game cut short shows once, in full as the list has it: 破轮蜡像金婚99.
        # Only a list name that differs in more than the cut keeps its 名单 note beside the name.
        tail = listed_tail(title, listed) if listed else None
        shown_name = listed if tail else title
        if like is not None:
            # 心动 shows the 昵称, or the full name as the list has it.
            shown_name = like.shown()
        # 直播模式: this page may be on stream, so a 黑名单 name is masked like on the 黑名单 page.
        hide = match is not None and bool(self.store.stream_mode)
        if hide:
            shown_name, listed, tail, title = masked_name(shown_name), "", None, masked_name(title)
        # Lobby order is not the player's number. Show the name until a later stage.
        label = title
        name_item = QTableWidgetItem(label)
        name_item.setData(Qt.UserRole, "" if unclear else title)
        name_item.setData(Qt.UserRole + 1, action)
        name_item.setData(Qt.UserRole + 2, stored)
        name_item.setData(Qt.UserRole + 3, like.name if like is not None else "")
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
        elif like is not None:
            tone = THEME["rose"]
            wash = THEME["rose_wash"]
            hover = THEME["rose_hover"]
        elif self._is_my_name(shown):
            tone = THEME["green"]
            wash = THEME["green_wash"]
            hover = ""
        else:
            tone = THEME["text"]
            wash = ""
            hover = THEME["gray_wash"]
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
        if like is not None:
            heart = QLabel()
            heart.setObjectName("seatHeart")
            heart.setPixmap(line_pixmap("heart", 16, THEME["rose"]))
            heart.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            heart.setStyleSheet("background: transparent;")
            line.addWidget(heart)
        name_label = _ElidedLabel(visible if unclear else shown_name)
        name_label.setObjectName("rowName")
        name_label.setFont(name_font)
        name_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        name_color = tone
        if unclear:
            name_label.setFont(record_font())
        name_label.setStyleSheet(
            f'color: {name_color}; background: transparent; font-family: "{chinese_family()}"; font-size: {BODY_PT}pt;'
        )
        line.addWidget(name_label, 1)
        if tail and not hide:
            name_item.setToolTip(f"读到「{title}」，是黑名单里的「{listed}」")
        if like is not None:
            name_item.setToolTip(f"读到「{title}」，是心动里的「{like.name}」")
        if not unclear and not name_item.toolTip():
            name_item.setToolTip(label)
        if listed and tail is None:
            listed_label = QLabel(f"黑名单：{listed}")
            listed_label.setObjectName("rowListed")
            listed_label.setFont(chinese_font(SMALL_PT))
            listed_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            listed_label.setStyleSheet(
                f'color: {THEME["red"]}; background: transparent; font-family: "{chinese_family()}";'
            )
            name_item.setToolTip(f"读到「{title}」，是黑名单里的「{listed}」")
            line.addWidget(listed_label, 0, Qt.AlignVCenter)
        if action:
            action_label = QLabel(action)
            action_label.setObjectName("rowAction")
            action_label.setFont(chinese_font())
            action_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            action_label.setFont(chinese_font(SMALL_PT))
            if action == "我":
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
        return "unclear" if unclear else "hit" if match is not None else "like" if like is not None else ""

    def _history_wrap_style(self, wash: str = "") -> str:
        """A seat: white with a thin gray outline, or filled when it means something (or is under the pointer)."""
        line = wash or seat_line()
        return f"QFrame#seat {{ background: {wash or THEME['surface']}; border: 1px solid {line}; border-radius: 6px; }}"

    def _history_cell_is_mine(self, row: int, column: int) -> bool:
        item = self.history_table.item(row, column)
        return item is not None and str(item.data(Qt.UserRole + 1) or "") == "我"

    def _history_cell_is_unclear(self, row: int, column: int) -> bool:
        item = self.history_table.item(row, column)
        return item is not None and item.text() == "未识别"

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
        if hot and str(item.data(Qt.UserRole + 1) or "") == "我":
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
        if item.data(Qt.UserRole + 2) or item.data(Qt.UserRole + 3):
            items.append(("编辑", ("seat", row, column)))
        elif action == "添加":
            items.append(("加入黑名单", ("seat", row, column)))
            items.append(("加入心动列表", ("like_seat", shown)))
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
        if not shown or str(item.data(Qt.UserRole + 1) or "") == "我":
            return
        stored = str(item.data(Qt.UserRole + 2) or "")
        if stored:
            for index, entry in enumerate(self.store.entries):
                if entry.name == stored:
                    self._edit_entry(index)
                    return
            return
        liked = str(item.data(Qt.UserRole + 3) or "")
        if liked:
            self.likes_page.edit(self.store.like_index(liked))
            return
        dialog = AddNameDialog(shown, title="添加", catalog=self.store.tag_catalog(), parent=self, taken=self._taken_names())
        if dialog.exec() != QDialog.Accepted or dialog.deleted:
            return
        if not self._take_from_likes(dialog.name):
            return
        if self.store.add(dialog.name, dialog.detail, tags=dialog.tags) is None:
            return
        self._show_list()
        self._show_history_scan(self._selected_scan())

    def _toggle_auto(self, checked: bool) -> None:
        if bool(checked) != self.store.auto_capture:
            log.info("方式: %s.", "自动检查" if checked else "手动检查")
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

    def _consent(self, mode: str) -> bool:
        """The first time 完整模式 is picked, say what it does and ask."""
        if mode in self.store.consented:
            return True
        title, body, confirm, cancel = CONSENT[mode]
        if not ConfirmDialog.ask(self, title, body, confirm, cancel=cancel):
            log.info("Declined %s.", "完整模式" if mode == "full" else "自动检查")
            return False
        log.info("Agreed to %s.", "完整模式" if mode == "full" else "自动检查")
        self.store.consented.append(mode)
        self.store.save_settings()
        return True

    def _on_auto_mode(self, key: str) -> None:
        if key == "auto" and self.store.safe_mode:
            self._sync_auto_controls()
            return
        self._toggle_auto(key == "auto")

    def _on_display_mode(self, key: str) -> None:
        if key == "full" and not self._consent("full"):
            self.display_mode.set_current("safe" if self.store.safe_mode else "full")
            return
        self._set_safe_mode(key == "safe")

    def _set_safe_mode(self, on: bool) -> None:
        if bool(on) != self.store.safe_mode:
            log.info("显示: %s.", "安全模式" if on else "完整模式")
        self.store.safe_mode = bool(on)
        self.store.save_settings()
        if self.store.safe_mode and self.store.auto_capture:
            # 安全模式 checks on the hotkey only.
            self._toggle_auto(False)
        self._sync_auto_controls()
        self.display_mode.set_current("safe" if self.store.safe_mode else "full")
        if self.store.safe_mode:
            # Off the game at once: nothing left drawn over it.
            self._hide_panel_after_title()
        else:
            self.notice.hide()
        self._sync_overlay_target()
        self._sync_status_tip()

    def _overlay_target(self) -> str:
        """Where the marks go: "screen" over the game (完整模式), "stream" only into 直播模式's
        window (安全模式 with 直播模式), or "" nowhere (安全模式)."""
        if not self.store.safe_mode:
            return "screen"
        return "stream" if self.store.stream_mode else ""

    def _sync_overlay_target(self) -> None:
        """Marks meant only for the stream are made but never put on the screen."""
        hidden = self._overlay_target() == "stream"
        marks = (self.panel, self.hit_card, self.like_card, self.clear_mark, self.love, self.alert)
        if self._overlay_target() == "" or any(mark.testAttribute(Qt.WA_DontShowOnScreen) != hidden for mark in marks):
            # Changed only while nothing shows: a window already on screen would stay there.
            self._hide_panel_after_title()
            for mark in marks:
                mark.setAttribute(Qt.WA_DontShowOnScreen, hidden)

    def _show_love_effects(self) -> None:
        LoveEffectsDialog(self.store, self.music, self).exec()
        self.love.choice = self.store.love_scene

    def _set_stream_mode(self, on: bool | str) -> None:
        if bool(on) != bool(self.store.stream_mode):
            log.info("直播模式 %s.", "on" if on else "off")
        self.store.stream_mode = "on" if on else ""
        self.store.save_settings()
        self.stream.enable(self.store.stream_mode)
        self._sync_switch(self.stream_switch, bool(self.store.stream_mode))
        self._sync_overlay_target()
        self._sync_name_hiding()

    def _sync_auto_controls(self) -> None:
        """The 方式 choice and the header's pill both follow the saved mode. In 安全模式 it is
        手动检查, and 自动检查 cannot be picked."""
        self.auto_mode.set_current("auto" if self.store.auto_capture else "manual")
        self.auto_on.setEnabled(not self.store.safe_mode)
        self._sync_status_tip()

    def _begin_hotkey(self) -> None:
        self._set_settings_note("")
        self.hotkey.clear()
        self.hotkey_edit.clear()
        self.hotkey_edit.setPlaceholderText("请按下快捷键")

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
        if spec is not None and self.hotkey.active != spec.display and not self.hotkey.apply(spec):
            log.warning("Hotkey %s did not register: another program holds it, or this PC has none.", spec.display)

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
            self._set_settings_note("用字母、数字或 F1–F12")
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
            self._set_settings_note("这个键用不了，换一个")
            return
        registered = self.hotkey.apply(spec)
        log.info("Hotkey set to %s%s.", spec.display, "" if registered else ", which did not register")
        self.store.hotkey = spec.display
        self.store.save_settings()
        self.hotkey_edit.setText(spec.display)
        if registered:
            self._set_settings_note("")
        elif sys.platform != "win32":
            self._set_settings_note("这台电脑用不了快捷键")
        else:
            self.store.hotkey = ""
            self.store.save_settings()
            self.hotkey_edit.clear()
            self._set_settings_note("这个键被别的程序占了，换一个")
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
        log.info("Hotkey: checking.")
        self._pressed_at = time.perf_counter()
        self._cpu = CpuWindow()
        self._release_foreground = True
        self._rescan_active = False
        lock_foreground(True)
        if self._start(self._capture_job, live=True):
            self._manual_check = True
        else:
            # Still busy with the last check or the model load: this press does nothing.
            log.info("Hotkey: busy, the press was ignored.")
            self._pressed_at = None

    def start_warmup(self) -> None:
        """Load the OCR models now, so the first lobby check does not wait for them."""
        if not self.worker.request(get_engine().warmup, kind="warmup"):
            return
        self._warm_state = "loading"
        self._warm_started = time.perf_counter()
        self._set_result("正在准备识别", "idle", "loading")

    def show_first_run_guide(self) -> None:
        """Once per PC: 使用声明 to agree to, then, on a new PC, the welcome guide."""
        if not self.store.disclaimer_accepted:
            # Over the window without a nested event loop, like the guide.
            notice = DisclaimerDialog(self)
            notice.setAttribute(Qt.WA_DeleteOnClose, True)
            notice.accepted.connect(self._accept_disclaimer)
            notice.rejected.connect(self._decline_disclaimer)
            notice.open()
            return
        if not self.store.first_run:
            return
        self.store.first_run = False
        self.store.save_settings()
        # Over the window without a nested event loop: this runs from the setup screen's fade.
        guide = GuideDialog(self, self._how_to_check())
        guide.setAttribute(Qt.WA_DeleteOnClose, True)
        guide.open()

    def _accept_disclaimer(self) -> None:
        log.info("使用声明 agreed to.")
        self.store.disclaimer_accepted = True
        self.store.save_settings()
        self.show_first_run_guide()

    def _decline_disclaimer(self) -> None:
        log.info("使用声明 declined: closing.")
        self.quit_app()

    def _show_disclaimer(self) -> None:
        DisclaimerDialog(self, asking=False).exec()

    def _export_logs(self) -> None:
        """日志: the computer, the last 环境测试 and the logs in one text file on the Desktop, shown in Explorer."""
        try:
            summary = summary_text(self.store, inference_device())
            report = self._flow_test.text() if self._flow_test is not None else ""
            target = export_logs(self.store.root, summary, report=report)
        except OSError as exc:
            log.warning("Logs could not be exported: %s", exc)
            self._say("桌面存不了文件，日志没导出")
            return
        log.info("Logs exported.")
        self._say(f"已存到桌面：{target.name}")
        if sys.platform == "win32":
            import subprocess

            subprocess.Popen(["explorer", "/select,", str(target)])

    def _on_stream_switch(self, on: bool) -> None:
        """The switch: the first time it is turned on, how to set it up comes with it."""
        self._set_stream_mode(on)
        if on and not self.store.stream_guided:
            self.store.stream_guided = True
            self.store.save_settings()
            self._show_stream_guide()

    def _show_stream_guide(self) -> None:
        StreamGuideDialog(self).exec()

    def _show_display_guide(self) -> None:
        DisplayGuideDialog(self).exec()

    def begin(self) -> None:
        """After the window opens: the environment check when it is due, then the first-run guide."""
        if not self.start_environment_check():
            self.show_first_run_guide()

    # --- 环境测试: 屏幕截图, 识别功能, 识别测试, then 自动检查 and 手动检查 timed ---------------

    def start_environment_check(self, force: bool = False) -> bool:
        """Run the test on the first open and after an update, or from 设置 › 环境测试 (force), which
        ends in a report of the timings. False when it is not due."""
        if not force and self.store.env_checked == __version__:
            return False
        self._env_report = force
        if force:
            log.info("环境测试 started from 设置.")
        if self.setup is None:
            from blacklist_detect.ui_setup import SetupCheck

            self.setup = SetupCheck(self.centralWidget())
            self.setup.retry.connect(self._run_environment_check)
            self.setup.dismissed.connect(self._after_environment_check)
        self._run_environment_check()
        return True

    def _run_environment_check(self) -> None:
        self.setup.start()
        # The lobby watch waits, so the check has the reader to itself.
        self._glance_pause_until = time.perf_counter() + 3600
        self.setup.step(0, "run")
        QTimer.singleShot(200, self._env_capture)

    def _env_capture(self) -> None:
        try:
            capture_top_band()
        except Exception as exc:  # noqa: BLE001 - every way the screen copy fails is shown the same way
            log.warning("Environment check: screen copy failed: %s", exc)
            self._env_fail(0, _plain_error(exc, "截屏失败，再试一次"))
            return
        self.setup.step(0, "ok")
        self.setup.step(1, "run")
        if self._warm_state == "ready":
            self._env_models_ready()
        elif self._warm_state == "failed":
            self._env_fail(1, self._warm_error)
        else:
            self._env_waiting = True
            if self._warm_state != "loading":
                self._env_load_models(0)

    def _env_load_models(self, tries: int) -> None:
        self.start_warmup()
        if self._warm_state == "loading":
            return
        if tries < 300:
            QTimer.singleShot(100, lambda: self._env_load_models(tries + 1))
            return
        self._env_fail(1, "正在识别，稍等一下")

    def _env_models_ready(self) -> None:
        self._env_waiting = False
        self.setup.step(1, "ok")
        self.setup.step(2, "run")
        self._env_sample(0)

    def _env_sample(self, tries: int) -> None:
        path = str(SAMPLE_LOBBY)
        if self.worker.request(lambda: check_image(path, []), kind="envcheck"):
            return
        if tries < 300:
            QTimer.singleShot(100, lambda: self._env_sample(tries + 1))
            return
        self._env_fail(2, "正在识别，稍等一下")

    def _on_env_sample(self, status: str, value) -> None:  # noqa: ANN001
        if status != "ok":
            log.warning("Environment check: sample lobby failed: %s", value)
            self._env_fail(2, _plain_error(value, "识别失败，再试一次"))
            return
        # The sample lobby's names are known: each one read is checked against them.
        seats = sorted(value.names, key=lambda slot: slot.index)
        right = sum(1 for slot, name in zip(seats, SAMPLE_NAMES, strict=False) if not slot.unclear and slot.visible == name)
        if not value.header_found or right < 10:
            log.warning("Environment check: lobby %s, %d of 12 names read right", value.header_found, right)
            self._env_fail(2, f"示例图只读对 {right} 个名字，可能不准")
            return
        log.info("Environment check passed: %d of 12 names read right", right)
        self.setup.step(2, "ok", f"{right}/12")
        self.store.env_checked = __version__
        self.store.save_settings()
        # Then the two ways a check starts, timed on the sample the size of this screen.
        self.setup.step(3, "run")
        self._env_flow(0)

    def _env_flow(self, tries: int) -> None:
        sample = SAMPLE_LOBBY
        if self.worker.request(lambda: run_flow_test(sample), kind="flowtest"):
            return
        if tries < 300:
            QTimer.singleShot(100, lambda: self._env_flow(tries + 1))
            return
        self._env_fail(3, "正在识别，稍等一下")

    def _on_flow_test(self, status: str, value) -> None:  # noqa: ANN001
        test = value if status == "ok" else FlowTest(error=_plain_error(value, "识别失败，再试一次"))
        self._flow_test = test
        log.info("%s", test.text())
        if test.error:
            self._env_fail(3, test.error)
            return
        tone = {"正常": "ok", "有点慢": "ok", "很慢": "ok"}[test.verdict()]
        self.setup.step(3, tone, f"{test.auto_total():.1f} 秒")
        self.setup.step(4, tone, f"{test.hotkey_total():.1f} 秒")
        self._glance_pause_until = 0.0
        if self._env_report:
            self.setup.succeed(fade=False)
            FlowReportDialog(test, self._export_logs, self).open()
            self.setup._dismiss()
        else:
            self.setup.succeed()

    def _env_fail(self, index: int, message: str) -> None:
        log.warning("Environment check failed at %s: %s", index, message)
        self._env_waiting = False
        self._glance_pause_until = 0.0
        self.setup.fail(index, message)

    def _after_environment_check(self) -> None:
        self.show_first_run_guide()

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
        self._picture_dialog = PictureResultDialog(title, error="正在识别，稍等一下", parent=self)
        self._picture_dialog.open()

    def _sync_picture_buttons(self) -> None:
        busy = bool(self._picture_pending)
        for button in (self.picture_button, self.picture_empty_button):
            button.setEnabled(not busy)
            button.setText("正在识别" if busy else "用截图检查")

    def _on_picture(self, status: str, value) -> None:  # noqa: ANN001
        title = self._picture_pending or "截图检查"
        self._picture_pending = ""
        self._sync_picture_buttons()
        if status != "ok":
            log.warning("Picture check failed: %s", value)
            error = _plain_error(value, "这张图打不开")
            self._picture_dialog = PictureResultDialog(title, error=error, parent=self)
        else:
            log.info("Picture check: lobby %s, %d on the list", value.header_found, len(value.hits))
            self._picture_dialog = PictureResultDialog(
                title, result=value, parent=self, likes=self.store.likes, hide_hits=bool(self.store.stream_mode),
                me=self.store.player_name,
            )
        self._picture_dialog.open()

    def _set_autostart(self, enabled: bool) -> None:
        if not autostart.set_enabled(enabled):
            log.warning("Could not change start with Windows to %s", enabled)
            self._say("开机启动没设上")
        self._sync_switch(self.autostart_switch, autostart.is_enabled())

    def _on_close_mode(self, key: str) -> None:
        self._set_close_to_tray(key == "tray")

    def _set_close_to_tray(self, enabled: bool) -> None:
        self.store.close_to_tray = bool(enabled)
        self.store.save_settings()

    @staticmethod
    def _sync_switch(switch: Switch, on: bool) -> None:
        if switch.isChecked() != on:
            switch.blockSignals(True)
            switch.setChecked(on)
            switch.blockSignals(False)

    def report_uncaught(self, text: str) -> None:
        """Any thread may call this. The window is updated on its own thread."""
        self.uncaught.emit(text)

    def _show_uncaught(self, text: str) -> None:
        # The exception and its trace are already in the log; the user sees only that something failed.
        del text
        self._set_result("出了点问题", "hit", "error")

    def _report_problem(self, problem) -> None:  # noqa: ANN001
        """Say what went wrong in the header and the tray. A check that silently stops is worse than an error."""
        if isinstance(problem, OcrUnavailable):
            label = "识别还没准备好"
        elif isinstance(problem, CaptureUnavailable):
            label = "读不到屏幕"
        else:
            label = "检查失败"
        raw = str(problem).strip() or label
        detail = _plain_error(problem, "检查失败，等会儿再试")
        if raw != self._problem:
            trace = (type(problem), problem, problem.__traceback__) if isinstance(problem, BaseException) else None
            expected = isinstance(problem, (OcrUnavailable, CaptureUnavailable))
            log.warning("%s: %s", label, raw, exc_info=None if expected else trace)
        if self._status_kind != "error" or raw != self._problem:
            self._set_result(label, "hit", "error", tip=detail)
        self._problem = raw

    def _clear_problem(self) -> None:
        if not self._problem:
            return
        self._problem = ""
        log.info("Checks work again.")
        if self._status_kind == "error":
            self._sync_watch_idle()

    def _capture_job(self) -> CheckResult:
        started = time.perf_counter()
        pressed, last = self._pressed_at, self._last_ocr_at
        windows = window_order()
        frames = capture_displays()
        captured = time.perf_counter() - started
        result = check_frames(frames, list(self.store.entries), on_lobby=self.worker.placed.emit)
        result.timings["capture"] = captured
        result.windows = windows
        result.timings["screens"] = len(frames)
        if pressed is not None:
            # From the hotkey to this job starting: the app was busy, or the computer was.
            result.timings["wait"] = started - pressed
        if last is not None:
            result.timings["idle"] = started - last
        return result

    def _timing_note(self, result: CheckResult) -> str:
        """Where a check's time went, and how long since the hotkey, for the log."""
        steps = result.timings
        note = ", ".join(f"{name} {steps[name]:.2f} s" for name in ("capture", "find", "read") if name in steps)
        if steps.get("screens", 1) != 1:
            note += f", {int(steps['screens'])} screens"
        if self._pressed_at is not None:
            note += f"; {time.perf_counter() - self._pressed_at:.2f} s since the hotkey"
        if steps.get("wait", 0) >= 0.2:
            note += f", started {steps['wait']:.2f} s after it"
        if "idle" in steps and steps["idle"] >= 60:
            note += f"; recognition idle {steps['idle'] / 60:.0f} min before"
        extra = [part for part in ((self._cpu.stop() if self._cpu else ""), power_note()) if part]
        if extra:
            note += "; " + ", ".join(extra)
        return note

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
            self.panel.set_mode("checking", "检查中")
            self.hit_card.hide()
            self.like_card.hide()
            self.clear_mark.hide()
            self.love.stop()
            self.alert.leave()
        # Nothing is checked before 使用声明 is agreed to.
        if not self.store.disclaimer_accepted or not self.worker.request(fn):
            self._unlock_foreground()
            return False
        self._check_started = time.perf_counter()
        if live and self.store.safe_mode and not quiet:
            self._notice_screen = QApplication.screenAt(QCursor.pos())
            self.notice.show_checking(self._notice_screen)
        return True

    def _unlock_foreground(self) -> None:
        if not self._release_foreground:
            return
        self._release_foreground = False
        lock_foreground(False)

    def _on_worker(self, payload) -> None:
        job, status, value = payload
        self.worker.running_job = False
        if job != "glance":
            self._last_ocr_at = time.perf_counter()
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
        if job == "envcheck":
            self._on_env_sample(status, value)
            return
        if job == "flowtest":
            self._on_flow_test(status, value)
            return
        self._on_checked(status, value)

    def _on_warmed(self, status: str, value) -> None:
        self._warm_state = "ready" if status == "ok" else "failed"
        self._warm_error = "" if status == "ok" else _plain_error(value, "识别还没准备好，稍等一下")
        if self._env_waiting:
            if status == "ok":
                self._env_models_ready()
            else:
                self._env_fail(1, self._warm_error)
        if status != "ok":
            self._report_problem(value)
            return
        if self._warm_started is not None:
            log.info("OCR ready in %.1f s on %s", time.perf_counter() - self._warm_started, inference_device())
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
        manual = self._manual_check
        elapsed = None
        if self._check_started is not None:
            elapsed = time.perf_counter() - self._check_started
            self._check_started = None
        if status == "err":
            if not rescan and self._live_check and self._rescan_now():
                return
            self._manual_check = False
            self._pressed_at = None
            self._report_problem(value)
            if self.store.auto_capture:
                self.watch.retry_after(time.perf_counter())
            self._hide_panel_after_title()
            if self.store.safe_mode and self._live_check and manual:
                self.notice.show_error(_plain_error(value, "等会儿再试"), self._notice_screen)
            elif self.notice.kind == "checking":
                self.notice.hide()
            return
        result: CheckResult = value
        if not result.header_found:
            if not rescan and self._live_check and self._rescan_now():
                return
            self._manual_check = False
            log.info("No lobby on screen (%s): %s", self._timing_note(result), result.message)
            self._pressed_at = None
            if self.store.auto_capture:
                self.watch.retry_after(time.perf_counter())
            self._hide_panel_after_title()
            if self.store.safe_mode and self._live_check and manual:
                self.notice.show_missing(self._notice_screen)
            elif self.notice.kind == "checking":
                self.notice.hide()
            return
        self._manual_check = False
        self._clear_problem()
        log.info(
            "Checked the lobby: %d on the list, %d unclear, %.2f s (%s)%s",
            len(result.hits),
            sum(1 for slot in result.names if slot.unclear),
            elapsed or 0.0,
            self._timing_note(result),
            ", second look" if rescan else "",
        )
        self._pressed_at = None
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
        self.like_card.hide()
        self.clear_mark.hide()
        self.love.stop()
        self._love_played = False
        self.alert.leave()
        if not self.store.auto_capture:
            self._watch_timer.stop()

    def _on_lobby_placed(self, box) -> None:
        if self._closing or not self._live_check or not self._overlay_target():
            return
        # A finished cover stays put. A second pass must not turn it yellow again.
        if self.panel.isVisible() and self.panel.mode in ("clear", "liked", "hit", "both"):
            return
        self._open_panel("checking", "检查中", box)
        self.hit_card.hide()
        self.like_card.hide()
        self.clear_mark.hide()
        self.alert.leave()

    def _show_panel(self, result: CheckResult) -> None:
        if not self._live_check or not result.header_found:
            self._hide_panel_after_title()
            return
        hits = self._hits_in(result)
        likes = self._likes_in(result)
        if not hits:
            # Never with a 黑名单 player: the warning is the news then, not the music.
            self.music.lobby([like.name for like in likes], self.store.love_music)
        if self.store.safe_mode:
            self._show_notice(result)
        elif exclusive_fullscreen():
            # 完整模式 over a game in exclusive full screen: Windows shows nothing over it but a
            # plain window, so the corner message comes too, as in 安全模式.
            log.info("The game is in exclusive full screen: the corner message is shown too.")
            self._show_notice(result)
        if not self._overlay_target():
            return
        if result.button_box is None:
            self._hide_panel_after_title()
            return
        self._game_box = result.button_box
        self._game_windows = result.windows
        self._frame_stream()
        if hits:
            self.clear_mark.hide()
            # A 黑名单 player is the news; the border would bury it.
            self.love.stop()
            # 心动 players too: the ring is rose on their side, and their card is on the left.
            self._open_panel("both" if likes else "hit", "", result.button_box)
            self._show_hit_card(hits)
            if self.hit_card.isVisible():
                self._show_like_card(likes)
                self._show_alert()
            return
        self.hit_card.hide()
        self.like_card.hide()
        self.alert.leave()
        text = "未发现黑名单"
        unclear = sum(1 for slot in result.names if slot.unclear)
        if unclear:
            text += f"\n{unclear} 人未识别"
        # 心动 players and no 黑名单: a rose ring, the heart badge, and their names on the left.
        self._open_panel("liked" if likes else "clear", text, result.button_box)
        self._show_clear_mark(heart=bool(likes))
        self._show_like_card(likes)
        if len(likes) >= 2 and not self._love_played:
            self._play_love()

    def _hits_in(self, result: CheckResult) -> list[Hit]:
        """黑名单 players in the lobby."""
        return list(result.hits)

    def _show_notice(self, result: CheckResult) -> None:
        """安全模式: who is in the lobby, in messages at the bottom right of the screen the game is on,
        above the taskbar: the corner of the screen, never the corner of a windowed game."""
        people: list[tuple[str, tuple[str, ...]]] = []
        for hit in self._hits_in(result):
            person = (hit.entry_name, tuple(hit.tags))
            if person not in people:
                people.append(person)
        likes = [like.shown() for like in self._likes_in(result)]
        unclear = sum(1 for slot in result.names if slot.unclear)
        screen = self._notice_screen
        if result.button_box is not None:
            origin_x, origin_y = virtual_origin()
            left, top, right, bottom = result.button_box
            x, y, _ratio = native_to_logical((left + right) / 2 + origin_x, (top + bottom) / 2 + origin_y)
            screen = QApplication.screenAt(QPoint(int(x), int(y))) or screen
        self.notice.show_result(people, likes, unclear, screen)

    def _show_alert(self) -> None:
        """The red glow over the game's screen, under the ring and the cards."""
        cover = self.panel.cover_geometry()
        screen = QApplication.screenAt(cover.center()) or QApplication.primaryScreen()
        if screen is None:
            return
        self.alert.show_on(self._game_area(screen))
        for mark in (self.panel, self.hit_card, self.like_card):
            if mark.isVisible():
                _pin_topmost(mark)

    def _play_love(self) -> None:
        """The 心动 scene over the game, parted around the button, the badge and the 心动 card."""
        cover = self.panel.cover_geometry()
        keep = cover
        for mark in (self.clear_mark, self.like_card):
            if mark.isVisible():
                keep = keep.united(mark.geometry())
        screen = QApplication.screenAt(cover.center()) or QApplication.primaryScreen()
        if screen is None:
            return
        self._love_played = True
        badge = self.clear_mark.geometry().center() if self.clear_mark.isVisible() else None
        self.love.choice = self.store.love_scene
        self.love.play(self._game_area(screen), keep, badge)

    def _frame_stream(self) -> None:
        """直播模式's window takes the size and place of the game's whole window, the one a
        streaming app's 窗口捕捉 captures: an emulator with its frame, or a full-screen game."""
        if not self.store.stream_mode or self._game_box is None:
            return
        left, top, right, bottom = self._game_box
        origin_x, origin_y = virtual_origin()
        x, y, _ratio = native_to_logical((left + right) / 2 + origin_x, (top + bottom) / 2 + origin_y)
        screen = QApplication.screenAt(QPoint(int(x), int(y))) or QApplication.primaryScreen()
        if screen is None:
            return
        frame = self._window_frame(screen, innermost=False)
        self.stream.set_frame(frame)
        size = (frame.width(), frame.height())
        if size != tuple(self.store.stream_size):
            log.info("直播模式's window now matches the game's window: %dx%d.", *size)
            self.store.stream_size = size
            self.store.save_settings()

    def _game_area(self, screen) -> QRect:  # noqa: ANN001
        return self._window_frame(screen, innermost=True)

    def _window_frame(self, screen, innermost: bool) -> QRect:  # noqa: ANN001
        """Where the game is drawn, for the border and the glow: its window when it sits in one (a
        windowed client, an emulator), else the whole screen."""
        area = screen.geometry()
        if self._game_box is None:
            return area
        origin_x, origin_y = virtual_origin()
        left, top, right, bottom = self._game_box
        found = window_rect_at(
            (left + right) // 2 + origin_x, (top + bottom) // 2 + origin_y, self._game_windows, innermost=innermost
        )
        if found is None:
            return area
        x, y, ratio = native_to_logical(found[0], found[1])
        rect = QRect(round(x), round(y), round((found[2] - found[0]) / ratio), round((found[3] - found[1]) / ratio))
        # Marks stay on the screen; the whole window is what a 窗口捕捉 sees, even partly off it.
        shown = rect.intersected(area)
        # Not much bigger than the button: not the game's window (a tooltip, a stray control).
        if shown.width() < 3 * (right - left) / ratio or shown.height() < 3 * (bottom - top) / ratio:
            return area
        return shown if innermost else rect

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
            self.like_card.hide()
            self.clear_mark.hide()
            return
        self.hit_card.set_people(people, self.panel.cover_geometry().height())
        self._place_beside(self.hit_card)

    def _likes_in(self, result: CheckResult) -> list[Entry]:
        """心动 players in the lobby, in seat order, each once."""
        found: list[Entry] = []
        for slot in result.names:
            label = NameLabel(raw=slot.raw, visible=slot.visible, truncated=slot.truncated, unclear=slot.unclear)
            for match in match_label(label, list(self.store.likes)):
                if all(match.entry is not seen for seen in found):
                    found.append(match.entry)
        return found

    def _show_like_card(self, likes: list[Entry]) -> None:
        """The 心动 card on the left of the cover, centered on it, inside the screen."""
        card = self.like_card
        if not likes:
            card.hide()
            return
        card.set_people([(like.shown(), ()) for like in likes], self.panel.cover_geometry().height())
        cover = self.panel.cover_geometry()
        x = cover.x() - 16 - card.width()
        y = cover.y() + (cover.height() - card.height()) // 2
        screen = QApplication.screenAt(cover.topLeft()) or QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            if x < area.left() + 8:
                # No room on the left: on the right, under the 黑名单 card or after the badge.
                if self.hit_card.isVisible():
                    x = self.hit_card.x()
                    y = self.hit_card.y() + self.hit_card.height() + 8
                else:
                    x = self.clear_mark.x() + self.clear_mark.width() - self.clear_mark.margin + 10
            y = max(area.top() + 8, min(y, area.bottom() - card.height() - 8))
        card.move(int(x), int(y))
        card.show()
        _pin_topmost(card)

    def _show_clear_mark(self, heart: bool = False) -> None:
        self.clear_mark.set_heart(heart)
        self.clear_mark.set_size(self.panel.cover_geometry().height())
        self._place_beside(self.clear_mark)

    def _place_beside(self, widget: QWidget) -> None:
        """Beside the cover, centered on it. A mark with a glow (margin) lines up by what it draws."""
        gap = 16
        cover = self.panel.cover_geometry()
        margin = getattr(widget, "margin", 0)
        x = cover.x() + cover.width() + gap - margin
        y = cover.y() + (cover.height() - widget.height()) // 2
        screen = QApplication.screenAt(cover.topLeft()) or QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            if x + widget.width() - margin > area.right() - 8:
                x = cover.x() - gap - widget.width() + margin
            x = max(area.left() + 8 - margin, min(x, area.right() - widget.width() + margin - 8))
            y = max(area.top() + 8 - margin, min(y, area.bottom() - widget.height() + margin - 8))
        widget.move(int(x), int(y))
        widget.show()
        _pin_topmost(widget)

    def _sync_status_tip(self) -> None:
        """The pill's tooltip: what went wrong, when something did."""
        chip = getattr(self, "status_chip", None)
        if chip is None:
            return
        chip.setToolTip(self._watch_tip)
        # 记录's empty page says how a check starts.
        empty = getattr(self, "history_empty", None)
        if empty is not None:
            empty.set_text("还没有记录", self._how_to_check())

    def _how_to_check(self) -> str:
        """How a check starts now, for 记录's empty page and the welcome guide."""
        if self.store.auto_capture:
            return "进入「推演成功」大厅时自动检查"
        spec = parse_hotkey(self.store.hotkey)
        key = spec.display if spec is not None else "快捷键"
        return f"在「推演成功」大厅按 {key} 检查"

    def _sync_watch_idle(self) -> None:
        if self.store.auto_capture:
            self._set_result("自动检查中", "watchOn", "watch")
        else:
            self._set_result("手动检查", "watchOff", "idle")

    def _set_result(self, text: str, tone: str = "status", kind: str = "result", tip: str = "") -> None:
        self._status_kind = kind
        self._watch_tone = tone
        self._watch_full = text
        self._watch_tip = tip
        # 手动检查 shows the hotkey that starts a check.
        self.status_chip.set_state(text, tone, self.store.hotkey if kind == "idle" else "")
        self._sync_status_tip()
        self._set_tray(text)

    def _remember_size(self) -> None:
        """Save the window's size and place now. A move or a resize waits for the drag to end."""
        if not hasattr(self, "store"):
            return
        changed = False
        width, height = self.width(), self.height()
        if width >= 900 and height >= 560 and self.store.window_size != (width, height):
            self.store.window_size = (width, height)
            changed = True
        if self.isVisible() and not self.isMinimized():
            geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
            if self.store.window_geometry != geometry:
                self.store.window_geometry = geometry
                changed = True
        if changed:
            self.store.save_settings()

    def _remember_geometry_soon(self) -> None:
        timer = getattr(self, "_geometry_timer", None)
        if timer is not None:
            timer.start()

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._remember_geometry_soon()

    def moveEvent(self, event) -> None:  # noqa: ANN001
        super().moveEvent(event)
        self._remember_geometry_soon()

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

    # --- Updates ---------------------------------------------------------------------------

    def _check_updates(self) -> None:
        if updater.app_root() is None or self._closing:
            return
        self.updates.check()

    def _check_updates_now(self) -> None:
        """检查更新: look now. A new version installs the way it does at start; otherwise the answer
        shows beside the button."""
        if updater.app_root() is None:
            self.update_note.setText("源码运行时不能更新")
            return
        if self._updating or not self.updates.check():
            return
        self._update_asked = True
        self.update_button.setEnabled(False)
        self.update_button.setText("检查中…")
        self.update_note.setText("")

    def _update_answered(self, note: str) -> None:
        self.update_button.setEnabled(True)
        self.update_button.setText("检查更新")
        if self._update_asked:
            self.update_note.setText(note)
        self._update_asked = False

    def _on_update_latest(self) -> None:
        log.info("Update check: %s is the newest.", __version__)
        self._update_answered("已是最新版本")

    def _on_update_failed(self, message: str) -> None:
        log.warning("Update check failed: %s", message)
        self._update_answered(message)

    def _on_update_found(self, release: updater.Release) -> None:
        """A new version is installed before the app is used: a dialog that stays until it is done,
        then a restart. In the tray it happens out of sight and the new version starts in the tray."""
        log.info("Update available: %s", release.version)
        self._update_answered("")
        root = updater.app_root()
        if root is None or self._updating or self._closing:
            return
        self._release = release
        self._updating = True
        if not release.needs_full() and not self.isVisible():
            download = Download(self)
            download.done.connect(self._restart_for_update)
            download.failed.connect(self._quiet_update_failed)
            download.start(release, root, self.store.root / "updates")
            return
        dialog = UpdateDialog(release, root, self.store.root, self)
        dialog.setAttribute(Qt.WA_DeleteOnClose, True)
        dialog.restart_requested.connect(self._restart_for_update)
        dialog.finished.connect(self._update_skipped)
        dialog.open()
        dialog.start()

    def _update_skipped(self, _result: int) -> None:
        # 跳过: this version goes on; the next start tries again.
        if self._updating:
            log.info("Update to %s not installed: the window was closed (跳过 or 前往下载).", self._release.version if self._release else "?")
        self._updating = False

    def _quiet_update_failed(self, message: str) -> None:
        # The next start tries again.
        log.info("Update in the tray failed: %s", message)
        self._updating = False

    def _restart_for_update(self, *_args) -> None:  # noqa: ANN002
        root = updater.app_root()
        version = self._release.version if self._release else ""
        if root is not None and not updater.note_restart(root, version):
            # Restarted into this version twice already and it did not go in: say so, do not loop.
            log.warning("Update %s did not install after %d restarts; not restarting again.", version, updater.MAX_TRIES)
            self._updating = False
            self._say("更新没装上，关掉所有模仿者小工具后重新打开")
            return
        if root is not None and restart_into_update(root, background=not self.isVisible()):
            log.info("Restarting into %s", self._release.version if self._release else "the update")
            self._updating = False
            self.quit_app()
        else:
            log.warning("Update downloaded, but the launcher to install it was not found.")
            self._updating = False

    def _confirm_update(self) -> None:
        """This version opened: tell the launcher, which would otherwise put the old one back."""
        said = updater.launcher_result(updater.app_root())
        if said:
            log.warning("Launcher: %s", said) if "失败" in said or "未完成" in said else log.info("Launcher: %s", said)
        if updater.confirm_started(updater.app_root()):
            self._say(f"已更新到 {__version__}")

    def quit_app(self) -> None:
        """Close for real, as 退出 in the tray menu does. The local installer asks for this before an update."""
        log.info("Asked to quit.")
        self.close()
        QApplication.quit()

    def _show_from_tray(self) -> None:
        """Back from the tray, or from a second launch: shown, not minimized, and in front."""
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
        bring_to_front(int(self.winId()))

    def _on_tray(self, reason) -> None:
        from PySide6.QtWidgets import QSystemTrayIcon

        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._show_from_tray()

    def closeEvent(self, event) -> None:  # noqa: ANN001
        if event.spontaneous() and self.store.close_to_tray and self.tray is not None and self.tray.isVisible():
            # Keep checking from the tray. Without a tray icon there would be no way back, so X quits.
            event.ignore()
            self.hide()
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
        self.like_card.close()
        self.clear_mark.close()
        self.love.stop()
        self.love.close()
        self.alert.stop()
        self.alert.close()
        self.notice.close()
        self.stream.enable("")
        self.stream.close()
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


# A menu item's icon, by what it does. The ones that delete are red, so they stand out.
def _plain_error(problem, fallback: str) -> str:  # noqa: ANN001
    """What a user may read about an error. The app's own errors are already plain Chinese;
    anything else (a library's message, often English, with paths) is logged and replaced."""
    if isinstance(problem, (OcrUnavailable, CaptureUnavailable)):
        return str(problem).strip() or fallback
    return fallback


class _ElidedLabel(QLabel):
    """One line that ends in … when it does not fit, instead of being cut mid-character."""

    def minimumSizeHint(self) -> QSize:
        return QSize(self.fontMetrics().horizontalAdvance("…") * 3, super().minimumSizeHint().height())

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        from PySide6.QtGui import QPainter

        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.setFont(self.font())
        text = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width())
        painter.drawText(self.rect(), int(Qt.AlignLeft | Qt.AlignVCenter), text)


def QSystemTrayIcon_available() -> bool:
    try:
        from PySide6.QtWidgets import QSystemTrayIcon

        return QSystemTrayIcon.isSystemTrayAvailable()
    except Exception:
        return False
