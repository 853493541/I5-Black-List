"""Golden data for the Rust port of updater.py and logs.py: runs the Python code on a set of cases and
saves what it says under rust/data/tests/golden/update/, for the Rust tests to give the same.

    uv run --python 3.12 --with cryptography --with requests tools/rust_golden_update.py

(3.12 is the release runtime: its base64 decoding differs from 3.13 at the edges.)

Runs offline, in a folder of its own: version comparison, version.json reading and its signature, the
choice of address (mirrors.json), a whole fetch through fake pages, restarts, and the log's lines,
rotation and account hiding."""

from __future__ import annotations

import base64
import json
import logging
import logging.handlers
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["TZ"] = "UTC"
time.tzset()

import requests  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat  # noqa: E402

from blacklist_detect import diagnostics, logs, updater  # noqa: E402

OUT = ROOT / "rust" / "data" / "tests" / "golden" / "update"
REAL = (OUT / "version.json").read_bytes()
REAL_SIG = (OUT / "version.json.sig").read_text(encoding="utf-8")
PRIVATE = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
PUBLIC = base64.b64encode(PRIVATE.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
D = updater.DOWNLOADS


def sign(data: bytes) -> str:
    return base64.b64encode(PRIVATE.sign(data)).decode()


def manifest(version="v9.0.0", base="v0.1.0", size=3, sha="a" * 64, url="", **extra) -> str:  # noqa: ANN001, ANN003
    data = {"version": version, "base": base, "notes": ["嘉宾列表"], "update": {"url": url or f"{D}{version}/x.zip", "sha256": sha, "size": size}}
    data.update(extra)
    return json.dumps(data, ensure_ascii=False)


VERSIONS = ["v0.10.0", "v0.9.9", "0.4.0", "dev", "V1.2", "vv1.0", " v1.0.1 ", "1._0", "1_0.2", "+1.-2", "1..2", "", "v", "1.0a",
            "１.0", "99999999999.1", "v1.0.1\n", "\u30001.0"]
GOOD = ["", "https://gh-proxy.org/", "https://a.b:8080/x/y/", "http://plain.example/", "https://x.example/a b/", "https://x/",
        "javascript:alert(1)//", "https://x.example", "https://x.example//", "https://:80/", "https://x:/", "https://x.example/a/b",
        "https://ex.com/~a._-/", "https://" + "a" * 190 + "/", "https://" + "a" * 200 + "/", "HTTPS://x/", "https://x_y/"]
MIRROR_FILES = [None, "", "{", "[]", '["preferred"]', '"preferred"', "3", "{}", '{"preferred": ""}',
                '{"preferred": "https://ghproxy.net/"}', '{"preferred": "https://new.example/", "listed": ["https://new.example/"]}',
                '{"preferred": "https://not-listed.example/"}', '{"listed": ["https://a.example/", "bad", "https://gh-proxy.org/"]}',
                '{"preferred": 3, "listed": "ab"}', '{"preferred": null, "listed": null}', '{"listed": {"https://k.example/": 1}}',
                '{"preferred": "https://wget.la/", "listed": [1, "https://b.example/"]}', '{"preferred": true}']
MANIFESTS = [manifest(), manifest(url="https://example.com/x.zip"), "{not json", "[]", manifest(size=0), manifest(size=100_000_001),
             manifest(sha="A" * 64), manifest(sha="a" * 63), manifest(version="dev"), manifest(size="12"), manifest(size=5.9),
             manifest(size=True), manifest(size=None), manifest(version=1.5), manifest(notes="ab"), manifest(notes=3),
             manifest(mirrors=["https://new.example/", "http://plain/", "x"]), manifest(base=None),
             json.dumps({"version": "v2.0", "update": {"url": D + "a", "sha256": "b" * 64, "size": " 7 "}}),
             json.dumps({"version": "v2.0", "update": []}), REAL.decode("utf-8")]


def verify_cases() -> list[dict]:
    sig = REAL_SIG
    tampered = REAL.replace(b"9101938", b"9101939")
    flipped = ("A" if sig[0] != "A" else "B") + sig[1:]
    cases = [(REAL, sig, None), (tampered, sig, None), (REAL + b"\n", sig, None), (REAL, flipped, None), (REAL, sig.strip()[:-2], None),
             (REAL, " \n" + sig[:10] + "!*\n" + sig[10:], None), (REAL, sig.strip() + "AAAA", None), (REAL, sig.strip() + "==AAAA", None),
             (REAL, "not base64!", None), (REAL, "", None), (REAL, sig, ""), (REAL, sig, PUBLIC), (REAL, sign(REAL), PUBLIC),
             (REAL, sign(REAL), None), (REAL, sig + "\u3000", None), (REAL, "é" + sig, None), (REAL, sig, PUBLIC[:-4])]
    return [{"manifest": m.decode("utf-8"), "signature": s, "key": k, "ok": updater.verify(m, s, k)} for m, s, k in cases]


class FakeSession:
    def __init__(self, pages: dict) -> None:
        self.pages, self.asked = pages, []

    def get(self, url: str, **_kw):  # noqa: ANN003, ANN201
        self.asked.append(url)
        page = self.pages.get(url, {"status": 404, "body": ""})
        if page == "error":
            raise requests.ConnectionError("cut off")
        response = requests.Response()
        response.status_code, response._content, response.encoding = page["status"], page["body"].encode("utf-8"), "utf-8"
        return response


def fetch_cases(folder: Path) -> list[dict]:
    m = manifest(mirrors=["https://new.example/"])
    ok = {"status": 200, "body": m}
    sig = {"status": 200, "body": sign(m.encode())}
    gh, px, px2 = updater.MANIFEST_URL, updater.MIRRORS[2] + updater.MANIFEST_URL, updater.MIRRORS[1] + updater.MANIFEST_URL
    bad = {"status": 200, "body": m.replace("v0.1.0", "v0.0.1")}
    scenarios = [
        ("found", {gh: ok, gh + ".sig": sig}, "v0.3.0", None),
        ("same version", {gh: ok, gh + ".sig": sig}, "v9.0.0", None),
        ("nothing published", {}, "v0.3.0", None),
        ("forged", {gh: ok, gh + ".sig": {"status": 200, "body": sign(b"other")}}, "v0.3.0", None),
        ("github cut off", {gh: "error", gh + ".sig": "error", px: ok, px + ".sig": sig}, "v0.3.0", None),
        ("proxy changes it", {gh: "error", px2: bad, px2 + ".sig": sig, px: ok, px + ".sig": sig}, "v0.3.0", None),
        ("all blocked", {u + gh: "error" for u in updater.MIRRORS}, "v0.3.0", None),
        ("server error", {gh: {"status": 500, "body": ""}}, "v0.3.0", None),
        ("sig missing", {gh: ok}, "v0.3.0", None),
        ("remembered first", {px: ok, px + ".sig": sig}, "v0.3.0", '{"preferred": "https://ghproxy.net/", "listed": []}'),
        ("signed but unreadable", {gh: {"status": 200, "body": "[]"}, gh + ".sig": {"status": 200, "body": sign(b"[]")}}, "v0.3.0", None),
    ]
    out = []
    for name, pages, current, before in scenarios:
        path = folder / updater.MIRROR_FILE
        path.unlink(missing_ok=True)
        if before is not None:
            path.write_text(before, encoding="utf-8")
        session = FakeSession(pages)
        try:
            release = updater.fetch_release(session, current=current)
            result = None if release is None else {"version": release.version, "mirror": release.mirror, "mirrors": list(release.mirrors)}
            error = None
        except updater.UpdateError as failure:
            result, error = None, str(failure)
        after = path.read_text(encoding="utf-8") if path.exists() else None
        out.append({"name": name, "pages": pages, "current": current, "before": before, "release": result, "error": error,
                    "asked": session.asked, "after": after})
    return out


def log_cases(folder: Path) -> dict:
    form = logs._Format()
    lines = []
    for created, msecs, level, thread, message in [(1760377403, 317, "INFO", "MainThread", "Check 12 (hotkey): lobby found"),
                                                   (0, 5, "WARNING", "update-check", "a\nb\n  c"), (1760377403, 999, "CRITICAL", "", "x"),
                                                   (1760377403, 0, "ERROR", "Thread-12 (worker)", "错误 示***"), (1, 1, "INFO", "watchdog", "")]:
        record = logging.makeLogRecord({"created": created, "msecs": msecs, "levelname": level, "threadName": thread or None, "msg": message})
        lines.append({"created": created, "msecs": msecs, "level": level, "thread": thread, "message": message, "line": form.format(record)})
    rot = folder / "rot" / "app.log"
    rot.parent.mkdir()
    handler = logging.handlers.RotatingFileHandler(rot, maxBytes=200, backupCount=4, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(message)s"))
    written = [("第%d行 " % i) * (i % 7) + "x" * (i * 13 % 50) for i in range(60)] + ["y" * 300, "z"]
    for text in written:
        handler.emit(logging.makeLogRecord({"msg": text}))
    handler.close()
    files = {p.name: p.read_text(encoding="utf-8") for p in sorted(rot.parent.iterdir())}
    users = [("C:\\Users\\Zhangsan", "Zhangsan"), ("C:\\Users\\张三", "张三"), ("C:\\Users\\ab", "ab"), ("", "")]
    texts = ["at C:\\Users\\Zhangsan\\AppData\\x.py and C:/Users/Zhangsan/y and Zhangsan alone", "C:\\Users\\张三\\桌面 张三", "ab C:\\Users\\ab"]
    hidden = [{"home": h, "user": u, "text": t, "out": _without(t, h, u)} for h, u in users for t in texts]
    dumps = []
    for home, user in [("C:/Users/Zhangsan", "Zhangsan"), ("C:/Users/张三", "张三"), ("C:/Users/x", "")]:
        data = "C:\\Users\\zhangSAN\\a.dll C:/users/张三/b USERS\\Zhangsanx".encode("utf-8")
        data += "C:\\Users\\ZhangSan\\c.dll|C:/Users/张三/d".encode("utf-16-le")
        dumps.append({"home": home, "user": user, "data": data.hex(), "out": _dump_without(data, home, user).hex()})
    return {"lines": lines, "rotation": {"max_bytes": 200, "backups": 4, "written": written, "files": files},
            "masked": {name: logs.masked(name) for name in ["示例坏人", "a", "", "心动小鹿🦌"]}, "hidden": hidden, "dumps": dumps}


def _without(text: str, home: str, user: str) -> str:
    saved = os.path.expanduser, os.environ.get("USERNAME")
    os.path.expanduser, os.environ["USERNAME"] = (lambda _p: home), user
    try:
        return diagnostics._without_user(text)
    finally:
        os.path.expanduser = saved[0]
        os.environ["USERNAME"] = saved[1] or ""


def _dump_without(data: bytes, home: str, user: str) -> bytes:
    saved = os.path.expanduser, os.environ.get("USERNAME")
    os.path.expanduser, os.environ["USERNAME"] = (lambda _p: home), user
    try:
        return diagnostics._dump_without_user(data)
    finally:
        os.path.expanduser = saved[0]
        os.environ["USERNAME"] = saved[1] or ""


def restart_cases(folder: Path) -> list[dict]:
    # Floats, as time.time() gives in the app.
    steps = [("v9.0.0", 1000.0), ("v9.0.0", 1010.0), ("v9.0.0", 1020.25), ("v9.0.1", 1030.0), ("v9.0.0", 1630.0), ("v9.0.0", 1731940000.123456)]
    out = []
    for version, now in steps:
        ok = updater.note_restart(folder, version, now=now)
        out.append({"version": version, "now": now, "ok": ok, "file": (folder / updater.TRIES).read_text(encoding="utf-8")})
    return out


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        updater._mirror_file = lambda: folder / updater.MIRROR_FILE
        updater.PUBLIC_KEY_REAL = updater.PUBLIC_KEY
        mirrors = []
        for text in MIRROR_FILES:
            (folder / updater.MIRROR_FILE).unlink(missing_ok=True)
            if text is not None:
                (folder / updater.MIRROR_FILE).write_text(text, encoding="utf-8")
            mirrors.append({"file": text, "order": updater.mirrors()})
        remember = []
        for before, preferred, listed in [(None, "", []), ('{"listed": ["https://a.example/", "x", ""]}', "https://ghproxy.net/", []),
                                          ('{"listed": "ab"}', "", []), ("[1]", "", []), (None, "https://wget.la/", ["https://n.example/", "bad"])]:
            (folder / updater.MIRROR_FILE).unlink(missing_ok=True)
            if before is not None:
                (folder / updater.MIRROR_FILE).write_text(before, encoding="utf-8")
            updater._remember(preferred, tuple(listed))
            remember.append({"before": before, "preferred": preferred, "listed": listed,
                             "after": (folder / updater.MIRROR_FILE).read_text(encoding="utf-8")})
        manifests = []
        for text in MANIFESTS:
            try:
                r = updater.read_manifest(text.encode("utf-8"))
                manifests.append({"text": text, "release": {"version": r.version, "url": r.url, "sha256": r.sha256, "size": r.size,
                                                            "base": r.base, "notes": list(r.notes), "mirrors": list(r.mirrors)}})
            except updater.UpdateError as error:
                manifests.append({"text": text, "error": str(error)})
        real_verify = verify_cases()
        updater.PUBLIC_KEY = PUBLIC
        fetch = fetch_cases(folder)
        (folder / "restart").mkdir()
        golden = {"public": PUBLIC, "versions": {text: list(updater.parse_version(text)) for text in VERSIONS},
                  "good_mirror": {text: updater._good_mirror(text) for text in GOOD}, "mirrors": mirrors, "remember": remember,
                  "manifests": manifests, "verify": real_verify, "fetch": fetch, "restarts": restart_cases(folder / "restart"),
                  "logs": log_cases(folder)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "golden.json").write_text(json.dumps(golden, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT / 'golden.json'}")


if __name__ == "__main__":
    main()
