"""The local install copies only what changed and never touches models or caches."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "build"))

from install_local import sync_tree  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_sync_copies_changes_and_removes_old_files(tmp_path):
    source = tmp_path / "repo" / "blacklist_detect"
    target = tmp_path / "install" / "blacklist_detect"
    _write(source / "ui.py", "new window")
    _write(source / "assets" / "app.ico", "icon")
    _write(source / "__pycache__" / "ui.cpython-312.pyc", "repo cache")
    _write(target / "ui.py", "old window")
    _write(target / "old_module.py", "gone from the repo")
    _write(target / "models" / "PP-OCRv6_medium_rec" / "inference.pdiparams", "weights")
    _write(target / "__pycache__" / "ui.cpython-312.pyc", "install cache")

    assert sync_tree(source, target) == (2, 1)
    assert (target / "ui.py").read_text(encoding="utf-8") == "new window"
    assert (target / "assets" / "app.ico").is_file()
    assert not (target / "old_module.py").exists()
    assert (target / "models" / "PP-OCRv6_medium_rec" / "inference.pdiparams").read_text(encoding="utf-8") == "weights"
    assert (target / "__pycache__" / "ui.cpython-312.pyc").read_text(encoding="utf-8") == "install cache"

    assert sync_tree(source, target) == (0, 0)
