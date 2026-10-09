"""Paddle cannot open model files under a path with Chinese characters."""

from blacklist_detect import ocr_engine
from blacklist_detect.ocr_engine import paddle_safe_dir


def _model(folder):
    folder.mkdir(parents=True)
    (folder / "inference.json").write_text("{}", encoding="utf-8")
    (folder / "inference.pdiparams").write_bytes(b"\0" * 64)
    return folder


def test_an_ascii_folder_is_used_as_it_is(tmp_path):
    folder = _model(tmp_path / "models" / "PP-OCRv5_mobile_det")
    assert paddle_safe_dir(folder, cache_roots=[tmp_path / "cache"]) == folder


def test_a_chinese_folder_is_copied_once_to_an_ascii_one(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_engine, "_short_path", lambda path: path)
    folder = _model(tmp_path / "黑名单检测" / "models" / "PP-OCRv6_medium_rec")
    cache = tmp_path / "cache"
    safe = paddle_safe_dir(folder, cache_roots=[tmp_path / "缓存", cache])
    assert safe == cache / "PP-OCRv6_medium_rec"
    assert str(safe).isascii()
    assert (safe / "inference.pdiparams").read_bytes() == b"\0" * 64
    stamp = (safe / "inference.json").stat().st_mtime_ns
    assert paddle_safe_dir(folder, cache_roots=[cache]) == safe
    assert (safe / "inference.json").stat().st_mtime_ns == stamp
    (folder / "inference.pdiparams").write_bytes(b"\1" * 80)
    paddle_safe_dir(folder, cache_roots=[cache])
    assert (safe / "inference.pdiparams").read_bytes() == b"\1" * 80


def test_a_short_name_is_used_when_windows_has_one(tmp_path, monkeypatch):
    folder = _model(tmp_path / "黑名单检测" / "PP-OCRv5_mobile_rec")
    short = _model(tmp_path / "HEIMIN~1" / "PP-OCRv5_mobile_rec")
    monkeypatch.setattr(ocr_engine, "_short_path", lambda path: short)
    assert paddle_safe_dir(folder, cache_roots=[tmp_path / "cache"]) == short
    assert not (tmp_path / "cache").exists()
