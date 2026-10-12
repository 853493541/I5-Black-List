"""Build 模仿者小工具.exe, the launcher, with the C# compiler that comes with Windows.

    python build/build_launcher.py

The launcher only starts runtime\\模仿者小工具.exe -m blacklist_detect (see build/launcher/Launcher.cs).
In C# it is about 10 KB; it was 8 MB as a PyInstaller exe, which carried a whole Python of its own.
It needs .NET Framework 4.8, which is part of Windows 10 and 11, so a friend installs nothing.

Output: dist/exe/模仿者小工具.exe, with the app's icon, name, and version.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "build" / "launcher" / "Launcher.cs"
ICON = REPO / "blacklist_detect" / "assets" / "app.ico"
OUT = REPO / "dist" / "exe" / "模仿者小工具.exe"


def compiler() -> Path:
    windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
    for framework in ("Framework64", "Framework"):
        csc = windows / "Microsoft.NET" / framework / "v4.0.30319" / "csc.exe"
        if csc.is_file():
            return csc
    raise SystemExit("The C# compiler of .NET Framework 4 (csc.exe) was not found.")


def version() -> str:
    sys.path.insert(0, str(REPO))
    from blacklist_detect import __version__

    numbers = [part for part in __version__.lstrip("v").split(".") if part.isdigit()]
    return ".".join((numbers + ["0", "0", "0", "0"])[:4])


def build(out: Path = OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        # The name, description and version Windows shows for the exe.
        info = Path(scratch) / "AssemblyInfo.cs"
        info.write_text(
            "using System.Reflection;\n"
            '[assembly: AssemblyTitle("模仿者小工具")]\n'
            '[assembly: AssemblyProduct("模仿者小工具")]\n'
            f'[assembly: AssemblyVersion("{version()}")]\n'
            f'[assembly: AssemblyFileVersion("{version()}")]\n',
            encoding="utf-8-sig",
        )
        # Built under an ASCII name, then moved into place: the compiler is old.
        built = Path(scratch) / "launcher.exe"
        done = subprocess.run(
            [
                str(compiler()),
                "/nologo",
                "/codepage:65001",
                "/target:winexe",
                "/optimize+",
                "/platform:anycpu",
                f"/win32icon:{ICON}",
                f"/out:{built}",
                str(SOURCE),
                str(info),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if done.returncode != 0 or not built.is_file():
            raise SystemExit(f"The launcher did not build:\n{done.stdout}{done.stderr}")
        out.unlink(missing_ok=True)
        out.write_bytes(built.read_bytes())
    return out


if __name__ == "__main__":
    path = build()
    print(f"{path} ({path.stat().st_size / 1024:.0f} KB)")
