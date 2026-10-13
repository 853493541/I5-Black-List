"""Play the 心动音乐 tunes into blacklist_detect/assets, so no recording is used.

    python build/wedding_tunes.py

Wagner's Bridal Chorus (Lohengrin, 1850), "Here comes the bride, all dressed in white", as
church organ, music box and 8-bit; Pachelbel's Canon (about 1690) on harp; and church bells ringing
rounds. All public domain; the performance is this script's own, so a stream can carry it. Each is
mono 16-bit 44.1 kHz like hit.wav, about five seconds, as loud as the chime (about -19 dBFS,
peaks under -3 dBFS).
"""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

SR = 44100
ASSETS = Path(__file__).resolve().parent.parent / "blacklist_detect" / "assets"
RNG = np.random.default_rng(7)

C2, D2, F2, G2, A2, B2 = 36, 38, 41, 43, 45, 47
C3, D3, E3, G3, A3, B3 = 48, 50, 52, 55, 57, 59
C4, D4, E4, F4, G4, A4, B4 = 60, 62, 64, 65, 67, 69, 71
C5, D5, E5, F5, G5, A5, B5, C6, D6 = 72, 74, 76, 77, 79, 81, 83, 84, 86

# (beat, beats, note): "Here comes the bride, all dressed in white", in C.
BRIDE = ((0, 1, G4), (1, 0.75, C5), (1.75, 0.25, C5), (2, 2, C5), (4, 1, G4), (5, 0.75, D5), (5.75, 0.25, B4), (6, 2.2, C5))
# (beat, beats, bass, chord) under it: C, then G, home to C.
CHORDS = ((0, 4, (C2, C3), (E3, G3, C4)), (4, 2, (G2, G3), (B3, D4, G3)), (6, 2.2, (C2, C3), (E3, G3, C4)))


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def times(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * SR)) / SR


def organ(midi: float, dur: float, vel: float = 1.0) -> np.ndarray:
    """Principal pipes with a few harmonics, two slightly detuned ranks and a slow tremulant."""
    t = times(dur + 0.18)
    f = hz(midi)
    out = np.zeros_like(t)
    for n, amp in ((0.5, 0.35), (1, 1.0), (2, 0.55), (3, 0.3), (4, 0.22), (6, 0.1), (8, 0.07)):
        for cents in (-2.0, 2.5):
            g = f * n * 2 ** (cents / 1200)
            if g < SR / 2.2:
                out += amp * np.sin(2 * np.pi * g * t + RNG.uniform(0, 6.28))
    env = np.minimum(1, t / 0.035)
    env = np.where(t > dur, np.exp(-(t - dur) / 0.07), env)
    env *= 1 + 0.035 * np.sin(2 * np.pi * 5.6 * t)
    return out * env * vel * 0.12


def music_box(midi: float, dur: float, vel: float = 1.0) -> np.ndarray:
    """A tine: bright attack, slightly stretched partials, each dying faster than the last."""
    t = times(max(dur, 1.4))
    f = hz(midi)
    out = np.zeros_like(t)
    for ratio, amp, tau in ((1, 1.0, 1.1), (2.0, 0.32, 0.5), (3.01, 0.16, 0.3), (4.17, 0.12, 0.2), (5.43, 0.07, 0.14), (6.8, 0.05, 0.09)):
        if f * ratio < SR / 2.2:
            out += amp * np.sin(2 * np.pi * f * ratio * t) * np.exp(-t / tau)
    click = RNG.normal(0, 1, len(t)) * np.exp(-t / 0.002) * 0.15
    return (out + click) * np.minimum(1, t / 0.002) * vel * 0.3


def square(midi: float, dur: float, vel: float = 1.0) -> np.ndarray:
    """An 8-bit pulse lead, a little vibrato once the note has sounded a moment."""
    t = times(dur + 0.03)
    vib = 1 + 0.006 * np.sin(2 * np.pi * 6 * t) * np.clip((t - 0.15) / 0.1, 0, 1)
    phase = np.cumsum(hz(midi) * vib / SR)
    out = np.where(phase % 1 < 0.25, 1.0, -1.0)
    env = np.minimum(1, t / 0.004) * (0.75 + 0.25 * np.exp(-t / 0.08))
    env = np.where(t > dur, np.exp(-(t - dur) / 0.01), env)
    return out * env * vel * 0.16


def triangle(midi: float, dur: float, vel: float = 1.0) -> np.ndarray:
    t = times(dur + 0.02)
    out = 4 * np.abs(hz(midi) * t % 1 - 0.5) - 1
    return out * np.where(t > dur, np.exp(-(t - dur) / 0.008), 1.0) * vel * 0.3


def hat(dur: float, vel: float = 1.0) -> np.ndarray:
    t = times(dur)
    return (RNG.integers(0, 2, len(t)) * 2.0 - 1.0) * np.exp(-t / 0.012) * vel * 0.08


def harp(midi: float, dur: float, vel: float = 1.0) -> np.ndarray:
    """A plucked harp string: partials plucked near one end, the high ones fading first."""
    t = times(max(dur, 1.6))
    f = hz(midi)
    out = np.zeros_like(t)
    for n in range(1, 11):
        if f * n > SR / 2.2:
            break
        amp = abs(math.sin(math.pi * n * 0.18)) / n**1.1
        out += amp * np.sin(2 * np.pi * f * n * t * (1 + 0.0004 * n * n)) * np.exp(-t / (1.9 / n**0.75))
    return out * np.minimum(1, t / 0.004) * vel * 0.32


def strings(midi: float, dur: float, vel: float = 1.0) -> np.ndarray:
    """A soft string section: detuned sawtooth voices, gently filtered, swelling in."""
    t = times(dur + 0.4)
    f = hz(midi)
    out = np.zeros_like(t)
    for cents in (-7, -2, 3, 8):
        g = f * 2 ** (cents / 1200)
        for n in range(1, 9):
            if g * n > SR / 2.5:
                break
            out += np.sin(2 * np.pi * g * n * t + RNG.uniform(0, 6.28)) / n**1.4
    env = np.minimum(1, t / 0.18)
    env = np.where(t > dur, np.exp(-(t - dur) / 0.15), env)
    vibrato = 1 + 0.02 * np.sin(2 * np.pi * 5 * t) * np.minimum(1, t / 0.6)
    return out * env * vibrato * vel * 0.05


def bell(midi: float, vel: float = 1.0) -> np.ndarray:
    """A church bell: hum, prime, minor third, fifth and nominal, each ringing for its own time."""
    t = times(3.2)
    f = hz(midi)
    out = np.zeros_like(t)
    for ratio, amp, tau in (
        (0.5, 0.55, 2.6), (1.0, 0.8, 1.8), (1.19, 0.6, 1.4), (1.5, 0.35, 1.1), (2.0, 0.75, 1.0),
        (2.51, 0.3, 0.6), (2.66, 0.22, 0.55), (3.01, 0.25, 0.45), (4.17, 0.16, 0.3), (5.43, 0.1, 0.2),
    ):
        if f * ratio < SR / 2.2:
            out += amp * np.sin(2 * np.pi * f * ratio * t + RNG.uniform(0, 6.28)) * np.exp(-t / tau)
    strike = RNG.normal(0, 1, len(t)) * np.exp(-t / 0.004) * 0.3
    return (out + strike) * np.minimum(1, t / 0.0015) * vel * 0.16


def render(events, seconds: float) -> np.ndarray:  # noqa: ANN001
    """events: (start in seconds, instrument, its arguments...)."""
    out = np.zeros(int((seconds + 4) * SR))
    for start, instrument, *args in events:
        note = instrument(*args)
        i = int(start * SR)
        out[i : i + len(note)] += note[: len(out) - i]
    return out


def reverb(dry: np.ndarray, size: float, wet: float, damp: float) -> np.ndarray:
    """A room: a decaying, darkened noise impulse, applied by FFT."""
    n = int(size * SR)
    t = np.arange(n) / SR
    ir = RNG.normal(0, 1, n) * np.exp(-t / (size / 5.5))
    ir[: int(0.012 * SR)] *= 0.3
    freqs = np.fft.rfftfreq(n, 1 / SR)
    ir = np.fft.irfft(np.fft.rfft(ir) / (1 + (freqs / damp) ** 2), n)
    ir /= np.sqrt((ir**2).sum())
    size_fft = 1 << int(math.ceil(math.log2(len(dry) + n)))
    wet_sig = np.fft.irfft(np.fft.rfft(dry, size_fft) * np.fft.rfft(ir, size_fft), size_fft)[: len(dry)]
    return dry * (1 - wet) + wet_sig * wet * 3.0


def finish(sig: np.ndarray, seconds: float, fade: float) -> np.ndarray:
    """Cut to length, fade out, and level to the chime's loudness."""
    sig = sig[: int(seconds * SR)].copy()
    n = int(fade * SR)
    sig[-n:] *= np.linspace(1, 0, n) ** 2
    rms = math.sqrt((sig**2).mean())
    return sig * min(10 ** (-19 / 20) / rms, 10 ** (-3 / 20) / np.abs(sig).max())


def organ_take() -> np.ndarray:
    beat = 60 / 104
    ev = []
    for at, length, note in BRIDE:
        # The tune doubled an octave up, a few dB over the chords so the ear keeps it.
        ev.append((at * beat, organ, note, length * beat * 0.97, 1.0))
        ev.append((at * beat, organ, note + 12, length * beat * 0.97, 0.5))
    for at, length, bass, chord in CHORDS:
        ev += [(at * beat, organ, note, length * beat, 0.45) for note in bass]
        ev += [(at * beat, organ, note, length * beat, 0.22) for note in chord]
    return finish(reverb(render(ev, 6), 2.6, 0.38, 4500), 5.0, 0.7)


def music_box_take() -> np.ndarray:
    beat = 60 / 100
    ev = [(at * beat, music_box, note + 12, length * beat, 1.0) for at, length, note in BRIDE]
    for at, note in ((0, C4), (1, G4), (2, E4), (3, G4), (4, G3), (5, D4), (6, C4), (6.5, E4), (7, G4)):
        ev.append((at * beat, music_box, note + 12, 1.0, 0.45))
    ev.append((8.0 * beat, music_box, C6 + 12, 1.0, 0.25))
    return finish(reverb(render(ev, 6), 2.0, 0.3, 7000), 5.0, 0.6)


def chip_take() -> np.ndarray:
    """As a game would play it, a little faster, ending on a level-clear run."""
    beat = 60 / 132
    ev = [(at * beat, square, note + 12, length * beat * 0.9, 1.0) for at, length, note in BRIDE[:-1]]
    ev.append((6 * beat, square, C6, beat * 0.9, 1.0))
    for k, note in enumerate((C5, E5, G5, C6)):
        ev.append(((7 + k * 0.25) * beat, square, note + 12, 0.25 * beat * 0.9, 0.8))
    ev.append((8 * beat, square, C6 + 12, 1.4 * beat, 0.9))
    roots = [C2] * 4 + [G2] * 2 + [C2] * 3
    for i in range(18):
        root = roots[min(i // 2, len(roots) - 1)]
        ev.append((i * 0.5 * beat, triangle, root + (12 if i % 2 else 0), 0.45 * beat, 0.9))
        ev.append(((i * 0.5 + 0.25) * beat, hat, 0.04, 0.7 if i % 2 else 0.4))
    return finish(reverb(render(ev, 6), 0.8, 0.08, 9000), 4.6, 0.35)


def canon_take() -> np.ndarray:
    """Pachelbel's Canon: its opening line over the eight chords, then home to D."""
    half = 0.52
    chords = (
        (D3, (D4, F4 + 1, A4)), (A2, (C4 + 1, E4, A4)), (B2, (D4, F4 + 1, B4)), (F2 + 1, (C4 + 1, F4 + 1, A4)),
        (G2, (D4, G4, B4)), (D3, (D4, F4 + 1, A4)), (G2, (D4, G4, B4)), (A2, (C4 + 1, E4, A4)),
    )
    tune = (F5 + 1, E5, D5, C5 + 1, B4, A4, B4, C5 + 1)
    ev = []
    for i, ((bass, chord), note) in enumerate(zip(chords, tune, strict=True)):
        at = i * half
        ev.append((at, harp, bass, half, 0.65))
        for k, c in enumerate((chord[0], chord[1], chord[2], chord[1])):
            ev.append((at + k * half / 4, harp, c, half / 4, 0.22))
        # The tune sits a few dB over the harp, or the ear loses it.
        ev.append((at, strings, note, half * 0.98, 2.3))
        ev.append((at, music_box, note + 12, half, 0.95))
    end = 8 * half
    for note, vel in ((D3, 0.9), (A3, 0.5), (D4, 0.5), (F4 + 1, 0.5), (A4, 0.5), (D5, 0.6)):
        ev.append((end + 0.03 * (note % 7), harp, note, 1.0, vel))
    ev.append((end, strings, D5, 0.9, 2.0))
    ev.append((end, music_box, D6, 1.0, 0.8))
    return finish(reverb(render(ev, 6), 2.2, 0.3, 6500), 5.2, 0.8)


def bells_take() -> np.ndarray:
    """Church bells ringing rounds, high to low, as they ring out after a wedding."""
    peal = (C6, B5, A5, G5, F5, E5, D5, C5)
    ev = [(k * 0.24 + RNG.uniform(-0.012, 0.012), bell, peal[k % len(peal)], 0.85 + 0.15 * RNG.random()) for k in range(17)]
    return finish(reverb(render(ev, 6), 3.0, 0.4, 5000), 5.0, 0.9)


def write(name: str, sig: np.ndarray) -> None:
    data = (np.clip(sig, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(ASSETS / name), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SR)
        out.writeframes(data.tobytes())
    print(f"{name}: {len(sig) / SR:.2f} s")


def main() -> None:
    write("wedding-organ.wav", organ_take())
    write("wedding-music-box.wav", music_box_take())
    write("wedding-8bit.wav", chip_take())
    write("wedding-canon.wav", canon_take())
    write("wedding-bells.wav", bells_take())


if __name__ == "__main__":
    main()
