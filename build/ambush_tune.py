"""Mix 遇袭's tune into blacklist_detect/assets/ambush.wav.

    python build/ambush_tune.py

The 指挥家's music from 模仿者狂欢 (build/sounds/conductor.wav: the game's own recording, cut from its
start; the user chose it knowing NetEase owns it) with the 演说家遇袭 notice's sound laid in at the
moment the claw strikes (love_scenes.claw.STRIKE). The notice's real sound has not been recorded yet:
until it is, a stand-in made here plays, a paper whoosh and a bright two-note chime. Put a recording of
the real one at build/sounds/orator_notice.wav and run this again to use it instead.

Mono 16-bit 44.1 kHz, as long as the scene, at about -19 dBFS with peaks under -3 dBFS like the others.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100
ROOT = Path(__file__).resolve().parent.parent
SOUNDS = ROOT / "build" / "sounds"
OUT = ROOT / "blacklist_detect" / "assets" / "ambush.wav"
# When the notice comes, from the start of the scene (love_scenes.claw.STRIKE), and the scene's length.
AT = 3.6
LENGTH = 6.6


def read(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, SR), path
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def stand_in() -> np.ndarray:
    """A newspaper tossed into view and a news chime: a short whoosh of filtered noise sweeping down,
    then two bright bell notes (E6, B6) ringing out."""
    rng = np.random.default_rng(3)
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n).astype(np.float32)
    # The whoosh: noise through a one-pole low-pass whose cutoff falls, under a quick swell.
    out = np.zeros(n, dtype=np.float32)
    y = 0.0
    for i in range(int(0.3 * SR)):
        cutoff = 5000 * (1 - i / (0.3 * SR)) + 600
        k = 1 - np.exp(-2 * np.pi * cutoff / SR)
        y += k * (noise[i] - y)
        out[i] = y
    swell = np.clip(t / 0.06, 0, 1) * np.exp(-np.clip(t - 0.06, 0, None) * 14)
    whoosh = out * swell * 0.5
    chime = np.zeros(n, dtype=np.float32)
    for start, freq in ((0.12, 1318.5), (0.2, 1975.5)):
        s = np.clip(t - start, 0, None)
        on = t >= start
        ring = np.sin(2 * np.pi * freq * s) + 0.35 * np.sin(2 * np.pi * freq * 2.76 * s) * np.exp(-s * 6)
        chime += on * ring * np.exp(-s * 3.2) * 0.32
    return (whoosh + chime).astype(np.float32)


def main() -> None:
    music = read(SOUNDS / "conductor.wav")
    real = SOUNDS / "orator_notice.wav"
    notice = read(real) if real.is_file() else stand_in()
    n = int(LENGTH * SR)
    mix = np.zeros(n, dtype=np.float32)
    mix[: min(n, len(music))] += music[:n]
    # The music fades under the notice for a moment and out at the end.
    duck = np.ones(n, dtype=np.float32)
    at = int(AT * SR)
    span = np.arange(n) / SR - AT
    duck *= 1 - 0.45 * np.exp(-np.clip(span, 0, None) * 2.2) * (span >= -0.05)
    fade = int(0.6 * SR)
    duck[-fade:] *= np.linspace(1, 0, fade) ** 1.5
    mix *= duck
    end = min(n, at + len(notice))
    mix[at:end] += notice[: end - at] * 1.6
    rms = np.sqrt(np.mean(mix**2))
    gain = min(10 ** (-19 / 20) / rms, 10 ** (-3 / 20) / np.abs(mix).max())
    mix = np.clip(mix * gain, -1, 1)
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    print(f"{OUT.name}: {n / SR:.1f} s, notice {'recorded' if real.is_file() else 'stand-in'} at {AT} s")


if __name__ == "__main__":
    main()
