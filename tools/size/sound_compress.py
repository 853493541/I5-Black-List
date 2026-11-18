"""Compress the scene tunes the Rust app ships: blacklist_detect/assets/*.wav to rust/assets/sounds/*.ogg (Vorbis).

The Python app keeps its WAVs; only the Rust build takes the .ogg files (sound::tunes::tune_path prefers a tune's .ogg
beside its .wav). Nothing is played: the listening pairs go to a folder for the user to hear later.

    python tools/size/sound_compress.py                    # encode, print sizes and how far each decode is off
    python tools/size/sound_compress.py --measure          # also every codec option tried (needs libopus in ffmpeg)
    python tools/size/sound_compress.py --listen <folder>  # original and compressed side by side, plus LISTEN.txt
    python tools/size/sound_compress.py --stage <folder>   # blacklist_detect/assets with the .ogg in place of the .wav,
                                                           # for build/make_rust_release.py --assets
"""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "blacklist_detect" / "assets"
OUT = ROOT / "rust" / "assets" / "sounds"
# The scene tunes (sound::tunes::TUNES / ui_music.TUNES).
TUNES = ["wedding-organ", "theme-ice", "theme-stars", "theme-cyber", "theme-neon", "wedding-bells", "wedding-canon",
         "theme-fluffy", "ambush", "lyre"]
# Vorbis q6 (about 92 kbps for these mono 44.1 kHz tunes): symphonia's vorbis decoder is already in the exe; its ogg
# reader adds 110,400 bytes (a stripped release build of sound with and without the feature, 2026-11-18).
QUALITY = "6"
OGG_READER = 110_400
# Options measured (--measure): label, ffmpeg codec arguments, extension, decoder bytes the exe would gain.
# Opus needs the same ogg reader and libopus: the shared libopus is 387 KB with its encoder, its decoder alone
# linked static about 250 KB.
OPTIONS = [
    ("wav", None, "wav", 0),
    ("vorbis q4", ["-c:a", "libvorbis", "-q:a", "4"], "ogg", OGG_READER),
    ("vorbis q5", ["-c:a", "libvorbis", "-q:a", "5"], "ogg", OGG_READER),
    ("vorbis q6", ["-c:a", "libvorbis", "-q:a", "6"], "ogg", OGG_READER),
    ("opus 48k", ["-c:a", "libopus", "-b:a", "48k"], "opus", OGG_READER + 250_000),
    ("opus 64k", ["-c:a", "libopus", "-b:a", "64k"], "opus", OGG_READER + 250_000),
    ("opus 96k", ["-c:a", "libopus", "-b:a", "96k"], "opus", OGG_READER + 250_000),
]


def encode(source: Path, target: Path, codec: list[str]) -> None:
    # bitexact and no metadata: the same WAV gives the same bytes on every run.
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(source), *codec, "-fflags", "+bitexact", "-flags:a",
                    "+bitexact", "-map_metadata", "-1", str(target)], check=True)


def samples(path: Path) -> np.ndarray:
    """Mono 44.1 kHz float samples in -1..1, decoded by ffmpeg."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", "44100", "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype="<f4").astype(np.float64)


def db(x: float) -> float:
    return 20 * math.log10(x) if x > 0 else -math.inf


def difference(wav: Path, other: Path) -> tuple[int, float, float]:
    """Frames more or fewer than the WAV, RMS of the difference and its biggest sample, in dB below full scale."""
    a, b = samples(wav), samples(other)
    n = min(len(a), len(b))
    diff = a[:n] - b[:n]
    return len(b) - len(a), db(float(np.sqrt(np.mean(diff**2)))), db(float(np.max(np.abs(diff))))


def compress() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    before = after = 0
    print(f"{'tune':15} {'wav':>8} {'ogg':>8} {'frames':>6} {'rms dB':>7} {'peak dB':>7}")
    for name in TUNES:
        wav, ogg = SOURCE / f"{name}.wav", OUT / f"{name}.ogg"
        encode(wav, ogg, ["-c:a", "libvorbis", "-q:a", QUALITY])
        before, after = before + wav.stat().st_size, after + ogg.stat().st_size
        extra, rms, peak = difference(wav, ogg)
        print(f"{name:15} {wav.stat().st_size:8} {ogg.stat().st_size:8} {extra:6} {rms:7.1f} {peak:7.1f}")
    print(f"{'total':15} {before:8} {after:8}  ({after / before:.1%})")


def measure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        print(f"{'option':10} {'assets':>8} {'decoder':>8} {'total':>8} {'worst rms dB':>12}")
        for label, codec, ext, decoder in OPTIONS:
            size, worst = 0, -math.inf
            for name in TUNES:
                wav = SOURCE / f"{name}.wav"
                if codec is None:
                    size += wav.stat().st_size
                    continue
                target = Path(tmp) / f"{name}.{ext}"
                encode(wav, target, codec)
                size += target.stat().st_size
                worst = max(worst, difference(wav, target)[1])
            print(f"{label:10} {size:8} {decoder:8} {size + decoder:8} {worst:12.1f}")


def listen(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    lines = ["Each scene tune twice: A is the original WAV, B the compressed one the Rust app ships.",
             "Play A then B (or B then A without looking) and note any tune where you hear a difference.", ""]
    for i, name in enumerate(TUNES, 1):
        shutil.copy(SOURCE / f"{name}.wav", folder / f"{i:02}-{name}-A-original.wav")
        shutil.copy(OUT / f"{name}.ogg", folder / f"{i:02}-{name}-B-compressed.ogg")
        lines.append(f"{i:02}  {name:14}  {i:02}-{name}-A-original.wav  /  {i:02}-{name}-B-compressed.ogg")
    (folder / "LISTEN.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"listening pairs in {folder}")


def stage(folder: Path) -> None:
    """The assets folder a Rust release ships: every file but the tunes' WAVs, and the tunes as .ogg."""
    if folder.exists():
        shutil.rmtree(folder)
    shutil.copytree(SOURCE, folder, ignore=shutil.ignore_patterns(*(f"{name}.wav" for name in TUNES)))
    for name in TUNES:
        shutil.copy(OUT / f"{name}.ogg", folder / f"{name}.ogg")
    print(f"staged assets in {folder}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--measure", action="store_true", help="also measure every codec option")
    parser.add_argument("--listen", type=Path, help="folder for the side-by-side listening files")
    parser.add_argument("--stage", type=Path, help="folder for the release's assets with the tunes compressed")
    args = parser.parse_args()
    for name in TUNES:
        with wave.open(str(SOURCE / f"{name}.wav")) as w:
            assert w.getsampwidth() == 2, name
    compress()
    if args.measure:
        measure()
    if args.listen:
        listen(args.listen)
    if args.stage:
        stage(args.stage)
    return 0


if __name__ == "__main__":
    sys.exit(main())
