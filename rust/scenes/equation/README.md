# 数学公式 on the graphics chip

`blacklist_detect/love_scenes/equation.py` ported to Rust (`../src/equation/`) and drawn with wgpu the
way the 星河许愿 spike is: shapes built on the CPU, every pixel shaded in WGSL (`equation.wgsl`), in the
Python painter's order. What the Python scene works out once with numpy (the equations' chalk glow, the
heart's fill and bloom, the drifting symbols' light) is worked out once on the CPU with the same box
blurs and glow curve (`light.rs`), packed into one atlas (`atlas.rs`) and laid on every frame, smoothed
as SmoothPixmapTransform does. Python's random is `pyrand.rs` with seed 23; the heart's Fourier series
is a plain 64-point DFT. The scene's marks (ring, badge, card) are not ported here.

## Letters

The formulas are glyph outlines filled into coverage masks (`text.rs`), placed as Qt places them:
FreeType's 16.16 linear advance cut to 1/64 px, the font's kern pairs, outline points on the 1/64 grid,
exact pixel areas. Advances match Qt to the 1/64 px (`advances_match_qt`).

| | Python asks for | Windows file | This container (Qt's fallback, compared against) |
|---|---|---|---|
| equations, labels, symbols | Cambria Math | `C:\Windows\Fonts\cambria.ttc`, face 1 | `/usr/share/fonts/truetype/freefont/FreeSerif.ttf` |
| 心动 | KaiTi | `C:\Windows\Fonts\simkai.ttf` | `/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc` |

`Fonts::load` takes the first file found in that order, so a PC gets Cambria Math and KaiTi.

## Pictures (1920x1080 over the sample lobby, made-up names)

- `side_t<t>.png`: Python left, Rust right, half size, t = 0.5, 1.5, 3.0, 4.4 s (4.4: the chalk crumbling).
- `crop_t<t>.png`: full size, Python left, Rust right: the heart and its system (top), the equations
  down the left (bottom).

Remake them (from the root, then from rust/):

    PYTHONPATH=. QT_QPA_PLATFORM=offscreen python rust/scenes/equation/py_frames.py   # py_t*.png, lobby_1920.png
    cargo run --release -p scenes --bin equation_frames                                # rust_t*.png, side_*, crop_*, the numbers

## Results (llvmpipe, no GPU)

| t | mean abs diff | pixels off by > 8 | > 32 | PSNR |
|---|---|---|---|---|
| 0.5 s | 0.40/255 | 0.65 % | 0.014 % | 45.2 dB |
| 1.5 s | 0.51/255 | 1.04 % | 0.130 % | 39.7 dB |
| 3.0 s | 0.52/255 | 1.02 % | 0.118 % | 39.9 dB |
| 4.4 s | 0.56/255 | 1.08 % | 0.146 % | 39.0 dB |

`frames_stay_close_to_python` asserts 44 dB at 0.5 s and 38.5 dB at 3.0 s (skipped without an adapter
or without these fonts).

Frame time on llvmpipe: median 72.7 ms, worst 102 ms (Python/Qt raster on the same CPU: median 23.3 ms);
building the shape list is 0.06 ms of it. llvmpipe shades every pixel on the CPU; measure on a PC.

## The gap (40 dB not reached after t = 0.5)

Almost all of the error after 0.5 s is the 22 drifting symbols (π Σ ∞ …) sitting elsewhere and being
other symbols. The Python scene picks each equation's chalk-dust specks with `rnd.sample` over the
pixels of its half-size mask above 0.5, and `_randbelow`'s rejections depend on that count; the Rust
masks agree with Qt's to about 0.002 mean (`max 0.15`), but the counts differ by a few pixels (e.g. 315
against 325), so the random stream parts after the first equation and the symbols drawn after it (and
the dust at 4.1 s on) land elsewhere. Same look, other places. Closing it needs Qt's mask bit for bit
(its glyph placement differs by hundredths of a pixel); 5 tries spent, written down here. The
formulas, heart, epicycles, polar plot, spiral and paper match to the edge pixels (`crop_*`).

Other small differences: Qt's DashLine and SquareCap ends are drawn as round-capped dashes, rect pens
with round joins, `drawText` (the spiral's numbers, the symbols) unhinted.
