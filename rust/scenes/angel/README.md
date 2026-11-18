# 金色传说 on the graphics chip

`love_scenes/angel.py` ported to Rust (`../src/angel/`) and drawn with wgpu. The scene's numpy
pictures are baked once on the CPU, done the same way numpy does them (`px.rs`, `gild.rs`, `glass.rs`,
`light.rs`): the raised gold of each tracery area and its warm light, the round window's smoky glass
with the 流浪汉 sack and the 愚人 hat (the icons resampled with Python's Catmull-Rom weights, seams
closed, grain from `light.noise`), the halo, the burst of rays, the shafts, the gold-leaf feather and
the spark. `pcg.rs` is numpy's `default_rng` (SeedSequence and PCG64, float64 and float32 draws, checked
against numpy's own numbers), so the noise, the shafts' streaks and the feather's barbs match Python's
values exactly. Python's `random.Random(31)` (`../src/pyrand.rs`) places the glints, feathers, motes and dust.

Each frame, `paint.rs` lays those pictures and the vector shapes on in the Python painter's order, as
image shapes (kind 7 in `angel.wgsl`, sampled from one atlas) beside the spike's gradients and stars.
Python copies the finished gold in along each line as its pen passes. Here every gold pixel keeps
the time the pen first comes within the copying stroke of it (`gild::times`), so the shader draws it
with no work on the CPU per frame. Qt's Plus at an opacity clips before it scales (`lerp(dst,
min(dst + src, 1), a)`). The round window's added light does the same in the shader against the gold
under it.

Pictures (1920x1080 over the sample lobby, made-up names):
- `side_t<t>.png`: Python left, Rust right, at half size, t = 0.5, 1.5, 3.0, 4.0 s (4.0 is after the reveal).
- `crop_t<t>.png`: full-size crops, Python left, Rust right: the top left corner (top) and the round window (bottom).

Remake them (from the root, then from rust/):

    PYTHONPATH=. python rust/scenes/angel/py_frames.py      # py_t*.png (lobby from ../spike/lobby_1920.png)
    cargo run --release -p scenes --bin angel_frames          # rust_t*.png, side_*, the numbers

Results on this container (Mesa llvmpipe through Vulkan, no GPU). `angel::parity` asserts the floors
47.5 / 45 / 44 / 42.5 dB:

| t | mean abs diff | pixels off by > 8 | > 32 | PSNR |
|---|---|---|---|---|
| 0.5 s | 0.11/255 | 0.24 % | 0.041 % | 48.7 dB |
| 1.5 s | 0.40/255 | 0.58 % | 0.027 % | 45.6 dB |
| 3.0 s | 0.48/255 | 0.67 % | 0.076 % | 44.6 dB |
| 4.0 s | 0.62/255 | 1.50 % | 0.053 % | 43.2 dB |

Baking the pictures takes 0.43 s (release), into a 2048x1486 atlas. Frame time on llvmpipe: median
78 ms, worst 145 ms (Python/Qt raster on the same CPU: 15.7 ms once its pictures are made). Building
the shape list takes 0.035 ms of that. llvmpipe shades every pixel on the CPU, so this says nothing
about a real GPU. Measure it on a PC.

Gaps:
- Qt's clipped Plus is matched only in the round window. Elsewhere (the halo's second pass, the pens'
  and glints' sparks over bright gold) the GPU adds and then clips, so those spots are 2-5/255 brighter.
  Matching them would need the target read back in the middle of a frame.
- Python bakes its pictures a frame or two before each is needed. Rust bakes all of them up front,
  which gives the same pictures; only the first frame takes longer.
- The line masks use exact distances, not Qt's rasterizer, so the edges of the gold wire differ by a
  level or two.
- Not ported: the marks (`ring`, `badge`, `card`, `lead`: the gilded button frame, rosette and lancet
  card). They belong with the overlay's marks, not with the scene's frames.
