"""The opt-in ONNX Runtime reader: Paddle stays the default, and onnx_ocr's steps match PaddleX's own.

The step-by-step comparisons run where PaddleX is installed (the Paddle setup); the reads themselves are checked
end to end by tools/engine_bench.py and, with BLACKLIST_DETECT_ENGINE=onnxruntime, test_reference_screenshot.py."""

import importlib.util

import numpy as np
import pytest

from blacklist_detect.ocr_engine import OcrEngine, ocr_backend

cv2 = pytest.importorskip("cv2")
pytest.importorskip("pyclipper")
from blacklist_detect import onnx_ocr  # noqa: E402

needs_paddlex = pytest.mark.skipif(importlib.util.find_spec("paddlex") is None, reason="PaddleX is not installed")


def test_paddle_is_the_default(monkeypatch):
    monkeypatch.delenv("BLACKLIST_DETECT_ENGINE", raising=False)
    assert ocr_backend() == "paddle"
    assert OcrEngine().backend == "paddle"


@pytest.mark.parametrize(("value", "backend"), [("onnxruntime", "onnxruntime"), (" ONNXRuntime ", "onnxruntime"), ("tensorrt", "paddle")])
def test_switch_reads_the_environment(monkeypatch, value, backend):
    monkeypatch.setenv("BLACKLIST_DETECT_ENGINE", value)
    assert ocr_backend() == backend
    assert OcrEngine().backend == backend
    assert OcrEngine(backend="paddle").backend == "paddle"


def test_missing_onnx_models_say_so_like_paddle(monkeypatch, tmp_path):
    from blacklist_detect.ocr_engine import OcrUnavailable

    monkeypatch.setenv("BLACKLIST_DETECT_MODEL_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    engine = OcrEngine(backend="onnxruntime")
    with pytest.raises(OcrUnavailable):
        engine.read_names([np.zeros((32, 160, 3), np.uint8)])


def _recognizer(characters):
    rec = onnx_ocr.TextRecognizer.__new__(onnx_ocr.TextRecognizer)
    rec.characters = ["blank", *characters, " "]
    rec.image_shape = [3, 48, 320]
    return rec


def test_ctc_drops_blanks_and_repeats_and_averages_the_kept():
    rec = _recognizer(["心", "动"])
    steps = [1, 1, 0, 2, 2, 0, 0, 1]  # 心 心 _ 动 动 _ _ 心 -> 心动心
    preds = np.full((1, len(steps), 4), 0.01, dtype=np.float32)
    for t, index in enumerate(steps):
        preds[0, t, index] = 0.9 if t != 3 else 0.6
    [(text, score)] = rec.decode(preds)
    assert text == "心动心"
    assert score == pytest.approx((0.9 + 0.6 + 0.9) / 3)
    assert rec.decode(np.zeros((1, 3, 4), np.float32) + np.eye(4)[0]) == [("", 0.0)]


def test_lines_sort_top_to_bottom_then_left_to_right():
    def box(x, y):
        return np.array([[x, y], [x + 10, y], [x + 10, y + 5], [x, y + 5]], dtype=np.int16)

    ordered = onnx_ocr.sort_boxes([box(50, 3), box(0, 40), box(10, 0)])
    assert [tuple(b[0]) for b in ordered] == [(10, 0), (50, 3), (0, 40)]


@needs_paddlex
@pytest.mark.parametrize("shape", [(20, 20, 3), (90, 700, 3), (1080, 1920, 3), (3000, 200, 3)])
def test_detection_resize_matches_paddlex(shape):
    from paddlex.inference.models.text_detection.processors import DetResizeForTest

    image = np.random.default_rng(1).integers(0, 255, shape, dtype=np.uint8)
    params = onnx_ocr.DET_PARAMS
    theirs = DetResizeForTest(limit_side_len=params["limit_side_len"], limit_type=params["limit_type"], max_side_limit=4000)
    [want], [want_shape] = theirs([image], params["limit_side_len"], params["limit_type"], params["max_side_limit"])
    got, got_shape = onnx_ocr.det_resize(image, params["limit_side_len"], params["limit_type"], params["max_side_limit"])
    assert np.array_equal(got, want) and np.array_equal(got_shape, want_shape)


@needs_paddlex
def test_db_boxes_match_paddlex():
    from paddlex.inference.models.text_detection.processors import DBPostProcess

    rng = np.random.default_rng(2)
    pred = (rng.random((160, 320)) * 0.2).astype(np.float32)
    for x, y, w, h, angle in [(20, 10, 80, 12, 0), (150, 30, 120, 18, 8), (40, 90, 60, 9, -5), (200, 120, 30, 20, 30)]:
        corners = cv2.boxPoints(((x + w / 2, y + h / 2), (w, h), angle)).astype(np.int32)
        cv2.fillPoly(pred, [corners], float(rng.uniform(0.7, 0.95)))
    pred = cv2.GaussianBlur(pred, (0, 0), 1.5)
    shape = np.array([300, 640, 160 / 300, 320 / 640])
    p = onnx_ocr.DET_PARAMS
    [want], [want_scores] = DBPostProcess(thresh=p["thresh"], box_thresh=p["box_thresh"], unclip_ratio=p["unclip_ratio"])(
        [pred[None, None]], [shape])
    got, scores = onnx_ocr.db_boxes(pred, shape, p["thresh"], p["box_thresh"], p["unclip_ratio"])
    assert len(want) >= 3
    assert np.array_equal(got, want) and scores == want_scores


@needs_paddlex
def test_sort_and_crop_match_paddlex():
    from paddlex.inference.pipelines.components.common.crop_image_regions import CropByPolys
    from paddlex.inference.pipelines.components.common.sort_boxes import SortQuadBoxes

    rng = np.random.default_rng(3)
    image = rng.integers(0, 255, (200, 300, 3), dtype=np.uint8)
    polys = np.array([[[x, y], [x + w, y + 2], [x + w - 1, y + h], [x, y + h - 1]]
                      for x, y, w, h in rng.integers(5, 120, (12, 4))], dtype=np.int16)
    want = SortQuadBoxes()(polys)
    got = onnx_ocr.sort_boxes(polys)
    assert all(np.array_equal(a, b) for a, b in zip(got, want, strict=True))
    for a, b in zip(onnx_ocr.crop_by_polys(image, got), CropByPolys("quad")(image, want), strict=True):
        assert np.array_equal(a, b)


@needs_paddlex
@pytest.mark.parametrize("size", [(48, 100), (30, 600), (20, 2000)])
def test_recognition_resize_matches_paddlex(size):
    from paddlex.inference.models.text_recognition.processors import OCRReisizeNormImg

    image = np.random.default_rng(4).integers(0, 255, (*size, 3), dtype=np.uint8)
    [want] = OCRReisizeNormImg(rec_image_shape=[3, 48, 320])([image])
    assert np.array_equal(_recognizer([]).resize_norm(image), want)


@needs_paddlex
def test_ctc_decode_matches_paddlex():
    from paddlex.inference.models.text_recognition.processors import CTCLabelDecode

    characters = list("示例坏人心动小鹿星abc")
    preds = np.random.default_rng(5).random((3, 40, len(characters) + 2)).astype(np.float32)
    preds /= preds.sum(axis=-1, keepdims=True)
    texts, scores = CTCLabelDecode(character_list=characters)([preds])
    assert _recognizer(characters).decode(preds) == list(zip(texts, scores, strict=True))
