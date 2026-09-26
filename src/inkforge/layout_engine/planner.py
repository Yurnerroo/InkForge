"""Build a Level 2 layout plan from a Level 1 manifest + a newspaper profile.

This is a *planning* step only: it decides which manifest pages are
automatable per the newspaper's profile, and computes a first-pass
proportional space distribution for their articles. It never touches
InDesign -- see ``extendscript/inkforge_layout.jsx`` for the (still partial)
executor that would eventually consume this plan's JSON output.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
    sub_order: int = 0
    # Only set for newspapers with a profile.page1_layout special page (MIF
    # page 1 currently): "main" or "storm_forecast" -- tells the ExtendScript
    # executor which fixed frame to route this article into instead of the
    # generic geometric-cluster matching used elsewhere.
    role: str = ""
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
    page1_layout: dict[str, str] | None = None
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
        page1_layout=asdict(profile.page1_layout) if profile.page1_layout is not None else None,
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

    if profile.page1_layout is not None and page_num == 1:
        return _plan_page1_special(page_num, articles_raw, profile, color_mode, notes)

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
            sub_order=article.get("sub_order", 0) or 0,
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


def _plan_page1_special(
    page_num: int,
    articles_raw: list[dict[str, Any]],
    profile: NewspaperProfile,
    color_mode: str | None,
    notes: list[str],
) -> PagePlan:
    """Plan MIF's page 1: role-based assignment into fixed IDML frames instead
    of the generic geometric-cluster distribution used for pages 2-7.

    Rules confirmed by the layout artist (see profiles/mif.yaml,
    ``page1_layout``):
      - The longest article on the page (excluding the storm-forecast match
        below) is "main" -- it always gets the large photo on the left.
      - The article whose title/body contains ``storm_forecast_keyword``
        (case-insensitive) is "прогноз магнітних бур" -- it goes into a
        fixed frame that already has a colored background in the template.
      - "Народні прикмети" is intentionally NOT assigned a role here (see
        profiles/mif.yaml notes) -- it stays a manual addition for now.
    """

    layout = profile.page1_layout
    assert layout is not None  # guarded by the caller
    keyword = layout.storm_forecast_keyword.lower()

    storm_candidates = []
    remaining = []
    for article in articles_raw:
        haystack = f"{article.get('title') or ''} {article.get('body') or ''}".lower()
        if keyword in haystack:
            storm_candidates.append(article)
        else:
            remaining.append(article)

    page1_notes = list(notes)
    storm_article: dict[str, Any] | None = None
    if len(storm_candidates) == 1:
        storm_article = storm_candidates[0]
    elif len(storm_candidates) > 1:
        page1_notes.append(
            f"Знайдено {len(storm_candidates)} статей із ключовим словом "
            f"'{layout.storm_forecast_keyword}' — неоднозначно, роль "
            "'storm_forecast' не призначено жодній, потребує ручної перевірки"
        )
        remaining = list(articles_raw)  # ambiguous: consider all for 'main' instead
    else:
        page1_notes.append(
            f"Не знайдено статті з ключовим словом '{layout.storm_forecast_keyword}' "
            "для прогнозу магнітних бур — роль 'storm_forecast' не призначено"
        )

    main_article: dict[str, Any] | None = None
    if remaining:
        main_article = max(remaining, key=lambda a: max(a.get("char_count", 0) or 0, 0))
    else:
        page1_notes.append("Немає статей для ролі 'main' (головна стаття) на сторінці 1")

    total_words = sum(max(article.get("word_count", 0) or 0, 0) for article in articles_raw) or 1
    articles: list[ArticlePlan] = []
    for article in articles_raw:
        role = ""
        if main_article is not None and article is main_article:
            role = "main"
        elif storm_article is not None and article is storm_article:
            role = "storm_forecast"
        articles.append(
            ArticlePlan(
                article_id=article["article_id"],
                order=article["order"],
                slug=article["slug"],
                word_count=max(article.get("word_count", 0) or 0, 0),
                has_image=article.get("image") is not None,
                text_share=round(max(article.get("word_count", 0) or 0, 0) / total_words, 4),
                image_color_mode=color_mode,
                sub_order=article.get("sub_order", 0) or 0,
                role=role,
                text_path=article.get("text_path"),
                image_path=article.get("image_path"),
                title=article.get("title") or "",
                lead=article.get("lead") or "",
                body=article.get("body") or "",
            )
        )

    return PagePlan(
        page=page_num,
        status="planned_page1_special",
        color_mode=color_mode,
        articles=articles,
        notes=page1_notes,
    )


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
