"""Find the match-found header and place the twelve name strips from it."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from blacklist_detect.model import OcrLine

# The reference shot is 3270×1695. Boxes are fractions of that shot:
# left, top, right, bottom. They describe this lobby, then get scaled
# from wherever the header is found on a later capture.
REF_W = 3270
REF_H = 1695

TITLE_BOX = (0.435, 0.074, 0.635, 0.187)
MODE_BOX = (0.401, 0.199, 0.654, 0.247)
COUNTDOWN_BOX = (0.466, 0.253, 0.604, 0.296)

NAME_BOXES: tuple[tuple[float, float, float, float], ...] = (
    (0.136, 0.487, 0.232, 0.527),
    (0.288, 0.489, 0.366, 0.526),
    (0.417, 0.483, 0.514, 0.528),
    (0.550, 0.486, 0.632, 0.528),
    (0.711, 0.486, 0.772, 0.530),
    (0.848, 0.487, 0.909, 0.528),
    (0.151, 0.777, 0.229, 0.817),
    (0.273, 0.774, 0.373, 0.819),
    (0.434, 0.774, 0.497, 0.818),
    (0.572, 0.773, 0.635, 0.815),
    (0.692, 0.777, 0.789, 0.816),
    (0.831, 0.776, 0.928, 0.816),
)

_COUNTDOWN_RE = re.compile(r"倒计时\s*[:：]?\s*(\d{1,3})\s*秒")
_READY_RE = re.compile(r"准备就绪\s*[:：]?\s*(\d{1,2})\s*/\s*12")


@dataclass(frozen=True)
class Anchor:
    found: bool
    reason: str
    countdown_seconds: int | None = None
    ready_count: int | None = None
    scale: float = 0.0
    name_boxes: tuple[tuple[int, int, int, int], ...] = ()
    title_box: tuple[float, float, float, float] | None = None
    mode_box: tuple[float, float, float, float] | None = None
    countdown_box: tuple[float, float, float, float] | None = None


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text or ""))


def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    left, top, right, bottom = box
    return (left + right) / 2.0, (top + bottom) / 2.0


def _union(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _height(box: tuple[float, float, float, float]) -> float:
    return max(0.0, box[3] - box[1])


def _vertical_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    if overlap <= 0:
        return 0.0
    smaller = min(_height(a), _height(b))
    if smaller <= 0:
        return 0.0
    return overlap / smaller


def _frac_to_px(box: tuple[float, float, float, float], width: int, height: int) -> tuple[float, float, float, float]:
    return (box[0] * width, box[1] * height, box[2] * width, box[3] * height)


def _x_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    return min(a[2], b[2]) - max(a[0], b[0])


def _same_row(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    if _vertical_overlap(a, b) >= 0.45:
        return True
    ay = _center(a)[1]
    by = _center(b)[1]
    return abs(ay - by) <= 0.45 * max(8.0, min(_height(a), _height(b)))


def _pick_tight(candidates: list[OcrLine], phrase: str) -> OcrLine | None:
    """Prefer the line that is the phrase, not the phrase plus a neighbor."""
    if not candidates:
        return None
    folded_len = len(_norm(phrase))

    def sort_key(line: OcrLine) -> tuple[float, float]:
        extra = max(0, len(_norm(line.text)) - folded_len)
        return (extra, -_height(line.box))

    return sorted(candidates, key=sort_key)[0]


def _assemble_mode(lines: list[OcrLine]) -> OcrLine | None:
    direct = [
        line
        for line in lines
        if "模仿者狂欢" in _norm(line.text) and "12人狂欢" in _norm(line.text)
    ]
    chosen = _pick_tight(direct, "模仿者狂欢（12人狂欢）")
    if chosen is not None:
        return chosen
    left = [line for line in lines if "模仿者狂欢" in _norm(line.text)]
    right = [line for line in lines if "12人狂欢" in _norm(line.text)]
    best: OcrLine | None = None
    best_gap = 10**9
    for a in left:
        for b in right:
            if a is b or not _same_row(a.box, b.box):
                continue
            gap = abs(_center(a.box)[0] - _center(b.box)[0])
            if gap < best_gap:
                best_gap = gap
                text = a.text + b.text if a.box[0] <= b.box[0] else b.text + a.text
                best = OcrLine(text, min(a.confidence, b.confidence), _union([a.box, b.box]))
    return best


def _assemble_countdown(lines: list[OcrLine]) -> tuple[OcrLine, int] | None:
    """倒计时, a seconds count, and 秒. The count is not required to be 10.

    The detector often splits 「倒计时」 from 「10秒」. Those pieces are one line.
    """
    bases = [line for line in lines if "倒计时" in _norm(line.text)]
    best: tuple[float, OcrLine, int] | None = None
    for base in bases:
        group = [base]
        limit = 4 * max(_height(base.box), 16)
        for other in lines:
            if other is base or not _same_row(base.box, other.box):
                continue
            if other.box[0] < base.box[0] - 8:
                continue
            if other.box[0] - base.box[2] > limit:
                continue
            token = _norm(other.text)
            if re.fullmatch(r"\d{1,3}|秒|\d{1,3}秒", token):
                group.append(other)
        ordered = sorted(group, key=lambda line: line.box[0])
        text = "".join(_norm(line.text) for line in ordered)
        count = re.search(r"倒计时[:：]?(\d{1,3})秒", text)
        if not count:
            continue
        box = _union([line.box for line in ordered])
        confidence = min(line.confidence for line in ordered)
        line = OcrLine(text, confidence, box)
        score = _height(box)
        if best is None or score > best[0]:
            best = (score, line, int(count.group(1)))
    if best is None:
        return None
    return best[1], best[2]


def find_anchor(lines: list[OcrLine], image_width: int, image_height: int) -> Anchor:
    """Require 推演成功, 模仿者狂欢（12人狂欢）, and 倒计时 <seconds> 秒.

    The seconds value is whatever is printed. It is not fixed at 10.
    A line beside the title is not part of the title, so it does not move the names.
    """
    titles = [line for line in lines if "推演成功" in _norm(line.text)]
    title = _pick_tight(titles, "推演成功")
    mode = _assemble_mode(lines)
    countdown = _assemble_countdown(lines)
    ready_count: int | None = None
    ready_y = 10**9
    for line in lines:
        ready = _READY_RE.search(unicodedata.normalize("NFKC", line.text or ""))
        if ready and line.box[1] < ready_y:
            ready_count = int(ready.group(1))
            ready_y = line.box[1]

    missing: list[str] = []
    if title is None:
        missing.append("推演成功")
    if mode is None:
        missing.append("模仿者狂欢（12人狂欢）")
    if countdown is None:
        missing.append("倒计时 … 秒")
    if missing:
        joined = "、".join(f"「{item}」" for item in missing)
        return Anchor(False, f"没有找到这间大厅，还缺{joined}。", ready_count=ready_count)

    assert title is not None and mode is not None and countdown is not None
    countdown_line, seconds = countdown
    titles = [title]
    modes = [mode]
    countdowns = [(countdown_line, seconds)]

    ref_title = _frac_to_px(TITLE_BOX, REF_W, REF_H)
    ref_count = _frac_to_px(COUNTDOWN_BOX, REF_W, REF_H)
    ref_title_c = _center(ref_title)
    ref_dy = _center(ref_count)[1] - ref_title_c[1]
    if ref_dy <= 0:
        return Anchor(False, "参考布局的标题和倒计时重叠，无法对齐。")

    best: tuple[float, OcrLine, OcrLine, OcrLine, int, float] | None = None
    for title in titles:
        for mode in modes:
            for countdown, seconds in countdowns:
                title_c = _center(title.box)
                mode_c = _center(mode.box)
                count_c = _center(countdown.box)
                if not (title_c[1] < mode_c[1] < count_c[1]):
                    continue
                if _x_overlap(title.box, mode.box) <= 0 or _x_overlap(mode.box, countdown.box) <= 0:
                    continue
                det_dy = count_c[1] - title_c[1]
                if det_dy < 8:
                    continue
                scale = det_dy / ref_dy
                if scale < 0.15 or scale > 6:
                    continue
                # Prefer the tightest header that still stacks in order.
                span = count_c[1] - title_c[1]
                drift = abs(title_c[0] - count_c[0])
                score = span + drift
                if best is None or score < best[0]:
                    best = (score, title, mode, countdown, seconds, scale)

    if best is None:
        return Anchor(
            False,
            "看到了标题、模式或倒计时，但三者不在同一块区域。",
            ready_count=ready_count,
        )

    _score, title, mode, countdown, seconds, scale = best
    title_c = _center(title.box)
    name_boxes: list[tuple[int, int, int, int]] = []
    for frac in NAME_BOXES:
        ref = _frac_to_px(frac, REF_W, REF_H)
        mapped = []
        for x, y in ((ref[0], ref[1]), (ref[2], ref[1]), (ref[0], ref[3]), (ref[2], ref[3])):
            mapped.append(
                (
                    title_c[0] + (x - ref_title_c[0]) * scale,
                    title_c[1] + (y - ref_title_c[1]) * scale,
                )
            )
        left = int(round(min(point[0] for point in mapped)))
        top = int(round(min(point[1] for point in mapped)))
        right = int(round(max(point[0] for point in mapped)))
        bottom = int(round(max(point[1] for point in mapped)))
        left = max(0, min(image_width - 1, left))
        top = max(0, min(image_height - 1, top))
        right = max(left + 1, min(image_width, right))
        bottom = max(top + 1, min(image_height, bottom))
        name_boxes.append((left, top, right, bottom))

    return Anchor(
        found=True,
        reason="",
        countdown_seconds=seconds,
        ready_count=ready_count,
        scale=scale,
        name_boxes=tuple(name_boxes),
        title_box=title.box,
        mode_box=mode.box,
        countdown_box=countdown.box,
    )
