"""特效管理's own sound: a player's file read once, as it is chosen, and kept as the app's own WAV,
mono 16-bit 44.1 kHz, as loud as the built-in tunes. Nothing here plays a sound."""

import sys
import time
import wave
from pathlib import Path

import numpy as np
import pytest

from blacklist_detect import sound_import
from blacklist_detect.sound_import import Decoded, SoundImportError, decode, save_clip

SOUNDS = Path(__file__).resolve().parent / "fixtures" / "sounds"
ROOT = Path(__file__).resolve().parent.parent


def _tone(seconds: float, rate: int = 44100, channels: int = 1) -> np.ndarray:
    """A tone that rises a semitone every second, so each second can be told apart: floats, frames x channels."""
    t = np.arange(round(seconds * rate)) / rate
    pitch = 220 * 2 ** (np.floor(t) / 12)
    mono = 0.3 * np.sin(2 * np.pi * np.cumsum(pitch) / rate)
    return np.repeat(mono[:, None], channels, axis=1)


def _write_wav(path: Path, samples: np.ndarray, rate: int, width: int) -> Path:
    if width == 1:
        data = np.clip(np.rint(samples * 127 + 128), 0, 255).astype(np.uint8).tobytes()
    elif width == 2:
        data = np.clip(np.rint(samples * 32767), -32768, 32767).astype("<i2").tobytes()
    elif width == 3:
        value = np.clip(np.rint(samples * (2**23 - 1)), -(2**23), 2**23 - 1).astype("<i4")
        data = value.view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    else:
        data = np.clip(np.rint(samples * (2**31 - 1)), -(2**31), 2**31 - 1).astype("<i4").tobytes()
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(samples.shape[1])
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(data)
    return path


def _read(path: Path) -> tuple[np.ndarray, tuple[int, int, int]]:
    with wave.open(str(path)) as wav:
        params = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate())
        return np.frombuffer(wav.readframes(wav.getnframes()), "<i2").astype(np.float64) / 32768, params


def _dbfs(samples: np.ndarray) -> float:
    return 20 * np.log10(np.sqrt(np.mean(samples**2)))


def _peak(samples: np.ndarray) -> float:
    return 20 * np.log10(np.abs(samples).max())


@pytest.fixture
def qt():  # noqa: ANN201
    """A Qt application, for the files Qt decodes; skipped where QtMultimedia is not there."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    if not sound_import.available():
        pytest.skip("QtMultimedia cannot be loaded here")
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize(
    ("width", "rate", "channels"),
    [(1, 22050, 1), (2, 44100, 1), (3, 44100, 1), (4, 44100, 1), (2, 48000, 2), (3, 48000, 2)],
)
def test_wav_of_any_depth_rate_and_channels_reads_as_mono_16_bit_at_44_1_khz(tmp_path, width, rate, channels):
    """8, 16, 24 and 32-bit PCM, 48 kHz stereo too: read without Qt, at the app's own format."""
    tone = _tone(2.0, rate, channels)
    decoded = decode(_write_wav(tmp_path / "我的 声音.wav", tone, rate, width))
    assert decoded.samples.dtype == np.int16 and decoded.samples.ndim == 1
    assert decoded.seconds == pytest.approx(2.0, abs=0.001)
    assert len(decoded.samples) == pytest.approx(2.0 * 44100, abs=2)
    assert decoded.name == "我的 声音" and not decoded.cut
    # The same sound: the tone at 44.1 kHz, as near as each depth holds it.
    expected = _tone(2.0)[:, 0]
    count = min(len(expected), len(decoded.samples))
    error = np.abs(decoded.samples[:count] / 32768 - expected[:count])
    assert np.median(error) < (0.02 if width == 1 else 0.005)


def test_a_long_file_keeps_the_part_chosen(tmp_path):
    """12 s read whole; 选择片段 keeps 5 s from 3 s on: the fourth second's pitch to the eighth's."""
    decoded = decode(_write_wav(tmp_path / "long.wav", _tone(12.0), 44100, 2))
    assert decoded.seconds == pytest.approx(12.0)
    kept = save_clip(decoded, "lace", tmp_path / "custom_sounds", start_s=3.0, length_s=5.0)
    assert kept.path == tmp_path / "custom_sounds" / "lace.wav"
    assert (kept.name, kept.original_s, kept.start_s, kept.length_s) == ("long", pytest.approx(12.0), 3.0, 5.0)
    samples, params = _read(kept.path)
    assert params == (1, 2, 44100)
    assert len(samples) / 44100 == pytest.approx(5.0, abs=0.001)
    # The middle of the clip is the tone of second 5: compare with the original there, leveled.
    original = decoded.samples[5 * 44100 : 6 * 44100] / 32768
    middle = samples[2 * 44100 : 3 * 44100]
    assert np.corrcoef(original, middle)[0, 1] > 0.999
    assert not list((tmp_path / "custom_sounds").glob("*.part"))


def test_the_kept_sound_is_as_loud_as_the_built_in_tunes(tmp_path):
    """About -19 dBFS RMS, a quiet file made louder and a loud one quieter, and never a peak past -3 dBFS."""
    rate = 44100
    for gain in (0.02, 1.0):
        decoded = decode(_write_wav(tmp_path / f"tone-{gain}.wav", _tone(5.0) * gain / 0.3 * 0.9, rate, 2))
        samples, _ = _read(save_clip(decoded, "ice", tmp_path).path)
        assert abs(_dbfs(samples) - -19.0) < 1.0
        assert _peak(samples) <= -3.0 + 0.01
    # Mostly quiet, with loud clicks: the clicks are held down on their own, the rest brought up.
    rng = np.random.default_rng(7)
    noise = rng.normal(0, 0.01, 5 * rate)
    noise[:: rate // 2] = 0.95
    clicks = Decoded(np.rint(noise * 32767).astype(np.int16), 5.0, "clicks")
    samples, _ = _read(save_clip(clicks, "claw", tmp_path).path)
    assert abs(_dbfs(samples) - -19.0) < 1.0
    assert _peak(samples) <= -3.0 + 0.01


def test_the_clip_fades_in_and_out_and_stays_inside_the_file(tmp_path):
    decoded = Decoded(np.full(6 * 44100, 8000, np.int16), 6.0, "flat")
    kept = save_clip(decoded, "stars", tmp_path, start_s=4.0, length_s=5.0)
    # Asked for 5 s from 4 s on, the file has 2 left.
    assert (kept.start_s, kept.length_s) == (4.0, 2.0)
    samples, _ = _read(kept.path)
    assert len(samples) == 2 * 44100
    assert samples[0] == 0 and abs(samples[-1]) < 1e-3
    assert abs(samples[441]) > 0.05  # 10 ms in, the sound is up
    assert abs(samples[-round(0.25 * 44100) - 10]) == pytest.approx(abs(samples[44100]), rel=0.01)
    # Never more than 5 s, however much is asked for.
    assert save_clip(decoded, "stars", tmp_path, length_s=30).length_s == 5.0


def test_a_new_sound_replaces_the_old_and_leaves_nothing_half_written(tmp_path):
    first = Decoded(np.full(44100, 3000, np.int16), 1.0, "第一个")
    second = Decoded(np.full(2 * 44100, 3000, np.int16), 2.0, "第二个")
    save_clip(first, "classic", tmp_path)
    kept = save_clip(second, "classic", tmp_path)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["classic.wav"]
    assert len(_read(kept.path)[0]) == 2 * 44100 and kept.name == "第二个"


def test_a_sound_that_cannot_be_written_says_so_and_leaves_no_part(tmp_path, monkeypatch):
    def refuse(*_args) -> None:  # noqa: ANN002
        raise PermissionError("in use")

    monkeypatch.setattr(sound_import.os, "replace", refuse)
    with pytest.raises(SoundImportError):
        save_clip(Decoded(np.full(44100, 3000, np.int16), 1.0, "x"), "lace", tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_silence_and_a_sliver_are_refused(tmp_path):
    with pytest.raises(SoundImportError):
        save_clip(Decoded(np.zeros(5 * 44100, np.int16), 5.0, "quiet"), "lace", tmp_path)
    with pytest.raises(SoundImportError):
        save_clip(Decoded(np.full(5 * 44100, 3000, np.int16), 5.0, "x"), "lace", tmp_path, start_s=4.99)
    with pytest.raises(ValueError):
        save_clip(Decoded(np.full(44100, 3000, np.int16), 1.0, "x"), "../lace", tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_a_file_longer_than_ten_minutes_is_read_to_ten_and_flagged(tmp_path, monkeypatch):
    monkeypatch.setattr(sound_import, "MAX_DECODE_S", 3)
    decoded = decode(_write_wav(tmp_path / "long.wav", _tone(5.0, 48000, 2), 48000, 2))
    assert decoded.cut and decoded.seconds == pytest.approx(3.0, abs=0.001)


def test_missing_empty_and_broken_files_are_refused_with_a_reason(tmp_path):
    with pytest.raises(SoundImportError, match="找不到"):
        decode(tmp_path / "gone.mp3")
    (tmp_path / "empty.mp3").write_bytes(b"")
    with pytest.raises(SoundImportError, match="空"):
        decode(tmp_path / "empty.mp3")


def test_without_qt_only_wav_is_read(tmp_path, monkeypatch):
    """Where QtMultimedia cannot be loaded, a WAV still is, and anything else says to use WAV."""

    def missing():  # noqa: ANN202
        raise ImportError("no QtMultimedia")

    monkeypatch.setattr(sound_import, "_load_qtmultimedia", missing)
    assert not sound_import.available()
    assert decode(_write_wav(tmp_path / "ok.wav", _tone(1.0), 44100, 2)).seconds == pytest.approx(1.0)
    with pytest.raises(SoundImportError, match="WAV"):
        decode(SOUNDS / "organ.mp3")


@pytest.mark.parametrize("name", ["organ.mp3", "organ.m4a", "organ.mp4"])
def test_mp3_m4a_and_a_videos_sound_are_read_through_qt(qt, tmp_path, name):
    """1.5 s of 玫瑰花边's organ in each: read as it was, and kept like any other."""
    decoded = decode(SOUNDS / name)
    assert decoded.samples.dtype == np.int16
    # MP3 and AAC add a few ms of padding at either end.
    assert decoded.seconds == pytest.approx(1.5, abs=0.1)
    assert decoded.name == "organ" and not decoded.cut
    with wave.open(str(ROOT / "blacklist_detect" / "assets" / "wedding-organ.wav")) as wav:
        wav.setpos(round(0.5 * 44100))
        organ = np.frombuffer(wav.readframes(round(1.5 * 44100)), "<i2").astype(np.float64)
    # The same music, give or take the encoder's delay.
    got = decoded.samples.astype(np.float64)
    best = max(np.corrcoef(organ[4410 : 4410 + 22050], got[4410 + lag : 4410 + lag + 22050])[0, 1] for lag in range(-4410, 4410, 5))
    assert best > 0.9
    kept = save_clip(decoded, "lace", tmp_path)
    samples, params = _read(kept.path)
    assert params == (1, 2, 44100) and abs(_dbfs(samples) - -19.0) < 1.0


def test_a_long_file_through_qt_is_read_to_the_limit_and_flagged(qt, monkeypatch):
    monkeypatch.setattr(sound_import, "MAX_DECODE_S", 1)
    decoded = decode(SOUNDS / "organ.mp3")
    assert decoded.cut and decoded.seconds == pytest.approx(1.0, abs=0.001)


def test_a_video_without_sound_and_garbage_are_refused_at_once(qt, tmp_path):
    with pytest.raises(SoundImportError, match="视频"):
        decode(SOUNDS / "silent-video.mp4")
    rng = np.random.default_rng(3)
    for name in ("noise.mp3", "noise.wav", "noise.m4a", "noise.wma"):
        path = tmp_path / name
        path.write_bytes(rng.integers(0, 256, 3000, dtype=np.uint8).tobytes())
        began = time.monotonic()
        with pytest.raises(SoundImportError):
            decode(path)
        assert time.monotonic() - began < 2.0, name
    # A WAV header with nothing sensible after it.
    (tmp_path / "header.wav").write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt " + bytes(40))
    began = time.monotonic()
    with pytest.raises(SoundImportError):
        decode(tmp_path / "header.wav")
    assert time.monotonic() - began < 2.0


def test_the_release_qtmedia_folder_is_loaded_from(tmp_path, monkeypatch):
    """In the release, QtMultimedia and its Windows backend come from blacklist_detect/qtmedia: the
    folder is where Windows finds its DLLs, where PySide6 finds the module, and where Qt finds the backend."""
    pytest.importorskip("PySide6")
    import PySide6
    from PySide6.QtCore import QCoreApplication

    folder = tmp_path / "qtmedia"
    (folder / "multimedia").mkdir(parents=True)
    added: list[str] = []
    monkeypatch.setattr(sound_import, "QTMEDIA", folder)
    monkeypatch.setattr(sound_import, "_qtmultimedia", None)
    monkeypatch.setattr(sound_import, "_dll_dirs", [])
    monkeypatch.setattr(sound_import.os, "add_dll_directory", lambda path: added.append(path) or path, raising=False)
    try:
        media = sound_import._load_qtmultimedia()
        assert media.__name__ == "PySide6.QtMultimedia"
        assert added == [str(folder), str(Path(PySide6.__file__).resolve().parent)]
        assert str(folder) in PySide6.__path__
        assert any(Path(path) == folder.resolve() for path in QCoreApplication.libraryPaths())
        # Once is enough.
        assert sound_import._load_qtmultimedia() is media and len(added) == 2
    finally:
        if str(folder) in PySide6.__path__:
            PySide6.__path__.remove(str(folder))
        QCoreApplication.removeLibraryPath(str(folder))


def test_the_file_dialog_offers_each_supported_kind():
    kinds = sound_import.FILTER.split()
    assert kinds == ["*.mp3", "*.m4a", "*.aac", "*.mp4", "*.mov", "*.wav", "*.flac", "*.wma", "*.webm", "*.mkv", "*.amr"]
    assert "*.ogg" not in kinds and "*.opus" not in kinds


def test_importing_it_loads_no_qt():
    """The app imports it as it starts; QtMultimedia is loaded only when a file is chosen."""
    import subprocess

    code = "import sys; import blacklist_detect.sound_import; print(any(name.startswith('PySide6') for name in sys.modules))"
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=60, check=True)
    assert result.stdout.strip() == "False"


def test_the_sample_sounds_are_small():
    for path in SOUNDS.iterdir():
        assert path.stat().st_size < 40_000, path.name
