"""Write the operator list a reduced ONNX Runtime build needs for the app's three OCR models.

    python tools/size/ort_ops.py <models dir> <out config> [--check <committed config>]

<models dir> holds PP-OCRv5_mobile_det, PP-OCRv5_mobile_rec and PP-OCRv6_medium_rec, each an inference.onnx. The list
is the union of each model's own operators and those of the same model after the stock onnxruntime's graph
optimizations at ORT_ENABLE_ALL (the level the app's sessions run at), because the optimizers put in fused operators
(FusedConv, NCHWc Conv, ReorderInput, ...) whose kernels a build with only the model's own operators would not have.
The output is ONNX Runtime's --include_ops_by_config format: one `domain;opset;op,op` line per domain and opset.
With --check, exits 1 when the written list differs from the committed one (a model or optimizer change).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

MODELS = ("PP-OCRv5_mobile_det", "PP-OCRv5_mobile_rec", "PP-OCRv6_medium_rec")


def graph_ops(graph, opsets: dict[str, int], out: dict) -> None:  # noqa: ANN001
    """Every node's (domain, opset) -> op type, subgraphs included."""
    for node in graph.node:
        domain = node.domain or "ai.onnx"
        out[(domain, opsets[domain])].add(node.op_type)
        for attr in node.attribute:
            for sub in [attr.g] if attr.HasField("g") else list(attr.graphs):
                graph_ops(sub, opsets, out)


def model_ops(path: Path, out: dict) -> None:
    import onnx

    model = onnx.load(str(path), load_external_data=False)
    opsets = {(imp.domain or "ai.onnx"): imp.version for imp in model.opset_import}
    graph_ops(model.graph, opsets, out)


def optimized(path: Path, folder: Path) -> Path:
    """The model as the stock onnxruntime runs it: ORT_ENABLE_ALL, saved after optimization."""
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.optimized_model_filepath = str(folder / f"{path.parent.name}.opt.onnx")
    options.log_severity_level = 3
    ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])
    return Path(options.optimized_model_filepath)


def config(models: Path) -> str:
    ops: dict = defaultdict(set)
    with tempfile.TemporaryDirectory() as tmp:
        for name in MODELS:
            path = models / name / "inference.onnx"
            model_ops(path, ops)
            model_ops(optimized(path, Path(tmp)), ops)
    lines = ["# The app's three OCR models and their ORT_ENABLE_ALL optimized forms (tools/size/ort_ops.py)."]
    lines += [f"{domain};{opset};{','.join(sorted(names))}" for (domain, opset), names in sorted(ops.items())]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("models", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args(argv)
    text = config(args.models)
    args.out.write_text(text, "utf-8")
    print(text, end="")
    if args.check and args.check.read_text("utf-8") != text:
        print(f"::warning::the operator list differs from {args.check}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
