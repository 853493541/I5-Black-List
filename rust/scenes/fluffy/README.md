# 毛茸茸保护协会 in Rust

`blacklist_detect/love_scenes/fluffy.py` ported to Rust (`../src/fluffy/`) and drawn with wgpu. Its
marks (ring, badge, card, lead) are not ported yet; this is the scene.

How it is built, as fluffy.py is:
- The pictures fluffy.py works out per pixel with numpy (the grained paper band, the fur of the four
  cats with its strands, blush and cool teal shade, the puffy ❖ stickers, the name tab, the enamel
  binder ring, the stamped paw print) are worked out the same way on the CPU, once (`bake.rs`,
  `paper.rs`, `pixels.rs`: light.blur, light.noise, np.gradient, light.picture). numpy's own
  generator is ported (`pcg.rs`: SeedSequence + PCG64 + `random(dtype=float32)`), so the noise,
  paper fibers and fur strands are the very numbers numpy draws; Python's `random` is `pyrand.rs`.
  Nothing is a flat fill: every pixel of fur and paper is shaded.
- The hand-drawn lines (`lines.rs`: fillet, even, tremor, pen strokes, ink outlines) are ported line
  for line, with the same seeds.
- Each frame lays the pictures on the lobby on the graphics chip (`fluffy.wgsl`): one atlas,
  bilinear where a picture is turned or sized, whole pixels where it is only moved (as QPainter
  does), clip rects; soft dots, stars and strokes are the spike's shapes. Two full-frame layers are
  worked out on the CPU only while they change: the page (band revealed behind the pens, the frame
  lines) until 1.52 s, the doodles until 2.05 s.
- What Qt itself builds (path booleans `united/intersected/simplified`, the stroker, the tab's words
  in its font) comes from Qt once as polygons at unit size: `../src/fluffy/shapes.txt`, written by
  `gen_shapes.py`. They scale with the cat, star and screen sizes.

Pictures (1920x1080 over the sample lobby, made-up names):
- `side_t<t>.png`: Python left, Rust right, half size, t = 0.5, 1.5, 3.0, 4.5 s.
- `crop_t<t>.png`: full size, Python left, Rust right: the big cat, the bottom right corner, the tab.

Remake them (from the root, then from rust/):

    PYTHONPATH=. python rust/scenes/fluffy/gen_shapes.py   # only when fluffy.py's shapes change
    PYTHONPATH=. python rust/scenes/fluffy/py_frames.py    # py_t*.png, lobby_1920.png
    cargo run --release -p scenes --bin fluffy_frames        # rust_t*.png, side_*, the numbers

Results on this container (Mesa llvmpipe, no GPU):

| t | mean abs diff | pixels off by > 8 | > 32 | PSNR |
|---|---|---|---|---|
| 0.5 s | 0.03/255 | 0.14 % | 0.013 % | 51.2 dB |
| 1.5 s | 0.06/255 | 0.22 % | 0.029 % | 48.8 dB |
| 3.0 s | 0.08/255 | 0.26 % | 0.033 % | 47.6 dB |
| 4.5 s | 0.05/255 | 0.17 % | 0.017 % | 50.6 dB |

`tests.rs` asserts 45 dB at 3.0 s (skipped without a Vulkan, Metal or DX12 adapter).

Where it still differs: most of what is left (about 60 % of the squared error) is the tab's words,
which Qt draws with its glyph rasterizer and the port fills from their outlines; the rest is
antialiased edges (the ink outlines, the cats' clip at the frame line). Here the words fall back to
WenQuanYi Micro Hei; on her PC they are YouYuan, so gen_shapes.py should run there once.

Frame time on llvmpipe: median 38 ms (Python/Qt raster on the same CPU: 7.6 ms); the worst, 155 ms,
are the frames while the pens draw, where the page layer is filled again on the CPU each frame.
Working out every picture at start: 100 ms (Python makes them lazily, a frame or two ahead).
llvmpipe shades every pixel on the CPU, so this says little about a GPU; measure on a PC. The pen
frames are the thing to watch: moving their lines onto the chip (or filling only the strip that
changed) is the fix if they miss 20 ms there.
