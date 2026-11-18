"""Record every network run of the app's check on stock ONNX Runtime, for the tract comparison (ort_tract/).

    python tools/size/ort_tract_dump.py <models dir> <out dir> <image or folder> [...]

Runs the app's own check (engine_bench.app_engine("onnxruntime"), the Python reader on the stock onnxruntime package)
on every image and writes each session.run as <out>/<n>.json (model, input and output shapes, the ORT seconds) beside
<n>.in.bin and <n>.out.bin (float32, little endian). The cases hold lobby pixels: keep <out> local and delete it after.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str]) -> int:
    models, out = Path(argv[0]), Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="tract-dump-")
    sys.path.insert(0, str(ROOT))
    import numpy as np
    import onnxruntime as ort

    from tools.engine_bench import app_engine, lobby_images, read_image

    real_run, count = ort.InferenceSession.run, [0]

    def run(self, output_names, input_feed, run_options=None):  # noqa: ANN001, ANN202
        started = time.perf_counter()
        result = real_run(self, output_names, input_feed, run_options)
        seconds = time.perf_counter() - started
        (value,), first = input_feed.values(), result[0]
        n = count[0] = count[0] + 1
        np.ascontiguousarray(value, dtype="<f4").tofile(out / f"{n}.in.bin")
        np.ascontiguousarray(first, dtype="<f4").tofile(out / f"{n}.out.bin")
        model = Path(self._model_path).parent.name
        meta = {"model": model, "input": list(value.shape), "output": list(first.shape), "ort_seconds": seconds}
        (out / f"{n}.json").write_text(json.dumps(meta), "utf-8")
        return result

    engine = app_engine("onnxruntime", models)
    count[0], before = 0, len(list(out.glob("*.json")))
    for stale in out.glob("*"):
        stale.unlink()
    ort.InferenceSession.run = run
    images = [p for folder in argv[2:] for p in lobby_images(Path(folder))]
    for path in images:
        read_image(engine, path, 1)
    print(f"{len(images)} images, {count[0]} network runs recorded (cleared {before} old)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
