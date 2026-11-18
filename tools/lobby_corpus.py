"""Build a corpus of real 模仿者狂欢 lobby frames from Bilibili videos, for comparing OCR engines.

    python tools/lobby_corpus.py <video, space or list URL> [--max-videos N] [--per-video N]

One video at a time: download it with yt-dlp (no login, best quality offered), sample a frame every few seconds,
keep the frames where the lobby title 推演成功 is on screen, keep the sharpest frame of each distinct lobby, save it
whole as JPEG into tests/lobby_corpus/<video-id>_<seconds>.jpg, add it to index.json, and delete the video.

Needs yt-dlp, opencv-python-headless, rapidocr-onnxruntime and ffmpeg. RapidOCR only decides whether a frame shows a
lobby; the reference reading of the names is Paddle's, made elsewhere. Real player names in these frames stay in
this corpus and never go into anything user-facing.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "tests" / "lobby_corpus"
STEP_S = 3.0  # the lobby countdown shows for 10 s or more, so a 3 s step sees each lobby several times
GAP_S = 20.0  # hits closer than this are the same lobby
DETECT_WIDTH = 640
TITLE = "推演成功"
TITLE_HINTS = ("模仿者狂欢", "准备就绪", "12人狂欢")

_ocr = None


def _engine():
    global _ocr
    if _ocr is None:
        from rapidocr_onnxruntime import RapidOCR

        _ocr = RapidOCR()
    return _ocr


def _shared(a: str, b: str) -> int:
    return sum(1 for ch in set(b) if ch in a)


def lobby_texts(texts: list[str]) -> bool:
    """True when the read lines show the lobby: the title (3 of its 4 characters) and one more lobby line."""
    joined = "".join(texts).replace(" ", "")
    title = any(_shared(t.replace(" ", ""), TITLE) >= 3 for t in texts)
    hint = any(hint in joined for hint in TITLE_HINTS) or "倒计时" in joined
    return title and hint


def shows_lobby(rgb: np.ndarray) -> bool:
    """Read the top half of a whole frame, small, and look for the lobby's title lines."""
    import cv2

    height, width = rgb.shape[:2]
    scale = DETECT_WIDTH / width
    small = cv2.resize(rgb, (DETECT_WIDTH, max(1, round(height * scale))), interpolation=cv2.INTER_AREA)
    top = small[: int(small.shape[0] * 0.6)]
    result, _ = _engine()(cv2.cvtColor(top, cv2.COLOR_RGB2BGR))
    return lobby_texts([line[1] for line in result or []])


def sharpness(rgb: np.ndarray) -> float:
    import cv2

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


@dataclass
class Hit:
    seconds: float
    sharp: float
    frame: np.ndarray


def group_hits(hits: list[Hit], gap: float = GAP_S) -> list[Hit]:
    """One hit per distinct lobby: hits within `gap` seconds of the last are the same lobby; keep the sharpest."""
    best: list[Hit] = []
    last = None
    for hit in sorted(hits, key=lambda h: h.seconds):
        if last is not None and hit.seconds - last <= gap:
            if hit.sharp > best[-1].sharp:
                best[-1] = hit
        else:
            best.append(hit)
        last = hit.seconds
    return best


def _probe(path: Path) -> tuple[int, int, float]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    info = json.loads(out)
    stream = info["streams"][0]
    return int(stream["width"]), int(stream["height"]), float(info["format"]["duration"])


def frames(path: Path, step: float, start: float = 0.0, length: float | None = None):
    """Yield (seconds, rgb) every `step` seconds, decoded by ffmpeg at full resolution."""
    width, height, _ = _probe(path)
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}"]
    if length is not None:
        cmd += ["-t", f"{length:.3f}"]
    cmd += ["-i", str(path), "-vf", f"fps=1/{step}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    size = width * height * 3
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
        index = 0
        while True:
            raw = proc.stdout.read(size)
            if len(raw) < size:
                break
            yield start + index * step, np.frombuffer(raw, np.uint8).reshape(height, width, 3)
            index += 1


def find_lobbies(path: Path, step: float = STEP_S) -> list[Hit]:
    """Coarse pass every `step` s, then a 1 s pass around each lobby to pick its sharpest frame."""
    coarse = [Hit(t, 0.0, np.empty(0)) for t, rgb in frames(path, step) if shows_lobby(rgb)]
    lobbies = group_hits(coarse)
    found = []
    for lobby in lobbies:
        span = [h.seconds for h in coarse if abs(h.seconds - lobby.seconds) <= GAP_S * 2]
        start = max(0.0, min(span) - step)
        fine = [Hit(t, sharpness(rgb), rgb.copy()) for t, rgb in frames(path, 1.0, start, max(span) - start + step)
                if shows_lobby(rgb)]
        if fine:
            found.append(max(fine, key=lambda h: h.sharp))
    return found


def save_jpeg(rgb: np.ndarray, path: Path) -> None:
    import cv2

    cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 95])


def load_index() -> list[dict]:
    path = CORPUS / "index.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def save_index(entries: list[dict]) -> None:
    CORPUS.mkdir(parents=True, exist_ok=True)
    text = json.dumps(sorted(entries, key=lambda e: e["file"]), ensure_ascii=False, indent=1)
    (CORPUS / "index.json").write_text(text + "\n", encoding="utf-8")


def _ytdlp(*args: str) -> subprocess.CompletedProcess:
    exe = shutil.which("yt-dlp") or str(Path(sys.executable).with_name("yt-dlp"))
    return subprocess.run([exe, *args], capture_output=True, text=True)


def list_videos(url: str) -> list[dict]:
    out = _ytdlp("--flat-playlist", "-J", url)
    if out.returncode:
        raise SystemExit(out.stderr.strip()[-800:])
    info = json.loads(out.stdout)
    entries = info.get("entries") or [info]
    return [{"id": e.get("id"), "url": e.get("url") or e.get("webpage_url") or url, "title": e.get("title")}
            for e in entries]


def download(url: str, folder: Path) -> tuple[Path, dict]:
    out = _ytdlp("-f", "bv*", "--no-playlist", "--print-json", "--no-simulate", "-o", str(folder / "%(id)s.%(ext)s"),
                 url)
    if out.returncode:
        raise RuntimeError(out.stderr.strip()[-800:])
    info = json.loads(out.stdout.strip().splitlines()[-1])
    return Path(info.get("_filename") or info["filename"]), info


def process(url: str, per_video: int) -> int:
    entries = load_index()
    done_ids = {e["video_id"] for e in entries}
    with tempfile.TemporaryDirectory(prefix="lobby_dl_") as tmp:
        video, info = download(url, Path(tmp))
        vid = info["id"]
        if vid in done_ids:
            print(f"{vid}: already in the corpus")
            return 0
        width, height, duration = _probe(video)
        print(f"{vid}: {width}x{height}, {duration / 60:.0f} min, {info.get('title')}", flush=True)
        lobbies = find_lobbies(video)
        lobbies = sorted(lobbies, key=lambda h: h.seconds)[:per_video] if per_video else lobbies
        CORPUS.mkdir(parents=True, exist_ok=True)
        for hit in lobbies:
            name = f"{vid}_{int(hit.seconds)}.jpg"
            save_jpeg(hit.frame, CORPUS / name)
            entries.append({"file": name, "video_id": vid, "source_url": info.get("webpage_url") or url,
                            "title": info.get("title"), "seconds": int(hit.seconds),
                            "resolution": f"{width}x{height}", "format": info.get("format_id")})
            print(f"  lobby at {int(hit.seconds)} s -> {name}", flush=True)
        save_index(entries)
    return len(lobbies)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url")
    parser.add_argument("--max-videos", type=int, default=1)
    parser.add_argument("--per-video", type=int, default=0, help="keep at most this many lobbies per video (0: all)")
    args = parser.parse_args()
    total = 0
    for video in list_videos(args.url)[: args.max_videos]:
        try:
            total += process(video["url"], args.per_video)
        except RuntimeError as error:
            print(f"{video['id']}: failed: {error}", flush=True)
    print(f"{total} lobbies saved")


if __name__ == "__main__":
    main()
