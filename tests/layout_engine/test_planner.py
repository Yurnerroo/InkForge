"""Tests for inkforge.layout_engine.planner."""

from __future__ import annotations

from typing import Any

from inkforge.layout_engine.planner import build_layout_plan
from inkforge.layout_engine.profile import NewspaperProfile, PhotoLinks, Spread, SpecialPage


def _make_profile(**overrides: Any) -> NewspaperProfile:
    defaults: dict[str, Any] = dict(
        id="test_gazeta",
        display_name="Test Gazeta",
        page_count=6,
        manual_pages=[1, 6],
        manual_pages_uncertain=[],
        spreads=[
            Spread(pages=[2, 3], color_mode="grayscale"),
            Spread(pages=[4, 5], color_mode="cmyk"),
        ],
        color_alternation_pattern="n/a",
        cmyk_profile=None,
        photo_links=PhotoLinks(storage="linked", naming_pattern="Links/{page}.{ext}"),
        paragraph_styles_found=["Body"],
        paragraph_style_roles={"body": ["Body"]},
        character_size_roles=None,
        headline_font_alternation=None,
        special_pages=[],
        fonts_installed=["Arial"],
        fonts_substituted=[],
        frame_stability="partial",
        samples_analyzed=["issue01"],
        notes="",
    )
    defaults.update(overrides)
    return NewspaperProfile(**defaults)


def _article(
    article_id: str,
    order: int,
    slug: str,
    word_count: int,
    has_image: bool = True,
    text_path: str | None = None,
    image_path: str | None = None,
    title: str = "",
    lead: str = "",
    body: str = "",
    sub_order: int = 0,
) -> dict[str, Any]:
    return {
        "article_id": article_id,
        "order": order,
        "slug": slug,
        "word_count": word_count,
        "image": {"width": 100, "height": 100} if has_image else None,
        "text_path": text_path,
        "image_path": image_path,
        "title": title,
        "lead": lead,
        "body": body,
        "sub_order": sub_order,
    }


def _manifest(pages: list[dict[str, Any]], root: str = "/tmp/issue") -> dict[str, Any]:
    return {"root": root, "pages": pages}


def test_manual_page_is_skipped() -> None:
    profile = _make_profile()
    manifest = _manifest([{"page": "1", "articles": [_article("1_1_a", 1, "a", 100)]}])

    plan = build_layout_plan(manifest, profile)

    assert len(plan.pages) == 1
    assert plan.pages[0].status == "manual"
    assert plan.pages[0].articles == []


def test_uncertain_page_is_skipped() -> None:
    profile = _make_profile(manual_pages_uncertain=[5])
    manifest = _manifest([{"page": "5", "articles": [_article("5_1_a", 1, "a", 100)]}])

    plan = build_layout_plan(manifest, profile)

    assert plan.pages[0].status == "manual_uncertain"


def test_special_page_with_no_automation_is_skipped() -> None:
    profile = _make_profile(
        special_pages=[SpecialPage(pages=[4, 5], description="ТВ-програма", automation="none")]
    )
    manifest = _manifest([{"page": "4", "articles": [_article("4_1_a", 1, "a", 100)]}])

    plan = build_layout_plan(manifest, profile)

    assert plan.pages[0].status == "special"


def test_out_of_range_page_is_flagged() -> None:
    profile = _make_profile(page_count=6)
    manifest = _manifest([{"page": "9", "articles": []}])

    plan = build_layout_plan(manifest, profile)

    assert plan.pages[0].status == "out_of_range"


def test_planned_page_distributes_text_share_proportionally() -> None:
    profile = _make_profile()
    manifest = _manifest(
        [
            {
                "page": "2",
                "articles": [
                    _article(
                        "2_1_a",
                        1,
                        "a",
                        300,
                        text_path="/tmp/issue/2/2_1_a.docx",
                        image_path="/tmp/issue/2/2_1_a.jpg",
                    ),
                    _article("2_2_b", 2, "b", 100, has_image=False),
                ],
            }
        ]
    )

    plan = build_layout_plan(manifest, profile)
    page = plan.pages[0]

    assert page.status == "planned"
    assert page.color_mode == "grayscale"
    assert len(page.articles) == 2
    assert page.articles[0].text_share == 0.75
    assert page.articles[1].text_share == 0.25
    assert page.articles[0].has_image is True
    assert page.articles[1].has_image is False
    assert page.articles[0].image_color_mode == "grayscale"
    assert page.articles[0].text_path == "/tmp/issue/2/2_1_a.docx"
    assert page.articles[0].image_path == "/tmp/issue/2/2_1_a.jpg"
    assert page.articles[1].text_path is None
    assert page.articles[1].image_path is None


def test_empty_automatable_page_is_flagged() -> None:
    profile = _make_profile()
    manifest = _manifest([{"page": "2", "articles": []}])

    plan = build_layout_plan(manifest, profile)

    assert plan.pages[0].status == "empty"
    assert plan.pages[0].color_mode == "grayscale"


def test_missing_automatable_page_produces_warning() -> None:
    profile = _make_profile()
    manifest = _manifest([{"page": "1", "articles": []}])  # only the manual page present

    plan = build_layout_plan(manifest, profile)

    assert any("Сторінка 2" in w for w in plan.warnings)
    assert any("Сторінка 3" in w for w in plan.warnings)
    assert any("Сторінка 4" in w for w in plan.warnings)
    assert any("Сторінка 5" in w for w in plan.warnings)


def test_plan_carries_profile_metadata_for_the_extendscript_executor() -> None:
    profile = _make_profile(
        cmyk_profile="ISOnewspaper26v4",
        fonts_substituted=["EB Garamond"],
        paragraph_style_roles={"headline": ["ZAG"], "body": ["Text"]},
    )
    manifest = _manifest([])

    plan = build_layout_plan(manifest, profile)

    assert plan.newspaper_id == "test_gazeta"
    assert plan.display_name == "Test Gazeta"
    assert plan.cmyk_profile == "ISOnewspaper26v4"
    assert plan.fonts_substituted == ["EB Garamond"]
    assert plan.paragraph_style_roles == {"headline": ["ZAG"], "body": ["Text"]}
    assert plan.min_horizontal_scale == 97
    assert plan.max_horizontal_scale == 102


def test_plan_carries_tbd_paragraph_style_roles_as_is() -> None:
    profile = _make_profile(paragraph_style_roles="TBD")
    manifest = _manifest([])

    plan = build_layout_plan(manifest, profile)

    assert plan.paragraph_style_roles == "TBD"


def test_plan_carries_character_size_roles_fallback() -> None:
    """Dyhovnist-style profiles pass character_size_roles through unchanged
    when paragraph_style_roles is unusable."""

    fallback = {
        "method": "character_point_size",
        "body_point_size_max": 11,
        "headline_like_point_size_min": 13,
    }
    profile = _make_profile(paragraph_style_roles="TBD", character_size_roles=fallback)
    manifest = _manifest([])

    plan = build_layout_plan(manifest, profile)

    assert plan.character_size_roles == fallback


def test_plan_defaults_character_size_roles_to_none_when_not_needed() -> None:
    profile = _make_profile()
    manifest = _manifest([])

    plan = build_layout_plan(manifest, profile)

    assert plan.character_size_roles is None


def test_plan_carries_headline_font_alternation() -> None:
    """Ty i Ya-style profiles pass headline_font_alternation through unchanged."""

    alternation = {
        "method": "alternate_by_article_order_on_page",
        "fonts": ["Comfortaa", "EB Garamond"],
        "confirmed": True,
    }
    profile = _make_profile(headline_font_alternation=alternation)
    manifest = _manifest([])

    plan = build_layout_plan(manifest, profile)

    assert plan.headline_font_alternation == alternation


def test_plan_defaults_headline_font_alternation_to_none_when_unconfirmed() -> None:
    profile = _make_profile()
    manifest = _manifest([])

    plan = build_layout_plan(manifest, profile)

    assert plan.headline_font_alternation is None


def test_pages_are_sorted_by_page_number() -> None:
    profile = _make_profile()
    manifest = _manifest(
        [
            {"page": "6", "articles": []},
            {"page": "1", "articles": []},
        ]
    )

    plan = build_layout_plan(manifest, profile)

    assert [page.page for page in plan.pages] == [1, 6]


def test_planned_page_carries_title_lead_body_for_the_extendscript_executor() -> None:
    profile = _make_profile()
    manifest = _manifest(
        [
            {
                "page": "2",
                "articles": [
                    _article(
                        "2_1_a",
                        1,
                        "a",
                        100,
                        title="Гучний заголовок",
                        lead="Короткий лід.",
                        body="Основний текст статті.",
                    )
                ],
            }
        ]
    )

    plan = build_layout_plan(manifest, profile)
    article = plan.pages[0].articles[0]

    assert article.title == "Гучний заголовок"
    assert article.lead == "Короткий лід."
    assert article.body == "Основний текст статті."


def test_planned_page_defaults_missing_title_lead_body_to_empty_strings() -> None:
    profile = _make_profile()
    manifest = _manifest([{"page": "2", "articles": [_article("2_1_a", 1, "a", 100)]}])
    del manifest["pages"][0]["articles"][0]["title"]
    del manifest["pages"][0]["articles"][0]["lead"]
    del manifest["pages"][0]["articles"][0]["body"]

    plan = build_layout_plan(manifest, profile)
    article = plan.pages[0].articles[0]

    assert article.title == ""
    assert article.lead == ""
    assert article.body == ""


def test_planned_page_carries_sub_order_for_split_articles() -> None:
    """sub_order (tie-break for articles split out of one multi-article
    source file) must reach the plan JSON so the ExtendScript executor can
    sort deterministically even though its Array.sort isn't stable."""

    profile = _make_profile()
    manifest = _manifest(
        [
            {
                "page": "2",
                "articles": [
                    _article("2_1_a", 1, "a", 50, sub_order=0),
                    _article("2_1_a_1", 1, "a", 50, sub_order=1),
                ],
            }
        ]
    )

    plan = build_layout_plan(manifest, profile)
    articles = plan.pages[0].articles

    assert [a.sub_order for a in articles] == [0, 1]


def test_planned_page_defaults_missing_sub_order_to_zero() -> None:
    """Backward compatibility: manifests written before sub_order existed
    (or any article dict omitting it) must default to 0, not error out."""

    profile = _make_profile()
    manifest = _manifest([{"page": "2", "articles": [_article("2_1_a", 1, "a", 100)]}])
    del manifest["pages"][0]["articles"][0]["sub_order"]

    plan = build_layout_plan(manifest, profile)

    assert plan.pages[0].articles[0].sub_order == 0
