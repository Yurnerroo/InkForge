"""Обчислення шляху до друк-PDF за узгодженою конвенцією найменування, у
виділеній підпапці ``export_results`` папки випуску:

    {newspaper_type}_{week_number}({total_publishes})_{export_numeration}.pdf

наприклад ``MIF_10(125)_1.pdf`` — той самий формат, яким верстальниця й так
називає готові випуски вручну (``newspaper_type`` — код газети з
``layout_plan.json``/профілю, ``week_number`` — номер випуску цього тижня,
``total_publishes`` — наскрізний номер від заснування газети).
``export_numeration`` починається з 1 і автоматично інкрементується для
кожного нового експорту цього самого випуску, щоб повторний експорт (напр.
після додаткового ручного доправлення) не перезаписував попередній файл
мовчки -- верстальниця може порівняти кілька спроб між собою.
"""

from __future__ import annotations

import re
from pathlib import Path

EXPORT_RESULTS_DIR_NAME = "export_results"


def build_export_base_name(newspaper_type: str, week_number: str, total_publishes: str) -> str:
    return f"{newspaper_type}_{week_number}({total_publishes})"


def next_export_pdf_path(
    issue_folder: Path,
    newspaper_type: str,
    week_number: str,
    total_publishes: str,
) -> Path:
    """Повертає наступний вільний шлях у ``{issue_folder}/export_results/``
    за конвенцією найменування; створює цю підпапку, якщо її ще немає."""

    export_dir = Path(issue_folder) / EXPORT_RESULTS_DIR_NAME
    base_name = build_export_base_name(newspaper_type, week_number, total_publishes)
    pattern = re.compile(r"^" + re.escape(base_name) + r"_(\d+)\.pdf$", re.IGNORECASE)

    existing_max = 0
    if export_dir.is_dir():
        for path in export_dir.iterdir():
            match = pattern.match(path.name)
            if match:
                existing_max = max(existing_max, int(match.group(1)))

    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir / f"{base_name}_{existing_max + 1}.pdf"
