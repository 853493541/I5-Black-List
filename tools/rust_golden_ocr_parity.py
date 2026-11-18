"""Prove the Rust reader (rust/ocr through rust/pyocr) reads every lobby exactly as the Python ONNX reader does.

    python tools/rust_golden_ocr_parity.py <models dir> <out dir> <image or folder> [...] [--repeat 3] [--threads N]

<models dir> holds PP-OCRv5_mobile_det, PP-OCRv5_mobile_rec and PP-OCRv6_medium_rec, each an inference.onnx (paddle2onnx
2.1.0, opset 11) beside its inference.yml. Two levels, image by image:

- the full read of the frame: onnx_ocr.OnnxOcr.predict against pyocr.Ocr.predict: every line's text, box, quad and score;
- the app's check (pipeline.check_rgb) on OcrEngine(backend="onnxruntime") against the same check with every OCR step in
  Rust (engine_bench.rust_engine): every name and its confidence, with the wall and CPU time of each check.

Pass rule: every text and name identical, every box identical, every confidence within 1e-4. The report (out dir/
parity.json and the printed summary) holds counts and gaps only, never a name. Runs in a data folder of its own.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOLERANCE = 1e-4


def timed(engine, path: Path, repeat: int) -> tuple[object, float, float]:  # noqa: ANN001
    """engine_bench.read_image's read, with the median wall and CPU seconds of one check."""
    from tools.engine_bench import read_image

    walls, cpus, read = [], [], None
    for _ in range(max(1, repeat)):
        cpu = time.process_time()
        read = read_image(engine, path, 1)
        cpus.append(time.process_time() - cpu)
        walls.append(read.seconds[0])
    return read, statistics.median(walls), statistics.median(cpus)


def frame_parity(python_ocr, rust_ocr, bgr) -> dict:  # noqa: ANN001
    """The full read of one frame on both readers: lines, identical texts, identical boxes, the largest score gap."""
    import numpy as np

    want, have = python_ocr.predict(bgr)[0], rust_ocr.predict(bgr)[0]
    pairs = list(zip(want["rec_texts"], have["rec_texts"], strict=False))
    boxes = sum(list(a) == list(b) for a, b in zip(want["rec_boxes"], have["rec_boxes"], strict=False))
    quads = sum(np.array_equal(np.asarray(a), np.asarray(b)) for a, b in zip(want["rec_polys"], have["rec_polys"], strict=False))
    gaps = [abs(float(a) - float(b)) for a, b in zip(want["rec_scores"], have["rec_scores"], strict=False)]
    return {"lines": len(want["rec_texts"]), "rust_lines": len(have["rec_texts"]), "texts": sum(a == b for a, b in pairs),
            "boxes": int(boxes), "quads": int(quads), "gap": max(gaps, default=0.0)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("models", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("images", type=Path, nargs="+")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--threads", type=int, default=os.cpu_count() or 4)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="data-", dir=args.out)
    os.environ["PADDLE_PDX_CPU_NUM_THREADS"] = str(args.threads)
    sys.path.insert(0, str(ROOT))

    from blacklist_detect.onnx_ocr import OnnxOcr
    from blacklist_detect.pipeline import load_rgb
    from tools.engine_bench import app_engine, compare, lobby_images, rust_engine

    images = [p for folder in args.images for p in lobby_images(folder)]
    det, rec = args.models / "PP-OCRv5_mobile_det", args.models / "PP-OCRv5_mobile_rec"
    python_engine, rust = app_engine("onnxruntime", args.models), rust_engine(args.models)
    python_ocr, rust_ocr = OnnxOcr(det, rec), rust._ensure()

    frames, checks = [], []
    for path in images:
        bgr = load_rgb(path)[:, :, ::-1].copy()
        frames.append({"image": path.name, **frame_parity(python_ocr, rust_ocr, bgr)})
        want, py_wall, py_cpu = timed(python_engine, path, args.repeat)
        have, rs_wall, rs_cpu = timed(rust, path, args.repeat)
        same, total, differences = compare([want], [have])
        gaps = [abs(a.confidence - b.confidence) for a, b in zip(want.names, have.names, strict=False)]
        checks.append({"image": path.name, "names": total, "identical": same, "differences": len(differences),
                       "found": [want.found, have.found], "gap": max(gaps, default=0.0),
                       "python": {"wall": py_wall, "cpu": py_cpu}, "rust": {"wall": rs_wall, "cpu": rs_cpu}})

    def median(key: str, side: str) -> float:
        return round(statistics.median(c[side][key] for c in checks), 4)

    report = {
        "images": len(images),
        "frame": {"lines": sum(f["lines"] for f in frames), "rust_lines": sum(f["rust_lines"] for f in frames),
                  "texts": sum(f["texts"] for f in frames), "boxes": sum(f["boxes"] for f in frames),
                  "quads": sum(f["quads"] for f in frames), "gap": max(f["gap"] for f in frames),
                  "frames_off": [f["image"] for f in frames
                                 if not f["lines"] == f["rust_lines"] == f["texts"] == f["boxes"] == f["quads"] or f["gap"] > TOLERANCE]},
        "check": {"names": sum(c["names"] for c in checks), "identical": sum(c["identical"] for c in checks),
                  "lobbies_found": [sum(c["found"][0] for c in checks), sum(c["found"][1] for c in checks)],
                  "gap": max(c["gap"] for c in checks),
                  "images_off": [c["image"] for c in checks if c["differences"] or c["gap"] > TOLERANCE],
                  "seconds": {side: {"wall": median("wall", side), "cpu": median("cpu", side)} for side in ("python", "rust")}},
        "threads": args.threads,
        "repeat": args.repeat,
    }
    report["verdict"] = "PASS" if not report["frame"]["frames_off"] and not report["check"]["images_off"] else "FAIL"
    (args.out / "parity.json").write_text(json.dumps({**report, "per_frame": frames, "per_check": checks}, indent=1), "utf-8")
    frame, check = report["frame"], report["check"]
    print(f"{report['verdict']}: {report['images']} images, {args.threads} threads")
    print(f"full read: lines {frame['rust_lines']}/{frame['lines']}, texts identical {frame['texts']}, boxes {frame['boxes']}, "
          f"quads {frame['quads']}, worst score gap {frame['gap']:.2e}, frames off {len(frame['frames_off'])}")
    print(f"check: names identical {check['identical']}/{check['names']}, lobbies found {check['lobbies_found']}, "
          f"worst confidence gap {check['gap']:.2e}, images off {len(check['images_off'])}")
    print(f"per check (median): python {check['seconds']['python']}, rust {check['seconds']['rust']}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
