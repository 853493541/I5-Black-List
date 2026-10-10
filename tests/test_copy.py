"""No system information reaches the user: no library names, commands, file paths or raw errors."""

import ast
import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "blacklist_detect"
# The command line in __main__.py is for developers, not for users of the window.
SKIP = {"__main__.py"}
CJK = re.compile(r"[\u4e00-\u9fff]")
BANNED = re.compile(r"PaddleOCR|paddle|python|README|BLACKLIST_DETECT|\.json|\.log\b|backups|logs|详情：|Traceback", re.I)


def _user_strings():
    for path in sorted(PACKAGE.glob("*.py")):
        if path.name in SKIP:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        # Docstrings explain the code to whoever reads it; they never reach the window.
        docs = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
                first = node.body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                    docs.add(id(first.value))
        for node in ast.walk(tree):
            if id(node) in docs:
                continue
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and CJK.search(node.value):
                yield path.name, node.lineno, node.value


def test_no_user_facing_text_names_the_system():
    found = [f"{name}:{line}: {text}" for name, line, text in _user_strings() if BANNED.search(text)]
    assert found == []


def test_the_app_sends_no_windows_notifications():
    """No popup from the tray: errors show in the window header, never over the game."""
    senders = [path.name for path in PACKAGE.glob("*.py") if "showMessage" in path.read_text(encoding="utf-8")]
    assert senders == []
