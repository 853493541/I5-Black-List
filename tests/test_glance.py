"""The 推演成功 glance reads only the tallest title-shaped lines, and skips an unchanged screen."""

import numpy as np

from blacklist_detect.ocr_engine import OcrEngine
from blacklist_detect.pipeline import band_signature, glance_title, same_band


class _Pipeline:
    """Stands in for PaddleOCR's internal pipeline: boxes come from det, text from rec."""

    text_rec_score_thresh = 0.0

    def __init__(self, lines):
        # lines: (x0, y0, x1, y1, text, score)
        self.lines = lines
        self.read: list[str] = []

    def get_text_det_params(self):
        return {}

    def text_det_model(self, images, **_params):
        polys = [np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float32) for x0, y0, x1, y1, *_ in self.lines]
        yield {"dt_polys": polys}

    def _sort_boxes(self, polys):
        return polys

    def _crop_by_polys(self, image, polys):
        for poly in polys:
            yield np.ones((int(poly[2][1] - poly[0][1]), int(poly[1][0] - poly[0][0]), 3), dtype=np.uint8)

    def text_rec_model(self, crops):
        by_size = {(line[3] - line[1], line[2] - line[0]): line for line in self.lines}
        for crop in crops:
            line = by_size[crop.shape[:2]]
            self.read.append(line[4])
            yield {"rec_text": line[4], "rec_score": line[5]}


def _engine(lines):
    pipeline = _Pipeline(lines)
    engine = OcrEngine()
    engine._ocr = type("Ocr", (), {"paddlex_pipeline": type("Wrapper", (), {"_pipeline": pipeline})()})()
    return engine, pipeline


def test_only_the_tallest_title_shaped_lines_are_read():
    lines = [
        (10, 10, 13, 30, "8", 0.9),  # one character: too narrow
        (10, 40, 400, 60, "a long sentence that is never the title", 0.9),  # too long
        (10, 70, 70, 90, "记录二", 0.9),
        (10, 100, 72, 118, "黑名单", 0.9),
        (10, 130, 64, 146, "手动检查", 0.9),
        (10, 150, 60, 164, "设置项目", 0.9),
        (300, 10, 390, 40, "推演成功", 0.95),
    ]
    engine, pipeline = _engine(lines)
    found = engine.read_tallest_lines(np.zeros((216, 960, 3), dtype=np.uint8))
    assert [line.text for line in found] == ["推演成功", "记录二", "黑名单", "手动检查"]
    assert pipeline.read == ["推演成功", "记录二", "黑名单", "手动检查"]
    assert glance_title(np.zeros((216, 960, 3), dtype=np.uint8), engine=engine) is True


def test_a_glance_without_the_title_is_false():
    engine, _pipeline = _engine([(10, 10, 70, 30, "记录二", 0.9)])
    assert glance_title(np.zeros((216, 960, 3), dtype=np.uint8), engine=engine) is False


def test_without_the_pipeline_internals_the_glance_reads_everything():
    class Plain:
        def __init__(self):
            self.full = 0

        def read_bgr(self, _bgr):
            from blacklist_detect.model import OcrLine

            self.full += 1
            return [OcrLine("推演成功", 0.9, (0, 0, 10, 3))]

    reader = Plain()
    assert glance_title(np.zeros((216, 960, 3), dtype=np.uint8), engine=reader) is True
    assert reader.full == 1
    engine = OcrEngine()
    engine._ocr = object()
    engine.read_bgr = reader.read_bgr
    assert [line.text for line in engine.read_tallest_lines(np.zeros((10, 10, 3), dtype=np.uint8))] == ["推演成功"]


def test_an_unchanged_band_is_recognized_and_a_new_title_is_not():
    rng = np.random.default_rng(1)
    band = rng.integers(0, 255, (864, 3840, 3), dtype=np.uint8)
    first = band_signature(band)
    assert first.shape[0] <= 40 and first.shape[1] <= 170
    assert same_band(None, first) is False
    noisy = band.astype(np.int16) + rng.integers(-1, 2, band.shape)
    assert same_band(first, band_signature(np.clip(noisy, 0, 255).astype(np.uint8))) is True
    titled = band.copy()
    titled[100:300, 1200:2600] = 255
    assert same_band(first, band_signature(titled)) is False
