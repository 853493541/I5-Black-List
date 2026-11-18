# 霓虹都市 (赛博朋克（二）) in Rust

`blacklist_detect/love_scenes/neon.py` ported to `../src/neon/` and drawn with wgpu, the spike's pattern:

- What Python works out per pixel once and caches (the night wash, the storm clouds lit by lightning,
  each side's flash, the frame tubes' glow, street haze, searchlight beam, every tower's body and lit
  windows with their bloom, the billboards' glyph pictures, each bolt's light, the round glows) is
  worked out per pixel once on the CPU (`sky.rs`, `towers.rs`, `signs.rs`, `fx.rs`; 0.4 s) and packed
  into one atlas. `np.rs` is numpy's `default_rng` (SeedSequence + PCG64, float32/float64 draws, the
  ziggurat normal and exponential with numpy's own tables in `zig.rs`), so the value noise, the rain
  and the sparks come out as numpy makes them; `pyrand.rs` covers Python's `random` (towers, windows,
  glyphs, bolts).
- Each frame is a list of shapes and pictures in the Python painter's order (`paint.rs`), shaded per
  pixel in `neon.wgsl`: rain, car trails, tubes, bolts, rings, arcs and sparks from the exact edge
  distance; pictures sampled bilinear where Qt smooths them; source-over and Plus runs.

Pictures (1920x1080 over the sample lobby, made-up names):
- `side_t<t>.png`: Python left, Rust right, at half size.
- `crop_t<t>.png`: full size, Python left, Rust right: the struck spire with its sparks (top), the
  right towers and ticker or the left tower (bottom).

Remake them (from the root, then from rust/):

    PYTHONPATH=. python rust/scenes/neon/py_frames.py        # py_t*.png, lobby_1920.png
    cargo run --release -p scenes --bin neon_frames            # rust_t*.png, side_*, the numbers

Results on this container (Mesa llvmpipe through Vulkan, a CPU rasterizer):

| t | what is on | mean abs diff | pixels off by > 8 | > 32 | PSNR |
|---|---|---|---|---|---|
| 0.5 s | night, spark round the frame, rain | 0.30/255 | 0.00 % | 0.001 % | 51.8 dB |
| 1.5 s | strike on the left spire, sparks, glitching screen | 1.16/255 | 5.83 % | 0.233 % | 37.0 dB |
| 3.0 s | leader feeling down to the frame | 0.69/255 | 1.97 % | 0.104 % | 41.9 dB |
| 3.75 s | second strike on the left, surge | 1.12/255 | 5.26 % | 0.163 % | 38.3 dB |

(2.0 s, nothing striking: 43.8 dB.) `check.rs` asserts floors about 3 dB under these.

Gaps, written down:
- Qt's `CompositionMode_Plus` applies the opacity after the saturating add,
  d·(1−o) + o·min(d+s, 1); the blend unit can only do min(d + o·s, 1). Where added light saturates
  (the strike's flash, the frame's surge, the tubes in their own glow) Rust is up to ~20/255 brighter.
  That is most of the error at 1.5 and 3.75 s. Fixing it needs the destination in the shader (a
  copy per Plus run).
- The lit frame tubes are drawn as their two strokes each frame; Python bakes them into strips and
  lays the strips at an opacity, which composes the glass and core differently by a few levels.
- Masks Qt rasterizes (tower outlines, glyphs, the frame for its glow) are exact area for rects and
  edge-distance elsewhere, supersampled where shapes meet: edges differ by a level or two.
- Tower pictures are laid with nearest sampling as Qt does without SmoothPixmapTransform; its exact
  pixel choice at fractional offsets can differ by one pixel on rising towers.

Frame time on llvmpipe: median 140 ms (Python/Qt raster on the same CPU: 27 ms); building the shape
list is 0.09 ms of it. llvmpipe shades every pixel on the CPU and the scene lays several screen-sized
pictures, so this says nothing about a real GPU, where it is a few hundred quads; measure it on a PC.
