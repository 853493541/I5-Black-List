"""Golden data for the Rust port of the check (rust/pipeline): what pipeline.check_frames finds on each lobby.

Runs the Python check on ONNX Runtime (BLACKLIST_DETECT_ENGINE=onnxruntime) over tests/fixtures/reference-lobby.png
(twice, so the second check takes the remembered spot) and every lobby-corpus frame, one engine for all as the app
keeps one. Writes the decoded frames as PNG to --frames (out of git: they show real names) and to --out one JSON per
check: where the lobby is, the countdown and ready count, the twelve seats (names as hashes, never as text) and the
warnings and 嘉宾 for two lists: made-up names only, and made-up names plus names derived from the seats read (seat
i % 12 on the 黑名单, its first four characters for seat (i + 5) % 12 on the 嘉宾), so matching is checked too.

    APPDATA=/tmp/pl/appdata HOME=/tmp/pl/appdata QT_QPA_PLATFORM=offscreen BLACKLIST_DETECT_ENGINE=onnxruntime \\
    BLACKLIST_DETECT_MODEL_DIR=/tmp/pl/models PYTHONPATH=. venv/bin/python tools/rust_golden_pipeline.py \\
        --corpus /tmp/pl/corpus/tests/lobby_corpus --frames /tmp/pl/frames

--no-ipp turns Intel IPP off in OpenCV, for comparison with an OpenCV built without it (Ubuntu's 4.6).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "rust" / "pipeline" / "tests" / "golden" / "checks.json"


def hashed(text: str) -> str:
    """A stable stand-in for a name: never the name itself."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def made_up():  # noqa: ANN201
    from blacklist_detect.model import Entry

    return [Entry("示例坏人", reason="炸房两次", tags=("贴脸", "炸房"))], [Entry("心动小鹿", nickname="心动星星")]


def derived(index: int, names) -> tuple[list, list]:  # noqa: ANN001
    """The made-up lists plus one name read on this frame on each."""
    from blacklist_detect.model import Entry

    black, likes = made_up()
    if names:
        warned = names[index % len(names)]
        liked = names[(index + 5) % len(names)]
        if warned.visible:
            black.append(Entry(warned.visible, reason="测试"))
        if liked.visible:
            likes.append(Entry(liked.visible[:4]))
    return black, likes


def likes_in(result, likes) -> list[list[int]]:  # noqa: ANN001
    """ui.MainWindow._likes_in, as (seat, entry index)."""
    from blacklist_detect.match import NameLabel, match_label

    warned = {hit.index for hit in result.hits}
    found: list[list[int]] = []
    for slot in result.names:
        if slot.index in warned:
            continue
        label = NameLabel(raw=slot.raw, visible=slot.visible, truncated=slot.truncated, unclear=slot.unclear)
        for match in match_label(label, likes):
            index = next(i for i, entry in enumerate(likes) if entry is match.entry)
            if all(seen[1] != index for seen in found):
                found.append([slot.index, index])
    return found


def marks(result, black, likes) -> dict:  # noqa: ANN001
    hits = []
    for hit in result.hits:
        entry = next(i for i, entry in enumerate(black) if entry.name == hit.entry_name)
        hits.append({"seat": hit.index, "entry": entry, "line": hashed(hit.line), "truncated": hit.truncated})
    return {"hits": hits, "likes": likes_in(result, likes)}


def rematch(result, black, likes) -> dict:  # noqa: ANN001
    """_read_names' matching again on the seats already read, with other lists (an engine that only replays)."""
    from blacklist_detect import pipeline
    from blacklist_detect.layout import Anchor

    class Replay:
        def read_names(self, crops):  # noqa: ANN001, ANN202
            return [(slot.raw, slot.confidence) for slot in result.names]

    anchor = Anchor(True, "", name_boxes=[slot.box for slot in result.names], scale=1.0)
    again = pipeline._read_names(Replay(), _blank(), anchor, black)
    return marks(again, black, likes)


def _blank():  # noqa: ANN202
    import numpy as np

    return np.zeros((2000, 4000, 3), dtype=np.uint8)


def record(name: str, result, index: int) -> dict:  # noqa: ANN001
    from blacklist_detect.pipeline import CheckResult

    assert isinstance(result, CheckResult)
    black, likes = made_up()
    more_black, more_likes = derived(index, result.names)
    return {
        "frame": name,
        "header_found": result.header_found,
        "message": result.message,
        "countdown": result.countdown_seconds,
        "ready": result.ready_count,
        "button_box": list(result.button_box) if result.button_box else None,
        "game_box": list(result.game_box) if result.game_box else None,
        "spot": "spot" in result.timings,
        "seats": [
            {
                "box": list(slot.box),
                "raw": hashed(slot.raw),
                "visible": hashed(slot.visible),
                "truncated": slot.truncated,
                "unclear": slot.unclear,
                "confidence": slot.confidence,
            }
            for slot in result.names
        ],
        "made_up": marks(result, black, likes),
        "derived": rematch(result, more_black, more_likes),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--frames", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--no-ipp", action="store_true")
    args = parser.parse_args()
    assert os.environ.get("BLACKLIST_DETECT_ENGINE") == "onnxruntime", "run with BLACKLIST_DETECT_ENGINE=onnxruntime"
    import cv2
    import numpy as np

    from blacklist_detect.ocr_engine import OcrEngine
    from blacklist_detect.pipeline import check_frames

    if args.no_ipp:
        cv2.ipp.setUseIPP(False)
    engine = OcrEngine("onnxruntime")
    sources = [ROOT / "tests" / "fixtures" / "reference-lobby.png"] * 2 + sorted(args.corpus.glob("*.jpg"))
    args.frames.mkdir(parents=True, exist_ok=True)
    checks = []
    for index, source in enumerate(sources):
        name = f"{source.stem}.png"
        rgb = np.asarray(Image.open(source).convert("RGB"))
        Image.fromarray(rgb).save(args.frames / name)
        black, likes = made_up()
        result = check_frames([rgb], black, engine=engine)
        checks.append(record(name, result, index))
        print(index, name, result.message)
    data = {"engine": "onnxruntime", "ipp": not args.no_ipp, "opencv": cv2.__version__, "checks": checks}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
