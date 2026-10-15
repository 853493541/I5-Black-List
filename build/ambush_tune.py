"""Mix 演说家遇袭's tune into blacklist_detect/assets/ambush.wav.

    python build/ambush_tune.py

The 指挥家's music from 模仿者狂欢 (build/sounds/conductor.wav: the game's own recording, cut from its
start; the user chose it knowing NetEase owns it) with the 演说家遇袭 notice's sound laid in at the
moment the claw strikes (love_scenes.claw.STRIKE). build/sounds/orator_notice.wav is the game's own
sound, cut by build/orator_notice_sound.py from two videos that hold it. Without it the notice is
silent: a made-up one sounded wrong to the user.

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
AT = 3.0
LENGTH = 6.6


def read(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, SR), path
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def main() -> None:
    music = read(SOUNDS / "conductor.wav")
    real = SOUNDS / "orator_notice.wav"
    notice = read(real) if real.is_file() else np.zeros(1, dtype=np.float32)
    n = int(LENGTH * SR)
    mix = np.zeros(n, dtype=np.float32)
    mix[: min(n, len(music))] += music[:n]
    # The music fades under the notice for a moment, when it has one, and out at the end.
    duck = np.ones(n, dtype=np.float32)
    at = int(AT * SR)
    span = np.arange(n) / SR - AT
    if real.is_file():
        duck *= 1 - 0.45 * np.exp(-np.clip(span, 0, None) * 2.2) * (span >= -0.05)
    fade = int(0.6 * SR)
    duck[-fade:] *= np.linspace(1, 0, fade) ** 1.5
    mix *= duck
    # The notice goes in at its own level: raised 4 dB it jumped out of the music, and the peak it made held the
    # whole tune 1.3 dB under the others.
    end = min(n, at + len(notice))
    mix[at:end] += notice[: end - at]
    rms = np.sqrt(np.mean(mix**2))
    gain = min(10 ** (-19 / 20) / rms, 10 ** (-3 / 20) / np.abs(mix).max())
    mix = np.clip(mix * gain, -1, 1)
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    print(f"{OUT.name}: {n / SR:.1f} s, notice {'recorded, at ' + str(AT) + ' s' if real.is_file() else 'silent (not recorded yet)'}")


if __name__ == "__main__":
    main()
