# 玫瑰花边 (lace) on the graphics chip

`blacklist_detect/love_scenes/lace.py` ported line for line to `../src/lace/` (it must stay exactly as it is):
the silk swags (quadratic curves stroked round-capped), the rose-gold frame and its curls (square-capped,
clipped off the rounded gap round the button), the roses and leaves, the knots of flowers and the glints
(`random.Random(3)` through `pyrand`), the pink side glow. As in Python, from 1.6 s the frame, roses and
knots are two layers drawn once (`Lace::layers`) and laid on each frame; only silk and glints are redrawn.

`../src/lace/` also holds the engine both this scene and 经典 use (copied from the spike and grown; the
master unifies it later): `prim.rs` (paths with subpaths, curves flattened to 0.02 px, rotations, square
caps cut flat as Qt's are, clips, reflected gradients, layers, a smoothed atlas), `gpu.rs`, `scene.wgsl`,
`check.rs` (PSNR and the comparison pictures).

Pictures (1920x1080 over the sample lobby, made-up names):
- `side_t<t>.png`: Python left, Rust right, half size, t = 0.5, 1.5, 3.0 and 4.2 s (fading out, from the layers).
- `crop_t<t>.png`: full size, Python left, Rust right: a swag and its knots, the curls beside the button, the left roses.

Remake them (from the root, then from rust/):

    PYTHONPATH=. python rust/scenes/lace/py_frames.py
    cargo run --release -p scenes --bin lace_frames

| t | mean abs diff | pixels off by > 8 | > 32 | PSNR |
|---|---|---|---|---|
| 0.5 s | 0.10/255 | 0.37 % | 0.008 % | 48.2 dB |
| 1.5 s | 0.12/255 | 0.46 % | 0.010 % | 47.6 dB |
| 3.0 s | 0.12/255 | 0.43 % | 0.009 % | 47.7 dB |
| 4.2 s | 0.17/255 | 0.12 % | 0.000 % | 51.7 dB |

`lace::tests::matches_the_python_frames` holds every frame to 47 dB (skipped without a GPU adapter).
What still differs: single pixels at the tight turn of each curl (Qt's offset curve against the exact
distance, up to about 60/255 on a few pixels per curl) and the edges of the petals' 0.7 px outlines.

Frame time on llvmpipe (CPU Vulkan, no GPU here): median 241 ms, worst 346 ms (Python/Qt raster on the
same CPU: 19.9 ms); building the shape list is 0.07 ms. The cost is the wide silk strokes: every pixel
of each swag's box measures its distance to all ~100 segments of the curve, 20 times. On a GPU that is
small, but measure it on her laptop; if it is over budget, the swags can be split into bands.
