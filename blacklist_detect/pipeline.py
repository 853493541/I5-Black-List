"""One check: header, twelve name strips, blacklist. No clicks, no memory reads."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from blacklist_detect import ui_text as T
from blacklist_detect.layout import Anchor, contains_title, find_anchor, snap_button_box
from blacklist_detect.match import (
    NameLabel,
    format_hit,
    match_label,
    normalize_text,
    split_ellipsis,
    strip_noise,
    with_game_ellipsis,
)
from blacklist_detect.model import Entry, OcrLine
from blacklist_detect.ocr_engine import (
    NAME_CONFIDENCE_MIN,
    downscale_rgb,
    get_engine,
    rgb_to_bgr,
    scale_lines,
)
from blacklist_detect.storage import describe_entry


@dataclass
class NameSlot:
    index: int
    box: tuple[int, int, int, int]
    raw: str
    visible: str
    truncated: bool
    confidence: float
    unclear: bool


@dataclass
class Hit:
    index: int
    read_text: str
    entry_name: str
    note: str
    truncated: bool
    line: str
    tags: tuple[str, ...] = ()


@dataclass
class CheckResult:
    header_found: bool
    message: str
    countdown_seconds: int | None = None
    ready_count: int | None = None
    names: list[NameSlot] = field(default_factory=list)
    hits: list[Hit] = field(default_factory=list)
    preview_rgb: np.ndarray | None = None
    button_box: tuple[int, int, int, int] | None = None


def load_rgb(path: str | Path) -> np.ndarray:
    image = Image.open(path).convert("RGB")
    return np.asarray(image)


def check_image(path: str | Path, entries: list[Entry], engine=None) -> CheckResult:
    return check_rgb(load_rgb(path), entries, engine=engine)


def check_frames(frames: list[np.ndarray], entries: list[Entry], engine=None, on_lobby=None) -> CheckResult:
    """Header-scan each monitor copy and read names only on the one that matches."""
    if not frames:
        return CheckResult(False, T.NO_FRAME)
    reader = engine or get_engine()
    chosen: tuple[np.ndarray, Anchor, list[OcrLine]] | None = None
    last_reason = T.NO_LOBBY
    for frame in frames:
        anchor, _lines = _locate(reader, frame)
        if anchor.found:
            chosen = (frame, anchor, _lines)
            break
        last_reason = anchor.reason or last_reason
    if chosen is None:
        result = CheckResult(False, last_reason)
        result.preview_rgb = frames[0]
        return result
    frame, anchor, _lines = chosen
    button = snap_button_box(frame, anchor.button_box)
    if on_lobby is not None and button is not None:
        on_lobby(button)
    result = _read_names(reader, frame, anchor, entries)
    result.button_box = button
    return result


def check_rgb(rgb: np.ndarray, entries: list[Entry], engine=None) -> CheckResult:
    return check_frames([rgb], entries, engine=engine)


def glance_title(rgb: np.ndarray, engine=None) -> bool:
    """Read only enough of a top-band copy to see 推演成功: the tallest few text lines."""
    reader = engine or get_engine()
    small, _factor = downscale_rgb(rgb, max_width=960)
    bgr = rgb_to_bgr(small)
    tallest = getattr(reader, "read_tallest_lines", None)
    lines = tallest(bgr) if tallest is not None else reader.read_bgr(bgr)
    return contains_title(lines)


def band_signature(rgb: np.ndarray) -> np.ndarray:
    """A tiny gray copy of a band, to tell whether the screen changed since the last glance."""
    step_y = max(1, rgb.shape[0] // 36)
    step_x = max(1, rgb.shape[1] // 160)
    return rgb[::step_y, ::step_x].mean(axis=2, dtype=np.float32)


def same_band(previous: np.ndarray | None, current: np.ndarray, tolerance: float = 1.0) -> bool:
    """True when the band is unchanged, so the last glance still holds. A title appearing changes it a lot."""
    if previous is None or previous.shape != current.shape:
        return False
    return float(np.abs(previous - current).mean()) < tolerance


def _locate(engine, rgb: np.ndarray) -> tuple[Anchor, list[OcrLine]]:
    small, factor = downscale_rgb(rgb, max_width=1280)
    lines = scale_lines(engine.read_bgr(rgb_to_bgr(small)), factor)
    height, width = rgb.shape[:2]
    return find_anchor(lines, width, height), lines


def _crop(rgb: np.ndarray, box: tuple[int, int, int, int], scale: float) -> np.ndarray:
    left, top, right, bottom = box
    pad_x = max(4, int(round(14 * scale)))
    pad_top = max(1, int(round(3 * scale)))
    pad_bottom = max(2, int(round(8 * scale)))
    height, width = rgb.shape[:2]
    left = max(0, left - pad_x)
    right = min(width, right + pad_x)
    top = max(0, top - pad_top)
    bottom = min(height, bottom + pad_bottom)
    return rgb[top:bottom, left:right]


def _read_names(engine, rgb: np.ndarray, anchor: Anchor, entries: list[Entry]) -> CheckResult:
    slots: list[NameSlot] = []
    hits: list[Hit] = []
    crops = [_crop(rgb, box, anchor.scale) for box in anchor.name_boxes]
    readings = engine.read_names(crops)
    for index, (raw, confidence) in enumerate(readings):
        visible, truncated = split_ellipsis(raw)
        visible = strip_noise(visible)
        unclear = confidence < NAME_CONFIDENCE_MIN or not visible
        if not unclear:
            visible = with_game_ellipsis(visible, truncated)
        slot = NameSlot(
            index=index,
            box=anchor.name_boxes[index],
            raw=raw,
            visible="" if unclear else visible,
            truncated=bool(truncated and not unclear),
            confidence=confidence,
            unclear=unclear,
        )
        slots.append(slot)
        label = NameLabel(
            raw=normalize_text(raw),
            visible=slot.visible,
            truncated=slot.truncated,
            unclear=unclear,
        )
        shown = slot.visible or visible
        for found in match_label(label, entries):
            line = format_hit(index, shown, slot.truncated, found.entry.name, describe_entry(found.entry))
            hits.append(
                Hit(
                    index=index,
                    read_text=shown,
                    entry_name=found.entry.name,
                    note=describe_entry(found.entry),
                    truncated=slot.truncated,
                    line=line,
                    tags=tuple(found.entry.tags),
                )
            )
    message = _message(anchor, slots, hits)
    result = CheckResult(
        header_found=True,
        message=message,
        countdown_seconds=anchor.countdown_seconds,
        ready_count=anchor.ready_count,
        names=slots,
        hits=hits,
        preview_rgb=rgb,
        button_box=anchor.button_box,
    )
    return result


def _message(anchor: Anchor, slots: list[NameSlot], hits: list[Hit]) -> str:
    unclear = sum(1 for slot in slots if slot.unclear)
    return T.lobby_summary(anchor.countdown_seconds, anchor.ready_count, len(hits), unclear)
