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


def test_sync_sees_a_same_size_edit_made_in_the_same_instant(tmp_path):
    import os

    source = tmp_path / "repo" / "blacklist_detect"
    target = tmp_path / "install" / "blacklist_detect"
    _write(source / "ui.py", "version A")
    sync_tree(source, target)
    stamp = (source / "ui.py").stat().st_mtime_ns
    _write(source / "ui.py", "version B")
    os.utime(source / "ui.py", ns=(stamp, stamp))
    assert sync_tree(source, target) == (1, 0)
    assert (target / "ui.py").read_text(encoding="utf-8") == "version B"
    assert sync_tree(source, target) == (0, 0)


def test_the_install_gets_the_release_qtmedia_folder_and_a_sync_keeps_it(tmp_path):
    """The installed runtime leaves QtMultimedia out like the release's, so 上传 needs qtmedia here too."""
    from install_local import install_qtmedia
    from make_release import QTMEDIA_FILES

    site = tmp_path / "runtime" / "Lib" / "site-packages"
    for rel in QTMEDIA_FILES:
        _write(site / rel, rel)
    source = tmp_path / "repo" / "blacklist_detect"
    app = tmp_path / "install" / "blacklist_detect"
    _write(source / "ui.py", "window")

    sync_tree(source, app)
    assert install_qtmedia(site, app) == 3
    plugin = app / "qtmedia" / "multimedia" / "windowsmediaplugin.dll"
    assert plugin.read_text(encoding="utf-8") == "PySide6/plugins/multimedia/windowsmediaplugin.dll"
    assert sync_tree(source, app) == (0, 0) and plugin.is_file()
    assert install_qtmedia(site, app) == 0

    _write(site / "PySide6" / "QtMultimedia.pyd", "a newer PySide6")
    assert install_qtmedia(site, app) == 1
    assert (app / "qtmedia" / "QtMultimedia.pyd").read_text(encoding="utf-8") == "a newer PySide6"

    # The runtime it came from is gone: what is installed stays.
    assert install_qtmedia(tmp_path / "gone", app) == 0 and plugin.is_file()
