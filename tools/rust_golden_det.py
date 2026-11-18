"""Golden data for the Rust OCR's detection side (rust/ocr): what blacklist_detect/onnx_ocr.py finds on the reference
lobby and ten corpus frames. Saves boxes, scores and crop checksums, never the images or any text read.

    python tools/rust_golden_det.py <det model dir> <corpus dir> [frames out dir]

The model dir holds inference.onnx and inference.yml; the corpus is tests/lobby_corpus of the data/lobby-corpus branch.
Each decoded frame is written as a lossless PNG to the frames dir (default /tmp/ocr-golden-frames, never committed), so
the Rust tests start from the same pixels without decoding JPEG themselves.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from blacklist_detect import onnx_ocr  # noqa: E402

OUT = ROOT / "rust" / "ocr" / "tests" / "golden" / "det.json"
FRAMES = 10


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def png_name(name: str) -> str:
    return name.replace("/", "_").rsplit(".", 1)[0] + ".png"


def frame_record(det: onnx_ocr.TextDetector, path: Path, name: str, frames_out: Path) -> dict:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    cv2.imwrite(str(frames_out / png_name(name)), image)
    params = onnx_ocr.DET_PARAMS
    resized, shape = onnx_ocr.det_resize(image, params["limit_side_len"], params["limit_type"], params["max_side_limit"])
    found = next(iter(det([image])))
    polys = found["dt_polys"]
    ordered = onnx_ocr.sort_boxes(polys)
    crops = onnx_ocr.crop_by_polys(image, ordered) if len(ordered) else []
    return {
        "name": name,
        "png": png_name(name),
        "decoded_sha256": sha(np.ascontiguousarray(image).tobytes()),
        "resized_sha256": sha(np.ascontiguousarray(resized).tobytes()),
        "shape": [float(v) for v in shape],
        "polys": np.asarray(polys).reshape(-1, 4, 2).tolist(),
        "scores": [float(s) for s in found["dt_scores"]],
        "sorted": [np.asarray(p).tolist() for p in ordered],
        "crops": [{"h": int(c.shape[0]), "w": int(c.shape[1]), "sha256": sha(np.ascontiguousarray(c).tobytes())} for c in crops],
    }


def main() -> None:
    model, corpus = Path(sys.argv[1]), Path(sys.argv[2])
    frames_out = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("/tmp/ocr-golden-frames")
    frames_out.mkdir(parents=True, exist_ok=True)
    det = onnx_ocr.TextDetector(model)
    frames = [("fixtures/reference-lobby.png", ROOT / "tests" / "fixtures" / "reference-lobby.png")]
    names = sorted(p.name for p in corpus.glob("*.jpg"))
    step = max(1, len(names) // FRAMES)
    frames += [(f"corpus/{name}", corpus / name) for name in names[::step][:FRAMES]]
    records = [frame_record(det, path, name, frames_out) for name, path in frames]
    from blacklist_detect.paths import ocr_threads

    threads = os.environ.get("PADDLE_PDX_CPU_NUM_THREADS", "") or ocr_threads()
    golden = {"threads": int(threads), "alpha": det.alpha, "beta": det.beta, "params": onnx_ocr.DET_PARAMS, "opencv": cv2.__version__,
              "frames": records}
    OUT.write_text(json.dumps(golden, indent=1) + "\n", encoding="utf-8")
    print(f"{len(records)} frames, {sum(len(r['polys']) for r in records)} boxes -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
