# One reader for every line (Rust, size-twomodels)

Question: can PP-OCRv6_medium_rec, the name reader, also read the lobby's own lines (title, countdown, ready count, the
lobby spot) so PP-OCRv5_mobile_rec is not shipped? Switch: `BLACKLIST_DETECT_ONE_READER=1`, or simply no line model
folder (ModelDirs then names the v6 folder for both and `Engine::new` loads it once). Tool:
`rust/pipeline/examples/one_reader.rs` (both modes, same build: OpenCV 4.10.0, onnxruntime 1.32.0, 4 threads, Linux).

Corpus: 85 lobby-corpus frames + reference-lobby.png, in the golden order (reference twice), 87 checks.

| | two readers (today) | one reader (v6 for all) |
|---|---|---|
| lobbies found, each check searched afresh (corpus + fixture once) | 78 (77 + 1) | 80 (79 + 1) |
| lobbies found, app order with the remembered spot (87 checks) | 85 (= golden) | 86 |
| countdown / ready / spot / name boxes on lobbies both find | - | identical (79/79 frames) |
| names on lobbies both find (948 seats) | - | identical raw and shown, confidence gap 0 |
| median per check, searched afresh | 0.75 s | 1.08 s |
| median per check, app order (spot remembered) | 0.49 s | 0.53 s |
| peak memory (VmHWM), app order | 1,140 MB | 899 MB |

The two extra lobbies (golden checks 35 and 82) are real lobbies with a faint header that the v5 line reader misses; v6
reads countdown 1 / ready 11 and countdown 19 / ready 0, both right by eye. In app order the second find moves the
remembered spot, so the next four checks place the game box 0.75 px differently (names unchanged).

Size saved: PP-OCRv5_mobile_rec folder (inference.onnx + inference.yml) 16.7 MB raw, 14.1 MB zipped (zip -9).
