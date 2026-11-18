# 演说家遇袭 (claw) in Rust

`blacklist_detect/love_scenes/claw.py` ported to `../src/claw/` and drawn with wgpu. As the Python scene does,
its pictures are made once on the CPU, per pixel (`art.rs`, `marks_art.rs`, with `light.rs` = light.py and
`rng.rs` = numpy's `default_rng`, SeedSequence + PCG64, bit-exact, so every noise field is the same); the
scene's `random.Random(19)` is `pyrand`. Each frame is a list of shapes and pictures with the painter's
transform and opacity (`frame.rs`), shaded per pixel in `claw.wgsl`: shapes antialiased from the exact edge
distance in their own units, pictures sampled bilinear (Qt's smooth transform), premultiplied, in the Python
painter's order. The veil (fog and flash) is drawn at half size into a texture of its own, cleared over the
button with the keep mask (DestinationIn), then laid on, as claw.py does.

The ??? and the notes are glyph outlines baked by `py_frames.py` into `../src/claw/glyphs.rs` from the faces Qt
found. Here that is Inter for both (no Microsoft YaHei or Segoe UI Symbol on Linux); run `py_frames.py` once on
Windows to bake the faces the app shows there.

## The marks (it brings its own instead of a ui_overlay look)

`marks.rs`: ring (lilac rim, claw marks at two corners striking again every 3.6 s), badge (the 指挥家's role
icon on a misty disc, the baton's tip glinting), card (misty glass, a glowing ♫), lead (a claw mark before
each name), and `LOOK` for the shared ring and the card's names. How the overlay hands things over:
- the scene: `Claw::new(width, height, gap, seats, assets)`: the stage in points, the gap (x, y, w, h) round
  the button, and the twelve name boxes (x, y, w, h) where the check read them, else layout's NAME_BOXES on a
  stage that size (`Stage.names()`); `paint(t, frame)` returns the veil's frame to draw first.
- the marks: `Marks::new(sizes, scale, assets)` once per window size and `scale` (pixels per point:
  devicePixelRatio times the painter's scale, rounded to 0.01), then `ring(frame, cover, t)`,
  `badge(frame, box, t)`, `card(frame, rect, t)`, `lead(frame, at, index)` in each window's points, t the
  seconds since the marks showed (MARKS_ANIMATED: about 30 redraws a second).

## Pictures and numbers

1920x1080 over the sample lobby (made-up names). `side_t<t>.jpg`: Python left, Rust right, half size;
`crop_t<t>.jpg` (1.5 s, 3.1 s): full-size crops of the middle (the slashes); `side_marks.jpg`: the marks,
Python left. Only these (JPEG, quality 90), `py_marks.png` and the script are committed; the full-size frames
are made again:

    PYTHONPATH=. python rust/scenes/claw/py_frames.py      # py_t*.png, py_marks.png, glyphs.rs
    cargo run --release -p scenes --bin claw_frames          # from rust/: rust_t*, side_*.png, crop_*.png, the numbers

The scene's parity test is skipped while `py_t*.png` are missing; the marks' test always runs.

| t | what | mean abs diff | pixels off by > 8 | > 32 | PSNR |
|---|---|---|---|---|---|
| 0.5 s | fog starting | 0.71/255 | 0.00 % | 0.000 % | 48.1 dB |
| 1.5 s | fog in, names lost, notes | 0.82/255 | 0.02 % | 0.003 % | 46.3 dB |
| 3.0 s | the strike starting | 0.83/255 | 0.02 % | 0.003 % | 46.5 dB |
| 3.1 s | slashes, flash, jolt, notice | 0.84/255 | 0.02 % | 0.003 % | 46.4 dB |
| 3.4 s | slashes held, smoke | 0.84/255 | 0.02 % | 0.004 % | 46.1 dB |
| 4.0 s | slashes frayed, notice | 0.81/255 | 0.01 % | 0.003 % | 46.2 dB |
| 5.3 s | fog clearing | 0.87/255 | 0.01 % | 0.003 % | 46.2 dB |
| marks | ring, badge, card, lead at t = 2 | 0.17/255 | 0.59 % | 0.024 % | 45.3 dB |

`parity.rs` asserts 45 dB on 1.5 s and 3.1 s and 44 dB on the marks (skipped with no Vulkan/Metal/DX12 adapter).
The mean difference is about 0.8/255 spread thinly over the fog: the fog passes through two 8-bit pictures
(the layers and the half-size veil) and Qt and the shader round each a little differently. The rest are edges:
masks here are antialiased from the edge distance where Qt measures area, QImage's smooth shrink of the notice
art is an area average here, and the ring and badge, drawn in Python without smooth scaling, are bilinear here.

Frame time on llvmpipe (no GPU; the CPU shades every pixel): median 63 ms, worst 118 ms at 1920x1080, building
and uploading included (Python/Qt on the same CPU: median 13.9 ms). The pictures are made in about 0.55 s,
once. This says little about a real GPU; measure it on a PC against the 20 ms budget.
