"""Golden data for the Rust port of name recognition (rust/ocr/src/rec): what the Python app reads on each name strip.

Runs the ONNX Runtime reference (blacklist_detect/onnx_ocr.py, ocr_engine.py's name preparation) on the twelve name
crops of the first lobby-corpus frames, as pipeline.py finds and cuts them. Writes the crops as PNG to --crops (out
of git: they show real names) and, under --out, one JSON with per strip the checksums of the crop and the prepared
images and the texts and scores. The Rust tests read both.

    BLACKLIST_DETECT_ENGINE=onnxruntime PYTHONPATH=. venv/bin/python tools/rust_golden_rec.py \
        --corpus /tmp/corpus/tests/lobby_corpus --models /tmp/rec/onnx --crops /tmp/rec/crops

--models holds PP-OCRv5_mobile_det, PP-OCRv5_mobile_rec and PP-OCRv6_medium_rec, each with inference.onnx (paddle2onnx,
opset 11) and inference.yml.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

STRIPS = 200


def checksum(image: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(image).tobytes()).hexdigest()


def reads(rec, images: list[np.ndarray]) -> list[dict]:  # noqa: ANN001
    return [{"text": item["rec_text"], "score": item["rec_score"]} for item in rec.predict(images)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--crops", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("rust/ocr/tests/golden/rec"))
    args = parser.parse_args()
    os.environ["BLACKLIST_DETECT_ENGINE"] = "onnxruntime"
    os.environ["BLACKLIST_DETECT_MODEL_DIR"] = str(args.models)

    from blacklist_detect import ocr_engine, pipeline
    from blacklist_detect.onnx_ocr import TextRecognizer

    engine = ocr_engine.OcrEngine()
    v6 = TextRecognizer(args.models / "PP-OCRv6_medium_rec", batch_size=12)
    v5 = TextRecognizer(args.models / "PP-OCRv5_mobile_rec", batch_size=12)
    args.crops.mkdir(parents=True, exist_ok=True)
    frames, total = [], 0
    for path in sorted(args.corpus.glob("*.jpg")):
        if total >= STRIPS:
            break
        rgb = np.array(Image.open(path).convert("RGB"))
        anchor, _lines = pipeline._locate(engine, rgb)
        if not anchor.found:
            print(f"{path.name}: no lobby")
            continue
        crops = [pipeline._crop(rgb, box, anchor.scale) for box in anchor.name_boxes][: STRIPS - total]
        prepared = [ocr_engine.prepare_name_line(crop) for crop in crops]
        plain = [ocr_engine.prepare_name_line_plain(crop) for crop in crops]
        final = engine.read_names(crops)
        primary, alternate, mobile = reads(v6, prepared), reads(v6, plain), reads(v5, prepared)
        # opencv-python resizes INTER_CUBIC through Intel IPP; an OpenCV built without IPP (Ubuntu's libopencv) gives
        # other pixels at non-integer scales. The same reads without IPP show the port is exact apart from that.
        cv2.ipp.setUseIPP(False)
        plain_noipp = [ocr_engine.prepare_name_line_plain(crop) for crop in crops]
        alternate_noipp, final_noipp = reads(v6, plain_noipp), engine.read_names(crops)
        cv2.ipp.setUseIPP(True)
        strips = []
        for slot, crop in enumerate(crops):
            name = f"{path.stem}_{slot:02d}.png"
            Image.fromarray(crop).save(args.crops / name)
            strips.append({
                "crop": name, "crop_sha": checksum(crop),
                "prepared_shape": list(prepared[slot].shape), "prepared_sha": checksum(prepared[slot]),
                "plain_shape": list(plain[slot].shape), "plain_sha": checksum(plain[slot]),
                "v6": primary[slot], "v6_plain": alternate[slot], "v5": mobile[slot],
                "final": {"text": final[slot][0], "score": final[slot][1]},
                "noipp": {"plain_sha": checksum(plain_noipp[slot]), "v6_plain": alternate_noipp[slot],
                          "final": {"text": final_noipp[slot][0], "score": final_noipp[slot][1]}},
            })
        frames.append({"frame": path.name, "strips": strips})
        total += len(strips)
        print(f"{path.name}: {len(strips)} strips")
    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "strips.json", "w", encoding="utf-8") as handle:
        json.dump({"frames": frames}, handle, ensure_ascii=False, indent=1)
    print(f"{total} strips in {len(frames)} frames")


if __name__ == "__main__":
    main()
