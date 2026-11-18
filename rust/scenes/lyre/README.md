# 竖琴清风 on the graphics chip

`blacklist_detect/love_scenes/lyre.py` ported to Rust (`../src/lyre/`). The Python scene works its pictures
out per pixel once (numpy and QPainter masks) and lays them on every frame; the port does the same:

- `npr.rs`: numpy's `default_rng` (SeedSequence + PCG64), bit for bit, so the band's noise, the grain on
  the leaves and the feathers' barbs are Python's own numbers. `pyrand.rs` (Python's `random`) seeds the
  feathers' splits and the cecilias.
- `img.rs`, `raster.rs`: light.py's blur, noise, relief, ramps, "over", 8-bit premultiplied pictures, and a
  Qt-like path filler (exact across a row, 16 lines down a pixel; odd-even and winding; pens with flat,
  square and round caps and Qt's round joins).
- `wind.rs` (band, lit current, curls, strands, glint, stalks), `lyre_art.rs` (the lyre, its aura, a
  ringing string), `sprites.rs` (maple, feather, cecilia, bud, seed), `birds.rs` (the cut-outs).
- `art.rs` makes every picture for a stage (1.7 s on this CPU, release) with the gap faded out as
  `_cut_gap` does; `paint.rs` lists one frame in lyre.py's paint order (pictures with their Qt
  transforms, soft dots, and the clips the current and strands draw themselves in through, square by
  square as Python's tiles do); `gpu.rs` + `lyre.wgsl` shade every pixel: bilinear sampling through the
  inverse transform, the radial soft dot, premultiplied blending.

Pictures (1920x1080 over the sample lobby, made-up names): `side_t<t>.png` (Python left, Rust right, half
size) and `crop_t<t>.png` (full size, Python left, Rust right: the lyre top, the curl and its leaves
bottom). Remake them (from the root, then from rust/):

    QT_QPA_PLATFORM=offscreen PYTHONPATH=. python rust/scenes/lyre/py_frames.py   # py_t*.png
    cargo run --release -p scenes --bin lyre_frames                               # rust_t*.png, side_*, crop_*

Results on this container (Mesa llvmpipe through Vulkan, no GPU):

| t | mean abs diff | pixels off by > 8 | > 32 | PSNR |
|---|---|---|---|---|
| 0.5 s | 0.07/255 | 0.08 % | 0.021 % | 43.5 dB |
| 1.5 s | 0.06/255 | 0.02 % | 0.000 % | 57.4 dB |
| 3.0 s | 0.06/255 | 0.02 % | 0.000 % | 57.4 dB |
| 4.0 s | 0.05/255 | 0.02 % | 0.000 % | 57.4 dB |
| 4.7 s | 0.18/255 | 0.04 % | 0.001 % | 53.5 dB |

`tests.rs` holds the floor: 42 dB at 0.5 s, 50 dB at 1.5 and 3.0 s (skipped without a Vulkan, Metal or
DX12 adapter). What still differs: at 0.5 s the edge of the current as it draws itself in (Qt's
antialiased clip against ours), and the birds' edges (Qt's smooth scaling against a triangle filter).

Frame time on llvmpipe: median 49.5 ms (Python/Qt raster on the same CPU: 15.4 ms); building the list
is 0.04 ms of it. llvmpipe shades every pixel on the CPU, so this says nothing about a GPU; measure on a PC.

## Marks and the overlay

lyre.py brings its own marks instead of an entry in ui_overlay.LOOKS. All ported: `LOOK` (the colors the
overlay reads: glow, rim, band, card, edge, ink, flowers, disc, heart, deep, deep_glow), `MARKS_ANIMATED`,
`CARD_TOP`, and in `../src/lyre/marks.rs` the pictures `card_art` (deep-jade glass, mint edge), `ring_art`
(the wind ribbon round the button) with `ring_shimmer` (its opacity and the soft dots running round it at
t), `badge_art` (the lyre on a jade disc) and `lead` (feather / maple before each name, three pixels a
point). Against Python's own pictures (`py_marks.py` writes `mark_*.png`; `tests.rs` holds a 42 dB floor),
PSNR over premultiplied RGBA: card 43.7, ring 48.9, badge 48.4, lead feather 51.7, lead maple 50.5 dB.

How the overlay should hand the seats over: per frame, in screen points, the button's cover rect (ring),
the badge box, and each seat's name rect (card behind it, lead icon of the name height before it, index
0, 1, ... for feather / maple in turn), with the scene's time t; the scene answers with items in the
same `paint::Item` form (pictures with transforms, soft dots), drawn after the scene's own frame.
Pictures are keyed on (rect size, sharpness), made once, as lyre.py's `_mark` keeps them.
