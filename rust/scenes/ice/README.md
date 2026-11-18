# 冰蓝极光 (ice) on the graphics chip

`blacklist_detect/love_scenes/ice.py` ported to Rust (`../src/ice/`) and drawn with wgpu, in the spike's
pattern (`../spike/README.md`): shapes built on the CPU, every pixel shaded in WGSL, antialiased from the
exact distance to the edge, premultiplied, in the Python painter's order. Seeds 14 and 15 through
`pyrand`, so the frost, the dust and the glints sit exactly where the Python scene puts them.

What the scene needed beyond the spike, all inside `src/ice/`:
- `aurora.rs` + `aurora.wgsl`: the aurora's half-size picture as Python draws it (three curtains of
  96 unantialiased ray strips with their 4-stop gradients, cut by the 161-stop fold mask, then the haze
  band and the hem glow), laid on scaled up with bilinear sampling, as Qt's SmoothPixmapTransform does.
- `glass.rs`: `_glass` (numpy) line for line on the CPU, once per size as Python caches it: outline
  mask, distance on every other pixel, the three-pass box blur, `np.gradient`, the glass shading.
- `heart.rs`: glints, glow, glass, the light inside the heart (drawn at a quarter size, added with
  Qt's Plus mode, clipped to the heart), the prism bands (clipped), the starlit edge, the melt.
- `prim.rs` + `ice.wgsl`: the spike's shapes widened to 8 gradient stops, a clip outline, additive
  shapes and segment lists (the frost is one path: where branches cross the glow is not doubled).
- `gpu.rs`: the passes: wash once; per frame aurora, inner light, then the frame.

Pictures (1920x1080 over the sample lobby, made-up names), t = 0.5, 1.5, 2.0 (prism), 3.0, 4.4 (melt):
- `side_t<t>.png`: Python left, Rust right, half size.
- `crop_t<t>.png`: full size, Python left, Rust right: the heart, the aurora over the title, the frost.
- `py_t<t>.png`: the Python frames (`py_frames.py`); the test `ice::tests::matches_the_python_frames`
  compares t = 1.5 and 2.0 with them and asserts PSNR >= 45 dB (skipped without a Vulkan/Metal/DX12 adapter).

Remake them (from the root, then from rust/):

    QT_QPA_PLATFORM=offscreen PYTHONPATH=. python rust/scenes/ice/py_frames.py
    cargo run --release -p scenes --bin ice_frames      # ICE_SAVE_RUST=1 also keeps rust_t*.png

Results on this container (Mesa llvmpipe through Vulkan, a CPU rasterizer):

| t | mean abs diff | pixels off by > 8 | > 32 | PSNR |
|---|---|---|---|---|
| 0.5 s | 0.21/255 | 0.00 % | 0.000 % | 52.4 dB |
| 1.5 s | 0.28/255 | 0.12 % | 0.012 % | 47.9 dB |
| 2.0 s | 0.28/255 | 0.15 % | 0.011 % | 48.0 dB |
| 3.0 s | 0.28/255 | 0.15 % | 0.013 % | 47.8 dB |
| 4.4 s | 0.30/255 | 0.25 % | 0.012 % | 47.8 dB |

The rest is spread thin: about 40 % in the aurora band (Rust about 0.3/255 brighter; Qt rounds each of
its layers to 8 bits, the shader keeps floats) and most of the rest on the frost's fine lines in the
bottom corners (Qt's coverage against a distance estimate). By eye the frames are the same.

Frame time on llvmpipe: median 77 ms, worst 119 ms (build + draw + wait; Python/Qt on the same CPU:
median 39 ms); building the shapes is 0.18 ms of it, the glass picture is made once. llvmpipe shades
every pixel on the CPU, so this says nothing about a real GPU; CLAUDE.md's budget is 20 ms at 1080p,
measure it on a PC.

Open: the lobby is read from `../spike/lobby_1920.png`, not copied here.
