"""Швидка структурна валідація папки тижневого випуску.

Викликається одразу після вибору папки в лаунчері (Рівень 3) — ще до
повного сканування контенту (яке читає ``.docx``-метрики і може бути
повільним на великому випуску). Перевіряє лише фундаментальні речі:

- чи папка взагалі існує;
- чи є обов'язкова підпапка ``FONTS`` зі шрифтами цього випуску (див.
  docs/content-structure.md) — якщо немає, це блокуюча помилка з чітким
  описом, як і де її створити;
- чи є хоч одна сторінкова підпапка (число, напр. ``01``);
- чи кожна сторінкова підпапка містить хоч один файл контенту (текст або
  фото) — порожня сторінка блокує наступні кроки, бо верстати нічого.

Усе інше (невпізнана підпапка, папка FONTS без жодного файлу шрифту) —
лише попередження, не блокує. Детальніші перевірки конвенції найменування
файлів (`{page}_{order}_{slug}`, дублікати order тощо) лишаються за повним
:func:`inkforge.content_checker.scanner.scan_issue`, який і так вже
викликається одразу після цієї швидкої перевірки.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .scanner import FONTS_FOLDER_NAME, IMAGE_EXTENSIONS, TEXT_EXTENSIONS, is_fonts_folder_name

if TYPE_CHECKING:
    from ..layout_engine.profile import NewspaperProfile

FONT_FILE_EXTENSIONS = (".ttf", ".otf", ".ttc")

_PAGE_FOLDER_PATTERN = re.compile(r"^\d+$")


@dataclass
class StructureValidation:
    """Результат швидкої структурної перевірки папки випуску."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pages_found: list[str] = field(default_factory=list)
    fonts_folder: str | None = None


def validate_issue_structure(
    root: Path, profile: "NewspaperProfile | None" = None
) -> StructureValidation:
    """Перевіряє фундаментальну структуру папки випуску ``root``.

    ``profile``, якщо переданий, дозволяє не вимагати контенту на
    сторінках, позначених у профілі як ``manual_pages`` (верстаються
    вручну, тому порожня папка для них — нормально, а не помилка).
    """

    root = Path(root)
    result = StructureValidation(valid=True)

    if not root.is_dir():
        result.valid = False
        result.errors.append(f"Папку випуску не знайдено: {root}")
        return result

    subfolders = [p for p in sorted(root.iterdir()) if p.is_dir()]

    fonts_dirs = [p for p in subfolders if is_fonts_folder_name(p.name)]
    if not fonts_dirs:
        result.valid = False
        result.errors.append(
            "Не знайдено папку зі шрифтами. Створіть підпапку "
            f"'{FONTS_FOLDER_NAME}' безпосередньо всередині папки випуску "
            f"(тобто {root / FONTS_FOLDER_NAME}) і покладіть туди файли "
            "шрифтів (.ttf/.otf/.ttc), потрібні для цього випуску."
        )
    else:
        fonts_dir = fonts_dirs[0]
        result.fonts_folder = str(fonts_dir)
        has_font_file = any(
            f.is_file() and f.suffix.lower() in FONT_FILE_EXTENSIONS
            for f in fonts_dir.rglob("*")
        )
        if not has_font_file:
            result.warnings.append(
                f"Папка '{fonts_dir.name}' існує, але не містить жодного "
                "файлу шрифту (.ttf/.otf/.ttc) — перевірте, чи туди справді "
                "покладено шрифти цього випуску."
            )

    page_folders = [p for p in subfolders if _PAGE_FOLDER_PATTERN.match(p.name)]
    if not page_folders:
        result.valid = False
        result.errors.append(
            "Не знайдено жодної сторінкової підпапки (наприклад '01', '02') "
            "безпосередньо всередині папки випуску."
        )

    recognized = set(fonts_dirs) | set(page_folders)
    for p in subfolders:
        if p in recognized:
            continue
        result.warnings.append(
            f"Непізнана підпапка '{p.name}' буде проігнорована (очікується "
            f"номер сторінки, наприклад '01', або папка '{FONTS_FOLDER_NAME}')."
        )

    for p in page_folders:
        page_num = int(p.name)
        result.pages_found.append(p.name)

        if profile is not None and profile.is_manual(page_num):
            continue  # ручна сторінка за профілем — контент не обов'язковий

        content_files = [
            f
            for f in p.iterdir()
            if f.is_file()
            and (f.suffix.lower() in TEXT_EXTENSIONS or f.suffix.lower() in IMAGE_EXTENSIONS)
        ]
        if not content_files:
            result.valid = False
            result.errors.append(
                f"Сторінка '{p.name}' порожня — немає жодного файлу статті "
                "(текст .docx/.doc/.txt або фото .jpg/.jpeg/.png/.tif/.tiff)."
            )

    return result
