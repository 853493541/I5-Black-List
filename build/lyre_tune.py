"""Cut 竖琴清风's tune into blacklist_detect/assets/lyre.wav.

    python build/lyre_tune.py

温迪's character-demo music, 诗人的工作 (Bard's Adventure, HOYO-MiX), at its hook: build/sounds/bard.wav is
6.0 s of it, song time 0:39.95 to 0:45.95. It is the game's own recording, the user's choice made knowing
HoYoverse owns it. The section's downbeat lands on the lyre's first strum (love_scenes.lyre.STRUMS).

Mono 16-bit 44.1 kHz, as long as the scene, at about -19 dBFS with peaks under -3 dBFS like the others.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100
ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "build" / "sounds" / "bard.wav"
OUT = ROOT / "blacklist_detect" / "assets" / "lyre.wav"
# Where the tune starts in bard.wav: song time 0:40.45, so the downbeat at 0:41.35 is the first strum, 0.9 s in.
START = 0.50
# The scene's length, and how long the tune fades in and out.
LENGTH = 5.0
FADE_IN = 0.25
FADE_OUT = 0.6


def read(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, SR), path
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def main() -> None:
    music = read(SOURCE)
    start, n = int(START * SR), int(LENGTH * SR)
    mix = music[start : start + n].copy()
    assert len(mix) == n, f"{SOURCE.name} is too short"
    rise, fall = int(FADE_IN * SR), int(FADE_OUT * SR)
    mix[:rise] *= np.linspace(0, 1, rise) ** 1.5
    mix[-fall:] *= np.linspace(1, 0, fall) ** 1.5
    rms = np.sqrt(np.mean(mix**2))
    gain = min(10 ** (-19 / 20) / rms, 10 ** (-3 / 20) / np.abs(mix).max())
    mix = np.clip(mix * gain, -1, 1)
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    level = 20 * np.log10(np.sqrt(np.mean(mix**2)))
    peak = 20 * np.log10(np.abs(mix).max())
    print(f"{OUT.name}: {n / SR:.1f} s from {START} s of {SOURCE.name}, {level:.1f} dBFS, peak {peak:.1f} dBFS")


if __name__ == "__main__":
    main()
