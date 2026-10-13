"""Writes build/修复更新.bat: double-click to close every copy of 模仿者小工具 (stuck ones too) and open it
again, so a waiting update goes in. ASCII only inside, so no code page can garble it; the Chinese
message is built from character codes. FIX_MATCH (for testing) narrows which folders count."""

import sys
from pathlib import Path

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("修复更新.bat")


def chars(text: str) -> str:
    return "+".join(f"[char]{ord(c)}" for c in text)


done = chars("已关闭模仿者小工具，正在重新打开。更新会自动装好。")
none = chars("没有找到正在运行的模仿者小工具。请直接打开它。")
title = chars("修复更新")
script = (
    "$m = if ($env:FIX_MATCH) { $env:FIX_MATCH } else { '*\\BlackListDetect\\*' }; "
    "$ps = Get-Process | Where-Object { $_.Path -and ($_.Path -like $m) }; "
    "Add-Type -AssemblyName System.Windows.Forms; "
    f"$t = ''+{title}; "
    "if (-not $ps) { "
    f"if (-not $env:FIX_QUIET) {{ [System.Windows.Forms.MessageBox]::Show(''+{none}, $t) | Out-Null }}; exit }}; "
    "$roots = @($ps | ForEach-Object { $d = Split-Path $_.Path; if ((Split-Path $d -Leaf) -eq 'runtime') { Split-Path $d } else { $d } } | Sort-Object -Unique); "
    "$ps | Stop-Process -Force -ErrorAction SilentlyContinue; "
    "Get-Process WerFault -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue; "
    "Start-Sleep -Seconds 2; "
    f"if (-not $env:FIX_QUIET) {{ [System.Windows.Forms.MessageBox]::Show(''+{done}, $t) | Out-Null }}; "
    "foreach ($r in $roots) { $l = Get-ChildItem -LiteralPath $r -Filter *.exe | Select-Object -First 1; "
    "if ($l) { Start-Process -FilePath $l.FullName -WorkingDirectory $r } }"
)
assert all(ord(c) < 128 for c in script)
header = (
    "@echo off\r\n"
    "rem Fixes a stuck update of the app: ends every copy running from a BlackListDetect folder,\r\n"
    "rem stuck ones too, then opens the app again so the waiting update goes in. For friends on\r\n"
    "rem v0.8.1 or older; v0.8.2 and later end a stuck copy by themselves. Made by build/make_fix_bat.py.\r\n"
)
bat = header + "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command \"" + script.replace('"', '\\"') + "\"\r\n"
out.write_bytes(bat.encode("ascii"))
print(out, len(bat))
