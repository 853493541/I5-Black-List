"""One check: header, twelve name strips, blacklist. No clicks, no memory reads."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from blacklist_detect.layout import Anchor, find_anchor
from blacklist_detect.match import (
    NameLabel,
    format_hit,
    match_label,
    normalize_text,
    split_ellipsis,
    strip_noise,
)
from blacklist_detect.model import Entry, OcrLine
from blacklist_detect.ocr_engine import (
    NAME_CONFIDENCE_MIN,
    downscale_rgb,
    get_engine,
    rgb_to_bgr,
    scale_lines,
)


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


@dataclass
class CheckResult:
    header_found: bool
    message: str
    countdown_seconds: int | None = None
    ready_count: int | None = None
    names: list[NameSlot] = field(default_factory=list)
    hits: list[Hit] = field(default_factory=list)
    preview_rgb: np.ndarray | None = None


def load_rgb(path: str | Path) -> np.ndarray:
    image = Image.open(path).convert("RGB")
    return np.asarray(image)


def check_image(path: str | Path, entries: list[Entry], engine=None) -> CheckResult:
    return check_rgb(load_rgb(path), entries, engine=engine)


def check_frames(frames: list[np.ndarray], entries: list[Entry], engine=None) -> CheckResult:
    """Header-scan each monitor copy and read names only on the one that matches."""
    if not frames:
        return CheckResult(False, "没有复制到画面。")
    reader = engine or get_engine()
    chosen: tuple[np.ndarray, Anchor, list[OcrLine]] | None = None
    last_reason = "没有找到这间大厅。"
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
    return _read_names(reader, frame, anchor, entries)


def check_rgb(rgb: np.ndarray, entries: list[Entry], engine=None) -> CheckResult:
    return check_frames([rgb], entries, engine=engine)


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
            line = format_hit(index, shown, slot.truncated, found.entry.name, found.entry.note)
            hits.append(
                Hit(
                    index=index,
                    read_text=shown,
                    entry_name=found.entry.name,
                    note=found.entry.note,
                    truncated=slot.truncated,
                    line=line,
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
    )
    return result


def _message(anchor: Anchor, slots: list[NameSlot], hits: list[Hit]) -> str:
    parts: list[str] = []
    if anchor.countdown_seconds is not None:
        parts.append(f"倒计时 {anchor.countdown_seconds} 秒")
    if anchor.ready_count is not None:
        parts.append(f"准备就绪 {anchor.ready_count}/12")
    if hits:
        parts.append(f"发现 {len(hits)} 条黑名单匹配")
    else:
        parts.append("黑名单里没有这些人")
    unclear = sum(1 for slot in slots if slot.unclear)
    if unclear:
        parts.append(f"{unclear} 个名字没看清")
    return "已检查这间大厅：" + "，".join(parts) + "。"
