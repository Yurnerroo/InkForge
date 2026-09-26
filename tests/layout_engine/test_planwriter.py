"""Tests for inkforge.layout_engine.planwriter."""

from __future__ import annotations

import json
from pathlib import Path

from inkforge.layout_engine.planner import build_layout_plan
from inkforge.layout_engine.planwriter import write_layout_plan
from inkforge.layout_engine.profile import NewspaperProfile, PhotoLinks, Spread


def _profile() -> NewspaperProfile:
    return NewspaperProfile(
        id="test_gazeta",
        display_name="Test Gazeta",
        page_count=3,
        manual_pages=[1],
        manual_pages_uncertain=[],
        spreads=[Spread(pages=[2, 3], color_mode="grayscale")],
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


def test_write_layout_plan_produces_valid_json(tmp_path: Path) -> None:
    manifest = {
        "root": str(tmp_path),
        "pages": [
            {
                "page": "2",
                "articles": [
                    {
                        "article_id": "2_1_a",
                        "order": 1,
                        "slug": "a",
                        "word_count": 10,
                        "image": None,
                        "text_path": "/tmp/issue/2/2_1_a.docx",
                        "image_path": None,
                    }
                ],
            }
        ],
    }
    plan = build_layout_plan(manifest, _profile())
    plan_path = tmp_path / "layout_plan.json"

    write_layout_plan(plan, plan_path)
    data = json.loads(plan_path.read_text(encoding="utf-8"))

    assert data["newspaper_id"] == "test_gazeta"
    assert "generated_at" in data
    assert data["pages"][0]["page"] == 2
    assert data["pages"][0]["articles"][0]["article_id"] == "2_1_a"
    assert data["pages"][0]["articles"][0]["text_path"] == "/tmp/issue/2/2_1_a.docx"
    assert data["paragraph_style_roles"] == {"body": ["Body"]}
    assert data["character_size_roles"] is None
    assert data["headline_font_alternation"] is None
