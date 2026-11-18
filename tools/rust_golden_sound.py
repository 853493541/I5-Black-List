"""Golden data for the Rust sound crate (rust/sound), written by the Python app's own code.

Writes rust/sound/tests/golden/: a few made-up WAVs (noise, clicks, silence: no recordings) and sound.json with
what blacklist_detect.ui_music, sound_import, ui_sound_trim and ui_soundwave make of them and of the scenes' tunes.
Silent: no sound is ever played (BLACKLIST_DETECT_SOUND stays unset). Run with APPDATA/HOME pointed at a temp folder
and QT_QPA_PLATFORM=offscreen:

    QT_QPA_PLATFORM=offscreen python tools/rust_golden_sound.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.pop("BLACKLIST_DETECT_SOUND", None)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from blacklist_detect import sound_import as si  # noqa: E402
from blacklist_detect import ui_music as um  # noqa: E402
from blacklist_detect import ui_sound_trim as st  # noqa: E402
from blacklist_detect.ui_soundwave import SoundWave  # noqa: E402

OUT = ROOT / "rust" / "sound" / "tests" / "golden"
SOUNDS = ROOT / "tests" / "fixtures" / "sounds"


def fnv(samples: np.ndarray) -> str:
    """FNV-1a 64 of int16 samples as little-endian bytes, as hex."""
    h = 0xCBF29CE484222325
    for byte in np.asarray(samples, dtype="<i2").tobytes():
        h = ((h ^ byte) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def stats(samples: np.ndarray) -> dict:
    s = np.asarray(samples, dtype=np.int16)
    return {"len": int(len(s)), "fnv": fnv(s), "every": s[::997].tolist(),
            "rms": float(np.sqrt(np.mean(s.astype(np.float64) ** 2))) if len(s) else 0.0}


def frames(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), "<i2")


def write(name: str, data: np.ndarray, rate: int, width: int, channels: int = 1) -> Path:
    """Float data (-1..1, frames x channels) as a PCM WAV of width bytes."""
    data = np.asarray(data, dtype=np.float64).reshape(-1, channels)
    if width == 1:
        raw = np.clip(np.rint(data * 127 + 128), 0, 255).astype(np.uint8).tobytes()
    elif width == 2:
        raw = np.clip(np.rint(data * 32767), -32768, 32767).astype("<i2").tobytes()
    elif width == 3:
        v = np.clip(np.rint(data * 8388607), -8388608, 8388607).astype("<i4").reshape(-1)
        raw = np.stack([v & 255, (v >> 8) & 255, (v >> 16) & 255], axis=1).astype(np.uint8).tobytes()
    else:
        raw = np.clip(np.rint(data * 2147483647), -2147483648, 2147483647).astype("<i4").tobytes()
    path = OUT / name
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(raw)
    return path


def made_up() -> dict[str, Path]:
    rng = np.random.default_rng(5)
    rate = 16000
    t = np.arange(7 * rate)
    loud = rng.normal(0, 0.01, len(t))
    loud[(t % (rate // 2)) < 40] = 0.9  # clicks: levelled up, they pass PEAK_DBFS and are limited
    loud[3 * rate : 4 * rate] = 0.0  # a silent second
    short = np.stack([np.sin(t[: 16000] * 0.05) * 0.5, rng.normal(0, 0.2, 16000)], axis=1)
    return {
        "loud.wav": write("loud.wav", loud, rate, 2),
        "short24.wav": write("short24.wav", short, 11025, 3, 2),
        "u8.wav": write("u8.wav", rng.normal(0, 0.3, 8000).clip(-1, 1), 8000, 1),
        "i32x3.wav": write("i32x3.wav", rng.normal(0, 0.2, (12000, 3)).clip(-1, 1), 48000, 4, 3),
        "tiny.wav": write("tiny.wav", rng.normal(0, 0.2, 1000), 44100, 2),
        "silence.wav": write("silence.wav", np.zeros(4000), 8000, 2),
    }


class FakeEvent:
    def __init__(self, x: float) -> None:
        self._x = x

    def position(self):  # noqa: ANN201
        return self

    def x(self) -> float:
        return self._x

    def accept(self) -> None:
        pass


def trim_golden() -> dict:
    out: dict = {"clock": {str(v): st.clock(v) for v in (0, 0.04, 0.05, 0.15, 12.34, 59.96, 61.25, 3725.0)}}
    rng = np.random.default_rng(9)
    samples = rng.integers(-30000, 30000, 1000, dtype=np.int16)
    out["peaks"] = {"samples": samples.tolist(), "560": st.peaks(samples, 560).tolist(), "7": st.peaks(samples, 7).tolist(),
                    "short": st.peaks(samples[:5], 9).tolist(), "none": st.peaks(samples[:0], 3).tolist()}
    wave_ = st.Waveform(np.zeros(int(12.3 * 1000), np.int16), 1000)
    steps = []
    for op, a, b in [("set", 3.0, 2.0), ("set", -1.0, 9.0), ("set", 11.0, 0.1), ("nudge", 0.1, 0), ("nudge", -0.3, 0),
                     ("cut", 2.0, 0), ("cut", 7.25, 0), ("drag_left", 250.0, 0), ("drag_left", 10.0, 0), ("drag_right", 400.0, 0),
                     ("drag_right", 545.0, 0), ("drag_right", 100.0, 0), ("set", 4.0, 0.6)]:
        if op == "set":
            wave_.set_selection(a, b)
        elif op == "nudge":
            wave_.nudge(a)
        elif op == "cut":
            wave_.set_selection(a - wave_.limit, wave_.limit)
        else:
            wave_._held = "left" if op == "drag_left" else "right"
            wave_.mouseMoveEvent(FakeEvent(a))
            wave_._held = ""
        grips = {str(x): (wave_._part(x) or "seek") for x in range(0, 561, 7)}
        steps.append({"op": op, "a": a, "b": b, "start": wave_.start, "length": wave_.length, "grips": grips,
                      "x_of": wave_.x_of(wave_.start), "time_at": wave_.time_at(123.0)})
    out["waveform"] = {"duration": wave_.duration, "limit": wave_.limit, "steps": steps}
    out["levels"] = {str(t): SoundWave.levels(SoundWave, t) for t in (0.0, 0.04, 1.0, 2.5, 13.37)}
    return out


def music_golden(folder: Path, own_song: Path) -> dict:
    clock = [0.0]
    played: list = []

    def play(path: Path | None) -> None:
        played.append(None if path is None else fnv(frames(path)))

    volumes = {"ice": 50, "stars": 0, "neon": 70, "lace": 100, "claw": 35}
    songs = {"neon": own_song, "lace": folder / "gone.wav"}
    music = um.ThemeMusic(play, lambda: clock[0], folder / "copies", lambda s: (songs.get(s), volumes.get(s, 100)))
    ops = [
        ["lobby", ["心动小鹿"], "ice", True], ["lobby", ["心动小鹿"], "ice", True], ["tick", 61], ["lobby", ["心动小鹿"], "ice", True],
        ["lobby", ["心动星星"], "stars", True], ["lobby", ["心动小鹿", "心动星星"], "classic", True], ["lobby", [], "ice", True],
        ["mine", ["a", "b", "c", "d"], "neon", True], ["mine", ["a", "b", "x", "y"], "neon", True], ["mine", ["x", "y", "z", "w"], "neon", True],
        ["tick", 61], ["mine", ["x"], "cyber", False], ["ungreet"], ["mine", ["x"], "cyber", True], ["lobby", ["示例坏人"], "lace", False],
        ["ungreet"], ["lobby", ["示例坏人"], "lace", True], ["preview", "claw", 1.25], ["preview", "classic", 0], ["taste", "ice"],
        ["taste", "lyre"], ["song", "equation", None, 0.5], ["song", "neon", "own", 0], ["trial", "own", "claw"], ["stop"],
        ["mute", True], ["lobby", ["心动鹿2"], "ice", True], ["preview", "ice", 0], ["taste", "ice"], ["mute", False],
        ["preview", "angel", 0], ["preview", "fluffy", 4.99],
    ]
    results = []
    for op in ops:
        before = len(played)
        kind = op[0]
        if kind == "tick":
            clock[0] += op[1]
            got = None
        elif kind == "lobby":
            got = music.lobby(op[1], op[2], now=op[3])
        elif kind == "mine":
            got = music.mine(op[1], op[2], now=op[3])
        elif kind == "ungreet":
            got = music.ungreet()
        elif kind == "preview":
            got = music.preview(op[1], at=op[2])
        elif kind == "taste":
            got = music.taste(op[1])
        elif kind == "song":
            got = music.song(op[1], own_song if op[2] == "own" else None, at=op[3])
        elif kind == "trial":
            got = music.trial(own_song, op[2])
        elif kind == "stop":
            got = music.stop()
        else:
            music.muted = op[1]
            got = None
        results.append({"op": op, "got": got, "played": played[before:]})
    return {"volumes": volumes, "ops": results}


def main() -> None:
    app = QApplication.instance() or QApplication([])  # noqa: F841
    OUT.mkdir(parents=True, exist_ok=True)
    golden: dict = {"tunes": {k: v.name for k, v in um.TUNES.items()}}
    inputs = made_up()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        assets = {}
        for key, path in um.TUNES.items():
            d = si.decode(path)
            entry = {"seconds": um.tune_seconds(path), "decoded": stats(d.samples), "cut": d.cut,
                     "peaks560": st.peaks(d.samples, 560).tolist(), "rolling": si._rolling_gain(d.samples).tolist(),
                     "part_gain": si._part_gain(d.samples, 1.0, 2.0)}
            scaled = {}
            for vol, secs, start in [(40, None, 0.0), (70, 1.5, 0.0), (100, None, 2.0), (55, 1.5, 1.0), (100, None, 0.0)]:
                made = um.scaled_tune(path, vol, tmp / "copies", secs, start)
                scaled[f"{vol}/{secs}/{start}"] = stats(frames(made))
            entry["scaled"] = scaled
            clip = si.save_clip(d, key, tmp / "clips", 0.7, 3.2)
            entry["clip"] = {**stats(frames(clip.path)), "start_s": clip.start_s, "length_s": clip.length_s}
            entry["rest"] = stats(frames(si.save_rest(d, 1.3, tmp / "rest.wav", 60)))
            assets[key] = entry
        golden["assets"] = assets
        made = {}
        for name, path in inputs.items():
            entry: dict = {}
            try:
                d = si.decode(path)
                entry["decoded"] = stats(d.samples)
                entry["cut"] = d.cut
                entry["rolling"] = si._rolling_gain(d.samples).tolist()
                for label, (start, length) in {"a": (0.0, 5.0), "b": (2.5, 9.0), "c": (6.9, 1.0), "d": (0.3, 0.04)}.items():
                    try:
                        clip = si.save_clip(d, "k", tmp / "clips", start, length)
                        entry["clip_" + label] = {**stats(frames(clip.path)), "start_s": clip.start_s, "length_s": clip.length_s}
                    except si.SoundImportError as error:
                        entry["clip_" + label] = {"error": str(error)}
                for vol in (100, 35):
                    entry[f"rest_{vol}"] = stats(frames(si.save_rest(d, 0.5, tmp / "rest.wav", vol)))
            except si.SoundImportError as error:
                entry["error"] = str(error)
            made[name] = entry
        golden["made_up"] = made
        errors = {"missing": str(tmp / "nope.mp3")}
        (tmp / "empty.mp3").write_bytes(b"")
        errors["empty"] = str(tmp / "empty.mp3")
        golden["errors"] = {}
        for label, path in errors.items():
            try:
                si.decode(Path(path))
                golden["errors"][label] = None
            except si.SoundImportError as error:
                golden["errors"][label] = str(error)
        golden["song_name"] = []
        (tmp / "songs").mkdir()
        for n in (1, 2, 4):
            (tmp / "songs" / f"ice-{n}.wav").write_bytes(b"x")
        golden["song_name"] = [si.song_name("ice", tmp / "songs"), si.song_name("stars", tmp / "songs")]
        qt = {}
        for path in sorted(SOUNDS.iterdir()):
            try:
                d = si.decode(path)
                qt[path.name] = {"len": len(d.samples), "rms": stats(d.samples)["rms"], "peak": int(np.abs(d.samples.astype(np.int32)).max())}
            except si.SoundImportError as error:
                qt[path.name] = {"error": str(error)}
        golden["qt_decoded"] = qt
        golden["music"] = music_golden(tmp, inputs["loud.wav"])
    golden["trim"] = trim_golden()
    (OUT / "sound.json").write_text(json.dumps(golden, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print("wrote", OUT / "sound.json")


if __name__ == "__main__":
    main()
