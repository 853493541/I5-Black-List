"""Every word the app shows, in one place.

The copy follows one glossary, so each idea has one name everywhere:

    检测      the lobby check: 自动检测 or 快捷键检测. Not 检查, 捕捉, or 截图.
    识别      reading names off the screen. A name that cannot be read is 未识别.
    玩家      a person on the list or in a lobby; 玩家名 is their name in the game.
              Counts read "N 名玩家" (or "N 人" in short status lines).
    原因      why someone is on the list. Not 详情 or 说明.
    拉黑      put a player from 对局记录 on the list; 移出黑名单 takes one off.
    批量导入  bring in many players at once; 复制名单 hands the list to a friend.
    快捷键    not 热键.
    我        the person using the app, when shown as a label. Not 你.

Buttons are a verb and its object, with no closing punctuation. Messages are
whole sentences ending in 。. Work in progress ends with …. Other controls are
named in 「」. Commands, file paths, and English error text belong in the log,
not on screen. tests/test_copy.py checks these rules.
"""

from __future__ import annotations

APP_NAME = "黑名单检测"

# Pages
TAB_RECORDS = "对局记录"
TAB_BLACKLIST = "黑名单"
TAB_SETTINGS = "设置"

# Header status
STATUS_OFF = "未开启"
STATUS_AUTO = "自动检测中"
STATUS_HOTKEY = "快捷键检测"
STATUS_LOADING = "正在加载识别模型…"
STATUS_MODEL_MISSING = "识别模型未就绪"
STATUS_SCREEN_FAILED = "无法截取屏幕"
STATUS_CHECK_FAILED = "检测失败"
STATUS_CRASHED = "程序发生错误"
SWITCH_TO_HOTKEY = "切换为快捷键检测"
SWITCH_TO_AUTO = "切换为自动检测"


def problem_tip(detail: str, log_path: object) -> str:
    return f"{detail}\n\n详细信息见日志：{log_path}"


# Tray and Windows notifications
TRAY_SHOW = "显示主窗口"
TRAY_QUIT = "退出"
NOTE_IN_TRAY = "已最小化到系统托盘"
NOTE_IN_TRAY_TEXT = "程序会在后台继续检测。右键单击托盘图标可以退出。"
NOTE_NO_LOBBY = "未检测到对局大厅"
NOTE_NO_LOBBY_TEXT = "请在显示「推演成功」的界面按快捷键。"
NOTE_LOADING = "识别模型正在加载"
NOTE_LOADING_TEXT = "请稍候几秒再按快捷键。"

# The cover drawn over 准备案件还原
OVERLAY_CHECKING = "检测中…"
OVERLAY_CLEAR = "未发现黑名单"


def unread_count(count: int) -> str:
    return f"{count} 人未识别"


# 黑名单 page
COL_NAME = "玩家名"
COL_TAGS = "标签"
COL_REASON = "原因"
COL_LAST_MET = "最近遇到"
COLUMN_TIP = "拖动列标题可调整顺序，拖动边缘可调整宽度"
SHOW_NAMES = "显示玩家名"
HIDE_NAMES = "隐藏玩家名"
LIST_EMPTY = "黑名单为空"
SEARCH_PLACEHOLDER = "搜索玩家名、标签或原因"
ADD_PLAYER = "添加玩家"
BATCH_IMPORT = "批量导入"
COPY_LIST = "复制名单"
COPY_LIST_TIP = "复制整个黑名单，好友可以在「批量导入」中粘贴导入"
CLEAR_LIST = "清空黑名单"
CONFIRM_CLEAR = "确认清空"
UNDO = "撤销"
UNDONE = "已撤销"


def search_empty(query: str) -> str:
    return f"没有找到与「{query}」相关的玩家"


def cleared_players(count: int) -> str:
    return f"已清空 {count} 名玩家"


def copied_players(count: int) -> str:
    return f"已复制 {count} 名玩家，好友可以在「批量导入」中粘贴导入。"


def added_player(name: str) -> str:
    return f"已将「{name}」加入黑名单"


def removed_player(name: str) -> str:
    return f"已将「{name}」移出黑名单"


def imported_players(added: int, skipped: int) -> str:
    text = f"已导入 {added} 名玩家"
    if skipped:
        text += f"，跳过 {skipped} 名重复玩家"
    return text


def all_already_listed(count: int) -> str:
    return f"这 {count} 名玩家已在黑名单中"


# 对局记录 page
RECORDS_EMPTY = "暂无对局记录"
RECORDS_EMPTY_HINT = "进入「推演成功」大厅后会自动检测，结果会显示在这里。"
CLEAR_RECORDS = "清空记录"
LOBBY_MODE = "模仿者狂欢（12人狂欢）"
UNREAD = "未识别"
ME = "我"
BLOCK = "拉黑"


def matched(listed: str) -> str:
    return f"匹配：{listed}"


def matched_tip(read: str, listed: str) -> str:
    return f"识别为「{read}」，匹配黑名单中的「{listed}」"


# 设置 page
MY_NAME = "我的角色名"
MY_NAME_PLACEHOLDER = "游戏内角色名"
CHECK_MODE = "检测方式"
MODE_AUTO = "自动检测"
MODE_HOTKEY = "快捷键检测"
HOTKEY_NONE = "未设置"
HOTKEY_PRESS = "请按下快捷键"
HOTKEY_KEY_NEEDED = "快捷键需要包含字母、数字或 F1–F12 中的一个键。"
HOTKEY_UNUSABLE = "该组合键不可用，请更换。"
HOTKEY_UNSUPPORTED = "当前系统不支持全局快捷键。"
HOTKEY_TAKEN = "该快捷键已被其他程序占用，请更换。"
HOTKEY_SAVED_UNSUPPORTED = "快捷键已保存，但当前系统不支持全局快捷键。"
RECOGNITION = "识别测试"
TEST_RECOGNITION = "测试识别"
TEST_RECOGNITION_TIP = "使用内置的示例截图测试识别，无需进入游戏"
RECOGNIZING = "识别中…"
CHECK_PICTURE = "检测截图"
CHECK_PICTURE_TIP = "选择一张大厅截图，检测其中是否有黑名单玩家"
PICK_PICTURE = "选择大厅截图"
PICTURE_FILTER = "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)"
TEST_TITLE = "识别测试"
PICTURE_TITLE = "截图检测"
READER_BUSY = "识别功能正忙，请稍后再试。"
SOUND = "提示音"
ON = "开"
OFF = "关"
SOUND_TIP = "发现黑名单玩家时播放提示音"
THEME_LABEL = "主题"
TAGS_LABEL = "标签"
NEW_TAG = "新建标签"
RECHECK_TAGS = "自动补全标签"
RECHECK_TAGS_TIP = "根据原因中的文字，为玩家补上对应的标签"
DATA_LABEL = "数据"
RESET_ALL = "重置所有数据"
OPEN_DATA = "打开数据文件夹"
OPEN_DATA_TIP = "黑名单、设置、每日备份（backups）和日志（logs）都保存在这里"
VERSION_LABEL = "版本"
RESET_CONFIRM = "将删除全部黑名单、对局记录和设置，并恢复到初始状态。此操作无法撤销，确定继续？"
NAMES_ETC = "等"


def delete_unused_tag(tag: str) -> str:
    return f"删除标签「{tag}」？目前没有玩家使用它。"


def delete_used_tag(tag: str, count: int, names: str) -> str:
    return f"有 {count} 名玩家使用了「{tag}」（{names}），删除后这些玩家将不再带有该标签。确定删除？"


# Dialogs
OK = "确定"
CANCEL = "取消"
SAVE = "保存"
DELETE = "删除"
CLOSE = "关闭"
ADD = "添加"
CREATE = "创建"
IMPORT = "导入"
EDIT_TAG = "编辑标签"
TAG_NAME = "标签名称"
TAG_NAME_NEEDED = "请输入标签名称"
TAG_EXISTS = "该标签已存在"
EDIT_PLAYER = "编辑玩家"
FIELD_NAME = "玩家名"
FIELD_TAGS = "标签"
FIELD_REASON = "原因"
REMOVE_PLAYER = "移出黑名单"
NAME_NEEDED = "请输入玩家名"
NAME_NEEDS_TEXT = "玩家名需要包含文字或数字"
NAME_LISTED = "该玩家已在黑名单中"
IMPORT_HINT = (
    "支持以下格式：\n"
    "· 每行一名玩家：玩家名，炸房，贴脸，原因\n"
    "· 玩家名（原因），原因中提到的标签会自动选中\n"
    "· 只有玩家名，用空格或换行分隔\n"
    "· 好友通过「复制名单」发来的名单"
)
IMPORT_PLACEHOLDER = "在此粘贴名单"
IMPORT_EMPTY = "没有识别到玩家名"
PICTURE_NEEDS_LOBBY = "请选择包含「推演成功」大厅的截图。"
PICTURE_CLEAR = "未发现黑名单玩家"


def picture_failed(detail: str) -> str:
    return f"检测失败：{detail}"


def picture_hits(count: int) -> str:
    return f"发现 {count} 名黑名单玩家"


def unread_after(count: int) -> str:
    return f"，{count} 人未识别"


GUIDE_TITLE = "欢迎使用黑名单检测"
GUIDE_INTRO = "进入「推演成功」大厅后，程序会识别 12 名玩家的名字，并标出黑名单中的玩家。程序只读取屏幕画面，不会改动游戏。"
GUIDE_STEPS = (
    "1. 在「设置」中填写你的角色名，对局记录里会标出你自己。",
    "2. 在「黑名单」中添加玩家，或通过「批量导入」粘贴好友发来的名单。",
    "3. 正常进入游戏即可。大厅中有黑名单玩家时，「准备案件还原」按钮会标红，并在旁边列出玩家名。",
)
GUIDE_TEST_TIP = "使用内置的示例截图测试识别"
START = "开始使用"

# Messages from storage, capture, the hotkey, and the OCR reader
STORE_SETTINGS_UNREADABLE = "设置文件读取失败，部分设置已恢复默认。"
CAPTURE_UNSUPPORTED = "当前系统不支持截屏检测，请使用「检测截图」。"
CAPTURE_FAILED = "截取屏幕失败，请重试。"
MODEL_MISSING = "识别模型缺失或已损坏，请重新解压完整的安装包。"
OCR_MISSING = "识别组件缺失，请重新解压完整的安装包。"
NO_FRAME = "没有截取到屏幕画面。"
NO_LOBBY = "未识别到对局大厅。"
LOBBY_LAYOUT_BROKEN = "大厅布局异常，无法定位玩家名。"
LOBBY_SCATTERED = "识别到部分大厅文字，但位置不符合大厅布局。"


def start_failed(detail: object, log_path: object) -> str:
    text = f"程序启动失败：{detail}"
    if log_path:
        text += f"\n\n详细信息已写入日志：{log_path}"
    return text


def list_unreadable(saved_as: str) -> str:
    return f"黑名单文件已损坏，已另存为 {saved_as}，当前使用空的黑名单。"


def lobby_missing(parts: str) -> str:
    return f"未识别到对局大厅，缺少{parts}。"


def lobby_summary(countdown: int | None, ready: int | None, hits: int, unread: int) -> str:
    parts: list[str] = []
    if countdown is not None:
        parts.append(f"倒计时 {countdown} 秒")
    if ready is not None:
        parts.append(f"准备就绪 {ready}/12")
    parts.append(picture_hits(hits) if hits else PICTURE_CLEAR)
    if unread:
        parts.append(unread_count(unread))
    return "已检测对局大厅：" + "，".join(parts) + "。"
