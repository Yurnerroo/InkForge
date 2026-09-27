"""Автоматичне копіювання файлів шрифтів (.ttf/.otf/.ttc) із центральної
папки користувача (напр. ``FONTS``, де назбирані всі шрифти всіх газет за
всі роки) у папку ``Document Fonts`` поруч із ``.indd``-файлом випуску.

InDesign автоматично підхоплює шрифти з ``Document Fonts`` без встановлення
в систему (стандартна конвенція самої програми, підтверджена верстальницею).
Це вирішує реальний випадок MIF_10(125): шрифт ``UkrainianXeniaExtended``
не був встановлений на машині й InDesign мовчки підмінив його на
``Everest-Demi`` -- верстальниця побачила попередження, але просто натиснула
"OK", не звернувши уваги. Якщо потрібний файл вже лежить у ``Document
Fonts`` до відкриття документа, підміни не станеться взагалі.

Зіставлення "назва шрифту з профілю" -> "файл шрифту" робиться приблизно
(без урахування регістру, пробілів, дефісів і підкреслень), бо реальні імена
файлів шрифтів рідко співпадають побайтово з назвою шрифту в InDesign
(напр. назва ``UkrainianXeniaExtended`` -- файл
``UKRAINIANXENIAEXTENDED.ttf``). Якщо для шрифту знайдено кілька файлів
(різні накреслення тощо), береться перший знайдений -- керуй іменуванням
файлів у папці ``FONTS``, якщо потрібна точність."""

from __future__ import annotations

import shutil
from pathlib import Path

FONT_FILE_EXTENSIONS = (".ttf", ".otf", ".ttc")

DOCUMENT_FONTS_DIR_NAME = "Document Fonts"


def _normalize_font_name(name: str) -> str:
    """Прибирає регістр, пробіли, дефіси й підкреслення для нежорсткого
    зіставлення назви шрифту з іменем файлу."""

    return "".join(ch for ch in name.lower() if ch.isalnum())


def index_font_files(fonts_folder: Path) -> dict[str, Path]:
    """Рекурсивно індексує файли шрифтів у ``fonts_folder`` за нормалізованим
    іменем (без розширення). Повертає порожній словник, якщо папки не існує."""

    fonts_folder = Path(fonts_folder)
    index: dict[str, Path] = {}
    if not fonts_folder.is_dir():
        return index

    for path in sorted(fonts_folder.rglob("*")):
        if path.is_file() and path.suffix.lower() in FONT_FILE_EXTENSIONS:
            key = _normalize_font_name(path.stem)
            index.setdefault(key, path)
    return index


def provision_missing_fonts(
    font_names: list[str], fonts_folder: Path, indd_path: Path
) -> dict[str, list[str]]:
    """Копіює файли шрифтів для ``font_names`` із ``fonts_folder`` у
    ``Document Fonts`` поруч із ``indd_path``.

    Повертає ``{"copied": [...], "not_found": [...]}`` -- список назв
    шрифтів, для яких вдалося/не вдалося знайти відповідний файл. Нічого не
    кидає при відсутньому файлі шрифту -- це очікуваний випадок (не кожен
    шрифт із профілю обов'язково має файл у папці користувача), лише
    звітується для показу в UI.
    """

    indd_path = Path(indd_path)
    doc_fonts_dir = indd_path.parent / DOCUMENT_FONTS_DIR_NAME
    index = index_font_files(Path(fonts_folder))

    copied: list[str] = []
    not_found: list[str] = []
    for name in font_names:
        src = index.get(_normalize_font_name(name))
        if src is None:
            not_found.append(name)
            continue

        doc_fonts_dir.mkdir(parents=True, exist_ok=True)
        dest = doc_fonts_dir / src.name
        if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
            shutil.copy2(src, dest)
        copied.append(name)

    return {"copied": copied, "not_found": not_found}
