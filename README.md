# Black List Detect

Windows desktop app for one lobby: **推演成功** / **模仿者狂欢（12人狂欢）** / a **倒计时** line. You set a hotkey. The app copies the display, reads the twelve names under the character cards, and warns you when one of them is on a local blacklist.

It does not click **准备案件还原**, does not read game memory, and does not send the hotkey into the lobby.

Any machine can edit the list and check a screenshot. The live screen copy (one GDI BitBlt) and the global hotkey exist only on Windows; elsewhere the window says so.

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

The blacklist is `%APPDATA%\BlackListDetect\blacklist.json` on Windows, and `$XDG_CONFIG_HOME/BlackListDetect/blacklist.json` (or `~/.config/BlackListDetect/blacklist.json`) elsewhere. The hotkey, check mode, theme, and debug-frame switch are in `settings.json` in that same folder.

That folder also holds:

- `backups\` — a copy of the list from each of the last 7 days it changed.
- `logs\app.log` — what the app did and any error, without player names. `logs\crash.log` catches a hard crash.
- `blacklist.unreadable-<time>.json` — a list file that could not be read, set aside instead of overwritten.

## Check a screenshot

In **设置 → 识别**, **检查截图** runs the same lobby and name check on a picture you pick, and **测试一下** runs it on the bundled `blacklist_detect/assets/sample-lobby.jpg`, so a friend can see recognition work without opening the game. Both show the twelve seats, with blacklist matches in red. The live check copies the screen with one GDI BitBlt on Windows; elsewhere only pictures can be checked.

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

The match-rule tests do not open a window. The reference-lobby tests run anchor detection and OCR on `tests/fixtures/reference-lobby.png` and on the bundled 测试一下 picture; they skip when PaddleOCR is not installed.

Lint with ruff (rules in `pyproject.toml`):

```bash
python -m ruff check .
```

GitHub Actions runs both on every push (`.github/workflows/tests.yml`), on Windows, without Paddle.

The window code is split by job: `ui.py` (main window and check loop), `ui_dialogs.py`, `ui_overlay.py` (the marks over the game), `ui_widgets.py`, and `ui_theme.py`.

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
on the reference lobby, and writes two zips to `distelease\`:

- `BlackListDetect-<version>-full.zip` for a first install. Right-click, Extract All, then run `黑名单检测.exe` in the folder.
- `BlackListDetect-<version>-update.zip` with only the app code. Extract it over the old folder. If `launcher.py` changed, send the full zip instead.

## Run the newest code on this PC

```bash
python build/install_local.py
```

The first run installs the app to `%LOCALAPPDATA%\Programs\BlackListDetect` and
puts a 黑名单检测 shortcut on the Desktop and in the Start menu. Every later run
asks the open app to quit, copies only the files that changed (a few seconds),
and starts it again, so the shortcut always opens the newest version. Add
`--verify` to read the reference lobby with the installed copy. Only one copy of
the app runs at a time; if another unzipped copy is open, the script says which
one to close.

## Lobby glance

Auto check copies the top 40% of the screen about twice a second and looks for
「推演成功」. It finds every text line (cheap), keeps lines shaped like a
four-character title, and reads only the four tallest; reading every line of a
text-heavy desktop took five seconds a glance on a CPU. A screen that has not
changed since the last glance is not read again. Measured on the CPU build for
30 seconds: 64 glances, half of one CPU core, 770 MB of memory (before: 6
glances, four and a half cores, 1.35 GB). The full lobby check and the name
reading are unchanged.

Paddle cannot open model files under a path with Chinese characters. The app
reaches such a folder by its Windows short name, or copies the models once to
`%LOCALAPPDATA%\BlackListDetect\models`. The release folder is still named in
English letters so neither is usually needed.

Other lobby layouts are not part of this first slice.
