"""Read lobbies with Paddle and with other engines running the same models, and compare every name.

    python tools/engine_bench.py <folder of lobby images> <out dir> [--engines onnxruntime openvino app-onnxruntime]
                                 [--threads N] [--repeat 3] [--sizes] [--reference paddle.json] [--onnx-models DIR]

The reference is the app's own check (pipeline.check_rgb on an OcrEngine): the same lobby search, the
same name crops, the same preparation of each strip and the same CTC decoding with the model's own
dictionary. A challenger changes only the step that runs the network: inside each PaddleX predictor
(detection, line recognition, PP-OCRv6 name recognition) the Paddle runner is swapped for one that
runs the same weights converted to ONNX (paddle2onnx). Everything before and after it is PaddleX's
own code, so a difference in a name can only come from the engine.

app-onnxruntime is the app's own switch (BLACKLIST_DETECT_ENGINE=onnxruntime): PaddleX builds the
predictors on its ONNX Runtime runner, with no paddlepaddle needed. Where Paddle is not installed, give
it --reference (paddle.json from a run where it was) and --onnx-models (the onnx_models folder that run made).

Pass rule: an engine passes only if every name on every image is identical to Paddle's. One
difference is a fail.

Models come from BLACKLIST_DETECT_MODEL_DIR, as in the app. The run uses a data folder of its own
(APPDATA under <out dir>) and makes no sound.
"""

from __future__ import annotations

import argparse
import contextlib
import difflib
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
CHALLENGERS = ("onnxruntime", "openvino")
# The app's own ONNX Runtime mode (BLACKLIST_DETECT_ENGINE=onnxruntime): PaddleX's runner, no Paddle needed.
APP_ONNX = "app-onnxruntime"
PASS_RULE = "An engine passes only if every name on every image is identical to Paddle's. One difference = fail."
# The Windows wheels each engine adds, for the size table (Python 3.12, win_amd64, without dependencies).
WHEELS = {
    "paddle": ["paddlepaddle==3.2.0"],
    "onnxruntime": ["onnxruntime"],
    "openvino": ["openvino"],
}


@dataclass
class Name:
    text: str
    confidence: float


@dataclass
class Read:
    """One engine's reading of one image."""

    image: str
    found: bool
    names: list[Name]
    seconds: list[float] = field(default_factory=list)


@dataclass
class Difference:
    image: str
    slot: int
    paddle: str
    other: str
    paddle_confidence: float
    other_confidence: float
    edits: list[str]


# ----- Comparison (no engine needed) -----


def char_edits(expected: str, actual: str) -> list[str]:
    """Where two names differ, character by character: 'replace 霁->雾 at 0', 'insert x at 3', ..."""
    edits = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=expected, b=actual, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            edits.append(f"insert {actual[j1:j2]!r} at {i1}")
        elif tag == "delete":
            edits.append(f"delete {expected[i1:i2]!r} at {i1}")
        else:
            edits.append(f"replace {expected[i1:i2]!r}->{actual[j1:j2]!r} at {i1}")
    return edits


def compare(reference: list[Read], other: list[Read]) -> tuple[int, int, list[Difference]]:
    """Names identical, names in all, and every difference, image by image and slot by slot.

    An image the other engine did not read, or where only one of the two found the lobby, counts every
    reference name on it as different (or one slot, when the reference found no names there)."""
    by_image = {read.image: read for read in other}
    same = total = 0
    differences: list[Difference] = []
    for ref in reference:
        got = by_image.get(ref.image)
        lobby_differs = got is None or got.found != ref.found
        slots = max(len(ref.names), len(got.names) if got else 0, 1 if lobby_differs else 0)
        for slot in range(slots):
            total += 1
            want = ref.names[slot] if slot < len(ref.names) else Name("", 0.0)
            have = got.names[slot] if got is not None and slot < len(got.names) else Name("", 0.0)
            if want.text == have.text and not lobby_differs:
                same += 1
                continue
            edits = char_edits(want.text, have.text)
            if got is None:
                edits = ["image not read"]
            elif lobby_differs:
                edits = [f"lobby found: paddle {ref.found}, other {got.found}", *edits]
            differences.append(Difference(ref.image, slot, want.text, have.text, want.confidence, have.confidence, edits))
    return same, total, differences


def verdict(same: int, total: int) -> str:
    return "PASS" if total and same == total else "FAIL"


def lobby_images(folder: Path) -> list[Path]:
    if folder.is_file():
        return [folder]
    return sorted(path for path in folder.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES)


# ----- Engines -----


class OnnxRuntimeRunner:
    """Runs an ONNX model the way PaddleX calls its runners: runner(x=[arrays]) -> [arrays]."""

    def __init__(self, onnx_path: Path, threads: int) -> None:
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.log_severity_level = 3
        # PP-OCRv6_medium_rec's activations go denormal; computed exactly, they made ORT ten times slower.
        options.add_session_config_entry("session.set_denormal_as_zero", "1")
        self.session = ort.InferenceSession(str(onnx_path), options, providers=["CPUExecutionProvider"])
        self.inputs = [meta.name for meta in self.session.get_inputs()]
        self.outputs = [meta.name for meta in self.session.get_outputs()]

    def __call__(self, x=None, **kwargs):  # noqa: ANN001
        x = kwargs.get("x") if x is None else x
        arrays = [x] if isinstance(x, np.ndarray) else list(x)
        feeds = {name: np.ascontiguousarray(array) for name, array in zip(self.inputs, arrays, strict=True)}
        return self.session.run(self.outputs, feeds)

    def close(self) -> None:
        pass


class OpenVinoRunner:
    """The same, on OpenVINO's CPU plugin, in full float32 (a CPU with bf16 would otherwise round)."""

    def __init__(self, model_path: Path, threads: int) -> None:
        import openvino as ov

        core = ov.Core()
        config = {"INFERENCE_NUM_THREADS": threads, "INFERENCE_PRECISION_HINT": "f32", "PERFORMANCE_HINT": "LATENCY"}
        self.compiled = core.compile_model(core.read_model(str(model_path)), "CPU", config)
        self.request = self.compiled.create_infer_request()

    def __call__(self, x=None, **kwargs):  # noqa: ANN001
        x = kwargs.get("x") if x is None else x
        arrays = [x] if isinstance(x, np.ndarray) else list(x)
        self.request.infer([np.ascontiguousarray(array) for array in arrays])
        return [self.request.get_output_tensor(i).data.copy() for i in range(len(self.compiled.outputs))]

    def close(self) -> None:
        pass


def openvino_reads_paddle(model_dir: Path) -> str:
    """Whether OpenVINO opens the Paddle model folder itself; '' when it does, else why not."""
    import openvino as ov

    source = next((model_dir / name for name in ("inference.pdmodel", "inference.json") if (model_dir / name).exists()), None)
    if source is None:
        return "no inference.pdmodel or inference.json"
    try:
        ov.Core().read_model(str(source))
    except Exception as exc:  # noqa: BLE001
        return " ".join(str(exc).split())[-300:]
    return ""


def to_onnx(model_dir: Path, cache: Path) -> tuple[Path, dict]:
    """The model converted with paddle2onnx (cached by folder name), and what the conversion was."""
    import onnx
    import paddle2onnx

    target = cache / f"{model_dir.name}.onnx"
    params = model_dir / "inference.pdiparams"
    program = model_dir / ("inference.json" if (model_dir / "inference.json").exists() else "inference.pdmodel")
    if not target.exists():
        # In a child: converting in this process left ONNX Runtime four times slower afterwards.
        from blacklist_detect.paths import child_env

        cache.mkdir(parents=True, exist_ok=True)
        convert = "import sys, paddle2onnx; paddle2onnx.export(*sys.argv[1:4], opset_version=11)"
        subprocess.run([sys.executable, "-c", convert, str(program), str(params), str(target)],
                       check=True, env=child_env(), capture_output=True, timeout=600)
    model = onnx.load(str(target), load_external_data=False)
    info = {
        "paddle2onnx": paddle2onnx.__version__,
        "opset": max(item.version for item in model.opset_import if item.domain in ("", "ai.onnx")),
        "program": program.name,
    }
    return target, info


def predictors(engine) -> dict[str, object]:  # noqa: ANN001
    """The three PaddleX predictors a check runs, by model name."""
    inner = engine._ensure().paddlex_pipeline._pipeline
    name_rec = engine._ensure_name_rec().paddlex_predictor
    found = {}
    for predictor in (inner.text_det_model, inner.text_rec_model, name_rec):
        found[Path(predictor.model_dir).name] = predictor
    return found


def read_image(engine, path: Path, repeat: int) -> Read:  # noqa: ANN001
    from blacklist_detect.pipeline import check_rgb, load_rgb

    rgb = load_rgb(path)
    seconds = []
    result = None
    for _ in range(max(1, repeat)):
        # Every engine searches the whole image, as a first check does.
        engine.lobby_spot = None
        started = time.perf_counter()
        result = check_rgb(rgb, [], engine=engine)
        seconds.append(time.perf_counter() - started)
    names = [Name(slot.raw, round(float(slot.confidence), 6)) for slot in result.names]
    return Read(path.name, bool(result.header_found), names, seconds)


def onnx_model_folders(paddle_engine, out: Path) -> Path:  # noqa: ANN001
    """The app's models as ONNX Runtime opens them through PaddleX: inference.onnx beside each inference.yml."""
    root = out / "onnx_models"
    for name, predictor in predictors(paddle_engine).items():
        model_dir = Path(predictor.model_dir)
        onnx_path, _info = to_onnx(model_dir, out / "onnx")
        folder = root / name
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(onnx_path, folder / "inference.onnx")
        shutil.copyfile(model_dir / "inference.yml", folder / "inference.yml")
    return root


def app_engine(backend: str, model_root: Path):  # noqa: ANN201
    """An OcrEngine as the app makes it for this backend, its models read from model_root."""
    from blacklist_detect.ocr_engine import OcrEngine

    before = os.environ.get("BLACKLIST_DETECT_MODEL_DIR")
    os.environ["BLACKLIST_DETECT_MODEL_DIR"] = str(model_root)
    try:
        engine = OcrEngine(backend=backend)
        engine.warmup()
    finally:
        if before is None:
            os.environ.pop("BLACKLIST_DETECT_MODEL_DIR", None)
        else:
            os.environ["BLACKLIST_DETECT_MODEL_DIR"] = before
    return engine


def load_reads(path: Path) -> list[Read]:
    return [Read(r["image"], r["found"], [Name(**n) for n in r["names"]], r.get("seconds", [])) for r in json.loads(path.read_text("utf-8"))]


def bench(images: list[Path], out: Path, engines: list[str], threads: int, repeat: int,
          reference_file: Path | None = None, onnx_models: Path | None = None) -> dict:
    os.environ["PADDLE_PDX_CPU_NUM_THREADS"] = str(threads)
    from blacklist_detect.ocr_engine import OcrEngine

    report: dict = {"rule": PASS_RULE, "threads": threads, "repeat": repeat, "images": [p.name for p in images], "engines": {}}
    report["versions"] = versions()
    engine = None
    if reference_file is None or any(kind in CHALLENGERS for kind in engines) or (APP_ONNX in engines and onnx_models is None):
        engine = OcrEngine(backend="paddle")
        engine.warmup()
    if reference_file is not None:
        wanted = {p.name for p in images}
        reference = [r for r in load_reads(reference_file) if r.image in wanted]
        report["reference"] = str(reference_file)
    else:
        reference = [read_image(engine, path, repeat) for path in images]
        (out / "paddle.json").write_text(json.dumps([asdict(r) for r in reference], ensure_ascii=False, indent=1), "utf-8")
    report["engines"]["paddle"] = {"seconds_per_lobby": median_seconds(reference), "lobbies_found": sum(r.found for r in reference)}

    for kind in engines:
        entry: dict = {"models": {}}
        report["engines"][kind] = entry
        try:
            if kind == APP_ONNX:
                root = onnx_models or onnx_model_folders(engine, out)
                entry["models"] = {"folder": str(root)}
                reader = app_engine("onnxruntime", root)
                reads = [read_image(reader, path, repeat) for path in images]
            else:
                reads = swapped_reads(engine, kind, images, out, threads, repeat, entry)
        except Exception as exc:  # noqa: BLE001
            entry.update(verdict="FAIL", error=f"{type(exc).__name__}: {exc}"[:600])
            continue
        (out / f"{kind}.json").write_text(json.dumps([asdict(r) for r in reads], ensure_ascii=False, indent=1), "utf-8")
        same, total, differences = compare(reference, reads)
        by_image = {r.image: r for r in reads}
        entry.update(
            verdict=verdict(same, total),
            identical=same,
            total=total,
            differences=[asdict(d) for d in differences],
            seconds_per_lobby=median_seconds(reads),
            lobbies_found=sum(r.found for r in reads),
            confidence=[[[n.text, want.confidence, n.confidence] for want, n in zip(r0.names, by_image[r0.image].names, strict=False)]
                        for r0 in reference if r0.image in by_image],
        )
    return report


def swapped_reads(engine, kind: str, images: list[Path], out: Path, threads: int, repeat: int, entry: dict) -> list[Read]:  # noqa: ANN001
    """Reads by the Paddle engine with its three runners swapped for this engine's, put back after."""
    originals = {name: predictor.runner for name, predictor in predictors(engine).items()}
    try:
        for name, predictor in predictors(engine).items():
            model_dir = Path(predictor.model_dir)
            onnx_path, info = to_onnx(model_dir, out / "onnx")
            if kind == "openvino":
                info["reads_paddle_folder"] = openvino_reads_paddle(model_dir) or "yes"
                predictor.runner = OpenVinoRunner(onnx_path, threads)
            else:
                predictor.runner = OnnxRuntimeRunner(onnx_path, threads)
            entry["models"][name] = info
        engine.warmup()
        return [read_image(engine, path, repeat) for path in images]
    finally:
        for name, predictor in predictors(engine).items():
            predictor.runner = originals[name]


def median_seconds(reads: list[Read]) -> float | None:
    values = [statistics.median(r.seconds) for r in reads if r.seconds]
    return round(statistics.median(values), 4) if values else None


def versions() -> dict[str, str]:
    from importlib.metadata import PackageNotFoundError, version

    found = {}
    for package in ("paddlepaddle", "paddleocr", "paddlex", "paddle2onnx", "onnx", "onnxruntime", "openvino"):
        with contextlib.suppress(PackageNotFoundError):
            found[package] = version(package)
    return found


# ----- Sizes of the Windows wheels -----


def unpacked_size(wheel: Path) -> int:
    with zipfile.ZipFile(wheel) as archive:
        return sum(info.file_size for info in archive.infolist())


def wheel_sizes(work: Path) -> dict[str, dict]:
    """Download each engine's Windows wheel (no dependencies) and add up what it unpacks to."""
    from blacklist_detect.paths import child_env

    sizes = {}
    for kind, packages in WHEELS.items():
        folder = work / kind
        folder.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, "-m", "pip", "download", "--quiet", "--platform", "win_amd64", "--python-version", "3.12",
                   "--only-binary=:all:", "--no-deps", "-d", str(folder), *packages]
        subprocess.run(command, check=True, env=child_env(), timeout=900)
        wheels = sorted(folder.glob("*.whl"))
        sizes[kind] = {
            "wheels": [w.name for w in wheels],
            "download_mb": round(sum(w.stat().st_size for w in wheels) / 1e6, 1),
            "unpacked_mb": round(sum(unpacked_size(w) for w in wheels) / 1e6, 1),
        }
    return sizes


# ----- Report -----


def summary(report: dict) -> str:
    lines = [f"Pass rule: {report['rule']}", f"Threads: {report['threads']} for every engine; time is the median of {report['repeat']} reads per lobby.", ""]
    sizes = report.get("sizes", {})
    for kind, entry in report["engines"].items():
        size = sizes.get(kind, {}).get("unpacked_mb")
        size_text = f", wheel unpacked {size} MB" if size is not None else ""
        if kind == "paddle":
            lines.append(f"paddle (reference): {entry['seconds_per_lobby']} s per lobby, lobbies found {entry['lobbies_found']}{size_text}")
            continue
        if "error" in entry:
            lines.append(f"{kind}: FAIL, did not run: {entry['error']}")
            continue
        lines.append(f"{kind}: {entry['verdict']}, names identical {entry['identical']}/{entry['total']}, "
                     f"{entry['seconds_per_lobby']} s per lobby, lobbies found {entry['lobbies_found']}{size_text}")
        for diff in entry["differences"]:
            lines.append(f"  {diff['image']} slot {diff['slot']}: paddle {diff['paddle']!r} ({diff['paddle_confidence']}) "
                         f"vs {diff['other']!r} ({diff['other_confidence']}): {'; '.join(diff['edits'])}")
        drift = [abs(a - b) for image in entry["confidence"] for _text, a, b in image]
        if drift:
            lines.append(f"  confidence: largest difference from paddle {max(drift):.6f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("images", type=Path, help="a lobby image, or a folder of them (searched recursively)")
    parser.add_argument("out", type=Path)
    parser.add_argument("--engines", nargs="+", choices=[*CHALLENGERS, APP_ONNX], default=[*CHALLENGERS, APP_ONNX])
    parser.add_argument("--threads", type=int, default=os.cpu_count() or 4)
    parser.add_argument("--repeat", type=int, default=3, help="reads per lobby for the time")
    parser.add_argument("--reference", type=Path, help="Paddle's reads (paddle.json of an earlier run) instead of reading with Paddle")
    parser.add_argument("--onnx-models", type=Path, help=f"model folders with inference.onnx for {APP_ONNX} (made from the Paddle ones if left out)")
    parser.add_argument("--sizes", action="store_true", help="also download the Windows wheels and add up their sizes")
    args = parser.parse_args(argv)

    images = lobby_images(args.images)
    if not images:
        parser.error(f"no images in {args.images}")
    args.out.mkdir(parents=True, exist_ok=True)
    data = Path(tempfile.mkdtemp(prefix="data-", dir=args.out))
    os.environ["APPDATA"] = str(data)
    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "bos")
    sys.path.insert(0, str(ROOT))

    report = bench(images, args.out, args.engines, args.threads, args.repeat, args.reference, args.onnx_models)
    if args.sizes:
        report["sizes"] = wheel_sizes(args.out / "wheels")
    (args.out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf-8")
    text = summary(report)
    (args.out / "report.txt").write_text(text + "\n", "utf-8")
    print(text)
    return 0 if all(e.get("verdict", "PASS") == "PASS" for e in report["engines"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
