"""Рівень 3 — One-Click Launcher: локальний FastAPI-застосунок, що керує
Рівнями 1-2 (Content Checker, layout planner) і, за наявності InDesign,
запускає ExtendScript-виконавець через COM. Див. docs/architecture.md,
розділ "Рівень 3".
"""

from .app import create_app

__all__ = ["create_app"]
