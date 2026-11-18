"""The Rust switch-over release (build/make_rust_release.py, docs/dev/research/rust-switchover.md)."""

from __future__ import annotations

import importlib.util
import os
import struct
import subprocess
import sys
from pathlib import Path, PurePosixPath

import pytest

from blacklist_detect import updater

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):  # noqa: ANN202
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release = _load("make_rust_release", REPO / "build" / "make_rust_release.py")


def _pe(dlls: list[str]) -> bytes:
    """A minimal PE32+ file whose import table names dlls."""
    section_rva, raw = 0x1000, 0x200
    descriptors = 20 * (len(dlls) + 1)
    names, offsets = b"", []
    for dll in dlls:
        offsets.append(section_rva + descriptors + len(names))
        names += dll.encode("ascii") + b"\0"
    body = b"".join(struct.pack("<12xI4x", rva) for rva in offsets) + bytes(20) + names
    optional = bytearray(240)
    struct.pack_into("<H", optional, 0, 0x20B)
    struct.pack_into("<II", optional, 112 + 8, section_rva, len(body))
    head = bytearray(b"MZ" + bytes(0x3A) + struct.pack("<I", 0x40))
    head += b"PE\0\0" + struct.pack("<HH12xHH", 0x8664, 1, len(optional), 0x22) + optional
    head += struct.pack("<8sIIII16x", b".idata", len(body), section_rva, len(body), raw)
    return bytes(head.ljust(raw, b"\0")) + body


def test_pe_imports_reads_the_import_table(tmp_path: Path) -> None:
    exe = tmp_path / "app.exe"
    exe.write_bytes(_pe(["KERNEL32.dll", "api-ms-win-crt-runtime-l1-1-0.dll", "VCRUNTIME140.dll", "opencv_world4100.dll"]))
    assert release.pe_imports(exe.read_bytes())[:2] == ["kernel32.dll", "api-ms-win-crt-runtime-l1-1-0.dll"]
    assert release.foreign_imports(exe) == ["opencv_world4100.dll", "vcruntime140.dll"]
    # dcomp.dll: DirectComposition, in Windows since 8; the scenes' see-through window draws through it.
    exe.write_bytes(_pe(["user32.dll", "d3d12.dll", "dcomp.dll"]))
    assert release.foreign_imports(exe) == []
    exe.write_bytes(b"\x7fELF")
    assert release.foreign_imports(exe) is None


def test_every_file_of_the_update_passes_v101s_updater(tmp_path: Path) -> None:
    models = tmp_path / "models" / "PP-OCRv5_mobile_det"
    models.mkdir(parents=True)
    (models / "inference.onnx").write_bytes(b"onnx")
    for name in ("app.exe", "ort.dll"):
        (tmp_path / name).write_bytes(b"MZ")
    args = release.parse(["--version", "v2.0.0", "--app-exe", str(tmp_path / "app.exe"), "--onnxruntime", str(tmp_path / "ort.dll"),
                          "--models", str(tmp_path / "models"), "--launcher", str(tmp_path / "app.exe"), "--notes", "换新"])
    files = release.lay_out(tmp_path / "stage", args)
    release.check_update(files)
    assert release.FILES_LIST in files and release.MARKER in files and release.LAUNCHER in files
    assert "blacklist_detect/ocr/PP-OCRv5_mobile_det/inference.onnx" in files
    assert all(updater._allowed(PurePosixPath(rel)) for rel in files if rel != release.LAUNCHER)
    listed = (tmp_path / "stage" / "BlackListDetect" / release.FILES_LIST).read_text(encoding="utf-8").split()
    assert listed == files
    with pytest.raises(SystemExit):
        release.check_update([*files, "blacklist_detect/models/x/inference.onnx"])


def _probe() -> Path | None:
    name = "switchover_probe.exe" if os.name == "nt" else "switchover_probe"
    path = REPO / "rust" / "target" / "debug" / "examples" / name
    return path if path.is_file() else None


@pytest.mark.skipif(_probe() is None, reason="cargo build -p data --example switchover_probe first")
def test_v101_takes_the_rust_release_end_to_end() -> None:
    has_tag = subprocess.run(["git", "rev-parse", "-q", "--verify", "refs/tags/v1.0.1"], cwd=REPO, capture_output=True).returncode == 0
    if not has_tag:
        pytest.skip("git fetch origin tag v1.0.1 --no-tags first")
    result = subprocess.run([sys.executable, str(REPO / "tools" / "rust_golden_switchover.py"), "--probe", str(_probe())],
                            cwd=REPO, capture_output=True, text=True, timeout=240)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
