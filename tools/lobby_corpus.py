"""Build a corpus of real 模仿者狂欢 lobby frames from Bilibili videos, for comparing OCR engines.

    python tools/lobby_corpus.py <video, space or list URL> [--max-videos N] [--per-video N]

One video part at a time, streamed and never saved (no login, best quality offered): read a 480p stream every few
seconds for the lobby title 推演成功, then take the frames around each lobby from the best stream by seeking, keep the
sharpest, and save it whole as JPEG into tests/lobby_corpus/<video-id>_<seconds>.jpg with a line in index.json.

Needs yt-dlp, opencv-python-headless, rapidocr-onnxruntime and ffmpeg. RapidOCR only decides whether a frame shows a
lobby; the reference reading of the names is Paddle's, made elsewhere. Real player names in these frames stay in
this corpus and never go into anything user-facing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "tests" / "lobby_corpus"
STEP_S = 12.0  # a lobby stays on screen about 15 s, so a 12 s step sees each one at least once
GAP_S = 20.0  # hits closer than this are the same lobby
DETECT_WIDTH = 640
WORKERS = 4
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
    """Read the top of a whole frame, small, and look for the lobby's title lines."""
    import cv2

    height, width = rgb.shape[:2]
    if width != DETECT_WIDTH:
        rgb = cv2.resize(rgb, (DETECT_WIDTH, max(1, round(height * DETECT_WIDTH / width))), interpolation=cv2.INTER_AREA)
    top = rgb[: int(rgb.shape[0] * 0.6)]
    result, _ = _engine()(cv2.cvtColor(top, cv2.COLOR_RGB2BGR))
    return lobby_texts([line[1] for line in result or []])


def _check(item: tuple[float, np.ndarray]) -> tuple[float, bool]:
    return item[0], shows_lobby(item[1])


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


@dataclass
class Source:
    where: str  # a local file or a stream URL
    width: int
    height: int


def local(path: Path) -> Source:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json",
         str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    stream = json.loads(out)["streams"][0]
    return Source(str(path), int(stream["width"]), int(stream["height"]))


def _input(source: Source) -> list[str]:
    """ffmpeg's input options: a Bilibili stream needs the Referer, and ffmpeg takes the proxy only when told."""
    if not source.where.startswith("http"):
        return []
    args = ["-headers", "Referer: https://www.bilibili.com/\r\n", "-user_agent", "Mozilla/5.0", "-reconnect", "1"]
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    return args + (["-http_proxy", proxy] if proxy else [])


def _read_bytes(log: str) -> int:
    return sum(int(n) for n in re.findall(r"Statistics: (\d+) bytes read", log))


def frames(source: Source, step: float, start: float, length: float, width_to: int = 0) -> tuple[list, int]:
    """(seconds, rgb) every `step` seconds over a short window, decoded in one pass, and the bytes it fetched."""
    width, height, scale = source.width, source.height, ""
    if width_to:
        height = round(height * width_to / width / 2) * 2
        width = width_to
        scale = f",scale={width}:{height}"
    cmd = ["ffmpeg", "-v", "verbose", *_input(source), "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", source.where,
           "-vf", f"fps=1/{step}{scale}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    done = subprocess.run(cmd, capture_output=True, timeout=240)
    size = width * height * 3
    raw = done.stdout
    shots = [(start + i * step, np.frombuffer(raw[i * size:(i + 1) * size], np.uint8).reshape(height, width, 3))
             for i in range(len(raw) // size)]
    return shots, _read_bytes(done.stderr.decode(errors="replace"))


def grab(source: Source, seconds: float) -> tuple[np.ndarray | None, int]:
    """One whole frame at `seconds` by seeking, so a stream sends only the part around it; and the bytes fetched."""
    cmd = ["ffmpeg", "-v", "verbose", *_input(source), "-ss", f"{seconds:.3f}", "-i", source.where, "-frames:v", "1",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    done = subprocess.run(cmd, capture_output=True, timeout=120)
    raw, size = done.stdout, source.width * source.height * 3
    rgb = np.frombuffer(raw[:size], np.uint8).reshape(source.height, source.width, 3) if len(raw) >= size else None
    return rgb, _read_bytes(done.stderr.decode(errors="replace"))


def _probe_at(job: tuple[Source, float]) -> tuple[float, bool, int]:
    source, seconds = job
    rgb, fetched = grab(source, seconds)
    return seconds, rgb is not None and shows_lobby(rgb), fetched


def _check(item: tuple[float, np.ndarray]) -> tuple[float, bool]:
    return item[0], shows_lobby(item[1])


def find_lobbies(scan: Source, duration: float, full: Source | None = None, step: float = STEP_S, picks: int = 8,
                 on_lobby=None) -> tuple[list[Hit], int]:  # noqa: ANN001
    """Probe `scan` (small) by seeking every `step` s; around each hit decode `scan` every 1 s; take up to `picks`
    of the lobby's seconds from `full` (best quality) and keep the sharpest that still shows the lobby.
    Returns the lobbies and the bytes fetched."""
    from multiprocessing import Pool

    full = full or scan
    times = list(np.arange(step / 2, duration, step))
    fetched, hits, found = 0, [], []
    with Pool(WORKERS) as pool:
        for n, (t, hit, got) in enumerate(pool.imap(_probe_at, [(scan, float(t)) for t in times]), 1):
            fetched += got
            if hit:
                hits.append(Hit(t, 0.0, np.empty(0)))
            if n % 60 == 0:
                print(f"  probed {t / 60:.0f}/{duration / 60:.0f} min, {len(hits)} hits, {fetched / 2**20:.0f} MiB",
                      flush=True)
        for lobby in group_hits(hits):
            span = [h.seconds for h in hits if abs(h.seconds - lobby.seconds) <= GAP_S * 2]
            start = max(0.0, min(span) - step)
            shots, got = frames(scan, 1.0, start, max(span) - start + step, width_to=DETECT_WIDTH)
            fetched += got
            seconds = [t for t, ok in pool.map(_check, shots) if ok]
            chosen = sorted({seconds[round(i * (len(seconds) - 1) / max(1, picks - 1))]
                             for i in range(min(picks, len(seconds)))})
            best = None
            for t, (rgb, got) in zip(chosen, pool.map(_grab_full, [(full, t) for t in chosen]), strict=True):
                fetched += got
                if rgb is None or not shows_lobby(rgb):
                    continue
                if best is None or sharpness(rgb) > best.sharp:
                    best = Hit(t, sharpness(rgb), rgb)
            if best is not None:
                found.append(best)
                if on_lobby is not None:
                    on_lobby(best)
    return found, fetched


def _grab_full(job: tuple[Source, float]) -> tuple[np.ndarray | None, int]:
    return grab(*job)


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


def _series(url: str) -> list[dict] | None:
    """A space series list (space.bilibili.com/<mid>/lists/<id>?type=series), newest first as the page shows it,
    read from api.bilibili.com: yt-dlp would fetch space.bilibili.com, which the network may not allow."""

    found = re.search(r"space\.bilibili\.com/(\d+)/lists/(\d+)", url)
    if not found or "type=season" in url:
        return None
    mid, series = found.groups()
    api = f"https://api.bilibili.com/x/series/archives?mid={mid}&series_id={series}&pn=1&ps=100&sort=desc"
    archives = _get_json(api)["data"]["archives"]
    return [{"id": a["bvid"], "url": f"https://www.bilibili.com/video/{a['bvid']}", "title": a["title"]}
            for a in archives]


def _get_json(url: str) -> dict:
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def parts(video: dict) -> list[dict]:
    """A stream replay is one BV with several parts (p=1, 2, ...): one entry per part."""

    found = re.search(r"(BV[0-9A-Za-z]{10})", video["url"])
    if not found:
        return [video]
    out = _ytdlp("--flat-playlist", "-J", f"https://www.bilibili.com/video/{found.group(1)}")
    if out.returncode:
        raise RuntimeError(out.stderr.strip()[-800:])
    pages = json.loads(out.stdout).get("entries") or []
    if len(pages) <= 1:
        return [video]
    return [{"id": f"{video['id']}_p{n}", "url": f"https://www.bilibili.com/video/{found.group(1)}?p={n}",
             "title": f"{video['title']} P{n}"} for n in range(1, len(pages) + 1)]


def list_videos(url: str) -> list[dict]:
    series = _series(url)
    if series is not None:
        return series
    out = _ytdlp("--flat-playlist", "-J", url)
    if out.returncode:
        raise SystemExit(out.stderr.strip()[-800:])
    info = json.loads(out.stdout)
    entries = info.get("entries") or [info]
    return [{"id": e.get("id"), "url": e.get("url") or e.get("webpage_url") or url, "title": e.get("title")}
            for e in entries]


def streams(url: str, tries: int = 8) -> tuple[Source, Source, dict]:
    """The scan stream (the smallest H.264 at 480p or more) and the full one (the largest H.264), both on a CDN
    host that serves them: the akamaized mirror refuses with 403, so ask again until both are elsewhere."""
    for _ in range(tries):
        out = _ytdlp("-J", "--no-playlist", url)
        if out.returncode:
            raise RuntimeError(out.stderr.strip()[-800:])
        info = json.loads(out.stdout)
        videos = [f for f in info.get("formats", []) if f.get("vcodec", "none").startswith("avc1") and f.get("height")]
        if not videos:
            raise RuntimeError("no H.264 video stream")
        full = max(videos, key=lambda f: (f["height"], f.get("tbr") or 0))
        scan = min((f for f in videos if f["height"] >= 480), key=lambda f: f["height"], default=full)
        if not any("akamaized" in f["url"] for f in (full, scan)):
            info["full_format"] = full
            return (Source(scan["url"], scan["width"], scan["height"]), Source(full["url"], full["width"], full["height"]),
                    info)
    raise RuntimeError("only the akamaized mirror was offered")


def process(video: dict, per_video: int) -> int:
    url, vid = video["url"], video["id"]
    entries = load_index()
    if vid in {e["video_id"] for e in entries}:
        print(f"{vid}: already in the corpus")
        return 0
    scan, full, info = streams(url)
    duration = float(info.get("duration") or 0)
    total = sum(f.get("filesize") or f.get("filesize_approx") or 0 for f in [info["full_format"]])
    print(f"{vid}: {full.width}x{full.height}, {duration / 60:.0f} min, {video.get('title')}", flush=True)
    CORPUS.mkdir(parents=True, exist_ok=True)
    saved = []

    def keep(hit: Hit) -> None:
        if per_video and len(saved) >= per_video:
            return
        name = f"{vid}_{int(hit.seconds)}.jpg"
        save_jpeg(hit.frame, CORPUS / name)
        entries.append({"file": name, "video_id": vid, "source_url": url, "title": video.get("title") or info.get("title"),
                        "seconds": int(hit.seconds), "resolution": f"{full.width}x{full.height}",
                        "format": info["full_format"].get("format_id")})
        save_index(entries)
        saved.append(name)
        print(f"  lobby at {int(hit.seconds)} s -> {name}", flush=True)

    _, fetched = find_lobbies(scan, duration, full, on_lobby=keep)
    print(f"{vid}: {len(saved)} lobbies, fetched {fetched / 2**20:.0f} MiB of a {total / 2**20:.0f} MiB "
          f"{full.height}p video", flush=True)
    return len(saved)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url")
    parser.add_argument("--max-videos", type=int, default=1)
    parser.add_argument("--per-video", type=int, default=0, help="keep at most this many lobbies per video (0: all)")
    args = parser.parse_args()
    total = 0
    for video in list_videos(args.url)[: args.max_videos]:
        for part in parts(video):
            try:
                total += process(part, args.per_video)
            except RuntimeError as error:
                print(f"{part['id']}: failed: {error}", flush=True)
    print(f"{total} lobbies saved")


if __name__ == "__main__":
    main()
