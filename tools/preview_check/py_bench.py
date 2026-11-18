"""The Python v1.0.1 side of the corpus bench, with the same protocol as the Rust app's `--bench-check <dir>`:
READY, then per .jpg in code-point name order (the Rust side's order; Windows paths sort case-blind, so not sorted(paths))
a `FILE\t<file name>` line and a frame line (`<ms>\t<header 0/1>\t<seats flagged>\t<seat names>`), DONE, then it waits for a line on
stdin. Each frame is checked as a first check is (no lobby spot kept from the frame before). Logs go to the app's own log
(APPDATA/BlackListDetect/logs). Run with PYTHONPATH at a v1.0.1 tree and APPDATA at a folder of its own.

    python tools/preview_check/py_bench.py <dir> [<list>]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path


def main() -> None:
    from blacklist_detect.logs import setup_logging
    from blacklist_detect.model import Entry
    from blacklist_detect.ocr_engine import get_engine
    from blacklist_detect.pipeline import check_rgb, load_rgb

    setup_logging()
    images = sorted((p for p in Path(sys.argv[1]).iterdir() if p.suffix.lower() == ".jpg"), key=lambda p: p.name)
    names_listed = Path(sys.argv[2]).read_text(encoding="utf-8").splitlines() if len(sys.argv) > 2 else []
    entries = [Entry(name=name) for name in names_listed if name.strip()]
    engine = get_engine()
    print(f"READY\t{len(images)}", flush=True)
    for image in images:
        rgb = load_rgb(image)
        if hasattr(engine, "lobby_spot"):
            engine.lobby_spot = None
        print(f"FILE\t{image.name}", flush=True)
        start = time.perf_counter()
        result = check_rgb(rgb, entries, engine=engine)
        ms = (time.perf_counter() - start) * 1000
        names = [slot.raw.replace("\t", " ").replace("\n", " ") for slot in result.names]
        hits = ",".join(str(hit.index) for hit in result.hits)
        print(f"{ms:.1f}\t{int(result.header_found)}\t{hits}\t" + "\t".join(names), flush=True)
    print("DONE", flush=True)
    sys.stdin.readline()


if __name__ == "__main__":
    main()
