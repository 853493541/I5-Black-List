"""The size table of ONNX Runtime builds: bytes, MiB, zipped (deflate level 9, as upload-artifact zips) and the DLLs
each imports that a clean Windows does not have.

    python tools/size/ort_sizes.py <label>=<library> [...]

Prints a Markdown table (for the step summary).
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def zipped(path: Path) -> int:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.write(path, path.name)
    return len(buffer.getvalue())


def main(argv: list[str]) -> int:
    sys.path.insert(0, str(ROOT / "build"))
    from make_rust_release import foreign_imports

    print("| build | bytes | MiB | zipped MiB | non-system imports |")
    print("|---|---|---|---|---|")
    for item in argv:
        label, path = item.split("=", 1)
        path = Path(path)
        size = path.stat().st_size
        print(f"| {label} | {size} | {size / 2**20:.2f} | {zipped(path) / 2**20:.2f} | {foreign_imports(path) or 'none'} |")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
