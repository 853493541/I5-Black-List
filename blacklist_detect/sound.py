"""One short chime. Playback is skipped when the user mutes the app."""

from __future__ import annotations

import math
import struct
import subprocess
import sys
import wave
from pathlib import Path


def chime_path(directory: Path) -> Path:
    path = directory / "chime.wav"
    if not path.exists():
        write_chime(path)
    return path


def write_chime(path: Path) -> None:
    """Two soft tones, under half a second. No external asset."""
    sample_rate = 22050
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = _tone(880, 0.09, sample_rate) + [0] * int(sample_rate * 0.03)
    samples += _tone(1175, 0.14, sample_rate)
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))


def _tone(frequency: float, seconds: float, sample_rate: int) -> list[int]:
    count = int(sample_rate * seconds)
    samples = []
    for index in range(count):
        envelope = min(1.0, index / (sample_rate * 0.01))
        envelope *= max(0.0, 1.0 - (index / count))
        value = math.sin(2 * math.pi * frequency * index / sample_rate)
        samples.append(int(0.35 * envelope * 32767 * value))
    return samples


def play_chime(path: Path) -> None:
    if sys.platform == "win32":
        import winsound

        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        return
    for program in ("paplay", "aplay"):
        try:
            subprocess.Popen(
                [program, str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except FileNotFoundError:
            continue
