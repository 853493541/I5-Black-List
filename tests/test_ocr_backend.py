"""The opt-in ONNX Runtime backend: Paddle stays the default, and the switch asks PaddleX for its own runner."""

import importlib.util

import pytest

from blacklist_detect.ocr_engine import OcrEngine, engine_kwargs, flush_denormals, ocr_backend


def test_paddle_is_the_default(monkeypatch):
    monkeypatch.delenv("BLACKLIST_DETECT_ENGINE", raising=False)
    assert ocr_backend() == "paddle"
    assert OcrEngine().backend == "paddle"
    assert engine_kwargs("paddle") == {}


@pytest.mark.parametrize(("value", "backend"), [("onnxruntime", "onnxruntime"), (" ONNXRuntime ", "onnxruntime"), ("tensorrt", "paddle")])
def test_switch_reads_the_environment(monkeypatch, value, backend):
    monkeypatch.setenv("BLACKLIST_DETECT_ENGINE", value)
    assert ocr_backend() == backend
    assert OcrEngine().backend == backend
    assert OcrEngine(backend="paddle").backend == "paddle"


def test_onnxruntime_runs_on_the_cpu_with_the_thread_count(monkeypatch):
    monkeypatch.setenv("PADDLE_PDX_CPU_NUM_THREADS", "4")
    assert engine_kwargs("onnxruntime") == {"engine": "onnxruntime", "engine_config": {"intra_op_num_threads": 4}, "device": "cpu"}
    monkeypatch.delenv("PADDLE_PDX_CPU_NUM_THREADS")
    assert engine_kwargs("onnxruntime")["engine_config"] == {}


@pytest.mark.skipif(not (importlib.util.find_spec("paddlex") and importlib.util.find_spec("onnxruntime")),
                    reason="PaddleX or ONNX Runtime is not installed")
def test_sessions_flush_denormals():
    from paddlex.inference.models.runners.onnxruntime_runner import ONNXRuntimeRunner

    assert flush_denormals() and flush_denormals()  # a second call does not wrap it again
    runner = ONNXRuntimeRunner.__new__(ONNXRuntimeRunner)
    runner._config = {}
    import onnxruntime as ort

    runner._ort = ort
    options = runner._build_session_options()
    assert options.get_session_config_entry("session.set_denormal_as_zero") == "1"
