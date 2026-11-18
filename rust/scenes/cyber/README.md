# 赛博朋克（一） on the graphics chip

`love_scenes/cyber.py` ported to Rust (`../src/cyber/`), drawn with wgpu in the spike's way: shapes built
on the CPU, every pixel shaded in WGSL (`cyber.wgsl`), antialiased from the edge distance, blended
premultiplied in the Python painter's order. What cyber.py works out once per pixel (the night, the
flashes, the tubes' glow, the round glows, the radar sweep, the projector cone, the scan beam, each bolt's
light, each panel's bloom) is worked out the same way on the CPU (`light.rs`, `pics.rs`, `hud.rs`) and
packed in an atlas. `npr.rs` is numpy's default_rng (SeedSequence, PCG64, float32 random, uniform, the
normal and exponential ziggurats), so the smog, the beam's streaks and the spark showers come from the
same seeds. Renderer additions over the spike: four blends (over, plus, atop, destination-out), clip
rects, transformed pictures, and drawable layers (the night's wash, the baked tubes, one per panel, laid
on folded, torn into color-split slices, surging, flaring under the beam).

Pictures (1920x1080 over the sample lobby, made-up names):
- `side_t<t>.jpg`: Python left, Rust right, half size (the tool writes them as PNG; the JPEGs are committed).
- `crop_t3.0.jpg`: the radar panel, Python above, Rust below. `crop_t1.5.jpg`: the mesh panel.

The full-size frames (`py_t*.png`, `rust_t*.png`, `lobby_1920.png`) stay out of git; the floor test runs
only once py_frames.py has written them.

Remake (from the root, then from rust/):

    PYTHONPATH=. python rust/scenes/cyber/py_frames.py            # py_t*.png, lobby_1920.png
    cargo run --release -p scenes --bin cyber_frames               # rust_t*.png, side_*, the numbers

`CYBER_SKIP=holo,rail,beam,strike,spark` leaves parts out of the Python frames, to compare a part at a time.

| t | mean abs diff | pixels off by > 8 | > 32 | PSNR |
|---|---|---|---|---|
| 0.5 s | 0.15/255 | 0.02 % | 0.001 % | 53.9 dB |
| 1.5 s | 1.97/255 | 12.1 % | 0.90 % | 31.7 dB |
| 3.0 s | 2.05/255 | 12.8 % | 1.32 % | 31.2 dB |

By part (Python with panels, rails and beam left out): night, frame, lightning and sparks reach 55.7 dB
at 0.5 s, 46.9 dB at 1.4 s, 38.4-39.1 dB at 1.5-3.0 s.

Gaps:
- Lettering is not drawn: the panels' titles, labels, readouts, typed hex lines, LOCK and the rails'
  numbers (no font rasterizer in the crate; Consolas is not on Linux either). This is most of what is
  left at 1.5 and 3.0 s.
- Qt's Plus with an opacity blends toward the clamped sum, `d + a * min(s, 1 - d)`; a fixed GPU blend
  gives `min(d + a * s, 1)`, so the strikes' surge on the tubes' glow is up to ~10/255 brighter near the
  tubes (1.5-3.0 s). Needs a copy of the screen to read, or a different order of draws.
- The normal and exponential ziggurat tables are worked out, not copied: values off by ~1e-12, the same
  draws kept.
- Wash, panel and tube layers are redrawn each frame where Python bakes them once (same pixels).

Frame time on llvmpipe (no GPU here): median 195 ms at 1920x1080 (the panels' layers and full-screen
pictures are many full passes on a CPU rasterizer); building the shape list is 0.14 ms. Says nothing about
a GPU; measure on a PC against the 20 ms budget.
