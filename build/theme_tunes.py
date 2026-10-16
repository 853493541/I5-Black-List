"""Play each 嘉宾特效 theme's own sound into blacklist_detect/assets, so no recording is used.

    python build/theme_tunes.py

Each sound is made for its scene, its accents on the scene's moments (love_scenes): 冰蓝极光's glass
rings as its heart forms; 星河许愿 plays Twinkle, Twinkle, Little Star on a celesta and a shooting star
chimes as its two stars meet; 赛博朋克（一） zaps at each of its five strikes over a synthwave pulse;
赛博朋克（二） rains and thunders at each of its four strikes over city-pop chords; 毛茸茸保护协会 plucks a
bouncy tune, pops its stars, boings its sprouts and pats its paw prints. The tunes are this script's
own or public domain, so a stream can carry them. 经典 greets in silence; 玫瑰花边, 金色传说 and
数学公式 keep the wedding tunes made for them (build/wedding_tunes.py: organ, bells, canon). Two are not
this rule's, both the user's choice made knowing who owns the music: 演说家遇袭's is the game's 指挥家 music
(build/ambush_tune.py) and 竖琴清风's 温迪's 诗人的工作 by HOYO-MiX (build/lyre_tune.py, 2026-10-16).

Each is mono 16-bit 44.1 kHz, as long as its scene, at about -19 dBFS with peaks under -3 dBFS.
"""

from __future__ import annotations

import math

import numpy as np
import wedding_tunes
from wedding_tunes import SR, finish, harp, hz, music_box, render, reverb, times, write

RNG = np.random.default_rng(11)


# Instruments ----------------------------------------------------------------------------------


def celesta(midi: float, vel: float = 1.0) -> np.ndarray:
    """A celesta: a steel bar struck in a wooden box, a pure tone with a faint octave and a quick ring
    of high partials."""
    t = times(2.0)
    f = hz(midi)
    out = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.9)
    for ratio, amp, tau in ((2.0, 0.22, 0.5), (4.07, 0.1, 0.12), (6.9, 0.05, 0.05)):
        if f * ratio < SR / 2.2:
            out += amp * np.sin(2 * np.pi * f * ratio * t) * np.exp(-t / tau)
    return out * np.minimum(1, t / 0.0025) * vel * 0.2


def glass(midi: float, dur: float, vel: float = 1.0) -> np.ndarray:
    """A glass harmonica: a pure tone swelling slowly in, a soft shimmer on it."""
    t = times(dur + 0.8)
    f = hz(midi)
    out = np.sin(2 * np.pi * f * t) + 0.16 * np.sin(2 * np.pi * 2 * f * t) + 0.05 * np.sin(2 * np.pi * 3 * f * t)
    rise = np.clip(t / 0.45, 0, 1)
    env = rise * rise * (3 - 2 * rise)
    env = np.where(t > dur, env * np.exp(-(t - dur) / 0.35), env)
    return out * env * (1 + 0.06 * np.sin(2 * np.pi * 4.5 * t)) * vel * 0.1


def chime(midi: float, vel: float = 1.0) -> np.ndarray:
    """A wind chime's tube: the partials of a free bar, ringing long."""
    t = times(3.0)
    f = hz(midi)
    out = np.zeros_like(t)
    for ratio, amp, tau in ((1.0, 1.0, 1.7), (2.76, 0.45, 0.8), (5.4, 0.22, 0.35), (8.93, 0.1, 0.15)):
        if f * ratio < SR / 2.2:
            out += amp * np.sin(2 * np.pi * f * ratio * t + RNG.uniform(0, 6.28)) * np.exp(-t / tau)
    return out * np.minimum(1, t / 0.0015) * vel * 0.13


def pizz(midi: float, vel: float = 1.0) -> np.ndarray:
    """A plucked string, short and round, as a pizzicato or a ukulele's nylon."""
    t = times(0.9)
    f = hz(midi)
    out = np.zeros_like(t)
    for n in range(1, 8):
        if f * n > SR / 2.2:
            break
        amp = abs(math.sin(math.pi * n * 0.3)) / n**1.2
        out += amp * np.sin(2 * np.pi * f * n * t) * np.exp(-t / (0.32 / n**0.7))
    return out * np.minimum(1, t / 0.003) * vel * 0.3


def epiano(midi: float, dur: float, vel: float = 1.0) -> np.ndarray:
    """An electric piano: a soft tine, a bell-like ping at its strike, a slow tremolo."""
    t = times(dur + 0.6)
    f = hz(midi)
    out = np.sin(2 * np.pi * f * t) * np.exp(-t / 1.6) + 0.25 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / 0.6)
    if f * 7 < SR / 2.2:
        out += 0.12 * np.sin(2 * np.pi * 7 * f * t) * np.exp(-t / 0.05)
    env = np.minimum(1, t / 0.004) * np.where(t > dur, np.exp(-(t - dur) / 0.2), 1.0)
    return out * env * (1 + 0.12 * np.sin(2 * np.pi * 4.2 * t)) * vel * 0.16


def saw_bass(midi: float, dur: float, vel: float = 1.0) -> np.ndarray:
    """A synth bass: a sawtooth whose top falls away after its attack, as a filter closing."""
    t = times(dur + 0.05)
    f = hz(midi)
    out = np.zeros_like(t)
    for n in range(1, 24):
        if f * n > SR / 2.5:
            break
        out += np.sin(2 * np.pi * f * n * t) / n * np.exp(-t * n * 6.0)
    env = np.minimum(1, t / 0.004) * np.where(t > dur, np.exp(-(t - dur) / 0.015), 1.0)
    return np.tanh(out * 1.6) * env * vel * 0.22


def synth_pad(midi: float, dur: float, vel: float = 1.0) -> np.ndarray:
    """A wide synth pad: detuned saws, their top cut, swelling in."""
    t = times(dur + 0.5)
    f = hz(midi)
    out = np.zeros_like(t)
    for cents in (-9, 0, 9):
        g = f * 2 ** (cents / 1200)
        for n in range(1, 7):
            out += np.sin(2 * np.pi * g * n * t + RNG.uniform(0, 6.28)) / n**1.5
    env = np.minimum(1, t / 0.3) * np.where(t > dur, np.exp(-(t - dur) / 0.25), 1.0)
    return out * env * vel * 0.03


def kick(vel: float = 1.0) -> np.ndarray:
    t = times(0.35)
    phase = np.cumsum(45 + 90 * np.exp(-t / 0.03)) / SR
    return np.sin(2 * np.pi * phase) * np.exp(-t / 0.16) * vel * 0.5


def band(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Noise or anything, kept between lo and hi hertz, rolled off softly either side."""
    spectrum = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR) + 1e-3
    spectrum *= 1 / (1 + (lo / f) ** 4) / (1 + (f / hi) ** 4)
    return np.fft.irfft(spectrum, len(x))


def sweep(x: np.ndarray, start: float, end: float) -> np.ndarray:
    """A low-pass that opens or closes from start to end hertz along x."""
    cutoff = np.geomspace(start, end, len(x))
    a = 1 - np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    state = 0.0
    for i in range(len(x)):
        state += a[i] * (x[i] - state)
        y[i] = state
    return y


def whoosh(dur: float, start: float, end: float, vel: float = 1.0) -> np.ndarray:
    """Air rushing past: noise through a sweeping filter, rising and falling."""
    t = times(dur)
    k = t / dur
    env = np.sin(np.pi * k) ** 1.5
    noise = RNG.normal(0, 1, len(t))
    return band(sweep(noise, start, end), 300, 14000) * env * vel * 0.5


def sparkle(vel: float = 1.0) -> np.ndarray:
    """A glint of sound: a very high bell, gone at once."""
    t = times(0.5)
    f = RNG.uniform(3200, 5200)
    out = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.12) + 0.4 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t / 0.05)
    return out * np.minimum(1, t / 0.001) * vel * 0.08


def zap(vel: float = 1.0) -> np.ndarray:
    """Lightning striking a panel: a crackle, a falling electric whine, a thump under it."""
    t = times(0.9)
    crackle = (RNG.random(len(t)) < 0.02 * np.exp(-t / 0.15)) * RNG.normal(0, 1, len(t)) * 2.5
    burst = band(RNG.normal(0, 1, len(t)), 1500, 12000) * np.exp(-t / 0.06)
    phase = np.cumsum(180 + 2600 * np.exp(-t / 0.05)) / SR
    whine = np.tanh(2.5 * np.sin(2 * np.pi * phase)) * np.exp(-t / 0.18) * 0.35
    thump = np.sin(2 * np.pi * np.cumsum(40 + 80 * np.exp(-t / 0.04)) / SR) * np.exp(-t / 0.22) * 0.8
    return (crackle * 0.4 + burst * 0.6 + whine + thump) * np.minimum(1, t / 0.0008) * vel * 0.35


def thunder(vel: float = 1.0, crack: float = 1.0) -> np.ndarray:
    """A crack and its rumble, rolling away."""
    t = times(3.0)
    snap = band(RNG.normal(0, 1, len(t)), 800, 9000) * np.exp(-t / 0.04) * crack
    brown = np.cumsum(RNG.normal(0, 1, len(t)))
    brown -= np.convolve(brown, np.ones(2001) / 2001, mode="same")
    rumble = band(brown, 25, 240)
    rumble /= np.abs(rumble).max() + 1e-9
    roll = (1 - np.exp(-t / 0.08)) * np.exp(-t / 0.9) * (1 + 0.35 * np.sin(2 * np.pi * 2.3 * t + RNG.uniform(0, 6.28)))
    return (snap * 0.5 + rumble * roll) * vel * 0.55


def rain(dur: float, vel: float = 1.0) -> np.ndarray:
    """Rain on a city at night: a hiss and drops."""
    t = times(dur)
    hiss = band(RNG.normal(0, 1, len(t)), 900, 7000) * (0.8 + 0.2 * np.sin(2 * np.pi * 0.7 * t))
    drops = (RNG.random(len(t)) < 0.0018) * RNG.uniform(0.3, 1.0, len(t))
    ping = np.exp(-np.arange(int(0.012 * SR)) / SR / 0.0025) * np.sin(2 * np.pi * 2600 * np.arange(int(0.012 * SR)) / SR)
    drops = np.convolve(drops, ping, mode="same")
    return (hiss * 0.12 + drops * 0.12) * vel


def hum(dur: float, on: list[tuple[float, float]], vel: float = 1.0) -> np.ndarray:
    """A neon tube's buzz, on only in the spans in on (start, end, in seconds), a little rough."""
    t = times(dur)
    out = np.zeros_like(t)
    for n, amp in ((1, 1.0), (2, 0.6), (3, 0.45), (5, 0.25), (7, 0.15)):
        out += amp * np.sin(2 * np.pi * 120 * n * t + RNG.uniform(0, 6.28))
    gate = np.zeros_like(t)
    for start, end in on:
        gate += (t >= start) & (t < end)
    gate = np.convolve(np.clip(gate, 0, 1), np.ones(64) / 64, mode="same")
    return np.tanh(out * 0.8) * gate * vel * 0.03


def boop(midi: float, vel: float = 1.0) -> np.ndarray:
    """A soft, round boop, dropping a little in pitch."""
    t = times(0.35)
    f = hz(midi) * (1 + 0.12 * np.exp(-t / 0.03))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.09) * np.minimum(1, t / 0.004) * vel * 0.18


def pop(midi: float, vel: float = 1.0) -> np.ndarray:
    """A bubble popping: a quick rising blip."""
    t = times(0.12)
    f = hz(midi) * (0.6 + 0.6 * (1 - np.exp(-t / 0.012)))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.03) * np.minimum(1, t / 0.002) * vel * 0.14


def boing(midi: float, vel: float = 1.0) -> np.ndarray:
    """A spring: a tone wobbling fast, the wobble dying away."""
    t = times(0.6)
    f = hz(midi) * (1 + 0.18 * np.sin(2 * np.pi * 14 * t) * np.exp(-t / 0.15)) * (1 + 0.15 * (1 - np.exp(-t / 0.05)))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.2) * np.minimum(1, t / 0.004) * vel * 0.15


def pat(midi: float, vel: float = 1.0) -> np.ndarray:
    """A little paw's pat: a soft thump with a whisper of paper."""
    t = times(0.15)
    thump = np.sin(2 * np.pi * hz(midi) * t) * np.exp(-t / 0.035)
    brush = band(RNG.normal(0, 1, len(t)), 1500, 6000) * np.exp(-t / 0.012) * 0.25
    return (thump + brush) * np.minimum(1, t / 0.002) * vel * 0.2


def heartbeat(vel: float = 1.0) -> np.ndarray:
    t = times(0.4)
    return np.sin(2 * np.pi * np.cumsum(70 - 20 * t) / SR) * np.exp(-t / 0.09) * np.minimum(1, t / 0.006) * vel * 0.35


# The themes -----------------------------------------------------------------------------------

D3, A3 = 50, 57


def ice_take() -> np.ndarray:
    """冰蓝极光, 5.0 s: a glass-harmonica chord in C# minor; a celesta runs up as the frost grows
    (0.15-1.3 s), the glass rings as the heart forms (1.55 s), a run as the prism sweeps (1.75 s), two
    soft heartbeats (2.25, 2.5 s), chimes as it twinkles (3.4 s), and it melts away (4.05 s)."""
    ev = []
    for note, vel in ((49, 0.7), (56, 0.6), (59, 0.55), (64, 0.5)):
        ev.append((0.0, glass, note, 4.0, vel))
    for k, note in enumerate((73, 76, 80, 83, 85, 88, 92)):
        ev.append((0.15 + k * 0.16, celesta, note, 0.55))
    for note in (76, 80, 83):
        ev.append((0.8, glass, note, 1.6, 0.45))
    ev.append((1.55, chime, 97, 0.9))
    ev.append((1.55, celesta, 88, 0.7))
    for k, note in enumerate((80, 83, 85, 88, 92, 95, 97, 100)):
        ev.append((1.75 + k * 0.07, celesta, note, 0.32))
    ev.append((2.25, heartbeat, 0.9))
    ev.append((2.25, celesta, 85, 0.35))
    ev.append((2.5, heartbeat, 0.7))
    ev.append((2.5, celesta, 80, 0.3))
    for k, note in enumerate((85, 88, 92, 95, 97)):
        ev.append((3.1 + k * 0.08, celesta, note, 0.22))
    for k, note in enumerate((97, 92, 100, 95, 97, 104)):
        ev.append((3.35 + k * 0.09 + RNG.uniform(0, 0.03), chime, note, 0.5))
    for k, note in enumerate((88, 85, 83, 80, 76)):
        ev.append((4.05 + k * 0.14, celesta, note, 0.32 - 0.05 * k))
    breath = band(RNG.normal(0, 1, int(5.5 * SR)), 2500, 9000) * 0.006
    return finish(reverb(render(ev, 5.5)[: len(breath)] + breath, 3.2, 0.45, 8000), 5.0, 0.8)


def stars_take() -> np.ndarray:
    """星河许愿, 5.0 s: "Twinkle, Twinkle, Little Star" (an old French tune, public domain) on a celesta
    under the dusk sky, a music box an octave over it, a harp rocking under it and a glassy pad; a
    shooting star rushes in and chimes where the two wishing stars meet (1.75 s), gold dust glittering
    after it, and another streaks past (3.1 s)."""
    beat = 0.3
    # (beat, beats, note), in F: twinkle, twinkle, little star, how I wonder what you are.
    tune = (
        (0, 1, 65), (1, 1, 65), (2, 1, 72), (3, 1, 72), (4, 1, 74), (5, 1, 74), (6, 2, 72),
        (8, 1, 70), (9, 1, 70), (10, 1, 69), (11, 1, 69), (12, 1, 67), (13, 1, 67), (14, 2, 65),
    )  # fmt: skip
    ev = []
    for at, _length, note in tune:
        ev.append((0.1 + at * beat, celesta, note + 12, 0.95))
        ev.append((0.1 + at * beat, music_box, note + 24, 0.6, 0.22))
    # Under it, the harp rocks through the chords, two beats each: F, F, Bb, F, Bb, F, C, F.
    chords = ((53, 60, 65), (53, 60, 65), (58, 62, 65), (53, 60, 65), (58, 62, 65), (53, 60, 65), (48, 55, 64), (53, 60, 65))
    for k, (low, mid, high) in enumerate(chords):
        at = 0.1 + k * 2 * beat
        for step, note in enumerate((low, mid, high, mid)):
            ev.append((at + step * beat / 2, harp, note, beat, 0.35 if step else 0.5))
    for note in (53, 60, 65, 69):
        ev.append((0.0, glass, note, 4.3, 0.45))
    ev.append((1.2, whoosh, 0.6, 9000, 2500, 0.55))
    for k, note in enumerate((96, 103, 100, 108)):
        ev.append((1.75 + k * 0.03, chime, note, 0.6 - 0.08 * k))
    for k in range(8):
        ev.append((1.85 + k * 0.06 + RNG.uniform(0, 0.03), sparkle, 0.6))
    ev.append((3.1, whoosh, 0.45, 8000, 3000, 0.25))
    return finish(reverb(render(ev, 5.5), 2.4, 0.36, 7000), 5.0, 0.7)


def cyber_take() -> np.ndarray:
    """赛博, 5.0 s: power coming on and the neon stuttering (0-0.9 s), then a synthwave pulse in A minor
    (a sixteenth-note bass, a kick on each beat, a pad), an electric zap at each of the five strikes
    (1.5, 2.1, 2.75, 3.3, 3.8 s), and the power going down (4.4 s)."""
    ev = []
    riser = band(RNG.normal(0, 1, int(0.9 * SR)), 400, 9000) * np.linspace(0, 1, int(0.9 * SR)) ** 2 * 0.06
    t = times(0.9)
    riser += np.sin(2 * np.pi * np.cumsum(np.geomspace(70, 420, len(t))) / SR) * np.linspace(0, 1, len(t)) * 0.08
    on = [(0.32, 0.38), (0.45, 0.5), (0.58, 0.7), (0.78, 4.4)]
    sixteenth = 0.125
    chords = ((0.9, 45, (57, 60, 64)), (1.9, 41, (57, 60, 65)), (2.9, 48, (55, 60, 64)), (3.9, 43, (55, 59, 62)))
    for start, root, pad in chords:
        for k in range(8):
            at = start + k * sixteenth
            if at >= 4.4:
                break
            ev.append((at, saw_bass, root + (0, 12, 7, 12)[k % 4], sixteenth * 0.8, 0.9 if k % 4 == 0 else 0.6))
        for note in pad:
            ev.append((start, synth_pad, note, 1.0, 1.0))
    for beat_at in np.arange(1.0, 4.45, 0.5):
        ev.append((float(beat_at), kick, 0.7))
    for when in (1.5, 2.1, 2.75, 3.3, 3.8):
        ev.append((when, zap, 1.0))
    base = render(ev, 5.5)
    base[: len(riser)] += riser
    base[: int(5.0 * SR)] += hum(5.0, on, 1.0)
    # The power going down: everything sinks and dims over the last 0.6 s.
    t = np.arange(len(base)) / SR
    base *= np.where(t > 4.4, np.exp(-(t - 4.4) / 0.25), 1.0)
    down = times(0.6)
    fall = np.sin(2 * np.pi * np.cumsum(np.geomspace(300, 40, len(down))) / SR) * np.exp(-down / 0.25) * 0.12
    base[int(4.4 * SR) : int(4.4 * SR) + len(fall)] += fall
    return finish(reverb(base, 1.2, 0.18, 9000), 5.0, 0.4)


def neon_take() -> np.ndarray:
    """霓虹都市, 5.0 s: rain on the city; the neon flickers on (0.3-1.1 s); city-pop chords on an electric
    piano (Fmaj7, Em7, Dm7, Cmaj7); thunder at each of the four strikes (1.3, 2.3, 3.05, 3.7 s); the
    neon powers down (4.35 s)."""
    ev = []
    chords = ((0.6, 41, (53, 57, 60, 64)), (1.8, 40, (52, 55, 59, 62)), (2.9, 38, (50, 53, 57, 60)), (3.8, 36, (48, 52, 55, 59)))
    for start, root, voicing in chords:
        ev.append((start, epiano, root, 1.1, 0.9))
        for k, note in enumerate(voicing):
            ev.append((start + k * 0.025, epiano, note, 1.1, 0.55))
    for at, note in ((1.15, 72), (1.4, 76), (2.55, 74), (3.45, 72), (4.1, 71)):
        ev.append((at, epiano, note, 0.4, 0.4))
    for when, vel, crack in ((1.3, 1.0, 1.0), (2.3, 0.6, 0.6), (3.05, 1.0, 1.0), (3.7, 0.45, 0.5)):
        ev.append((when, thunder, vel, crack))
    base = render(ev, 5.5)
    wet = rain(5.0)
    wet *= np.clip((times(5.0) - 0.15) / 0.75, 0, 1)
    base[: len(wet)] += wet
    base[: int(5.0 * SR)] += hum(5.0, [(0.3, 0.36), (0.42, 0.5), (0.6, 0.66), (0.72, 4.35)], 0.8)
    t = np.arange(len(base)) / SR
    base *= np.where(t > 4.35, np.exp(-(t - 4.35) / 0.3), 1.0)
    return finish(reverb(base, 2.0, 0.3, 7000), 5.0, 0.5)


def fluffy_take() -> np.ndarray:
    """毛茸茸, 5.0 s: the name tab drops in with a boing (0.35 s); a bouncy pizzicato tune in G with
    ukulele strums; a pop for each ❖ star as it pops in, a boing for each sprout, and soft pats as
    the paw prints trot across (1.5 s and 2.15 s on)."""
    ev = [(0.35, boing, 67, 0.9)]
    tune = ((0.6, 79), (0.85, 83), (1.1, 86), (1.35, 88), (1.6, 86), (1.85, 83), (2.1, 79), (2.6, 81), (2.85, 83), (3.1, 81), (3.35, 79), (3.6, 74), (3.85, 79))
    for at, note in tune:
        ev.append((at, pizz, note, 0.9))
    for at, chord in ((0.6, (55, 59, 62, 67)), (1.6, (55, 60, 64, 67)), (2.1, (55, 59, 62, 67)), (3.1, (54, 57, 62, 66)), (3.85, (55, 59, 62, 67))):
        for k, note in enumerate(chord):
            ev.append((at + k * 0.018, pizz, note, 0.45))
    for k, at in enumerate((0.6, 0.65, 0.75, 0.8, 0.9, 0.95, 1.05, 1.1, 1.2, 1.35, 1.45, 1.55, 1.6, 2.0)):
        ev.append((at + 0.04, pop, 84 + (k * 5) % 12, 0.55))
    for at, note in ((0.95, 72), (1.25, 76), (1.6, 79), (1.72, 81)):
        ev.append((at + 0.05, boing, note, 0.5))
    for k in range(8):
        ev.append((1.5 + 0.2 * k, pat, 60 + (3 if k % 2 else 0), 0.7))
    for k in range(7):
        ev.append((2.15 + 0.2 * k, pat, 62 + (3 if k % 2 else 0), 0.6))
    ev.append((4.1, boop, 79, 0.8))
    ev.append((4.25, boop, 86, 0.6))
    return finish(reverb(render(ev, 5.5), 1.4, 0.22, 8000), 5.0, 0.7)


def main() -> None:
    global RNG
    # Each sound with randomness of its own, so changing one leaves the others as they were.
    for seed, (name, take) in enumerate(
        (("theme-ice.wav", ice_take), ("theme-stars.wav", stars_take), ("theme-cyber.wav", cyber_take),
         ("theme-neon.wav", neon_take), ("theme-fluffy.wav", fluffy_take)),
        start=11,
    ):  # fmt: skip
        RNG = wedding_tunes.RNG = np.random.default_rng(seed)
        write(name, take())


if __name__ == "__main__":
    main()
