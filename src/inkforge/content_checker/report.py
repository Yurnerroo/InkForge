"""Render a human-readable report of a scanned issue."""

from __future__ import annotations

from .models import IssueContent


def render_report(issue: IssueContent) -> str:
    """Build a plain-text summary suitable for console/GUI display."""

    lines: list[str] = []
    title = issue.newspaper or issue.root.name
    lines.append(f"Перевірка контенту: {title}")
    lines.append(f"Папка: {issue.root}")
    lines.append("")

    if not issue.pages:
        lines.append("Сторінкових папок не знайдено.")
    else:
        for page in issue.pages:
            article_count = len(page.articles)
            lines.append(
                f"Сторінка {page.page}: {article_count} {_pluralize_articles(article_count)}, "
                f"{page.total_word_count} слів"
            )

    warnings = issue.all_warnings
    lines.append("")
    if warnings:
        lines.append(f"Знайдено попереджень: {len(warnings)}")
        for warning in warnings:
            lines.append(f"  ⚠ {warning}")
    else:
        lines.append("Попереджень не знайдено — контент готовий до верстки.")

    return "\n".join(lines)


def _pluralize_articles(count: int) -> str:
    """Ukrainian plural form of "стаття" (article) for ``count``."""

    if count % 10 == 1 and count % 100 != 11:
        return "стаття"
    if 2 <= count % 10 <= 4 and not (11 <= count % 100 <= 14):
        return "статті"
    return "статей"
