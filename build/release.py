"""Publish a release on GitHub that the app can update itself from.

Once, on the PC that publishes:
    python build/release.py keygen
        Makes the release key in %USERPROFILE%\\.blacklist-detect\\release-key.pem and writes its
        public half into blacklist_detect/updater.py. Keep a copy of that file somewhere safe:
        without it no later release is accepted by the copies friends already have.

For each release, after build/make_release.py has made the zips:
    python build/release.py sign       writes dist/release/version.json and version.json.sig
    python build/release.py publish    creates the GitHub release with the update zip and those two
    python build/release.py check      asks GitHub the way the app does, and shows what it gets
    python build/release.py check --each   the same through GitHub and each proxy, one by one

What is new goes in build/notes/<version>.txt, one line per change, in the words friends read.
build/release.json holds "base": the oldest version the update zip can be laid over. Raise it
to the new version when the runtime or the models change; those copies are sent to the full zip.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from blacklist_detect import __version__, updater  # noqa: E402
from blacklist_detect.names import APP_NAME  # noqa: E402

KEY = Path.home() / ".blacklist-detect" / "release-key.pem"
OUT = REPO / "dist" / "release"
NOTES = REPO / "build" / "notes"
SETTINGS = REPO / "build" / "release.json"
UPDATER = REPO / "blacklist_detect" / "updater.py"


def _zip(kind: str) -> Path:
    return OUT / f"{updater.FOLDER}-{__version__}-{kind}.zip"


def _notes() -> list[str]:
    path = NOTES / f"{__version__}.txt"
    if not path.is_file():
        raise SystemExit(f"Write what is new in {path.relative_to(REPO)} first, one line per change.")
    lines = [line.strip().lstrip("-·•* ").strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line]


def _private_key():  # noqa: ANN202
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    if not KEY.is_file():
        raise SystemExit(f"No release key at {KEY}. Run: python build/release.py keygen")
    return load_pem_private_key(KEY.read_bytes(), password=None)


def keygen(_args: argparse.Namespace) -> int:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

    if KEY.exists():
        raise SystemExit(f"A release key already exists at {KEY}. It is kept: copies friends have trust it.")
    private = Ed25519PrivateKey.generate()
    KEY.parent.mkdir(parents=True, exist_ok=True)
    KEY.write_bytes(private.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    public = base64.b64encode(private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    source = UPDATER.read_text(encoding="utf-8")
    source, count = re.subn(r'^PUBLIC_KEY = ".*"$', f'PUBLIC_KEY = "{public}"', source, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit("Could not find PUBLIC_KEY in blacklist_detect/updater.py")
    UPDATER.write_text(source, encoding="utf-8")
    print(f"Release key: {KEY}")
    print(f"Public key written into {UPDATER.relative_to(REPO)}: {public}")
    print("Keep a copy of the key file somewhere safe (a USB stick, a password manager). Never commit it.")
    return 0


def sign(_args: argparse.Namespace) -> int:
    update = _zip("update")
    if not update.is_file():
        raise SystemExit(f"{update.relative_to(REPO)} is missing. Run: python build/make_release.py")
    base = json.loads(SETTINGS.read_text(encoding="utf-8"))["base"]
    payload = update.read_bytes()
    manifest = {
        "version": __version__,
        "base": base,
        "notes": _notes(),
        # The proxies copies of this version try when GitHub is cut off; change them in updater.MIRRORS.
        "mirrors": [prefix for prefix in updater.MIRRORS if prefix],
        "update": {
            "url": f"{updater.DOWNLOADS}{__version__}/{update.name}",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
        },
    }
    data = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    signature = base64.b64encode(_private_key().sign(data)).decode()
    if not updater.verify(data, signature):
        raise SystemExit("The key does not match PUBLIC_KEY in blacklist_detect/updater.py; the app would refuse this release.")
    updater.read_manifest(data)
    (OUT / "version.json").write_bytes(data)
    (OUT / "version.json.sig").write_text(signature + "\n", encoding="ascii")
    print(data.decode("utf-8"))
    print(f"Signed: {(OUT / 'version.json.sig').relative_to(REPO)}")
    return 0


def _gh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", check=check)


def publish(args: argparse.Namespace) -> int:
    assets = [_zip("update"), OUT / "version.json", OUT / "version.json.sig"]
    if args.with_full:
        assets.append(_zip("full"))
    missing = [path.name for path in assets if not path.is_file()]
    if missing:
        raise SystemExit(f"Missing: {', '.join(missing)}. Run make_release.py, then release.py sign.")
    if json.loads((OUT / "version.json").read_text(encoding="utf-8"))["version"] != __version__:
        raise SystemExit("version.json is for another version. Run: python build/release.py sign")
    if _gh("release", "view", __version__, "--repo", updater.REPO, check=False).returncode == 0:
        raise SystemExit(f"{__version__} is already published. Raise __version__ for a new release.")
    notes = OUT / "release-notes.md"
    lines = ["**更新内容**", "", *(f"- {line}" for line in _notes())]
    lines += [
        "",
        "**安装与更新**",
        "",
        "- 已安装 v0.4.0 及以上：打开程序，按提示更新",
        f"- 更早版本：下载 {_zip('update').name}，解压覆盖原文件夹",
        f"- 首次安装：下载 {_zip('full').name}，解压后运行「模仿者小工具.exe」",
    ]
    if args.with_full:
        # From mainland China the GitHub link is often cut off: the same file through a proxy.
        direct = f"{updater.DOWNLOADS}{__version__}/{_zip('full').name}"
        lines += ["", "**国内下载**（GitHub 打不开时）", ""]
        lines += [f"- {prefix}{direct}" for prefix in [prefix for prefix in updater.MIRRORS if prefix][:2]]
    notes.write_text("\n".join(lines) + "\n", encoding="utf-8")
    command = [
        "release", "create", __version__,
        "--repo", updater.REPO,
        "--target", args.target,
        "--title", f"{APP_NAME} {__version__}",
        "--notes-file", str(notes),
        *(str(path) for path in assets),
    ]  # fmt: skip
    print("gh " + " ".join(command))
    if args.dry_run:
        return 0
    done = _gh(*command, check=False)
    print(done.stdout + done.stderr)
    return done.returncode


def check(args: argparse.Namespace) -> int:
    """Ask GitHub what the app would be offered, as a copy two versions back.

    With --each, ask GitHub and every proxy on its own, and fetch the update zip through each:
    a proxy passes only when version.json carries the release key's signature and the zip matches.
    """
    import os
    import tempfile

    # The app remembers the address that worked beside its settings; not in this PC's real ones.
    os.environ["APPDATA"] = os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()
    ways = list(updater.MIRRORS) if args.each else [None]
    failed = 0
    for prefix in ways:
        if prefix is not None:
            updater.MIRRORS = (prefix,)
        name = "GitHub" if not prefix else prefix
        try:
            release = updater.fetch_release(current="v0.0.0")
            if release is not None and args.each:
                with tempfile.TemporaryDirectory() as folder:
                    updater.download(release, Path(folder))
        except updater.UpdateError as error:
            print(f"{name}: the app would say: {error}")
            failed += 1
            continue
        if release is None:
            print(f"{name}: no release with version.json yet.")
            failed += 1
            continue
        if args.each:
            print(f"{name}: OK, {release.version}, signature and zip checked")
            continue
        print(f"The app would offer {release.version} ({release.size / 1e6:.2f} MB), for copies from {release.base} on:")
        for line in release.notes:
            print(f"  · {line}")
    return 1 if failed == len(ways) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    steps = parser.add_subparsers(dest="step", required=True)
    steps.add_parser("keygen", help="make the release key, once").set_defaults(run=keygen)
    steps.add_parser("sign", help="write and sign version.json").set_defaults(run=sign)
    out = steps.add_parser("publish", help="create the GitHub release")
    out.add_argument("--target", default="main", help="branch the release tag points at")
    out.add_argument("--with-full", action="store_true", help="also attach the full zip (about 316 MB)")
    out.add_argument("--dry-run", action="store_true", help="show the gh command without running it")
    out.set_defaults(run=publish)
    asked = steps.add_parser("check", help="see what the app would be offered")
    asked.add_argument("--each", action="store_true", help="try GitHub and every proxy one by one")
    asked.set_defaults(run=check)
    args = parser.parse_args()
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
