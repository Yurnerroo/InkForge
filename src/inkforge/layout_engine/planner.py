"""Build a Level 2 layout plan from a Level 1 manifest + a newspaper profile.

This is a *planning* step only: it decides which manifest pages are
automatable per the newspaper's profile, and computes a first-pass
proportional space distribution for their articles. It never touches
InDesign -- see ``extendscript/inkforge_layout.jsx`` for the (still partial)
executor that would eventually consume this plan's JSON output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .profile import NewspaperProfile

# Allowed horizontal-scale bounds per docs/architecture.md (Рівень 2, крок 3):
# text may only be nudged via Horizontal Scale 97-102% and tracking, never a
# free/arbitrary scale. Recorded here so the (future) ExtendScript executor
# and any future auto-fit logic share the same constant instead of
# re-guessing it.
MIN_HORIZONTAL_SCALE = 97
MAX_HORIZONTAL_SCALE = 102


@dataclass
class ArticlePlan:
    """One article assigned to a page, with a first-pass space share."""

    article_id: str
    order: int
    slug: str
    word_count: int
    has_image: bool
    text_share: float
    image_color_mode: str | None
    text_path: str | None = None
    image_path: str | None = None
    title: str = ""
    lead: str = ""
    body: str = ""


@dataclass
class PagePlan:
    """The plan for one page of the issue."""

    page: int
    status: str
    color_mode: str | None
    articles: list[ArticlePlan] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class LayoutPlan:
    """The full plan for one issue, self-contained for the ExtendScript executor."""

    newspaper_id: str
    display_name: str
    root: str
    cmyk_profile: str | None = None
    fonts_installed: list[str] = field(default_factory=list)
    fonts_substituted: list[str] = field(default_factory=list)
    paragraph_style_roles: dict[str, str] | str | None = None
    character_size_roles: dict[str, Any] | str | None = None
    headline_font_alternation: dict[str, Any] | None = None
    min_horizontal_scale: int = MIN_HORIZONTAL_SCALE
    max_horizontal_scale: int = MAX_HORIZONTAL_SCALE
    pages: list[PagePlan] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_layout_plan(manifest: dict[str, Any], profile: NewspaperProfile) -> LayoutPlan:
    """Combine a Level 1 ``manifest`` dict with a ``profile`` into a LayoutPlan."""

    plan = LayoutPlan(
        newspaper_id=profile.id,
        display_name=profile.display_name,
        root=manifest.get("root", ""),
        cmyk_profile=profile.cmyk_profile,
        fonts_installed=list(profile.fonts_installed),
        fonts_substituted=list(profile.fonts_substituted),
        paragraph_style_roles=profile.paragraph_style_roles,
        character_size_roles=profile.character_size_roles,
        headline_font_alternation=profile.headline_font_alternation,
    )

    seen_pages: set[int] = set()

    for page_entry in manifest.get("pages", []):
        page_num = _parse_page_number(page_entry.get("page"))
        if page_num is None:
            plan.warnings.append(
                f"Не вдалося розпізнати номер сторінки '{page_entry.get('page')}' — пропущено"
            )
            continue
        seen_pages.add(page_num)
        plan.pages.append(_plan_for_page(page_num, page_entry, profile))

    _check_missing_automatable_pages(plan, profile, seen_pages)
    plan.pages.sort(key=lambda page_plan: page_plan.page)

    return plan


def _plan_for_page(
    page_num: int, page_entry: dict[str, Any], profile: NewspaperProfile
) -> PagePlan:
    if page_num < 1 or page_num > profile.page_count:
        return PagePlan(
            page=page_num,
            status="out_of_range",
            color_mode=None,
            notes=[f"Сторінка виходить за межі профілю (page_count={profile.page_count})"],
        )

    if profile.is_manual(page_num):
        return PagePlan(
            page=page_num,
            status="manual",
            color_mode=None,
            notes=["Ручна сторінка за профілем — не автоматизується"],
        )

    if profile.is_uncertain(page_num):
        return PagePlan(
            page=page_num,
            status="manual_uncertain",
            color_mode=None,
            notes=[
                "Статус сторінки не підтверджено — за замовчуванням не "
                "автоматизується, потребує уточнення у верстальниці"
            ],
        )

    special = profile.special_page_for(page_num)
    if special is not None and special.automation == "none":
        return PagePlan(
            page=page_num,
            status="special",
            color_mode=None,
            notes=[f"Спеціальна сторінка ({special.description.strip()}) — не автоматизується"],
        )

    color_mode = profile.color_mode_for_page(page_num)
    notes = []
    if color_mode is None:
        notes.append("Не знайдено розворот у профілі — колірний режим невідомий")

    articles_raw = page_entry.get("articles") or []
    if not articles_raw:
        return PagePlan(
            page=page_num,
            status="empty",
            color_mode=color_mode,
            notes=notes + ["Немає статей у маніфесті для автоматизованої сторінки"],
        )

    total_words = sum(max(article.get("word_count", 0) or 0, 0) for article in articles_raw) or 1
    articles = [
        ArticlePlan(
            article_id=article["article_id"],
            order=article["order"],
            slug=article["slug"],
            word_count=max(article.get("word_count", 0) or 0, 0),
            has_image=article.get("image") is not None,
            text_share=round(max(article.get("word_count", 0) or 0, 0) / total_words, 4),
            image_color_mode=color_mode,
            text_path=article.get("text_path"),
            image_path=article.get("image_path"),
            title=article.get("title") or "",
            lead=article.get("lead") or "",
            body=article.get("body") or "",
        )
        for article in articles_raw
    ]
    notes.append(
        "text_share — початковий пропорційний розподіл за обсягом слів; "
        "потребує уточнення після отримання точної геометрії фреймів"
    )

    return PagePlan(page=page_num, status="planned", color_mode=color_mode, articles=articles, notes=notes)


def _parse_page_number(raw: Any) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _check_missing_automatable_pages(
    plan: LayoutPlan, profile: NewspaperProfile, seen_pages: set[int]
) -> None:
    """Warn about automatable pages the profile expects but the manifest lacks."""

    for page_num in range(1, profile.page_count + 1):
        if page_num in seen_pages:
            continue
        if profile.is_manual(page_num) or profile.is_uncertain(page_num):
            continue
        special = profile.special_page_for(page_num)
        if special is not None and special.automation == "none":
            continue
        plan.warnings.append(
            f"Сторінка {page_num} має бути автоматизованою за профілем, "
            "але відсутня в маніфесті"
        )
