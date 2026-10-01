"""Copy the display with DXGI Desktop Duplication. Windows only.

The copy is the whole output, so borderless, windowed, and exclusive
fullscreen all come through the same path. This module never looks up a
game window, never reads process memory, and never sends a click or a key.
"""

from __future__ import annotations

import sys
import time


class CaptureUnavailable(RuntimeError):
    """DXGI Desktop Duplication cannot run on this machine."""


def capture_capability_message() -> str:
    if sys.platform != "win32":
        return (
            "这台系统没有 DXGI Desktop Duplication，不能复制显示器。"
            "全局热键在这里也不会截屏。用「打开截图」检查一张图片。"
        )
    try:
        import dxcam  # noqa: F401
    except ImportError:
        return "未安装 dxcam，不能用 DXGI 复制显示器。用「打开截图」检查一张图片。"
    return "热键和「立即检查」会复制每台显示器，并检查有这间大厅的那一屏。"


def capture_displays() -> list:
    """Return one RGB uint8 frame per attached output. Raises CaptureUnavailable."""
    if sys.platform != "win32":
        raise CaptureUnavailable(capture_capability_message())
    try:
        import dxcam
    except ImportError as exc:
        raise CaptureUnavailable(
            "未安装 dxcam，不能用 DXGI Desktop Duplication 复制显示器。"
        ) from exc

    frames = []
    first_error = ""
    for output_idx in range(8):
        camera = None
        try:
            camera = dxcam.create(output_idx=output_idx, output_color="RGB")
        except Exception as exc:
            if output_idx == 0 and not frames:
                first_error = str(exc)
            break
        if camera is None:
            break
        try:
            frame = None
            for _attempt in range(5):
                frame = camera.grab()
                if frame is not None:
                    break
                time.sleep(0.02)
            if frame is not None:
                frames.append(frame)
        finally:
            release = getattr(camera, "release", None)
            if callable(release):
                try:
                    release()
                except Exception:
                    pass
    if not frames:
        detail = first_error or "没有拿到画面"
        raise CaptureUnavailable(f"DXGI 复制失败：{detail}")
    return frames
