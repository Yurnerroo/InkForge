"""Точка входу `inkforge-launcher`: піднімає локальний веб-застосунок Рівня 3
і одразу відкриває його в браузері."""

from __future__ import annotations

import argparse
import threading
import webbrowser

import uvicorn

from .app import app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="inkforge-launcher",
        description="Запускає локальний One-Click Launcher (Рівень 3) у браузері.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Не відкривати браузер автоматично",
    )
    args = parser.parse_args(argv)

    url = f"http://{args.host}:{args.port}/"
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()

    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
