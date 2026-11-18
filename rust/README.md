# Rust rewrite

One Cargo workspace for the Rust version of the app, shipped as one release (docs/dev/research/rust-plan-2026-11-18.md).

| Crate | What |
|---|---|
| ocr | lobby reading on ONNX Runtime: detection, recognition, CTC; must match blacklist_detect/onnx_ocr.py exactly |
| lobby | layout.py and match.py: the lobby, its name boxes, matching names to the lists |
| data | the lists, settings, 嘉宾, import, backups, logs, updater, in the Python app's exact file formats |
| win | Windows only: capture, hotkeys, single instance, tray, autostart, overlay |
| scenes | the 嘉宾 scenes |

Rules for every crate (taken in part from google/skills migrate-to-rust):
- 0 `cargo clippy` warnings.
- Files of at most about 400 lines.
- `#![forbid(unsafe_code)]` everywhere but `win` and the thin FFI edges.
- Parity with the Python app is proven on golden data that the Python code itself writes.
- Randomness is seeded and repeatable.
- A failing check gets at most 5 fix tries, then the gap is written down.
- The models and lobby frames are not committed; real player names never go into anything user-facing.

Build and test: `cd rust && cargo test && cargo clippy --all-targets`.
