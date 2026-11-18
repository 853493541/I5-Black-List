# ocr

The detection side of `blacklist_detect/onnx_ocr.py` on ONNX Runtime (`ort`, load-dynamic) and OpenCV (core, imgproc),
with the unclip on Clipper 6.4.2 (`clipper-sys`, the library pyclipper wraps).

## OpenCV must be 4.10

The Python app runs opencv-python 4.10.0. OpenCV 4.6.0 (Ubuntu 24.04's libopencv-dev) draws `fillPoly` differently on
some slanted quads (one pixel on a 243 x 17 box), which moves `box_score_fast` scores by up to 4e-4 (29 of 310 golden
boxes); boxes, resize and crops already match on 4.6. Linked to 4.10.0, every golden box, score and crop matches.
`examples/fillpoly_check.rs` shows the difference on the masks the Python side drew.

Build against a 4.10 (here built from the opencv-python-headless 4.10.0.84 sources, core/imgproc/imgcodecs):

    export OPENCV_LINK_LIBS=opencv_core,opencv_imgproc,opencv_imgcodecs
    export OPENCV_LINK_PATHS=/tmp/cv410/install/lib OPENCV_INCLUDE_PATHS=/tmp/cv410/install/include/opencv4
    export LD_LIBRARY_PATH=/tmp/cv410/install/lib
    cargo test -p ocr

## Golden data

`tools/rust_golden_det.py <model dir> <corpus dir>` (Python with onnxruntime 1.32.0, opencv 4.10, pyclipper) writes
`tests/golden/det.json` and the decoded frames to `/tmp/ocr-golden-frames`. The model is PP-OCRv5_mobile_det converted
with paddle2onnx 2.1.0, opset 11. `tests/det_golden.rs` finds them through `OCR_ORT_LIB`, `OCR_DET_MODEL` and
`OCR_GOLDEN_FRAMES` (defaults under /tmp) and skips with a note when they are missing.
