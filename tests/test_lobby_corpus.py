"""The lobby corpus tool tells a lobby frame from any other and keeps one frame per lobby."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("lobby_corpus", ROOT / "tools" / "lobby_corpus.py")
lobby_corpus = importlib.util.module_from_spec(spec)
sys.modules["lobby_corpus"] = lobby_corpus
spec.loader.exec_module(lobby_corpus)


def test_lobby_texts_needs_title_and_a_lobby_line():
    assert lobby_corpus.lobby_texts(["推演成功", "模仿者狂欢（12人狂欢）"])
    assert lobby_corpus.lobby_texts(["推演成", "模仿者狂欢（12人狂"])
    assert not lobby_corpus.lobby_texts(["推演成功", "自由假面", "倒计时10秒"])
    assert not lobby_corpus.lobby_texts(["推演成功"])
    assert not lobby_corpus.lobby_texts(["模仿者狂欢", "开始匹配"])


def test_group_hits_keeps_the_sharpest_per_lobby():
    hits = [lobby_corpus.Hit(t, s, np.empty(0)) for t, s in [(100, 1), (103, 5), (106, 2), (900, 3), (903, 1)]]
    best = lobby_corpus.group_hits(hits)
    assert [(h.seconds, h.sharp) for h in best] == [(103, 5), (900, 3)]


@pytest.mark.parametrize("name", ["tests/fixtures/reference-lobby.png", "blacklist_detect/assets/sample-lobby.jpg"])
def test_shows_lobby_on_a_whole_frame(name):
    cv2 = pytest.importorskip("cv2")
    pytest.importorskip("rapidocr_onnxruntime")
    crop = cv2.cvtColor(cv2.imread(str(ROOT / name)), cv2.COLOR_BGR2RGB)
    frame = np.full((1080, 1920, 3), 30, np.uint8)
    frame[120:949, 160:1760] = cv2.resize(crop, (1600, 829))
    assert lobby_corpus.shows_lobby(frame)
    frame[:] = 30
    assert not lobby_corpus.shows_lobby(frame)
