"""Local PaddleOCR Chinese reader.

The model stays on this machine. If the weight files are not already under
the app's models directory or the PaddleX cache, the first check downloads
them. The window still opens when that download has not happened; a check
then reports that the reader is unavailable.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import numpy as np

from blacklist_detect.model import OcrLine

# A read below this is 未看清 and is not matched.
NAME_CONFIDENCE_MIN = 0.55
# The 推演成功 glance reads only the tallest few lines shaped like the title. See read_tallest_lines.
TITLE_CANDIDATES = 4
# Four characters measure about 3 to 3.5 times as wide as tall at any window size.
TITLE_SHAPE = (2.0, 6.0)

_ENGINE: OcrEngine | None = None
_CONSOLE_HIDDEN = False


def silence_console_children() -> None:
    """Stop Paddle's `where` lookups from opening a console window.

    On Windows, the first check imports Paddle's compiler helpers, which run
    `where ccache` and `where nvcc`. pythonw has no console, so each of those
    opens an empty window and closes it. Those tools are not needed to read names.
    """
    global _CONSOLE_HIDDEN
    if _CONSOLE_HIDDEN or sys.platform != "win32":
        return
    import subprocess

    original_check_output = subprocess.check_output
    original_popen = subprocess.Popen

    def check_output(args, *pargs, **kwargs):
        command = args[0] if isinstance(args, (list, tuple)) and args else args
        name = os.path.basename(str(command)).lower()
        if name in {"where", "where.exe", "which"}:
            raise subprocess.CalledProcessError(1, args, output=b"")
        return original_check_output(args, *pargs, **kwargs)

    class QuietPopen(original_popen):
        def __init__(self, args, *pargs, **kwargs):
            kwargs["creationflags"] = int(kwargs.get("creationflags", 0)) | 0x08000000
            info = kwargs.get("startupinfo") or subprocess.STARTUPINFO()
            info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            info.wShowWindow = 0
            kwargs["startupinfo"] = info
            super().__init__(args, *pargs, **kwargs)

    subprocess.check_output = check_output
    subprocess.Popen = QuietPopen
    _CONSOLE_HIDDEN = True


def inference_device() -> str:
    """Run on the NVIDIA GPU when this Paddle build can see one."""
    silence_console_children()
    try:
        import paddle

        if paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
            return "gpu:0"
    except Exception:
        return "cpu"
    return "cpu"


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


def bundled_model(name: str) -> Path | None:
    """A model folder shipped beside the app, so a check does not need to download it."""
    roots: list[Path] = []
    env = os.environ.get("BLACKLIST_DETECT_MODEL_DIR")
    if env:
        roots.append(Path(env))
    roots.append(Path(__file__).resolve().parent / "models")
    roots.append(Path.cwd() / "models")
    for root in roots:
        candidate = root / name
        if candidate.is_dir():
            return candidate
    return None


def _short_path(path: Path) -> Path:
    """Windows' 8.3 name for a folder. Some disks have 8.3 names turned off; then the path comes back unchanged."""
    if sys.platform != "win32":
        return path
    import ctypes

    buffer = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, len(buffer)):
        return Path(buffer.value)
    return path


def _ascii_cache_roots() -> list[Path]:
    """Where a copy of the models may go. A Chinese user name is reached by its short name."""
    roots: list[Path] = []
    for key in ("LOCALAPPDATA", "PROGRAMDATA"):
        value = os.environ.get(key)
        if value and Path(value).is_dir():
            roots.append(_short_path(Path(value)) / "BlackListDetect" / "models")
    return roots


# Download bookkeeping from the model hub. Paddle does not read it, and its paths are the deepest.
_SKIP_IN_COPY = ".cache"


def _same_files(source: Path, target: Path) -> bool:
    if not target.is_dir():
        return False
    for item in source.rglob("*"):
        if _SKIP_IN_COPY in item.relative_to(source).parts:
            continue
        if item.is_file():
            copy = target / item.relative_to(source)
            if not copy.is_file() or copy.stat().st_size != item.stat().st_size:
                return False
    return True


def paddle_safe_dir(folder: Path, cache_roots: list[Path] | None = None) -> Path:
    """A path to this model folder that Paddle can open.

    Paddle cannot open model files under a path with Chinese characters in it,
    for example a 黑名单检测 folder or a Chinese Windows user name. Such a folder
    is reached by its 8.3 short name, or else copied once to an ASCII folder.
    """
    if str(folder).isascii():
        return folder
    short = _short_path(folder)
    if str(short).isascii() and short.is_dir():
        return short
    for root in cache_roots if cache_roots is not None else _ascii_cache_roots():
        target = root / folder.name
        if not str(target).isascii():
            continue
        try:
            if not _same_files(folder, target):
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(folder, target, ignore=shutil.ignore_patterns(_SKIP_IN_COPY))
        except OSError:
            continue
        return target
    return folder


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

    def read_tallest_lines(self, bgr: np.ndarray, keep: int = TITLE_CANDIDATES) -> list[OcrLine]:
        """Find every text line, but read only the tallest ones. For the 推演成功 glance.

        Finding lines is cheap; reading them is not. A desktop full of text has
        dozens of lines and took five seconds a glance on a CPU. The title is the
        tallest title-shaped line on the screen whenever the full read can see
        it at all (tried with the lobby in windows from 960 px to full screen on
        a busy 4K desktop), so reading the tallest few such lines is enough.
        Lines are found, sorted, and cropped exactly as PaddleOCR's own pipeline
        does, so a line that is read gives the same text as the full read.
        """
        engine = self._ensure()
        inner = getattr(getattr(engine, "paddlex_pipeline", None), "_pipeline", None)
        det = getattr(inner, "text_det_model", None)
        rec = getattr(inner, "text_rec_model", None)
        sort_boxes = getattr(inner, "_sort_boxes", None)
        crop = getattr(inner, "_crop_by_polys", None)
        if det is None or rec is None or sort_boxes is None or crop is None:
            return self.read_bgr(bgr)
        found = next(iter(det([bgr], **inner.get_text_det_params())))
        polys = list(sort_boxes(found["dt_polys"]))
        if not polys:
            return []
        crops = list(crop(bgr, polys))
        candidates = []
        for poly, sub in zip(polys, crops, strict=False):
            box = _as_box(poly)
            if box is None or sub.size == 0:
                continue
            width, height = box[2] - box[0], box[3] - box[1]
            # Single characters and long sentences are never the title, and long ones are slow to read.
            if height <= 0 or not TITLE_SHAPE[0] <= width / height <= TITLE_SHAPE[1]:
                continue
            candidates.append((height, box, sub))
        candidates.sort(key=lambda item: item[0], reverse=True)
        chosen = candidates[:keep]
        if not chosen:
            return []
        lines: list[OcrLine] = []
        for (_height, box, _sub), result in zip(chosen, rec([item[2] for item in chosen]), strict=False):
            text, score = _recognition_text([result])
            if text and score >= inner.text_rec_score_thresh:
                lines.append(OcrLine(text, score, box))
        return lines

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
        primary = _predict_batch(rec, prepared)
        if len(primary) != len(prepared):
            for slot, image in zip(indexes, prepared, strict=False):
                results[slot] = _recognition_text(_predict_one(rec, image))
            return results
        blank_slots: list[int] = []
        for slot, first in zip(indexes, primary, strict=False):
            results[slot] = _recognition_text([first])
            if not results[slot][0]:
                blank_slots.append(slot)
        if not blank_slots:
            return results
        alternate = _predict_batch(rec, [prepare_name_line_plain(images[slot]) for slot in blank_slots])
        if len(alternate) != len(blank_slots):
            return results
        for slot, second in zip(blank_slots, alternate, strict=False):
            results[slot] = choose_name_read(results[slot], _recognition_text([second]))
        return results

    def _ensure(self):
        if self._ocr is not None:
            return self._ocr
        # Skip the host check once weights are on disk. A missing model still errors clearly.
        silence_console_children()
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
            "text_recognition_batch_size": 16,
            "device": inference_device(),
        }
        det, rec = model_dirs()
        if det and rec:
            kwargs["text_detection_model_dir"] = str(paddle_safe_dir(det))
            kwargs["text_recognition_model_dir"] = str(paddle_safe_dir(rec))
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
        silence_console_children()
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        os.environ.setdefault("FLAGS_use_mkldnn", "0")
        try:
            from paddleocr import TextRecognition
        except ImportError as exc:
            raise OcrUnavailable(
                "没有安装 PaddleOCR，不能读取名字。"
            ) from exc
        try:
            name_kwargs: dict = {
                "model_name": "PP-OCRv6_medium_rec",
                "device": inference_device(),
            }
            local_rec = bundled_model("PP-OCRv6_medium_rec")
            if local_rec is not None:
                name_kwargs["model_dir"] = str(paddle_safe_dir(local_rec))
            self._name_rec = TextRecognition(**name_kwargs)
            sampler = getattr(self._name_rec.paddlex_predictor, "batch_sampler", None)
            if sampler is not None:
                sampler.batch_size = 12
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


def _bottom_text_band(rgb: np.ndarray) -> np.ndarray:
    """Keep the name line. The portrait above it is bright too, so the first bright row is not the name."""
    gray = rgb.max(axis=2)
    ink = (gray >= 150).sum(axis=1)
    need = max(4, int(rgb.shape[1] * 0.03))
    active = ink > need
    groups: list[tuple[int, int]] = []
    start = None
    for index, on in enumerate(active):
        if on and start is None:
            start = index
        elif not on and start is not None:
            if index - start >= 3:
                groups.append((start, index))
            start = None
    if start is not None and len(active) - start >= 3:
        groups.append((start, len(active)))
    if not groups:
        return rgb
    top, bottom = groups[-1]
    for begin, end in reversed(groups[:-1]):
        if top - end <= 6:
            top = begin
        else:
            break
    top = max(0, top - 8)
    bottom = min(rgb.shape[0], bottom + 6)
    return rgb[top:bottom]


def prepare_name_line(rgb: np.ndarray) -> np.ndarray:
    """Tighten to the name line, enlarge, and raise contrast. Returns BGR."""
    import cv2

    rgb = _bottom_text_band(rgb)
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


def prepare_name_line_plain(rgb: np.ndarray) -> np.ndarray:
    """Read the same strip at the recognizer's height, without cutting a band out of it."""
    import cv2

    height, width = rgb.shape[:2]
    if height < 2 or width < 2:
        return prepare_name_line(rgb)
    target = 48
    scale = target / float(height)
    enlarged = cv2.resize(
        rgb,
        (max(1, int(round(width * scale))), target),
        interpolation=cv2.INTER_CUBIC,
    )
    gray = cv2.cvtColor(enlarged, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (0, 0), 0.8)
    sharp = cv2.addWeighted(gray, 1.5, blur, -0.5, 0)
    low = float(np.percentile(sharp, 10))
    high = float(np.percentile(sharp, 97))
    if high <= low + 1:
        high = low + 1
    stretched = np.clip((sharp.astype(np.float32) - low) * (255.0 / (high - low)), 0, 255).astype(np.uint8)
    ink = cv2.cvtColor(255 - stretched, cv2.COLOR_GRAY2BGR)
    return cv2.copyMakeBorder(ink, 8, 8, 12, 12, cv2.BORDER_CONSTANT, value=(255, 255, 255))


def _letters(text: str) -> str:
    kept = []
    for ch in text.casefold():
        if ch.isalnum() or "\u4e00" <= ch <= "\u9fff":
            kept.append(ch)
    return "".join(kept)


def choose_name_read(primary: tuple[str, float], alternate: tuple[str, float]) -> tuple[str, float]:
    """Keep the surer read of the same strip. A small confidence edge does not replace the primary."""
    text_a, score_a = primary
    text_b, score_b = alternate
    if not text_b:
        return primary
    if not text_a:
        return alternate
    if _letters(text_a) == _letters(text_b):
        return primary if score_a >= score_b else alternate
    if score_b >= score_a + 0.08:
        return alternate
    return primary


def _predict_one(rec, image: np.ndarray):
    try:
        return rec.predict(image)
    except TypeError:
        return rec.predict(input=image)


def _predict_batch(rec, images: list[np.ndarray]):
    try:
        batch = rec.predict(images)
    except TypeError:
        batch = rec.predict(input=images)
    except Exception:
        return []
    parsed = list(batch) if isinstance(batch, (list, tuple)) else []
    if len(parsed) != len(images):
        return []
    return parsed


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
