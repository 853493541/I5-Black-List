"""The engine comparison tool's own logic: comparing names, the pass rule, finding images, and a real run when
Paddle, ONNX Runtime and the models are all here."""

import importlib.util
import os
import zipfile
from pathlib import Path

import numpy as np
import pytest

from tools.engine_bench import (
    Name,
    OnnxRuntimeRunner,
    Read,
    char_edits,
    compare,
    load_reads,
    lobby_images,
    main,
    summary,
    unpacked_size,
    verdict,
)

FIXTURE = Path(__file__).parent / "fixtures" / "reference-lobby.png"


def read(image, *texts, found=True):
    return Read(image, found, [Name(text, 0.9) for text in texts])


def test_char_edits_name_each_change():
    assert char_edits("心动小鹿", "心动小鹿") == []
    assert char_edits("心动小鹿", "心动小廘") == ["replace '鹿'->'廘' at 3"]
    assert char_edits("示例坏人", "示例坏人呀") == ["insert '呀' at 4"]
    assert char_edits("心动星星", "心星星") == ["delete '动' at 1"]


def test_identical_reads_pass():
    reference = [read("a.png", "心动小鹿", "示例坏人"), read("b.png", "心动星星")]
    same, total, differences = compare(reference, [read("b.png", "心动星星"), read("a.png", "心动小鹿", "示例坏人")])
    assert (same, total, differences) == (3, 3, [])
    assert verdict(same, total) == "PASS"


def test_one_character_off_fails():
    same, total, differences = compare([read("a.png", "心动小鹿", "示例坏人")], [read("a.png", "心动小鹿", "示例坏入")])
    assert (same, total) == (1, 2)
    assert verdict(same, total) == "FAIL"
    [diff] = differences
    assert (diff.image, diff.slot, diff.paddle, diff.other) == ("a.png", 1, "示例坏人", "示例坏入")
    assert diff.edits == ["replace '人'->'入' at 3"]


def test_missing_names_images_and_lobbies_count_as_differences():
    reference = [read("a.png", "心动小鹿", "示例坏人"), read("b.png", "心动星星"), read("c.png", found=False)]
    other = [read("a.png", "心动小鹿"), read("c.png", "多余", found=True)]
    same, total, differences = compare(reference, other)
    assert (same, total) == (1, 4)
    assert [(d.image, d.slot) for d in differences] == [("a.png", 1), ("b.png", 0), ("c.png", 0)]
    assert differences[1].edits == ["image not read"]
    assert differences[2].edits[0] == "lobby found: paddle False, other True"


def test_saved_reads_load_back(tmp_path):
    import json
    from dataclasses import asdict

    saved = [Read("a.png", True, [Name("心动小鹿", 0.98)], [0.5, 0.6]), read("b.png", found=False)]
    path = tmp_path / "paddle.json"
    path.write_text(json.dumps([asdict(r) for r in saved], ensure_ascii=False), "utf-8")
    assert load_reads(path) == saved


def test_nothing_compared_is_not_a_pass():
    assert verdict(0, 0) == "FAIL"


def test_lobby_images_takes_a_file_or_any_folder(tmp_path):
    (tmp_path / "sub").mkdir()
    for name in ("b.PNG", "a.jpg", "sub/c.webp", "notes.txt"):
        (tmp_path / name).write_bytes(b"")
    assert [p.name for p in lobby_images(tmp_path)] == ["a.jpg", "b.PNG", "c.webp"]
    assert lobby_images(tmp_path / "a.jpg") == [tmp_path / "a.jpg"]


def test_unpacked_size_adds_up_the_files(tmp_path):
    wheel = tmp_path / "x-1.0-py3-none-win_amd64.whl"
    with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("a.bin", b"0" * 1000)
        archive.writestr("b.bin", b"1" * 234)
    assert unpacked_size(wheel) == 1234


def test_summary_states_the_rule_and_every_difference():
    report = {
        "rule": "One difference = fail.",
        "threads": 4,
        "repeat": 3,
        "engines": {
            "paddle": {"seconds_per_lobby": 0.8, "lobbies_found": 1},
            "onnxruntime": {
                "verdict": "FAIL", "identical": 1, "total": 2, "seconds_per_lobby": 0.6, "lobbies_found": 1,
                "differences": [{"image": "a.png", "slot": 1, "paddle": "示例坏人", "other": "示例坏入",
                                 "paddle_confidence": 0.9, "other_confidence": 0.8, "edits": ["replace '人'->'入' at 3"]}],
                "confidence": [[["心动小鹿", 0.9, 0.9], ["示例坏入", 0.9, 0.8]]],
            },
            "openvino": {"verdict": "FAIL", "error": "RuntimeError: no"},
        },
        "sizes": {"onnxruntime": {"unpacked_mb": 30.0}},
    }
    text = summary(report)
    assert "One difference = fail." in text
    assert "onnxruntime: FAIL, names identical 1/2" in text and "wheel unpacked 30.0 MB" in text
    assert "a.png slot 1: paddle '示例坏人' (0.9) vs '示例坏入' (0.8): replace '人'->'入' at 3" in text
    assert "openvino: FAIL, did not run" in text


def test_onnx_runner_takes_paddlex_calls(tmp_path):
    onnx = pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")
    from onnx import TensorProto, helper

    graph = helper.make_graph(
        [helper.make_node("Relu", ["x"], ["y"])],
        "relu",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [None, 3])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [None, 3])],
    )
    path = tmp_path / "relu.onnx"
    onnx.save(helper.make_model(graph, opset_imports=[helper.make_opsetid("", 11)], ir_version=7), path)
    runner = OnnxRuntimeRunner(path, threads=1)
    x = np.array([[-1.0, 0.0, 2.0]], dtype=np.float32)
    for call in (lambda: runner(x=[x]), lambda: runner([x]), lambda: runner(x=x)):
        assert call()[0].tolist() == [[0.0, 0.0, 2.0]]


def _engines_here() -> bool:
    needed = ("paddleocr", "paddle2onnx", "onnxruntime", "openvino")
    return all(importlib.util.find_spec(name) for name in needed) and bool(os.environ.get("BLACKLIST_DETECT_MODEL_DIR"))


@pytest.mark.skipif(not _engines_here(), reason="Paddle, the challenger engines or the models are not here")
def test_reference_lobby_reads_the_same_on_every_engine(tmp_path, capsys, monkeypatch):
    # The tool sets these for its own run; they go back after the test.
    for name in ("APPDATA", "PADDLE_PDX_CPU_NUM_THREADS", "PADDLE_PDX_MODEL_SOURCE"):
        monkeypatch.delenv(name, raising=False)
    assert main([str(FIXTURE), str(tmp_path), "--repeat", "1"]) == 0
    text = capsys.readouterr().out
    assert "onnxruntime: PASS, names identical 12/12" in text
    assert "openvino: PASS, names identical 12/12" in text
    assert "app-onnxruntime: PASS, names identical 12/12" in text
