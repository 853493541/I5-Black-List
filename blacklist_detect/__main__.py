"""Run the window, or check one image without opening it."""

from __future__ import annotations

import logging
import sys


def main(argv: list[str] | None = None) -> int:
    from blacklist_detect.ocr_engine import silence_console_children

    silence_console_children()
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["check"]:
        return _check_cli(args[1:])
    if args[:1] == ["download-models"]:
        return _download_models()
    from blacklist_detect.autostart import BACKGROUND
    from blacklist_detect.ui import run_app

    code = run_app(background=BACKGROUND in args)
    _end(code)
    return code


def _end(code: int) -> None:
    """Leave now. By the time the window is gone everything is saved and closed, but PaddleOCR
    leaves threads behind that Python would wait on for ever: the app vanished from the screen
    and the tray, while its process stayed, holding its memory and blocking the next update.
    And os._exit still unloads the libraries, where PySide6 crashes: the process is ended outright."""
    from blacklist_detect.single import exit_now

    logging.shutdown()
    exit_now(code)


def _check_cli(args: list[str]) -> int:
    if len(args) != 1:
        print("用法: python -m blacklist_detect check <图片.png>", file=sys.stderr)
        return 2
    from blacklist_detect.pipeline import check_image
    from blacklist_detect.storage import Store

    store = Store()
    try:
        result = check_image(args[0], store.entries)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(result.message)
    for slot in result.names:
        if slot.unclear:
            state = "未识别"
        elif slot.truncated:
            state = "截断"
        else:
            state = "完整"
        print(f"{slot.index + 1:2d}  {state:4s}  {slot.confidence:0.2f}  {slot.raw}")
    for hit in result.hits:
        print(hit.line)
    return 0 if result.header_found else 1


def _download_models() -> int:
    from blacklist_detect.ocr_engine import OcrUnavailable, get_engine

    try:
        get_engine().warmup()
    except OcrUnavailable as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("PaddleOCR 中文模型已在本机可用。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
