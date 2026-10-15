"""Cut the 演说家遇袭 notice's own sound out of two recordings of it, for the 演说家遇袭 scene (build/ambush_tune.py).

    python build/orator_notice_sound.py <clean.wav> <noisy.wav>

clean.wav is the first 3 s of Bilibili video BV12upMeEE3R, which opens on the notice, with little under
it; noisy.wav is 0:36-0:50 of BV1pPx6zAEez, where the game's music plays under it (both mono 16-bit
44.1 kHz, made with ffmpeg). The user chose the game's own sound, knowing NetEase owns it. The two hold
the same sound sample for sample, the clean one's 0 s at the noisy one's 4.6544 s, and it starts with a
ring just after the attack's hit. The clean one is used, except in the bits of sound where the noisy one
is much quieter (something in the clean one only), and a mouse click in it is smoothed over. Writes
build/sounds/orator_notice.wav.
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

SR = 44100
OUT = Path(__file__).resolve().parent / "sounds" / "orator_notice.wav"
# Where the notice's sound is in the clean recording (from just before its ring to where the video cuts
# away), where that is in the noisy one, and how much louder the sound is there.
START, END = 0.285, 1.235
NOISY_AT = 4.6544
NOISY_GAIN = 0.846
N, HOP = 1024, 256
WIN = np.hanning(N)


def read(path: str) -> np.ndarray:
    with wave.open(path) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, SR), path
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def stft(x: np.ndarray) -> np.ndarray:
    return np.array([np.fft.rfft(x[i : i + N] * WIN) for i in range(0, len(x) - N + 1, HOP)])


def istft(s: np.ndarray, length: int) -> np.ndarray:
    out, norm = np.zeros(length), np.zeros(length)
    for k, i in enumerate(range(0, length - N + 1, HOP)):
        out[i : i + N] += np.fft.irfft(s[k], N) * WIN
        norm[i : i + N] += WIN**2
    return out / np.maximum(norm, 1e-6)


def unclick(s: np.ndarray, times: np.ndarray) -> np.ndarray:
    """Frames whose top end (over 5 kHz) jumps over their neighbours' get it no louder than either side's,
    their own phase kept. Only past the ring's start: its first strike is a jump too, and is the sound."""
    mag = np.abs(s)
    high = np.fft.rfftfreq(N, 1 / SR) > 5000
    level = 10 * np.log10((mag[:, high] ** 2).sum(axis=1) + 1e-12)
    around = np.array([np.median(np.r_[level[max(0, k - 8) : max(0, k - 2)], level[k + 3 : k + 9]]) for k in range(len(level))])
    bad = np.flatnonzero((level - around > 3) & (times > 0.5))
    for k in bad:
        lo, hi = max(0, k - 4), min(len(s) - 1, k + 4)
        while lo in bad and lo > 0:
            lo -= 1
        while hi in bad and hi < len(s) - 1:
            hi += 1
        w = (k - lo) / (hi - lo)
        fill = np.exp((1 - w) * np.log(mag[lo] + 1e-9) + w * np.log(mag[hi] + 1e-9))
        s[k, high] = s[k, high] / (mag[k, high] + 1e-9) * np.minimum(mag[k, high], fill[high])
    return s


def main() -> None:
    clean, noisy = read(sys.argv[1]), read(sys.argv[2])
    pad = int(0.05 * SR)
    i0, i1 = int(START * SR) - pad, int(END * SR)
    at = int(NOISY_AT * SR)
    sc, sn = stft(clean[i0:i1]), stft(noisy[at + i0 : at + i1] * NOISY_GAIN)
    s = np.where(np.abs(sn) < 0.5 * np.abs(sc), sn, sc)
    s = unclick(s, (np.arange(len(s)) * HOP + N / 2 - pad) / SR + START)
    out = istft(s, i1 - i0)[pad:].astype(np.float32)
    # The bass under it out, short fades, and its clicks brought down to -3 dBFS around a -17 dBFS body.
    spec = np.fft.rfft(out)
    f = np.fft.rfftfreq(len(out), 1 / SR)
    out = np.fft.irfft(spec / np.sqrt(1 + (120 / np.maximum(f, 1)) ** 4), len(out)).astype(np.float32)
    fade_in, fade_out = int(0.006 * SR), int(0.22 * SR)
    out[:fade_in] *= np.sin(np.linspace(0, np.pi / 2, fade_in)) ** 2
    out[-fade_out:] *= np.cos(np.linspace(0, np.pi / 2, fade_out)) ** 2
    body = slice(0, int(0.4 * SR))
    out *= 10 ** (-17 / 20) / np.sqrt(np.mean(out[body] ** 2))
    h = int(0.003 * SR)
    peak = np.array([np.abs(out[max(0, i - h) : i + h]).max() for i in range(len(out))])
    gain = np.minimum(1, 10 ** (-3 / 20) / np.maximum(peak, 1e-6))
    kernel = np.hanning(int(0.006 * SR))
    out *= np.minimum(gain, np.convolve(gain, kernel / kernel.sum(), "same"))
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(out, -1, 1) * 32767).astype(np.int16).tobytes())
    print(f"{OUT.name}: {len(out) / SR:.2f} s, peak {20 * np.log10(np.abs(out).max()):.1f} dBFS")


if __name__ == "__main__":
    main()
