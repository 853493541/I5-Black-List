# pyocr

The `ocr` crate's reader as a Python module (pyo3, abi3), so the app's own check can run on Rust and be compared name by
name with `blacklist_detect/onnx_ocr.py`. It is a test tool, not part of the shipped app.

Build into the Python that runs the tools (OpenCV and libclang as for the `ocr` crate; see `../ocr/README.md`):

    cd rust/pyocr && maturin develop --release

Then, with the ONNX model folders (PP-OCRv5_mobile_det, PP-OCRv5_mobile_rec, PP-OCRv6_medium_rec: inference.onnx from
paddle2onnx 2.1.0 at opset 11, beside each model's inference.yml):

    python tools/rust_golden_ocr_parity.py <models> <out> tests/lobby_corpus tests/fixtures/reference-lobby.png
    python tools/engine_bench.py <images> <out> --engines rust --reference <reads.json> --onnx-models <models>

`tests/test_engine_bench.py` runs the reference lobby through both readers when the module is built and
BLACKLIST_DETECT_MODEL_DIR holds those folders; otherwise it skips.

The module loads ONNX Runtime from the onnxruntime package's own library (ORT_DYLIB_PATH wins), the same build the Python
reader runs, with its session settings: threads from PADDLE_PDX_CPU_NUM_THREADS or paths.ocr_threads, denormals as zero,
no spinning.

`cargo test` does not build a test binary for this crate (an extension module has no interpreter to link against); its
logic lives in `ocr::read`, tested there.

## Parity (2026-11-18)

Linked to OpenCV 4.10.0 (the version opencv-python 4.10.0.84 ships), on the 85 corpus frames and the reference lobby
(4 threads, onnxruntime 1.32.0): full reads 2308/2308 lines with identical texts, boxes and quads, score gap 0; the app's
check 936/936 names identical, lobbies found 78 on both, confidence gap 0. Per check (median of 3): Python 0.700 s wall,
2.10 s CPU; Rust 0.708 s wall, 2.11 s CPU (the networks are nearly all of it, and both run the same ONNX Runtime). Linked to Ubuntu's OpenCV 4.6, two frames find one extra box whose score lands just above
box_thresh 0.6 (fillPoly draws slanted quads differently, as `../ocr/README.md` describes), and one name strip's
preparation differs enough to move its confidence by 0.018, the text unchanged.
