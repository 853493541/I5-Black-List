"""The on-screen Chinese follows one glossary (see blacklist_detect/ui_text.py)."""

import ast
import inspect
import re
from pathlib import Path

from blacklist_detect import ui_text as T

PACKAGE = Path(__file__).resolve().parent.parent / "blacklist_detect"
CJK = re.compile(r"[\u4e00-\u9fff]")

# Words that crept in from literal translation, or name one idea two ways.
BANNED = ("检查", "捕捉", "看清", "热键", "详情", "批量添加", "复原", "出错了", "没能", "没有就绪", "人在黑名单里")

BUTTONS = (
    T.ADD_PLAYER, T.BATCH_IMPORT, T.COPY_LIST, T.CLEAR_LIST, T.CONFIRM_CLEAR, T.UNDO, T.CLEAR_RECORDS,
    T.TEST_RECOGNITION, T.CHECK_PICTURE, T.RECHECK_TAGS, T.RESET_ALL, T.OPEN_DATA, T.OK, T.CANCEL, T.SAVE,
    T.DELETE, T.CLOSE, T.ADD, T.CREATE, T.IMPORT, T.REMOVE_PLAYER, T.START, T.BLOCK, T.MODE_AUTO,
    T.MODE_HOTKEY, T.ON, T.OFF, T.TRAY_SHOW, T.TRAY_QUIT, T.NEW_TAG,
)
SENTENCES = (
    T.RECORDS_EMPTY_HINT, T.NOTE_IN_TRAY_TEXT, T.NOTE_NO_LOBBY_TEXT, T.NOTE_LOADING_TEXT, T.HOTKEY_KEY_NEEDED,
    T.HOTKEY_UNUSABLE, T.HOTKEY_UNSUPPORTED, T.HOTKEY_TAKEN, T.HOTKEY_SAVED_UNSUPPORTED, T.READER_BUSY,
    T.RESET_CONFIRM, T.PICTURE_NEEDS_LOBBY, T.GUIDE_INTRO, *T.GUIDE_STEPS, T.STORE_SETTINGS_UNREADABLE,
    T.CAPTURE_UNSUPPORTED, T.CAPTURE_FAILED, T.MODEL_MISSING, T.OCR_MISSING, T.NO_FRAME, T.NO_LOBBY,
    T.LOBBY_LAYOUT_BROKEN, T.LOBBY_SCATTERED, T.copied_players(2), T.delete_unused_tag("炸房"),
    T.delete_used_tag("炸房", 2, "甲、乙"), T.list_unreadable("x.json"), T.lobby_missing("「推演成功」"),
    T.lobby_summary(10, 12, 1, 1),
)
IN_PROGRESS = (T.STATUS_LOADING, T.OVERLAY_CHECKING, T.RECOGNIZING)
# English the player may see on purpose: key names, and the two folder names in 打开数据文件夹.
ALLOWED_LATIN = {"F", "Alt", "backups", "logs"}


def _all_text(skip: tuple[str, ...] = ()) -> list[str]:
    """Every constant in the catalog, and every function called with sample values."""
    found: list[str] = []
    for name, value in vars(T).items():
        if name.startswith("_") or name == "PICTURE_FILTER" or name in skip:
            continue
        if isinstance(value, str):
            found.append(value)
        elif isinstance(value, tuple):
            found.extend(item for item in value if isinstance(item, str))
        elif inspect.isfunction(value) and value.__module__ == T.__name__:
            samples = {"int": 2, "str": "甲", "object": "C:/data/app.log", "int | None": 10}
            args = [samples.get(str(p.annotation), "甲") for p in inspect.signature(value).parameters.values()]
            found.append(value(*args))
    return found


def test_no_banned_words():
    for text in _all_text():
        for word in BANNED:
            assert word not in text, f"{word!r} in {text!r}"
    assert T.ME == "我"


def test_buttons_have_no_closing_punctuation():
    for label in BUTTONS:
        assert label and label[-1] not in "。！？.!?：:，,", label
        assert len(label) <= 7, label


def test_messages_are_whole_sentences():
    for text in SENTENCES:
        assert text.endswith(("。", "？")), text


def test_work_in_progress_ends_with_an_ellipsis():
    for text in IN_PROGRESS:
        assert text.endswith("…"), text


def test_no_english_and_no_ascii_punctuation_inside_chinese():
    # These two show the log's path on purpose, so a friend can find and send it.
    for text in _all_text(skip=("problem_tip", "start_failed")):
        if not CJK.search(text):
            continue
        for word in re.findall(r"[A-Za-z]+", text):
            assert word in ALLOWED_LATIN, f"{word!r} in {text!r}"
        assert not re.search(r"[\u4e00-\u9fff][,.;?!()]|[,;?!()][\u4e00-\u9fff]", text), text


def test_windows_take_their_words_from_the_catalog():
    """New Chinese in the window code would skip the glossary. Dates and relative times are exempt."""
    allowed = {"中", "月", "日", "刚刚", "分钟前", "小时前", "天前", "个月前", "年前"}
    for name in ("ui.py", "ui_dialogs.py", "ui_widgets.py", "ui_overlay.py"):
        tree = ast.parse((PACKAGE / name).read_text(encoding="utf-8"))
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef))
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                if CJK.search(node.value):
                    assert node.value in allowed, f"{name}:{node.lineno} {node.value!r}"
