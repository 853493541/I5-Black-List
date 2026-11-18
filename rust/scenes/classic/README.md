# 经典 (classic) on the graphics chip

`blacklist_detect/love_scenes/classic.py` ported line for line to `../src/classic/`. Its soft layers
(numpy in Python, `love_scenes/light.py`) are worked out once on the CPU in `soft.rs` with the same maths
(three box blurs per axis, `np.gradient`, smoothstep, premultiplied bytes): the dimmed hall with its light
from above, the frame's glow (its lines rasterized as a mask at half size, blurred twice), and 心动嘉宾 in
gold with its near-white sheen. They go to the chip as one atlas and are laid on smoothed (bilinear). The
gold double frame, its spark, the brackets, diamonds and motes (`random.Random(23)`) are shapes shaded per
pixel by the engine in `../src/lace/` (gold pens are reflected gradients, as `draw.gold_pen`).

The title's words are the one thing it does not draw: `TitleMask` is the words as a text engine sets them
(white on black at twice their size, and the font's height). Here they come from Qt (`py_frames.py` writes
`title_mask.png` and `title.txt`); the app must render them with its own text engine (Slint or a font
rasterizer) in the same face: Noto Serif SC, Source Han Serif SC or SimSun, bold, 7 pt letter spacing.

Pictures (1920x1080 over the sample lobby, made-up names):
- `side_t<t>.jpg`: Python left, Rust right, half size, t = 0.5, 1.5, 2.0 (the sheen), 3.0 and 4.0 s (fading).
- `crop_t2.0.jpg`: full size, Python left, Rust right: the title, the top left corner, the frame's ends by the button.

Remake them (from the root, then from rust/; the bin writes PNGs, committed as JPEG quality 90 to keep
this folder small; the full-size Python frames stay out of git and the test needs them written first):

    PYTHONPATH=. python rust/scenes/classic/py_frames.py
    cargo run --release -p scenes --bin classic_frames

| t | mean abs diff | pixels off by > 8 | > 32 | PSNR |
|---|---|---|---|---|
| 0.5 s | 0.07/255 | 0.00 % | 0.000 % | 59.6 dB |
| 1.5 s | 0.15/255 | 0.01 % | 0.000 % | 55.7 dB |
| 2.0 s | 0.13/255 | 0.01 % | 0.000 % | 56.2 dB |
| 3.0 s | 0.15/255 | 0.01 % | 0.000 % | 55.8 dB |
| 4.0 s | 0.24/255 | 0.00 % | 0.000 % | 53.6 dB |

`classic::tests::matches_the_python_frames` holds every frame to 53 dB (skipped without a GPU adapter).

Frame time on llvmpipe (CPU Vulkan, no GPU here): median 88 ms, worst 126 ms (Python/Qt raster on the
same CPU: 16.1 ms); building the shape list is 0.04 ms. The soft pictures are made once, at the start,
as Python makes them in `make`.
