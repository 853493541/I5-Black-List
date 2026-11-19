# Preview check on GitHub's Windows runners

`.github/workflows/rust-preview-check.yml` runs the Rust preview (`--features preview`) beside the Python v1.0.1 app on
`windows-2022` and `windows-2025`, standing in for the player's PC (Windows 10 Home 22H2, i5-11400H, RTX 3050 Laptop,
1920x1080 at 125 %; docs/dev/research/test-pc-like-hers-2026-10-18.md). It runs on a push to `feature/rust` and by hand
(workflow_dispatch). Artifacts only: no release, tag or draft, nothing pushed anywhere.

## What it does

1. Pictures at 125 % and 150 %, light theme, ui_shots' made-up data:
   - Rust: `<exe> --shots <dir>` with `BLACKLIST_DETECT_SCALE=125` (or 1.25) draws every page and dialog with Slint's
     software renderer, no window and no sound (`rust/app/src/preview_check.rs`), named as tools/ui_shots.py names them.
   - Python: v1.0.1's `tools/ui_shots.py --scale 125 150` (QT_SCALE_FACTOR), in a data folder of its own.
   - The on-game cards: ui_shots' `game_*` (Python) and `cargo run -p overlay --example on_game` (Rust marks over the
     sample lobby, beside Python's).
   - `sides-125/`, `sides-150/` in the artifact: Python left, Rust right, one picture per name; `index.json` lists the
     names only one side has.
2. Measurements, same runner (`tools/preview_check/check.py`):
   - start: launch to the first visible window (median of 3), and memory 5 s later; Rust with `SLINT_SCALE_FACTOR=1.25`
     and `BLACKLIST_DETECT_SILENT=1` (the window's run makes no sound), Python with `QT_SCALE_FACTOR=1.25`.
   - corpus: the 85 frames of `data/lobby-corpus` read on the runner by one checker each (`<exe> --bench-check <dir>`,
     `tools/preview_check/py_bench.py`): time per lobby, CPU time, memory when ready / after 10 checks / at the end, and
     per frame whether the names read are identical (compared by hash; no frame or name leaves the runner).
   - scenes: `cargo run -p stage --example scene_times` (median, p95, worst at 1920x1080, as the overlay draws) and
     v1.0.1's `tools/love_frames.py` (median, 90 %, worst).
3. `report.md` (also the job summary): the table, the picture lists, and what the runner cannot test.

## What the runner cannot test

No graphics chip (scenes on WARP, so frame times compare scenes, not the 20 ms budget); Windows Server, not Windows 10
Home; no real 125 % monitor (scale per process); no game, MuMu or 直播姬 (hotkeys, game capture and the live overlay are
not exercised); the system locale stays as the image has it (a change needs a restart): the user culture is set to
zh-CN and Microsoft YaHei is installed when missing, and the report says which.

## Reading the result

Download `preview-check-<runner>-<sha>` from the run, open `report.md`, then look at every picture in `sides-125/`.

## A/B of the builds (`.github/workflows/rust-ab.yml`)

CPU per check, build against build, on the same runner. Each build is the app's own checker
(`rust/app/examples/bench_check.rs`) laid onto that build's commit and built with its release profile, next to the
models it ships. `tools/preview_check/ab.py` runs them interleaved, every build once per round, so a slow spell on the
runner hits all of them. A cold pass reads 85 lobbies as first checks (spot reset); a hot pass reads one lobby 20 times
with the spot kept, as a repeated hotkey does. The report gives the median and the min to max over rounds of CPU and
wall time per check, plus peak memory, and checks parity against the first build by the gate's rule. Start it by hand
with the v3 commit as input.
