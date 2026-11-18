# Switch-over: v1.0.1 (Python) to the Rust app in one in-app update

2026-11-18. Package `switchover` of the Rust rewrite (docs/dev/research/rust-plan-2026-11-18.md, M6).

## The route

The release keeps the folder layout v1.0.1 already knows, so v1.0.1's updater and launcher do the
whole move as shipped. The player clicks 更新 as for any update; nothing is done by hand, and there is no
full download.

What v1.0.1 imposes (`blacklist_detect/updater.py`, `build/launcher/Launcher.cs`, identical at the tag and
at `feature/rust`; CI checks this with `git diff --exit-code v1.0.1`):

- `stage()` keeps only `blacklist_detect/**` (without a `models` or `__pycache__` part), the launchers,
  `runtime/模仿者小工具.exe` or `runtime/I5黑名单.exe`, and `使用说明.txt`, and refuses an update without
  `blacklist_detect/__init__.py`. The zip is at most 100 MB (`MAX_SIZE`).
- `read_manifest()` takes only a `releases/download/` URL on this repository, signed with the release key.
- The launcher (old code, still in memory on the first start) lays `update.new` over the folder, moving
  what it replaces into `update.old`, writes `update.check`, then starts
  `runtime\模仿者小工具.exe -m blacklist_detect [args]` (the first of 模仿者小工具.exe, I5黑名单.exe,
  pythonw.exe that exists), with the folder as working directory.

So the Rust app takes the place of the app's process exe, and everything else goes under `blacklist_detect\`:

| Path in the folder | What |
|---|---|
| `模仿者小工具.exe` | the launcher, unchanged (not in the update; in the full zip for new players) |
| `runtime\模仿者小工具.exe` | **the Rust app** |
| `blacklist_detect\__init__.py` | one-line marker v1.0.1's updater insists on |
| `blacklist_detect\onnxruntime.dll` | loaded by path (`ort` load-dynamic) |
| `blacklist_detect\ocr\<model>\inference.onnx`, `inference.yml` | the OCR models (`ocr`, not `models`, which v1.0.1 drops) |
| `blacklist_detect\assets\...` | pictures and sounds, only if the app reads them from disk |
| `blacklist_detect\files.txt` | every file the release ships: the keep list for the clean-up |
| `使用说明.txt` | the instructions, with the version filled in |

`build/make_rust_release.py` builds this, checks every update file against v1.0.1's own `_allowed`, the
marker and `MAX_SIZE`, signs version.json (`base` v1.0.1), and checks the exe imports no DLL a clean
Windows 10 lacks. The manifest format, URLs and mirrors are those of `build/release.py`.

## How the launcher starts the Rust exe

Unchanged launcher, unchanged path: it starts `runtime\模仿者小工具.exe -m blacklist_detect [--background]`.
The Rust app drops a leading `-m blacklist_detect` (`switchover::app_args`) and ignores the Python
variables the launcher sets (PYTHONPATH, PYTHONUTF8, QT_QPA_PLATFORM). Because the process keeps the name
and folder, the launcher's `RunningHere` check (it never lays an update under a running copy) and the
sign-in start (the Run key points at the launcher with `--background`) keep working. Folders from before the
rename (`runtime\I5黑名单.exe`, launcher `黑名单检测.exe`) work too: the launcher tries 模仿者小工具.exe first.

**Hard requirement on the app build:** `runtime\` keeps only the exe once the Python runtime is gone, and
v1.0.1's updater cannot put a DLL there, so the exe may import system DLLs only: build with
`-C target-feature=+crt-static`, link OpenCV statically (vcpkg `x64-windows-static`), load
`blacklist_detect\onnxruntime.dll` by path (`ort::init_from`). `make_rust_release.py` refuses an exe that
imports anything else (it reads the PE import table). Plan B, if a static build is not possible: a tiny
std-only Rust exe at `runtime\模仿者小工具.exe` that starts the real app from `blacklist_detect\app\`
with its DLLs beside it (costs the RunningHere guarantee, so the launcher must then be updated too).

## The data folder

`%APPDATA%\BlackListDetect` (lists, settings, 嘉宾, backups, logs, custom_sounds, mirrors.json) is used
as is: the formats are byte-compatible (`rust/data`), nothing is migrated, and no update step writes
there. The only write during the switch is v1.0.1's own `mirrors.json` (the route that worked).

## Cleaning up the Python app (about 770 MB)

`switchover::after_good_start(root, version)`, called by the app once it is up (main window or tray shown,
lists loaded; run it off the UI thread, deleting ~9,000 files takes seconds):

1. `stage::confirm_started`: deletes `update.check` and `update.old`; from here the launcher keeps the Rust app.
2. Unless an update is waiting (`update.new`, `update.part`) or unconfirmed (`update.check`), deletes every
   file under `runtime\` and `blacklist_detect\` that `files.txt` does not list, then the empty folders.
   Nothing else in the folder is touched. Without a proper `files.txt` (it must list itself, the marker and
   the exe), nothing is deleted. A file in use is skipped and retried at the next start.

The same call runs on every start of every later release, so files a later release drops go too.
`install_root(exe)` finds the folder (`root\runtime\<exe>` beside a launcher; None in a source build).

## A failed start

If the Rust app never confirms (crash, missing DLL, closed before it was up), `update.check` is still there
at the next launcher start, and the launcher puts v1.0.1 back from `update.old`: the files the update
added are deleted, the replaced ones return, the new ones it cannot delete are left as `<name>.failed`
(inert; the next Apply replaces them). The player sees 新版本启动失败，已恢复到之前的版本 and is on v1.0.1
again, data untouched. Nothing was deleted, as the clean-up only runs after the confirmation.

## Releases after the switch

The Rust updater (`rust/data/src/update`) keeps v1.0.1's rules (`stage::allowed`, the marker), so every
later Rust update zip has the same shape, made by the same script with `--base` the oldest Rust version it
completes. The clean-up after each confirmed start removes what the new `files.txt` no longer lists.

## Proof (Linux and windows-latest CI)

`tools/rust_golden_switchover.py` (CI: `.github/workflows/rust-switchover.yml`; pytest:
`tests/test_rust_switchover.py`): in a temp folder with its own APPDATA, lays out a v1.0.1 folder (the
tag's `blacklist_detect\`, a stand-in Python runtime) and a data folder with made-up lists; builds the
release with a throwaway Ed25519 key; serves it with http.server; runs v1.0.1's `updater.py` from the tag
(fetch_release, download, stage) as the app does on 更新; then the launcher (the real exe built from
v1.0.1's Launcher.cs on Windows, a line-for-line port on Linux) lays it over and starts the app, here
`switchover_probe` (rust/data/examples), which records its start and runs `after_good_start`.
Checks: offered without a full download, the launcher started `runtime\模仿者小工具.exe` with
`-m blacklist_detect`, update confirmed, only the release's files left in `runtime\` and
`blacklist_detect\`, launcher unchanged, data folder byte for byte the same; and for a start that fails,
v1.0.1 back byte for byte after the next launcher start.

## Needs a clean Windows 10 VM

- The real Rust app (not the probe) started by the launcher on a Windows 10 without the VC++ runtime,
  OpenCV or onnxruntime installed: OCR on a lobby, the overlay, wgpu on a GPU and on WARP.
- The real v1.0.1 app's 更新 button, end to end (Qt dialog, restart via `--wait-pid`), from GitHub and
  through a mirror, then a reboot (the Run-key start with `--background`).
- Antivirus (Defender) on a new unsigned exe at the old path, and a folder under a Chinese path.
- Clean-up while the folder is open in Explorer or a file is locked; the 770 MB really gone.
- A failed start: the 新版本启动失败 notice, v1.0.1 running again, and the update offered again.
