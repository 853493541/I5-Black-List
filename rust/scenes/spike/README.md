# Scene spike: 星河许愿 on the graphics chip

`stars.py` ported to Rust (`../src/stars.rs`) and drawn with wgpu: each frame is a list of shapes (discs,
polygons, strokes, crescents, gradients) built on the CPU, and one instanced draw shades every pixel of
every shape in WGSL (`../src/scene.wgsl`), antialiased from the exact distance to the edge and blended
premultiplied, in the Python painter's order. `../src/pyrand.rs` is Python's own random generator, so
the stars, dust and Milky Way sit exactly where the Python scene puts them (seeds 31 and 52).

Why stars.py: it is short (291 lines), uses most of what the scenes draw with (radial and linear
gradients, soft dots, four-point stars, a stroked heart, a clipped crescent, a cached Wash with a
feathered hole over the button) and no numpy, so it is a fair test of the drawing model.

Pictures (1920x1080 over the sample lobby, made-up names):
- `side_t<t>.png`: Python left, Rust right, at half size, t = 0.5, 1.5, 3.0 s.
- `crop_t<t>.png`: full-size crops, Python left, Rust right: the heart (top) and the moon (bottom).

Remake them (from the root, then from rust/):

    PYTHONPATH=. python rust/scenes/spike/py_frames.py      # py_t*.png, lobby_1920.png
    cargo run --release -p scenes --bin stars_spike           # rust_t*.png, side_*, the numbers

Results on this container (no GPU: Mesa llvmpipe through Vulkan, a CPU rasterizer):

| t | mean abs diff | pixels off by > 8 | > 32 | PSNR |
|---|---|---|---|---|
| 0.5 s | 0.04/255 | 0.01 % | 0.000 % | 60.0 dB |
| 1.5 s | 0.04/255 | 0.04 % | 0.002 % | 56.1 dB |
| 3.0 s | 0.04/255 | 0.05 % | 0.005 % | 53.9 dB |

The few pixels that differ are the edges of sub-pixel stars (Qt's coverage against a distance
estimate). Frame time on llvmpipe: median 91 ms (Python/Qt raster on the same CPU: 24 ms); building
the shape list is 0.06 ms of it. llvmpipe shades every pixel on the CPU, so this says nothing about a
real GPU, where the same ~400 quads are a fraction of a millisecond; measure it on a PC.
