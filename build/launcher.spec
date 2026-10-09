# -*- mode: python ; coding: utf-8 -*-
# The small 黑名单检测.exe that starts runtime\pythonw.exe -m blacklist_detect.
# Build from the repo root:
#   pyinstaller build/launcher.spec --distpath dist/exe --workpath dist/pyi
# The exe holds no app code, so it only needs rebuilding when launcher.py changes.

from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="黑名单检测",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(ROOT / "blacklist_detect" / "assets" / "app.ico")],
)
