"""Read text with ONNX Runtime alone: the app's models without Paddle, PaddleX or PaddleOCR.

The steps around the networks are ported from PaddleX 3.7.2, so a line reads exactly as it does there:
detection resize, normalise and DB post-processing (paddlex/inference/models/text_detection/processors.py),
the OCR pipeline's sorting, cropping and reading order (paddlex/inference/pipelines/ocr/pipeline.py,
pipelines/components/common/sort_boxes.py and crop_image_regions.py), and recognition resize, padding and
CTC decoding (paddlex/inference/models/text_recognition/predictor.py and processors.py). Only what the app
runs is kept: quad boxes, no orientation models, no word boxes. tools/engine_bench.py checks that every
name reads the same as on Paddle.

Ported code: Copyright (c) 2024 PaddlePaddle Authors. All Rights Reserved.
Licensed under the Apache License, Version 2.0 (http://www.apache.org/licenses/LICENSE-2.0).

Each model folder holds inference.onnx (the Paddle model converted with paddle2onnx) and the model's own
inference.yml, which gives the input size and the recognition dictionary.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np

# The settings PaddleOCR 3.7 runs PP-OCRv5 with (the pipeline's get_text_det_params and the DB post-process).
DET_PARAMS = {"limit_side_len": 64, "limit_type": "min", "thresh": 0.3, "max_side_limit": 4000, "box_thresh": 0.6, "unclip_ratio": 1.5}
MAX_CANDIDATES = 1000
MIN_SIZE = 3
REC_SCORE_THRESH = 0.0
LINE_BATCH = 16


def read_config(model_dir: Path) -> dict:
    import yaml

    with open(model_dir / "inference.yml", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def session(model_dir: Path):  # noqa: ANN201
    """An ONNX Runtime session for the model in this folder, on the CPU."""
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.log_severity_level = 3
    threads = os.environ.get("PADDLE_PDX_CPU_NUM_THREADS", "")
    if threads.isdigit() and int(threads) > 0:
        options.intra_op_num_threads = int(threads)
    # PP-OCRv6_medium_rec's activations go denormal; computed exactly, they made a check five times slower.
    options.add_session_config_entry("session.set_denormal_as_zero", "1")
    return ort.InferenceSession(str(model_dir / "inference.onnx"), options, providers=["CPUExecutionProvider"])


def _run(sess, batch: np.ndarray) -> np.ndarray:  # noqa: ANN001
    return sess.run(None, {sess.get_inputs()[0].name: np.ascontiguousarray(batch)})[0]


# ----- Detection -----


class TextDetector:
    """PP-OCRv5 detection: det([bgr, ...], **params) yields {"dt_polys", "dt_scores"} per image."""

    def __init__(self, model_dir: Path) -> None:
        config = read_config(model_dir)
        normalize = next(op["NormalizeImage"] for op in config["PreProcess"]["transform_ops"] if "NormalizeImage" in op)
        scale = normalize.get("scale", 1 / 255)
        scale = eval(scale, {}) if isinstance(scale, str) else scale  # "1./255." in the model's file
        mean, std = normalize["mean"], normalize["std"]
        self.alpha = [scale / std[i] for i in range(len(std))]
        self.beta = [-mean[i] / std[i] for i in range(len(std))]
        self.session = session(model_dir)

    def __call__(self, images: list[np.ndarray], limit_side_len=None, limit_type=None, thresh=None,  # noqa: ANN001
                 max_side_limit=None, box_thresh=None, unclip_ratio=None):
        params = {**DET_PARAMS}
        given = {"limit_side_len": limit_side_len, "limit_type": limit_type, "thresh": thresh, "max_side_limit": max_side_limit,
                 "box_thresh": box_thresh, "unclip_ratio": unclip_ratio}
        params.update({key: value for key, value in given.items() if value is not None})
        for image in images:
            resized, shape = det_resize(image, params["limit_side_len"], params["limit_type"], params["max_side_limit"])
            batch = np.stack([self.normalize(resized).transpose((2, 0, 1))], axis=0).astype(np.float32, copy=False)
            pred = _run(self.session, batch)
            polys, scores = db_boxes(pred[0][0], shape, params["thresh"], params["box_thresh"], params["unclip_ratio"])
            yield {"dt_polys": polys, "dt_scores": scores}

    def normalize(self, img: np.ndarray) -> np.ndarray:
        """NormalizeImage, order hwc: each channel scaled and shifted in float32, as cv2.split and merge do."""
        import cv2

        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        channels = list(cv2.split(img))
        for c in range(img.shape[2]):
            channels[c] = channels[c].astype(np.float32)
            channels[c] *= self.alpha[c]
            channels[c] += self.beta[c]
        return cv2.merge(channels)


def det_resize(img: np.ndarray, limit_side_len: int, limit_type: str, max_side_limit: int) -> tuple[np.ndarray, np.ndarray]:
    """DetResizeForTest, resize type 0: sides to multiples of 32. Returns the image and [h, w, ratio_h, ratio_w]."""
    import cv2

    src_h, src_w, _ = img.shape
    if sum([src_h, src_w]) < 64:
        padded = np.zeros((max(32, src_h), max(32, src_w), img.shape[2]), np.uint8)
        padded[:src_h, :src_w, :] = img
        img = padded
    h, w, _ = img.shape
    if limit_type == "max":
        ratio = float(limit_side_len) / (h if h > w else w) if max(h, w) > limit_side_len else 1.0
    elif limit_type == "min":
        ratio = float(limit_side_len) / (h if h < w else w) if min(h, w) < limit_side_len else 1.0
    elif limit_type == "resize_long":
        ratio = float(limit_side_len) / max(h, w)
    else:
        raise ValueError(f"limit type {limit_type!r}")
    resize_h, resize_w = int(h * ratio), int(w * ratio)
    if max(resize_h, resize_w) > max_side_limit:
        ratio = float(max_side_limit) / max(resize_h, resize_w)
        resize_h, resize_w = int(resize_h * ratio), int(resize_w * ratio)
    resize_h = max(int(round(resize_h / 32) * 32), 32)
    resize_w = max(int(round(resize_w / 32) * 32), 32)
    if resize_h == h and resize_w == w:
        return img, np.array([src_h, src_w, 1.0, 1.0])
    img = cv2.resize(img, (int(resize_w), int(resize_h)))
    return img, np.array([src_h, src_w, resize_h / float(h), resize_w / float(w)])


def db_boxes(pred: np.ndarray, shape: np.ndarray, thresh: float, box_thresh: float, unclip_ratio: float):  # noqa: ANN201
    """DBPostProcess, quad boxes, fast score: the boxes (int16, N x 4 x 2) and their scores."""
    import cv2

    bitmap = pred > thresh
    src_h, src_w = shape[0], shape[1]
    height, width = bitmap.shape
    width_scale, height_scale = src_w / width, src_h / height
    outs = cv2.findContours((bitmap * 255).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = outs[1] if len(outs) == 3 else outs[0]
    boxes, scores = [], []
    for contour in contours[:MAX_CANDIDATES]:
        points, sside = mini_box(contour)
        if sside < MIN_SIZE:
            continue
        points = np.array(points)
        score = box_score_fast(pred, points.reshape(-1, 2))
        if box_thresh > score:
            continue
        box, sside = mini_box(unclip(points, unclip_ratio).reshape(-1, 1, 2))
        if sside < MIN_SIZE + 2:
            continue
        box = np.array(box)
        for i in range(box.shape[0]):
            box[i, 0] = max(0, min(round(box[i, 0] * width_scale), src_w))
            box[i, 1] = max(0, min(round(box[i, 1] * height_scale), src_h))
        boxes.append(box.astype(np.int16))
        scores.append(score)
    return np.array(boxes, dtype=np.int16), scores


def unclip(box: np.ndarray, unclip_ratio: float) -> np.ndarray:
    import cv2
    import pyclipper

    distance = cv2.contourArea(box) * unclip_ratio / cv2.arcLength(box, True)
    offset = pyclipper.PyclipperOffset()
    offset.AddPath(box, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
    try:
        return np.array(offset.Execute(distance))
    except ValueError:
        return np.array(offset.Execute(distance)[0])


def _ordered_corners(points: list) -> list:
    """Four box corners sorted by x, put in order: top left, top right, bottom right, bottom left."""
    points = sorted(points, key=lambda x: x[0])
    first, fourth = (0, 1) if points[1][1] > points[0][1] else (1, 0)
    second, third = (2, 3) if points[3][1] > points[2][1] else (3, 2)
    return [points[first], points[second], points[third], points[fourth]]


def mini_box(contour: np.ndarray) -> tuple[list, float]:
    import cv2

    bounding_box = cv2.minAreaRect(contour)
    return _ordered_corners(list(cv2.boxPoints(bounding_box))), min(bounding_box[1])


def box_score_fast(bitmap: np.ndarray, box: np.ndarray) -> float:
    import cv2

    h, w = bitmap.shape[:2]
    box = box.copy()
    xmin = max(0, min(math.floor(box[:, 0].min()), w - 1))
    xmax = max(0, min(math.ceil(box[:, 0].max()), w - 1))
    ymin = max(0, min(math.floor(box[:, 1].min()), h - 1))
    ymax = max(0, min(math.ceil(box[:, 1].max()), h - 1))
    mask = np.zeros((ymax - ymin + 1, xmax - xmin + 1), dtype=np.uint8)
    box[:, 0] = box[:, 0] - xmin
    box[:, 1] = box[:, 1] - ymin
    cv2.fillPoly(mask, box.reshape(1, -1, 2).astype(np.int32), 1)
    return cv2.mean(bitmap[ymin : ymax + 1, xmin : xmax + 1], mask)[0]


def sort_boxes(dt_polys) -> list:  # noqa: ANN001
    """SortQuadBoxes: top to bottom, then left to right within 10 px of height."""
    dt_boxes = np.array(dt_polys)
    boxes = list(sorted(dt_boxes, key=lambda x: (x[0][1], x[0][0])))
    for i in range(dt_boxes.shape[0] - 1):
        for j in range(i, -1, -1):
            if abs(boxes[j + 1][0][1] - boxes[j][0][1]) < 10 and boxes[j + 1][0][0] < boxes[j][0][0]:
                boxes[j], boxes[j + 1] = boxes[j + 1], boxes[j]
            else:
                break
    return boxes


def crop_by_polys(img: np.ndarray, dt_polys) -> list[np.ndarray]:  # noqa: ANN001
    """CropByPolys, quad: each box's minimum-area rectangle, straightened."""
    import cv2

    crops = []
    for points in np.array(dt_polys):
        box = _ordered_corners(list(cv2.boxPoints(cv2.minAreaRect(np.array(points).astype(np.int32)))))
        crops.append(rotate_crop(img, np.array(box)))
    return crops


def rotate_crop(img: np.ndarray, points: np.ndarray) -> np.ndarray:
    import cv2

    width = int(max(np.linalg.norm(points[0] - points[1]), np.linalg.norm(points[2] - points[3])))
    height = int(max(np.linalg.norm(points[0] - points[3]), np.linalg.norm(points[1] - points[2])))
    target = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
    matrix = cv2.getPerspectiveTransform(points, target)
    crop = cv2.warpPerspective(img, matrix, (width, height), borderMode=cv2.BORDER_REPLICATE, flags=cv2.INTER_CUBIC)
    if crop.shape[0] * 1.0 / crop.shape[1] >= 1.5:
        crop = np.rot90(crop)
    return crop


# ----- Recognition -----


class TextRecognizer:
    """Line recognition: rec([bgr, ...]) yields {"rec_text", "rec_score"} per line, in batches as PaddleX makes them."""

    def __init__(self, model_dir: Path, batch_size: int = 1) -> None:
        config = read_config(model_dir)
        resize = next(op["RecResizeImg"] for op in config["PreProcess"]["transform_ops"] if "RecResizeImg" in op)
        self.image_shape = list(resize["image_shape"])
        # CTCLabelDecode: blank first, then the dictionary, then a space.
        self.characters = ["blank", *config["PostProcess"]["character_dict"], " "]
        self.batch_size = batch_size
        self.session = session(model_dir)

    def __call__(self, images: list[np.ndarray]):
        for start in range(0, len(images), self.batch_size):
            yield from self.read_batch(images[start : start + self.batch_size])

    def predict(self, images: list[np.ndarray] | np.ndarray) -> list[dict]:
        return list(self([images] if isinstance(images, np.ndarray) else list(images)))

    def read_batch(self, images: list[np.ndarray]) -> list[dict]:
        resized = [self.resize_norm(img) for img in images]
        widest = max(img.shape[2] for img in resized)
        padded = [np.pad(img, ((0, 0), (0, 0), (0, widest - img.shape[2])), mode="constant", constant_values=0) for img in resized]
        preds = _run(self.session, np.stack(padded, axis=0).astype(np.float32, copy=False))
        return [{"rec_text": text, "rec_score": score} for text, score in self.decode(preds)]

    def resize_norm(self, img: np.ndarray) -> np.ndarray:
        """OCRReisizeNormImg: height 48, width by the line's own shape (at most 3200), values to [-1, 1]."""
        import cv2

        channels, height, width = self.image_shape
        h, w = img.shape[:2]
        max_wh_ratio = max(width / height, w * 1.0 / h)
        width = int(height * max_wh_ratio)
        if width > 3200:
            image, resized_w, width = cv2.resize(img, (3200, height)), 3200, 3200
        else:
            ratio = w / float(h)
            resized_w = width if math.ceil(height * ratio) > width else int(math.ceil(height * ratio))
            image = cv2.resize(img, (resized_w, height))
        image = image.astype("float32").transpose((2, 0, 1)) / 255
        image -= 0.5
        image /= 0.5
        padded = np.zeros((channels, height, width), dtype=np.float32)
        padded[:, :, 0:resized_w] = image
        return padded

    def decode(self, preds: np.ndarray) -> list[tuple[str, float]]:
        """CTC: the best character per step, repeats and blanks dropped; the score is their mean probability."""
        indexes, probs = preds.argmax(axis=-1), preds.max(axis=-1)
        out = []
        for index, prob in zip(indexes, probs, strict=True):
            keep = np.ones(len(index), dtype=bool)
            keep[1:] = index[1:] != index[:-1]
            keep &= index != 0
            text = "".join(self.characters[i] for i in index[keep])
            confidence = prob[keep] if keep.any() else [0]
            out.append((text, np.mean(confidence).tolist()))
        return out


# ----- The OCR pipeline -----


class OnnxOcr:
    """What OcrEngine uses of PaddleOCR's pipeline, on ONNX Runtime: the two models, sorting, cropping, a full read."""

    text_rec_score_thresh = REC_SCORE_THRESH

    def __init__(self, det_dir: Path, rec_dir: Path) -> None:
        self.text_det_model = TextDetector(det_dir)
        self.text_rec_model = TextRecognizer(rec_dir, batch_size=LINE_BATCH)
        self._sort_boxes = sort_boxes
        self._crop_by_polys = crop_by_polys

    def get_text_det_params(self) -> dict:
        return dict(DET_PARAMS)

    def predict(self, bgr: np.ndarray) -> list[dict]:
        """Every line of the image, as the OCR pipeline reads it: lines narrowest first, then back in reading order."""
        found = next(iter(self.text_det_model([bgr], **DET_PARAMS)))
        polys = self._sort_boxes(found["dt_polys"])
        texts, scores, kept = [], [], []
        if polys:
            pairs = [(crop, poly) for crop, poly in zip(self._crop_by_polys(bgr, polys), polys, strict=True)
                     if crop.size > 0 and crop.shape[0] > 0 and crop.shape[1] > 0]
            order = sorted(range(len(pairs)), key=lambda i: pairs[i][0].shape[1] / float(pairs[i][0].shape[0]))
            reads: dict[int, dict] = {}
            for slot, result in zip(order, self.text_rec_model([pairs[i][0] for i in order]), strict=True):
                reads[slot] = result
            for slot, (_crop, poly) in enumerate(pairs):
                if reads[slot]["rec_score"] >= self.text_rec_score_thresh:
                    texts.append(reads[slot]["rec_text"])
                    scores.append(reads[slot]["rec_score"])
                    kept.append(poly)
        boxes = [[int(p[:, 0].min()), int(p[:, 1].min()), int(p[:, 0].max()), int(p[:, 1].max())] for p in map(np.asarray, kept)]
        return [{"rec_texts": texts, "rec_scores": scores, "rec_polys": kept, "rec_boxes": boxes}]
