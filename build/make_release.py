"""Make the two release zips from an assembled runtime.

    python build/make_release.py

The source runtime is copied, never changed. Files the app never loads are left
out of the copy (see the rules below). The copy is then run once with its own
Python against the reference lobby, and is zipped only if it still reads the
same twelve names.

Output in dist/release/:
    BlackListDetect-<version>-full.zip    first install: runtime, models, app
    BlackListDetect-<version>-update.zip  later versions: the app code only

The top folder is ASCII on purpose. Paddle cannot open model files under a
path with Chinese characters, so a 黑名单检测 folder breaks every check.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FOLDER = "BlackListDetect"
EXE_NAME = "黑名单检测.exe"

# Whole packages nothing imports during a window open, a lobby check, or a title glance.
# dxcam and comtypes: capture is a GDI BitBlt in capture.py. The rest come in with
# PaddleX for features this app does not use (downloads, PDF, graph tools).
DROP_PACKAGES = {
    "pip": "pip-",
    "dxcam": "dxcam-",
    "comtypes": "comtypes-",
    "networkx": "networkx-",
    "hf_xet": "hf_xet-",
    "Crypto": "pycryptodome-",
    "baidubce": "bce_python_sdk-",
    "future": "future-",
    "past": None,
    "libfuturize": None,
    "libpasteurize": None,
    "fsspec": "fsspec-",
}

# PySide6 is the full Qt. The app uses widgets, plus QtNetwork's local socket so only one copy runs.
PYSIDE_KEEP_FILES = {
    "__init__.py",
    "_config.py",
    "_git_pyside_version.py",
    "py.typed",
    "PySide6_Essentials.json",
    "PySide6_Addons.json",
    "pyside6.abi3.dll",
    "Qt6Core.dll",
    "Qt6Gui.dll",
    "Qt6Widgets.dll",
    "Qt6Network.dll",
    "Qt6Svg.dll",
    "QtCore.pyd",
    "QtGui.pyd",
    "QtWidgets.pyd",
    "QtNetwork.pyd",
    "QtSvg.pyd",
    "concrt140.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "msvcp140_codecvt_ids.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "vccorlib140.dll",
    "vcomp140.dll",
    "vcamp140.dll",
}
PYSIDE_KEEP_DIRS = {"support", "plugins", "__pycache__"}
PYSIDE_KEEP_PLUGINS = {"platforms", "styles", "imageformats", "iconengines"}

# PaddleX imports modelscope only for its download helpers (hub, utils). The model,
# training, and dataset code is unused here, and it holds the deepest paths in the
# bundle (200 characters), which break unzipping under a long folder on Windows.
MODELSCOPE_DROP_DIRS = {
    "cli",
    "exporters",
    "metrics",
    "models",
    "msdatasets",
    "ops",
    "outputs",
    "pipelines",
    "preprocessors",
    "server",
    "tools",
    "trainers",
}
# The deepest path allowed inside the release folder. Unpacked under a folder up
# to about 90 characters long, that stays inside Windows' 260-character limit.
MAX_INNER_PATH = 170

# Never loaded at run time: tests, C headers, import libraries, type stubs,
# OpenCV's video codec and face-detection data.
DROP_DIR_NAMES = {"tests"}
DROP_FILE_GLOBS = ("*.lib", "*.h", "*.hpp", "*.pyi", "opencv_videoio_ffmpeg*.dll")


class Pruner:
    def __init__(self, site: Path) -> None:
        self.site = site
        self.dropped: dict[str, int] = {}

    def _note(self, rule: str, path: Path) -> None:
        if path.is_dir():
            size = sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
        else:
            size = path.stat().st_size
        self.dropped[rule] = self.dropped.get(rule, 0) + size

    def _rule(self, path: Path) -> str | None:
        name = path.name
        if path.parent.name == "runtime" and name == "Scripts":
            return "runtime/Scripts (pip launchers)"
        try:
            rel = path.relative_to(self.site)
        except ValueError:
            return None
        parts = rel.parts
        if not parts:
            return None
        if len(parts) == 1:
            if name in DROP_PACKAGES:
                return f"package {name}"
            for prefix in DROP_PACKAGES.values():
                if prefix and name.startswith(prefix) and name.endswith(".dist-info"):
                    return f"package {prefix.rstrip('-')}"
        if parts[0] == "PySide6" and len(parts) == 2:
            if path.is_dir() and name not in PYSIDE_KEEP_DIRS:
                return "PySide6 unused Qt modules"
            if path.is_file() and name not in PYSIDE_KEEP_FILES:
                return "PySide6 unused Qt modules"
        if parts[:2] == ("PySide6", "plugins") and len(parts) == 3 and name not in PYSIDE_KEEP_PLUGINS:
            return "PySide6 unused Qt plugins"
        if parts[0] == "modelscope" and len(parts) == 2 and path.is_dir() and name in MODELSCOPE_DROP_DIRS:
            return "modelscope model and training code"
        if parts[:2] == ("cv2", "data") and name.endswith(".xml"):
            return "OpenCV face-detection data"
        if path.is_dir() and name in DROP_DIR_NAMES:
            return "test suites"
        if path.is_dir() and name == "include" and not any(path.rglob("*.py")):
            return "C headers"
        if path.is_file():
            for pattern in DROP_FILE_GLOBS:
                if fnmatch.fnmatch(name, pattern):
                    return "headers, stubs, import libs, video codec"
        return None

    def ignore(self, directory: str, names: list[str]) -> set[str]:
        skipped: set[str] = set()
        for name in names:
            path = Path(directory) / name
            rule = self._rule(path)
            if rule:
                self._note(rule, path)
                skipped.add(name)
        return skipped


def _expected_names() -> list[list]:
    """The reference lobby read, from the repo's own test, without importing it."""
    source = (REPO / "tests" / "test_reference_screenshot.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "EXPECTED" for t in node.targets):
            return [list(item) for item in ast.literal_eval(node.value)]
    raise SystemExit("EXPECTED not found in tests/test_reference_screenshot.py")


def _version() -> str:
    source = (REPO / "blacklist_detect" / "__init__.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "__version__" for t in node.targets):
            return str(ast.literal_eval(node.value)).replace(" ", "-")
    return "dev"


def _size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _verify(stage: Path) -> None:
    runtime_python = stage / "runtime" / "python.exe"
    with tempfile.TemporaryDirectory() as scratch:
        report = Path(scratch) / "report.json"
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("PYTHON", "QT_", "BLACKLIST_DETECT"))
        }
        env.update(
            {
                "APPDATA": str(Path(scratch) / "appdata"),
                "PYTHONNOUSERSITE": "1",
                "PYTHONUTF8": "1",
                "QT_QPA_PLATFORM": "windows",
            }
        )
        subprocess.run(
            [str(runtime_python), str(REPO / "build" / "verify_bundle.py"), str(REPO / "tests" / "fixtures" / "reference-lobby.png"), str(report)],
            cwd=stage,
            env=env,
            check=True,
            timeout=900,
        )
        data = json.loads(report.read_text(encoding="utf-8"))
    problems: list[str] = []
    if data["names"] != _expected_names():
        problems.append(f"names differ: {data['names']}")
    if not data["header"] or not data["glance"]:
        problems.append("lobby title not found")
    if data["hits"] != ["gffdsd"]:
        problems.append(f"hits differ: {data['hits']}")
    if not data.get("single_instance"):
        problems.append("a second copy could not reach the first (QtNetwork)")
    if data["platform"] != "windows" or not data["icon"]:
        problems.append(f"Qt platform {data['platform']!r}, icon loaded {data['icon']}")
    root = str(stage).lower()
    for path in data["modules"] + data["dlls"]:
        lowered = path.lower()
        if "site-packages" in lowered and not lowered.startswith(root):
            problems.append(f"loaded from outside the bundle: {path}")
    if problems:
        raise SystemExit("Release check failed:\n  " + "\n  ".join(problems))
    print(f"Verified: 12 names match, Qt style {data['style']}, all modules from the bundle.")


def _zip(source: Path, target: Path, include) -> None:
    target.unlink(missing_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob("*")):
            rel = path.relative_to(source.parent)
            if path.is_file() and include(path.relative_to(source)):
                archive.write(path, rel.as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runtime", type=Path, default=REPO / "dist" / "黑名单检测" / "runtime",
                        help="assembled embeddable Python with the app's packages installed")
    parser.add_argument("--models", type=Path, default=REPO / "dist" / "黑名单检测" / "blacklist_detect" / "models",
                        help="folder with PP-OCRv5_mobile_det, PP-OCRv5_mobile_rec, PP-OCRv6_medium_rec")
    parser.add_argument("--launcher", type=Path, default=REPO / "dist" / "exe" / EXE_NAME,
                        help="launcher exe built from launcher.py (see build/launcher.spec)")
    parser.add_argument("--out", type=Path, default=REPO / "dist" / "release")
    parser.add_argument("--skip-verify", action="store_true")
    args = parser.parse_args()

    for path in (args.runtime / "python.exe", args.models, args.launcher):
        if not path.exists():
            raise SystemExit(f"missing {path}")

    stage = args.out / FOLDER
    if stage.exists():
        shutil.rmtree(stage)
    args.out.mkdir(parents=True, exist_ok=True)

    pruner = Pruner(args.runtime / "Lib" / "site-packages")
    print(f"Copying runtime from {args.runtime} ...")
    shutil.copytree(args.runtime, stage / "runtime", ignore=pruner.ignore)
    shutil.copytree(
        REPO / "blacklist_detect",
        stage / "blacklist_detect",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "models"),
    )
    shutil.copytree(args.models, stage / "blacklist_detect" / "models")
    shutil.copy2(args.launcher, stage / EXE_NAME)

    print("Left out of the runtime:")
    for rule, size in sorted(pruner.dropped.items(), key=lambda item: -item[1]):
        print(f"  {size / 1e6:8.1f} MB  {rule}")
    print(f"  {sum(pruner.dropped.values()) / 1e6:8.1f} MB  total")

    too_long = [
        rel
        for rel in (path.relative_to(args.out).as_posix() for path in stage.rglob("*"))
        if len(rel) > MAX_INNER_PATH
    ]
    if too_long:
        listed = "\n  ".join(sorted(too_long, key=len, reverse=True)[:10])
        raise SystemExit(f"{len(too_long)} paths are longer than {MAX_INNER_PATH} characters:\n  {listed}")

    if not args.skip_verify:
        _verify(stage)

    version = _version()
    full = args.out / f"{FOLDER}-{version}-full.zip"
    update = args.out / f"{FOLDER}-{version}-update.zip"
    print("Zipping ...")
    _zip(stage, full, lambda rel: True)
    _zip(
        stage,
        update,
        lambda rel: rel.parts[0] == "blacklist_detect" and "models" not in rel.parts,
    )
    print(f"Folder: {_size(stage) / 1e6:.0f} MB unpacked (source runtime {_size(args.runtime) / 1e6:.0f} MB)")
    print(f"  {full.name}: {full.stat().st_size / 1e6:.1f} MB")
    print(f"  {update.name}: {update.stat().st_size / 1e3:.0f} KB (unzip over the old folder)")
    seven = _seven_zip()
    if seven is None:
        print("7-Zip not found, so no .7z or self-extracting .exe was made.")
        return 0
    packed = args.out / f"{FOLDER}-{version}-full.7z"
    sfx = args.out / f"{FOLDER}-{version}-full.exe"
    print("Packing with 7-Zip ...")
    packed.unlink(missing_ok=True)
    subprocess.run(
        [str(seven), "a", "-t7z", "-mx=9", "-m0=LZMA2", "-md=256m", "-mmt=on", "-bso0", "-bsp0", str(packed), FOLDER],
        cwd=args.out,
        check=True,
    )
    # 7z.sfx in front of the archive is a plain self-extractor. It asks where to unpack.
    with open(sfx, "wb") as handle:
        handle.write((seven.parent / "7z.sfx").read_bytes())
        with open(packed, "rb") as source:
            shutil.copyfileobj(source, handle)
    print(f"  {packed.name}: {packed.stat().st_size / 1e6:.1f} MB (needs 7-Zip, Bandizip, or WinRAR)")
    print(f"  {sfx.name}: {sfx.stat().st_size / 1e6:.1f} MB (double-click to unpack, nothing to install)")
    return 0


def _seven_zip() -> Path | None:
    for candidate in (
        shutil.which("7z"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "7-Zip", "7z.exe"),
    ):
        if candidate and Path(candidate).is_file() and (Path(candidate).parent / "7z.sfx").is_file():
            return Path(candidate)
    return None


if __name__ == "__main__":
    sys.exit(main())
