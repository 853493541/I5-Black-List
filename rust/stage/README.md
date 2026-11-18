# stage: where and how a 嘉宾 scene plays over the game

The Rust side of `blacklist_detect/ui_love.py` (LoveBorder) and `love_scenes.Stage`.

| Module | What | Python |
|---|---|---|
| `geom` | Stage (size, gap round the button, badge, seats, unit, names, heart), Placement → Stage, sample_stage | love_scenes.Stage, LoveBorder.play, sample_stage |
| `pick` | SCENES, REPLACED, shown, choose, Picker (pick / draw_again / heard) | love_scenes.choose, LoveBorder.pick |
| `clock` | Player: play → Started / Waiting / Off, 33 ms tick, the scene's clock, stop → dropped | LoveBorder._begin, _step, stop |
| `scene` | the `Scene` trait, the stars.rs adapter, `make(key, stage)` | love_scenes.load(key).make(stage) |
| `paint` | the scenes shader onto any texture, over transparent (the lobby picture left out) | paintEvent |
| `window` (Windows) | topmost, click-through, see-through window: DirectComposition, else UpdateLayeredWindow | LoveBorder's window flags |

## For scene packages

Implement `Scene` (duration, optional still picture, frame at t) and `MakeScene` (make from a Stage), then add one
line to `scene::make`. A scene keeps the shape stars.rs has (`new(width, height, gap)`, `paint(t) -> Frame`,
optional still layer); the adapter is three lines. Seeds are the Python module's own, so no seed is passed.

## Parity

`tools/rust_golden_stage.py` writes `tests/golden/stage.json` from the Python code; `tests/golden.rs` matches it:
240 choose cases (4 seeds × 12 choices × 5 lasts × 6 draws), 12 LoveBorder pick runs, 4 placements (gap, unit,
heart, names, with and without seats), 3 sample stages, every scene's DURATION, TICK 33 ms, READY 0.02 s. All exact
(geometry within 1e-9).

## Frame time (星河许愿, 1920x1080, draw + wait, `tests/overlay.rs::frame_time_at_1080p`)

- llvmpipe (this container, CPU rasterizer through Vulkan): median about 100 ms, readback 10 ms (release).
- WARP (windows-latest CI, DX12 software, debug build, 4 shared cores): draw median 1126 ms at 1920x1080; in the
  window at 960x540, DirectComposition present median 269 ms, layered (draw + readback + UpdateLayeredWindow) 309 ms.
  Both paths open, play and read back with no error on WARP (`tests/windows_overlay.rs`, workflow rust-stage.yml).

Both shade every pixel on the CPU, so they only prove the paths work; they say nothing about a real GPU, where
the same few hundred quads are well under a millisecond. Python/Qt draws this scene in about 24 ms on the CPU.

## What needs a real PC

- See-through over a real game: DirectComposition's premultiplied swap chain on a WS_EX_LAYERED +
  WS_EX_NOREDIRECTIONBITMAP window, seen over MuMu in full screen and windowed; clicks reaching the game.
- The RTX 3050 + UHD laptop: which chip HighPerformance picks, and whether DirectComposition works across the
  hybrid pair (the swap chain on the dGPU, DWM on the iGPU) without stutter; frame time there.
- DPI: the window is placed in desktop pixels (the app must be per-monitor DPI aware); 125 / 150 / 200 %, and a
  game on a second monitor with another scale.
- The layered fallback's cost at 1080p and above (a readback every frame).
- Staying above the game: topmost against a full-screen game, and over 直播姬's capture.
