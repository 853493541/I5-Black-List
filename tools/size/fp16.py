"""Store the OCR models' weights in FP16 and prove whether the reader still reads every lobby the same.

    python tools/size/fp16.py convert <fp32 models dir> <out dir>
    python tools/size/fp16.py parity <fp32 models dir> <variant models dir> <out json> <image or folder> [...]

<fp32 models dir> holds PP-OCRv5_mobile_det, PP-OCRv5_mobile_rec and PP-OCRv6_medium_rec, each an inference.onnx
(paddle2onnx 2.1.0, opset 11) beside its inference.yml. `convert` writes three variants of that folder under <out dir>:

- a-cast: every FP32 weight stored as FP16, a Cast back to FP32 in front of the graph (compute stays FP32; ONNX
  Runtime folds the Casts at load);
- a-upcast: the same weights rounded to FP16 and stored as FP32 again: what a loader that widens FP16 weights in Rust
  before creating the session would hand ONNX Runtime;
- b-fp16: onnxconverter-common's float16 conversion with keep_io_types (FP16 compute where ORT CPU has the kernels).

`parity` reads every image with the Python ONNX reader (onnx_ocr.OnnxOcr, which the Rust reader matches exactly) and the
app's check (OcrEngine backend onnxruntime) on both model folders: lines, texts, boxes, names, lobbies found, the largest
score gap and the time per check. The report holds counts, gaps and frame hashes only, never a name. Runs in a data
folder of its own.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = ("PP-OCRv5_mobile_det", "PP-OCRv5_mobile_rec", "PP-OCRv6_medium_rec")
VARIANTS = ("a-cast", "a-upcast", "b-fp16")
TOLERANCE = 1e-4
# Small constants (shapes, scales, epsilons) stay FP32: they weigh nothing and FP16 would round them.
MIN_ELEMENTS = 16


def _float_tensors(model):  # noqa: ANN001, ANN202
    """Every FP32 weight of the model: its initializers and the tensors of its Constant nodes (paddle2onnx 2.1.0 keeps
    every weight in a Constant node), as (holder, name) pairs."""
    from onnx import TensorProto

    found = [(init, init.name) for init in model.graph.initializer if init.data_type == TensorProto.FLOAT]
    for node in model.graph.node:
        if node.op_type == "Constant":
            found += [(attr.t, node.output[0]) for attr in node.attribute
                      if attr.name == "value" and attr.t.data_type == TensorProto.FLOAT and _count(attr.t) >= MIN_ELEMENTS]
    return found


def _count(tensor) -> int:  # noqa: ANN001
    total = 1
    for dim in tensor.dims:
        total *= dim
    return total


def _fp16_weights(model):  # noqa: ANN001, ANN202
    """The model with every FP32 weight stored as FP16 and widened again by a Cast right after it (compute stays FP32)."""
    import numpy as np
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    renames = {}
    for tensor, name in _float_tensors(model):
        tensor.CopyFrom(numpy_helper.from_array(numpy_helper.to_array(tensor).astype(np.float16), tensor.name))
        renames[name] = f"{name}__fp16"
    nodes = []
    for node in model.graph.node:
        outputs = [renames.get(out, out) for out in node.output]
        del node.output[:]
        node.output.extend(outputs)
        nodes.append(node)
        nodes += [helper.make_node("Cast", [renames[out]], [out], to=TensorProto.FLOAT, name=f"{out}__cast")
                  for out in renames if renames[out] in outputs]
    for init in model.graph.initializer:
        if init.name in renames:
            init.name = renames[init.name]
            nodes.insert(0, helper.make_node("Cast", [init.name], [init.name[:-6]], to=TensorProto.FLOAT))
    del model.graph.node[:]
    model.graph.node.extend(nodes)
    onnx.checker.check_model(model)
    return model


def _rounded(model):  # noqa: ANN001, ANN202
    """The model with every FP32 weight rounded through FP16, still stored as FP32: what a loader that widens the FP16
    weights before ONNX Runtime sees them would hand it."""
    import numpy as np
    from onnx import numpy_helper

    for tensor, _ in _float_tensors(model):
        back = numpy_helper.to_array(tensor).astype(np.float16).astype(np.float32)
        tensor.CopyFrom(numpy_helper.from_array(back, tensor.name))
    return model


def _fp16_compute(model):  # noqa: ANN001, ANN202
    from onnxconverter_common import float16

    return float16.convert_float_to_float16(model, keep_io_types=True)


def convert(source: Path, out: Path) -> dict:
    """The three variants of the models in `source`, under out/<variant>, and each model's size raw and zipped."""
    import onnx

    make = {"a-cast": _fp16_weights, "a-upcast": _rounded, "b-fp16": _fp16_compute}
    sizes = {"fp32": {name: sizes_of(source / name / "inference.onnx") for name in MODELS}}
    for variant in VARIANTS:
        sizes[variant] = {}
        for name in MODELS:
            target = out / variant / name
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(source / name, target)
            onnx.save(make[variant](onnx.load(str(source / name / "inference.onnx"))), str(target / "inference.onnx"))
            sizes[variant][name] = sizes_of(target / "inference.onnx")
    for sizes_by_model in sizes.values():
        sizes_by_model["total"] = {key: sum(v[key] for v in sizes_by_model.values()) for key in ("raw", "zipped")}
    return sizes


def sizes_of(path: Path) -> dict:
    with tempfile.TemporaryDirectory() as folder:
        packed = Path(folder) / "model.zip"
        with zipfile.ZipFile(packed, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.write(path, path.name)
        return {"raw": path.stat().st_size, "zipped": packed.stat().st_size}


def _frame(want: dict, have: dict) -> dict:
    import numpy as np

    pairs = list(zip(want["rec_texts"], have["rec_texts"], strict=False))
    boxes = sum(list(a) == list(b) for a, b in zip(want["rec_boxes"], have["rec_boxes"], strict=False))
    gaps = [abs(float(a) - float(b)) for a, b in zip(want["rec_scores"], have["rec_scores"], strict=False)]
    off = [i for i, (a, b) in enumerate(pairs) if a != b]
    quads = sum(np.array_equal(np.asarray(a), np.asarray(b)) for a, b in zip(want["rec_polys"], have["rec_polys"], strict=False))
    return {"lines": len(want["rec_texts"]), "variant_lines": len(have["rec_texts"]), "texts": len(pairs) - len(off),
            "boxes": int(boxes), "quads": int(quads), "gap": max(gaps, default=0.0), "lines_off": off}


def _check(engine, rgb, repeat: int):  # noqa: ANN001, ANN202
    from blacklist_detect.pipeline import check_rgb

    walls, result = [], None
    for _ in range(max(1, repeat)):
        engine.lobby_spot = None
        started = time.perf_counter()
        result = check_rgb(rgb, [], engine=engine)
        walls.append(time.perf_counter() - started)
    return result, statistics.median(walls)


def parity(fp32: Path, variant: Path, images: list[Path], repeat: int) -> dict:
    from blacklist_detect.onnx_ocr import OnnxOcr
    from blacklist_detect.pipeline import load_rgb
    from tools.engine_bench import app_engine

    readers = [OnnxOcr(root / MODELS[0], root / MODELS[1]) for root in (fp32, variant)]
    engines = [app_engine("onnxruntime", root) for root in (fp32, variant)]
    frames = []
    for path in images:
        rgb = load_rgb(path)
        bgr = rgb[:, :, ::-1].copy()
        frame = _frame(readers[0].predict(bgr)[0], readers[1].predict(bgr)[0])
        (want, want_s), (have, have_s) = (_check(engine, rgb, repeat) for engine in engines)
        names = [(a.raw, b.raw) for a, b in zip(want.names, have.names, strict=False)]
        gaps = [abs(float(a.confidence) - float(b.confidence)) for a, b in zip(want.names, have.names, strict=False)]
        frame.update({
            "frame": hashlib.sha256(path.read_bytes()).hexdigest()[:12],
            "names": len(want.names), "variant_names": len(have.names), "names_same": sum(a == b for a, b in names),
            "found": [bool(want.header_found), bool(have.header_found)], "name_gap": max(gaps, default=0.0),
            "seconds": [want_s, have_s],
        })
        frame["identical"] = (frame["lines"] == frame["variant_lines"] == frame["texts"] == frame["boxes"] == frame["quads"]
                              and frame["names"] == frame["variant_names"] == frame["names_same"]
                              and frame["found"][0] == frame["found"][1])
        frame["within"] = frame["identical"] and max(frame["gap"], frame["name_gap"]) <= TOLERANCE
        frames.append(frame)
    return {
        "images": len(frames),
        "lobbies_found": [sum(f["found"][0] for f in frames), sum(f["found"][1] for f in frames)],
        "identical_frames": sum(f["identical"] for f in frames),
        "within_tolerance_frames": sum(f["within"] for f in frames),
        "lines": [sum(f["lines"] for f in frames), sum(f["texts"] for f in frames)],
        "names": [sum(f["names"] for f in frames), sum(f["names_same"] for f in frames)],
        "max_line_gap": max(f["gap"] for f in frames),
        "max_name_gap": max(f["name_gap"] for f in frames),
        "seconds_per_check": [round(statistics.median(f["seconds"][i] for f in frames), 4) for i in (0, 1)],
        "verdict": "KEEP" if all(f["within"] for f in frames) else "DROP",
        "frames_off": [{k: f[k] for k in ("frame", "lines_off", "gap", "name_gap", "names", "names_same", "found")}
                       for f in frames if not f["within"]],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("convert")
    make.add_argument("models", type=Path)
    make.add_argument("out", type=Path)
    check = sub.add_parser("parity")
    check.add_argument("fp32", type=Path)
    check.add_argument("variant", type=Path)
    check.add_argument("report", type=Path)
    check.add_argument("images", type=Path, nargs="+")
    check.add_argument("--repeat", type=int, default=3)
    check.add_argument("--threads", type=int, default=os.cpu_count() or 4)
    args = parser.parse_args(argv)
    if args.command == "convert":
        print(json.dumps(convert(args.models, args.out), indent=1))
        return 0
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="fp16-data-")
    os.environ["PADDLE_PDX_CPU_NUM_THREADS"] = str(args.threads)
    sys.path.insert(0, str(ROOT))
    from tools.engine_bench import lobby_images

    images = [p for folder in args.images for p in lobby_images(folder)]
    report = parity(args.fp32, args.variant, images, args.repeat)
    args.report.write_text(json.dumps(report, indent=1), "utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "frames_off"}), f"frames off {len(report['frames_off'])}")
    return 0 if report["verdict"] == "KEEP" else 1


if __name__ == "__main__":
    sys.exit(main())
