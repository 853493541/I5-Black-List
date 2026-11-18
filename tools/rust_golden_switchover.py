"""Prove the switch-over: a v1.0.1 folder takes the Rust release through v1.0.1's own updater.

    python tools/rust_golden_switchover.py --probe rust/target/debug/examples/switchover_probe [--launcher 模仿者小工具.exe]

In a temp folder of its own (APPDATA, XDG_CONFIG_HOME and HOME point there): lays out a v1.0.1 install
(the app's code from the v1.0.1 tag, a stand-in Python runtime) and a data folder with made-up lists, makes
the Rust release with build/make_rust_release.py and a throwaway Ed25519 key, serves it over http.server,
and runs v1.0.1's updater.py (from the tag) to check, download and stage it, as the app does when a player
clicks 更新. Then the launcher lays it over and starts the app: the real launcher exe with --launcher (on
Windows), else a line-for-line port of its Apply/Restore (build/launcher/Launcher.cs). The app is
switchover_probe, which records how it was started and runs switchover::after_good_start.

Two runs: "good" (the app starts: the Rust files are in place, the Python ones gone, data untouched) and
"failed" (the app stops before confirming: the next launcher start puts v1.0.1 back byte for byte).
Exit status 0 when every check holds; the result is printed as JSON.
"""

from __future__ import annotations

import argparse
import base64
import functools
import hashlib
import http.server
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TAG = "v1.0.1"
VERSION = "v2.0.0"
LAUNCHER = "模仿者小工具.exe"
APP_EXE = "runtime/模仿者小工具.exe"
GITHUB = "https://github.com/"
# Made-up names only (CLAUDE.md): what a player's data folder holds.
DATA = {
    "blacklist.json": '{"names": ["示例坏人"]}',
    "settings.json": '{"theme": "light", "hotkey": "F8"}',
    "guests.json": '{"guests": [{"name": "心动小鹿", "scene": "星河许愿"}, {"name": "心动星星"}]}',
    "backups/blacklist-2026-11-01.json": '{"names": ["示例坏人"]}',
    "logs/app.log": "2026-11-17 20:00:00 started\n",
    "custom_sounds/alarm.wav": "RIFF....WAVE",
}

# v1.0.1's updater, run in a child Python with the tag's code first on its path.
UPDATE_STEP = r"""
import json, sys, requests
from pathlib import Path
from blacklist_detect import updater, __version__
updater.PUBLIC_KEY = sys.argv[1]
base, root, downloads = sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])

class Local(requests.Session):
    def request(self, method, url, *args, **kwargs):
        return super().request(method, url.replace("https://github.com/", base), *args, **kwargs)

release = updater.fetch_release(Local())
zip_path = updater.download(release, downloads, session=Local())
staged = updater.stage(zip_path, root, release.version)
print(json.dumps({"running": __version__, "offered": release.version, "needs_full": release.needs_full(),
                  "staged": updater.staged_version(root), "updater": updater.__file__}))
"""


def tree(root: Path, skip: tuple[str, ...] = ()) -> dict[str, str]:
    """Every file under root (relative path -> SHA-256), leaving out top-level names in skip."""
    out = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_file() and rel.split("/")[0] not in skip:
            out[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def v101_code(dest: Path) -> str:
    """The v1.0.1 tag's blacklist_detect/ into dest; returns where it came from."""
    archive = subprocess.run(["git", "archive", "--format=tar", TAG, "blacklist_detect"], cwd=REPO, capture_output=True)
    if archive.returncode != 0:
        raise SystemExit(f"No {TAG} tag here; run: git fetch origin tag {TAG} --no-tags")
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as bundle:
        bundle.extractall(dest, filter="data")
    return f"git archive {TAG}"


def make_release(work: Path, probe: Path, launcher: Path | None) -> str:
    """The Rust release with a throwaway key into work/server; returns the key's public half."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

    key = Ed25519PrivateKey.generate()
    pem = work / "throwaway-key.pem"
    pem.write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    public = base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    inputs = work / "inputs"
    for model in ("PP-OCRv5_mobile_det", "PP-OCRv6_medium_rec"):
        (inputs / "models" / model).mkdir(parents=True)
        (inputs / "models" / model / "inference.onnx").write_bytes(hashlib.sha256(model.encode()).digest() * 64)
        (inputs / "models" / model / "inference.yml").write_text(f"Global:\n  model_name: {model}\n", encoding="utf-8")
    (inputs / "onnxruntime.dll").write_bytes(b"MZ stand-in for onnxruntime")
    out = work / "release"
    command = [sys.executable, str(REPO / "build" / "make_rust_release.py"), "--version", VERSION, "--app-exe", str(probe),
               "--onnxruntime", str(inputs / "onnxruntime.dll"), "--models", str(inputs / "models"), "--key", str(pem),
               "--public-key", public, "--out", str(out), "--notes", "换成新版程序，更快更小"]
    if launcher is not None:
        command += ["--launcher", str(launcher)]
    if os.name != "nt":
        command.append("--allow-non-pe")
    subprocess.run(command, check=True)
    server = work / "server" / "853493541" / "I5-Black-List" / "releases"
    (server / "latest" / "download").mkdir(parents=True)
    (server / "download" / VERSION).mkdir(parents=True)
    for name in ("version.json", "version.json.sig"):
        shutil.copyfile(out / name, server / "latest" / "download" / name)
    update = out / f"BlackListDetect-{VERSION}-update.zip"
    shutil.copyfile(update, server / "download" / VERSION / update.name)
    return public


def install(base: Path, code: Path, launcher: Path | None) -> tuple[Path, Path]:
    """A v1.0.1 folder and a data folder under base."""
    root = base / "BlackListDetect"
    shutil.copytree(code / "blacklist_detect", root / "blacklist_detect")
    model = root / "blacklist_detect" / "models" / "PP-OCRv5_mobile_det"
    model.mkdir(parents=True)
    (model / "inference.pdiparams").write_bytes(b"paddle weights")
    if launcher is not None:
        shutil.copyfile(launcher, root / LAUNCHER)
    else:
        (root / LAUNCHER).write_bytes(b"MZ v1.0.1 launcher")
    for rel, text in {APP_EXE: "MZ pythonw with the app's icon", "runtime/python311.dll": "python",
                      "runtime/Lib/site-packages/PySide6/Qt6Core.dll": "qt", "runtime/vcruntime140.dll": "crt",
                      "使用说明.txt": "v1.0.1 guide"}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    data = base / "AppData" / "BlackListDetect"
    for rel, text in DATA.items():
        (data / rel).parent.mkdir(parents=True, exist_ok=True)
        (data / rel).write_text(text, encoding="utf-8")
    return root, data


def apply(root: Path) -> None:
    """Launcher.cs Updates.Apply, line for line."""
    staged, backup, pending = root / "update.new", root / "update.old", root / "update.check"
    shutil.rmtree(backup, ignore_errors=True)
    backup.mkdir()
    marker = staged / ".version"
    version = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    marker.unlink(missing_ok=True)
    pending.write_text(version, encoding="utf-8")
    for file in sorted(path for path in staged.rglob("*") if path.is_file()):
        rel = file.relative_to(staged)
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            (backup / rel).parent.mkdir(parents=True, exist_ok=True)
            target.rename(backup / rel)
        else:
            with open(backup / ".added", "a", encoding="utf-8") as added:
                added.write(str(rel) + "\n")
        file.rename(target)
    shutil.rmtree(staged)


def restore(root: Path) -> None:
    """Launcher.cs Updates.Restore, line for line."""
    backup, pending = root / "update.old", root / "update.check"
    if backup.is_dir():
        added = backup / ".added"
        if added.is_file():
            for rel in added.read_text(encoding="utf-8").splitlines():
                if rel.strip() and (root / rel.strip()).is_file():
                    (root / rel.strip()).unlink()
            added.unlink()
        for file in sorted(path for path in backup.rglob("*") if path.is_file()):
            rel = file.relative_to(backup)
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target.replace(Path(str(target) + ".failed"))
            file.rename(target)
        shutil.rmtree(backup)
    pending.unlink(missing_ok=True)


def launch(root: Path, env: dict, real: bool, apply_only: bool = False) -> int:
    """One start of the launcher: lay over or roll back, then start runtime\\模仿者小工具.exe -m blacklist_detect."""
    if real:
        result = subprocess.run([str(root / LAUNCHER)] + (["--apply-only"] if apply_only else []), env=env, timeout=120)
        return result.returncode
    if (root / "update.new").is_dir():
        apply(root)
    elif (root / "update.check").exists():
        restore(root)
        if apply_only:
            return 2
    if apply_only:
        return 0
    exe = root / APP_EXE
    exe.chmod(0o755)  # zipfile drops the exec bit; Windows has none
    child = dict(env, PYTHONPATH=str(root), PYTHONNOUSERSITE="1", PYTHONUTF8="1")
    return subprocess.run([str(exe), "-m", "blacklist_detect"], cwd=root, env=child, timeout=60).returncode


def wait_probe(root: Path, budget: float = 60) -> dict:
    """probe.json once the app wrote it (the real launcher does not wait for the app); at most budget s."""
    end = time.monotonic() + budget
    while time.monotonic() < end:
        try:
            return json.loads((root / "probe.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            time.sleep(0.5)
    raise SystemExit(f"The app never wrote probe.json in {budget} s")


def run(name: str, work: Path, code: Path, public: str, base_url: str, launcher: Path | None, fail: bool) -> dict:
    base = work / name
    root, data = install(base, code, launcher)
    before_root, before_data = tree(root), tree(data)
    env = dict(os.environ, APPDATA=str(base / "AppData"), XDG_CONFIG_HOME=str(base / "AppData"), HOME=str(base / "home"))
    env.pop("BLACKLIST_DETECT_SOUND", None)
    if fail:
        env["SWITCHOVER_PROBE_FAIL"] = "1"
    step = subprocess.run([sys.executable, "-c", UPDATE_STEP, public, base_url, str(root), str(base / "downloads")],
                          env=dict(env, PYTHONPATH=str(code), PYTHONDONTWRITEBYTECODE="1"), cwd=base,
                          capture_output=True, text=True, timeout=120)
    if step.returncode != 0:
        raise SystemExit(f"v1.0.1's updater failed:\n{step.stderr}")
    result = {"updater": json.loads(step.stdout), "launcher": "real exe" if launcher else "Launcher.cs port"}
    launch(root, env, launcher is not None)
    result["probe"] = probe = wait_probe(root)
    checks = {
        "updater_is_v101": result["updater"]["running"] == TAG and result["updater"]["updater"].startswith(str(code)),
        "offered_without_full_download": result["updater"]["offered"] == VERSION and not result["updater"]["needs_full"],
        "launcher_started_rust_exe": Path(probe["exe"]).resolve() == (root / APP_EXE).resolve(),
        "launcher_args_dropped": probe["raw_args"][:2] == ["-m", "blacklist_detect"] and probe["args"] == [],
        "launcher_unchanged": tree(root).get(LAUNCHER) == before_root[LAUNCHER],
    }
    if not fail:
        listed = (root / "blacklist_detect" / "files.txt").read_text(encoding="utf-8").split()
        after = tree(root, skip=("update.result", "probe.json"))
        checks |= {
            "confirmed": probe["confirmed"] and not (root / "update.check").exists() and not (root / "update.old").exists(),
            "only_release_files_left": set(after) == {*listed, "使用说明.txt", LAUNCHER},
            "python_runtime_gone": not (root / "runtime" / "Lib").exists() and not (root / "runtime" / "python311.dll").exists(),
        }
        result["deleted"] = probe["deleted"]
    else:
        code_rc = launch(root, env, launcher is not None, apply_only=True)
        checks |= {
            "rolled_back_message": code_rc == 2,
            # Launcher.cs moves the new version's files aside as <name>.failed rather than deleting them.
            "v101_back_byte_for_byte": {rel: digest for rel, digest in tree(root, skip=("update.result", "probe.json")).items()
                                        if not rel.endswith(".failed")} == before_root,
        }
        result["left_aside"] = sorted(rel for rel in tree(root) if rel.endswith(".failed"))
    result["data_files"] = len(before_data)
    after_data = tree(data)
    after_data.pop("mirrors.json", None)  # v1.0.1's updater remembers the route that worked; not ours
    checks["data_untouched"] = after_data == before_data
    result["checks"] = checks
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--probe", type=Path, required=True, help="the switchover_probe example binary")
    parser.add_argument("--launcher", type=Path, help="the real launcher exe (Windows only)")
    parser.add_argument("--keep", type=Path, help="work in this folder and keep it")
    args = parser.parse_args()
    work = args.keep or Path(tempfile.mkdtemp(prefix="switchover-"))
    work.mkdir(parents=True, exist_ok=True)
    code = work / "v1.0.1"
    source = v101_code(code)
    public = make_release(work, args.probe.resolve(), args.launcher)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(work / "server"))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}/"
    try:
        report = {"v101_code": source, "release_zip_bytes": next((work / "release").glob("*-update.zip")).stat().st_size,
                  "good": run("good", work, code, public, base_url, args.launcher, fail=False),
                  "failed": run("failed", work, code, public, base_url, args.launcher, fail=True)}
    finally:
        server.shutdown()
        if args.keep is None:
            shutil.rmtree(work, ignore_errors=True)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    bad = [f"{run_name}.{check}" for run_name in ("good", "failed") for check, ok in report[run_name]["checks"].items() if not ok]
    print("FAILED: " + ", ".join(bad) if bad else "All checks hold.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
