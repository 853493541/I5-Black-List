"""Golden data for the Rust lobby crate (rust/lobby): what the Python code reads and decides on every lobby-corpus frame.

    BLACKLIST_DETECT_ENGINE=onnxruntime BLACKLIST_DETECT_MODEL_DIR=<onnx models> \
        python tools/rust_golden_lobby.py <corpus folder> rust/lobby/tests/golden

For each frame (named by its number in the sorted corpus, never by a player): the lines the app reads to find the
lobby (pipeline._locate), what find_anchor, ready_strip and game_screen make of them, what the text functions of
match.py and layout.py give for every line, and the twelve names read from the name boxes matched against a list made
from them (the same name, a cut-off name, other case, a longer listed name, a made-up name). The Rust tests feed the
same lines and names in and must give the same answers. Runs in a data folder of its own and makes no sound.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("APPDATA", tempfile.mkdtemp(prefix="golden-appdata-"))

from blacklist_detect import layout, match, pipeline  # noqa: E402
from blacklist_detect.model import Entry  # noqa: E402
from blacklist_detect.ocr_engine import NAME_CONFIDENCE_MIN, OcrEngine  # noqa: E402


def box(values) -> list | None:  # noqa: ANN001
    return None if values is None else [float(value) for value in values]


def anchor_json(anchor: layout.Anchor) -> dict:
    return {
        "found": anchor.found,
        "reason": anchor.reason,
        "countdown_seconds": anchor.countdown_seconds,
        "ready_count": anchor.ready_count,
        "scale": float(anchor.scale),
        "name_boxes": [[int(value) for value in item] for item in anchor.name_boxes],
        "button_box": None if anchor.button_box is None else [int(value) for value in anchor.button_box],
        "title_box": box(anchor.title_box),
        "mode_box": box(anchor.mode_box),
        "countdown_box": box(anchor.countdown_box),
    }


def text_json(text: str) -> dict:
    visible, truncated = match.split_ellipsis(text)
    return {
        "text": text,
        "normalize_text": match.normalize_text(text),
        "split_ellipsis": [visible, truncated],
        "with_game_ellipsis": match.with_game_ellipsis(visible, truncated),
        "strip_noise": match.strip_noise(text),
        "fold": match.fold(text),
        "clean_stored_name": match.clean_stored_name(text),
        "is_lobby_chrome": match.is_lobby_chrome(text),
        "countdown_in": layout.countdown_in(text),
        "ready_in": layout.ready_in(text),
    }


def listed_from(names: list[str]) -> list[Entry]:
    """A list built from the names read: each as listed, cut, in other case, longer, and a made-up name."""
    entries = [Entry(name="示例坏人"), Entry(name="心动小鹿99")]
    for name in names:
        bare = name.removesuffix("...")
        entries += [Entry(name=bare), Entry(name=bare[:4] + "尾巴"), Entry(name=bare.upper()), Entry(name=bare + "九九")]
        if len(bare) > 3:
            entries.append(Entry(name=bare[:3]))
    return entries


def names_json(engine, rgb, anchor: layout.Anchor) -> tuple[list[dict], list[str]]:  # noqa: ANN001
    crops = [pipeline._crop(rgb, item, anchor.scale) for item in anchor.name_boxes]
    seats = []
    for raw, confidence in engine.read_names(crops):
        visible, truncated = match.split_ellipsis(raw)
        visible = match.strip_noise(visible)
        unclear = confidence < NAME_CONFIDENCE_MIN or not visible
        if not unclear:
            visible = match.with_game_ellipsis(visible, truncated)
        seats.append({
            "raw": match.normalize_text(raw),
            "visible": "" if unclear else visible,
            "truncated": bool(truncated and not unclear),
            "unclear": unclear,
        })
    return seats, [seat["visible"] for seat in seats if seat["visible"]]


def frame_json(engine, number: int, path: Path) -> dict:  # noqa: ANN001
    rgb = pipeline.load_rgb(path)
    height, width = rgb.shape[:2]
    _app_anchor, lines = pipeline._locate(engine, rgb)
    anchor = layout.find_anchor(lines, width, height)
    out = {
        "frame": number,
        "width": width,
        "height": height,
        "lines": [{"text": line.text, "confidence": float(line.confidence), "box": box(line.box)} for line in lines],
        "anchor": anchor_json(anchor),
        "contains_title": layout.contains_title(lines),
        "ready_strip": box(layout.ready_strip(anchor)),
        "game_screen": box(layout.game_screen(anchor)),
        "texts": [text_json(line.text) for line in lines],
        "seats": [],
        "entries": [],
    }
    if anchor.found:
        seats, names = names_json(engine, rgb, anchor)
        entries = listed_from(names)
        for seat in seats:
            label = match.NameLabel(seat["raw"], seat["visible"], seat["truncated"], seat["unclear"])
            index = {id(entry): place for place, entry in enumerate(entries)}
            seat["matches"] = [[index[id(found.entry)], found.kind, found.truncated] for found in match.match_label(label, entries)]
            seat["texts"] = text_json(seat["raw"])
            seat["listed_tail"] = [match.listed_tail(seat["visible"], entry.name) for entry in entries]
        out["seats"] = seats
        out["entries"] = [entry.name for entry in entries]
    return out


def main(corpus: Path, out: Path) -> None:
    engine = OcrEngine(backend="onnxruntime")
    engine.warmup()
    out.mkdir(parents=True, exist_ok=True)
    frames = sorted(path for path in corpus.iterdir() if path.suffix.lower() in (".jpg", ".png"))
    for number, path in enumerate(frames, start=1):
        record = frame_json(engine, number, path)
        target = out / f"frame_{number:03d}.json"
        target.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        print(number, record["anchor"]["found"], len(record["lines"]), flush=True)
    constants = {"name_boxes": [list(item) for item in layout.NAME_BOXES]}
    (out / "constants.json").write_text(json.dumps(constants, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
