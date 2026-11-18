"""Make the Rust app's release: the zips, version.json and its signature.

    python build/make_rust_release.py --version v2.0.0 --app-exe rust/target/release/app.exe \
        --onnxruntime path/onnxruntime.dll --models path/onnx-models --launcher dist/exe/模仿者小工具.exe

The folder keeps the layout v1.0.1's updater and launcher know (docs/dev/research/rust-switchover.md):

    模仿者小工具.exe                     the launcher (unchanged; only in the full zip)
    使用说明.txt
    runtime/模仿者小工具.exe             the Rust app, where the launcher starts the app
    blacklist_detect/__init__.py        a one-line marker v1.0.1's updater insists on
    blacklist_detect/onnxruntime.dll    loaded by path (ort load-dynamic)
    blacklist_detect/ocr/<model>/...    inference.onnx and inference.yml per model ("models" is a name
                                        v1.0.1's updater leaves out of an update, so not that)
    blacklist_detect/assets/...         the app's pictures and sounds, when it reads them from disk
    blacklist_detect/files.txt          every file above: the app deletes what is not listed once it
                                        started well (rust/data/src/update/switchover.rs)

Output in dist/release/ (or --out): BlackListDetect-<version>-full.zip, -update.zip, version.json and
version.json.sig. The update zip is checked against v1.0.1's own rules (updater._allowed, the marker,
MAX_SIZE) and the signature against the key the app trusts (updater.PUBLIC_KEY unless --public-key).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import struct
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from blacklist_detect import updater  # noqa: E402

FOLDER = updater.FOLDER
LAUNCHER = "模仿者小工具.exe"
APP_EXE = "runtime/模仿者小工具.exe"
GUIDE = "使用说明.txt"
MARKER = "blacklist_detect/__init__.py"
FILES_LIST = "blacklist_detect/files.txt"
ORT = "blacklist_detect/onnxruntime.dll"
OCR = "blacklist_detect/ocr"
ASSETS = "blacklist_detect/assets"
# The DLLs a clean Windows 10 has. The app's exe may import nothing else: the folder it runs from
# (runtime\) holds only the exe once the Python runtime is gone, and v1.0.1's updater cannot put a DLL
# there. So the C runtime is linked in (+crt-static), OpenCV statically, onnxruntime.dll loaded by path.
SYSTEM_DLLS = {
    "combase.dll",
    "advapi32.dll", "bcrypt.dll", "bcryptprimitives.dll", "comctl32.dll", "comdlg32.dll", "crypt32.dll",
    "d2d1.dll", "d3d11.dll", "d3d12.dll", "d3dcompiler_47.dll", "dwmapi.dll", "dwrite.dll", "dxgi.dll",
    "gdi32.dll", "gdiplus.dll", "imm32.dll", "kernel32.dll", "ntdll.dll", "ole32.dll", "oleaut32.dll",
    "opengl32.dll", "propsys.dll", "secur32.dll", "setupapi.dll", "shcore.dll", "shell32.dll", "shlwapi.dll",
    "user32.dll", "userenv.dll", "uxtheme.dll", "version.dll", "winmm.dll", "ws2_32.dll", "msimg32.dll",
    "windowscodecs.dll", "winhttp.dll", "wininet.dll", "mfplat.dll", "mfreadwrite.dll", "ksuser.dll",
    "avrt.dll", "mmdevapi.dll", "dbghelp.dll", "powrprof.dll", "iphlpapi.dll", "ncrypt.dll", "msvcrt.dll",
}


def pe_imports(data: bytes) -> list[str] | None:
    """The DLLs a Windows exe imports (lower case), or None when data is not a PE file."""
    if data[:2] != b"MZ" or len(data) < 64:
        return None
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe : pe + 4] != b"PE\0\0":
        return None
    sections, optional_size = struct.unpack_from("<H12xH", data, pe + 6)
    optional = pe + 24
    magic = struct.unpack_from("<H", data, optional)[0]
    directories = optional + (112 if magic == 0x20B else 96)
    import_rva = struct.unpack_from("<I", data, directories + 8)[0]
    table = optional + optional_size
    spans = [struct.unpack_from("<8xIIII", data, table + 40 * index) for index in range(sections)]

    def offset(rva: int) -> int:
        for size, address, raw_size, raw in spans:
            if address <= rva < address + max(size, raw_size):
                return rva - address + raw
        raise ValueError(f"RVA {rva:#x} outside every section")

    names = []
    at = offset(import_rva) if import_rva else None
    while at is not None:
        name_rva = struct.unpack_from("<I", data, at + 12)[0]
        if name_rva == 0:
            break
        start = offset(name_rva)
        names.append(data[start : data.index(b"\0", start)].decode("ascii").lower())
        at += 20
    return names


def foreign_imports(exe: Path) -> list[str] | None:
    """The DLLs exe imports that a clean Windows 10 does not have; None when exe is not a PE file."""
    names = pe_imports(exe.read_bytes())
    if names is None:
        return None
    return sorted(name for name in names if name not in SYSTEM_DLLS and not name.startswith(("api-ms-win-", "ext-ms-")))


def lay_out(stage: Path, args: argparse.Namespace) -> list[str]:
    """Copy the release into stage/BlackListDetect; returns the folder-relative files, sorted."""
    top = stage / FOLDER

    def put(rel: str, source: Path) -> None:
        target = top / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    put(APP_EXE, args.app_exe)
    put(ORT, args.onnxruntime)
    for model in sorted(path for path in args.models.iterdir() if path.is_dir()):
        for item in sorted(model.rglob("*")):
            if item.is_file():
                put(f"{OCR}/{model.name}/{item.relative_to(model).as_posix()}", item)
    if args.assets is not None:
        for item in sorted(args.assets.rglob("*")):
            if item.is_file():
                put(f"{ASSETS}/{item.relative_to(args.assets).as_posix()}", item)
    if args.launcher is not None:
        put(LAUNCHER, args.launcher)
    guide = (REPO / "build" / GUIDE).read_text(encoding="utf-8").replace("{version}", args.version)
    (top / GUIDE).write_text(guide, encoding="utf-8-sig", newline="\r\n")
    (top / MARKER).write_text(
        f'"""The Rust app\'s folder; v1.0.1\'s updater takes only an update that has this file."""\n'
        f'__version__ = "{args.version}"\n',
        encoding="utf-8",
    )
    files = sorted({path.relative_to(top).as_posix() for path in top.rglob("*") if path.is_file()} | {FILES_LIST})
    (top / FILES_LIST).write_text("\n".join(files) + "\n", encoding="utf-8")
    return files


def check_update(files: list[str]) -> None:
    """Every file of the update zip passes v1.0.1's updater._allowed, and the marker is there."""
    shipped = [rel for rel in files if rel != LAUNCHER]
    refused = [rel for rel in shipped if not updater._allowed(PurePosixPath(rel))]
    if refused:
        raise SystemExit(f"v1.0.1's updater would leave these out: {refused}")
    if MARKER not in shipped or APP_EXE not in shipped:
        raise SystemExit("The update lacks the marker or the app's exe.")


def write_zip(top: Path, files: list[str], target: Path) -> None:
    target.unlink(missing_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for rel in files:
            archive.write(top / rel, f"{FOLDER}/{rel}")


def sign(update: Path, args: argparse.Namespace) -> tuple[bytes, str]:
    """version.json for update, and its signature with the key at args.key."""
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    payload = update.read_bytes()
    manifest = {
        "version": args.version,
        "base": args.base,
        "notes": args.notes,
        "mirrors": [prefix for prefix in updater.MIRRORS if prefix],
        "update": {
            "url": f"{updater.DOWNLOADS}{args.version}/{update.name}",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
        },
    }
    data = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    key = load_pem_private_key(args.key.read_bytes(), password=None)
    signature = base64.b64encode(key.sign(data)).decode()
    if not updater.verify(data, signature, args.public_key):
        raise SystemExit("The key does not match the public key the app trusts; the app would refuse this release.")
    release = updater.read_manifest(data)
    if release.needs_full(args.base) or release.size > updater.MAX_SIZE:
        raise SystemExit("The update zip is too big for the app's updater, or base is wrong.")
    return data, signature


def parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", required=True, help="the Rust app's version, e.g. v2.0.0")
    parser.add_argument("--app-exe", type=Path, required=True)
    parser.add_argument("--onnxruntime", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True, help="one folder per model, each with inference.onnx")
    parser.add_argument("--assets", type=Path, help="pictures and sounds the app reads from disk")
    parser.add_argument("--launcher", type=Path, help="the launcher exe; without it no full zip is made")
    parser.add_argument("--base", default="v1.0.1", help="the oldest version the update zip may be laid over")
    parser.add_argument("--notes", nargs="*", help="update notes; default build/notes/<version>.txt")
    parser.add_argument("--key", type=Path, default=Path.home() / ".blacklist-detect" / "release-key.pem")
    parser.add_argument("--public-key", default=updater.PUBLIC_KEY, help="for tests only: a throwaway key's public half")
    parser.add_argument("--out", type=Path, default=REPO / "dist" / "release")
    parser.add_argument("--allow-non-pe", action="store_true", help="for tests on Linux: the app exe may be an ELF stand-in")
    args = parser.parse_args(argv)
    if args.notes is None:
        notes = REPO / "build" / "notes" / f"{args.version}.txt"
        args.notes = [line.strip() for line in notes.read_text(encoding="utf-8").splitlines() if line.strip()] if notes.is_file() else []
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse(argv)
    foreign = foreign_imports(args.app_exe)
    if foreign is None and not args.allow_non_pe:
        raise SystemExit(f"{args.app_exe} is not a Windows exe.")
    if foreign:
        raise SystemExit(f"The app exe imports DLLs a clean Windows 10 lacks: {foreign}")
    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        files = lay_out(Path(temp), args)
        check_update(files)
        top = Path(temp) / FOLDER
        update = args.out / f"{FOLDER}-{args.version}-update.zip"
        write_zip(top, [rel for rel in files if rel != LAUNCHER], update)
        if args.launcher is not None:
            write_zip(top, files, args.out / f"{FOLDER}-{args.version}-full.zip")
    data, signature = sign(update, args)
    (args.out / "version.json").write_bytes(data)
    (args.out / "version.json.sig").write_text(signature + "\n", encoding="ascii")
    print(f"{update.name}: {update.stat().st_size / 1e6:.1f} MB, {len(files)} files; signed version.json in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
