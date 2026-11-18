# Rust preview

A build of the Rust rewrite that a player runs beside v1.0.1 to try it. It is only a GitHub Actions artifact: never a
release, draft, tag or update offer, never signed with the release key, never pushed to `main` or `1.x`.

## What differs from the normal build (`cargo build --features preview`, `rust/app/src/preview.rs`)

| | Normal | Preview |
|---|---|---|
| Name (window title, tray tooltip, log) | 模仿者小工具 | 模仿者小工具 Rust 预览 11月 v2 |
| Data folder | `%APPDATA%\BlackListDetect` | `%APPDATA%\BlackListDetect-RustPreview` (`common::paths::use_folder_name`) |
| Single-instance key | `BlackListDetect-<sha1>` | the same with `-RustPreview` |
| 开机启动 | refreshes the Run entry | never reads or writes it |
| Updater | (stub today) | always `Quiet`, whatever is wired (`preview::updater`) |
| Switch-over sweep | after a good start | never (`install_root` is None) |

First run: when the preview folder holds nothing but its logs and no `preview-copied.txt`, everything in
`%APPDATA%\BlackListDetect` is copied, each file opened read-only (`File::open`) and closed after its read: the lists
(tags, notes), 嘉宾, 组合, 我, records, 设置 (hotkeys, theme), backups, `custom_sounds\` and any other file. Left behind
(`preview::SKIPPED`): `logs\`, `sounds\` (tunes made again from the assets), `updates\` (update staging),
`mirrors.json` (the updater's), `debug\` (debug captures), and `*.tmp`, `*.lock`, `*.part`. Then `preview-copied.txt`
is written, so a later run copies nothing. The log lists what was copied (`Preview: copied N files from ...`).
`--data <folder>` skips the copy.

Tests: `cargo test -p app --features preview --test preview --lib preview` (a v1.0.1 folder written by the Python store, read back
through the data crate equal item by item; old files byte-identical with unchanged mtimes; a second run copies nothing, key and folder differ from the normal build).

## The build (`.github/workflows/rust-preview.yml`)

On push to `feature/rust` or `feature/rust-preview`, or by hand (workflow_dispatch), on windows-latest:

1. OpenCV 4.10 static (cache shared with `rust.yml`), `cargo build --release --features preview`.
2. Models: PP-OCRv5_mobile_det, PP-OCRv5_mobile_rec, PP-OCRv6_medium_rec from PaddleX's `paddle3.0.0` tarballs,
   converted with paddle2onnx 2.1.0 at opset 11 (paddlepaddle 3.2.2: paddle2onnx 2.1.0 refuses 3.0.0) in a Linux job
   (its Windows wheel fails to load its DLL), cached, handed to the Windows job as a one-day artifact. Checked here:
   the debug preview exe reads all 12 seats of the sample lobby whole with them.
3. Folder `模仿者小工具 Rust 预览 11月 v2\`: the exe (release profile: opt z, hot crates at 3, fat LTO), `onnxruntime.dll`
   (1.32, from the pip wheel), `models\` with PP-OCRv5_mobile_det and PP-OCRv6_medium_rec only (no PP-OCRv5_mobile_rec:
   the one-reader path), `assets\` laid out as `tools/size/sound_compress.py --stage` does, from the committed `rust/assets/sounds/*.ogg`
   (Vorbis q6; the script's --stage re-encodes first, so it is not run),
   `使用说明.txt` (`rust/app/preview/使用说明.txt`, written as UTF-8 with BOM and CRLF).
4. Smoke: a temp `%APPDATA%` with a made-up v1.0.1 list; `--quit-after-start` must log every start-up step ok, the
   models found and the copy, leave the old list unchanged; `check blacklist_detect/assets/sample-lobby.jpg` must find
   the lobby and read at least 8 of 12 seats whole. Both outputs go to the run summary.
5. Upload as artifact `模仿者小工具 Rust 预览 11月 v2` (the name the user gave this preview: "Nov v2"), kept 14 days. The exe's
   .pdb is its own artifact (`... pdb`), never in the player's zip. A Sizes step writes a table per part to the summary.

## What only a real PC shows

Hotkeys and the screen copy over the game, the marks on the game, the tray icon and menu, sounds, 直播模式, SmartScreen's
warning, and that the copy from a real v1.0.1 folder reads the player's own lists.
