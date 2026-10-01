"""Local PaddleOCR Chinese reader.

The model stays on this machine. If the weight files are not already under
the app's models directory or the PaddleX cache, the first check downloads
them. The window still opens when that download has not happened; a check
then reports that the reader is unavailable.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from blacklist_detect.model import OcrLine

# A read below this is 未看清 and is not matched.
NAME_CONFIDENCE_MIN = 0.55

_ENGINE: OcrEngine | None = None


class OcrUnavailable(RuntimeError):
    """The local Chinese model could not be loaded."""


def model_dirs() -> tuple[Path | None, Path | None]:
    """Detection and recognition dirs, if the user or the repo already has them."""
    roots: list[Path] = []
    env = os.environ.get("BLACKLIST_DETECT_MODEL_DIR")
    if env:
        roots.append(Path(env))
    roots.append(Path(__file__).resolve().parent / "models")
    roots.append(Path.cwd() / "models")
    for root in roots:
        if not root.is_dir():
            continue
        det = _find_model_dir(root, "det")
        rec = _find_model_dir(root, "rec")
        if det and rec:
            return det, rec
    return None, None


def models_are_cached() -> bool:
    det, rec = model_dirs()
    if det and rec:
        return True
    cache = Path.home() / ".paddlex" / "official_models"
    if not cache.is_dir():
        return False
    names = {path.name for path in cache.iterdir()}
    return any("det" in name for name in names) and any("rec" in name for name in names)


def _find_model_dir(root: Path, kind: str) -> Path | None:
    if (root / "inference.yml").exists() or (root / "inference.json").exists() or (root / "inference.pdmodel").exists():
        label = root.name.lower()
        if kind in label:
            return root
    for child in sorted(root.iterdir()) if root.is_dir() else []:
        if not child.is_dir():
            continue
        label = child.name.lower()
        if kind not in label:
            continue
        if any((child / name).exists() for name in ("inference.yml", "inference.json", "inference.pdmodel", "inference.pdiparams")):
            return child
        # A directory of weights is enough for PaddleOCR 3 to accept model_dir.
        if any(child.iterdir()):
            return child
    return None


class OcrEngine:
    def __init__(self) -> None:
        self._ocr = None
        self._name_rec = None

    def warmup(self) -> None:
        self._ensure()
        self._ensure_name_rec()
        blank = np.zeros((32, 160, 3), dtype=np.uint8)
        self.read_bgr(blank)
        self.read_name(blank)

    def read_bgr(self, bgr: np.ndarray) -> list[OcrLine]:
        engine = self._ensure()
        if hasattr(engine, "predict"):
            try:
                result = engine.predict(bgr)
            except TypeError:
                result = engine.predict(input=bgr)
        else:
            result = engine.ocr(bgr, cls=False)
        return parse_ocr_output(result)

    def read_name(self, rgb: np.ndarray) -> tuple[str, float]:
        """Read one name strip. Recognition only, on a tightened line."""
        return self.read_names([rgb])[0]

    def read_names(self, images: list[np.ndarray]) -> list[tuple[str, float]]:
        """Read every name strip in one pass."""
        results: list[tuple[str, float]] = [("", 0.0)] * len(images)
        prepared: list[np.ndarray] = []
        indexes: list[int] = []
        for index, rgb in enumerate(images):
            if rgb.size == 0 or rgb.shape[0] < 4 or rgb.shape[1] < 4:
                continue
            prepared.append(prepare_name_line(rgb))
            indexes.append(index)
        if not prepared:
            return results
        rec = self._ensure_name_rec()
        try:
            batch = rec.predict(prepared)
        except TypeError:
            batch = rec.predict(input=prepared)
        except Exception:
            batch = None
        parsed = list(batch) if isinstance(batch, (list, tuple)) else []
        if len(parsed) != len(prepared):
            for index, image in zip(indexes, prepared):
                try:
                    one = rec.predict(image)
                except TypeError:
                    one = rec.predict(input=image)
                results[index] = _recognition_text(one)
            return results
        for index, item in zip(indexes, parsed):
            results[index] = _recognition_text([item])
        return results

    def _ensure(self):
        if self._ocr is not None:
            return self._ocr
        # Skip the host check once weights are on disk. A missing model still errors clearly.
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        os.environ.setdefault("FLAGS_use_mkldnn", "0")
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise OcrUnavailable(
                "没有安装 PaddleOCR。按 README 安装 paddlepaddle 和 paddleocr 后再检查名字。"
            ) from exc
        kwargs: dict = {
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
            "text_detection_model_name": "PP-OCRv5_mobile_det",
            "text_recognition_model_name": "PP-OCRv5_mobile_rec",
        }
        det, rec = model_dirs()
        if det and rec:
            kwargs["text_detection_model_dir"] = str(det)
            kwargs["text_recognition_model_dir"] = str(rec)
        try:
            self._ocr = PaddleOCR(**kwargs)
        except TypeError:
            self._ocr = PaddleOCR(use_angle_cls=False, lang="ch", show_log=False)
        except Exception as exc:
            raise OcrUnavailable(
                "本地 PaddleOCR 中文模型没有就绪。"
                "联网时运行 python -m blacklist_detect download-models，"
                "或把模型目录放到环境变量 BLACKLIST_DETECT_MODEL_DIR。"
                f" 详情：{exc}"
            ) from exc
        return self._ocr

    def _ensure_name_rec(self):
        if self._name_rec is not None:
            return self._name_rec
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        os.environ.setdefault("FLAGS_use_mkldnn", "0")
        try:
            from paddleocr import TextRecognition
        except ImportError as exc:
            raise OcrUnavailable(
                "没有安装 PaddleOCR，不能读取名字。"
            ) from exc
        try:
            self._name_rec = TextRecognition(model_name="PP-OCRv5_mobile_rec")
        except Exception as exc:
            raise OcrUnavailable(
                "本地 PaddleOCR 中文识别模型没有就绪。"
                "联网时运行 python -m blacklist_detect download-models。"
                f" 详情：{exc}"
            ) from exc
        return self._name_rec


def get_engine() -> OcrEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = OcrEngine()
    return _ENGINE


def parse_ocr_output(result) -> list[OcrLine]:
    if result is None:
        return []
    if isinstance(result, list) and result and _looks_like_v2(result):
        page = result[0] if isinstance(result[0], list) else result
        return _parse_v2(page)
    items = result if isinstance(result, (list, tuple)) else [result]
    lines: list[OcrLine] = []
    for item in items:
        if item is None:
            continue
        mapped = _as_mapping(item)
        if mapped and "rec_texts" in mapped:
            lines.extend(_lines_from_mapped(mapped))
        elif isinstance(item, list):
            lines.extend(_parse_v2(item))
    return lines


def _looks_like_v2(result) -> bool:
    page = result[0] if result and isinstance(result[0], list) else None
    if not page or not isinstance(page, list) or not page[0]:
        return False
    first = page[0]
    return isinstance(first, (list, tuple)) and len(first) >= 2 and isinstance(first[0], (list, tuple))


def _as_mapping(item):
    if isinstance(item, dict):
        if "rec_texts" in item:
            return item
        inner = item.get("res")
        if isinstance(inner, dict) and "rec_texts" in inner:
            return inner
        return None
    json_attr = getattr(item, "json", None)
    if json_attr is not None:
        payload = json_attr() if callable(json_attr) else json_attr
        mapped = _as_mapping(payload) if not isinstance(payload, (str, bytes)) else None
        if mapped:
            return mapped
    try:
        if "rec_texts" in item:
            return item
    except Exception:
        return None
    return None


def _lines_from_mapped(payload: dict) -> list[OcrLine]:
    texts = list(payload.get("rec_texts") or [])
    scores = list(payload.get("rec_scores") or [])
    boxes = payload.get("rec_boxes")
    polys = payload.get("rec_polys")
    lines: list[OcrLine] = []
    for index, text in enumerate(texts):
        if text is None or str(text).strip() == "":
            continue
        score = float(scores[index]) if index < len(scores) else 0.0
        box = _box_at(boxes, index) or _box_at(polys, index) or (0.0, 0.0, 0.0, 0.0)
        lines.append(OcrLine(str(text), score, box))
    return lines


def _box_at(collection, index: int):
    if collection is None:
        return None
    try:
        raw = collection[index]
    except Exception:
        return None
    return _as_box(raw)


def _as_box(raw) -> tuple[float, float, float, float] | None:
    if raw is None:
        return None
    values = raw.tolist() if hasattr(raw, "tolist") else raw
    try:
        flat = [float(value) for value in values]
    except TypeError:
        flat = []
    if len(flat) == 4:
        return (flat[0], flat[1], flat[2], flat[3])
    points = []
    for point in values:
        try:
            points.append((float(point[0]), float(point[1])))
        except Exception:
            return None
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _parse_v2(page) -> list[OcrLine]:
    lines: list[OcrLine] = []
    if not page:
        return lines
    for line in page:
        if not line or len(line) < 2:
            continue
        box = _as_box(line[0]) or (0.0, 0.0, 0.0, 0.0)
        text_score = line[1]
        if isinstance(text_score, (list, tuple)) and len(text_score) >= 2:
            text, score = text_score[0], text_score[1]
        else:
            continue
        if str(text).strip():
            lines.append(OcrLine(str(text), float(score), box))
    return lines


def rgb_to_bgr(rgb: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(rgb[:, :, ::-1])


def downscale_rgb(rgb: np.ndarray, max_width: int = 1600) -> tuple[np.ndarray, float]:
    """Return a smaller RGB image and the factor to map boxes back to full size."""
    height, width = rgb.shape[:2]
    if width <= max_width:
        return rgb, 1.0
    scale = max_width / float(width)
    new_w = max(1, int(round(width * scale)))
    new_h = max(1, int(round(height * scale)))
    try:
        import cv2

        small = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
    except ImportError:
        from PIL import Image

        image = Image.fromarray(rgb).resize((new_w, new_h), Image.Resampling.BOX)
        small = np.array(image)
    return small, 1.0 / scale


def scale_lines(lines: list[OcrLine], factor: float) -> list[OcrLine]:
    if factor == 1.0:
        return lines
    scaled = []
    for line in lines:
        box = tuple(value * factor for value in line.box)
        scaled.append(OcrLine(line.text, line.confidence, box))  # type: ignore[arg-type]
    return scaled


def prepare_name_line(rgb: np.ndarray) -> np.ndarray:
    """Tighten to the light text, enlarge, and raise contrast. Returns BGR."""
    import cv2

    gray = rgb.max(axis=2)
    rows = np.where((gray >= 150).sum(axis=1) > 2)[0]
    if len(rows):
        top = max(0, int(rows[0]) - 2)
        bottom = min(rgb.shape[0], int(rows[-1]) + 3)
        rgb = rgb[top:bottom]
    height, width = rgb.shape[:2]
    enlarged = cv2.resize(
        rgb,
        (max(1, width * 2), max(1, height * 2)),
        interpolation=cv2.INTER_CUBIC,
    )
    gray = cv2.cvtColor(enlarged, cv2.COLOR_RGB2GRAY)
    low = float(np.percentile(gray, 5))
    high = float(np.percentile(gray, 98))
    if high <= low + 1:
        high = low + 1
    stretched = np.clip((gray.astype(np.float32) - low) * (255.0 / (high - low)), 0, 255).astype(np.uint8)
    inverted = cv2.cvtColor(255 - stretched, cv2.COLOR_GRAY2BGR)
    return cv2.copyMakeBorder(inverted, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=(255, 255, 255))


def _recognition_text(result) -> tuple[str, float]:
    items = result if isinstance(result, (list, tuple)) else [result]
    best_text = ""
    best_score = 0.0
    for item in items:
        if item is None:
            continue
        payload = item
        json_attr = getattr(item, "json", None)
        if json_attr is not None:
            payload = json_attr() if callable(json_attr) else json_attr
        if isinstance(payload, dict) and "res" in payload and isinstance(payload["res"], dict):
            payload = payload["res"]
        if not isinstance(payload, dict):
            continue
        text = payload.get("rec_text")
        score = payload.get("rec_score")
        if text is None and payload.get("rec_texts"):
            text = "".join(str(part) for part in payload["rec_texts"])
            scores = list(payload.get("rec_scores") or [0])
            score = min(float(value) for value in scores) if scores else 0.0
        if not text:
            continue
        score_f = float(score or 0.0)
        cleaned = "".join(str(text).split())
        if score_f >= best_score and cleaned:
            best_text = cleaned
            best_score = score_f
    return best_text, best_score
