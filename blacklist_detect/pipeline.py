"""One check: header, twelve name strips, blacklist. No clicks, no memory reads."""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
from PIL import Image

from blacklist_detect.layout import (
    Anchor,
    contains_title,
    countdown_in,
    find_anchor,
    game_screen,
    ready_in,
    snap_button_box,
)
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
    # The whole game screen as the lobby places it (layout.game_screen), in the same pixels.
    game_box: tuple[float, float, float, float] | None = None
    # Seconds each step took (capture, find, read), for the log.
    timings: dict[str, float] = field(default_factory=dict)
    # The windows front to back at the screenshot, to find the game's window in (game_area).
    windows: tuple[int, ...] = ()


def load_rgb(path: str | Path) -> np.ndarray:
    image = Image.open(path).convert("RGB")
    return np.asarray(image)


def check_image(path: str | Path, entries: list[Entry], engine=None) -> CheckResult:
    return check_rgb(load_rgb(path), entries, engine=engine)


def check_frames(frames: list[np.ndarray], entries: list[Entry], engine=None, on_lobby=None) -> CheckResult:
    """Header-scan each monitor copy and read names only on the one that matches.

    Where the lobby was last time is tried first: a game's window seldom moves between lobbies, so
    the search is skipped when its title looks as it did (see _at_spot)."""
    if not frames:
        return CheckResult(False, "截屏失败，再试一次")
    reader = engine or get_engine()
    chosen: tuple[np.ndarray, Anchor, list[OcrLine]] | None = None
    last_reason = "没有找到「推演成功」大厅"
    started = time.perf_counter()
    spot = getattr(reader, "lobby_spot", None)
    at_spot = False
    if isinstance(spot, LobbySpot) and hasattr(reader, "read_crops"):
        for frame in frames:
            if frame.shape[:2] != spot.size:
                continue
            anchor, _lines = _at_spot(reader, frame, spot)
            if anchor.found:
                chosen = (frame, anchor, _lines)
                at_spot = True
                break
    for frame in frames if chosen is None else ():
        anchor, _lines = _locate(reader, frame)
        if anchor.found:
            chosen = (frame, anchor, _lines)
            break
        last_reason = anchor.reason or last_reason
    if chosen is None:
        result = CheckResult(False, last_reason)
        result.preview_rgb = frames[0]
        result.timings["find"] = time.perf_counter() - started
        return result
    frame, anchor, _lines = chosen
    if not at_spot and hasattr(reader, "lobby_spot"):
        # Found by searching: remember where, for the next check.
        reader.lobby_spot = _remember(frame, anchor, _lines)
    button = snap_button_box(frame, anchor.button_box)
    found = time.perf_counter()
    if on_lobby is not None and button is not None:
        on_lobby(button)
    result = _read_names(reader, frame, anchor, entries)
    result.button_box = button
    result.game_box = game_screen(anchor)
    result.timings["find"] = found - started
    result.timings["read"] = time.perf_counter() - found
    if at_spot:
        result.timings["spot"] = 1.0
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
    """Find the lobby: first by reading only the title and the few lines under it, and when that
    does not find it, by reading every line on the screen. So the quick way can only be faster,
    never miss a lobby the full read would find; a press with no lobby on screen pays for both."""
    small, factor = downscale_rgb(rgb, max_width=1280)
    bgr = rgb_to_bgr(small)
    height, width = rgb.shape[:2]
    quick = getattr(engine, "read_lobby_lines", None)
    lines = quick(bgr) if quick is not None else None
    if lines is not None:
        lines = scale_lines(lines, factor)
        anchor = find_anchor(lines, width, height)
        if anchor.found:
            return anchor, lines
        if factor > 1.0 and contains_title(lines):
            # The title is there, but the lines under it were too small to read once the screen was
            # shrunk (a game window on a big screen): read them again, sharp, from the full copy.
            sharp = _under_title(engine, rgb, lines)
            anchor = find_anchor(sharp, width, height)
            if anchor.found:
                return anchor, sharp
    lines = scale_lines(engine.read_bgr(bgr), factor)
    return find_anchor(lines, width, height), lines


# The title as a small gray picture, to tell whether the lobby is still where it was: the same window
# shows the same pixels, a moved or resized one does not. Mean difference per pixel, 0 to 255.
SPOT_THUMB = (96, 24)
SPOT_STILL = 12.0


@dataclass(frozen=True)
class LobbySpot:
    """Where the last lobby was: the search's own anchor, the title as a thumbnail, and where the
    countdown and 准备就绪 lines were, read again each time since they change."""

    size: tuple[int, int]
    anchor: Anchor
    thumb: np.ndarray
    lines: tuple[tuple[float, float, float, float] | None, tuple[float, float, float, float] | None]


def _thumb(rgb: np.ndarray, box) -> np.ndarray:  # noqa: ANN001
    left, top, right, bottom = (int(round(value)) for value in box)
    crop = rgb[max(0, top):max(top + 1, bottom), max(0, left):max(left + 1, right)]
    return np.asarray(Image.fromarray(crop).convert("L").resize(SPOT_THUMB, Image.BILINEAR), dtype=np.float32)


def _remember(frame: np.ndarray, anchor: Anchor, lines: list[OcrLine]) -> LobbySpot | None:
    if anchor.title_box is None:
        return None
    ready = next((line.box for line in lines if ready_in(line.text) is not None), None)
    return LobbySpot(frame.shape[:2], anchor, _thumb(frame, anchor.title_box), (anchor.countdown_box, ready))


def _cut(rgb: np.ndarray, box) -> np.ndarray:  # noqa: ANN001
    """A text line cut out for reading, with a little room round it, as BGR."""
    left, top, right, bottom = box
    pad = 0.15 * (bottom - top)
    height, width = rgb.shape[:2]
    x0, x1 = max(0, int(left - pad)), min(width, int(right + pad))
    y0, y1 = max(0, int(top - pad)), min(height, int(bottom + pad))
    return rgb_to_bgr(rgb[y0:y1, x0:x1])


def _at_spot(engine, rgb: np.ndarray, spot: LobbySpot) -> tuple[Anchor, list[OcrLine]]:  # noqa: ANN001
    """The lobby where it was last time, without searching. The title must look as it did, pixel
    for pixel; then the search's own anchor is used, so the names are cut and read exactly as a
    search would, and only the countdown and 准备就绪 are read again where they were. A window that
    moved, changed size or shows something else is searched for as usual."""
    title = spot.anchor.title_box
    if title is None or float(np.abs(_thumb(rgb, title) - spot.thumb).mean()) > SPOT_STILL:
        return Anchor(False, "没有找到「推演成功」大厅"), []
    boxes = [box for box in spot.lines if box is not None]
    read = engine.read_crops([_cut(rgb, box) for box in boxes]) if boxes else []
    if read is None:
        return Anchor(False, "没有找到「推演成功」大厅"), []
    texts = dict(zip(boxes, (text for text, _score in read), strict=False))
    countdown_box, ready_box = spot.lines
    seconds = countdown_in(texts.get(countdown_box, "")) if countdown_box is not None else None
    ready = ready_in(texts.get(ready_box, "")) if ready_box is not None else None
    return replace(spot.anchor, countdown_seconds=seconds, ready_count=ready), []


def _under_title(engine, rgb: np.ndarray, lines: list[OcrLine]) -> list[OcrLine]:
    """The lines around 推演成功, read from the full-size copy: the title, the header under it and
    准备就绪, which sit within a few title-heights of it (see ocr_engine.LOBBY_BANDS)."""
    title = next(line for line in lines if "推演成功" in line.text.replace(" ", ""))
    left, top, right, bottom = title.box
    title_w, title_h, middle = right - left, bottom - top, (left + right) / 2
    height, width = rgb.shape[:2]
    x0, x1 = max(0, int(middle - 1.4 * title_w)), min(width, int(middle + 1.4 * title_w))
    y0, y1 = max(0, int(top - 0.4 * title_h)), min(height, int(top + 7.6 * title_h))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return lines
    found = engine.read_bgr(rgb_to_bgr(rgb[y0:y1, x0:x1]))
    return [OcrLine(line.text, line.confidence, (line.box[0] + x0, line.box[1] + y0, line.box[2] + x0, line.box[3] + y0)) for line in found]


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
    parts: list[str] = []
    if anchor.countdown_seconds is not None:
        parts.append(f"倒计时 {anchor.countdown_seconds} 秒")
    if anchor.ready_count is not None:
        parts.append(f"准备就绪 {anchor.ready_count}/12")
    if hits:
        parts.append(f"发现 {len(hits)} 名黑名单玩家")
    else:
        parts.append("未发现黑名单玩家")
    unclear = sum(1 for slot in slots if slot.unclear)
    if unclear:
        parts.append(f"{unclear} 人未识别")
    return "检查完成：" + "，".join(parts) + "。"
