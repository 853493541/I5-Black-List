"""场景管理's own sound: a player's file, read once as it is chosen, kept as the app's own WAV.

Whatever the file (FILTER), decode reads it into mono 16-bit samples at 44.1 kHz, the format of the
built-in tunes (ui_music.TUNES), and save_clip keeps at most CLIP_S of it, about as loud as they are
(TARGET_RMS_DBFS, peaks no higher than PEAK_DBFS), as <scene key>-<n>.wav in a folder of the app's own
(song_name: a 场景 keeps up to three).
From then on it plays like any tune: winsound, a quieter copy for its 音量 (ui_music.scaled_tune).
While the part is picked (选择片段), save_rest writes the song from a moment on, for winsound to play there:
it cannot start a file anywhere but at its start.

WAV is read here with Python's wave. Everything else goes through Qt's QAudioDecoder, which hands the
file to Windows' own decoders (Media Foundation): nothing is bundled for the formats themselves. The
release's runtime has no QtMultimedia, though (make_release keeps the Qt it starts with small), so it
carries the three files QAudioDecoder needs in blacklist_detect/qtmedia, which an update delivers like
the rest of the app, and _load_qtmultimedia loads them from there. Only when a file is chosen, never as
the app starts: a failure there would only leave WAV, where at start it would roll an update back.
"""

from __future__ import annotations

import itertools
import logging
import os
import re
import time
import wave
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

# What the 上传 file dialog offers. Not .ogg or .opus: Windows has no decoder for them.
FILTER = "*.mp3 *.m4a *.aac *.mp4 *.mov *.wav *.flac *.wma *.webm *.mkv *.amr"
# Where Qt cannot be loaded, only WAV is read.
WAV_FILTER = "*.wav"
# Videos: their sound is what is kept.
VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".mkv"}
RATE = 44100
# The most of a file read: a longer one is read this far, and flagged (Decoded.cut).
MAX_DECODE_S = 600
# The most of it kept.
CLIP_S = 5.0
FADE_IN_S = 0.01
FADE_OUT_S = 0.25
# As loud as the built-in tunes are made, with room left above the loudest moment.
TARGET_RMS_DBFS = -19.0
PEAK_DBFS = -3.0
# How long Qt is given: this long, and this much more for every minute it has read.
DECODE_TIMEOUT_S = 10.0
DECODE_TIMEOUT_PER_MINUTE_S = 2.0
# The release's QtMultimedia and its Windows backend (make_release._stage_qtmedia).
QTMEDIA = Path(__file__).resolve().parent / "qtmedia"

_KEY = re.compile(r"[a-z0-9_-]+")
# Shorter than this is no sound at all.
_MIN_S = 0.05


class SoundImportError(Exception):
    """The file cannot be used; the message is for the player."""


@dataclass(frozen=True)
class Decoded:
    """A file's sound, mono 16-bit at RATE. seconds: how much was read; cut: the file is longer than
    MAX_DECODE_S and only its start was read. name: the file's name without its type."""

    samples: np.ndarray
    seconds: float
    name: str
    cut: bool = False


@dataclass(frozen=True)
class Imported:
    """A sound kept for a 场景: the WAV at path, made from length_s seconds of the file called name
    (original_s long, as read) from start_s on."""

    path: Path
    name: str
    original_s: float
    start_s: float
    length_s: float


_qtmultimedia = None
_dll_dirs: list = []


def _load_qtmultimedia():  # noqa: ANN202
    """PySide6.QtMultimedia, from the release's qtmedia folder when it has one, else PySide6's own.
    Raises ImportError or OSError when it cannot be loaded."""
    global _qtmultimedia
    if _qtmultimedia is not None:
        return _qtmultimedia
    if QTMEDIA.is_dir():
        import PySide6
        from PySide6.QtCore import QCoreApplication

        folder = str(QTMEDIA)
        if folder not in PySide6.__path__:
            # Qt6Multimedia.dll from here, Qt6Core.dll and the rest it needs from PySide6's folder.
            _dll_dirs.append(os.add_dll_directory(folder))
            _dll_dirs.append(os.add_dll_directory(str(Path(PySide6.__file__).resolve().parent)))
            PySide6.__path__.append(folder)
            # Qt finds its backend in <library path>/multimedia.
            QCoreApplication.addLibraryPath(folder)
    from PySide6 import QtMultimedia

    _qtmultimedia = QtMultimedia
    return QtMultimedia


def available() -> bool:
    """Whether files other than WAV can be read here (loads QtMultimedia: call it on upload only).
    Not where its Windows backend cannot load (Windows N without the Media Feature Pack, a blocked
    windowsmediaplugin.dll): QtMultimedia itself loads there, but decodes nothing."""
    try:
        media = _load_qtmultimedia()
        decodes = media.QMediaFormat().supportedFileFormats(media.QMediaFormat.ConversionMode.Decode)
    except (ImportError, OSError):
        log.warning("QtMultimedia cannot be loaded: only WAV can be read", exc_info=True)
        return False
    if not decodes:
        log.warning("QtMultimedia has no backend to decode with: only WAV can be read")
        return False
    return True


def decode(source: Path) -> Decoded:
    """The sound of source, mono 16-bit at RATE, at most MAX_DECODE_S of it. Needs a Qt application
    for anything but WAV. Raises SoundImportError with the reason for the player."""
    source = Path(source)
    try:
        size = source.stat().st_size
    except OSError as error:
        raise SoundImportError("找不到这个文件") from error
    if size == 0:
        raise SoundImportError("这个文件是空的")
    read = None
    if source.suffix.lower() == ".wav":
        try:
            read = _read_wav(source)
        except (wave.Error, EOFError, ValueError, RuntimeError) as error:
            # Float samples, or a WAV wave cannot read (RuntimeError: a chunk longer than the file): Qt may.
            log.info("WAV %s goes to Qt: %s", source.name, error)
        except OSError as error:
            raise SoundImportError("这个文件打不开") from error
    if read is None:
        if not available():
            if source.suffix.lower() == ".wav":
                raise SoundImportError("这个 WAV 文件放不了")
            raise SoundImportError("这台电脑只能用 WAV 文件，换成 WAV 试试")
        read = _read_qt(source)
    samples, cut = read
    if len(samples) < _MIN_S * RATE:
        raise SoundImportError("这个视频里没有能放的声音" if source.suffix.lower() in VIDEO_SUFFIXES else "这个文件没有声音")
    return Decoded(samples, len(samples) / RATE, source.stem, cut)


def _read_wav(source: Path) -> tuple[np.ndarray, bool]:
    """A PCM WAV, 8 to 32 bits, any rate and channels. wave.Error for anything else."""
    with wave.open(str(source)) as wav:
        channels, width, rate, frames = wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()
        if width not in (1, 2, 3, 4) or channels < 1 or rate < 1000:
            raise wave.Error(f"{width * 8}-bit, {channels} channels at {rate} Hz")
        wanted = min(frames, MAX_DECODE_S * rate)
        mono: list[np.ndarray] = []
        done = 0
        # A minute at a time, so a long file never sits in memory as floats whole.
        while done < wanted:
            raw = wav.readframes(min(60 * rate, wanted - done))
            raw = raw[: len(raw) // (width * channels) * width * channels]
            if not raw:
                break
            mono.append(_to_mono(_pcm(raw, width), channels))
            done += len(mono[-1])
    samples = np.concatenate(mono) if mono else np.zeros(0, np.int16)
    return _resample(samples, rate), frames > wanted


def _pcm(raw: bytes, width: int) -> np.ndarray:
    """Little-endian PCM samples as float32 in -1..1. 8-bit WAV is unsigned, the rest signed."""
    if width == 1:
        return (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128
    if width == 2:
        return np.frombuffer(raw, "<i2").astype(np.float32) / 32768
    if width == 3:
        triples = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        value = triples[:, 0] | (triples[:, 1] << 8) | (triples[:, 2] << 16)
        value = np.where(value >= 1 << 23, value - (1 << 24), value)
        return value.astype(np.float32) / (1 << 23)
    return (np.frombuffer(raw, "<i4").astype(np.float64) / (1 << 31)).astype(np.float32)


def _to_mono(samples: np.ndarray, channels: int) -> np.ndarray:
    """Interleaved float samples, the channels mixed into one, as int16."""
    if channels > 1:
        samples = samples[: len(samples) // channels * channels].reshape(-1, channels).mean(axis=1)
    return np.clip(np.rint(samples * 32768), -32768, 32767).astype(np.int16)


def _resample(samples: np.ndarray, rate: int) -> np.ndarray:
    """int16 samples at rate, at RATE: straight lines between them, a few seconds at a time."""
    if rate == RATE or not len(samples):
        return samples
    count = int(len(samples) * RATE / rate)
    out = np.empty(count, np.int16)
    step = 10 * RATE
    for begin in range(0, count, step):
        where = np.arange(begin, min(begin + step, count)) * (rate / RATE)
        low = int(where[0])
        high = min(len(samples), int(where[-1]) + 2)
        part = np.interp(where, np.arange(low, high), samples[low:high].astype(np.float32))
        out[begin : begin + len(where)] = np.clip(np.rint(part), -32768, 32767).astype(np.int16)
    return out


def _read_qt(source: Path) -> tuple[np.ndarray, bool]:
    """Any file Windows can decode, through QAudioDecoder, asked for Int16 mono at RATE. Waits in a
    nested event loop: the window still paints, and a file that never ends is given up on."""
    from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer, QUrl

    if QCoreApplication.instance() is None:
        raise RuntimeError("decode needs a Qt application")
    media = _load_qtmultimedia()
    wanted = media.QAudioFormat()
    wanted.setSampleFormat(media.QAudioFormat.SampleFormat.Int16)
    wanted.setChannelCount(1)
    wanted.setSampleRate(RATE)
    decoder = media.QAudioDecoder()
    decoder.setAudioFormat(wanted)
    decoder.setSource(QUrl.fromLocalFile(str(source.resolve())))
    parts: list[np.ndarray] = []
    state = {"frames": 0, "cut": False, "done": False, "error": "", "late": False}
    loop = QEventLoop()
    began = time.monotonic()

    def take() -> None:
        while decoder.bufferAvailable() and not state["cut"]:
            buffer = decoder.read()
            if not buffer.isValid():
                continue
            part = _buffer_samples(media, buffer)
            room = MAX_DECODE_S * RATE - state["frames"]
            if len(part) >= room:
                part, state["cut"] = part[:room], True
            parts.append(part)
            state["frames"] += len(part)
        if state["cut"]:
            loop.quit()

    def finished() -> None:
        state["done"] = True
        loop.quit()

    def failed(error) -> None:  # noqa: ANN001
        state["error"] = state["error"] or decoder.errorString() or str(error)
        loop.quit()

    def check() -> None:
        minutes = state["frames"] / RATE / 60
        if time.monotonic() - began > DECODE_TIMEOUT_S + DECODE_TIMEOUT_PER_MINUTE_S * minutes:
            state["late"] = True
            loop.quit()

    decoder.bufferReady.connect(take)
    decoder.finished.connect(finished)
    decoder.error.connect(failed)
    timer = QTimer()
    timer.setInterval(100)
    timer.timeout.connect(check)
    try:
        decoder.start()
        # Qt's ffmpeg backend fails inside start(), before the loop would hear it. Asked through the class:
        # decoder.error() (a method named like the signal) keeps a reference to the decoder for good.
        if media.QAudioDecoder.error(decoder) != media.QAudioDecoder.Error.NoError:
            state["error"] = state["error"] or decoder.errorString() or "error"
        if not (state["error"] or state["cut"] or state["done"]):
            timer.start()
            loop.exec()
        if not (state["error"] or state["late"]):
            take()
    finally:
        timer.stop()
        decoder.stop()
        # PySide holds connected slots from C++, out of gc's sight: left connected, they would keep the
        # decoder and every sample read alive for as long as the app runs.
        decoder.bufferReady.disconnect(take)
        decoder.finished.disconnect(finished)
        decoder.error.disconnect(failed)
        timer.timeout.disconnect(check)
    if state["error"]:
        log.info("Qt could not decode %s: %s", source.name, state["error"])
        raise SoundImportError("这个视频里没有能放的声音" if source.suffix.lower() in VIDEO_SUFFIXES else "这个文件放不了")
    if state["late"]:
        log.info("Qt took too long decoding %s", source.name)
        raise SoundImportError("这个文件读不完，换一个试试")
    samples = np.concatenate(parts) if parts else np.zeros(0, np.int16)
    return samples, bool(state["cut"])


def _buffer_samples(media, buffer) -> np.ndarray:  # noqa: ANN001
    """A QAudioBuffer's samples as int16 mono at RATE, whatever format the backend gave."""
    form = buffer.format()
    raw = bytes(buffer.constData())
    kind = form.sampleFormat()
    formats = media.QAudioFormat.SampleFormat
    if kind == formats.Int16 and form.channelCount() == 1 and form.sampleRate() == RATE:
        return np.frombuffer(raw[: len(raw) // 2 * 2], "<i2").copy()
    if kind == formats.Int16:
        samples = np.frombuffer(raw[: len(raw) // 2 * 2], "<i2").astype(np.float32) / 32768
    elif kind == formats.Int32:
        samples = (np.frombuffer(raw[: len(raw) // 4 * 4], "<i4").astype(np.float64) / (1 << 31)).astype(np.float32)
    elif kind == formats.Float:
        samples = np.frombuffer(raw[: len(raw) // 4 * 4], "<f4")
    elif kind == formats.UInt8:
        samples = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128
    else:
        return np.zeros(0, np.int16)
    return _resample(_to_mono(samples, max(1, form.channelCount())), form.sampleRate() or RATE)


def save_clip(decoded: Decoded, key: str, folder: Path, start_s: float = 0.0, length_s: float = CLIP_S) -> Imported:
    """Keep length_s seconds of decoded from start_s on (at most CLIP_S, within the file) as
    folder/<key>.wav: fading in and out, as loud as the built-in tunes. Written beside it first, then
    put in its place, so a half-written sound is never played."""
    if not _KEY.fullmatch(key):
        raise ValueError(f"not a scene key: {key!r}")
    total = len(decoded.samples)
    begin = min(max(0, round(start_s * RATE)), total)
    end = min(begin + round(max(0.0, min(CLIP_S, length_s)) * RATE), total)
    if end - begin < _MIN_S * RATE:
        raise SoundImportError("选的这段太短了")
    clip = _level(decoded.samples[begin:end].astype(np.float64) / 32768)
    _fade(clip)
    folder = Path(folder)
    target = folder / f"{key}.wav"
    part = folder / f"{key}.wav.part"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        _write(part, [clip])
        os.replace(part, target)
    except OSError as error:
        part.unlink(missing_ok=True)
        log.warning("Could not keep the sound for %s", key, exc_info=True)
        raise SoundImportError("声音存不下来，再试一次") from error
    return Imported(target, decoded.name, decoded.seconds, begin / RATE, (end - begin) / RATE)


def song_name(key: str, folder: Path) -> str:
    """The name a 场景's next song is kept under (save_clip's key): <key>-<n>, n the first number with no file of
    it in folder. Never a file there already, which winsound may still hold."""
    folder = Path(folder)
    return next(f"{key}-{n}" for n in itertools.count(1) if not (folder / f"{key}-{n}.wav").exists())


def save_rest(decoded: Decoded, start_s: float, path: Path, volume: int = 100) -> Path:
    """The sound of decoded from start_s to its end as the WAV at path, at volume percent of its loudness as
    read (no levelling, no fades): what 选择片段 plays as the song goes on from a moment. A minute at a time,
    so a long song never sits in memory as floats whole."""
    total = len(decoded.samples)
    begin = min(max(0, round(start_s * RATE)), total)
    step = 60 * RATE
    gain = max(0, volume) / 100 / 32768
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        _write(path, (decoded.samples[at : at + step].astype(np.float64) * gain for at in range(begin, total, step)))
    except OSError as error:
        Path(path).unlink(missing_ok=True)
        log.warning("Could not write the song from %.1f s", start_s, exc_info=True)
        raise SoundImportError("放不了，再试一次") from error
    return Path(path)


def _write(path: Path, parts: Iterable[np.ndarray]) -> None:
    """Float samples (-1..1), part by part, as a mono 16-bit WAV at RATE."""
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        for part in parts:
            wav.writeframes(np.clip(np.rint(part * 32768), -32768, 32767).astype("<i2").tobytes())


def _level(clip: np.ndarray) -> np.ndarray:
    """clip (floats, -1..1) at about TARGET_RMS_DBFS, the moments that would go past PEAK_DBFS
    turned down on their own rather than the whole clip with them."""
    rms = float(np.sqrt(np.mean(clip**2)))
    if rms < 10 ** (-70 / 20):
        raise SoundImportError("选的这段没有声音")
    target = 10 ** (TARGET_RMS_DBFS / 20)
    peak = 10 ** (PEAK_DBFS / 20)
    for _ in range(4):
        clip = _limit(clip * (target / rms), peak)
        rms = float(np.sqrt(np.mean(clip**2)))
        if rms >= target * 10 ** (-0.25 / 20):
            break
    return np.clip(clip, -peak, peak)


def _limit(clip: np.ndarray, peak: float, block: int = RATE // 100) -> np.ndarray:
    """clip with no sample past peak: each 10 ms block's gain is the least it and its neighbours
    need, and between block centres the gain runs straight, so it never jumps and never lets one through."""
    loud = np.abs(clip)
    if loud.max(initial=0.0) <= peak:
        return clip
    blocks = -(-len(clip) // block)
    padded = np.zeros(blocks * block)
    padded[: len(clip)] = loud
    need = np.minimum(1.0, peak / np.maximum(padded.reshape(blocks, block).max(axis=1), 1e-12))
    edged = np.concatenate([need[:1], need, need[-1:]])
    need = np.minimum(np.minimum(edged[:-2], edged[1:-1]), edged[2:])
    centres = np.arange(blocks) * block + block / 2
    return clip * np.interp(np.arange(len(clip)), centres, need)


def _fade(clip: np.ndarray) -> None:
    """In place: FADE_IN_S up from silence, FADE_OUT_S down to it (less on a very short clip)."""
    rise = min(round(FADE_IN_S * RATE), len(clip) // 10)
    fall = min(round(FADE_OUT_S * RATE), len(clip) // 3)
    if rise:
        clip[:rise] *= np.linspace(0.0, 1.0, rise, endpoint=False)
    if fall:
        clip[len(clip) - fall :] *= np.linspace(1.0, 0.0, fall)
