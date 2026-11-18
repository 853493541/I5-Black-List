"""Fail loudly when an ONNX Runtime build cannot run one of the app's three OCR models.

    python tools/size/ort_load_test.py <onnxruntime library> <models dir> <lobby image>

Opens PP-OCRv5_mobile_det, PP-OCRv5_mobile_rec and PP-OCRv6_medium_rec through the Rust reader (rust/pyocr, as the app
opens them: inference.ort when the folder has one, else inference.onnx) on that library, and runs the app's check on one
lobby. A reduced build missing a kernel fails while a session is made ("Could not find an implementation for ...") or
on the first run; either way this exits 1. Prints counts only. Runs in a data folder of its own.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str]) -> int:
    library, models, image = (Path(arg) for arg in argv[:3])
    os.environ["ORT_DYLIB_PATH"] = str(library)
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="ort-load-")
    sys.path.insert(0, str(ROOT))
    from tools.engine_bench import read_image, rust_engine

    try:
        engine = rust_engine(models)
        read = read_image(engine, image, 1)
    except Exception as err:  # noqa: BLE001 - any failure here is the build missing something
        print(f"::error::{library.name} cannot run the OCR models: {err}")
        return 1
    whole = sum(bool(name.text) for name in read.names)
    print(f"{library}: 3 models loaded, lobby found {read.found}, names {whole}, {read.seconds[0]:.3f} s")
    if not read.found or whole < 8:
        print(f"::error::{library.name} read the lobby badly (found {read.found}, names {whole})")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
