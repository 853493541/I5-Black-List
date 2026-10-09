# Black List Detect

Windows desktop app for one lobby: **推演成功** / **模仿者狂欢（12人狂欢）** / a **倒计时** line. You set a hotkey. The app copies the display, reads the twelve names under the character cards, and warns you when one of them is on a local blacklist.

It does not click **准备案件还原**, does not read game memory, and does not send the hotkey into the lobby.

This machine can edit the list and check a screenshot. DXGI Desktop Duplication and the global hotkey exist only on Windows. If that API is missing, the window says so.

## Run

Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -U pip
python -m pip install paddlepaddle==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
python -m pip install -r requirements.txt
PYTHONPATH=. python -m blacklist_detect
```

On Windows, also install the capture binding:

```bash
python -m pip install "dxcam>=0.0.5"
```

The blacklist is `%APPDATA%\BlackListDetect\blacklist.json` on Windows, and `$XDG_CONFIG_HOME/BlackListDetect/blacklist.json` (or `~/.config/BlackListDetect/blacklist.json`) elsewhere. The hotkey, mute switch, and debug-frame switch are in `settings.json` in that same folder.

## Check a screenshot

**打开截图** in the window runs the same anchor and name pipeline on a picture you pick. **立即检查** copies the display on Windows. On Linux it reports that DXGI Desktop Duplication is not available.

From a terminal, with no window:

```bash
PYTHONPATH=. python -m blacklist_detect check tests/fixtures/reference-lobby.png
```

On the included reference shot this prints twelve names. Ten of them match the lobby labels, including the three cut-off names. The third card is read as **霁玥吉尔曼** and the Latin card as **gffdsd**. The app shows that text as read. It does not rewrite it to **罪玥吉尔曼** or **gifdsd**.

## OCR model

The header is found with PaddleOCR `PP-OCRv5_mobile_det` and `PP-OCRv5_mobile_rec`. Each name strip is read once with `PP-OCRv6_medium_rec` (Chinese, local). Both run as one GPU batch on the RTX 5080 through the CUDA 12.9 Paddle build; without that build they stay on the CPU. Weights are not in this repo. The first check downloads them into the PaddleX cache (`~/.paddlex/official_models`) when the network is available.

To fetch them before opening the window:

```bash
PYTHONPATH=. python -m blacklist_detect download-models
```

If you already have the model folders, set `BLACKLIST_DETECT_MODEL_DIR` to the directory that contains the detection and recognition folders. The app still opens when the model is missing; a check then says the reader is not ready. There is no separate mock reader that invents names.

## Tests

```bash
PYTHONPATH=. python -m pytest
```

The match-rule tests do not open a window. The reference-lobby test runs anchor detection and OCR on `tests/fixtures/reference-lobby.png`.

## Release

Friends get a folder with its own Python, so they do not install anything:

```
BlackListDetect\
  黑名单检测.exe          launcher (build/launcher.spec), starts runtime\pythonw.exe
  runtime\               embeddable Python 3.12 with the packages installed
  blacklist_detect\      the app, plus models\ with the three PaddleOCR folders
```

Make the zips from an assembled `dist\黑名单检测\runtime`:

```bash
python build/make_release.py
```

It copies the runtime without the files the app never loads (unused Qt modules,
pip, test suites, headers, dxcam, and other PaddleX extras), runs the copy once
on the reference lobby, and writes two zips to `dist\release\`:

- `BlackListDetect-<version>-full.exe` for a first install. It is the `.7z` with 7-Zip's self-extractor in front, so it unpacks with a double-click. Made only when 7-Zip is installed.
- `BlackListDetect-<version>-full.7z`, the same files for people with 7-Zip, Bandizip, or WinRAR.
- `BlackListDetect-<version>-full.zip`, the same files again, about 100 MB larger, for anyone who can only open `.zip`.
- `BlackListDetect-<version>-update.zip` with only the app code. Unzip it over the old folder. If `launcher.py` changed, send the full zip instead.

Keep the top folder name in English letters. Paddle cannot open model files when
the path has Chinese characters in it, so every check fails in such a folder.

Other lobby layouts are not part of this first slice.
